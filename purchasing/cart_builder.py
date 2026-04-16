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


async def build_cart(session_path: str, items: list[dict]) -> list[CartItem]:
    """
    Add each item to the Amazon Whole Foods cart.
    items: list of {name, asin, product_title, price, quantity, unit}
    Returns list of CartItem for items successfully added.
    """
    from playwright.async_api import async_playwright
    from playwright_stealth import stealth_async

    cookies = load_session(session_path)
    if cookies is None:
        raise RuntimeError(
            f"No session found at {session_path}. Run: python -m purchasing auth login"
        )

    added = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await stealth_async(page)
        await context.add_cookies(cookies)

        for item in items:
            print(f"  Adding {item['name']}...", end=" ", flush=True)
            try:
                await page.goto(
                    f"https://www.amazon.com/dp/{item['asin']}",
                    wait_until="domcontentloaded",
                )
                await asyncio.sleep(random.uniform(1.0, 3.0))
                await page.click("[id='add-to-cart-button']", timeout=10_000)
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
