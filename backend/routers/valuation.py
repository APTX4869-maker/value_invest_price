from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..db import connect, dumps, loads, now_iso
from ..dependencies import get_facts_or_404
from ..schemas import SnapshotRequest, ValuationRequest
from ..valuation import run_valuation


router = APIRouter(prefix="/api", tags=["valuation"])


@router.post("/valuation/run")
def valuation(payload: ValuationRequest) -> dict[str, Any]:
    facts = get_facts_or_404(payload.ticker)
    return run_valuation(facts, payload.assumptions)


@router.post("/valuation/snapshot")
def save_snapshot(payload: SnapshotRequest) -> dict[str, Any]:
    ts = now_iso()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO valuation_snapshots (ticker, title, inputs_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payload.ticker.upper(), payload.title, dumps(payload.inputs), dumps(payload.result), ts),
        )
        snapshot_id = cursor.lastrowid
    return {"id": snapshot_id, "created_at": ts}


@router.get("/snapshots/{ticker}")
def snapshots(ticker: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM valuation_snapshots WHERE ticker = ? ORDER BY created_at DESC",
            (ticker.upper(),),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "ticker": row["ticker"],
            "title": row["title"],
            "inputs": loads(row["inputs_json"], {}),
            "result": loads(row["result_json"], {}),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
