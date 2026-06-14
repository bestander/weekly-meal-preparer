"""Tests for on-disk product search cache."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from purchasing.product_cache import ProductCache


def test_cache_hit_within_ttl(tmp_path):
    path = tmp_path / "cache.json"
    cache = ProductCache(str(path), ttl_days=3)
    cache.set_candidates("garlic", [{"asin": "B1", "title": "Garlic", "price": 1.0}])

    loaded = ProductCache(str(path), ttl_days=3)
    assert loaded.get_candidates("garlic") == [{"asin": "B1", "title": "Garlic", "price": 1.0}]


def test_cache_miss_after_ttl(tmp_path):
    path = tmp_path / "cache.json"
    stale = {
        "garlic": {
            "cached_at": (datetime.now(timezone.utc) - timedelta(days=4)).isoformat(),
            "candidates": [{"asin": "B1", "title": "Garlic", "price": 1.0}],
        }
    }
    path.write_text(json.dumps(stale))

    cache = ProductCache(str(path), ttl_days=3)
    assert cache.get_candidates("garlic") is None


def test_wrap_search_caches_results(tmp_path):
    path = tmp_path / "cache.json"
    cache = ProductCache(str(path), ttl_days=3)
    calls = {"n": 0}

    def raw(_name):
        calls["n"] += 1
        return [{"asin": "B1", "title": "Spinach", "price": 3.0}]

    search = cache.wrap_search(raw, lambda n: n.lower())
    assert search("Baby Spinach")[0]["asin"] == "B1"
    assert search("Baby Spinach")[0]["asin"] == "B1"
    assert calls["n"] == 1
