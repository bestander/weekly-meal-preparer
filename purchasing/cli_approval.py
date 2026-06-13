from dataclasses import dataclass, field
from purchasing.ingredient_resolver import ResolvedIngredient

SKIP = "SKIP"
CART_URL = "https://www.amazon.com/cart"


@dataclass
class ApprovalResult:
    approved: bool
    confirmed_items: list[dict]  # [{name, asin, product_title, price, quantity, unit}]
    skipped_items: list[str] = field(default_factory=list)


def run_approval(
    resolved: list[ResolvedIngredient],
    meals: list[dict],
    search_fn=None,
) -> ApprovalResult | None:
    """
    Show the weekly cart to the user. Collect picks for review items.
    Returns ApprovalResult on confirm, None on cancel.
    """
    auto_items = [r for r in resolved if r.status == "auto"]
    review_items = [r for r in resolved if r.status == "review"]

    _print_header(meals)
    kept_auto, skipped_auto = _review_auto_items(auto_items)
    picks, skipped_review = _collect_picks(review_items, search_fn)
    if picks is None:
        return None

    skipped = skipped_auto + skipped_review

    while True:
        _print_summary(kept_auto, picks, skipped)
        choice = input(
            "\n[c] Confirm & add to cart   [e] Edit review items   [x] Cancel\n> "
        ).strip().lower()
        if choice == "x":
            print("Order cancelled.")
            return None
        if choice == "c":
            break
        if choice == "e":
            picks, skipped_review = _collect_picks(review_items, search_fn)
            if picks is None:
                return None
            skipped = skipped_auto + skipped_review

    confirmed = [
        {"name": r.name, "asin": r.asin, "product_title": r.product_title,
         "price": r.price, "quantity": r.quantity, "unit": r.unit}
        for r in kept_auto
    ] + picks

    return ApprovalResult(approved=True, confirmed_items=confirmed, skipped_items=skipped)


def _print_header(meals: list[dict]):
    print("\n" + "=" * 57)
    print("  Meal Rotation — Weekly Order")
    print(f"  {', '.join(m['name'] for m in meals)}")
    print("=" * 57)


def _review_auto_items(auto_items: list[ResolvedIngredient]) -> tuple[list[ResolvedIngredient], list[str]]:
    """Show auto-matched items and let the user skip ones they already have."""
    if not auto_items:
        return [], []

    print("\nAUTO-MATCHED ITEMS:")
    for index, item in enumerate(auto_items, 1):
        title = item.product_title or "N/A"
        price = item.price or 0
        print(f"  [{index}] {item.name} {item.quantity} {item.unit:<10}  →  {title:<35}  ${price:.2f}")

    skipped = _prompt_skip(auto_items, "auto-matched")
    kept = [item for index, item in enumerate(auto_items, 1) if index not in skipped]
    return kept, [auto_items[index - 1].name for index in skipped]


def _collect_picks(
    review_items: list[ResolvedIngredient],
    search_fn=None,
) -> tuple[list[dict] | None, list[str]]:
    """Prompt user to pick one candidate per review item. Returns (picks, skipped_names)."""
    if not review_items:
        return [], []

    picks = []
    skipped = []
    print("\nITEMS NEEDING YOUR SELECTION:")
    for item in review_items:
        pick = _pick_candidate(item, search_fn)
        if pick is None:
            return None, []
        if pick == SKIP:
            skipped.append(item.name)
            continue
        picks.append(pick)
    return picks, skipped


def _pick_candidate(item: ResolvedIngredient, search_fn=None) -> dict | str | None:
    """Prompt for one candidate pick. Returns chosen dict, SKIP, or None on cancel."""
    while True:
        print(f"\n  ? {item.name} {item.quantity} {item.unit}")
        if not item.candidates:
            print("     No products found on Amazon Whole Foods.")
            if search_fn is None:
                choice = input("     [s] Skip   [x] Cancel: ").strip().lower()
                if choice == "s":
                    print("     Skipped.")
                    return SKIP
                if choice == "x":
                    print("Order cancelled.")
                    return None
                print("     Invalid choice. Enter [s] to skip or [x] to cancel.")
                continue

            choice = input("     [r] Retry search   [s] Skip   [x] Cancel: ").strip().lower()
            if choice == "s":
                print("     Skipped.")
                return SKIP
            if choice == "x":
                print("Order cancelled.")
                return None
            if choice == "r":
                print("     Searching...")
                item.candidates = search_fn(item.name)[:3]
                continue
            print("     Invalid choice. Enter [r], [s], or [x].")
            continue

        for i, c in enumerate(item.candidates, 1):
            print(f"     [{i}] {c['title']:<40}  ${c['price']:.2f}")

        max_pick = len(item.candidates)
        choice = input(
            f"     Pick [1-{max_pick}], [s] Skip, or [x] Cancel: "
        ).strip().lower()
        if choice == "s":
            print("     Skipped.")
            return SKIP
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
        print(f"     Invalid choice. Enter 1-{max_pick}, [s], or [x].")


def _prompt_skip(items: list[ResolvedIngredient], label: str) -> set[int]:
    """Return 1-based indices of items the user wants to skip."""
    while True:
        choice = input(
            f"\n  Skip any {label} items you already have? "
            "Enter numbers (e.g. 2,4) or press Enter: "
        ).strip()
        if not choice:
            return set()
        try:
            indices = {int(part.strip()) for part in choice.split(",") if part.strip()}
        except ValueError:
            print("  Invalid input. Use comma-separated numbers, e.g. 2,4")
            continue
        invalid = [index for index in indices if index < 1 or index > len(items)]
        if invalid:
            print(f"  Invalid item numbers: {', '.join(str(i) for i in sorted(invalid))}")
            continue
        return indices


def _print_summary(
    auto_items: list[ResolvedIngredient],
    picks: list[dict],
    skipped: list[str],
):
    total = sum(i.price or 0 for i in auto_items) + sum(p["price"] or 0 for p in picks)
    print(f"\n{'─' * 57}")
    print("  ORDERING:")
    for item in auto_items:
        title = item.product_title or "N/A"
        price = item.price or 0
        print(f"  ✓  {item.name} {item.quantity} {item.unit:<10}  →  {title:<35}  ${price:.2f}")
    for item in picks:
        print(
            f"  ✓  {item['name']} {item['quantity']} {item['unit']:<10}  →  "
            f"{item['product_title']:<35}  ${item['price'] or 0:.2f}"
        )
    if skipped:
        print("\n  SKIPPED (already have):")
        for name in skipped:
            print(f"  -  {name}")
    print(f"\n  Estimated total: ${total:.2f}")
