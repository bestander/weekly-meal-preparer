"""Web-oriented purchase commands (JSON line protocol on stdout)."""

import asyncio
import json
import pathlib

from purchasing.approval import apply_approval
from purchasing.auth import is_session_valid
from purchasing.cli_approval import CART_URL
from purchasing.ingredient_resolver import resolve_ingredients_async
from purchasing.main import (
    DEFAULT_DB_PATH,
    DEFAULT_RECIPE_PATH,
    DEFAULT_SESSION_PATH,
    _save_confirmed_to_pantry,
)
from purchasing.search_stack import run_cached_search_session
from purchasing.pantry_db import PantryDB
from purchasing.serialize import resolved_from_dict, resolved_to_dict
from purchasing.cart_builder import build_cart, dedupe_by_asin, dedupe_by_asin


def _emit(obj: dict) -> None:
    print(json.dumps(obj), flush=True)


async def _resolve_meals(meals, pantry, session_path, on_progress):
    async def run(search, price_fn):
        return await resolve_ingredients_async(
            meals, pantry, search, price_fn, on_progress=on_progress,
        )

    return await run_cached_search_session(session_path, run)


def cmd_resolve(
    recipe_path: str = DEFAULT_RECIPE_PATH,
    db_path: str = DEFAULT_DB_PATH,
    session_path: str = DEFAULT_SESSION_PATH,
) -> int:
    p = pathlib.Path(recipe_path)
    if not p.exists():
        _emit({"type": "error", "message": f"Recipe file not found: {recipe_path}"})
        return 1

    if not is_session_valid(session_path):
        _emit({"type": "error", "message": "Amazon session missing or expired."})
        return 1

    meals = json.loads(p.read_text())["meals"]
    pantry = PantryDB(db_path)

    def on_progress(event: dict) -> None:
        _emit({"type": "progress", **event})

    try:
        resolved = asyncio.run(_resolve_meals(meals, pantry, session_path, on_progress))
    except Exception as exc:
        _emit({"type": "error", "message": str(exc)})
        return 1

    _emit({
        "type": "done",
        "meals": [m["name"] for m in meals],
        "resolved": [resolved_to_dict(item, i) for i, item in enumerate(resolved)],
    })
    return 0


async def _finish_cart(session_path, items, on_cart_progress):
    return await build_cart(session_path, items, on_progress=on_cart_progress)


def cmd_finish(
    approval_path: str,
    db_path: str = DEFAULT_DB_PATH,
    session_path: str = DEFAULT_SESSION_PATH,
    checkout: bool = False,
) -> int:
    data = json.loads(pathlib.Path(approval_path).read_text())
    resolved = [resolved_from_dict(item) for item in data["resolved"]]
    skipped_auto = set(data.get("skippedAuto") or [])
    review_picks = {int(k): int(v) for k, v in (data.get("reviewPicks") or {}).items()}

    try:
        approval = apply_approval(resolved, skipped_auto, review_picks)
    except ValueError as exc:
        _emit({"type": "error", "message": str(exc)})
        return 1

    if not approval.confirmed_items:
        _emit({"type": "done", "itemsAdded": 0, "itemsRequested": 0, "cartUrl": CART_URL})
        return 0

    pantry = PantryDB(db_path)
    _save_confirmed_to_pantry(pantry, approval.confirmed_items)

    cart_items = dedupe_by_asin(approval.confirmed_items)
    _emit({
        "type": "progress",
        "phase": "cart",
        "message": "Adding items to cart…",
        "current": 0,
        "total": len(cart_items),
        "itemsAdded": 0,
        "cartTotal": 0,
    })

    def on_cart_progress(event: dict) -> None:
        _emit({
            "type": "progress",
            "message": f"Adding {event['name']}…",
            **event,
        })

    async def _run_finish():
        added = await _finish_cart(session_path, approval.confirmed_items, on_cart_progress)
        result = {
            "type": "done",
            "itemsAdded": len(added),
            "itemsRequested": len(approval.confirmed_items),
            "cartTotal": sum(i.price or 0 for i in added),
            "cartUrl": CART_URL,
            "skippedItems": approval.skipped_items,
        }
        if checkout:
            from purchasing.checkout import run_checkout
            _emit({"type": "progress", "phase": "checkout", "message": "Proceeding to checkout…"})
            estimated_total = sum(i.get("price") or 0 for i in approval.confirmed_items)
            confirmation = await run_checkout(session_path, estimated_total)
            result["checkout"] = {
                "orderId": confirmation.order_id,
                "total": confirmation.total,
            }
        return result

    try:
        result = asyncio.run(_run_finish())
    except Exception as exc:
        _emit({"type": "error", "message": str(exc)})
        return 1

    _emit(result)
    return 0


async def _search_one(ingredient, session_path):
    async def run(search, _price_fn):
        return (await search(ingredient))[:3]

    return await run_cached_search_session(session_path, run)


def cmd_search_one(
    ingredient: str,
    session_path: str = DEFAULT_SESSION_PATH,
) -> int:
    if not is_session_valid(session_path):
        _emit({"type": "error", "message": "Amazon session missing or expired."})
        return 1

    try:
        candidates = asyncio.run(_search_one(ingredient, session_path))
    except Exception as exc:
        _emit({"type": "error", "message": str(exc)})
        return 1

    _emit({"type": "done", "candidates": candidates})
    return 0
