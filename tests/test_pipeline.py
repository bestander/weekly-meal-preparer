"""Integration harness for the meal ordering pipeline.

These tests exercise real module wiring with a fake Amazon boundary.
They are meant to catch regressions in user-visible behavior, not to
re-test trivial helpers in isolation.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from purchasing.cart_builder import CartItem
from purchasing.ingredient_resolver import resolve_ingredients
from purchasing.main import run_pipeline, CartResult
from purchasing.checkout import OrderConfirmation
from purchasing.pantry_db import PantryDB


def _cart_items(items: list[dict]) -> list[CartItem]:
    return [
        CartItem(
            name=item["name"],
            asin=item["asin"],
            product_title=item["product_title"],
            price=item.get("price") or 0,
        )
        for item in items
    ]


class PipelineHarness:
    def __init__(self, recipe_path, db_path, session_path, amazon):
        self.recipe_path = recipe_path
        self.db_path = db_path
        self.session_path = session_path
        self.amazon = amazon
        self.cart_calls: list[list[dict]] = []

    async def _capture_cart(self, _session_path, items):
        self.cart_calls.append(items)
        return _cart_items(items)

    def run(self, inputs: list[str], checkout: bool = False):
        with patch("builtins.input", side_effect=inputs), \
             patch("purchasing.main.build_cart", side_effect=self._capture_cart) as mock_cart, \
             patch("purchasing.main.run_checkout", new_callable=AsyncMock) as mock_checkout:
            result = run_pipeline(
                self.recipe_path,
                self.db_path,
                self.session_path,
                search_fn=self.amazon.search,
                checkout=checkout,
            )
        return result, mock_cart, mock_checkout


@pytest.fixture
def harness(write_recipe, mixed_meal, mixed_catalog, db_path, session_path):
    recipe_path = write_recipe(mixed_meal)
    return PipelineHarness(recipe_path, db_path, session_path, mixed_catalog)


def test_resolve_classifies_specialty_and_generic(write_recipe, mixed_meal, mixed_catalog, pantry):
    recipe_path = write_recipe(mixed_meal)
    meals = json.loads(Path(recipe_path).read_text())["meals"]
    resolved = resolve_ingredients(meals, pantry, mixed_catalog.search, mixed_catalog.price_for_asin)

    by_name = {item.name: item for item in resolved}
    assert by_name["Baby Spinach"].status == "auto"
    assert by_name["Baby Spinach"].asin == "B_SPIN"
    assert by_name["Baby Spinach"].price == 3.49

    assert by_name["Paneer Cheese"].status == "review"
    assert by_name["Paneer Cheese"].candidates[0]["asin"] == "B_PAN1"

    assert by_name["Vadouvan Curry Powder"].status == "review"


def test_pantry_recall_keeps_asin_and_refreshes_price(write_recipe, mixed_meal, mixed_catalog, pantry):
    pantry.save("baby spinach", "B_SPIN", "Saved Spinach", confirmed_by_user=True)
    meals = mixed_meal
    resolved = resolve_ingredients(meals, pantry, mixed_catalog.search, mixed_catalog.price_for_asin)
    spinach = next(item for item in resolved if item.name == "Baby Spinach")

    assert spinach.asin == "B_SPIN"
    assert spinach.price == 3.49
    assert spinach.price != 0


def test_pantry_uses_price_lookup_when_search_top_results_differ(write_recipe, mixed_meal, pantry):
    pantry.save("baby spinach", "B_STALE", "Saved Spinach", confirmed_by_user=True)

    def search(_query):
        return [{"asin": "B_OTHER", "title": "Different Spinach", "price": 9.99}]

    def price_fn(asin):
        return 2.49 if asin == "B_STALE" else None

    resolved = resolve_ingredients(mixed_meal, pantry, search, price_fn)
    spinach = next(item for item in resolved if item.name == "Baby Spinach")

    assert spinach.asin == "B_STALE"
    assert spinach.price == 2.49


def test_pipeline_confirm_builds_cart_without_checkout(harness):
    result, mock_cart, mock_checkout = harness.run(["", "1", "1", "c"])

    assert isinstance(result, CartResult)
    assert result.items_added == 3
    assert result.cart_url == "https://www.amazon.com/cart"
    mock_cart.assert_called_once()
    mock_checkout.assert_not_called()

    sent_asins = {item["asin"] for item in harness.cart_calls[0]}
    assert sent_asins == {"B_SPIN", "B_PAN1", "B_VAD1"}


def test_pipeline_persists_confirmed_mappings_to_pantry(harness, db_path):
    harness.run(["", "2", "1", "c"])

    pantry = PantryDB(db_path)
    paneer = pantry.get("Paneer Cheese")
    vadouvan = pantry.get("Vadouvan Curry Powder")

    assert paneer["asin"] == "B_PAN2"
    assert paneer["confirmed_by_user"] is True
    assert vadouvan["asin"] == "B_VAD1"


def test_pipeline_skips_items_already_on_hand(harness):
    result, mock_cart, _ = harness.run(["1", "s", "1", "c"])

    assert isinstance(result, CartResult)
    assert result.items_added == 1
    assert len(harness.cart_calls[0]) == 1
    assert harness.cart_calls[0][0]["name"] == "Vadouvan Curry Powder"


def test_pipeline_all_skipped_never_builds_cart(write_recipe, mixed_meal, mixed_catalog, db_path, session_path):
    recipe_path = write_recipe([{
        "name": "Only Specialty",
        "servings": 2,
        "ingredients": [{"name": "Paneer Cheese", "quantity": 8, "unit": "oz"}],
    }])
    harness = PipelineHarness(recipe_path, db_path, session_path, mixed_catalog)

    with patch("builtins.input", side_effect=["s", "c"]), \
         patch("purchasing.main.build_cart", new_callable=AsyncMock) as mock_cart:
        result = run_pipeline(
            recipe_path, db_path, session_path,
            search_fn=mixed_catalog.search,
        )

    assert isinstance(result, CartResult)
    assert result.items_requested == 0
    mock_cart.assert_not_called()


def test_pipeline_cancel_does_not_touch_cart_or_pantry(harness, db_path):
    with patch("builtins.input", side_effect=["", "x"]), \
         patch("purchasing.main.build_cart", new_callable=AsyncMock) as mock_cart:
        result = run_pipeline(
            harness.recipe_path,
            harness.db_path,
            harness.session_path,
            search_fn=harness.amazon.search,
        )

    assert result is None
    mock_cart.assert_not_called()
    assert PantryDB(db_path).get("Paneer Cheese") is None


def test_pipeline_checkout_only_when_explicitly_requested(harness):
    checkout_result = OrderConfirmation("123-456", 18.47)

    with patch("builtins.input", side_effect=["", "1", "1", "c"]), \
         patch("purchasing.main.build_cart", side_effect=harness._capture_cart), \
         patch("purchasing.main.run_checkout", new_callable=AsyncMock, return_value=checkout_result) as mock_checkout:
        result = run_pipeline(
            harness.recipe_path,
            harness.db_path,
            harness.session_path,
            search_fn=harness.amazon.search,
            checkout=True,
        )

    assert result.order_id == "123-456"
    mock_checkout.assert_called_once()


def test_real_recipe_fixtures_resolve_through_pipeline(write_recipe, pantry, session_path):
    """Guard the real recipe JSON files against schema drift and pipeline breakage."""
    catalog = {
        "Naan Bread": [{"asin": "B_NAAN", "title": "Naan", "price": 4.99}],
        "Chickpeas": [{"asin": "B_CHICK", "title": "Chickpeas", "price": 1.29}],
        "Paneer Cheese": [{"asin": "B_PAN", "title": "Paneer", "price": 5.99}],
        "Baby Spinach": [{"asin": "B_SPIN", "title": "Spinach", "price": 3.49}],
        "Heavy Cream": [{"asin": "B_CREAM", "title": "Cream", "price": 4.29}],
        "Labneh Cheese": [{"asin": "B_LAB", "title": "Labneh", "price": 6.99}],
        "Tomato Achaar": [{"asin": "B_ACH", "title": "Achaar", "price": 7.99}],
        "Tomato Sauce": [{"asin": "B_SAUCE", "title": "Sauce", "price": 2.59}],
        "Vadouvan Curry Powder": [{"asin": "B_VAD", "title": "Vadouvan", "price": 8.99}],
        "Potatoes": [{"asin": "B_POT", "title": "Potatoes", "price": 5.99}],
        "Onion": [{"asin": "B_ONION", "title": "Onion", "price": 2.49}],
        "Dried Thyme": [{"asin": "B_THYME", "title": "Thyme", "price": 3.99}],
        "Beef for Braising": [{"asin": "B_BEEF", "title": "Beef", "price": 12.99}],
        "Beef Stock Concentrate": [{"asin": "B_STOCK", "title": "Stock", "price": 4.99}],
        "Worcestershire Sauce": [{"asin": "B_WORC", "title": "Worcestershire", "price": 3.49}],
        "Carrots": [{"asin": "B_CARROT", "title": "Carrots", "price": 2.99}],
        "Flour": [{"asin": "B_FLOUR", "title": "Flour", "price": 5.49}],
        "Swiss Cheese": [{"asin": "B_SWISS", "title": "Swiss", "price": 4.99}],
        "Garlic Powder": [{"asin": "B_GARLIC", "title": "Garlic Powder", "price": 2.99}],
        "Demi-Baguette": [{"asin": "B_BAG", "title": "Baguette", "price": 3.99}],
    }

    def search(query):
        return catalog.get(query, [{"asin": "B_TEST", "title": query, "price": 1.0}])

    from purchasing.ingredient_aggregate import aggregate_ingredients

    for recipe_path in Path("recipes").glob("week-*.json"):
        meals = json.loads(recipe_path.read_text())["meals"]
        resolved = resolve_ingredients(meals, pantry, search)
        assert len(resolved) == len(aggregate_ingredients(meals))
        assert all(item.name for item in resolved)


@pytest.mark.parametrize("specialty", [
    "Paneer Cheese",
    "Vadouvan Curry Powder",
    "Tomato Achaar",
    "Labneh Cheese",
])
def test_specialty_ingredients_always_require_review(specialty, pantry):
    def search(_query):
        return [{"asin": "B001", "title": "Candidate", "price": 1.0}]

    meals = [{"name": "Test", "servings": 2, "ingredients": [
        {"name": specialty, "quantity": 1, "unit": "unit"},
    ]}]
    resolved = resolve_ingredients(meals, pantry, search)
    assert resolved[0].status == "review"
    assert resolved[0].asin is None
    assert len(resolved[0].candidates) == 1
