"""Command-line entry points for local pipeline stages."""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from rtr4_learning.stages.register import register_book
from rtr4_learning.stages.render import parse_page_selection, render_pages


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rtr4-learning")
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register", help="register a source PDF")
    register.add_argument("--book-id", required=True)
    register.add_argument("--pdf", required=True)
    register.add_argument("--chapter", required=True)
    register.add_argument("--data-root", required=True)
    register.add_argument("--title")
    render = commands.add_parser("render", help="render cited PDF pages")
    render.add_argument("--book-id", required=True)
    render.add_argument("--pages", required=True)
    render.add_argument("--scale", required=True, type=float)
    render.add_argument("--data-root", default=str(Path.cwd() / "data"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    logging.getLogger("pypdf").setLevel(logging.CRITICAL)
    try:
        if args.command == "register":
            register_book(
                book_id=args.book_id,
                pdf_path=args.pdf,
                chapter=args.chapter,
                data_root=args.data_root,
                title=args.title,
            )
        elif args.command == "render":
            result = render_pages(
                book_id=args.book_id,
                pages=parse_page_selection(args.pages),
                scale=args.scale,
                data_root=args.data_root,
            )
            status = "reused" if result.reused else "rendered"
            print(f"{status} {result.fingerprint} {result.output_dir}")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
