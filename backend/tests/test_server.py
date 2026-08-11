import pytest

from rtr4_learning.server import create_environment_app


def test_environment_app_requires_explicit_local_roots(tmp_path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    content_root = tmp_path / "content"
    source_root = tmp_path / "sources"
    for path in (data_root, content_root, source_root):
        path.mkdir()
    monkeypatch.setenv("RTR4_DATA_ROOT", str(data_root))
    monkeypatch.setenv("RTR4_CONTENT_ROOT", str(content_root))
    monkeypatch.setenv("RTR4_SOURCE_ROOTS", str(source_root))

    app = create_environment_app()

    assert app.title == "RTR4 Learning API"


def test_environment_app_rejects_missing_configuration(monkeypatch) -> None:
    for name in ("RTR4_DATA_ROOT", "RTR4_CONTENT_ROOT", "RTR4_SOURCE_ROOTS"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match="RTR4_DATA_ROOT"):
        create_environment_app()
