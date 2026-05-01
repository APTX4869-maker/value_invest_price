from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..db import connect, dumps, loads, now_iso, row_to_dict
from ..dependencies import get_facts_or_404
from ..schemas import ConsensusEstimates, SnapshotRequest, ValuationCalculatorRequest, ValuationRequest
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


@router.get("/valuation/consensus/{ticker}")
def get_consensus_estimates(ticker: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM consensus_estimates WHERE ticker = ?", (ticker.upper(),)).fetchone()
    return row_to_dict(row)


@router.put("/valuation/consensus/{ticker}")
def save_consensus_estimates(ticker: str, payload: ConsensusEstimates) -> dict[str, Any]:
    ts = payload.updated_at or now_iso()
    raw = {"source": payload.source, "updated_at": ts}
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO consensus_estimates
            (ticker, fiscal_year, revenue_next_year, revenue_2y, eps_next_year, eps_2y,
             ebitda_next_year, operating_income_next_year, fcf_next_year,
             long_term_eps_growth, source, updated_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                fiscal_year = excluded.fiscal_year,
                revenue_next_year = excluded.revenue_next_year,
                revenue_2y = excluded.revenue_2y,
                eps_next_year = excluded.eps_next_year,
                eps_2y = excluded.eps_2y,
                ebitda_next_year = excluded.ebitda_next_year,
                operating_income_next_year = excluded.operating_income_next_year,
                fcf_next_year = excluded.fcf_next_year,
                long_term_eps_growth = excluded.long_term_eps_growth,
                source = excluded.source,
                updated_at = excluded.updated_at,
                raw_json = excluded.raw_json
            """,
            (
                ticker.upper(),
                None,
                payload.revenue_next_year,
                payload.revenue_2y,
                payload.eps_next_year,
                payload.eps_2y,
                payload.ebitda_next_year,
                payload.operating_income_next_year,
                payload.fcf_next_year,
                payload.long_term_eps_growth,
                payload.source,
                ts,
                dumps(raw),
            ),
        )
    saved = get_consensus_estimates(ticker)
    return saved or {"ticker": ticker.upper(), "updated_at": ts}


@router.delete("/valuation/consensus/{ticker}")
def delete_consensus_estimates(ticker: str) -> dict[str, Any]:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM consensus_estimates WHERE ticker = ?", (ticker.upper(),))
    return {"ticker": ticker.upper(), "deleted": cursor.rowcount > 0}


def save_valuation_run(ticker: str, run_type: str, facts: dict[str, Any], inputs: dict[str, Any], result: dict[str, Any]) -> None:
    target = result.get("target_price", {})
    confidence = result.get("confidence", {})
    ts = now_iso()
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
                ts,
            ),
        )
        multiples = result.get("multiples", {}).get("current", {})
        if multiples:
            conn.execute(
                """
                INSERT INTO valuation_multiples_history
                (ticker, date, price, market_cap, enterprise_value, pe_forward,
                 ev_sales, ev_ebitda, fcf_yield, ps_ratio, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker.upper(),
                    ts,
                    result.get("current_price") or facts.get("price"),
                    result.get("market_cap") or facts.get("market_cap"),
                    result.get("enterprise_value"),
                    multiples.get("forward_pe"),
                    multiples.get("ev_sales"),
                    multiples.get("ev_ebitda"),
                    multiples.get("fcf_yield"),
                    result.get("sanity_metrics", {}).get("price_to_sales"),
                    "valuation_run",
                    ts,
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
