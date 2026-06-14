"""Tests for cart deduplication and Whole Foods–only add to cart."""

import asyncio

import pytest

from purchasing.cart_builder import dedupe_by_asin
from purchasing.wholefoods import WF_ADD_TO_CART_SELECTOR, WHOLE_FOODS_NOT_FOUND
from purchasing import cart_builder as cb


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

    async def wait_for(self, state="visible", timeout=15_000):
        if self.selector not in self.page.visible_selectors:
            raise TimeoutError(f"{self.selector} not visible")

    async def click(self, timeout=10_000):
        if self.selector not in self.page.visible_selectors:
            raise TimeoutError(f"{self.selector} not clickable")
        self.page.clicked.append(self.selector)


class FakePage:
    def __init__(self, visible_selectors):
        self.visible_selectors = visible_selectors
        self.clicked = []

    def locator(self, selector):
        return FakeLocator(self, selector)


def test_whole_foods_grocery_button_is_used():
    page = FakePage([WF_ADD_TO_CART_SELECTOR])
    asyncio.run(cb._click_add_to_cart_whole_foods(page))
    assert page.clicked == [WF_ADD_TO_CART_SELECTOR]


def test_regular_amazon_button_is_not_used():
    page = FakePage(["#add-to-cart-button"])
    with pytest.raises(RuntimeError, match=WHOLE_FOODS_NOT_FOUND):
        asyncio.run(cb._click_add_to_cart_whole_foods(page))
    assert page.clicked == []
