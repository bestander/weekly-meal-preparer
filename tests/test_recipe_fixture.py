import json
import pathlib

FIXTURE = pathlib.Path("recipes/week-2026-04-20.json")

def test_fixture_exists():
    assert FIXTURE.exists(), "recipes/week-2026-04-20.json not found"

def test_fixture_structure():
    data = json.loads(FIXTURE.read_text())
    assert data["week"] == "2026-04-20"
    assert len(data["meals"]) >= 1
    meal = data["meals"][0]
    assert meal["name"] == "Baked Paneer Curry"
    assert meal["servings"] == 4
    assert len(meal["ingredients"]) == 9

def test_fixture_ingredient_names():
    data = json.loads(FIXTURE.read_text())
    names = {i["name"] for i in data["meals"][0]["ingredients"]}
    assert "Paneer Cheese" in names
    assert "Vadouvan Curry Powder" in names
    assert "Baby Spinach" in names

def test_fixture_ingredient_schema():
    data = json.loads(FIXTURE.read_text())
    for ingredient in data["meals"][0]["ingredients"]:
        assert "name" in ingredient
        assert "quantity" in ingredient
        assert "unit" in ingredient
        assert isinstance(ingredient["quantity"], (int, float))
        assert isinstance(ingredient["name"], str)
        assert isinstance(ingredient["unit"], str)
