# Campus Customs (HW4)

Storefront and AI shopping assistant ("Ask the Bulldog") for Campus Customs, the Yale apparel shop behind
[yalebulldogblue.com](https://yalebulldogblue.com/).

| Layer | Stack |
|---|---|
| Frontend | React + Vite + TypeScript (`frontend/`, port 5173) |
| Backend | Python FastAPI + Uvicorn (`backend/main.py`, port 8000) |
| Agent | PydanticAI (`backend/agent.py`, `tools.py`, `models.py`, `prompts/prompt.md`), model `gpt-5.6-luna` via Portkey |
| Data | SQLite `data/campus_customs.db` + product images `data/products/` (**local only, not in this repo**) |

**How the whole system works:** see [`output/harness.md`](output/harness.md).

---

## 1. Put the local data pack in place

The database and product images are **not** in the repository (they're git-ignored). Copy the provided data pack so the folder looks like this:

```
hw4/
└─ data/
   ├─ campus_customs.db        ← tables: catalogue, inventory, users, chat_messages
   └─ products/
      ├─ 2025-yale-vs-harvard-t-shirt.jpg
      ├─ basic-hoodie-big-yale.jpg
      └─ … (102 images; file names match catalogue.image_file_path)
```

## 2. Add your API key

```bash
cp .env.example .env
```
Then edit `.env` and set `PORTKEY_API_KEY` to your real key. `.env` is git-ignored. The backend reads the nearest of `backend/.env`, `hw4/.env`, or a parent folder's `.env`.

## 3. Run the backend (FastAPI)

Requires Python 3.12+. From `hw4/`:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r requirements.txt
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

Check it: http://127.0.0.1:8000/api/health should return `{"ok":true,"database":true,"images":true,...}`. API docs: http://127.0.0.1:8000/docs

## 4. Run the frontend (React + Vite)

Requires Node 20+. In a second terminal, from `hw4/`:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api` and `/media` to the backend on port 8000, so keep both running.

**Shortcut:** after steps 1–2 and the two installs, `./start.sh` (from `hw4/`) starts both servers; Ctrl-C stops both.

**Test login:** `test@campuscustoms.yale.edu` / `password`, or create your own account.

---

## Tests and the app check

```bash
# Unit/integration tests (no model calls), from hw4/backend
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q

# End-to-end check with screenshots (both servers running; uses your installed Google Chrome), from hw4/
backend/.venv/bin/python tools/app_check.py   # writes output/app_check.html + output/app_check_images/
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/chat` | Chatbot: `{message, history, page}` → `{reply, results, cue, tools_used}` |
| GET / DELETE | `/api/chat/history` | Signed-in user's saved chat (+ welcome-back recap) / clear it |
| POST | `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` | Accounts |
| GET | `/api/auth/me` | Current user |
| GET | `/api/products?q=&category=&collection=` | Product cards |
| GET | `/api/products/{product_id}` | One product with stock and SKU per size |
| GET | `/api/categories`, `/api/collections` | Filters |
| GET | `/api/health` | Health check |
| GET | `/media/products/{file}` | Product images |

## What's where

| Path | Contents |
|---|---|
| `AI_prompts.md` | Log of the prompts used for each problem |
| `backend/` | `main.py` (API), `agent.py`, `tools.py`, `models.py`, `prompts/prompt.md` (agent), plus `catalog.py`, `auth.py`, `memory.py`, `audit.py`, `tests/` |
| `frontend/` | React app (`src/pages`, `src/components`, styles) |
| `output/harness.md` | **Start here.** System spec: run steps, limits, agent loop, models, tools, safety rules, audit trail |
| `output/audit_trail.json` | Append-only log of every agent run |
| `output/usability.md` | Problem 9 improvements |
| `output/design.md` | Problem 10 design refresh |
| `output/app_check.html` | Problem 11 end-to-end check (double-click to open; images in `output/app_check_images/`) |
| `tools/app_check.py` | Regenerates the app check |
| `requirements.txt` | Backend Python dependencies |
| `.env.example` | Environment variables (placeholders only) |
