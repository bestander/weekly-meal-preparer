"""Shared approval logic for CLI and web flows."""

from purchasing.cli_approval import ApprovalResult
from purchasing.ingredient_resolver import ResolvedIngredient


def apply_approval(
    resolved: list[ResolvedIngredient],
    skipped_auto: set[int],
    review_picks: dict[int, int],
) -> ApprovalResult:
    """
    Apply user choices to resolved ingredients.

    skipped_auto: 0-based indices into the auto-matched sublist.
    review_picks: resolved list index -> candidate index (0-based), or -1 to skip.
    """
    auto_items = [r for r in resolved if r.status == "auto"]
    kept_auto = [item for i, item in enumerate(auto_items) if i not in skipped_auto]
    skipped = [auto_items[i].name for i in sorted(skipped_auto)]

    picks = []
    for idx, item in enumerate(resolved):
        if item.status != "review":
            continue
        if idx not in review_picks:
            raise ValueError(f"No pick for review item: {item.name}")
        pick_idx = review_picks[idx]
        if pick_idx == -1:
            skipped.append(item.name)
            continue
        if pick_idx < 0 or pick_idx >= len(item.candidates):
            raise ValueError(f"Invalid candidate for {item.name}")
        c = item.candidates[pick_idx]
        picks.append({
            "name": item.name,
            "asin": c["asin"],
            "product_title": c["title"],
            "price": c["price"],
            "quantity": item.quantity,
            "unit": item.unit,
        })

    confirmed = [
        {
            "name": r.name,
            "asin": r.asin,
            "product_title": r.product_title,
            "price": r.price,
            "quantity": r.quantity,
            "unit": r.unit,
        }
        for r in kept_auto
    ] + picks

    return ApprovalResult(approved=True, confirmed_items=confirmed, skipped_items=skipped)
