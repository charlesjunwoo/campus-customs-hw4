"""The product-card contract (agent.check_products) and how /api/chat hydrates cards.

Run from backend/:  .venv/bin/python -m pytest -q
No model calls: the agent's run is replaced with a canned AgentReply.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent  # noqa: E402
import catalog  # noqa: E402
import main  # noqa: E402
from models import AgentReply  # noqa: E402
from pydantic_ai.messages import ModelRequest, ToolReturnPart  # noqa: E402

pytestmark = pytest.mark.skipif(not catalog.DB_PATH.is_file(), reason="database not present")


def _turn(tool: str, payload: dict) -> list:
    return [ModelRequest(parts=[ToolReturnPart(tool_name=tool, content=json.dumps(payload), tool_call_id="1")])]


SEARCH = _turn(
    "search_products",
    {"products": [
        {"product_id": "yale-dad-hoodie", "name": "Yale Dad Hoodie"},
        {"product_id": "yale-dad-crewneck", "name": "Yale Dad Crewneck"},
    ]},
)


def test_contract_accepts_listed_matches():
    out = AgentReply(reply="Try the **Yale Dad Hoodie**!", product_ids=["yale-dad-hoodie"], results_title="For Dad")
    assert agent.check_products(SEARCH, out) == []


def test_contract_requires_cards_when_search_found_matches():
    out = AgentReply(reply="We have a couple of dad options!")
    assert any("product_ids is empty" in p for p in agent.check_products(SEARCH, out))


def test_contract_requires_every_mentioned_product():
    out = AgentReply(
        reply="The Yale Dad Hoodie and the Yale Dad Crewneck are both great.",
        product_ids=["yale-dad-hoodie"],
        results_title="For Dad",
    )
    assert any("yale-dad-crewneck" in p for p in agent.check_products(SEARCH, out))


def test_contract_rejects_ids_not_returned_this_turn():
    out = AgentReply(reply="Here you go", product_ids=["yale-dad-hoodie", "made-up-id"], results_title="x")
    assert any("made-up-id" in p for p in agent.check_products(SEARCH, out))


def test_contract_requires_title_with_cards():
    out = AgentReply(reply="Yale Dad Hoodie!", product_ids=["yale-dad-hoodie"])
    assert any("results_title" in p for p in agent.check_products(SEARCH, out))


def test_no_products_no_cards_is_fine():
    assert agent.check_products([], AgentReply(reply="Hi! What can I help you find?")) == []


def test_chat_route_hydrates_cards_from_database(monkeypatch):
    async def fake_run_chat(message, history, deps, audit_meta=None):
        out = AgentReply(
            reply="Here are two picks.",
            product_ids=["yale-dad-hoodie", "not-a-real-id", "basic-hoodie-big-yale"],
            results_title="Hoodies for Dad",
        )
        return agent.ChatRun(output=out, tools_used=["search_products"], cue="found")

    monkeypatch.setattr(agent, "run_chat", fake_run_chat)
    body = TestClient(main.app).post("/api/chat", json={"message": "hoodie for dad"}).json()
    assert body["results"]["title"] == "Hoodies for Dad"
    cards = body["results"]["products"]
    assert [c["product_id"] for c in cards] == ["yale-dad-hoodie", "basic-hoodie-big-yale"]  # fake id dropped
    db = catalog.get_product("yale-dad-hoodie")
    assert cards[0]["name"] == db.name and cards[0]["price"] == db.price
    assert cards[0]["image_url"] == "/media/products/yale-dad-hoodie.jpg" and cards[0]["one_liner"]


def test_chat_route_without_matches_has_no_results(monkeypatch):
    async def fake_run_chat(message, history, deps, audit_meta=None):
        return agent.ChatRun(output=AgentReply(reply="Hi there!"), tools_used=[], cue=None)

    monkeypatch.setattr(agent, "run_chat", fake_run_chat)
    body = TestClient(main.app).post("/api/chat", json={"message": "hello"}).json()
    assert body["results"] is None


TRUNCATED = _turn(
    "search_products",
    {"total_matches": 28, "showing": 2, "products": [
        {"product_id": "yale-dad-crewneck", "name": "Yale Dad Crewneck"},
        {"product_id": "yale-mom-crewneck", "name": "Yale Mom Crewneck"},
    ]},
)


def test_truncated_search_count_must_be_the_total():
    ids = ["yale-dad-crewneck", "yale-mom-crewneck"]
    bad = AgentReply(reply="I found 2 crewnecks for you!", product_ids=ids, results_title="Crewnecks")
    assert any("there are 28 matches" in p for p in agent.check_products(TRUNCATED, bad))
    good = AgentReply(reply="We have 28 crewnecks; here are 2 to start.", product_ids=ids, results_title="Crewnecks")
    assert agent.check_products(TRUNCATED, good) == []
