"""Tests for shared web/CLI approval logic."""

import pytest

from purchasing.approval import apply_approval
from purchasing.ingredient_resolver import ResolvedIngredient


def _auto(name, price=1.0):
    return ResolvedIngredient(
        name=name, quantity=1, unit="oz", status="auto",
        asin="B1", product_title=f"{name} Product", price=price,
    )


def _review(name, idx):
    return ResolvedIngredient(
        name=name, quantity=1, unit="oz", status="review",
        candidates=[
            {"asin": f"B_{idx}a", "title": f"{name} A", "price": 2.0},
            {"asin": f"B_{idx}b", "title": f"{name} B", "price": 3.0},
        ],
    )


def test_apply_approval_skips_auto_and_review():
    resolved = [_auto("Rice", 5.0), _auto("Onion", 2.0), _review("Paneer", 1)]
    result = apply_approval(resolved, skipped_auto={1}, review_picks={2: 0})

    assert len(result.confirmed_items) == 2
    assert result.confirmed_items[0]["name"] == "Rice"
    assert result.confirmed_items[1]["name"] == "Paneer"
    assert "Onion" in result.skipped_items


def test_apply_approval_requires_review_pick():
    resolved = [_review("Paneer", 1)]
    with pytest.raises(ValueError, match="No pick"):
        apply_approval(resolved, skipped_auto=set(), review_picks={})
