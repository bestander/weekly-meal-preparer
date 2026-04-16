import json
import pathlib
from datetime import datetime, timezone


SESSION_MAX_AGE_DAYS = 25  # Amazon sessions last ~30 days; refresh proactively


def save_session(cookies: list[dict], path: str) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    data = {"saved_at": datetime.now(timezone.utc).isoformat(), "cookies": cookies}
    pathlib.Path(path).write_text(json.dumps(data, indent=2))


def load_session(path: str) -> list[dict] | None:
    p = pathlib.Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return data.get("cookies")


def is_session_valid(path: str) -> bool:
    p = pathlib.Path(path)
    if not p.exists():
        return False
    data = json.loads(p.read_text())
    saved_at = datetime.fromisoformat(data["saved_at"])
    age_days = (datetime.now(timezone.utc) - saved_at).days
    return age_days < SESSION_MAX_AGE_DAYS


async def login_interactive(session_path: str) -> None:
    """
    Open a visible Chrome browser. User logs in to Amazon and selects Whole Foods
    as delivery store. When they close the window, cookies are saved.
    """
    from playwright.async_api import async_playwright
    from playwright_stealth import stealth_async

    print("Opening browser. Log in to Amazon, confirm Whole Foods as your delivery store,")
    print("then close the browser window.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await stealth_async(page)
        await page.goto("https://www.amazon.com/gp/flex/sign-in/select.html")

        # Wait until the user closes the browser
        try:
            await page.wait_for_event("close", timeout=300_000)  # 5 min timeout
        except Exception:
            pass

        cookies = await context.cookies()
        await browser.close()

    save_session(cookies, session_path)
    print(f"Session saved to {session_path}")
