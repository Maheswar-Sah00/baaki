"""Media storage behind a small interface.

LocalStorage keeps files under backend/data/media (gitignored). A cloud storage class with the
same four methods replaces it in production (Render's disk is wiped on restart). Keys are relative POSIX paths such as "c1/20261108T101500_ab12cd34.ogg".
"""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Protocol

from . import config


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> str: ...
    def get(self, key: str) -> bytes: ...
    def local_path(self, key: str) -> Path | None: ...  # None when the file is not on local disk
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or config.media_dir())

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("storage key escapes the media root")
        return p

    def put(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def local_path(self, key: str) -> Path | None:
        p = self._path(key)
        return p if p.exists() else None

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage


def set_storage(s: Storage | None) -> None:
    global _storage
    _storage = s


def new_key(case_id: int | None, ext: str) -> str:
    import datetime as dt

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"c{case_id or 0}/{stamp}_{secrets.token_hex(16)}.{ext.lstrip('.') or 'bin'}"
