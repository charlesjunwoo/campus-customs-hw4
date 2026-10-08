"""Tools the Campus Customs agent can call.

All tools are read-only views of campus_customs.db (via catalog.py), queried
fresh on every call, and return typed models from models.py (PydanticAI sends
them to the model as JSON). Lookups never guess: an unknown product or size
returns NotFound with real suggestions. The only user data any tool exposes is
the signed-in shopper's own profile (get_current_user), taken from ctx.deps, which
the server builds from the session cookie. No tool can see other users, user ids,
password hashes, or sessions.
"""

from __future__ import annotations

import re

from pydantic_ai import RunContext

import catalog
from models import (
    ChatDeps,
    NotFound,
    ProductDetail,
    ProductLookup,
    SearchHit,
    SearchResults,
    ShopperProfile,
    SizeAvailability,
    StockCheck,
)

MAX_SEARCH_RESULTS = 12
SIZES = catalog.SIZE_ORDER

# Spoken size names -> catalogue codes.
SIZE_ALIASES = {
    "xs": "XS", "extra small": "XS", "x-small": "XS", "xsmall": "XS",
    "s": "S", "small": "S", "sm": "S",
    "m": "M", "medium": "M", "med": "M",
    "l": "L", "large": "L", "lg": "L",
    "xl": "XL", "extra large": "XL", "x-large": "XL", "xlarge": "XL",
    "xxl": "XXL", "2xl": "XXL", "xx-large": "XXL", "xxlarge": "XXL", "double xl": "XXL",
}


# ---------------------------------------------------------------- helpers


def normalize_size(size: str) -> str | None:
    key = re.sub(r"\s+", " ", size.strip().lower())
    return SIZE_ALIASES.get(key) or (key.upper() if key.upper() in SIZES else None)


def _state(quantity: int) -> str:
    if quantity == 0:
        return "out_of_stock"
    return "low_stock" if quantity <= catalog.LOW_STOCK else "in_stock"


def _sizes_in_stock(detail: ProductDetail) -> list[str]:
    return [s.size for s in detail.inventory if s.quantity > 0]


def _hit(detail: ProductDetail) -> SearchHit:
    return SearchHit(
        product_id=detail.product_id,
        name=detail.name,
        category=detail.category,
        price_usd=detail.price,
        summary=detail.one_liner,
        total_units=detail.total_stock,
        sizes_in_stock=_sizes_in_stock(detail),
    )


def _resolve(product: str) -> ProductDetail | NotFound:
    """Find one product by exact id or exact name; otherwise suggest, never guess."""
    key = product.strip()
    detail = catalog.get_product(key) or catalog.get_product(key.lower().replace(" ", "-"))
    if detail:
        return detail
    matches = catalog.search_products(key)
    exact = [c for c in matches if c.name.lower() == key.lower()]
    if len(exact) == 1 or len(matches) == 1:
        found = catalog.get_product((exact or matches)[0].product_id)
        if found:
            return found
    suggestions = [d for c in matches[:5] if (d := catalog.get_product(c.product_id))]
    return NotFound(
        error=f"No single product matches {product!r}. Ask the shopper which one they mean, "
        "or use search_products. Do not guess.",
        did_you_mean=[_hit(d) for d in suggestions],
    )


# ---------------------------------------------------------------- tools


def search_products(
    ctx: RunContext[ChatDeps],
    query: str = "",
    category: str | None = None,
    collection: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    color: str | None = None,
) -> SearchResults | NotFound:
    """Search the Campus Customs catalogue. Use this to find or recommend products.

    Results include price and which sizes are in stock, but for any specific price,
    description, or stock question, follow up with get_product_details or check_stock.

    Args:
        query: Keywords such as a color, sport, residential college, school, family member,
            or style, e.g. "navy hockey", "Davenport", "grandpa", "vintage bulldog".
            Every keyword must match, so use 1-3 specific words; leave empty to browse a
            category or collection.
        category: Optional. One of: Hoodies, Crewnecks, T-Shirts, Quarter-Zips,
            Jackets & Fleece, Long Sleeves.
        collection: Optional. One of: residential-colleges, athletics, family, graduate-schools.
        max_price: Optional price ceiling in USD.
        size: Optional. Only return products with this size in stock (XS, S, M, L, XL, XXL).
        color: Optional. Only return products whose listed colors include this color
            (e.g. "red", "heather gray"). Use this, not `query`, for color requests.
    """
    if collection and collection not in catalog.COLLECTIONS:
        return NotFound(error=f"Unknown collection. Use one of: {', '.join(catalog.COLLECTIONS)}")
    wanted = normalize_size(size) if size else None
    if size and not wanted:
        return NotFound(error=f"Unknown size {size!r}. Sizes are {', '.join(SIZES)}.")

    details = [
        d
        for c in catalog.search_products(
            query, category=category, collection=collection, max_price=max_price, color=color
        )
        if (d := catalog.get_product(c.product_id))
    ]
    if wanted:
        details = [d for d in details if wanted in _sizes_in_stock(d)]
    hits = [_hit(d) for d in details[:MAX_SEARCH_RESULTS]]
    note = (
        f"Only the first {len(hits)} of {len(details)} matches are listed. If you give a count, "
        f"say {len(details)} in total (e.g. 'here are {len(hits)} of our {len(details)}'), "
        "or narrow the search."
        if len(details) > len(hits)
        else None
    )
    return SearchResults(total_matches=len(details), showing=len(hits), products=hits, note=note)


def get_product_details(ctx: RunContext[ChatDeps], product: str) -> ProductLookup | NotFound:
    """Look up one product's description, exact price, colors, and stock for EVERY size.

    Call this whenever the shopper asks about a specific product's price, description,
    colors, materials/look, or which sizes are available, even if it came up earlier.

    Args:
        product: The product_id from search results (preferred, e.g. "yale-dad-hoodie")
            or the product's exact name (e.g. "Yale Dad Hoodie").
    """
    detail = _resolve(product)
    if isinstance(detail, NotFound):
        return detail
    stock = [
        SizeAvailability(
            size=s.size, quantity=s.quantity, in_stock=s.quantity > 0, state=_state(s.quantity), sku=s.sku
        )
        for s in detail.inventory
    ]
    return ProductLookup(
        product_id=detail.product_id,
        name=detail.name,
        garment_type=detail.garment_type,
        category=detail.category,
        price_usd=detail.price,
        description=detail.description,
        colors=detail.colors,
        stock_by_size=stock,
        sizes_in_stock=[s.size for s in stock if s.in_stock],
        sizes_out_of_stock=[s.size for s in stock if not s.in_stock],
        total_units=detail.total_stock,
    )


def check_stock(ctx: RunContext[ChatDeps], product: str, size: str) -> StockCheck | NotFound:
    """Definitive stock check for one product in one size ("Is the M in stock?").

    Returns the exact quantity on hand. in_stock=False means the size is out of stock
    (or not made), and the answer is final. Use other_sizes_in_stock to suggest alternatives.

    Args:
        product: The product_id (preferred) or exact product name.
        size: XS, S, M, L, XL or XXL (words like "medium" or "extra large" also work).
    """
    wanted = normalize_size(size)
    if not wanted:
        return NotFound(error=f"Unknown size {size!r}. Sizes are {', '.join(SIZES)}.")
    detail = _resolve(product)
    if isinstance(detail, NotFound):
        return detail
    row = next((s for s in detail.inventory if s.size == wanted), None)
    qty = row.quantity if row else None
    return StockCheck(
        product_id=detail.product_id,
        name=detail.name,
        size=wanted,
        offered=qty is not None,
        quantity=qty or 0,
        in_stock=bool(qty),
        sku=row.sku if row else None,
        price_usd=detail.price,
        other_sizes_in_stock=[s for s in _sizes_in_stock(detail) if s != wanted],
    )


def get_current_user(ctx: RunContext[ChatDeps]) -> ShopperProfile:
    """Who is chatting: the signed-in shopper's first/last name, email, and member-since date.

    Use when the shopper asks about their account ("what email am I signed in with?",
    "do you know who I am?"). Returns signed_in=false for guests. Only ever describes
    the current shopper; there is no way to look up anyone else.
    """
    return ctx.deps.shopper or ShopperProfile(signed_in=False)


def get_viewed_product(ctx: RunContext[ChatDeps]) -> ProductLookup | NotFound:
    """Full details (description, price, colors, stock by size) of the product page the
    shopper currently has open.

    Call this when the shopper says "this", "it", "this one", or asks about colors, sizes,
    price, or stock without naming a product while viewing a product page.
    """
    viewed = ctx.deps.viewed_product
    if viewed is None:
        return NotFound(error="The shopper is not on a product page. Ask which product they mean.")
    return get_product_details(ctx, viewed.product_id)


def catalogue_overview(ctx: RunContext[ChatDeps]) -> dict:
    """List product categories and shop-by collections with item counts and the price range.

    Use this for broad questions like "what do you sell?" before searching.
    """
    cards = catalog.search_products()
    prices = [c.price for c in cards]
    return {
        "total_products": len(cards),
        "price_range_usd": [min(prices), max(prices)] if prices else None,
        "categories": [c.model_dump() for c in catalog.list_categories()],
        "collections": [c.model_dump() for c in catalog.list_collections()],
        "sizes": SIZES,
        "source": "campus_customs.db",
    }


TOOLS = (
    search_products,
    get_product_details,
    check_stock,
    get_viewed_product,
    get_current_user,
    catalogue_overview,
)
