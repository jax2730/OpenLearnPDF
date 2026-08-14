"""Run the native pdf-inspector probe from an isolated Python environment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from rtr4_learning.pdf_inspector_probe import run_probe

DEFAULT_ANCHORS = {
    109: ("精确光源", "5.9"),
    111: ("平方反比", "5.11", "5.14"),
    113: ("聚光", "5.17", "5.18"),
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pages", nargs="+", required=True, type=int)
    return parser


def main() -> int:
    args = _parser().parse_args()
    requested_pages = tuple(args.pages)
    anchors = {page: DEFAULT_ANCHORS.get(page, ()) for page in requested_pages}
    report = run_probe(
        source_path=args.pdf,
        output_dir=args.output,
        requested_pages=requested_pages,
        expected_anchors=anchors,
    )
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
