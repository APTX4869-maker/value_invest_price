from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..db import connect, now_iso
from ..dependencies import get_facts_or_404, serialize_company
from ..schemas import AddCompanyRequest
from ..valuation import run_valuation


router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def _delete_company_records(ticker: str, purge: bool = False) -> dict[str, Any]:
    ticker = ticker.upper()
    with connect() as conn:
        row = conn.execute("SELECT ticker FROM companies WHERE ticker = ?", (ticker,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="研究队列里没有这个 ticker")
        conn.execute("DELETE FROM companies WHERE ticker = ?", (ticker,))
        conn.execute("DELETE FROM financial_facts WHERE ticker = ?", (ticker,))
        conn.execute("DELETE FROM research_queue WHERE ticker = ?", (ticker,))
        if purge:
            conn.execute("DELETE FROM notes WHERE ticker = ?", (ticker,))
            conn.execute("DELETE FROM investment_memos WHERE ticker = ?", (ticker,))
            conn.execute("DELETE FROM valuation_snapshots WHERE ticker = ?", (ticker,))
            conn.execute("DELETE FROM consensus_estimates WHERE ticker = ?", (ticker,))
            conn.execute("DELETE FROM valuation_multiples_history WHERE ticker = ?", (ticker,))
            conn.execute("DELETE FROM peer_valuation_snapshot WHERE ticker = ? OR peer_ticker = ?", (ticker, ticker))
            conn.execute("DELETE FROM valuation_runs WHERE ticker = ?", (ticker,))
    if purge:
        return {
            "ticker": ticker,
            "deleted": True,
            "purged": True,
            "message": "已彻底删除该公司，本地财务缓存、研究笔记和历史快照都已清除。",
        }
    return {
        "ticker": ticker,
        "deleted": True,
        "purged": False,
        "message": "已从研究队列移除，并清除本地财务缓存；研究笔记和历史快照仍保留。",
    }


@router.get("")
def watchlist() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*, f.price, f.market_cap, f.updated_at AS facts_updated_at
            FROM companies c
            LEFT JOIN financial_facts f ON f.ticker = c.ticker
            ORDER BY c.ticker
            """
        ).fetchall()
    output = []
    for row in rows:
        item = serialize_company(dict(row))
        try:
            facts = get_facts_or_404(item["ticker"])
            result = run_valuation(facts)
            item["valuation"] = {
                "judgement": result["judgement"],
                "quality_score": result["quality_score"],
                "confidence": result["confidence"],
                "fair_value_center": result["fair_value_center"],
                "fair_value_range": result["fair_value_range"],
                "current_price": result["current_price"],
            }
        except HTTPException:
            item["valuation"] = None
        output.append(item)
    return output


@router.post("")
def add_company(payload: AddCompanyRequest) -> dict[str, Any]:
    ticker = payload.ticker.upper()
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO companies
            (ticker, name, industry, sector, description, business_overview,
             company_type, segments_json, peers_json, profile_source, created_at, updated_at)
            VALUES (?, ?, '', '', '', '', '稳定复利公司', '[]', '[]', '', ?, ?)
            """,
            (ticker, payload.name or ticker, ts, ts),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO research_queue
            (ticker, status, tags_json, next_action, entry_reason, source, priority_score,
             discovery_label, ignored, created_at, updated_at)
            VALUES (?, 'candidate', '[]', ?, ?, 'manual_add', NULL, '手动添加', 0, ?, ?)
            """,
            (
                ticker,
                "刷新财务数据，确认这家公司是否值得进入初筛。",
                "手动加入研究队列。",
                ts,
                ts,
            ),
        )
        row = conn.execute("SELECT * FROM companies WHERE ticker = ?", (ticker,)).fetchone()
    return serialize_company(dict(row))


@router.delete("/{ticker}")
def delete_company_from_watchlist(ticker: str) -> dict[str, Any]:
    return _delete_company_records(ticker, purge=False)


@router.delete("/{ticker}/purge")
def purge_company_from_storage(ticker: str) -> dict[str, Any]:
    return _delete_company_records(ticker, purge=True)
