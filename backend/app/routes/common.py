from __future__ import annotations

from fastapi import HTTPException


def not_implemented(what: str) -> HTTPException:
    return HTTPException(status_code=501, detail={"error": "not_implemented", "what": what})
