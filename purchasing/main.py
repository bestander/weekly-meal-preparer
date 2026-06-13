import asyncio
import json
import pathlib
import sys
from dataclasses import dataclass

from purchasing.pantry_db import PantryDB
from purchasing.ingredient_resolver import resolve_ingredients
from purchasing.cli_approval import run_approval, CART_URL
from purchasing.cart_builder import build_cart
from purchasing.checkout import run_checkout, OrderConfirmation
from purchasing.auth import is_session_valid, load_session
from purchasing.prices import make_price_lookup, _parse_price

DEFAULT_RECIPE_PATH = "recipes/current-week.json"
DEFAULT_DB_PATH = "data/pantry.db"
DEFAULT_SESSION_PATH = "data/session.json"


@dataclass
class CartResult:
    items_added: int
    items_requested: int
    cart_url: str = CART_URL


def _make_amazon_search(session_path: str):
    """Return a search function that uses the saved Amazon session."""

    def _amazon_search(query: str) -> list[dict]:
        from playwright.sync_api import sync_playwright
        from purchasing.stealth import apply_stealth_sync

        cookies = load_session(session_path)
        if cookies is None:
            raise RuntimeError(
                f"No session found at {session_path}. Run: python -m purchasing auth login"
            )

        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            context.add_cookies(cookies)
            page = context.new_page()
            apply_stealth_sync(page)
            url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}&i=wholefoods"
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector("[data-component-type='s-search-result']", timeout=10_000)

            for item in page.query_selector_all("[data-component-type='s-search-result']")[:3]:
                try:
                    asin = item.get_attribute("data-asin")
                    title_el = item.query_selector("h2 span, .a-text-normal")
                    price_el = item.query_selector(".a-price .a-offscreen")
                    title = title_el.inner_text().strip() if title_el else "Unknown"
                    price_text = price_el.inner_text() if price_el else ""
                    price = _parse_price(price_text)
                    if asin:
                        results.append({"asin": asin, "title": title, "price": price})
                except Exception:
                    continue

            browser.close()
        return results

    return _amazon_search


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
    checkout: bool = False,
) -> CartResult | OrderConfirmation | None:
    """Run the weekly ordering pipeline. Stops at cart unless checkout=True."""
    p = pathlib.Path(recipe_path)
    if not p.exists():
        raise FileNotFoundError(f"Recipe file not found: {recipe_path}")
    meals = json.loads(p.read_text())["meals"]

    if not is_session_valid(session_path):
        print("Amazon session missing or expired. Run: python -m purchasing auth login")
        sys.exit(1)

    pantry = PantryDB(db_path)
    print("Resolving ingredients...")
    search = search_fn or _make_amazon_search(session_path)
    price_fn = None if search_fn else make_price_lookup(session_path)
    resolved = resolve_ingredients(meals, pantry, search, price_fn)

    approval = run_approval(resolved, meals, search)
    if approval is None:
        return None

    if not approval.confirmed_items:
        print("\nNo items to order.")
        return CartResult(items_added=0, items_requested=0)

    _save_confirmed_to_pantry(pantry, approval.confirmed_items)

    print("\nBuilding cart...")
    added = asyncio.run(build_cart(session_path, approval.confirmed_items))

    print(f"\nCart ready: {CART_URL}")
    print(f"Added {len(added)} of {len(approval.confirmed_items)} items.")
    if approval.skipped_items:
        print(f"Skipped {len(approval.skipped_items)} items already on hand.")

    if not checkout:
        return CartResult(items_added=len(added), items_requested=len(approval.confirmed_items))

    estimated_total = sum(i.get("price") or 0 for i in approval.confirmed_items)
    print("\nProceeding to checkout...")
    return asyncio.run(run_checkout(session_path, estimated_total))
