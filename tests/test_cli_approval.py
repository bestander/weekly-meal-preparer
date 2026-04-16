from unittest.mock import patch
import pytest
from purchasing.ingredient_resolver import ResolvedIngredient
from purchasing.cli_approval import run_approval, ApprovalResult

AUTO_ITEMS = [
    ResolvedIngredient("Baby Spinach", 6, "oz", "auto", "B001", "365 Baby Spinach 5oz", 3.49, []),
    ResolvedIngredient("Tomato Sauce", 2, "8oz can", "auto", "B002", "365 Tomato Sauce", 2.59, []),
]

REVIEW_ITEMS = [
    ResolvedIngredient("Paneer Cheese", 8, "oz", "review", None, None, None, [
        {"asin": "B010", "title": "Gopi Paneer 12oz", "price": 5.99},
        {"asin": "B011", "title": "Nanak Paneer 14oz", "price": 6.49},
        {"asin": "B012", "title": "365 Paneer 8oz", "price": 4.99},
    ]),
]

MEALS = [{"name": "Test Meal", "servings": 2, "ingredients": []}]

def test_cancel_returns_none():
    with patch("builtins.input", return_value="x"):
        result = run_approval(AUTO_ITEMS, MEALS)
    assert result is None

def test_confirm_auto_only_returns_approval():
    with patch("builtins.input", return_value="c"):
        result = run_approval(AUTO_ITEMS, MEALS)
    assert isinstance(result, ApprovalResult)
    assert result.approved is True
    assert len(result.confirmed_items) == 2

def test_review_item_pick_is_captured():
    # inputs: pick candidate 1 for paneer, then confirm
    with patch("builtins.input", side_effect=["1", "c"]):
        result = run_approval(AUTO_ITEMS + REVIEW_ITEMS, MEALS)
    assert result is not None
    paneer = next(i for i in result.confirmed_items if i["name"] == "Paneer Cheese")
    assert paneer["asin"] == "B010"
    assert paneer["product_title"] == "Gopi Paneer 12oz"

def test_review_item_requires_valid_pick():
    # first input invalid, second valid, then confirm
    with patch("builtins.input", side_effect=["9", "2", "c"]):
        result = run_approval(AUTO_ITEMS + REVIEW_ITEMS, MEALS)
    assert result is not None
    paneer = next(i for i in result.confirmed_items if i["name"] == "Paneer Cheese")
    assert paneer["asin"] == "B011"

def test_confirmed_items_include_auto_matches():
    with patch("builtins.input", side_effect=["1", "c"]):
        result = run_approval(AUTO_ITEMS + REVIEW_ITEMS, MEALS)
    names = {i["name"] for i in result.confirmed_items}
    assert "Baby Spinach" in names
    assert "Tomato Sauce" in names
    assert "Paneer Cheese" in names
