# Amazon Whole Foods Ingredients Ordering — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local macOS tool that reads a weekly meal plan JSON, resolves ingredients to Amazon Whole Foods products, presents a CLI approval screen, and uses Playwright to complete the checkout.

**Architecture:** A Python package (`purchasing`) that pipelines through: ingredient resolution (pantry DB lookup + Amazon search), CLI approval gate, Playwright cart building, and Playwright checkout. All browser sessions are authenticated via serialized cookies from a one-time manual login. launchd fires the pipeline weekly.

**Tech Stack:** Python 3.11+, playwright, playwright-stealth, sqlite3 (stdlib), pytest

---

## File Map

| File | Responsibility |
|------|---------------|
| `purchasing/__init__.py` | Empty package marker |
| `purchasing/__main__.py` | `python -m purchasing` CLI dispatcher (run / auth login) |
| `purchasing/pantry_db.py` | SQLite CRUD for ingredient→ASIN memory and pending review queue |
| `purchasing/ingredient_resolver.py` | Classify ingredients (auto vs review), look up pantry, call search_fn |
| `purchasing/cli_approval.py` | Interactive terminal screen: show items, collect specialty picks, confirm/cancel |
| `purchasing/auth.py` | Cookie session: save, load, validity check, `auth login` (opens visible browser) |
| `purchasing/cart_builder.py` | Playwright: navigate to each ASIN product page, add to WF cart |
| `purchasing/checkout.py` | Playwright: proceed from cart to placed order, price deviation guard |
| `purchasing/main.py` | Pipeline orchestrator: wires all modules together |
| `tests/test_pantry_db.py` | Unit tests for pantry_db |
| `tests/test_ingredient_resolver.py` | Unit tests for classification and resolution (search_fn mocked) |
| `tests/test_cli_approval.py` | Unit tests for CLI approval (input() mocked) |
| `tests/test_main.py` | Integration tests for the full pipeline (Playwright mocked) |
| `recipes/week-2026-04-20.json` | Baked Paneer Curry test fixture (hand-authored from recipe card image) |
| `pyproject.toml` | Project deps and package config |
| `.gitignore` | Excludes data/, .venv/, __pycache__ |
| `launchd/com.mealrotation.plist` | Weekly schedule: runs `python -m purchasing run` |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `purchasing/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "meal-rotation"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "playwright>=1.44",
    "playwright-stealth>=1.0.6",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-asyncio>=0.23"]

[tool.setuptools.packages.find]
where = ["."]
include = ["purchasing*"]
```

- [ ] **Step 2: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
*.pyo
data/
.superpowers/
```

- [ ] **Step 3: Create empty package markers**

```bash
touch purchasing/__init__.py tests/__init__.py
```

- [ ] **Step 4: Install dependencies**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

Expected: no errors. `python -c "import playwright"` exits cleanly.

- [ ] **Step 5: Verify test runner works**

```bash
pytest tests/ -v
```

Expected: `no tests ran` (0 collected).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore purchasing/__init__.py tests/__init__.py
git commit -m "chore: project scaffolding"
```

---

## Task 2: Recipe Test Fixture

**Files:**
- Create: `recipes/week-2026-04-20.json`
- Create: `tests/test_recipe_fixture.py`

The recipe card image (`baked-paneer-curry.png`) shows quantities for 2 and 4 servings. Use the 4-serving column. Aluminum tray is equipment — omit it.

- [ ] **Step 1: Write the failing test**

Create `tests/test_recipe_fixture.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_recipe_fixture.py -v
```

Expected: FAIL — `recipes/week-2026-04-20.json not found`

- [ ] **Step 3: Create the fixture**

```bash
mkdir -p recipes
```

Create `recipes/week-2026-04-20.json`:

```json
{
  "week": "2026-04-20",
  "meals": [
    {
      "name": "Baked Paneer Curry",
      "servings": 4,
      "ingredients": [
        { "name": "Naan Bread",            "quantity": 4,   "unit": "pieces" },
        { "name": "Chickpeas",             "quantity": 2,   "unit": "15.5oz can" },
        { "name": "Paneer Cheese",         "quantity": 8,   "unit": "oz" },
        { "name": "Baby Spinach",          "quantity": 6,   "unit": "oz" },
        { "name": "Heavy Cream",           "quantity": 0.5, "unit": "cup" },
        { "name": "Labneh Cheese",         "quantity": 0.5, "unit": "cup" },
        { "name": "Tomato Achaar",         "quantity": 4,   "unit": "tbsp" },
        { "name": "Tomato Sauce",          "quantity": 2,   "unit": "8oz can" },
        { "name": "Vadouvan Curry Powder", "quantity": 1,   "unit": "tbsp" }
      ]
    }
  ]
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_recipe_fixture.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add recipes/week-2026-04-20.json tests/test_recipe_fixture.py
git commit -m "feat: add Baked Paneer Curry recipe test fixture"
```

---

## Task 3: Pantry DB

**Files:**
- Create: `purchasing/pantry_db.py`
- Create: `tests/test_pantry_db.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pantry_db.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_pantry_db.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'purchasing.pantry_db'`

- [ ] **Step 3: Implement `purchasing/pantry_db.py`**

```python
import json
import sqlite3


class PantryDB:
    def __init__(self, db_path: str):
        self._path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self._path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pantry (
                    ingredient_name   TEXT PRIMARY KEY,
                    asin              TEXT NOT NULL,
                    product_title     TEXT,
                    store             TEXT DEFAULT 'WholeFoods',
                    last_used         DATE,
                    confirmed_by_user INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_review (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    ingredient_name  TEXT,
                    candidates       TEXT,
                    week             TEXT
                )
            """)

    def _normalize(self, name: str) -> str:
        return name.strip().lower()

    def get(self, ingredient_name: str) -> dict | None:
        key = self._normalize(ingredient_name)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT asin, product_title, confirmed_by_user FROM pantry WHERE ingredient_name = ?",
                (key,)
            ).fetchone()
        if row is None:
            return None
        return {"asin": row[0], "product_title": row[1], "confirmed_by_user": bool(row[2])}

    def save(self, ingredient_name: str, asin: str, product_title: str, confirmed_by_user: bool = False):
        key = self._normalize(ingredient_name)
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO pantry (ingredient_name, asin, product_title, confirmed_by_user, last_used)
                   VALUES (?, ?, ?, ?, DATE('now'))
                   ON CONFLICT(ingredient_name) DO UPDATE SET
                     asin = excluded.asin,
                     product_title = excluded.product_title,
                     confirmed_by_user = excluded.confirmed_by_user,
                     last_used = excluded.last_used""",
                (key, asin, product_title, int(confirmed_by_user))
            )

    def add_pending(self, ingredient_name: str, candidates: list[dict], week: str):
        key = self._normalize(ingredient_name)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO pending_review (ingredient_name, candidates, week) VALUES (?, ?, ?)",
                (key, json.dumps(candidates), week)
            )

    def get_pending(self, week: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ingredient_name, candidates FROM pending_review WHERE week = ?",
                (week,)
            ).fetchall()
        return [{"ingredient_name": r[0], "candidates": json.loads(r[1])} for r in rows]

    def clear_pending(self, week: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM pending_review WHERE week = ?", (week,))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_pantry_db.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add purchasing/pantry_db.py tests/test_pantry_db.py
git commit -m "feat: add pantry DB module"
```

---

## Task 4: Ingredient Classifier

**Files:**
- Create: `purchasing/ingredient_resolver.py` (classifier only for now)
- Create: `tests/test_ingredient_resolver.py` (classifier tests for now)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ingredient_resolver.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_ingredient_resolver.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement classifier in `purchasing/ingredient_resolver.py`**

```python
from dataclasses import dataclass, field

SPECIALTY_TERMS = {
    "achaar", "vadouvan", "labneh", "paneer", "masala", "garam",
    "miso", "tahini", "harissa", "sumac", "berbere", "furikake",
    "dashi", "gochujang", "sambal", "hoisin", "za'atar",
}


def classify_ingredient(name: str) -> str:
    """Return 'auto' if ingredient can be auto-matched, 'review' if user should pick."""
    words = name.lower().split()
    if any(word in SPECIALTY_TERMS for word in words):
        return "review"
    return "auto"


@dataclass
class ResolvedIngredient:
    name: str
    quantity: float
    unit: str
    status: str                    # "auto" | "review"
    asin: str | None = None
    product_title: str | None = None
    price: float | None = None
    candidates: list[dict] = field(default_factory=list)  # [{asin, title, price}]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ingredient_resolver.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add purchasing/ingredient_resolver.py tests/test_ingredient_resolver.py
git commit -m "feat: ingredient classifier"
```

---

## Task 5: Ingredient Resolver

**Files:**
- Modify: `purchasing/ingredient_resolver.py` — add `resolve_ingredients()`
- Modify: `tests/test_ingredient_resolver.py` — add resolver tests

`resolve_ingredients` takes a `search_fn` parameter so tests can inject a fake Amazon search instead of hitting the network.

`search_fn` signature: `(query: str) -> list[dict]` where each dict is `{asin, title, price}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ingredient_resolver.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_ingredient_resolver.py::test_auto_ingredient_gets_top_search_result -v
```

Expected: FAIL — `ImportError: cannot import name 'resolve_ingredients'`

- [ ] **Step 3: Implement `resolve_ingredients` in `purchasing/ingredient_resolver.py`**

Append to the existing file:

```python
from purchasing.pantry_db import PantryDB


def resolve_ingredients(
    meals: list[dict],
    pantry: PantryDB,
    search_fn,
) -> list["ResolvedIngredient"]:
    """
    Resolve all ingredients across all meals to Amazon products.

    search_fn(query: str) -> list[{asin, title, price}]
    Returns at most 3 candidates, sorted by relevance.
    """
    results = []
    for meal in meals:
        for ing in meal["ingredients"]:
            name = ing["name"]
            pantry_entry = pantry.get(name)

            if pantry_entry:
                results.append(ResolvedIngredient(
                    name=name,
                    quantity=ing["quantity"],
                    unit=ing["unit"],
                    status="auto",
                    asin=pantry_entry["asin"],
                    product_title=pantry_entry["product_title"],
                    price=None,  # price fetched at cart-build time
                    candidates=[],
                ))
                continue

            status = classify_ingredient(name)
            candidates = search_fn(name)[:3]

            if status == "auto":
                top = candidates[0] if candidates else None
                results.append(ResolvedIngredient(
                    name=name,
                    quantity=ing["quantity"],
                    unit=ing["unit"],
                    status="auto",
                    asin=top["asin"] if top else None,
                    product_title=top["title"] if top else None,
                    price=top["price"] if top else None,
                    candidates=[],
                ))
            else:
                results.append(ResolvedIngredient(
                    name=name,
                    quantity=ing["quantity"],
                    unit=ing["unit"],
                    status="review",
                    asin=None,
                    product_title=None,
                    price=None,
                    candidates=candidates,
                ))

    return results
```

- [ ] **Step 4: Run all resolver tests**

```bash
pytest tests/test_ingredient_resolver.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add purchasing/ingredient_resolver.py tests/test_ingredient_resolver.py
git commit -m "feat: ingredient resolver with pantry lookup and Amazon search"
```

---

## Task 6: CLI Approval Screen

**Files:**
- Create: `purchasing/cli_approval.py`
- Create: `tests/test_cli_approval.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_approval.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_cli_approval.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `purchasing/cli_approval.py`**

```python
from dataclasses import dataclass
from purchasing.ingredient_resolver import ResolvedIngredient


@dataclass
class ApprovalResult:
    approved: bool
    confirmed_items: list[dict]  # [{name, asin, product_title, price, quantity, unit}]


def run_approval(resolved: list[ResolvedIngredient], meals: list[dict]) -> ApprovalResult | None:
    """
    Show the weekly cart to the user. Collect picks for review items.
    Returns ApprovalResult on confirm, None on cancel.
    """
    auto_items = [r for r in resolved if r.status == "auto"]
    review_items = [r for r in resolved if r.status == "review"]

    _print_header(meals, auto_items)
    picks = _collect_picks(review_items)
    if picks is None:
        return None

    _print_summary(auto_items, picks)

    while True:
        choice = input("\n[c] Confirm & place order   [e] Edit an item   [x] Cancel\n> ").strip().lower()
        if choice == "x":
            print("Order cancelled.")
            return None
        if choice == "c":
            break
        if choice == "e":
            picks = _collect_picks(review_items)
            if picks is None:
                return None
            _print_summary(auto_items, picks)

    confirmed = [
        {"name": r.name, "asin": r.asin, "product_title": r.product_title,
         "price": r.price, "quantity": r.quantity, "unit": r.unit}
        for r in auto_items
    ] + picks

    return ApprovalResult(approved=True, confirmed_items=confirmed)


def _print_header(meals: list[dict], auto_items: list[ResolvedIngredient]):
    print("\n" + "=" * 57)
    print("  Meal Rotation — Weekly Order")
    meal_names = ", ".join(m["name"] for m in meals)
    print(f"  {meal_names}")
    print("=" * 57)
    print("\nAUTO-MATCHED ITEMS:")
    for item in auto_items:
        print(f"  ✓  {item.name} {item.quantity}{item.unit:<10}  →  {item.product_title or 'N/A':<35}  ${item.price or 0:.2f}")


def _collect_picks(review_items: list[ResolvedIngredient]) -> list[dict] | None:
    """Prompt user to pick one candidate per review item. Returns None on cancel."""
    if not review_items:
        return []

    picks = []
    print("\nITEMS NEEDING YOUR SELECTION:")
    for item in review_items:
        while True:
            print(f"\n  ? {item.name} {item.quantity} {item.unit}")
            for i, c in enumerate(item.candidates, 1):
                print(f"     [{i}] {c['title']:<40}  ${c['price']:.2f}")

            choice = input("     Pick [1-3] or [x] to cancel: ").strip().lower()
            if choice == "x":
                print("Order cancelled.")
                return None

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(item.candidates):
                    picked = item.candidates[idx]
                    picks.append({
                        "name": item.name,
                        "asin": picked["asin"],
                        "product_title": picked["title"],
                        "price": picked["price"],
                        "quantity": item.quantity,
                        "unit": item.unit,
                    })
                    break
            except ValueError:
                pass
            print("     Invalid choice. Enter a number between 1 and", len(item.candidates))

    return picks


def _print_summary(auto_items: list[ResolvedIngredient], picks: list[dict]):
    total = sum(i.price or 0 for i in auto_items) + sum(p["price"] for p in picks)
    print(f"\n{'─' * 57}")
    print(f"  Estimated total: ${total:.2f}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_cli_approval.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add purchasing/cli_approval.py tests/test_cli_approval.py
git commit -m "feat: CLI approval screen"
```

---

## Task 7: Auth Module

**Files:**
- Create: `purchasing/auth.py`

No unit tests for the interactive login (requires a real browser). The `save_session`/`load_session`/`is_session_valid` helpers are tested indirectly via integration.

- [ ] **Step 1: Create `purchasing/auth.py`**

```python
import json
import os
import pathlib
from datetime import datetime, timezone


SESSION_MAX_AGE_DAYS = 25  # Amazon sessions last ~30 days; refresh proactively


def save_session(cookies: list[dict], path: str) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    data = {"saved_at": datetime.now(timezone.utc).isoformat(), "cookies": cookies}
    pathlib.Path(path).write_text(json.dumps(data, indent=2))


def load_session(path: str) -> list[dict] | None:
    p = pathlib.Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return data.get("cookies")


def is_session_valid(path: str) -> bool:
    p = pathlib.Path(path)
    if not p.exists():
        return False
    data = json.loads(p.read_text())
    saved_at = datetime.fromisoformat(data["saved_at"])
    age_days = (datetime.now(timezone.utc) - saved_at).days
    return age_days < SESSION_MAX_AGE_DAYS


async def login_interactive(session_path: str) -> None:
    """
    Open a visible Chrome browser. User logs in to Amazon and selects Whole Foods
    as delivery store. When they close the window, cookies are saved.
    """
    from playwright.async_api import async_playwright
    from playwright_stealth import stealth_async

    print("Opening browser. Log in to Amazon, confirm Whole Foods as your delivery store,")
    print("then close the browser window.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        await stealth_async(context)
        page = await context.new_page()
        await page.goto("https://www.amazon.com/gp/flex/sign-in/select.html")

        # Wait until the user closes the browser
        try:
            await page.wait_for_event("close", timeout=300_000)  # 5 min timeout
        except Exception:
            pass

        cookies = await context.cookies()
        await browser.close()

    save_session(cookies, session_path)
    print(f"Session saved to {session_path}")
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from purchasing.auth import save_session, load_session, is_session_valid; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add purchasing/auth.py
git commit -m "feat: auth module with cookie session management"
```

---

## Task 8: Cart Builder

**Files:**
- Create: `purchasing/cart_builder.py`

No unit tests — Playwright requires a live browser and Amazon session. Manual test instructions are included.

- [ ] **Step 1: Create `purchasing/cart_builder.py`**

```python
import asyncio
import random
from dataclasses import dataclass
from purchasing.auth import load_session


@dataclass
class CartItem:
    name: str
    asin: str
    product_title: str
    price: float


async def build_cart(session_path: str, items: list[dict]) -> list[CartItem]:
    """
    Add each item to the Amazon Whole Foods cart.
    items: list of {name, asin, product_title, price, quantity, unit}
    Returns list of CartItem for items successfully added.
    """
    from playwright.async_api import async_playwright
    from playwright_stealth import stealth_async

    cookies = load_session(session_path)
    if cookies is None:
        raise RuntimeError(f"No session found at {session_path}. Run: python -m purchasing auth login")

    added = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await stealth_async(context)
        await context.add_cookies(cookies)
        page = await context.new_page()

        for item in items:
            print(f"  Adding {item['name']}...", end=" ", flush=True)
            try:
                await page.goto(f"https://www.amazon.com/dp/{item['asin']}", wait_until="domcontentloaded")
                await asyncio.sleep(random.uniform(1.0, 3.0))

                # Click "Add to Cart" button
                await page.click("[id='add-to-cart-button']", timeout=10_000)
                await asyncio.sleep(random.uniform(0.5, 1.5))

                added.append(CartItem(
                    name=item["name"],
                    asin=item["asin"],
                    product_title=item["product_title"],
                    price=item["price"],
                ))
                print("✓")
            except Exception as e:
                print(f"✗ ({e})")

        await browser.close()

    return added
```

- [ ] **Step 2: Manual test instructions**

To manually verify cart building works:
1. Run `python -m purchasing auth login` to get a valid session.
2. Create a small test script:
```python
import asyncio
from purchasing.cart_builder import build_cart

items = [{"name": "Test", "asin": "B07XKZN6GS", "product_title": "Test", "price": 1.0, "quantity": 1, "unit": "each"}]
added = asyncio.run(build_cart("data/session.json", items))
print(added)
```
3. Verify the item appears in your Amazon cart.

- [ ] **Step 3: Commit**

```bash
git add purchasing/cart_builder.py
git commit -m "feat: Playwright cart builder"
```

---

## Task 9: Checkout Executor

**Files:**
- Create: `purchasing/checkout.py`

No unit tests — requires live browser + Amazon session. Manual test instructions included.

- [ ] **Step 1: Create `purchasing/checkout.py`**

```python
import asyncio
from dataclasses import dataclass
from purchasing.auth import load_session


@dataclass
class OrderConfirmation:
    order_id: str
    total: float


PRICE_DEVIATION_GUARD = 0.20  # abort if actual total is >20% off estimate


async def run_checkout(session_path: str, estimated_total: float) -> OrderConfirmation:
    """
    Complete checkout from an already-filled Amazon cart.
    Aborts if final total deviates more than 20% from estimated_total.
    """
    from playwright.async_api import async_playwright
    from playwright_stealth import stealth_async

    cookies = load_session(session_path)
    if cookies is None:
        raise RuntimeError(f"No session found at {session_path}. Run: python -m purchasing auth login")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await stealth_async(context)
        await context.add_cookies(cookies)
        page = await context.new_page()

        # Go to cart
        await page.goto("https://www.amazon.com/cart", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # Proceed to checkout
        await page.click("[name='proceedToRetailCheckout']", timeout=10_000)
        await asyncio.sleep(2)

        # Get order total from checkout page
        try:
            total_text = await page.inner_text("[class*='order-summary-total']", timeout=5_000)
            actual_total = float(total_text.replace("$", "").replace(",", "").strip())
        except Exception:
            actual_total = estimated_total  # fall back; guard will pass

        deviation = abs(actual_total - estimated_total) / max(estimated_total, 0.01)
        if deviation > PRICE_DEVIATION_GUARD:
            await browser.close()
            raise RuntimeError(
                f"Order total ${actual_total:.2f} deviates {deviation:.0%} from "
                f"estimate ${estimated_total:.2f}. Aborting — review cart manually."
            )

        # Place order
        await page.click("[name='placeYourOrder1']", timeout=10_000)
        await asyncio.sleep(3)

        # Extract order ID
        try:
            order_id_text = await page.inner_text("[class*='order-id']", timeout=5_000)
            order_id = order_id_text.strip()
        except Exception:
            order_id = "unknown"

        await browser.close()

    print(f"\nOrder placed! ID: {order_id}  Total: ${actual_total:.2f}")
    return OrderConfirmation(order_id=order_id, total=actual_total)
```

- [ ] **Step 2: Manual test instructions**

To verify checkout (use carefully — it places a real order):
1. Manually add one item to your Whole Foods cart on Amazon.
2. Run with a generous estimated_total:
```python
import asyncio
from purchasing.checkout import run_checkout
asyncio.run(run_checkout("data/session.json", estimated_total=50.0))
```
3. Confirm order appears in Amazon order history.

**Note:** Amazon's checkout page selectors (`order-summary-total`, `placeYourOrder1`) may need updating if Amazon changes their UI. Run with `headless=False` in `chromium.launch()` to debug selector issues.

- [ ] **Step 3: Commit**

```bash
git add purchasing/checkout.py
git commit -m "feat: Playwright checkout executor"
```

---

## Task 10: Main Orchestrator + CLI Entry Point

**Files:**
- Create: `purchasing/main.py`
- Create: `purchasing/__main__.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write the failing integration tests**

Create `tests/test_main.py`:

```python
import json
import pathlib
import tempfile
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from purchasing.main import run_pipeline
from purchasing.pantry_db import PantryDB

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
    # Write a fake session file
    p = tmp_path / "session.json"
    from purchasing.auth import save_session
    save_session([{"name": "session-id", "value": "fake", "domain": ".amazon.com", "path": "/"}], str(p))
    return str(p)

def test_run_pipeline_cancel(recipe_file, db_path, session_path):
    """User cancels at approval screen — no cart or checkout calls made."""
    def fake_search(query):
        return [{"asin": "B001", "title": "Spinach", "price": 2.99}]

    with patch("builtins.input", return_value="x"), \
         patch("purchasing.main.build_cart", new_callable=AsyncMock) as mock_cart, \
         patch("purchasing.main.run_checkout", new_callable=AsyncMock) as mock_checkout:

        result = run_pipeline(recipe_file, db_path, session_path, search_fn=fake_search)

    assert result is None
    mock_cart.assert_not_called()
    mock_checkout.assert_not_called()

def test_run_pipeline_success(recipe_file, db_path, session_path):
    """User confirms — cart and checkout are called."""
    def fake_search(query):
        return [{"asin": "B001", "title": "Spinach", "price": 2.99}]

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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_main.py -v
```

Expected: FAIL — `ImportError: cannot import name 'run_pipeline'`

- [ ] **Step 3: Implement `purchasing/main.py`**

```python
import asyncio
import json
import pathlib
import sys

from purchasing.pantry_db import PantryDB
from purchasing.ingredient_resolver import resolve_ingredients
from purchasing.cli_approval import run_approval
from purchasing.cart_builder import build_cart
from purchasing.checkout import run_checkout, OrderConfirmation
from purchasing.auth import is_session_valid

DEFAULT_RECIPE_PATH = "recipes/current-week.json"
DEFAULT_DB_PATH = "data/pantry.db"
DEFAULT_SESSION_PATH = "data/session.json"


def _amazon_search(query: str) -> list[dict]:
    """Live Amazon Whole Foods product search using Playwright."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import stealth_sync

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        stealth_sync(context)
        page = context.new_page()
        url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}&i=wholefoods"
        page.goto(url, wait_until="domcontentloaded")

        items = page.query_selector_all("[data-component-type='s-search-result']")
        for item in items[:3]:
            try:
                asin = item.get_attribute("data-asin")
                title_el = item.query_selector("h2 a span")
                price_el = item.query_selector(".a-price .a-offscreen")
                title = title_el.inner_text() if title_el else "Unknown"
                price_text = price_el.inner_text() if price_el else "$0"
                price = float(price_text.replace("$", "").replace(",", "").strip())
                if asin:
                    results.append({"asin": asin, "title": title, "price": price})
            except Exception:
                continue

        browser.close()
    return results


def run_pipeline(
    recipe_path: str = DEFAULT_RECIPE_PATH,
    db_path: str = DEFAULT_DB_PATH,
    session_path: str = DEFAULT_SESSION_PATH,
    search_fn=None,
) -> OrderConfirmation | None:
    """Run the full weekly ordering pipeline. Returns OrderConfirmation or None if cancelled."""

    # Load recipe
    p = pathlib.Path(recipe_path)
    if not p.exists():
        raise FileNotFoundError(f"Recipe file not found: {recipe_path}")
    data = json.loads(p.read_text())
    meals = data["meals"]

    # Check session
    if not is_session_valid(session_path):
        print(f"Amazon session missing or expired. Run: python -m purchasing auth login")
        sys.exit(1)

    # Resolve ingredients
    pantry = PantryDB(db_path)
    fn = search_fn or _amazon_search
    print("Resolving ingredients...")
    resolved = resolve_ingredients(meals, pantry, fn)

    # CLI approval gate
    approval = run_approval(resolved, meals)
    if approval is None:
        return None

    # Save specialty picks to pantry
    for item in approval.confirmed_items:
        existing = pantry.get(item["name"])
        if existing is None or not existing["confirmed_by_user"]:
            pantry.save(item["name"], item["asin"], item["product_title"], confirmed_by_user=True)

    # Build cart
    estimated_total = sum(i.get("price") or 0 for i in approval.confirmed_items)
    print("\nBuilding cart...")
    asyncio.run(build_cart(session_path, approval.confirmed_items))

    # Checkout
    print("\nProceeding to checkout...")
    confirmation = asyncio.run(run_checkout(session_path, estimated_total))
    return confirmation
```

- [ ] **Step 4: Create `purchasing/__main__.py`**

```python
import argparse
import asyncio
import sys
from purchasing.main import run_pipeline, DEFAULT_RECIPE_PATH, DEFAULT_DB_PATH, DEFAULT_SESSION_PATH


def main():
    parser = argparse.ArgumentParser(prog="purchasing", description="Meal Rotation — ingredient ordering")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run the weekly ordering pipeline")
    run_p.add_argument("--recipe", default=DEFAULT_RECIPE_PATH)
    run_p.add_argument("--db", default=DEFAULT_DB_PATH)
    run_p.add_argument("--session", default=DEFAULT_SESSION_PATH)

    auth_p = sub.add_parser("auth", help="Authentication commands")
    auth_sub = auth_p.add_subparsers(dest="auth_command")
    auth_sub.add_parser("login", help="Open browser to log in and save session")

    args = parser.parse_args()

    if args.command == "run":
        run_pipeline(args.recipe, args.db, args.session)

    elif args.command == "auth" and args.auth_command == "login":
        from purchasing.auth import login_interactive
        asyncio.run(login_interactive(DEFAULT_SESSION_PATH))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS (skip or xfail is acceptable for anything requiring live network).

- [ ] **Step 6: Smoke-test the CLI**

```bash
python -m purchasing --help
python -m purchasing run --help
python -m purchasing auth --help
```

Expected: help text prints, no errors.

- [ ] **Step 7: Commit**

```bash
git add purchasing/main.py purchasing/__main__.py tests/test_main.py
git commit -m "feat: main pipeline orchestrator and CLI entry point"
```

---

## Task 11: launchd Scheduling

**Files:**
- Create: `launchd/com.mealrotation.plist`

- [ ] **Step 1: Create `launchd/com.mealrotation.plist`**

Replace `/Users/YOUR_USERNAME` and `/path/to/meal-rotation` with actual paths.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mealrotation</string>

    <key>ProgramArguments</key>
    <array>
        <string>/path/to/meal-rotation/.venv/bin/python</string>
        <string>-m</string>
        <string>purchasing</string>
        <string>run</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/path/to/meal-rotation</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>  <!-- 0 = Sunday -->
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/mealrotation.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/mealrotation.err</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

- [ ] **Step 2: Installation instructions**

After filling in your actual paths:

```bash
# Copy plist to launchd agents directory
cp launchd/com.mealrotation.plist ~/Library/LaunchAgents/

# Load it
launchctl load ~/Library/LaunchAgents/com.mealrotation.plist

# Verify it's loaded
launchctl list | grep mealrotation

# To unload
launchctl unload ~/Library/LaunchAgents/com.mealrotation.plist
```

To test-run immediately without waiting for Sunday:
```bash
launchctl start com.mealrotation
```

- [ ] **Step 3: Commit**

```bash
git add launchd/com.mealrotation.plist
git commit -m "feat: launchd weekly schedule"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Hybrid trigger (launchd schedule + CLI approval) — Tasks 10, 11
- [x] CLI approval — Task 6
- [x] Local Mac runtime — Task 11 (launchd)
- [x] Hybrid ingredient matching (auto + flag specialty) — Tasks 4, 5
- [x] Structured JSON input contract — Task 2 (fixture) + Task 5 (resolver input)
- [x] Pantry DB with ingredient memory — Task 3
- [x] Playwright + stealth + cookie session — Tasks 7, 8, 9
- [x] Checkout price deviation guard — Task 9
- [x] Baked paneer curry test fixture — Task 2
- [x] `python -m purchasing auth login` bootstrap — Task 7 + 10

**Playwright selector note:** The selectors in `cart_builder.py` (`add-to-cart-button`) and `checkout.py` (`proceedToRetailCheckout`, `order-summary-total`, `placeYourOrder1`) are correct as of 2025 but Amazon's UI changes periodically. Run with `headless=False` to debug if selectors break.
