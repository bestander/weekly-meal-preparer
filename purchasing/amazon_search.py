"""Amazon Whole Foods search with a reusable async browser session."""

from __future__ import annotations

from purchasing.auth import load_session
from purchasing.prices import _parse_price
from purchasing.stealth import apply_stealth_async

SEARCH_SELECTOR = "[data-component-type='s-search-result']"
PRICE_SELECTOR = "#buybox .a-price .a-offscreen, .a-price .a-offscreen"


class AsyncAmazonSearchSession:
    """Reuse one async Playwright browser for searches and price lookups."""

    def __init__(self, session_path: str):
        self._session_path = session_path
        self._playwright = None
        self._browser = None
        self._page = None

    async def start(self) -> None:
        if self._page is not None:
            return

        from playwright.async_api import async_playwright

        cookies = load_session(self._session_path)
        if cookies is None:
            raise RuntimeError(
                f"No session found at {self._session_path}. Run: python -m purchasing auth login"
            )

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        context = await self._browser.new_context()
        await context.add_cookies(cookies)
        self._page = await context.new_page()
        await apply_stealth_async(self._page)

    async def search(self, query: str) -> list[dict]:
        await self.start()
        url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}&i=wholefoods"
        await self._page.goto(url, wait_until="domcontentloaded")
        await self._page.wait_for_selector(SEARCH_SELECTOR, timeout=10_000)

        results = []
        for item in await self._page.query_selector_all(SEARCH_SELECTOR):
            if len(results) >= 3:
                break
            try:
                asin = await item.get_attribute("data-asin")
                title_el = await item.query_selector("h2 span, .a-text-normal")
                price_el = await item.query_selector(".a-price .a-offscreen")
                title = (await title_el.inner_text()).strip() if title_el else "Unknown"
                price_text = await price_el.inner_text() if price_el else ""
                price = _parse_price(price_text)
                if asin:
                    results.append({"asin": asin, "title": title, "price": price})
            except Exception:
                continue
        return results

    async def lookup_price(self, asin: str) -> float | None:
        await self.start()
        await self._page.goto(
            f"https://www.amazon.com/dp/{asin}",
            wait_until="domcontentloaded",
        )
        await self._page.wait_for_selector(PRICE_SELECTOR, timeout=10_000)
        price_el = await self._page.query_selector(PRICE_SELECTOR)
        if not price_el:
            return None
        return _parse_price(await price_el.inner_text())

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_args):
        await self.close()
