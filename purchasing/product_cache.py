"""On-disk cache for Amazon product search results."""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

DEFAULT_CACHE_PATH = "data/product_cache.json"
DEFAULT_TTL_DAYS = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProductCache:
    def __init__(self, path: str = DEFAULT_CACHE_PATH, ttl_days: int = DEFAULT_TTL_DAYS):
        self._path = pathlib.Path(path)
        self._ttl_days = ttl_days
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._data = {}
            return
        try:
            self._data = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))

    def _is_fresh(self, entry: dict) -> bool:
        cached_at = entry.get("cached_at")
        if not cached_at:
            return False
        try:
            saved = datetime.fromisoformat(cached_at)
            if saved.tzinfo is None:
                saved = saved.replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        age = _utcnow() - saved
        return age.days < self._ttl_days

    def get_candidates(self, ingredient_key: str) -> list[dict] | None:
        entry = self._data.get(ingredient_key)
        if not entry or not self._is_fresh(entry):
            return None
        return entry.get("candidates")

    def set_candidates(self, ingredient_key: str, candidates: list[dict]) -> None:
        self._data[ingredient_key] = {
            "cached_at": _utcnow().isoformat(),
            "candidates": candidates,
        }
        self._save()

    def wrap_search(self, search_fn, normalize_key):
        """Return a search function that reads/writes the cache."""

        def cached_search(name: str) -> list[dict]:
            key = normalize_key(name)
            hit = self.get_candidates(key)
            if hit is not None:
                return hit
            results = search_fn(name)[:3]
            self.set_candidates(key, results)
            return results

        return cached_search
