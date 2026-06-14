#!/usr/bin/env python3
"""Rename recipe card images to match recipe names from the week JSON."""

from __future__ import annotations

import json
import pathlib
import re
import sys
import unicodedata


IMAGES_DIR = pathlib.Path(__file__).parent / "images"
WEEK_JSON = pathlib.Path(__file__).parent / "week-2026-06-16.json"


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("&", "and").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def list_legacy_images() -> list[pathlib.Path]:
    return sorted(IMAGES_DIR.glob("*.jpg"), key=lambda p: p.stem)


def rename_images(week_path: pathlib.Path = WEEK_JSON) -> list[tuple[str, str, str]]:
    meals = json.loads(week_path.read_text())["meals"]
    images = list_legacy_images()
    expected = len(meals) * 2
    if len(images) != expected:
        raise SystemExit(
            f"Expected {expected} images for {len(meals)} meals, found {len(images)}"
        )

    planned: list[tuple[pathlib.Path, pathlib.Path]] = []
    used_slugs: set[str] = set()
    for meal, ing_src, inst_src in zip(meals, images[::2], images[1::2]):
        base = slugify(meal["name"])
        if base in used_slugs:
            raise SystemExit(f"Duplicate slug: {base}")
        used_slugs.add(base)
        planned.append((ing_src, IMAGES_DIR / f"{base}-ingredients.jpg"))
        planned.append((inst_src, IMAGES_DIR / f"{base}-instructions.jpg"))

    # Two-phase rename avoids collisions when sources and targets overlap.
    temp: list[tuple[pathlib.Path, pathlib.Path, pathlib.Path]] = []
    for i, (src, dst) in enumerate(planned):
        if src == dst:
            continue
        tmp = IMAGES_DIR / f".rename-tmp-{i:03d}.jpg"
        src.rename(tmp)
        temp.append((tmp, dst, src))

    for tmp, dst, _src in temp:
        tmp.rename(dst)

    return [
        (src.name, dst.name, "ingredients" if dst.name.endswith("-ingredients.jpg") else "instructions")
        for src, dst in planned
        if src != dst
    ]


def main() -> None:
    week_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WEEK_JSON
    changes = rename_images(week_path)
    print(f"Renamed {len(changes)} files using {week_path.name}")
    for old, new, kind in changes:
        print(f"  {old} -> {new}")


if __name__ == "__main__":
    main()
