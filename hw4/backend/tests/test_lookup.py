"""Lookup tools and fact guard, checked against campus_customs.db directly.

Run from backend/:  .venv/bin/python -m pytest -q
No model calls; these tests are free and deterministic.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import catalog  # noqa: E402
from agent import check_facts  # noqa: E402
from models import NotFound, ProductLookup, SearchResults, StockCheck  # noqa: E402
from pydantic_ai.messages import ModelRequest, ToolReturnPart, UserPromptPart  # noqa: E402
from tools import check_stock, get_product_details, normalize_size, search_products  # noqa: E402

pytestmark = pytest.mark.skipif(not catalog.DB_PATH.is_file(), reason="database not present")
CTX = None  # tools never touch ctx


def raw_rows():
    conn = sqlite3.connect(f"file:{catalog.DB_PATH}?mode=ro", uri=True)
    products = conn.execute("SELECT product_id, name, price, description FROM catalogue").fetchall()
    stock = {}
    for pid, size, qty in conn.execute("SELECT product_id, size, quantity FROM inventory"):
        stock.setdefault(pid, {})[size] = qty
    conn.close()
    return products, stock


PRODUCTS, STOCK = raw_rows()


@pytest.mark.parametrize("pid,name,price,description", PRODUCTS, ids=[p[0] for p in PRODUCTS])
def test_details_match_database_exactly(pid, name, price, description):
    r = get_product_details(CTX, pid)
    assert isinstance(r, ProductLookup)
    assert r.name == name and r.price_usd == price
    if "filename-based stub" not in description:
        assert r.description == description
    assert {s.size: s.quantity for s in r.stock_by_size} == STOCK[pid]
    assert r.total_units == sum(STOCK[pid].values())
    assert set(r.sizes_out_of_stock) == {s for s, q in STOCK[pid].items() if q == 0}
    for s in r.stock_by_size:
        assert s.in_stock == (s.quantity > 0)


def test_every_size_check_is_definitive():
    checked = out = 0
    for pid, sizes in STOCK.items():
        for size, qty in sizes.items():
            r = check_stock(CTX, pid, size)
            assert isinstance(r, StockCheck)
            assert r.quantity == qty and r.in_stock == (qty > 0) and r.offered
            assert size not in r.other_sizes_in_stock
            checked += 1
            out += qty == 0
    assert checked == 612 and out == 145  # every inventory row; matches harness §1


def test_size_words_and_names_resolve():
    assert normalize_size("medium") == "M" and normalize_size("extra large") == "XL"
    assert normalize_size("2xl") == "XXL" and normalize_size("huge") is None
    r = check_stock(CTX, "Yale Grandpa Hoodie", "large")
    assert isinstance(r, StockCheck) and r.size == "L" and r.in_stock is False and r.quantity == 0


def test_unknown_product_and_size_never_guess():
    assert isinstance(get_product_details(CTX, "yale-pink-unicorn-onesie"), NotFound)
    assert isinstance(check_stock(CTX, "yale-dad-hoodie", "XXXL"), NotFound)
    vague = get_product_details(CTX, "hoodie")
    assert isinstance(vague, NotFound) and vague.did_you_mean  # ambiguous -> suggestions


def test_search_size_filter_only_returns_in_stock():
    r = search_products(CTX, "hoodie", size="L")
    assert isinstance(r, SearchResults) and r.total_matches > 0
    for hit in r.products:
        assert STOCK[hit.product_id]["L"] > 0


# ---------------------------------------------------------------- fact guard


def _msgs(tool_json: str, user: str = "hi"):
    return [
        ModelRequest(parts=[UserPromptPart(content=user)]),
        ModelRequest(parts=[ToolReturnPart(tool_name="get_product_details", content=tool_json, tool_call_id="1")]),
    ]


def test_fact_guard_accepts_tool_backed_numbers():
    msgs = _msgs('{"price_usd": 68.0, "stock_by_size": [{"size": "XL", "quantity": 2}]}')
    assert check_facts(msgs, "It's **$68**, and XL is in stock (only 2 left).") == []


def test_fact_guard_rejects_invented_numbers():
    msgs = _msgs('{"price_usd": 68.0, "quantity": 2}')
    assert "price $59.99" in check_facts(msgs, "It's $59.99 today!")
    assert "quantity 14" in check_facts(msgs, "We have 14 in stock.")


def test_fact_guard_requires_a_lookup():
    msgs = [ModelRequest(parts=[UserPromptPart(content="price of the dad hoodie?")])]
    assert "no lookup tool was called this turn" in check_facts(msgs, "It's $68.")


def test_fact_guard_allows_shopper_numbers():
    msgs = [ModelRequest(parts=[UserPromptPart(content="anything under $70?")])]
    assert check_facts(msgs, "Sure, let me look for things under $70.") == []


def test_color_filter_uses_listed_colors_only():
    conn = sqlite3.connect(f"file:{catalog.DB_PATH}?mode=ro", uri=True)
    expected = {
        pid for pid, colors in conn.execute("SELECT product_id, colors FROM catalogue")
        if any(c.lower().split()[0] == "red" or " red" in f" {c.lower()}" for c in json.loads(colors))
    }
    conn.close()
    r = search_products(CTX, color="red")
    assert isinstance(r, SearchResults)
    assert {h.product_id for h in r.products} == expected and r.total_matches == len(expected)


def test_search_matches_whole_words_not_substrings():
    # "red" must not match "featured"/"embroidered"; Boola Boola tee has no red.
    ids = {c.product_id for c in catalog.search_products("red")}
    assert "boola-boola-t-shirt" not in ids and "divinity-school-fleece-sweater" not in ids
