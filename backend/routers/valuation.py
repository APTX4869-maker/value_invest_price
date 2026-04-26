from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..db import connect, dumps, loads, now_iso
from ..dependencies import get_facts_or_404
from ..schemas import SnapshotRequest, ValuationCalculatorRequest, ValuationRequest
from ..valuation import run_target_price_calculator, run_valuation


router = APIRouter(prefix="/api", tags=["valuation"])


@router.post("/valuation/run")
def valuation(payload: ValuationRequest) -> dict[str, Any]:
    facts = get_facts_or_404(payload.ticker)
    result = run_valuation(facts, payload.assumptions)
    save_valuation_run(payload.ticker, "legacy_run", facts, {"assumptions": payload.assumptions}, result)
    return result


@router.post("/valuation/target")
def target_price_calculator(payload: ValuationCalculatorRequest) -> dict[str, Any]:
    facts = get_facts_or_404(payload.ticker)
    result = run_target_price_calculator(facts, payload)
    save_valuation_run(payload.ticker, "target_price", facts, payload.model_dump(), result)
    return result


def save_valuation_run(ticker: str, run_type: str, facts: dict[str, Any], inputs: dict[str, Any], result: dict[str, Any]) -> None:
    target = result.get("target_price", {})
    confidence = result.get("confidence", {})
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO valuation_runs
            (ticker, run_type, price_at_run, target_bear, target_base, target_bull,
             upside_base, confidence_score, inputs_json, outputs_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker.upper(),
                run_type,
                facts.get("price"),
                target.get("bear"),
                target.get("base"),
                target.get("bull"),
                target.get("upside_base"),
                confidence.get("score") if isinstance(confidence, dict) else None,
                dumps(inputs),
                dumps(result),
                now_iso(),
            ),
        )


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
