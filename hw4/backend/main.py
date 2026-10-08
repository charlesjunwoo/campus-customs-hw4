"""Campus Customs API.

Run from the backend/ folder:
    uvicorn main:app --reload --port 8000

Routes
  POST /api/chat              -> chatbot reply (PydanticAI agent, see agent.py)
  GET  /api/chat/history      -> signed-in shopper's saved chat (memory.py)
  DELETE /api/chat/history    -> clear it
  POST /api/auth/register     -> create account (first/last name, email, password)
  POST /api/auth/login        -> sign in with email + password (sets HttpOnly cookie)
  POST /api/auth/logout       -> end session
  GET  /api/auth/me           -> current signed-in user
  GET  /api/products          -> product cards (optional ?q=, ?category=, ?collection=)
  GET  /api/products/{id}     -> one product with sizes and stock
  GET  /api/categories        -> product categories with counts
  GET  /api/collections       -> shop-by collections (colleges, athletics, family, schools)
  GET  /api/health            -> liveness check
  GET  /media/products/...    -> product images from data/products/

Catalogue and inventory are read-only (catalog.py). Writes: auth.py (users,
sessions) and memory.py (chat_messages, signed-in shoppers only).
"""

from __future__ import annotations

import logging
from urllib.parse import unquote

from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior

from fastapi import Cookie, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import agent
import auth
import catalog
import memory
from models import (
    Category,
    ChatDeps,
    ChatHistory,
    ChatRequest,
    ChatResponse,
    ChatResults,
    ChatTurn,
    Collection,
    PageInfo,
    ProductCard,
    ProductDetail,
    ViewedProduct,
)

log = logging.getLogger("campus_customs")

# Shown when the model provider's content filter blocks a message (e.g. jailbreak attempts).
FILTERED_REPLY = (
    "I can't help with that one, but I'd love to help you find some Yale gear! "
    "Ask me about hoodies, sizes, colors, or what's in stock."
)


# Shown when the agent can't produce a reply whose prices/stock pass the fact guard.
UNVERIFIED_REPLY = (
    "Sorry, I couldn't double-check that against our inventory just now, and I don't want to "
    "give you a wrong price or stock count. Please try asking again, or check the product page."
)


def _is_content_filter(exc: ModelHTTPError) -> bool:
    body = exc.body if isinstance(exc.body, dict) else {}
    return body.get("code") == "content_filter" or "content_filter" in str(exc.body)


app = FastAPI(title="Campus Customs API", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

auth.init(catalog.DB_PATH)
memory.init(catalog.DB_PATH)
app.include_router(auth.router)

if catalog.PRODUCTS_DIR.is_dir():
    app.mount("/media/products", StaticFiles(directory=catalog.PRODUCTS_DIR), name="products")


@app.exception_handler(catalog.DatabaseMissing)
def _db_missing(_: Request, exc: catalog.DatabaseMissing) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# ---------------------------------------------------------------- catalogue


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "database": catalog.DB_PATH.is_file(),
        "images": catalog.PRODUCTS_DIR.is_dir(),
        "model": agent.MODEL_NAME,
    }


@app.get("/api/products", response_model=list[ProductCard])
def list_products(
    q: str | None = Query(None, max_length=100, description="Search name, description, colors, tags"),
    category: str | None = Query(None, max_length=50),
    collection: str | None = Query(None, max_length=50, description="Slug from /api/collections"),
) -> list[ProductCard]:
    if collection and collection not in catalog.COLLECTIONS:
        raise HTTPException(404, "Unknown collection")
    return catalog.search_products(q, category=category, collection=collection)


@app.get("/api/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: str) -> ProductDetail:
    product = catalog.get_product(product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    return product


@app.get("/api/categories", response_model=list[Category])
def list_categories() -> list[Category]:
    return catalog.list_categories()


@app.get("/api/collections", response_model=list[Collection])
def list_collections() -> list[Collection]:
    return catalog.list_collections()


# ---------------------------------------------------------------- chat


def _viewed_product(page: PageInfo | None) -> ViewedProduct | None:
    """Resolve the product page the shopper is on, trusting only the database."""
    if page is None:
        return None
    pid = page.product_id
    if not pid and page.path.startswith("/products/"):
        pid = unquote(page.path.removeprefix("/products/").split("/")[0].split("?")[0])
    product = catalog.get_product(pid) if pid else None
    if product is None:
        return None
    return ViewedProduct(product_id=product.product_id, name=product.name, garment_type=product.garment_type)


async def _answer(message: str, history: list[ChatTurn], deps: ChatDeps, user_id: int | None) -> ChatResponse:
    try:
        run = await agent.run_chat(message, history, deps, audit_meta={"user_id": user_id})
    except agent.AgentUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except UnexpectedModelBehavior:
        # Usually the fact guard rejected every attempt: refuse rather than risk a wrong number.
        log.warning("chat reply failed verification; returned safe fallback")
        return ChatResponse(reply=UNVERIFIED_REPLY, cue="oops")
    except ModelHTTPError as exc:
        if _is_content_filter(exc):
            log.info("chat message blocked by provider content filter")
            return ChatResponse(reply=FILTERED_REPLY, cue="oops")
        log.error("chat model error: status %s", exc.status_code)
        raise HTTPException(502, "The assistant hit a snag. Please try again in a moment.") from exc
    except Exception as exc:  # model/network errors: log the type, never the key or prompt
        log.exception("chat agent failed: %s", type(exc).__name__)
        raise HTTPException(502, "The assistant hit a snag. Please try again in a moment.") from exc

    # Cards are built from the database, so names, images, prices and stock are always real;
    # any id the model made up simply doesn't resolve.
    output = run.output
    cards = catalog.get_cards(output.product_ids)
    results = ChatResults(title=output.results_title or "From our chat", products=cards) if cards else None
    return ChatResponse(reply=output.reply, results=results, cue=run.cue, tools_used=run.tools_used)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, cc_session: str | None = Cookie(default=None)) -> ChatResponse:
    user = auth.current_user(cc_session)
    message = req.message.strip()
    page = req.page
    deps = ChatDeps(
        shopper=memory.shopper_profile(user.id) if user else None,
        page_path=page.path if page else None,
        viewed_product=_viewed_product(page),
        recent_products=memory.recent_products(user.id) if user else [],
    )
    # Signed in: memory comes from the database (the browser's copy is ignored, so it
    # can't be forged). Guest: the browser's in-memory history, never stored.
    history = memory.agent_history(user.id) if user else req.history

    response = await _answer(message, history, deps, user.id if user else None)
    if user:
        memory.save_exchange(user.id, message, response.reply, response.results)
    return response


@app.get("/api/chat/history", response_model=ChatHistory)
def chat_history(cc_session: str | None = Cookie(default=None)) -> ChatHistory:
    """The signed-in shopper's saved conversation (guests get an empty list)."""
    user = auth.current_user(cc_session)
    if user is None:
        return ChatHistory(signed_in=False)
    return ChatHistory(
        signed_in=True,
        messages=memory.load_messages(user.id),
        recap=memory.recap(user.id, user.first_name),
    )


@app.delete("/api/chat/history", status_code=204)
def clear_chat_history(cc_session: str | None = Cookie(default=None)) -> Response:
    user = auth.current_user(cc_session)
    if user is None:
        raise HTTPException(401, "Not signed in.")
    memory.clear(user.id)
    return Response(status_code=204)
