"""Whole Foods–only helpers for Amazon search and cart."""

WHOLE_FOODS_SEARCH_INDEX = "wholefoods"
WHOLE_FOODS_NOT_FOUND = "Not available at Whole Foods"
WF_ADD_TO_CART_SELECTOR = "#add-to-cart-button-grocery"


async def is_whole_foods_search_result(item) -> bool:
    """True if a search result listing appears to be from Whole Foods."""
    try:
        text = (await item.inner_text()).lower()
        if "whole foods" in text:
            return True
    except Exception:
        pass
    badge = await item.query_selector(
        "[aria-label*='Whole Foods' i], [aria-label*='Whole Foods Market' i]"
    )
    return badge is not None
