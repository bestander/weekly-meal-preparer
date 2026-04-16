# Amazon Whole Foods Ingredients Ordering — Design Spec

**Date:** 2026-04-16  
**Scope:** Ingredients purchasing flow only. Recipe search and structured ingredient extraction are a separate future module.

---

## Overview

A local tool that reads a structured weekly meal plan (JSON), resolves each ingredient to an Amazon Whole Foods product, presents a CLI approval screen for the user to review and confirm, then uses Playwright to complete the Whole Foods checkout. Runs on macOS via launchd on a weekly schedule.

---

## Architecture

### Pipeline

```
launchd (weekly, e.g. Sunday 8am)
  └── main.py
        ├── 1. Recipe Reader        — reads recipes/current-week.json
        ├── 2. Ingredient Resolver  — maps ingredients to ASINs + fetches prices
        │         ├── pantry.db lookup (known mappings)
        │         ├── Playwright Amazon search (unknowns, gets top-3 with prices)
        │         └── classifier: auto-match vs flag for review
        ├── 3. CLI Approval Gate    — user reviews all items, picks specialty items, confirms
        ├── 4. Cart Builder         — Playwright adds all confirmed items to WF cart
        └── 5. Checkout Executor    — Playwright completes checkout; pantry DB updated
```

Note: ingredient resolution (step 2) fetches prices via search results before any cart interaction, so the CLI can show accurate estimates. Cart building only starts after user confirms — no dirty cart on cancel.

### Project Structure

```
meal-rotation/
├── purchasing/
│   ├── __init__.py
│   ├── main.py                  # pipeline orchestrator; CLI entry point
│   ├── auth.py                  # cookie session save/restore
│   ├── ingredient_resolver.py   # ingredient → ASIN mapping + classification
│   ├── cart_builder.py          # Playwright: search + add to WF cart
│   ├── checkout.py              # Playwright: complete checkout
│   ├── cli_approval.py          # interactive terminal review screen
│   └── pantry_db.py             # SQLite: ingredient → ASIN memory
├── data/
│   ├── pantry.db                # SQLite (gitignored)
│   └── session.json             # serialized Amazon cookies (gitignored)
├── recipes/
│   └── week-2026-04-20.json     # test fixture: Baked Paneer Curry (parsed from image)
└── launchd/
    └── com.mealrotation.plist
```

---

## Data Models

### Recipe JSON (input contract)

```json
{
  "week": "2026-04-20",
  "meals": [
    {
      "name": "Baked Paneer Curry",
      "servings": 4,
      "ingredients": [
        { "name": "Paneer Cheese",        "quantity": 8,    "unit": "oz" },
        { "name": "Baby Spinach",          "quantity": 6,    "unit": "oz" },
        { "name": "Vadouvan Curry Powder", "quantity": 1,    "unit": "tbsp" },
        { "name": "Labneh Cheese",         "quantity": 0.5,  "unit": "cup" },
        { "name": "Tomato Sauce",          "quantity": 1,    "unit": "8oz can" },
        { "name": "Heavy Cream",           "quantity": 0.25, "unit": "cup" },
        { "name": "Tomato Achaar",         "quantity": 4,    "unit": "tbsp" },
        { "name": "Naan Bread",            "quantity": 4,    "unit": "pieces" },
        { "name": "Chickpeas",             "quantity": 2,    "unit": "15.5oz can" }
      ]
    }
  ]
}
```

This file is hand-authored for the first test fixture, parsed from `baked-paneer-curry.png` using the recipe card visible in that image.

### Pantry DB Schema (SQLite)

```sql
-- Remembered ingredient → product mappings
CREATE TABLE pantry (
  ingredient_name   TEXT PRIMARY KEY,   -- normalized lowercase: "baby spinach"
  asin              TEXT NOT NULL,
  product_title     TEXT,
  store             TEXT DEFAULT 'WholeFoods',
  last_used         DATE,
  confirmed_by_user INTEGER DEFAULT 0   -- 1 = user explicitly picked this
);

-- Specialty items queued for review in the current week's session
CREATE TABLE pending_review (
  id               INTEGER PRIMARY KEY,
  ingredient_name  TEXT,
  candidates       TEXT,               -- JSON array: [{asin, title, price}, ...]
  week             TEXT
);
```

---

## Ingredient Resolution

### Classification Rules

**Auto-match** (add to cart without user input):
- Single-word staples: produce, common dairy, canned goods
- Items already confirmed in pantry DB (regardless of complexity)
- Examples: Baby Spinach, Tomato Sauce, Heavy Cream, Chickpeas, Naan Bread

**Flag for review** (show top-3 candidates in CLI):
- Multi-word names containing cuisine-specific terms
- Any ingredient not in pantry DB, even if it looks generic
- Examples: Vadouvan Curry Powder, Tomato Achaar, Labneh Cheese, Paneer Cheese

Once a specialty item is picked by the user, it is stored in pantry DB with `confirmed_by_user = 1` and auto-matched on all future occurrences.

### Amazon Search

- URL pattern: `amazon.com/s?k={query}&i=wholefoods`
- Extracts top-3 results: ASIN, product title, price
- Playwright session with `playwright-stealth` patches applied on context creation

---

## Playwright Automation

### Session Auth (`auth.py`)

```
python -m purchasing auth login
```

Opens a visible (non-headless) Chrome window. User logs in to Amazon, confirms Whole Foods as delivery store, closes window. Cookies serialized to `data/session.json`. Session reused until expiry (~30 days). Tool prompts for re-auth if session is invalid.

### Cart Builder (`cart_builder.py`)

- Navigates to `amazon.com/dp/{asin}` for each item
- Clicks "Add to cart", confirms Whole Foods store selection on first run
- Random 1–3s delay between items (human-like pacing)
- Headless mode with `playwright-stealth`; falls back to visible mode on detection errors

### Checkout (`checkout.py`)

- Flow: Cart → Proceed to checkout → Confirm address/delivery slot → Place order
- Guard: aborts and prompts user if order total deviates >20% from CLI estimate

---

## CLI Approval Screen

Displayed after ingredient resolution, before any cart interaction:

```
┌─────────────────────────────────────────────────────────┐
│  Meal Rotation — Weekly Order                            │
│  Week of 2026-04-20  ·  3 meals  ·  ~$87.40 estimated   │
└─────────────────────────────────────────────────────────┘

MEAL 1: Baked Paneer Curry (4 servings)
────────────────────────────────────────
✓  Baby Spinach 6oz        →  365 Organic Baby Spinach 5oz     $3.49
✓  Tomato Sauce 8oz can    →  365 Organic Tomato Sauce 8oz     $1.29
...

?  Paneer Cheese 8oz       →  NEEDS SELECTION
   [1] Gopi Paneer 12oz                    $5.99
   [2] Nanak Fresh Paneer 14oz             $6.49
   [3] 365 Paneer Cheese 8oz               $4.99
   Pick [1-3] or search [s]: _

────────────────────────────────────────
Estimated total: $87.40

[c] Confirm & place order   [e] Edit an item   [x] Cancel
```

On confirm:
- Specialty item choices saved to pantry DB
- Checkout executor runs

---

## Scheduling (launchd)

`launchd/com.mealrotation.plist` runs `python -m purchasing run` on a weekly schedule (e.g. Sunday 8am). The job expects `recipes/current-week.json` to exist; if not found, it exits cleanly with a log message. The recipe search module (future) is responsible for writing that file.

---

## Interface Boundary with Recipe Search Module (Future)

The purchasing flow owns everything downstream of a valid `recipes/current-week.json`. The recipe search module owns everything upstream. The contract is the JSON schema defined above. No other coupling between the two modules.

---

## Out of Scope

- Recipe search and selection
- Ingredient extraction from images or text (the baked paneer curry JSON is hand-authored for testing)
- Mobile notifications or web UI
- Multi-user / household support
- Amazon Fresh (only Whole Foods delivery is targeted)
