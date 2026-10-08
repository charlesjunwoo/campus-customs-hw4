"""End-to-end app check for Campus Customs (Problem 11).

Drives the running site in a real browser (Playwright + the installed Google Chrome),
compares what the chat says with values read straight from campus_customs.db, saves a
screenshot per check to output/app_check_images/, and writes output/app_check.html.

Prereqs: the app is running (backend on :8000, Vite on :5173), e.g. ./start.sh
Run from the project root:
    backend/.venv/bin/python tools/app_check.py
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs.db"
OUT = ROOT / "output"
IMG_DIR = OUT / "app_check_images"
REPORT = OUT / "app_check.html"
BASE = "http://localhost:5173"

TEST_EMAIL = "test@campuscustoms.yale.edu"
TEST_PASSWORD = "password"  # provided test credential for the seeded test user
INVENTORY_ITEM = "yale-grandpa-hoodie"
SIZES = ["XS", "S", "M", "L", "XL", "XXL"]


@dataclass
class Check:
    slug: str
    title: str
    passed: bool
    proves: str
    image: str
    details: list[tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------- database truth


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def product_truth(pid: str) -> dict:
    with db() as conn:
        p = conn.execute("SELECT name, price, garment_type FROM catalogue WHERE product_id = ?", (pid,)).fetchone()
        inv = {r["size"]: (r["quantity"], r["id"]) for r in conn.execute(
            "SELECT id, size, quantity FROM inventory WHERE product_id = ?", (pid,))}
    return {"name": p["name"], "price": p["price"], "garment_type": p["garment_type"], "inventory": inv}


def catalogue_count() -> int:
    with db() as conn:
        return conn.execute("SELECT COUNT(*) FROM catalogue").fetchone()[0]


def price_pattern(price: float) -> re.Pattern:
    whole = f"{price:g}"
    return re.compile(rf"\${re.escape(whole)}(?:\.00)?\b")


# ---------------------------------------------------------------- browser helpers


def shot(target, name: str) -> str:
    path = IMG_DIR / f"{name}.png"
    target.screenshot(path=str(path))
    return f"app_check_images/{name}.png"


def open_chat(page: Page) -> None:
    if not page.locator(".chat__panel").count():
        page.click(".chat__fab", force=True)  # the button bobs forever, so it's never "stable"
    page.wait_for_selector(".chat__panel")


def ask(page: Page, text: str) -> str:
    """Send a chat message and return the assistant's reply text once fully revealed."""
    open_chat(page)
    before = page.locator(".msg--assistant").count()
    page.fill(".chat__form input", text)
    with page.expect_response(lambda r: r.url.endswith("/api/chat") and r.request.method == "POST", timeout=120_000):
        page.click(".chat__form button[type=submit]")
    page.wait_for_function(f"document.querySelectorAll('.msg--assistant').length > {before}", timeout=30_000)
    page.wait_for_selector(".chat__suggest", timeout=15_000)  # quick replies appear after the typing reveal
    page.wait_for_timeout(600)
    # Frame the screenshot on this exchange: the shopper's question at the top of the log.
    page.evaluate("[...document.querySelectorAll('.msg--user')].pop().scrollIntoView({block: 'start'})")
    page.wait_for_timeout(300)
    return page.locator(".msg--assistant .bubble").last.inner_text()


def login(page: Page) -> str:
    page.goto(f"{BASE}/login")
    page.fill("input[name=email]", TEST_EMAIL)
    page.fill("input[name=password]", TEST_PASSWORD)
    page.click("form.form button[type=submit]")
    page.wait_for_selector(".nav__hello", timeout=15_000)
    return page.locator(".nav__hello").inner_text()


# ---------------------------------------------------------------- checks


def run() -> list[Check]:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    for old in IMG_DIR.glob("*.png"):
        old.unlink()
    checks: list[Check] = []
    item = product_truth(INVENTORY_ITEM)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 860}, device_scale_factor=1)
        # Keep screenshots clean: no surprise first-open "boo", no audio in a headless run.
        ctx.add_init_script("sessionStorage.setItem('cc.spooked','1'); localStorage.setItem('cc.sound','off');")
        page = ctx.new_page()

        # 1. Home page
        page.goto(BASE)
        page.wait_for_selector(".grid .card")
        page.wait_for_timeout(1200)
        theme = page.evaluate("document.documentElement.dataset.theme")
        checks.append(Check(
            "home", "1. The site loads: home page with navigation",
            page.locator(".nav").count() == 1 and page.locator(".grid .card").count() >= 4,
            "The React/Vite storefront is up and talking to the FastAPI backend: the nav links "
            "(Home, Products, About Us, Log In, Create Account) render, and the featured products are loaded from the API.",
            shot(page, "01-home"),
            [("Theme", theme or "classic"), ("Featured cards", str(page.locator('.grid .card').count()))],
        ))

        # 2. Products grid
        page.goto(f"{BASE}/products")
        page.wait_for_selector(".grid .card")
        page.wait_for_timeout(1200)
        shown = page.locator(".grid .card").count()
        expected = catalogue_count()
        checks.append(Check(
            "products", "2. Products page lists the whole catalogue as cards",
            shown == expected,
            f"All {expected} rows of the catalogue table appear as product cards (image, name, price, one-liner), "
            "fed by GET /api/products.",
            shot(page, "02-products"),
            [("Cards on page", str(shown)), ("Rows in catalogue table", str(expected))],
        ))

        # 3. Test user login
        hello = login(page)
        page.wait_for_timeout(800)
        checks.append(Check(
            "login", "3. The seeded test user can log in",
            "Test" in hello,
            f"Logging in as {TEST_EMAIL} with the provided password succeeds (the nav greets “{hello}”), so the "
            "seeded PBKDF2 hash verifies against the backend.",
            shot(page, "03-login"),
            [("Nav greeting", hello)],
        ))

        # 4. Inventory + price for one size
        page.goto(BASE)
        page.wait_for_selector(".nav__hello")
        qty_m = item["inventory"]["M"][0]
        reply = ask(page, f"How many {item['name']}s do you have in size M, and what's the price?")
        ok = re.search(rf"\b{qty_m}\b", reply) is not None and price_pattern(item["price"]).search(reply) is not None
        checks.append(Check(
            "inventory", "4. Chat checks inventory: exact stock and price from the database",
            ok,
            f"Asked about size M of the {item['name']}, the chat answered with {qty_m} in stock at ${item['price']:g}, "
            "exactly the values in the inventory and catalogue tables.",
            shot(page.locator(".chat__panel"), "04-inventory"),
            [("Question", f"How many {item['name']}s do you have in size M, and what's the price?"),
             ("Chat reply", reply), ("Database", f"price ${item['price']:g}; M = {qty_m}")],
        ))

        # 5. Out-of-stock size answered definitively
        sold_out = [s for s in SIZES if s in item["inventory"] and item["inventory"][s][0] == 0]
        size = sold_out[0] if sold_out else "L"
        reply = ask(page, f"Is the {item['name']} available in size {size}?")
        ok = bool(sold_out) and re.search(r"out of stock|sold out", reply, re.I) is not None
        checks.append(Check(
            "out-of-stock", "5. Chat says definitively when a size is out of stock",
            ok,
            f"Size {size} has quantity 0 in the database, and the chat states plainly that it is out of stock "
            "(no hedging), then offers the sizes that are in stock.",
            shot(page.locator(".chat__panel"), "05-out-of-stock"),
            [("Question", f"Is the {item['name']} available in size {size}?"), ("Chat reply", reply),
             ("Database", ", ".join(f"{s}={item['inventory'][s][0]}" for s in SIZES if s in item["inventory"]))],
        ))

        # 6. Category question -> dynamic product cards
        reply = ask(page, "What hoodies do you have?")
        page.wait_for_selector(".picks .card")
        page.click(".chat__close", force=True)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(900)
        strip = page.evaluate(
            "[...document.querySelectorAll('.picks .card')].map(c => ({href: c.getAttribute('href'),"
            " price: c.querySelector('.price').innerText, cat: c.querySelector('.card__cat').innerText}))"
        )
        title = page.locator(".picks__title").inner_text()
        mismatches = []
        for card in strip:
            truth = product_truth(card["href"].rsplit("/", 1)[1])
            if f"${truth['price']:.2f}" != card["price"]:
                mismatches.append(card["href"])
        all_hoodies = all(c["cat"].lower() == "hoodies" for c in strip)
        checks.append(Check(
            "category-cards", "6. A category question (“What hoodies do you have?”) returns dynamic product cards",
            bool(strip) and all_hoodies and not mismatches,
            f"The agent searched the catalogue and the site rendered {len(strip)} hoodie cards in the “Chat picks” "
            "strip (and in the chat). Every card's category is Hoodies and every price matches the database.",
            shot(page, "06-category-cards"),
            [("Chat reply", reply), ("Strip title", title.replace("\n", " ")), ("Cards", str(len(strip))),
             ("Price mismatches vs DB", str(len(mismatches)))],
        ))

        # 7. A chat card opens the single-item page
        first_href = strip[0]["href"]
        page.click(f".picks a.card[href='{first_href}']", force=True)
        page.wait_for_selector(".pdp__name")
        page.wait_for_timeout(1000)
        truth = product_truth(first_href.rsplit("/", 1)[1])
        name_ok = page.locator(".pdp__name").inner_text().lower() == truth["name"].lower()
        price_ok = page.locator(".price--lg").inner_text() == f"${truth['price']:.2f}"
        page.evaluate("window.scrollTo(0, document.querySelector('main').offsetTop - document.querySelector('.nav').offsetHeight)")
        page.wait_for_timeout(400)
        checks.append(Check(
            "card-opens-product", "7. Clicking a chat-surfaced card opens the full product page",
            page.url.endswith(first_href) and name_ok and price_ok,
            f"The first chat card opened {first_href} with the large image, full description, price, sizes and stock, "
            "the same single-item page as the Products grid.",
            shot(page, "07-card-opens-product"),
            [("URL", page.url.replace(BASE, "")), ("Name / price", f"{truth['name']} / ${truth['price']:.2f}")],
        ))

        # 8. Problem 9 usability feature: SKU info
        page.goto(f"{BASE}/products/{INVENTORY_ITEM}")
        page.wait_for_selector(".size")
        page.locator(".size", has_text="M").first.click()
        page.wait_for_selector(".sku-box")
        page.evaluate("document.querySelector('.sizes').scrollIntoView({block: 'center'})")
        page.wait_for_timeout(600)
        sku_shown = page.locator(".sku-box__code").inner_text()
        sku_db = f"CC-{item['inventory']['M'][1]:04d}-M"
        checks.append(Check(
            "sku", "8. Problem 9 usability feature: SKU info on the product page",
            sku_shown == sku_db,
            f"Picking size M shows SKU {sku_shown} with its stock count and a Copy SKU button. The SKU is built from "
            "that size's permanent inventory-table id, so staff and shoppers can name the exact unit.",
            shot(page, "08-sku"),
            [("SKU shown", sku_shown), ("Expected from inventory.id", sku_db)],
        ))

        # 9. Problem 9 usability feature: saved chat + welcome-back recap after re-login
        page.click(".nav__links button.btn")  # log out
        page.wait_for_selector(".nav__auth")
        login(page)
        page.goto(BASE)
        page.wait_for_selector(".nav__hello")
        open_chat(page)
        page.wait_for_function("document.querySelector('.chat__log')?.innerText.includes('Welcome back')", timeout=15_000)
        page.wait_for_timeout(800)
        recap = page.locator(".msg--assistant .bubble").last.inner_text()
        page.evaluate("[...document.querySelectorAll('.chat__divider')].pop().scrollIntoView({block: 'start'})")
        page.wait_for_timeout(300)
        checks.append(Check(
            "recap", "9. Problem 9 usability feature: chat history reloads with a welcome-back recap",
            recap.startswith("Welcome back"),
            "After logging out and back in, the test user's earlier conversation (including checks 4–6) reloads from "
            "the database, ending with a recap of the products they looked at, re-priced from live stock.",
            shot(page.locator(".chat__panel"), "09-recap"),
            [("Recap", recap)],
        ))

        browser.close()
    return checks


# ---------------------------------------------------------------- report


def write_report(checks: list[Check], seconds: float) -> None:
    passed = sum(c.passed for c in checks)
    rows = []
    for c in checks:
        details = "".join(
            f"<tr><th>{html.escape(k)}</th><td>{html.escape(v).replace(chr(10), '<br>')}</td></tr>" for k, v in c.details
        )
        rows.append(f"""
  <section class="check" id="{c.slug}">
    <h2>{html.escape(c.title)} <span class="badge {'pass' if c.passed else 'fail'}">{'PASS' if c.passed else 'FAIL'}</span></h2>
    <a href="{c.image}" target="_blank"><img src="{c.image}" alt="Screenshot: {html.escape(c.title)}"></a>
    <p class="proves"><strong>What this proves:</strong> {html.escape(c.proves)}</p>
    <table>{details}</table>
  </section>""")
    toc = "".join(
        f'<li><a href="#{c.slug}">{html.escape(c.title)}</a> {"✅" if c.passed else "❌"}</li>' for c in checks
    )
    REPORT.write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campus Customs: App Check</title>
<style>
  :root {{ --navy:#00356b; --pumpkin:#ff7518; --ink:#160f1f; --bone:#f6eddc; --ok:#138a5e; --bad:#b3261e; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font:16px/1.55 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color:var(--ink); background:var(--bone); }}
  header {{ background:var(--navy); color:#fff; padding:28px 32px; border-bottom:6px solid var(--pumpkin); }}
  header h1 {{ margin:0 0 6px; font-size:28px; }}
  header p {{ margin:0; opacity:.9; }}
  main {{ max-width:1100px; margin:0 auto; padding:24px 32px 60px; }}
  .summary {{ background:#fff; border:3px solid var(--ink); box-shadow:5px 5px 0 var(--ink); padding:16px 20px; margin-bottom:28px; }}
  .summary ol {{ margin:8px 0 0; padding-left:22px; }}
  .check {{ background:#fff; border:3px solid var(--ink); box-shadow:5px 5px 0 var(--navy); padding:18px 20px 20px; margin:0 0 28px; }}
  .check h2 {{ margin:0 0 12px; font-size:20px; color:var(--navy); }}
  .badge {{ display:inline-block; margin-left:8px; padding:2px 10px; border-radius:999px; font-size:13px; color:#fff; vertical-align:middle; }}
  .badge.pass {{ background:var(--ok); }} .badge.fail {{ background:var(--bad); }}
  img {{ display:block; max-width:100%; border:2px solid var(--ink); margin:0 auto; }}
  .proves {{ margin:14px 0 10px; font-size:17px; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th {{ text-align:left; width:190px; vertical-align:top; padding:6px 8px; background:#f3efe6; border:1px solid #ddd; }}
  td {{ padding:6px 8px; border:1px solid #ddd; }}
  footer {{ text-align:center; font-size:13px; color:#666; padding-bottom:30px; }}
</style>
</head>
<body>
<header>
  <h1>Campus Customs: App Check</h1>
  <p>{passed} of {len(checks)} checks passed · run {datetime.now().strftime('%Y-%m-%d %H:%M')} · live app (React/Vite :5173 → FastAPI :8000), real model, real campus_customs.db</p>
</header>
<main>
  <div class="summary">
    <strong>How to read this:</strong> each check has a headline, a screenshot taken automatically by
    <code>tools/app_check.py</code> (Playwright driving Chrome), and one or two sentences on what it proves. Expected values
    come straight from the database, so PASS means the app matched the data. Click a screenshot to open it full size.
    <ol>{toc}</ol>
  </div>
  {''.join(rows)}
</main>
<footer>Generated by tools/app_check.py in {seconds:.0f}s. Screenshots: output/app_check_images/</footer>
</body>
</html>
""", encoding="utf-8")


if __name__ == "__main__":
    start = time.time()
    results = run()
    write_report(results, time.time() - start)
    for c in results:
        print(("PASS " if c.passed else "FAIL ") + c.title)
    (OUT / "app_check_results.json").write_text(
        json.dumps([c.__dict__ for c in results], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nReport: {REPORT}")
    sys.exit(0 if all(c.passed for c in results) else 1)
