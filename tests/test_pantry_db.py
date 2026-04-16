import pytest
import tempfile
import os
from purchasing.pantry_db import PantryDB

@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield PantryDB(path)
    os.unlink(path)

def test_get_unknown_returns_none(db):
    assert db.get("baby spinach") is None

def test_save_and_get(db):
    db.save("baby spinach", "B001234", "365 Organic Baby Spinach 5oz", confirmed_by_user=False)
    result = db.get("baby spinach")
    assert result["asin"] == "B001234"
    assert result["product_title"] == "365 Organic Baby Spinach 5oz"
    assert result["confirmed_by_user"] == False

def test_save_overwrites_existing(db):
    db.save("baby spinach", "B001234", "Old Product", confirmed_by_user=False)
    db.save("baby spinach", "B005678", "New Product", confirmed_by_user=True)
    result = db.get("baby spinach")
    assert result["asin"] == "B005678"
    assert result["confirmed_by_user"] == True

def test_get_normalizes_name(db):
    db.save("baby spinach", "B001234", "365 Organic Baby Spinach 5oz", confirmed_by_user=False)
    assert db.get("Baby Spinach") is not None
    assert db.get("BABY SPINACH") is not None

def test_add_and_get_pending(db):
    candidates = [
        {"asin": "B001", "title": "Product A", "price": 5.99},
        {"asin": "B002", "title": "Product B", "price": 6.99},
    ]
    db.add_pending("paneer cheese", candidates, "2026-04-20")
    pending = db.get_pending("2026-04-20")
    assert len(pending) == 1
    assert pending[0]["ingredient_name"] == "paneer cheese"
    assert len(pending[0]["candidates"]) == 2

def test_clear_pending(db):
    db.add_pending("paneer cheese", [], "2026-04-20")
    db.clear_pending("2026-04-20")
    assert db.get_pending("2026-04-20") == []

def test_pending_for_different_weeks_are_isolated(db):
    db.add_pending("paneer cheese", [], "2026-04-20")
    db.add_pending("labneh", [], "2026-04-27")
    assert len(db.get_pending("2026-04-20")) == 1
    assert len(db.get_pending("2026-04-27")) == 1
