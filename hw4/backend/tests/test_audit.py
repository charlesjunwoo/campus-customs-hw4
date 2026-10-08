"""Append-only audit trail (Problem 12).

Unit tests write to a temp file; the full-loop test drives the real agent wiring
(tools, fact guard, card contract) with PydanticAI's FunctionModel, so no API calls.
Run from backend/:  .venv/bin/python -m pytest -q
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent  # noqa: E402
import audit  # noqa: E402
import catalog  # noqa: E402
from models import ChatDeps, ShopperProfile, ViewedProduct  # noqa: E402
from pydantic_ai.messages import ModelResponse, ToolCallPart  # noqa: E402
from pydantic_ai.models.function import AgentInfo, FunctionModel  # noqa: E402


def test_append_keeps_earlier_entries_byte_for_byte(tmp_path):
    path = tmp_path / "audit_trail.json"
    audit.append({"n": 1}, path)
    first = path.read_bytes()
    audit.append({"n": 2}, path)
    audit.append({"n": 3}, path)
    data = json.loads(path.read_text())
    assert [e["n"] for e in data] == [1, 2, 3]
    # Everything before the old closing bracket is untouched.
    assert path.read_bytes().startswith(first[: first.rstrip().rfind(b"]")])


def test_append_to_existing_empty_array(tmp_path):
    path = tmp_path / "audit_trail.json"
    path.write_text("[]\n")
    audit.append({"n": 1}, path)
    assert json.loads(path.read_text()) == [{"n": 1}]


def test_corrupt_file_is_never_overwritten(tmp_path):
    path = tmp_path / "audit_trail.json"
    path.write_text("not json at all")
    audit.append({"n": 1}, path)
    assert path.read_text() == "not json at all"
    recovered = tmp_path / "audit_trail.recovered.jsonl"
    assert json.loads(recovered.read_text().strip()) == {"n": 1}


def test_concurrent_appends_stay_valid(tmp_path):
    import threading

    path = tmp_path / "audit_trail.json"
    threads = [threading.Thread(target=audit.append, args=({"n": i}, path)) for i in range(25)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(e["n"] for e in json.loads(path.read_text())) == list(range(25))


def test_short_truncates():
    assert audit.short("x" * 500, 10) == "x" * 9 + "…"
    assert audit.short({"a": 1}) == '{"a":1}'


@pytest.mark.skipif(not catalog.DB_PATH.is_file(), reason="database not present")
def test_full_agent_loop_is_audited(tmp_path, monkeypatch):
    path = tmp_path / "audit_trail.json"
    monkeypatch.setattr(audit, "AUDIT_PATH", path)
    monkeypatch.setenv("PORTKEY_API_KEY", "test-key-not-used")
    agent.build_agent.cache_clear()
    calls = {"n": 0}

    def scripted(messages, info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        final = info.output_tools[0].name
        if calls["n"] == 1:  # look the size up
            return ModelResponse(parts=[ToolCallPart("check_stock", {"product": "yale-grandpa-hoodie", "size": "L"})])
        if calls["n"] == 2:  # invent a number: the fact guard must reject this
            return ModelResponse(parts=[ToolCallPart(final, {"reply": "We have 99 in stock!", "product_ids": []})])
        return ModelResponse(parts=[ToolCallPart(final, {
            "reply": "**Size L is out of stock** for the Yale Grandpa Hoodie.",
            "product_ids": ["yale-grandpa-hoodie"], "results_title": "Yale Grandpa Hoodie"})])

    deps = ChatDeps(
        shopper=ShopperProfile(signed_in=True, first_name="T", email="t@example.com"),
        page_path="/products/yale-grandpa-hoodie",
        viewed_product=ViewedProduct(product_id="yale-grandpa-hoodie", name="Yale Grandpa Hoodie", garment_type="hoodie"),
    )
    try:
        with agent.build_agent().override(model=FunctionModel(scripted)):
            run = asyncio.run(agent.run_chat("is L in stock?", [], deps, audit_meta={"user_id": 42}))
    finally:
        agent.build_agent.cache_clear()

    assert run.cue == "out_of_stock" and run.output.product_ids == ["yale-grandpa-hoodie"]
    [entry] = json.loads(path.read_text())
    types = [s["type"] for s in entry["steps"]]
    assert types.count("tool_call") == 1 and "tool_result" in types and "retry" in types and "final_output" in types
    call = next(s for s in entry["steps"] if s["type"] == "tool_call")
    assert call["tool"] == "check_stock" and "yale-grandpa-hoodie" in call["args"] and call["time"]
    result = next(s for s in entry["steps"] if s["type"] == "tool_result")
    assert '"in_stock":false' in result["result"]
    retry = next(s for s in entry["steps"] if s["type"] == "retry")
    assert "quantity 99" in retry["reason"]
    assert entry["stop_reason"] == "completed" and entry["summary"]["retries"] == 1
    assert entry["shopper"] == {"signed_in": True, "user_id": 42}
    assert "t@example.com" not in path.read_text()  # no emails in the audit log


@pytest.mark.skipif(not catalog.DB_PATH.is_file(), reason="database not present")
def test_failed_run_is_audited_with_stop_reason(tmp_path, monkeypatch):
    path = tmp_path / "audit_trail.json"
    monkeypatch.setattr(audit, "AUDIT_PATH", path)
    monkeypatch.setenv("PORTKEY_API_KEY", "test-key-not-used")
    agent.build_agent.cache_clear()

    def always_invents(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"reply": "Only $1 today!", "product_ids": []})])

    try:
        with agent.build_agent().override(model=FunctionModel(always_invents)):
            with pytest.raises(Exception):
                asyncio.run(agent.run_chat("price?", [], ChatDeps(), audit_meta={"user_id": None}))
    finally:
        agent.build_agent.cache_clear()
    [entry] = json.loads(path.read_text())
    assert entry["stop_reason"] == "retries_exhausted" and entry["output"] is None
    # 1 attempt + OUTPUT_RETRIES retries, every rejection logged
    assert entry["summary"]["model_requests"] == agent.OUTPUT_RETRIES + 1
    assert entry["summary"]["retries"] == agent.OUTPUT_RETRIES
    assert entry["shopper"]["signed_in"] is False


def test_redaction_of_sensitive_text():
    out = audit.short("card 4111 1111 1111 1111, email ada@example.com, my password is hunter2!")
    assert "4111" not in out and "ada@example.com" not in out and "hunter2" not in out
    assert "[card number redacted]" in out and "[email redacted]" in out and "password is [redacted]" in out
    # Ordinary numbers (prices, stock, SKUs, years) survive.
    keep = audit.short("Size M: 25 left at $68, SKU CC-0507-M, class of 2026")
    assert keep == "Size M: 25 left at $68, SKU CC-0507-M, class of 2026"
