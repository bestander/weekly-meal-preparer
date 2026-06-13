"""Thin wrapper around playwright-stealth 2.x API."""
from playwright_stealth import Stealth

_instance = Stealth()


async def apply_stealth_async(page_or_context) -> None:
    await _instance.apply_stealth_async(page_or_context)


def apply_stealth_sync(page_or_context) -> None:
    _instance.apply_stealth_sync(page_or_context)
