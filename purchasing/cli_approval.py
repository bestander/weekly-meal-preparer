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
    print(f"  {', '.join(m['name'] for m in meals)}")
    print("=" * 57)
    print("\nAUTO-MATCHED ITEMS:")
    for item in auto_items:
        title = item.product_title or "N/A"
        price = item.price or 0
        print(f"  ✓  {item.name} {item.quantity}{item.unit:<10}  →  {title:<35}  ${price:.2f}")


def _collect_picks(review_items: list[ResolvedIngredient]) -> list[dict] | None:
    """Prompt user to pick one candidate per review item. Returns None on cancel."""
    if not review_items:
        return []

    picks = []
    print("\nITEMS NEEDING YOUR SELECTION:")
    for item in review_items:
        pick = _pick_candidate(item)
        if pick is None:
            return None
        picks.append(pick)
    return picks


def _pick_candidate(item: ResolvedIngredient) -> dict | None:
    """Prompt for one candidate pick. Returns chosen dict or None on cancel."""
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
                c = item.candidates[idx]
                return {
                    "name": item.name, "asin": c["asin"], "product_title": c["title"],
                    "price": c["price"], "quantity": item.quantity, "unit": item.unit,
                }
        except ValueError:
            pass
        print("     Invalid choice. Enter a number between 1 and", len(item.candidates))


def _print_summary(auto_items: list[ResolvedIngredient], picks: list[dict]):
    total = sum(i.price or 0 for i in auto_items) + sum(p["price"] for p in picks)
    print(f"\n{'─' * 57}")
    print(f"  Estimated total: ${total:.2f}")
