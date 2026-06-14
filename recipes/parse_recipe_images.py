#!/usr/bin/env python3
"""Pair recipe card images for parsing.

Recipe cards are photographed in order: ingredients page, then instructions page.
Images are named {recipe-slug}-ingredients.jpg and {recipe-slug}-instructions.jpg.

Run from the repo root:

    python3 recipes/parse_recipe_images.py pairs
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


IMAGES_DIR = pathlib.Path(__file__).parent / "images"


def pair_images() -> list[tuple[pathlib.Path, pathlib.Path]]:
    ingredients = sorted(IMAGES_DIR.glob("*-ingredients.jpg"), key=lambda p: p.stem)
    pairs: list[tuple[pathlib.Path, pathlib.Path]] = []
    for ing in ingredients:
        slug = ing.stem[: -len("-ingredients")]
        inst = IMAGES_DIR / f"{slug}-instructions.jpg"
        if not inst.exists():
            print(f"Warning: missing instructions image for {slug}", file=sys.stderr)
            continue
        pairs.append((ing, inst))

    if not pairs:
        # Fallback for legacy IMG_*.jpg filenames.
        jpgs = sorted(IMAGES_DIR.glob("*.jpg"), key=lambda p: p.stem)
        if len(jpgs) % 2:
            print(f"Warning: odd number of images ({len(jpgs)}); last image has no pair", file=sys.stderr)
        for i in range(0, len(jpgs) - len(jpgs) % 2, 2):
            pairs.append((jpgs[i], jpgs[i + 1]))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    pairs_parser = sub.add_parser("pairs", help="List ingredient/instruction image pairs")
    pairs_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    pairs = pair_images()
    if args.json:
        payload = [
            {"ingredients": str(a), "instructions": str(b)} for a, b in pairs
        ]
        print(json.dumps(payload, indent=2))
        return

    for i, (ing, inst) in enumerate(pairs, 1):
        print(f"{i:2}. {ing.name}  +  {inst.name}")


if __name__ == "__main__":
    main()
