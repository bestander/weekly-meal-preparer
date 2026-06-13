"""Amazon product price lookup helpers."""


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def make_price_lookup(session_path: str):
    """Return a function that fetches the current price for an ASIN."""

    def lookup(asin: str) -> float | None:
        from playwright.sync_api import sync_playwright
        from purchasing.auth import load_session
        from purchasing.stealth import apply_stealth_sync

        cookies = load_session(session_path)
        if cookies is None:
            return None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            context.add_cookies(cookies)
            page = context.new_page()
            apply_stealth_sync(page)
            page.goto(f"https://www.amazon.com/dp/{asin}", wait_until="domcontentloaded")
            page.wait_for_selector(
                "#buybox .a-price .a-offscreen, .a-price .a-offscreen",
                timeout=10_000,
            )
            price_el = page.query_selector("#buybox .a-price .a-offscreen, .a-price .a-offscreen")
            price = _parse_price(price_el.inner_text()) if price_el else None
            browser.close()
        return price

    return lookup
