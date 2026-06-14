"""Tests for cart deduplication."""

import asyncio

import pytest

from purchasing.cart_builder import ADD_TO_CART_SELECTORS, _click_add_to_cart, dedupe_by_asin


def test_dedupe_by_asin_keeps_first_occurrence():
    items = [
        {"asin": "B001", "name": "Zucchini", "product_title": "Z", "price": 1.0},
        {"asin": "B002", "name": "Onion", "product_title": "O", "price": 2.0},
        {"asin": "B001", "name": "Zucchini again", "product_title": "Z", "price": 1.0},
    ]
    deduped = dedupe_by_asin(items)
    assert len(deduped) == 2
    assert deduped[0]["name"] == "Zucchini"
    assert {i["asin"] for i in deduped} == {"B001", "B002"}


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    async def count(self):
        return 1 if self.selector in self.page.visible_selectors else 0

    async def is_visible(self):
        return self.selector in self.page.visible_selectors

    async def click(self, timeout=10_000):
        if self.selector not in self.page.visible_selectors:
            raise TimeoutError(f"{self.selector} not clickable")
        self.page.clicked.append(self.selector)


class FakePage:
    def __init__(self, visible_selectors):
        self.visible_selectors = visible_selectors
        self.clicked = []

    async def wait_for_selector(self, combined, timeout=15_000):
        if not any(sel in self.visible_selectors for sel in ADD_TO_CART_SELECTORS):
            raise TimeoutError("no add-to-cart selector appeared")

    def locator(self, selector):
        return FakeLocator(self, selector)


@pytest.mark.parametrize("visible,expected", [
    (["#add-to-cart-button-grocery"], "#add-to-cart-button-grocery"),
    (["#add-to-cart-button"], "#add-to-cart-button"),
    (["#add-to-cart-button-grocery", "#add-to-cart-button"], "#add-to-cart-button-grocery"),
])
def test_whole_foods_selector_takes_priority(visible, expected):
    page = FakePage(visible)
    asyncio.run(_click_add_to_cart(page))
    assert page.clicked == [expected]


def test_missing_add_to_cart_raises_clear_error():
    page = FakePage([])
    with pytest.raises(TimeoutError):
        asyncio.run(_click_add_to_cart(page))
