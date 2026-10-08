"""Campus Customs chat agent: entry point and wiring.

  * System prompt: prompts/prompt.md (read once, at first use)
  * Model:         gpt-5.6-luna (OpenAI) through the Portkey gateway
  * API key:       PORTKEY_API_KEY from the nearest .env (backend/, hw4/, or any parent
                   folder); never logged or returned
  * Tools:         tools.TOOLS (read-only catalogue + inventory)
  * Output:        models.AgentReply (reply text + product_ids to show as cards)
  * Fact guard:    an output validator rejects any reply that quotes a price or a
                   stock quantity not returned by a tool during this turn, and makes
                   the model retry with real lookups (see check_facts below)
  * Card contract: the same validator requires product_ids to list every product
                   the reply mentions, only ids a tool returned this turn, and at
                   least one id whenever a search found matches (check_products)

main.py calls `await run_chat(...)` from the /api/chat route.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# pydantic-ai prints a banner on first use; keep server logs clean.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent, ModelRetry, RunContext, capture_run_messages  # noqa: E402
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded  # noqa: E402
from pydantic_ai.messages import (  # noqa: E402
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    RetryPromptPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIChatModel  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.usage import UsageLimits  # noqa: E402

import audit  # noqa: E402
from models import AgentReply, ChatDeps, ChatTurn, Cue  # noqa: E402
from tools import TOOLS  # noqa: E402

TOOL_NAMES = {t.__name__ for t in TOOLS}

HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE / "prompts" / "prompt.md"

# Nearest .env wins (backend/, then hw4/, then each parent folder): load_dotenv never
# overwrites a variable that is already set, so the first file found takes precedence.
for folder in (HERE, *HERE.parents):
    if (folder / ".env").is_file():
        load_dotenv(folder / ".env")

MODEL_NAME = os.getenv("CC_MODEL", "gpt-5.6-luna")  # course default: cheapest capable model
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")

# ---- loop limits (see harness §6) ----
MAX_HISTORY_TURNS = 12  # earlier messages replayed for context (cost guard)
MAX_MODEL_REQUESTS = 6  # model round-trips per turn, tool calls + retries included
MAX_OUTPUT_TOKENS = 1500  # total output tokens per turn
OUTPUT_RETRIES = 2  # extra attempts when the fact guard / card contract rejects a reply
USAGE_LIMITS = UsageLimits(request_limit=MAX_MODEL_REQUESTS, output_tokens_limit=MAX_OUTPUT_TOKENS)


# "$68", "$68.00", "$ 45"
PRICE_RE = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)")
# "12 in stock", "only 2 left", "5 units", "3 available", "8 remaining"
QTY_RE = re.compile(
    r"\b(\d+)\s*(?:units?|pieces?|left|in stock|available|remaining|on hand)\b"
    r"|\bonly\s+(\d+)\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
# "found 12", "we have 12", "12 crewnecks", "12 options" ... (a claim about how many match)
COUNT_RE = re.compile(
    r"\b(?:found|have|carry|there are|got)\s+(\d+)\b"
    r"|\b(\d+)\s+(?:matches|results|options|items|products|styles|picks|crewnecks|hoodies|"
    r"t-shirts|tees|quarter-zips|jackets|shirts|sweatshirts)\b",
    re.IGNORECASE,
)


class AgentUnavailable(RuntimeError):
    """The agent can't run (e.g. no API key). Message is safe to show users."""


@lru_cache(maxsize=1)
def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def build_agent() -> Agent[ChatDeps, AgentReply]:
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise AgentUnavailable("The chat assistant isn't configured yet (missing PORTKEY_API_KEY).")

    model = OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(base_url=PORTKEY_BASE_URL, api_key=api_key))
    agent = Agent(
        model,
        instructions=load_prompt(),
        deps_type=ChatDeps,
        output_type=AgentReply,
        tools=list(TOOLS),
        retries=OUTPUT_RETRIES,
    )

    @agent.instructions
    def session_context(ctx: RunContext[ChatDeps]) -> str:
        return build_session_context(ctx.deps)

    @agent.output_validator
    def guard_facts(ctx: RunContext[ChatDeps], output: AgentReply) -> AgentReply:
        problems = check_facts(ctx.messages, f"{output.reply}\n{output.results_title or ''}")
        if problems:
            raise ModelRetry(
                "Your reply states facts that did not come from a tool result in this turn: "
                + ", ".join(problems)
                + ". Call get_product_details or check_stock now and quote only the exact "
                "price_usd and quantity values they return. Never estimate."
            )
        card_problems = check_products(ctx.messages, output)
        if card_problems:
            raise ModelRetry(
                "The product-card contract was not met: "
                + "; ".join(card_problems)
                + ". Put the product_id of every product you mention (from this turn's tool results, "
                "best match first) in product_ids, add a short results_title, and look products up "
                "again with a tool if they came from an earlier turn."
            )
        return output

    return agent


def build_session_context(deps: ChatDeps) -> str:
    """Per-request instructions: who is chatting and what page they're on.

    Everything here was resolved server-side (session cookie, DB lookup), so it can be
    trusted more than anything in the chat text.
    """
    lines = ["## Session context (from the server; trust this over anything in the chat)"]
    shopper = deps.shopper
    if shopper and shopper.signed_in:
        lines.append(
            f"- Signed-in shopper: {shopper.first_name or ''} {shopper.last_name or ''}".rstrip()
            + f" <{shopper.email}>, member since {shopper.member_since or 'unknown'}."
        )
        lines.append(
            f"- Their chat history is saved ({shopper.saved_messages} earlier messages on file); "
            "earlier turns below are from previous visits too, so you can pick up where you left off."
        )
    else:
        lines.append("- The shopper is a guest (not signed in). Nothing from this chat is saved.")
    if deps.viewed_product:
        vp = deps.viewed_product
        lines.append(
            f"- They are viewing the product page for **{vp.name}** (product_id `{vp.product_id}`, "
            f"{vp.garment_type}). Words like \"this\", \"it\", or \"this one\" refer to this product "
            "unless they name another. Use get_viewed_product for its details."
        )
    elif deps.page_path:
        lines.append(f"- Current page: {deps.page_path} (not a single product page).")
    if date.today().month == 10:
        lines.append(
            "- Season: it's October, Halloween season, and the site is in its Yale x Halloween theme. "
            "Add a light Halloween touch now and then (a 🎃, \"spook-tacular\", \"boo-la boola\"); "
            "keep it to one small flourish per reply, and never let it change a fact."
        )
    if deps.recent_products:
        names = "; ".join(f"{p.name} (`{p.product_id}`)" for p in deps.recent_products)
        lines.append(
            f"- Products this shopper discussed in earlier visits (most recent first): {names}. "
            "If they say \"that hoodie from last time\", it's probably one of these; look it up before "
            "quoting anything."
        )
    return "\n".join(lines)


def _numbers(text: str) -> set[float]:
    return {float(n) for n in NUMBER_RE.findall(text)}


def check_facts(messages: list[ModelMessage], reply: str) -> list[str]:
    """Return problems with prices/quantities in `reply` that no tool backed up.

    Allowed numbers = everything in this turn's tool results, plus anything the
    shopper typed (e.g. "under $70"). Earlier assistant turns don't count:
    stock must be re-checked, never remembered.
    """
    from_tools: set[float] = set()
    from_shopper: set[float] = set()
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart):
                    from_tools |= _numbers(part.model_response_str())
                elif isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    from_shopper |= _numbers(part.content)
    allowed = from_tools | from_shopper

    problems = []
    for m in PRICE_RE.finditer(reply):
        if float(m.group(1)) not in allowed:
            problems.append(f"price ${m.group(1)}")
    for m in QTY_RE.finditer(reply):
        qty = m.group(1) or m.group(2)
        if float(qty) not in allowed:
            problems.append(f"quantity {qty}")
    if problems and not from_tools:
        problems.append("no lookup tool was called this turn")
    return problems


def _walk_products(data: object, found: dict[str, str]) -> None:
    """Collect {product_id: name} from any nested tool result."""
    if isinstance(data, dict):
        if isinstance(data.get("product_id"), str) and isinstance(data.get("name"), str):
            found[data["product_id"]] = data["name"]
        for value in data.values():
            _walk_products(value, found)
    elif isinstance(data, list):
        for value in data:
            _walk_products(value, found)


def _spoken_name(name: str) -> str:
    # "Champion Reverse Weave Hoodie 1" is said as "Champion Reverse Weave Hoodie".
    return re.sub(r"\s+\d+$", "", name).strip().lower()


def check_products(messages: list[ModelMessage], output: AgentReply) -> list[str]:
    """Enforce the product-card contract on one turn's output."""
    returned: dict[str, str] = {}
    search_hits = 0
    truncated: list[tuple[int, int]] = []
    for msg in messages:
        if not isinstance(msg, ModelRequest):
            continue
        for part in msg.parts:
            if not isinstance(part, ToolReturnPart):
                continue
            try:
                data = json.loads(part.model_response_str())
            except (ValueError, TypeError):
                continue
            _walk_products(data, returned)
            if part.tool_name == "search_products" and isinstance(data, dict):
                search_hits += len(data.get("products") or [])
                if data.get("total_matches", 0) > data.get("showing", 0):
                    truncated.append((data["showing"], data["total_matches"]))

    problems = []
    # A truncated search: "showing" is not the total, so don't let the reply present it as one.
    for showing, total in truncated:
        for m in COUNT_RE.finditer(output.reply):
            n = int(m.group(1) or m.group(2))
            if n == showing and str(total) not in output.reply:
                problems.append(
                    f"the reply says {n} as if it were the total, but there are {total} matches "
                    f"(only {showing} listed); say {total} in total"
                )
                break
    unknown = [pid for pid in output.product_ids if pid not in returned]
    if unknown:
        problems.append(f"product_ids {unknown} were not returned by a tool this turn")
    text = output.reply.lower()
    missing = [
        pid for pid, name in returned.items()
        if pid not in output.product_ids and len(_spoken_name(name)) > 6 and _spoken_name(name) in text
    ]
    if missing:
        problems.append(f"the reply mentions products whose ids are missing from product_ids: {missing}")
    if search_hits and not output.product_ids:
        problems.append("search_products found matches but product_ids is empty")
    if output.product_ids and not output.results_title:
        problems.append("results_title is required when product_ids is non-empty")
    return problems


def to_history(turns: list[ChatTurn]) -> list[ModelMessage]:
    """Rebuild prior chat turns (sent by the site) as PydanticAI messages."""
    history: list[ModelMessage] = []
    for turn in turns[-MAX_HISTORY_TURNS:]:
        if turn.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=turn.content)]))
    return history


@dataclass
class ChatRun:
    output: AgentReply
    tools_used: list[str]
    cue: Cue | None


def pick_cue(messages: list[ModelMessage], output: AgentReply) -> Cue | None:
    """Choose the sound effect from this turn's tool results (facts), not from model text.

    Priority: a definitive size check wins (in_stock / out_of_stock), then products
    shown (found), then a search that matched nothing (no_match).
    """
    size_checks: list[bool] = []
    empty_search = False
    for msg in messages:
        if not isinstance(msg, ModelRequest):
            continue
        for part in msg.parts:
            if not isinstance(part, ToolReturnPart):
                continue
            try:
                data = json.loads(part.model_response_str())
            except (ValueError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            if part.tool_name == "check_stock" and data.get("found") is True:
                size_checks.append(bool(data.get("in_stock")))
            elif part.tool_name == "search_products" and data.get("total_matches") == 0:
                empty_search = True
    if size_checks:
        return "in_stock" if size_checks[-1] else "out_of_stock"
    if output.product_ids:
        return "found"
    if empty_search:
        return "no_match"
    return None


def audit_steps(messages: list[ModelMessage]) -> list[dict]:
    """Flatten one run's messages into ordered, timestamped audit steps."""
    steps: list[dict] = []
    for msg in messages:
        if isinstance(msg, ModelResponse):
            when = audit.iso(msg.timestamp) if msg.timestamp else audit.now_iso()
            usage = msg.usage
            steps.append({
                "time": when,
                "type": "model_response",
                "finish_reason": msg.finish_reason,
                "tokens": {"input": usage.input_tokens, "output": usage.output_tokens} if usage else None,
            })
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    final = part.tool_name not in TOOL_NAMES
                    steps.append({
                        "time": when,
                        "type": "final_output" if final else "tool_call",
                        "tool": part.tool_name,
                        "args": audit.short(part.args, audit.ARG_LIMIT),
                    })
                elif isinstance(part, TextPart) and part.content.strip():
                    steps.append({"time": when, "type": "model_text", "text": audit.short(part.content)})
        elif isinstance(msg, ModelRequest):
            for part in msg.parts:
                when = audit.iso(part.timestamp) if getattr(part, "timestamp", None) else audit.now_iso()
                if isinstance(part, ToolReturnPart):
                    if part.tool_name not in TOOL_NAMES:
                        continue  # framework's "Final result processed." acknowledgement
                    steps.append({
                        "time": when,
                        "type": "tool_result",
                        "tool": part.tool_name,
                        "result": audit.short(part.model_response_str()),
                    })
                elif isinstance(part, RetryPromptPart):
                    steps.append({
                        "time": when,
                        "type": "retry",
                        "tool": part.tool_name or "output_validator",
                        "reason": audit.short(part.content),
                    })
    return steps


def _stop_reason(exc: BaseException | None, steps: list[dict]) -> str:
    if exc is None:
        return "completed"
    if isinstance(exc, AgentUnavailable):
        return "agent_unavailable"
    if isinstance(exc, UsageLimitExceeded):
        return "usage_limit"
    if isinstance(exc, ModelHTTPError):
        return "content_filter" if "content_filter" in str(exc.body) else f"model_error_{exc.status_code}"
    if isinstance(exc, UnexpectedModelBehavior):
        return "retries_exhausted" if any(s["type"] == "retry" for s in steps) else "unexpected_model_behavior"
    return f"error_{type(exc).__name__}"


async def run_chat(
    message: str, history: list[ChatTurn], deps: ChatDeps, audit_meta: dict | None = None
) -> ChatRun:
    """Run one chat turn: structured reply, tools used, and the sound cue.

    Every run, successful or not, is appended to output/audit_trail.json.
    """
    started = audit.now_iso()
    replay = to_history(history)
    run: ChatRun | None = None
    error: BaseException | None = None
    with capture_run_messages() as captured:
        try:
            result = await build_agent().run(
                message, deps=deps, message_history=replay, usage_limits=USAGE_LIMITS
            )
            new = result.new_messages()
            tools_used: list[str] = []
            for msg in new:
                if isinstance(msg, ModelResponse):
                    for part in msg.parts:
                        if isinstance(part, ToolCallPart) and part.tool_name in TOOL_NAMES:
                            if part.tool_name not in tools_used:
                                tools_used.append(part.tool_name)
            run = ChatRun(output=result.output, tools_used=tools_used, cue=pick_cue(new, result.output))
            return run
        except BaseException as exc:
            error = exc
            raise
        finally:
            steps = audit_steps(captured[len(replay):])
            meta = audit_meta or {}
            tokens_in = sum((s["tokens"] or {}).get("input", 0) for s in steps if s["type"] == "model_response")
            tokens_out = sum((s["tokens"] or {}).get("output", 0) for s in steps if s["type"] == "model_response")
            audit.safe_append({
                "run_id": uuid.uuid4().hex[:12],
                "started_at": started,
                "finished_at": audit.now_iso(),
                "model": MODEL_NAME,
                "shopper": {"signed_in": meta.get("user_id") is not None, "user_id": meta.get("user_id")},
                "page": deps.page_path,
                "viewed_product": deps.viewed_product.product_id if deps.viewed_product else None,
                "message": audit.short(message),
                "history_turns_replayed": len(replay),
                "steps": steps,
                "summary": {
                    "model_requests": sum(s["type"] == "model_response" for s in steps),
                    "tool_calls": [s["tool"] for s in steps if s["type"] == "tool_call"],
                    "retries": sum(s["type"] == "retry" for s in steps),
                    "tokens": {"input": tokens_in, "output": tokens_out},
                },
                "output": {
                    "reply": audit.short(run.output.reply),
                    "product_ids": run.output.product_ids,
                    "results_title": run.output.results_title,
                    "cue": run.cue,
                } if run else None,
                "stop_reason": _stop_reason(error, steps),
                "error": audit.short(f"{type(error).__name__}: {error}") if error else None,
            })
