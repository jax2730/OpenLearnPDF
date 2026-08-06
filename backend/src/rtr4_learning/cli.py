"""Command-line entry points for local pipeline stages."""

import argparse
from collections.abc import Sequence

from rtr4_learning.stages.register import register_book


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rtr4-learning")
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register", help="register a source PDF")
    register.add_argument("--book-id", required=True)
    register.add_argument("--pdf", required=True)
    register.add_argument("--chapter", required=True)
    register.add_argument("--data-root", required=True)
    register.add_argument("--title")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "register":
            register_book(
                book_id=args.book_id,
                pdf_path=args.pdf,
                chapter=args.chapter,
                data_root=args.data_root,
                title=args.title,
            )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
