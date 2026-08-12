from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _payload() -> dict[str, object]:
    figures = []
    for number, page in (
        ("5.6", 112),
        ("5.15", 126),
        ("5.16", 126),
        ("5.18", 128),
        ("5.22", 130),
        ("5.23", 131),
        ("5.41", 153),
    ):
        figures.append(
            {
                "number": number,
                "page": page,
                "bbox": [0.1, 0.1, 0.9, 0.5],
                "caption": f"Figure {number} reviewed caption.",
                "crop_sha256": "a" * 64,
                "evidence": f"Visually verified on PDF page {page}.",
            }
        )
    return {"schema_version": 1, "render_scale": 3, "figures": figures}


def test_loads_fixed_chapter_5_visual_policy(tmp_path: Path) -> None:
    from rtr4_learning.visual_enrichment import load_visual_enrichments

    path = tmp_path / "visual-enrichments.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")

    policy = load_visual_enrichments(path)

    assert [figure.number for figure in policy.figures] == [
        "5.6",
        "5.15",
        "5.16",
        "5.18",
        "5.22",
        "5.23",
        "5.41",
    ]
    assert [figure.page for figure in policy.figures] == [112, 126, 126, 128, 130, 131, 153]
    assert policy.render_scale == 3


def test_committed_chapter_5_visual_policy_is_source_reviewed() -> None:
    from rtr4_learning.visual_enrichment import load_visual_enrichments

    policy = load_visual_enrichments(
        REPO_ROOT / "content/rtr4-cn/chapter-05/visual-enrichments.json"
    )

    assert len(policy.figures) == 7
    assert all(figure.caption.startswith(f"图 {figure.number}：") for figure in policy.figures)
    assert all("RTR4-CN-v1.1.pdf" in figure.evidence for figure in policy.figures)


@pytest.mark.parametrize(
    "change",
    [
        lambda payload: payload.update(schema_version=2),
        lambda payload: payload["figures"].pop(),
        lambda payload: payload["figures"][0].update(page=111),
        lambda payload: payload["figures"][0].update(bbox=[0, 0, 1.1, 1]),
        lambda payload: payload["figures"][0].update(crop_sha256="bad"),
        lambda payload: payload["figures"][0].update(evidence=""),
    ],
)
def test_rejects_visual_policy_outside_fixed_contract(tmp_path: Path, change) -> None:
    from rtr4_learning.visual_enrichment import load_visual_enrichments

    payload = _payload()
    change(payload)
    path = tmp_path / "visual-enrichments.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises((ValueError, TypeError)):
        load_visual_enrichments(path)
