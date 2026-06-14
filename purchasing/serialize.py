from purchasing.ingredient_resolver import ResolvedIngredient


def resolved_to_dict(item: ResolvedIngredient, index: int) -> dict:
    meals = item.meals or []
    return {
        "index": index,
        "meals": meals,
        "meal": ", ".join(meals[:2]) + (f" (+{len(meals) - 2})" if len(meals) > 2 else ""),
        "name": item.name,
        "quantity": item.quantity,
        "unit": item.unit,
        "orderOnce": item.order_once,
        "status": item.status,
        "asin": item.asin,
        "productTitle": item.product_title,
        "price": item.price,
        "candidates": item.candidates,
    }


def resolved_from_dict(data: dict) -> ResolvedIngredient:
    meals = data.get("meals")
    if not meals and data.get("meal"):
        meals = [data["meal"]]
    return ResolvedIngredient(
        meals=list(meals or []),
        order_once=bool(data.get("orderOnce")),
        name=data["name"],
        quantity=data["quantity"],
        unit=data["unit"],
        status=data["status"],
        asin=data.get("asin"),
        product_title=data.get("productTitle"),
        price=data.get("price"),
        candidates=data.get("candidates") or [],
    )
