from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..db import connect, dumps, now_iso, row_to_dict
from ..dependencies import build_default_note
from ..memo_history import list_memo_versions, record_memo_version, serialize_memo
from ..schemas import InvestmentMemoRequest, NoteRequest


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


@router.get("/{ticker}/memo")
def get_memo(ticker: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM investment_memos WHERE ticker = ?", (ticker.upper(),)).fetchone()
    return serialize_memo(row_to_dict(row), ticker)


@router.get("/{ticker}/memo/history")
def get_memo_history(ticker: str) -> list[dict[str, Any]]:
    with connect() as conn:
        versions = list_memo_versions(conn, ticker)
    return versions


@router.put("/{ticker}/memo")
def put_memo(ticker: str, payload: InvestmentMemoRequest) -> dict[str, Any]:
    ts = now_iso()
    with connect() as conn:
        existing = conn.execute("SELECT created_at FROM investment_memos WHERE ticker = ?", (ticker.upper(),)).fetchone()
        conn.execute(
            """
            INSERT INTO investment_memos
            (ticker, conclusion, attention_reason, thesis_json, business_moat,
             financial_quality, valuation_view, bear_case, review_triggers_json,
             free_notes, snapshot_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                conclusion = excluded.conclusion,
                attention_reason = excluded.attention_reason,
                thesis_json = excluded.thesis_json,
                business_moat = excluded.business_moat,
                financial_quality = excluded.financial_quality,
                valuation_view = excluded.valuation_view,
                bear_case = excluded.bear_case,
                review_triggers_json = excluded.review_triggers_json,
                free_notes = excluded.free_notes,
                snapshot_id = excluded.snapshot_id,
                updated_at = excluded.updated_at
            """,
            (
                ticker.upper(),
                payload.conclusion,
                payload.attention_reason,
                dumps(payload.thesis),
                payload.business_moat,
                payload.financial_quality,
                payload.valuation_view,
                payload.bear_case,
                dumps(payload.review_triggers),
                payload.free_notes,
                payload.snapshot_id,
                existing["created_at"] if existing else ts,
                ts,
            ),
        )
        record_memo_version(conn, ticker, "manual", ts)
        row = conn.execute("SELECT * FROM investment_memos WHERE ticker = ?", (ticker.upper(),)).fetchone()
    return serialize_memo(row_to_dict(row), ticker)
