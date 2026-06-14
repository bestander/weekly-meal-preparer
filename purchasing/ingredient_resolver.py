from dataclasses import dataclass, field

from purchasing.ingredient_aggregate import aggregate_ingredients

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
    meals: list[str] = field(default_factory=list)
    order_once: bool = False
    asin: str | None = None
    product_title: str | None = None
    price: float | None = None
    candidates: list[dict] = field(default_factory=list)  # [{asin, title, price}]


def _match_candidate(asin: str, candidates: list[dict]) -> tuple[float | None, str | None]:
    for candidate in candidates:
        if candidate["asin"] == asin:
            return candidate.get("price"), candidate.get("title")
    return None, None


def _resolve_one(ing: dict, pantry, search_fn, price_fn=None) -> "ResolvedIngredient":
    """Resolve a single aggregated ingredient dict to a ResolvedIngredient."""
    name = ing["name"]
    pantry_entry = pantry.get(name)
    if pantry_entry:
        candidates = search_fn(name)[:3]
        price, title = _match_candidate(pantry_entry["asin"], candidates)
        if price is None and price_fn:
            price = price_fn(pantry_entry["asin"])
        return ResolvedIngredient(
            name=name,
            quantity=ing["quantity"],
            unit=ing["unit"],
            status="auto",
            meals=list(ing.get("meals") or []),
            order_once=bool(ing.get("order_once")),
            asin=pantry_entry["asin"],
            product_title=title or pantry_entry["product_title"],
            price=price,
        )

    status = classify_ingredient(name)
    candidates = search_fn(name)[:3]

    if status == "auto":
        top = candidates[0] if candidates else None
        return ResolvedIngredient(
            name=name,
            quantity=ing["quantity"],
            unit=ing["unit"],
            status="auto",
            meals=list(ing.get("meals") or []),
            order_once=bool(ing.get("order_once")),
            asin=top["asin"] if top else None,
            product_title=top["title"] if top else None,
            price=top["price"] if top else None,
        )

    return ResolvedIngredient(
        name=name,
        quantity=ing["quantity"],
        unit=ing["unit"],
        status="review",
        meals=list(ing.get("meals") or []),
        order_once=bool(ing.get("order_once")),
        candidates=candidates,
    )


def resolve_ingredients(
    meals: list[dict],
    pantry,
    search_fn,
    price_fn=None,
    on_progress=None,
) -> list["ResolvedIngredient"]:
    """
    Resolve aggregated ingredients across all meals to Amazon products.

    search_fn(query: str) -> list[{asin, title, price}]
    price_fn(asin: str) -> float | None  — optional fallback for pantry items
    on_progress(event: dict) — optional callback with phase, meal, ingredient, etc.
    """
    aggregated = aggregate_ingredients(meals)
    results = []
    total = len(aggregated)

    for current, ing in enumerate(aggregated, 1):
        meal_label = ", ".join(ing["meals"]) if len(ing["meals"]) <= 2 else f"{len(ing['meals'])} meals"
        if on_progress:
            on_progress({
                "phase": "searching",
                "current": current,
                "total": total,
                "meal": meal_label,
                "ingredient": ing["name"],
                "aggregated": True,
            })
        resolved = _resolve_one(ing, pantry, search_fn, price_fn)
        results.append(resolved)
        if on_progress:
            on_progress({
                "phase": "resolved",
                "current": current,
                "total": total,
                "meal": meal_label,
                "ingredient": ing["name"],
                "status": resolved.status,
                "aggregated": True,
            })

    return results


async def resolve_ingredients_async(
    meals: list[dict],
    pantry,
    search_fn,
    price_fn=None,
    on_progress=None,
) -> list["ResolvedIngredient"]:
    """
    Async variant of resolve_ingredients.

    search_fn(query) — awaitable returning [{asin, title, price}]
    price_fn(asin) — optional awaitable returning price
    """
    aggregated = aggregate_ingredients(meals)
    results = []
    total = len(aggregated)

    for current, ing in enumerate(aggregated, 1):
        meal_label = ", ".join(ing["meals"]) if len(ing["meals"]) <= 2 else f"{len(ing['meals'])} meals"
        if on_progress:
            on_progress({
                "phase": "searching",
                "current": current,
                "total": total,
                "meal": meal_label,
                "ingredient": ing["name"],
                "aggregated": True,
            })
        resolved = await _resolve_one_async(ing, pantry, search_fn, price_fn)
        results.append(resolved)
        if on_progress:
            on_progress({
                "phase": "resolved",
                "current": current,
                "total": total,
                "meal": meal_label,
                "ingredient": ing["name"],
                "status": resolved.status,
                "aggregated": True,
            })

    return results


async def _resolve_one_async(ing: dict, pantry, search_fn, price_fn=None) -> "ResolvedIngredient":
    name = ing["name"]
    pantry_entry = pantry.get(name)
    if pantry_entry:
        candidates = (await search_fn(name))[:3]
        price, title = _match_candidate(pantry_entry["asin"], candidates)
        if price is None and price_fn:
            price = await price_fn(pantry_entry["asin"])
        return ResolvedIngredient(
            name=name,
            quantity=ing["quantity"],
            unit=ing["unit"],
            status="auto",
            meals=list(ing.get("meals") or []),
            order_once=bool(ing.get("order_once")),
            asin=pantry_entry["asin"],
            product_title=title or pantry_entry["product_title"],
            price=price,
        )

    status = classify_ingredient(name)
    candidates = (await search_fn(name))[:3]

    if status == "auto":
        top = candidates[0] if candidates else None
        return ResolvedIngredient(
            name=name,
            quantity=ing["quantity"],
            unit=ing["unit"],
            status="auto",
            meals=list(ing.get("meals") or []),
            order_once=bool(ing.get("order_once")),
            asin=top["asin"] if top else None,
            product_title=top["title"] if top else None,
            price=top["price"] if top else None,
        )

    return ResolvedIngredient(
        name=name,
        quantity=ing["quantity"],
        unit=ing["unit"],
        status="review",
        meals=list(ing.get("meals") or []),
        order_once=bool(ing.get("order_once")),
        candidates=candidates,
    )
