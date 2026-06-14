import asyncio
import json
import pathlib
import sys
from dataclasses import dataclass

from purchasing.pantry_db import PantryDB
from purchasing.ingredient_resolver import resolve_ingredients, resolve_ingredients_async
from purchasing.cli_approval import run_approval, CART_URL
from purchasing.cart_builder import build_cart
from purchasing.checkout import run_checkout, OrderConfirmation
from purchasing.auth import is_session_valid
from purchasing.search_stack import run_cached_search_session

DEFAULT_RECIPE_PATH = "recipes/current-week.json"
DEFAULT_DB_PATH = "data/pantry.db"
DEFAULT_SESSION_PATH = "data/session.json"


@dataclass
class CartResult:
    items_added: int
    items_requested: int
    cart_url: str = CART_URL


def _save_confirmed_to_pantry(pantry: PantryDB, confirmed_items: list[dict]) -> None:
    for item in confirmed_items:
        existing = pantry.get(item["name"])
        if existing is None or not existing["confirmed_by_user"]:
            pantry.save(item["name"], item["asin"], item["product_title"], confirmed_by_user=True)


async def _resolve_for_pipeline(meals, pantry, session_path):
    async def run(search, price_fn):
        return await resolve_ingredients_async(meals, pantry, search, price_fn)

    return await run_cached_search_session(session_path, run)


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

    if search_fn is not None:
        resolved = resolve_ingredients(meals, pantry, search_fn)
    else:
        resolved = asyncio.run(_resolve_for_pipeline(meals, pantry, session_path))

    approval = run_approval(resolved, meals, search_fn)
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
