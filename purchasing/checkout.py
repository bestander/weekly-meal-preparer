import asyncio
from dataclasses import dataclass
from purchasing.auth import load_session


@dataclass
class OrderConfirmation:
    order_id: str
    total: float


PRICE_DEVIATION_GUARD = 0.20  # abort if actual total is >20% off estimate


async def run_checkout(session_path: str, estimated_total: float) -> OrderConfirmation:
    """
    Complete checkout from an already-filled Amazon cart.
    Aborts if final total deviates more than 20% from estimated_total.
    """
    from playwright.async_api import async_playwright
    from purchasing.stealth import apply_stealth_async

    cookies = load_session(session_path)
    if cookies is None:
        raise RuntimeError(
            f"No session found at {session_path}. Run: python -m purchasing auth login"
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await apply_stealth_async(page)
        await context.add_cookies(cookies)

        await page.goto("https://www.amazon.com/cart", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        await page.click("[name='proceedToRetailCheckout']", timeout=10_000)
        await asyncio.sleep(2)

        actual_total = await _get_order_total(page, estimated_total)
        _check_price_deviation(actual_total, estimated_total, browser)

        await page.click("[name='placeYourOrder1']", timeout=10_000)
        await asyncio.sleep(3)

        order_id = await _get_order_id(page)
        await browser.close()

    print(f"\nOrder placed! ID: {order_id}  Total: ${actual_total:.2f}")
    return OrderConfirmation(order_id=order_id, total=actual_total)


async def _get_order_total(page, fallback: float) -> float:
    try:
        text = await page.inner_text("[class*='order-summary-total']", timeout=5_000)
        return float(text.replace("$", "").replace(",", "").strip())
    except Exception:
        return fallback


def _check_price_deviation(actual: float, estimated: float, browser) -> None:
    deviation = abs(actual - estimated) / max(estimated, 0.01)
    if deviation > PRICE_DEVIATION_GUARD:
        raise RuntimeError(
            f"Order total ${actual:.2f} deviates {deviation:.0%} from "
            f"estimate ${estimated:.2f}. Aborting — review cart manually."
        )


async def _get_order_id(page) -> str:
    try:
        text = await page.inner_text("[class*='order-id']", timeout=5_000)
        return text.strip()
    except Exception:
        return "unknown"
