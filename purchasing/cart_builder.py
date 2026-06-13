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


async def build_cart(session_path: str, items: list[dict]) -> list[CartItem]:
    """
    Add each item to the Amazon Whole Foods cart.
    items: list of {name, asin, product_title, price, quantity, unit}
    Returns list of CartItem for items successfully added.
    """
    from playwright.async_api import async_playwright
    from purchasing.stealth import apply_stealth_async

    cookies = load_session(session_path)
    if cookies is None:
        raise RuntimeError(
            f"No session found at {session_path}. Run: python -m purchasing auth login"
        )

    added = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_cookies(cookies)
        page = await context.new_page()
        await apply_stealth_async(page)

        for item in items:
            print(f"  Adding {item['name']}...", end=" ", flush=True)
            try:
                await page.goto(
                    f"https://www.amazon.com/dp/{item['asin']}",
                    wait_until="domcontentloaded",
                )
                await asyncio.sleep(random.uniform(1.0, 3.0))
                await _click_add_to_cart(page)
                await asyncio.sleep(random.uniform(0.5, 1.5))
                added.append(CartItem(
                    name=item["name"],
                    asin=item["asin"],
                    product_title=item["product_title"],
                    price=item["price"],
                ))
                print("✓")
            except Exception as e:
                print(f"✗ ({e})")

        await browser.close()

    return added
