"""Reproduce reviewed visual-enrichment crops outside the Git worktree."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from PIL import Image

from rtr4_learning.stages.render import render_pages
from rtr4_learning.visual_enrichment import load_visual_enrichments


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-id", default="rtr4-cn")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--review-name", default="chapter-05-visuals-final")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy = load_visual_enrichments(args.policy)
    result = render_pages(
        book_id=args.book_id,
        pages=tuple(sorted({figure.page for figure in policy.figures})),
        scale=policy.render_scale,
        data_root=args.data_root,
    )
    review_root = (args.data_root / "review" / args.review_name).resolve()
    data_root = args.data_root.resolve()
    if data_root not in review_root.parents:
        raise ValueError("review output must remain below data_root/review")
    review_root.mkdir(parents=True, exist_ok=True)

    matched = True
    for figure in policy.figures:
        with Image.open(result.output_dir / "pages" / f"p{figure.page}.png") as page:
            width, height = page.size
            crop = page.crop(
                (
                    round(figure.bbox.x0 * width),
                    round(figure.bbox.y0 * height),
                    round(figure.bbox.x1 * width),
                    round(figure.bbox.y1 * height),
                )
            )
            output = review_root / f"figure-{figure.number}.png"
            crop.save(output, format="PNG")
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        status = "OK" if digest == figure.crop_sha256 else "MISMATCH"
        print(f"{figure.number} page={figure.page} pixels={crop.size[0]}x{crop.size[1]} sha256={digest} {status}")
        if status != "OK":
            matched = False
    return 0 if matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
