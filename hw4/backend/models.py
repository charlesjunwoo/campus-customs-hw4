"""Pydantic / PydanticAI structured types for Campus Customs.

Four groups:
  * Catalogue shapes returned by the REST API.
  * Agent tool results (ProductLookup, StockCheck, SearchResults, NotFound).
  * The chat request/response contract between the website and /api/chat.
  * AgentReply, the structured output the PydanticAI agent must produce.

Prices and stock are never authored by the model: AgentReply only carries
product_ids, and the server turns those into ProductCards from the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

StockStatus = Literal["in_stock", "low", "sold_out"]


# ---------------------------------------------------------------- catalogue


class SizeStock(BaseModel):
    size: str
    quantity: int
    status: StockStatus
    sku: str = Field(description="Stock-keeping unit for this product in this size, e.g. CC-0123-M")


class ProductCard(BaseModel):
    """Compact product summary used by the Products grid and chat product cards."""

    product_id: str
    name: str
    category: str
    garment_type: str
    one_liner: str
    price: float
    image_url: str
    total_stock: int
    sizes_in_stock: int
    status: StockStatus


class ProductDetail(ProductCard):
    description: str
    colors: list[str]
    search_tags: list[str]
    inventory: list[SizeStock]


class Category(BaseModel):
    name: str
    count: int


class Collection(BaseModel):
    slug: str
    name: str
    count: int


# ---------------------------------------------------------------- agent tool results
#
# Typed return values for the agent's lookup tools. PydanticAI serializes them to
# JSON for the model. Every number here is read from campus_customs.db at call
# time; the model is told to quote these fields and nothing else.

SOURCE = "campus_customs.db"
SizeState = Literal["in_stock", "low_stock", "out_of_stock"]


class SizeAvailability(BaseModel):
    size: str = Field(description="XS, S, M, L, XL or XXL")
    quantity: int = Field(description="Units on hand right now. 0 means out of stock.")
    in_stock: bool = Field(description="True if quantity > 0. False is definitive: this size is sold out.")
    state: SizeState
    sku: str = Field(description="SKU for this product in this size; quote exactly if asked")


class ProductLookup(BaseModel):
    """Everything a shopper can ask about one product, straight from the database."""

    found: Literal[True] = True
    product_id: str
    name: str
    garment_type: str
    category: str
    price_usd: float = Field(description="Exact catalogue price. Quote as-is, e.g. 68.0 -> $68.")
    description: str
    colors: list[str] = Field(description="Listed colors. Empty means colors are not listed; do not guess.")
    stock_by_size: list[SizeAvailability] = Field(description="Every size the product is offered in, XS..XXL.")
    sizes_in_stock: list[str]
    sizes_out_of_stock: list[str]
    total_units: int
    source: str = SOURCE


class StockCheck(BaseModel):
    """Definitive yes/no answer for one product in one size."""

    found: Literal[True] = True
    product_id: str
    name: str
    size: str
    offered: bool = Field(description="False if this product is never made in this size.")
    quantity: int = Field(description="Units on hand right now (0 if out of stock or not offered).")
    in_stock: bool = Field(description="Definitive. False means the size is out of stock or not offered.")
    sku: str | None = Field(default=None, description="SKU for this size (None if not offered)")
    price_usd: float
    other_sizes_in_stock: list[str] = Field(description="Alternatives to offer if this size is unavailable.")
    source: str = SOURCE


class SearchHit(BaseModel):
    product_id: str
    name: str
    category: str
    price_usd: float
    summary: str
    total_units: int
    sizes_in_stock: list[str]


class SearchResults(BaseModel):
    total_matches: int = Field(description="How many products match in the whole catalogue.")
    showing: int = Field(description="How many are listed below (capped). Not the total.")
    products: list[SearchHit]
    note: str | None = Field(default=None, description="Set when results were truncated; follow it.")
    source: str = SOURCE


class NotFound(BaseModel):
    """Returned instead of guessing when a lookup can't be answered from the database."""

    found: Literal[False] = False
    error: str
    did_you_mean: list[SearchHit] = Field(default_factory=list)


# ---------------------------------------------------------------- chat API


class ChatTurn(BaseModel):
    """One earlier message in the conversation, as the site remembers it."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class PageInfo(BaseModel):
    """Where the shopper is on the site when they send a message."""

    path: str = Field(max_length=200, description="e.g. /products/yale-dad-hoodie")
    product_id: str | None = Field(
        default=None, max_length=120, description="Set on single-item pages; verified against the DB server-side."
    )


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    # Only used for signed-out shoppers. Signed-in shoppers' history is loaded from the
    # database, and whatever the browser sends is ignored.
    history: list[ChatTurn] = Field(default_factory=list, max_length=40)
    page: PageInfo | None = None


class ChatResults(BaseModel):
    """Product matches the website renders as cards (in the chat and on the page)."""

    title: str = Field(description="Short heading for the results strip, e.g. 'Navy hoodies under $70'")
    products: list[ProductCard] = Field(description="Hydrated from the database, in the agent's order")


class StoredMessage(BaseModel):
    """One saved chat message, as returned to the site when history reloads."""

    id: int
    role: Literal["user", "assistant"]
    content: str
    results: ChatResults | None = None  # cards re-hydrated from the DB (current price/stock)
    created_at: str


class ChatHistory(BaseModel):
    signed_in: bool
    messages: list[StoredMessage] = Field(default_factory=list)
    recap: Recap | None = None


# Sound cue for the reply, chosen server-side from what the database lookups returned
# (never by the model): found products, a size in stock, a size sold out, no match,
# or a blocked/failed turn.
Cue = Literal["found", "in_stock", "out_of_stock", "no_match", "oops"]


class ChatResponse(BaseModel):
    """The /api/chat contract.

    reply    - text for the chat bubble
    results  - product cards to show on the page, or null when the turn has no product matches
    cue      - which sound effect the site plays (null = none)
    """

    reply: str
    results: ChatResults | None = None
    cue: Cue | None = None
    tools_used: list[str] = Field(default_factory=list)


class Recap(BaseModel):
    """Welcome-back summary for a returning shopper, built from saved history + live stock."""

    text: str
    products: list[ProductCard] = Field(default_factory=list)


# ---------------------------------------------------------------- agent


MAX_RESULT_CARDS = 12


class AgentReply(BaseModel):
    """Structured output the agent must return on every turn.

    product_ids is the product-match contract: every product the reply talks about
    must be listed here (validated in agent.py), and the website shows exactly these
    as cards. The model never sends names, prices, or images for the cards; the
    server looks each id up in the database.
    """

    reply: str = Field(
        description=(
            "The message to show the shopper, in the Campus Customs voice. Short, friendly, "
            "plain text with light markdown (bold, bullet lists). Never include image paths or URLs."
        )
    )
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_RESULT_CARDS,
        description=(
            "REQUIRED whenever products are found or discussed: the product_id of every product "
            "you mention or recommend, exactly as returned by a tool in this turn, best match first "
            f"(max {MAX_RESULT_CARDS}). These become product cards on the website. Empty only when "
            "no product is relevant (greetings, policy questions, nothing found)."
        ),
    )
    results_title: str | None = Field(
        default=None,
        max_length=60,
        description=(
            "Short heading for the product cards, describing the match set in the shopper's terms, "
            "e.g. 'Navy hoodies under $70' or 'Gifts for Grandpa'. Required when product_ids is non-empty."
        ),
    )


class ShopperProfile(BaseModel):
    """The signed-in shopper, as the agent sees them (tool result and deps).

    Deliberately excludes the user id, password hash, and sessions.
    """

    signed_in: bool
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    member_since: str | None = Field(default=None, description="Account creation date, YYYY-MM-DD")
    saved_messages: int = Field(default=0, description="How many earlier chat messages are on file")


class ViewedProduct(BaseModel):
    """The product page the shopper has open, resolved from the URL against the database."""

    product_id: str
    name: str
    garment_type: str


@dataclass
class ChatDeps:
    """Per-request context handed to the agent and its tools.

    Built server-side in main.chat(): the shopper comes from the session cookie (never
    from the message), and the viewed product is verified against the database.
    """

    shopper: ShopperProfile | None = None
    page_path: str | None = None
    viewed_product: ViewedProduct | None = None
    recent_products: list[ViewedProduct] = field(default_factory=list)  # from saved history
