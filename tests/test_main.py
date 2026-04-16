import json
import pytest
from unittest.mock import patch, AsyncMock
from purchasing.main import run_pipeline
from purchasing.auth import save_session


@pytest.fixture
def recipe_file(tmp_path):
    recipe = {
        "week": "2026-04-20",
        "meals": [{"name": "Test Meal", "servings": 2, "ingredients": [
            {"name": "Baby Spinach", "quantity": 6, "unit": "oz"},
        ]}]
    }
    p = tmp_path / "week.json"
    p.write_text(json.dumps(recipe))
    return str(p)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "pantry.db")


@pytest.fixture
def session_path(tmp_path):
    p = tmp_path / "session.json"
    save_session([{"name": "session-id", "value": "fake", "domain": ".amazon.com", "path": "/"}], str(p))
    return str(p)


def fake_search(query):
    return [{"asin": "B001", "title": "Spinach", "price": 2.99}]


def test_run_pipeline_cancel(recipe_file, db_path, session_path):
    """User cancels at approval screen — no cart or checkout calls made."""
    with patch("builtins.input", return_value="x"), \
         patch("purchasing.main.build_cart", new_callable=AsyncMock) as mock_cart, \
         patch("purchasing.main.run_checkout", new_callable=AsyncMock) as mock_checkout:
        result = run_pipeline(recipe_file, db_path, session_path, search_fn=fake_search)

    assert result is None
    mock_cart.assert_not_called()
    mock_checkout.assert_not_called()


def test_run_pipeline_success(recipe_file, db_path, session_path):
    """User confirms — cart and checkout are called."""
    from purchasing.cart_builder import CartItem
    from purchasing.checkout import OrderConfirmation

    with patch("builtins.input", return_value="c"), \
         patch("purchasing.main.build_cart", new_callable=AsyncMock,
               return_value=[CartItem("Baby Spinach", "B001", "Spinach", 2.99)]) as mock_cart, \
         patch("purchasing.main.run_checkout", new_callable=AsyncMock,
               return_value=OrderConfirmation("123-456", 2.99)) as mock_checkout:
        result = run_pipeline(recipe_file, db_path, session_path, search_fn=fake_search)

    assert result is not None
    assert result.order_id == "123-456"
    mock_cart.assert_called_once()
    mock_checkout.assert_called_once()


def test_missing_recipe_file_raises(db_path, session_path):
    with pytest.raises(FileNotFoundError):
        run_pipeline("/nonexistent/recipe.json", db_path, session_path)
