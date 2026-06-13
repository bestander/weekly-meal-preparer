import json
from dataclasses import dataclass, field

import pytest

from purchasing.auth import save_session
from purchasing.pantry_db import PantryDB


@dataclass
class FakeAmazon:
    """In-memory Amazon boundary for pipeline tests."""

    catalog: dict[str, list[dict]]
    asin_prices: dict[str, float] = field(default_factory=dict)
    search_calls: list[str] = field(default_factory=list)
    price_calls: list[str] = field(default_factory=list)

    def search(self, query: str) -> list[dict]:
        self.search_calls.append(query)
        return list(self.catalog.get(query, []))[:3]

    def price_for_asin(self, asin: str) -> float | None:
        self.price_calls.append(asin)
        return self.asin_prices.get(asin)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "pantry.db")


@pytest.fixture
def pantry(db_path):
    return PantryDB(db_path)


@pytest.fixture
def session_path(tmp_path):
    path = tmp_path / "session.json"
    save_session(
        [{"name": "session-id", "value": "fake", "domain": ".amazon.com", "path": "/"}],
        str(path),
    )
    return str(path)


@pytest.fixture
def write_recipe(tmp_path):
    def _write(meals: list[dict], week: str = "2026-06-16") -> str:
        recipe_path = tmp_path / "week.json"
        recipe_path.write_text(json.dumps({"week": week, "meals": meals}))
        return str(recipe_path)

    return _write


@pytest.fixture
def mixed_meal():
    """One auto ingredient and two specialty ingredients that need review."""
    return [{
        "name": "Baked Paneer Curry",
        "servings": 4,
        "ingredients": [
            {"name": "Baby Spinach", "quantity": 6, "unit": "oz"},
            {"name": "Paneer Cheese", "quantity": 8, "unit": "oz"},
            {"name": "Vadouvan Curry Powder", "quantity": 1, "unit": "tbsp"},
        ],
    }]


@pytest.fixture
def mixed_catalog():
    return FakeAmazon(catalog={
        "Baby Spinach": [
            {"asin": "B_SPIN", "title": "365 Baby Spinach 5oz", "price": 3.49},
        ],
        "Paneer Cheese": [
            {"asin": "B_PAN1", "title": "Gopi Paneer 12oz", "price": 5.99},
            {"asin": "B_PAN2", "title": "Nanak Paneer 14oz", "price": 6.49},
        ],
        "Vadouvan Curry Powder": [
            {"asin": "B_VAD1", "title": "Vadouvan Blend", "price": 8.99},
            {"asin": "B_VAD2", "title": "Alt Vadouvan", "price": 9.99},
        ],
    })
