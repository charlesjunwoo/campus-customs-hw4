"""Customer memory: saved chat history for signed-in shoppers.

Storage is the existing `chat_messages` table in campus_customs.db:
    id, user_id -> users.id, role ('user' | 'assistant'), content, products_json, created_at

products_json holds the product cards shown with an assistant message, as
    {"title": "Navy hockey hoodies", "product_ids": ["ice-hockey-left-chest-hoodie", ...]}
Only ids are stored. When history reloads, cards are rebuilt from the catalogue,
so prices and stock are always current. (Rows written before this module stored a
list of full product dicts; those still load, again using only their ids.)

Signed-out shoppers are never written here.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import catalog
from datetime import datetime

from models import ChatResults, ChatTurn, Recap, ShopperProfile, StoredMessage, ViewedProduct

UI_HISTORY_LIMIT = 100  # messages sent back to the site on reload
AGENT_HISTORY_TURNS = 12  # messages replayed to the model for context (cost guard)

_db_path: Path | None = None


def init(db_path: Path) -> None:
    global _db_path
    _db_path = db_path
    if not db_path.is_file():
        return
    with _connect() as conn:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages (user_id, id)"
        )


def _connect() -> sqlite3.Connection:
    if _db_path is None or not _db_path.is_file():
        raise catalog.DatabaseMissing(f"Database not found at {_db_path}")
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------- encode / decode


def _encode(results: ChatResults | None) -> str | None:
    if not results or not results.products:
        return None
    return json.dumps({"title": results.title, "product_ids": [p.product_id for p in results.products]})


def _decode(raw: str | None) -> tuple[str, list[str]] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if isinstance(data, dict):  # current format
        ids = [i for i in data.get("product_ids", []) if isinstance(i, str)]
        title = data.get("title") or "Earlier picks"
    elif isinstance(data, list):  # legacy: list of full product dicts
        ids = [d["product_id"] for d in data if isinstance(d, dict) and isinstance(d.get("product_id"), str)]
        title = "Earlier picks"
    else:
        return None
    return (title, ids) if ids else None


# ---------------------------------------------------------------- read / write


def save_exchange(user_id: int, user_text: str, reply: str, results: ChatResults | None) -> None:
    """Store one user message and the assistant's reply together (one transaction)."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)", (user_id, user_text)
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, reply, _encode(results)),
        )


def _recent_rows(user_id: int, limit: int) -> list[sqlite3.Row]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT id, role, content, products_json, created_at FROM chat_messages
               WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return list(reversed(rows))


def load_messages(user_id: int, limit: int = UI_HISTORY_LIMIT) -> list[StoredMessage]:
    """History for the site, with product cards rebuilt from the current catalogue."""
    out = []
    for row in _recent_rows(user_id, limit):
        if row["role"] not in ("user", "assistant"):
            continue
        results = None
        decoded = _decode(row["products_json"])
        if decoded:
            cards = catalog.get_cards(decoded[1])
            results = ChatResults(title=decoded[0], products=cards) if cards else None
        out.append(
            StoredMessage(
                id=row["id"], role=row["role"], content=row["content"], results=results, created_at=row["created_at"]
            )
        )
    return out


def agent_history(user_id: int, turns: int = AGENT_HISTORY_TURNS) -> list[ChatTurn]:
    """Recent history for the model. Assistant turns note which cards were shown, so
    "the second one" can be resolved; prices/stock are deliberately not included."""
    history = []
    for row in _recent_rows(user_id, turns):
        if row["role"] not in ("user", "assistant"):
            continue
        content = row["content"]
        decoded = _decode(row["products_json"]) if row["role"] == "assistant" else None
        if decoded:
            names = {c.product_id: c.name for c in catalog.get_cards(decoded[1])}
            shown = "; ".join(f"{i + 1}. {names[pid]} ({pid})" for i, pid in enumerate(decoded[1]) if pid in names)
            if shown:
                content += f"\n\n[Cards shown, in order: {shown}]"
        history.append(ChatTurn(role=row["role"], content=content[:4000]))
    return history


def recent_product_ids(user_id: int, limit: int = 3, scan: int = 60) -> list[str]:
    """Most recently shown products in this shopper's saved chat, newest first, unique.

    The top pick of each reply comes first, so "what we talked about" favors the
    products the conversation was actually about over long alternative lists.
    """
    with _connect() as conn:
        rows = conn.execute(
            """SELECT products_json FROM chat_messages
               WHERE user_id = ? AND role = 'assistant' AND products_json IS NOT NULL
               ORDER BY id DESC LIMIT ?""",
            (user_id, scan),
        ).fetchall()
    decoded = [d[1] for r in rows if (d := _decode(r["products_json"]))]
    ordered: list[str] = []
    for ids in decoded:  # first pass: each reply's top pick
        if ids[0] not in ordered:
            ordered.append(ids[0])
    for ids in decoded:  # then the rest, if we still need more
        ordered += [i for i in ids if i not in ordered]
    return ordered[:limit]


def recent_products(user_id: int, limit: int = 3) -> list[ViewedProduct]:
    out = []
    for pid in recent_product_ids(user_id, limit):
        p = catalog.get_product(pid)
        if p:
            out.append(ViewedProduct(product_id=p.product_id, name=p.name, garment_type=p.garment_type))
    return out


def _when(ts: str | None) -> str:
    try:
        return datetime.strptime(ts or "", "%Y-%m-%d %H:%M:%S").strftime("%b %-d")
    except ValueError:
        return "your last visit"


def recap(user_id: int, first_name: str | None) -> Recap | None:
    """Deterministic welcome-back message: what they looked at last time, with today's
    price and availability read from the catalogue. No model call: free, instant, and
    every number comes straight from the database."""
    rows = _recent_rows(user_id, 1)
    if not rows:
        return None
    ids = recent_product_ids(user_id)
    hello = f"Welcome back, {first_name}!" if first_name else "Welcome back!"
    if not ids:
        return Recap(text=f"{hello} Your chat from {_when(rows[-1]['created_at'])} is below. What can I find for you today?")
    lines = [f"{hello} Last time ({_when(rows[-1]['created_at'])}) you were looking at these. Here's where they stand today:"]
    cards = []
    for pid in ids:
        p = catalog.get_product(pid)
        if p is None:
            continue
        cards.append(catalog.get_cards([pid])[0])
        in_stock = [s.size for s in p.inventory if s.quantity > 0]
        low = [f"{s.size} ({s.quantity} left)" for s in p.inventory if 0 < s.quantity <= catalog.LOW_STOCK]
        if not in_stock:
            status = "sold out in every size right now"
        else:
            status = f"in stock in {', '.join(in_stock)}"
            if low:
                status += f"; running low: {', '.join(low)}"
        lines.append(f"- **{p.name}**: ${p.price:g}, {status}")
    lines.append("Want me to check a size, or find something new?")
    return Recap(text="\n".join(lines), products=cards)


def clear(user_id: int) -> int:
    with _connect() as conn:
        return conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,)).rowcount


def shopper_profile(user_id: int) -> ShopperProfile | None:
    """What the agent may know about the signed-in shopper (no id, no password hash)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT name, email, first_name, last_name, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        count = conn.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (user_id,)).fetchone()[0]
    name = (row["name"] or "").split(" ", 1)
    return ShopperProfile(
        signed_in=True,
        first_name=row["first_name"] or name[0] or None,
        last_name=row["last_name"] or (name[1] if len(name) > 1 else None),
        email=row["email"],
        member_since=(row["created_at"] or "")[:10] or None,
        saved_messages=count,
    )
