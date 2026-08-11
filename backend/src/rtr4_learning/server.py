"""Explicit environment-based Uvicorn application factory."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from rtr4_learning.api import create_app
from rtr4_learning.settings import Settings


def _required_path(name: str) -> Path:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be configured")
    path = Path(value).resolve()
    if not path.is_dir():
        raise RuntimeError(f"{name} directory does not exist: {path}")
    return path


def create_environment_app() -> FastAPI:
    data_root = _required_path("RTR4_DATA_ROOT")
    content_root = _required_path("RTR4_CONTENT_ROOT")
    source_value = os.environ.get("RTR4_SOURCE_ROOTS", "").strip()
    if not source_value:
        raise RuntimeError("RTR4_SOURCE_ROOTS must be configured")
    source_roots = tuple(
        Path(value).resolve()
        for value in source_value.split(os.pathsep)
        if value.strip()
    )
    if not source_roots or any(not path.is_dir() for path in source_roots):
        raise RuntimeError("RTR4_SOURCE_ROOTS must contain existing directories")
    dimensions = int(os.environ.get("RTR4_EMBEDDING_DIMENSIONS", "64"))
    return create_app(
        Settings(
            data_root=data_root,
            content_root=content_root,
            source_roots=source_roots,
            embedding_dimensions=dimensions,
        )
    )
