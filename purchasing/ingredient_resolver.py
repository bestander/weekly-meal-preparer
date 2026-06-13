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


def _match_candidate(asin: str, candidates: list[dict]) -> tuple[float | None, str | None]:
    for candidate in candidates:
        if candidate["asin"] == asin:
            return candidate.get("price"), candidate.get("title")
    return None, None


def _resolve_one(ing: dict, pantry, search_fn, price_fn=None) -> "ResolvedIngredient":
    """Resolve a single ingredient dict to a ResolvedIngredient."""
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
            asin=top["asin"] if top else None,
            product_title=top["title"] if top else None,
            price=top["price"] if top else None,
        )

    return ResolvedIngredient(
        name=name,
        quantity=ing["quantity"],
        unit=ing["unit"],
        status="review",
        candidates=candidates,
    )


def resolve_ingredients(
    meals: list[dict],
    pantry,
    search_fn,
    price_fn=None,
) -> list["ResolvedIngredient"]:
    """
    Resolve all ingredients across all meals to Amazon products.

    search_fn(query: str) -> list[{asin, title, price}]
    price_fn(asin: str) -> float | None  — optional fallback for pantry items
    """
    return [
        _resolve_one(ing, pantry, search_fn, price_fn)
        for meal in meals
        for ing in meal["ingredients"]
    ]
