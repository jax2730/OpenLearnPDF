"""Command-line entry points for local pipeline stages."""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from rtr4_learning.ingest import ingest_mineru_slice
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
    ingest = commands.add_parser(
        "ingest-mineru", help="normalize and index a MinerU content-list-v2 slice"
    )
    ingest.add_argument("--book-id", required=True)
    ingest.add_argument("--content-list", required=True)
    ingest.add_argument("--first-page", required=True, type=int)
    ingest.add_argument("--chapter", required=True, type=int)
    ingest.add_argument("--parser-version", required=True)
    ingest.add_argument("--data-root", required=True)
    ingest.add_argument("--formula-corrections")
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
        elif args.command == "ingest-mineru":
            result = ingest_mineru_slice(
                data_root=args.data_root,
                book_id=args.book_id,
                content_list=args.content_list,
                first_page=args.first_page,
                parser_version=args.parser_version,
                chapter=args.chapter,
                formula_corrections=args.formula_corrections,
            )
            print(
                f"ingested {len(result.pages)} pages "
                f"{result.normalized_path} {result.index_path}"
            )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
