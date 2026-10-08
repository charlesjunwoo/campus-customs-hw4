"""Append-only audit trail of every agent run: output/audit_trail.json.

One entry per /api/chat agent run, with an ordered `steps` list of everything that
happened inside the loop (model responses, tool calls with short args, tool results,
validator retries), token usage, the final output, and the stop reason.

Append-only, never wiped:
  * The file is a single JSON array, so it always opens as valid JSON.
  * New entries are written by overwriting only the closing "]" at the end of the file
    (", {entry}\\n]"). Earlier bytes are never rewritten, truncated, or reordered.
  * A process lock plus an OS file lock (fcntl) keep concurrent requests from interleaving.
  * If the file is ever not a JSON array (e.g. hand-edited), it is left untouched and new
    entries go to audit_trail.recovered.jsonl instead. Nothing is ever deleted.

Privacy: shoppers are recorded by numeric user_id (or "guest"), never by name. Every
text field passes through redact(), which masks card-like numbers, email addresses,
and anything following "password", and is then truncated.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = Path(os.getenv("CC_AUDIT_PATH", PROJECT_ROOT / "output" / "audit_trail.json"))

ARG_LIMIT = 200  # characters kept from tool arguments
RESULT_LIMIT = 300  # characters kept from tool results / replies / messages

log = logging.getLogger("campus_customs.audit")
_lock = threading.Lock()


# 13-19 digits, optionally separated by spaces or dashes (payment cards).
CARD_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PASSWORD_RE = re.compile(r"(?i)(pass(?:word|code)?|pwd)(\s*(?:is|=|:)?\s*)(\S+)")


def redact(text: str) -> str:
    text = CARD_RE.sub("[card number redacted]", text)
    text = EMAIL_RE.sub("[email redacted]", text)
    return PASSWORD_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted]", text)


def iso(dt: datetime | None = None) -> str:
    """UTC timestamp with milliseconds, e.g. 2026-10-08T03:01:51.899Z."""
    dt = (dt or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def now_iso() -> str:
    return iso()


def short(value: Any, limit: int = RESULT_LIMIT) -> str:
    """Compact one-line text for the log, truncated with an ellipsis."""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
        except (TypeError, ValueError):
            value = str(value)
    value = redact(" ".join(value.split()))
    return value if len(value) <= limit else value[: limit - 1] + "…"


def append(entry: dict, path: Path | None = None) -> None:
    """Append one entry to the audit array without touching earlier entries."""
    path = path or AUDIT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(entry, ensure_ascii=False, indent=2)
    body = "\n".join("  " + line for line in body.splitlines()).encode("utf-8")

    with _lock:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        with os.fdopen(fd, "r+b") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size == 0:
                    f.write(b"[\n" + body + b"\n]\n")
                    return
                # Find the closing bracket among the last bytes (skipping trailing whitespace).
                tail_len = min(size, 64)
                f.seek(size - tail_len)
                tail = f.read(tail_len)
                stripped = tail.rstrip()
                if not stripped.endswith(b"]"):
                    raise ValueError("audit file does not end with ']'")
                bracket = size - tail_len + len(stripped) - 1
                # Is the array empty ("[]")? Then no comma is needed.
                f.seek(0)
                empty = f.read(min(size, 64)).strip() in (b"[]", b"[\n]")
                f.seek(bracket)
                f.truncate()
                f.write((b"\n" if empty else b",\n") + body + b"\n]\n")
            except ValueError:
                recovered = path.with_name(path.stem + ".recovered.jsonl")
                with recovered.open("a", encoding="utf-8") as r:
                    r.write(json.dumps(entry, ensure_ascii=False) + "\n")
                log.warning("audit file %s is not a JSON array; wrote entry to %s", path, recovered)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def safe_append(entry: dict, path: Path | None = None) -> None:
    """Auditing must never break a shopper's chat: log and continue on any failure."""
    try:
        append(entry, path)
    except Exception:  # noqa: BLE001
        log.exception("could not write audit entry")
