"""Wire Amazon search, disk cache, and browser session reuse."""

from __future__ import annotations

import asyncio

from purchasing.amazon_search import AsyncAmazonSearchSession
from purchasing.ingredient_aggregate import normalize_ingredient_key
from purchasing.product_cache import DEFAULT_CACHE_PATH, ProductCache


async def run_cached_search_session(
    session_path: str,
    callback,
    cache_path: str = DEFAULT_CACHE_PATH,
    ttl_days: int = 3,
):
    """
    Open one async browser session, provide cached search + price lookup to callback.

    callback(search_fn, price_fn) — async or sync callable receiving awaitable functions
    """
    cache = ProductCache(cache_path, ttl_days=ttl_days)
    session = AsyncAmazonSearchSession(session_path)
    await session.start()

    async def search(name: str) -> list[dict]:
        key = normalize_ingredient_key(name)
        hit = cache.get_candidates(key)
        if hit is not None:
            return hit
        results = (await session.search(name))[:3]
        cache.set_candidates(key, results)
        return results

    async def price_fn(asin: str):
        return await session.lookup_price(asin)

    try:
        result = callback(search, price_fn)
        if asyncio.iscoroutine(result):
            return await result
        return result
    finally:
        await session.close()
