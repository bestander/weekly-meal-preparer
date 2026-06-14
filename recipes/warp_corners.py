#!/usr/bin/env python3
"""Perspective-warp an image given four corner points (JSON on stdin).

Input JSON:
  {"input": "/path/to/source.jpg", "output": "/path/to/out.jpg", "corners": [[x,y], ...]}

Corners are in pixel coords: top-left, top-right, bottom-right, bottom-left.
"""

from __future__ import annotations

import json
import sys

import cv2
import numpy as np


def order_points(pts: np.ndarray) -> np.ndarray:
    pts = np.array(pts, dtype="float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    return np.array(
        [
            pts[np.argmin(s)],
            pts[np.argmin(diff)],
            pts[np.argmax(s)],
            pts[np.argmax(diff)],
        ],
        dtype="float32",
    )


def warp_image(img: np.ndarray, corners: list) -> np.ndarray:
    pts = order_points(np.array(corners, dtype="float32"))
    tl, tr, br, bl = pts
    max_w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    max_h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    dst = np.array(
        [[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(img, matrix, (max_w, max_h))


def main() -> None:
    data = json.load(sys.stdin)
    img = cv2.imread(data["input"])
    if img is None:
        print(f"Could not read {data['input']}", file=sys.stderr)
        sys.exit(1)
    result = warp_image(img, data["corners"])
    cv2.imwrite(data["output"], result, [cv2.IMWRITE_JPEG_QUALITY, 92])


if __name__ == "__main__":
    main()
