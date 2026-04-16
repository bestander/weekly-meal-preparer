from purchasing.ingredient_resolver import classify_ingredient

def test_single_word_generic_is_auto():
    assert classify_ingredient("Chickpeas") == "auto"

def test_two_word_generic_is_auto():
    assert classify_ingredient("Baby Spinach") == "auto"
    assert classify_ingredient("Tomato Sauce") == "auto"
    assert classify_ingredient("Heavy Cream") == "auto"
    assert classify_ingredient("Naan Bread") == "auto"

def test_specialty_single_term_triggers_review():
    assert classify_ingredient("Vadouvan Curry Powder") == "review"
    assert classify_ingredient("Tomato Achaar") == "review"

def test_specialty_cheese_triggers_review():
    assert classify_ingredient("Labneh Cheese") == "review"
    assert classify_ingredient("Paneer Cheese") == "review"

def test_classification_is_case_insensitive():
    assert classify_ingredient("vadouvan curry powder") == "review"
    assert classify_ingredient("BABY SPINACH") == "auto"


# --- Resolver tests ---

import tempfile, os
import pytest
from purchasing.pantry_db import PantryDB
from purchasing.ingredient_resolver import resolve_ingredients, ResolvedIngredient

@pytest.fixture
def empty_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield PantryDB(path)
    os.unlink(path)

def fake_search(query):
    return [
        {"asin": "B001", "title": f"Product for {query}", "price": 3.99},
        {"asin": "B002", "title": f"Alt for {query}", "price": 4.99},
        {"asin": "B003", "title": f"Generic {query}", "price": 2.99},
    ]

MEALS = [{"name": "Test Meal", "servings": 2, "ingredients": [
    {"name": "Baby Spinach", "quantity": 6, "unit": "oz"},
    {"name": "Paneer Cheese", "quantity": 8, "unit": "oz"},
]}]

def test_auto_ingredient_gets_top_search_result(empty_db):
    results = resolve_ingredients(MEALS, empty_db, fake_search)
    spinach = next(r for r in results if r.name == "Baby Spinach")
    assert spinach.status == "auto"
    assert spinach.asin == "B001"
    assert spinach.price == 3.99

def test_review_ingredient_gets_all_candidates(empty_db):
    results = resolve_ingredients(MEALS, empty_db, fake_search)
    paneer = next(r for r in results if r.name == "Paneer Cheese")
    assert paneer.status == "review"
    assert paneer.asin is None
    assert len(paneer.candidates) == 3

def test_pantry_hit_is_used_without_search(empty_db):
    empty_db.save("baby spinach", "B_PANTRY", "Pantry Spinach", confirmed_by_user=True)
    called = []
    def tracking_search(query):
        called.append(query)
        return fake_search(query)

    results = resolve_ingredients(MEALS, empty_db, tracking_search)
    spinach = next(r for r in results if r.name == "Baby Spinach")
    assert spinach.asin == "B_PANTRY"
    assert "baby spinach" not in " ".join(called).lower()

def test_all_meals_are_flattened(empty_db):
    meals = [
        {"name": "Meal A", "servings": 2, "ingredients": [
            {"name": "Chickpeas", "quantity": 1, "unit": "can"}
        ]},
        {"name": "Meal B", "servings": 2, "ingredients": [
            {"name": "Tomato Sauce", "quantity": 1, "unit": "can"}
        ]},
    ]
    results = resolve_ingredients(meals, empty_db, fake_search)
    names = {r.name for r in results}
    assert "Chickpeas" in names
    assert "Tomato Sauce" in names
