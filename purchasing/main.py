import asyncio
import json
import pathlib
import sys

from purchasing.pantry_db import PantryDB
from purchasing.ingredient_resolver import resolve_ingredients
from purchasing.cli_approval import run_approval
from purchasing.cart_builder import build_cart
from purchasing.checkout import run_checkout, OrderConfirmation
from purchasing.auth import is_session_valid

DEFAULT_RECIPE_PATH = "recipes/current-week.json"
DEFAULT_DB_PATH = "data/pantry.db"
DEFAULT_SESSION_PATH = "data/session.json"


def _amazon_search(query: str) -> list[dict]:
    """Live Amazon Whole Foods product search using Playwright."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import stealth_sync

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        stealth_sync(page)
        url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}&i=wholefoods"
        page.goto(url, wait_until="domcontentloaded")

        for item in page.query_selector_all("[data-component-type='s-search-result']")[:3]:
            try:
                asin = item.get_attribute("data-asin")
                title_el = item.query_selector("h2 a span")
                price_el = item.query_selector(".a-price .a-offscreen")
                title = title_el.inner_text() if title_el else "Unknown"
                price_text = price_el.inner_text() if price_el else "$0"
                price = float(price_text.replace("$", "").replace(",", "").strip())
                if asin:
                    results.append({"asin": asin, "title": title, "price": price})
            except Exception:
                continue

        browser.close()
    return results


def _save_confirmed_to_pantry(pantry: PantryDB, confirmed_items: list[dict]) -> None:
    for item in confirmed_items:
        existing = pantry.get(item["name"])
        if existing is None or not existing["confirmed_by_user"]:
            pantry.save(item["name"], item["asin"], item["product_title"], confirmed_by_user=True)


def run_pipeline(
    recipe_path: str = DEFAULT_RECIPE_PATH,
    db_path: str = DEFAULT_DB_PATH,
    session_path: str = DEFAULT_SESSION_PATH,
    search_fn=None,
) -> OrderConfirmation | None:
    """Run the full weekly ordering pipeline. Returns OrderConfirmation or None if cancelled."""
    p = pathlib.Path(recipe_path)
    if not p.exists():
        raise FileNotFoundError(f"Recipe file not found: {recipe_path}")
    meals = json.loads(p.read_text())["meals"]

    if not is_session_valid(session_path):
        print("Amazon session missing or expired. Run: python -m purchasing auth login")
        sys.exit(1)

    pantry = PantryDB(db_path)
    print("Resolving ingredients...")
    resolved = resolve_ingredients(meals, pantry, search_fn or _amazon_search)

    approval = run_approval(resolved, meals)
    if approval is None:
        return None

    _save_confirmed_to_pantry(pantry, approval.confirmed_items)

    estimated_total = sum(i.get("price") or 0 for i in approval.confirmed_items)
    print("\nBuilding cart...")
    asyncio.run(build_cart(session_path, approval.confirmed_items))

    print("\nProceeding to checkout...")
    return asyncio.run(run_checkout(session_path, estimated_total))
