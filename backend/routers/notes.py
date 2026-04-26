from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..db import connect, now_iso
from ..dependencies import build_default_note
from ..schemas import NoteRequest


router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("/{ticker}")
def get_note(ticker: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM notes WHERE ticker = ?", (ticker.upper(),)).fetchone()
    if not row:
        return build_default_note(ticker)
    return dict(row)


@router.put("/{ticker}")
def put_note(ticker: str, payload: NoteRequest) -> dict[str, Any]:
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO notes (ticker, content, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at
            """,
            (ticker.upper(), payload.content, ts),
        )
        row = conn.execute("SELECT * FROM notes WHERE ticker = ?", (ticker.upper(),)).fetchone()
    return dict(row)
