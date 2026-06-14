"""Combine duplicate ingredients across meals before Amazon resolution."""

from __future__ import annotations

# Map variant names to a shared shopping key.
NAME_ALIASES: dict[str, str] = {
    "yellow onion": "onion",
    "white onion": "onion",
    "red onion": "onion",
    "sweet onion": "onion",
    "green onion": "scallion",
    "green onions": "scallion",
    "all-purpose flour": "flour",
    "all purpose flour": "flour",
}

# Units that convert to a canonical base for summing.
WEIGHT_TO_OZ = {"oz": 1.0, "ounce": 1.0, "lb": 16.0, "pound": 16.0, "lbs": 16.0}

HERB_SPICE_WORDS = {
    "garlic", "thyme", "cilantro", "parsley", "basil", "oregano", "rosemary",
    "sage", "dill", "chives", "chive", "ginger", "jalapeño", "jalapeno",
    "lemongrass", "mint", "bay", "cumin", "paprika", "turmeric", "coriander",
    "cinnamon", "nutmeg", "vanilla", "oregano", "tarragon", "marjoram",
}

ONCE_UNITS = {"clove", "tsp", "tbsp", "bunch", "sprig", "pinch", "packet"}


def normalize_ingredient_key(name: str) -> str:
    key = name.strip().lower()
    return NAME_ALIASES.get(key, key)


def _normalize_unit(unit: str) -> str:
    u = unit.strip().lower().rstrip("s")
    if u == "pieces":
        return "piece"
    if u == "bunches":
        return "bunch"
    if u == "cloves":
        return "clove"
    if u == "packets":
        return "packet"
    if u == "heads":
        return "head"
    if u == "cups":
        return "cup"
    return u


def _to_oz(quantity: float, unit: str) -> tuple[float, str] | None:
    u = _normalize_unit(unit)
    factor = WEIGHT_TO_OZ.get(u)
    if factor is None:
        return None
    return quantity * factor, "oz"


def _units_compatible(a: str, b: str) -> bool:
    na, nb = _normalize_unit(a), _normalize_unit(b)
    if na == nb:
        return True
    if na in WEIGHT_TO_OZ and nb in WEIGHT_TO_OZ:
        return True
    return False


def _combine_quantity(existing_qty: float, existing_unit: str, add_qty: float, add_unit: str) -> tuple[float, str]:
    ea, eb = _normalize_unit(existing_unit), _normalize_unit(add_unit)

    existing_oz = _to_oz(existing_qty, existing_unit)
    add_oz = _to_oz(add_qty, add_unit)
    if existing_oz and add_oz:
        return existing_oz[0] + add_oz[0], "oz"

    if ea == eb:
        return existing_qty + add_qty, existing_unit

    # Incompatible units — keep the larger single-meal need for display.
    return max(existing_qty, add_qty), existing_unit


def is_order_once(name: str, unit: str, total_quantity: float) -> bool:
    """
    Small aromatics/spices: one package covers the whole week even if several
    recipes call for a little.
    """
    u = _normalize_unit(unit)
    if u in ONCE_UNITS:
        return True

    words = normalize_ingredient_key(name).replace("-", " ").split()
    if any(word in HERB_SPICE_WORDS for word in words):
        return True

    n = normalize_ingredient_key(name)
    if ("concentrate" in n or "paste" in n) and u in ONCE_UNITS:
        return True

    # Very small total amounts of dry spices.
    if u in ("tsp", "tbsp") and total_quantity <= 8:
        return True

    return False


def aggregate_ingredients(meals: list[dict]) -> list[dict]:
    """
    Merge ingredients across meals.

    Returns dicts with: name, quantity, unit, meals (list[str]), order_once (bool).
    """
    buckets: dict[str, dict] = {}

    for meal in meals:
        meal_name = meal["name"]
        for ing in meal["ingredients"]:
            key = normalize_ingredient_key(ing["name"])
            qty = float(ing["quantity"])
            unit = ing["unit"]

            if key not in buckets:
                buckets[key] = {
                    "name": ing["name"],
                    "quantity": qty,
                    "unit": unit,
                    "meals": [meal_name],
                }
                continue

            bucket = buckets[key]
            if meal_name not in bucket["meals"]:
                bucket["meals"].append(meal_name)

            if _units_compatible(bucket["unit"], unit):
                combined_qty, combined_unit = _combine_quantity(
                    bucket["quantity"], bucket["unit"], qty, unit,
                )
                bucket["quantity"] = combined_qty
                bucket["unit"] = combined_unit
            else:
                bucket["quantity"] = max(bucket["quantity"], qty)

    result = []
    for bucket in buckets.values():
        bucket["order_once"] = is_order_once(
            bucket["name"], bucket["unit"], bucket["quantity"],
        )
        result.append(bucket)
    return result
