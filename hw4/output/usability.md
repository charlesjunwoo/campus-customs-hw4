# Campus Customs: Show & Improve (Problem 9)

Part 1 shows that the shop works end to end. Part 2 covers four usability improvements: two in the frontend and two in the agent/backend. For each one: what was added, why it helps the shopper and the business, and how it was verified in the running app.

---

## Part 1: The shop works

Run against the live dev stack (`uvicorn main:app --reload --port 8000` in `backend/`, Vite on `:5173`), real `campus_customs.db`, real model (`gpt-5.6-luna` via Portkey).

### End-to-end smoke test (through the Vite proxy, as a browser would)

| Step | Result |
|---|---|
| Home page | `200` |
| `/api/health` | `{"ok":true,"database":true,"images":true,"model":"gpt-5.6-luna"}` |
| Products page data | 102 product cards |
| Single-item page data (`yale-grandpa-hoodie`) | name, $68, per-size stock **and SKUs** (`XS 5 CC-0505-XS`, `S 20 CC-0506-S`, …) |
| Product image | `200` |
| Create account (fresh user) | `201`, signed in |
| `/api/auth/me` | `Sam Smoke` |
| Chat while signed in: "any Davenport gear?" | Davenport College Crewneck card, `cue: found`, personalized "Absolutely, Sam…" |
| Log out → log back in | `204` → `200` |
| Saved history + recap | 2 messages restored; recap "Welcome back, Sam! Last time (Oct 8) you were looking at these… **Davenport College Crewneck**…" |
| Wrong password | `401` |
| Backend test suite | **135 passed** (no model calls; every product/size checked against the DB) |
| Frontend type-check + production build | clean |

### What a shopper can do (verified across Problems 3–8)

| Feature | Where verified |
|---|---|
| Browse, search, filter (type, collection), and sort 102 products; every card opens a large-image product page with price, description, colors, and stock by size | Problem 3 (browser) |
| Create an account / log in / log out; passwords hashed with PBKDF2-SHA256 (600k iterations, per-user salt) | Problem 4 (API + browser), harness §2 |
| Ask the Bulldog assistant; answers grounded in the DB with a server-side fact guard on prices and quantities | Problems 5–6, harness §5–6 |
| Chat matches appear as product cards in the chat and in a "Chat picks" strip on the page | Problem 7, harness §3.4 |
| Signed-in chat history saved and reloaded; the agent knows who's chatting and which product page they're on | Problem 8, harness §3.5 |

---

## Part 2: Improvements

| # | Layer | Improvement |
|---|---|---|
| F1 | Frontend | A more natural conversation flow |
| F2 | Frontend | SKU info on product pages |
| B1 | Agent / backend | Prior chat history reload, upgraded with a "welcome back" recap and earlier-visit memory |
| B2 | Agent / backend | Sound effects chosen from what the database said |

### F1. A more natural conversation flow *(frontend)*

**What I added** (`ChatWidget.tsx`, `TypedText.tsx`)
- **Replies type out** word by word, like a person typing. It's capped at about 1.4 s however long the reply is, and skipped for "reduced motion" users. Product cards and suggestions appear after the text finishes, so the reply reads in order: the answer first, then the products.
- **Context-aware quick replies** under the latest message, chosen from what just happened:
  - after product cards: "Is the *Grandpa Hoodie* in M?", "Which is your top pick?" / "Show me similar items", "Anything cheaper?"
  - after a sold-out answer: "Which sizes are in stock?", "Show me similar items"
  - after no match: "Show me hoodies", "What do you sell?"
  - on a product page with no context yet: "Is this in stock in M?", "What colors does this come in?", "Tell me more about this one"
- **"Ask about this item" buttons** on every product page. "💬 Ask about this item" opens the chat and asks about the product being viewed (page context from Problem 8 tells the agent which one). After you pick a size, "Check M with the assistant" asks about that size.
- **Date dividers** in restored history ("Earlier today" / "Wed, Oct 8" … "Now"), so returning shoppers can tell old messages from new.

**Why it helps the shopper:** the next question is one tap away, so shoppers don't need to know how to phrase things. Size checks after a recommendation, alternatives after a sold-out answer, and questions about the item on screen all happen without typing. The typing reveal makes the assistant feel conversational rather than a wall of text appearing at once.

**Why it helps the business:** each reply now leads to a likely next step, so more chats go from a search to a specific item and size. "Ask about this item" turns product pages into a direct route into assisted selling, which matters most for hesitant buyers.

**Verified in the app (browser):** on `/products/yale-grandpa-hoodie`, clicking "Ask about this item" opened the chat and sent the question. The reply was 69 characters long partway through the reveal and 243 characters at the end. Afterwards the chips read "Is the Grandpa Hoodie in M? / Show me similar items / Anything cheaper?". Asking "Is the L in stock?" switched them to "Which sizes are in stock? / Show me similar items". Restored history showed the "Earlier today" divider.

### F2. SKU info *(frontend + catalogue field)*

**What I added**
- Every product × size now has a **SKU** like `CC-0507-M`. It comes from that size's `inventory.id`, the database's permanent integer key for exactly one sellable product/size, so it's unique, stable, and never invented (`catalog.sku_for`). Exposed as `sku` on `/api/products/{id}`, on the agent's `ProductLookup`/`StockCheck` results, and as a quotable fact in the prompt.
- **Product page:** picking a size shows a SKU box (`SKU CC-0507-M · Size M: 25 in stock · Copy SKU`), and the stock table gains a SKU row for every size.
- **Chat:** "What's the SKU for the medium?" is answered from the tool result. The prompt tells the agent to give SKUs only when asked and to quote them exactly.

**Why it helps the shopper:** a precise item number to give the store ("can you hold CC-0507-M?"), to note down, or to compare. No ambiguity about which size or which of several similar hoodies they mean.

**Why it helps the business:** SKUs are how stores do stock checks, holds, and orders. Staff at 57 Broadway can find the exact unit, and the later ordering flow has a stable key per product/size. It also removes "which one did you mean?" back-and-forth in support.

**Verified in the app (browser + DB):** selecting **M** on the Yale Grandpa Hoodie showed `CC-0507-M` and "25 in stock". The stock table's SKU row read `CC-0505 … CC-0510`, and the DB inventory ids for that product are 505–510 (M = 507, quantity 25). Tests check all **612** SKUs are unique, match the DB id, and reach both the API and the tools.

### B1. Prior chat history reload, upgraded with a recap and earlier-visit memory *(agent/backend)*

Problem 8 already saves and reloads signed-in chats. This improvement makes the reload useful to the shopper and the agent, not just a scrollback.

**What I added**
- **Welcome-back recap** (`memory.recap`, returned as `recap` by `GET /api/chat/history`). When a signed-in shopper returns, the chat ends with a summary of what they were looking at last time, re-checked against the **current** database:
  > Welcome back, Uma! Last time (Oct 8) you were looking at these. Here's where they stand today:
  > - **District Vit Hoodie Vintage Bulldog**: $68, in stock in XS, S, M, L, XL
  >
  > Want me to check a size, or find something new?

  It also flags low stock ("running low: XL (2 left)") or "sold out in every size right now", and shows the products as cards. It's **deterministic: no model call**, so it's instant, free, and every number is straight from the DB. The most recent replies' top picks come first.
- **Earlier-visit memory for the agent:** `deps.recent_products` (the last 3 products discussed across saved history) goes into the agent's Session context, so "that hoodie from last time" resolves even when it's beyond the 12-message replay window. The prompt still requires a fresh lookup before any price or stock claim.

**Why it helps the shopper:** they pick up exactly where they left off and immediately see whether the thing they wanted is still available and at what price, without re-searching or re-explaining.

**Why it helps the business:** it brings back abandoned shopping intent. "Still in stock, and XL is running low" is the cue that turns a browse into a purchase. Because it costs no model tokens, it scales to every returning visit for free.

**Verified in the app:**
- **Browser:** after a reload while signed in, the chat showed restored history under an "Earlier today" divider, then the recap above with a District Vit Hoodie card. The recap's "$68, in stock in XS, S, M, L, XL" matches the DB (XXL = 0).
- **API smoke test:** a fresh account asked about Davenport gear, logged out and back in, and got "Welcome back, Sam! … **Davenport College Crewneck** …".
- **Tests:** no recap for a brand-new user, live DB price in the recap text, and `recent_products` reaching the agent's deps and Session context.

### B2. Sound effects, chosen from the facts *(agent/backend + frontend player)*

**What I added**
- `ChatResponse.cue`: one of `found`, `in_stock`, `out_of_stock`, `no_match`, `oops`, or `null`. It's chosen **server-side from this turn's tool results**, not by the model (`agent.pick_cue`):
  1. a `check_stock` result decides `in_stock` / `out_of_stock` (most specific wins);
  2. else product cards shown → `found`;
  3. else a search with 0 matches → `no_match`;
  4. a blocked or unverifiable turn → `oops`.
- `sound.ts` plays a short, quiet 80s-synth sound for each cue with the Web Audio API. There are no audio files, in keeping with the "build visuals/assets in code" rule.

| Cue | Sound |
|---|---|
| found | rising C-E-G square-wave arpeggio |
| in_stock | bright two-note "yes!" |
| out_of_stock | gentle falling minor third |
| no_match | single soft low blip |
| oops | short low buzz |

- **Shopper control:** a "♪ On / ♪ Off" toggle in the chat header, remembered in `localStorage`. Turning it on plays a preview. Sound is skipped for reduced-motion users and only plays after the shopper sends a message (never on page load).

**Why it helps the shopper:** they know the outcome before reading. A happy chime means "found it / your size is there", and a soft falling tone means "sold out". That helps people glancing back at the chat while browsing, and adds a playful, on-brand 80s touch. Because the cue comes from the database result, a cheerful sound can never accompany bad news.

**Why it helps the business:** small positive feedback makes the assistant memorable and fun to use, which helps engagement and repeat use. Low volume and a one-click mute avoid annoying anyone.

**Verified in the app (browser, with the Web Audio oscillators instrumented to record notes):**

| Message | Server cue | Notes played |
|---|---|---|
| "Tell me more about this one" (Grandpa Hoodie page) | `found` | 523, 659, 784 Hz |
| "Is the L in stock?" (L = 0 in DB) | `out_of_stock` | 440 → 370 Hz |
| Sound toggled **Off**, then "And XL?" | `in_stock` | *(none)*; `localStorage cc.sound = off` |

**Tests:** cue priority (size check beats cards, then found, then no_match), and `/api/chat` returning the cue.

---

## Bugs found while verifying (fixed)

- **History didn't load after the F1/B1 rewrite.** The chat loaded history whenever the `user` object changed, but the auth context can hand back a new object for the same person. The second run cancelled the first fetch and then skipped as "already loaded". Fix: key the effect on the user **id**, and only mark history as loaded once the fetch actually finishes, so a cancelled run retries. Re-verified in the browser.
- **Divider wording:** "Earlier today" followed by "Today" was confusing, so the final divider now says "Now".

## Files touched (Problem 9)

| Area | Files |
|---|---|
| Backend | `catalog.py` (`sku_for`, SKU in `get_product`), `models.py` (`sku` fields, `Cue`, `Recap`, `ChatHistory.recap`, `ChatDeps.recent_products`), `tools.py` (SKU in lookups), `agent.py` (`ChatRun`, `pick_cue`, recent products in Session context), `memory.py` (`recent_product_ids`, `recent_products`, `recap`), `main.py` (cue + recap wiring), `prompts/prompt.md` (SKU rule, earlier-visit products) |
| Frontend | `components/ChatWidget.tsx` (typing, quick replies, dividers, recap, sound toggle, `cc:ask` listener), `components/TypedText.tsx`, `sound.ts`, `pages/ProductPage.tsx` (SKU box/row, Ask buttons), `types.ts`, `index.css` |
| Tests | `tests/test_usability.py` (SKUs, cues, recap, recent products); existing tests updated for `ChatRun` |
