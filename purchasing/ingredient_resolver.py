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
