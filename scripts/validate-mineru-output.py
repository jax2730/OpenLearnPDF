from __future__ import annotations

import json
import sys
from pathlib import Path

ASSET_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".svg"}


def inspect_output(root: Path) -> dict[str, int | None]:
    markdown = list(root.rglob("*.md"))
    json_files = [path for path in root.rglob("*.json") if path.name != "probe.json"]
    assets = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in ASSET_SUFFIXES
    ]
    content_v2 = list(root.rglob("*_content_list_v2.json"))
    page_count = None
    nonempty_page_count = 0
    block_count = 0
    equation_block_count = 0
    image_block_count = 0
    referenced_assets: list[Path] = []
    if len(content_v2) == 1:
        payload = json.loads(content_v2[0].read_text(encoding="utf-8"))
        if isinstance(payload, list):
            page_count = len(payload)
            for page in payload:
                if not isinstance(page, list):
                    continue
                blocks = [block for block in page if isinstance(block, dict)]
                if blocks:
                    nonempty_page_count += 1
                block_count += len(blocks)
                for block in blocks:
                    block_type = block.get("type")
                    equation_block_count += block_type == "equation_interline"
                    image_block_count += block_type == "image"
                    content = block.get("content")
                    if not isinstance(content, dict):
                        continue
                    image_source = content.get("image_source")
                    if isinstance(image_source, dict) and isinstance(
                        image_source.get("path"), str
                    ):
                        referenced_assets.append(content_v2[0].parent / image_source["path"])
    return {
        "asset_count": len(assets),
        "asset_nonempty_count": sum(path.stat().st_size > 0 for path in assets),
        "block_count": block_count,
        "content_v2_count": len(content_v2),
        "equation_block_count": equation_block_count,
        "image_block_count": image_block_count,
        "json_count": len(json_files),
        "markdown_count": len(markdown),
        "markdown_nonempty_count": sum(
            bool(path.read_text(encoding="utf-8").strip()) for path in markdown
        ),
        "missing_referenced_asset_count": sum(
            not path.is_file() or path.stat().st_size == 0 for path in referenced_assets
        ),
        "nonempty_page_count": nonempty_page_count,
        "page_count": page_count,
        "referenced_asset_count": len(referenced_assets),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate-mineru-output.py OUTPUT_DIR", file=sys.stderr)
        return 2
    print(json.dumps(inspect_output(Path(sys.argv[1])), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
