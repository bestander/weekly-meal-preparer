import asyncio
import random
from dataclasses import dataclass

from purchasing.auth import load_session


@dataclass
class CartItem:
    name: str
    asin: str
    product_title: str
    price: float


ADD_TO_CART_SELECTORS = [
    "#add-to-cart-button-grocery",  # Whole Foods / local market
    "#add-to-cart-button",
    "#add-to-cart-button-ubb",
    "input[name='submit.add-to-cart']",
]

NAV_TIMEOUT_MS = 60_000


def dedupe_by_asin(items: list[dict]) -> list[dict]:
    """Keep one entry per ASIN (same product matched for multiple recipe lines)."""
    seen: dict[str, dict] = {}
    for item in items:
        asin = item.get("asin")
        if not asin:
            continue
        if asin not in seen:
            seen[asin] = item
    return list(seen.values())


async def _click_add_to_cart(page) -> None:
    """Click the first visible add-to-cart control on a product page."""
    combined = ", ".join(ADD_TO_CART_SELECTORS)
    await page.wait_for_selector(combined, timeout=15_000)
    for selector in ADD_TO_CART_SELECTORS:
        button = page.locator(selector)
        if await button.count() and await button.first.is_visible():
            await button.first.click(timeout=10_000)
            return
    raise RuntimeError("Add to cart button not found")


async def _add_one_via_product_page(page, item: dict) -> None:
    await page.goto(
        f"https://www.amazon.com/dp/{item['asin']}",
        wait_until="domcontentloaded",
        timeout=NAV_TIMEOUT_MS,
    )
    await asyncio.sleep(random.uniform(0.75, 1.5))
    await _click_add_to_cart(page)
    await asyncio.sleep(random.uniform(0.4, 0.8))


def _emit_cart_progress(on_progress, *, index, total, added, cart_total, item, status, error=None):
    if not on_progress:
        return
    event = {
        "phase": "cart",
        "status": status,
        "current": index,
        "total": total,
        "itemsAdded": len(added),
        "cartTotal": cart_total,
        "name": item["name"],
    }
    if error:
        event["error"] = error
    on_progress(event)


async def build_cart(
    session_path: str,
    items: list[dict],
    on_progress=None,
) -> list[CartItem]:
    """
    Add each item to the Amazon Whole Foods cart one at a time.

    items: list of {name, asin, product_title, price, quantity, unit}
    on_progress(event: dict) — optional callback during cart building
    Returns list of CartItem for items successfully added.
    """
    from playwright.async_api import async_playwright
    from purchasing.stealth import apply_stealth_async

    cookies = load_session(session_path)
    if cookies is None:
        raise RuntimeError(
            f"No session found at {session_path}. Run: python -m purchasing auth login"
        )

    unique_items = dedupe_by_asin(items)
    total = len(unique_items)
    added_items: list[dict] = []
    cart_total = 0.0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_cookies(cookies)
        page = await context.new_page()
        await apply_stealth_async(page)

        for index, item in enumerate(unique_items, 1):
            _emit_cart_progress(
                on_progress,
                index=index,
                total=total,
                added=added_items,
                cart_total=cart_total,
                item=item,
                status="adding",
            )
            print(f"  Adding {item['name']}...", end=" ", flush=True)
            try:
                await _add_one_via_product_page(page, item)
                added_items.append(item)
                cart_total += item.get("price") or 0
                print("✓")
                _emit_cart_progress(
                    on_progress,
                    index=index,
                    total=total,
                    added=added_items,
                    cart_total=cart_total,
                    item=item,
                    status="added",
                )
            except Exception as exc:
                print(f"✗ ({exc})")
                _emit_cart_progress(
                    on_progress,
                    index=index,
                    total=total,
                    added=added_items,
                    cart_total=cart_total,
                    item=item,
                    status="failed",
                    error=str(exc),
                )

        await browser.close()

    return [
        CartItem(
            name=item["name"],
            asin=item["asin"],
            product_title=item["product_title"],
            price=item["price"],
        )
        for item in added_items
    ]
