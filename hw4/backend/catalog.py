"""Read-only access to the catalogue and inventory tables.

Shared by the REST routes in main.py and the agent's tools in tools.py, so the
website and the chatbot always see the same prices and stock.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from models import Category, Collection, ProductCard, ProductDetail, SizeStock, StockStatus

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("CC_DATA_DIR", PROJECT_ROOT / "data"))
DB_PATH = DATA_DIR / "campus_customs.db"
PRODUCTS_DIR = DATA_DIR / "products"

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
LOW_STOCK = 5

# garment_type in the catalogue is free text ("short-sleeve T-shirt", "t-shirt", ...),
# so collapse it into a few shopper-friendly categories. First match wins.
CATEGORY_RULES: list[tuple[str, str]] = [
    ("quarter-zip", "Quarter-Zips"),
    ("jacket", "Jackets & Fleece"),
    ("hood", "Hoodies"),
    ("t-shirt", "T-Shirts"),
    ("performance", "Long Sleeves"),
    ("crew", "Crewnecks"),
    ("mockneck", "Crewnecks"),
]

# Shop-by collections, modeled on the reference store's menus (residential
# colleges, sports, relatives, graduate schools). Matched against product names.
COLLECTIONS: dict[str, tuple[str, list[str]]] = {
    "residential-colleges": ("Residential Colleges", [
        "Benjamin Franklin", "Berkeley", "Branford", "Davenport", "Ezra Stiles", "Grace Hopper",
        "Jonathan Edwards", "Morse", "Pauli Murray", "Pierson", "Saybrook", "Silliman",
        "Timothy Dwight", "Trumbull",
    ]),
    "athletics": ("Athletics", [
        "Baseball", "Basketball", "Crew Left", "Diving", "Fencing", "Field Hockey", "Football",
        "Golf", "Hockey", "Lacrosse", "Sailing", "Soccer", "Squash", "Swimming", "Tennis",
        "Track", "Volleyball",
    ]),
    "family": ("Bulldog Family", [
        "Mom", "Dad", "Aunt", "Uncle", "Brother", "Sister", "Cousin", "Grandma", "Grandpa",
    ]),
    "graduate-schools": ("Graduate & Professional Schools", [
        "School Of", "Law School", "Divinity School", "Forest School",
    ]),
}

# Words that carry no product meaning in a shopper's query.
STOP_WORDS = {
    "a", "an", "and", "any", "are", "do", "for", "have", "i", "in", "is", "me", "my", "of",
    "on", "or", "show", "some", "something", "the", "to", "want", "with", "you", "your",
}

CARD_SQL = """
SELECT c.product_id, c.name, c.garment_type, c.description, c.colors,
       c.search_tags, c.image_file_path, c.price,
       COALESCE(SUM(i.quantity), 0)                         AS total_stock,
       COALESCE(SUM(CASE WHEN i.quantity > 0 THEN 1 END), 0) AS sizes_in_stock
FROM catalogue c
LEFT JOIN inventory i ON i.product_id = c.product_id
"""


class DatabaseMissing(RuntimeError):
    pass


def connect() -> sqlite3.Connection:
    if not DB_PATH.is_file():
        raise DatabaseMissing(f"Database not found at {DB_PATH}")
    # Read-only: catalogue and inventory are never written here (auth.py owns user writes).
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------- helpers


def category_for(garment_type: str) -> str:
    g = garment_type.lower()
    for needle, label in CATEGORY_RULES:
        if needle in g:
            return label
    return "Other"


def clean_description(row: sqlite3.Row) -> str:
    """A few catalogue rows hold an image-pipeline placeholder instead of real copy."""
    desc = row["description"]
    if "filename-based stub" in desc:
        return f"{row['name']}: a Yale {row['garment_type'].lower()} from Campus Customs. Full details coming soon."
    return desc


def one_liner(description: str, limit: int = 90) -> str:
    """Short card blurb: the first clause of the description, trimmed."""
    first = re.split(r"(?<=[.!?])\s", description.strip(), maxsplit=1)[0]
    first = re.split(r",\s(?:with|featuring)\s", first, maxsplit=1)[0].rstrip(".")
    if len(first) > limit:
        first = first[:limit].rsplit(" ", 1)[0] + "…"
    return first


def image_url(path: str) -> str:
    # Catalogue paths look like "products/<slug>.jpg"
    return f"/media/{path.lstrip('/')}"


def in_collection(name: str, slug: str) -> bool:
    return any(re.search(rf"\b{re.escape(k)}\b", name, re.IGNORECASE) for k in COLLECTIONS[slug][1])


def stock_status(quantity: int) -> StockStatus:
    if quantity == 0:
        return "sold_out"
    if quantity <= LOW_STOCK:
        return "low"
    return "in_stock"


def sku_for(inventory_id: int, size: str) -> str:
    """Stock-keeping unit for one product in one size.

    Each inventory row *is* one sellable unit type (product x size), and its INTEGER
    PRIMARY KEY never changes, so it is the natural SKU key: CC-0123-M.
    """
    return f"CC-{inventory_id:04d}-{size}"


def query_terms(q: str) -> list[str]:
    """Split a free-text query into search terms ("navy hoodies" -> ["navy", "hoodie"])."""
    terms = []
    for word in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", q.lower()):
        if word in STOP_WORDS:
            continue
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]  # crude plural: hoodies -> hoodie, crewnecks -> crewneck
        terms.append(word)
    return terms


def row_to_card(row: sqlite3.Row) -> ProductCard:
    return ProductCard(
        product_id=row["product_id"],
        name=row["name"],
        category=category_for(row["garment_type"]),
        garment_type=row["garment_type"],
        one_liner=one_liner(clean_description(row)),
        price=row["price"],
        image_url=image_url(row["image_file_path"]),
        total_stock=row["total_stock"],
        sizes_in_stock=row["sizes_in_stock"],
        status=stock_status(row["total_stock"]),
    )


# ---------------------------------------------------------------- queries


def _matches(term: str, text: str) -> bool:
    """Whole-word (prefix) match: "red" matches "red" and "reds", not "featured"."""
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}", text) is not None


def search_products(
    q: str | None = None,
    category: str | None = None,
    collection: str | None = None,
    max_price: float | None = None,
    color: str | None = None,
) -> list[ProductCard]:
    """Every query term must start a word in the name, description, colors, tags, or type.

    `color` matches only the product's listed colors (e.g. "red" -> colors containing a
    word starting with "red"), so accent colors in descriptions don't count.
    """
    sql, params = CARD_SQL, []
    if max_price is not None:
        sql += " WHERE c.price <= ?"
        params.append(max_price)
    sql += " GROUP BY c.product_id ORDER BY c.name"
    terms = query_terms(q or "")
    color_terms = query_terms(color or "")
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    cards = []
    for r in rows:
        haystack = " ".join(
            [r["name"], r["description"], r["colors"], r["search_tags"], r["garment_type"]]
        ).lower()
        if not all(_matches(t, haystack) for t in terms):
            continue
        if color_terms:
            colors = " ".join(json.loads(r["colors"])).lower()
            if not all(_matches(t, colors) for t in color_terms):
                continue
        cards.append(row_to_card(r))
    if category:
        cards = [c for c in cards if c.category.lower() == category.lower()]
    if collection:
        cards = [c for c in cards if in_collection(c.name, collection)]
    return cards


def get_cards(product_ids: list[str]) -> list[ProductCard]:
    """Cards for the given ids, in the given order; unknown ids are dropped."""
    if not product_ids:
        return []
    marks = ",".join("?" * len(product_ids))
    with connect() as conn:
        rows = conn.execute(
            CARD_SQL + f" WHERE c.product_id IN ({marks}) GROUP BY c.product_id", product_ids
        ).fetchall()
    by_id = {r["product_id"]: row_to_card(r) for r in rows}
    return [by_id[i] for i in dict.fromkeys(product_ids) if i in by_id]


def get_product(product_id: str) -> ProductDetail | None:
    with connect() as conn:
        row = conn.execute(
            CARD_SQL + " WHERE c.product_id = ? GROUP BY c.product_id", (product_id,)
        ).fetchone()
        if row is None:
            return None
        inv = {
            r["size"]: (r["quantity"], r["id"])
            for r in conn.execute("SELECT id, size, quantity FROM inventory WHERE product_id = ?", (product_id,))
        }
    sizes = sorted(inv, key=lambda s: SIZE_ORDER.index(s) if s in SIZE_ORDER else 99)
    return ProductDetail(
        **row_to_card(row).model_dump(),
        description=clean_description(row),
        colors=json.loads(row["colors"]),
        search_tags=json.loads(row["search_tags"]),
        inventory=[
            SizeStock(size=s, quantity=inv[s][0], status=stock_status(inv[s][0]), sku=sku_for(inv[s][1], s))
            for s in sizes
        ],
    )


def list_categories() -> list[Category]:
    counts: dict[str, int] = {}
    with connect() as conn:
        for (garment_type,) in conn.execute("SELECT garment_type FROM catalogue"):
            label = category_for(garment_type)
            counts[label] = counts.get(label, 0) + 1
    return [Category(name=k, count=v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]


def list_collections() -> list[Collection]:
    with connect() as conn:
        names = [n for (n,) in conn.execute("SELECT name FROM catalogue")]
    return [
        Collection(slug=slug, name=label, count=sum(in_collection(n, slug) for n in names))
        for slug, (label, _) in COLLECTIONS.items()
    ]
