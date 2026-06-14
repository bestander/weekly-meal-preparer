"""Tests for cross-meal ingredient aggregation."""

from purchasing.ingredient_aggregate import aggregate_ingredients, normalize_ingredient_key


def test_sums_same_unit_quantities():
    meals = [
        {
            "name": "Meal A",
            "ingredients": [{"name": "Potatoes", "quantity": 12, "unit": "oz"}],
        },
        {
            "name": "Meal B",
            "ingredients": [{"name": "Potatoes", "quantity": 12, "unit": "oz"}],
        },
    ]
    agg = aggregate_ingredients(meals)
    potatoes = next(i for i in agg if i["name"] == "Potatoes")
    assert potatoes["quantity"] == 24
    assert potatoes["unit"] == "oz"
    assert potatoes["order_once"] is False
    assert len(potatoes["meals"]) == 2


def test_converts_pounds_to_ounces():
    meals = [
        {
            "name": "Meal A",
            "ingredients": [{"name": "Ground Beef", "quantity": 0.5, "unit": "lb"}],
        },
        {
            "name": "Meal B",
            "ingredients": [{"name": "Ground Beef", "quantity": 0.5, "unit": "lb"}],
        },
    ]
    agg = aggregate_ingredients(meals)
    beef = next(i for i in agg if i["name"] == "Ground Beef")
    assert beef["quantity"] == 16
    assert beef["unit"] == "oz"


def test_garlic_orders_once_across_meals():
    meals = [
        {
            "name": "Meal A",
            "ingredients": [{"name": "Garlic", "quantity": 2, "unit": "cloves"}],
        },
        {
            "name": "Meal B",
            "ingredients": [{"name": "Garlic", "quantity": 4, "unit": "cloves"}],
        },
    ]
    agg = aggregate_ingredients(meals)
    garlic = next(i for i in agg if i["name"] == "Garlic")
    assert garlic["quantity"] == 6
    assert garlic["order_once"] is True
    assert len(garlic["meals"]) == 2


def test_merges_onion_aliases():
    meals = [
        {
            "name": "Meal A",
            "ingredients": [{"name": "Yellow Onion", "quantity": 2, "unit": "pieces"}],
        },
        {
            "name": "Meal B",
            "ingredients": [{"name": "Onion", "quantity": 1, "unit": "pieces"}],
        },
    ]
    agg = aggregate_ingredients(meals)
    assert normalize_ingredient_key("Yellow Onion") == "onion"
    onions = [i for i in agg if normalize_ingredient_key(i["name"]) == "onion"]
    assert len(onions) == 1
    assert onions[0]["quantity"] == 3
