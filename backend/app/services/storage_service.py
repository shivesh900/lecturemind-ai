"""Configurable storage strategy. Default: local disk under STORAGE_DIR.

Files are stored under random names (never the user's filename), in a per-user
folder, and are never executed. To use S3/GCS, implement the same four methods.
"""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from ..core.config import get_settings


class LocalStorage:
    def __init__(self, root: str | None = None):
        self.root = Path(root or get_settings().storage_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "tmp").mkdir(exist_ok=True)

    def lecture_dir(self, user_id: str, lecture_id: str) -> Path:
        d = (self.root / "users" / str(user_id) / str(lecture_id)).resolve()
        if self.root not in d.parents:
            raise ValueError("Invalid storage path")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def new_tmp_path(self, suffix: str = "") -> Path:
        return self.root / "tmp" / f"{uuid.uuid4().hex}{suffix}"

    def resolve(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if self.root not in p.parents:
            raise ValueError("Invalid storage path")
        return p

    def relpath(self, p: Path) -> str:
        return str(Path(p).resolve().relative_to(self.root))

    def delete_lecture(self, user_id: str, lecture_id: str) -> None:
        d = self.root / "users" / str(user_id) / str(lecture_id)
        shutil.rmtree(d, ignore_errors=True)

    def delete_user(self, user_id: str) -> None:
        shutil.rmtree(self.root / "users" / str(user_id), ignore_errors=True)

    @staticmethod
    def remove_quietly(p: Path | str | None) -> None:
        if p:
            try:
                os.remove(p)
            except OSError:
                pass


_storage: LocalStorage | None = None


def get_storage() -> LocalStorage:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
