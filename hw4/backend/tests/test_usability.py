"""Problem 9 improvements: SKUs, sound cues, and the returning-shopper recap.

Run from backend/:  .venv/bin/python -m pytest -q   (no model calls)
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent  # noqa: E402
import catalog  # noqa: E402
import main  # noqa: E402
import memory  # noqa: E402
from models import AgentReply, StockCheck  # noqa: E402
from pydantic_ai.messages import ModelRequest, ToolReturnPart  # noqa: E402
from tools import check_stock  # noqa: E402

from test_memory import PASSWORD, _signup, db  # noqa: E402,F401  (fixture reuse)

pytestmark = pytest.mark.skipif(not catalog.DB_PATH.is_file(), reason="database not present")


# ---------------------------------------------------------------- SKUs


def test_every_size_has_a_unique_db_backed_sku():
    conn = sqlite3.connect(f"file:{catalog.DB_PATH}?mode=ro", uri=True)
    rows = conn.execute("SELECT id, product_id, size FROM inventory").fetchall()
    conn.close()
    seen = set()
    for inv_id, pid, size in rows:
        sku = next(s.sku for s in catalog.get_product(pid).inventory if s.size == size)
        assert sku == f"CC-{inv_id:04d}-{size}" and re.fullmatch(r"CC-\d{4}-(XS|S|M|L|XL|XXL)", sku)
        seen.add(sku)
    assert len(seen) == len(rows) == 612


def test_sku_reaches_api_and_tools():
    body = TestClient(main.app).get("/api/products/yale-dad-hoodie").json()
    assert all(s["sku"].startswith("CC-") for s in body["inventory"])
    r = check_stock(None, "yale-dad-hoodie", "M")
    assert isinstance(r, StockCheck) and r.sku == next(s["sku"] for s in body["inventory"] if s["size"] == "M")


# ---------------------------------------------------------------- sound cues


def _ret(tool: str, payload: dict):
    return ModelRequest(parts=[ToolReturnPart(tool_name=tool, content=json.dumps(payload), tool_call_id=tool)])


def test_cue_comes_from_tool_facts():
    none = AgentReply(reply="x")
    shown = AgentReply(reply="x", product_ids=["a"], results_title="t")
    sold_out = _ret("check_stock", {"found": True, "in_stock": False})
    available = _ret("check_stock", {"found": True, "in_stock": True})
    empty = _ret("search_products", {"total_matches": 0, "showing": 0, "products": []})
    assert agent.pick_cue([sold_out], shown) == "out_of_stock"  # size check beats cards
    assert agent.pick_cue([available], none) == "in_stock"
    assert agent.pick_cue([], shown) == "found"
    assert agent.pick_cue([empty], none) == "no_match"
    assert agent.pick_cue([], none) is None


def test_chat_response_carries_cue(monkeypatch):
    async def fake(message, history, deps, audit_meta=None):
        return agent.ChatRun(output=AgentReply(reply="Sold out in L."), tools_used=["check_stock"], cue="out_of_stock")

    monkeypatch.setattr(agent, "run_chat", fake)
    assert TestClient(main.app).post("/api/chat", json={"message": "L?"}).json()["cue"] == "out_of_stock"


# ---------------------------------------------------------------- recap


def test_recap_for_returning_shopper_uses_live_db_values(db):
    client = TestClient(main.app)
    _signup(client, "recap.test@example.com")
    assert client.get("/api/chat/history").json()["recap"] is None  # brand-new: nothing to recap
    client.post("/api/chat", json={"message": "a dad hoodie please"})
    recap = client.get("/api/chat/history").json()["recap"]
    p = catalog.get_product("yale-dad-hoodie")
    assert recap["text"].startswith("Welcome back, Mia!")
    assert f"**{p.name}**: ${p.price:g}" in recap["text"]
    assert [c["product_id"] for c in recap["products"]] == ["yale-dad-hoodie"]


def test_recent_products_reach_agent_deps(db):
    _, calls = db
    client = TestClient(main.app)
    _signup(client, "recent.test@example.com")
    client.post("/api/chat", json={"message": "a dad hoodie please"})
    client.post("/api/chat", json={"message": "and that one from before?"})
    assert [p.product_id for p in calls[-1]["deps"].recent_products] == ["yale-dad-hoodie"]
    assert "Yale Dad Hoodie" in agent.build_session_context(calls[-1]["deps"])
