from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..db import connect, dumps, loads, now_iso, row_to_dict
from ..dependencies import get_facts_or_404, serialize_company
from ..schemas import ResearchQueuePatchRequest, ResearchQueueRequest
from ..valuation import run_valuation


router = APIRouter(prefix="/api/research-queue", tags=["research_queue"])


QUEUE_STATUSES = {
    "candidate": "候选",
    "initial_review": "初筛通过",
    "deep_research": "深度研究中",
    "concluded": "已形成结论",
    "review": "复盘中",
}

STATUS_ORDER = {
    "candidate": 1,
    "initial_review": 2,
    "deep_research": 3,
    "concluded": 4,
    "review": 5,
}

DEFAULT_NEXT_ACTION = {
    "candidate": "先刷新财务数据，确认低估线索是否来自真实现金流和合理假设。",
    "initial_review": "补业务模式、护城河和主要竞争对手，判断是否进入深度研究。",
    "deep_research": "完善业务、财务质量、估值敏感性、同行比较和反证清单。",
    "concluded": "等待价格、财报或关键假设变化后复盘。",
    "review": "对照原 memo 和最新数据，判断结论是否需要更新。",
}


def _normalize_status(status: str | None) -> str:
    status = (status or "candidate").strip()
    return status if status in QUEUE_STATUSES else "candidate"


def _ensure_company(ticker: str, name: str | None = None) -> None:
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO companies
            (ticker, name, industry, sector, description, business_overview,
             company_type, segments_json, peers_json, profile_source, created_at, updated_at)
            VALUES (?, ?, '', '', '', '', '稳定复利公司', '[]', '[]', '', ?, ?)
            """,
            (ticker.upper(), name or ticker.upper(), ts, ts),
        )


def _valuation_brief(ticker: str) -> dict[str, Any] | None:
    try:
        facts = get_facts_or_404(ticker)
        result = run_valuation(facts)
        return {
            "judgement": result["judgement"],
            "quality_score": result["quality_score"],
            "confidence": result["confidence"],
            "fair_value_center": result["fair_value_center"],
            "fair_value_range": result["fair_value_range"],
            "current_price": result["current_price"],
        }
    except HTTPException:
        return None


def _serialize_queue_row(row: dict[str, Any]) -> dict[str, Any]:
    status = _normalize_status(row.get("status"))
    item = {
        "ticker": row["ticker"],
        "status": status,
        "status_label": QUEUE_STATUSES[status],
        "tags": loads(row.get("tags_json"), []),
        "next_action": row.get("next_action") or DEFAULT_NEXT_ACTION[status],
        "entry_reason": row.get("entry_reason") or "",
        "source": row.get("source") or "",
        "priority_score": row.get("priority_score"),
        "discovery_label": row.get("discovery_label") or "",
        "ignored": bool(row.get("ignored")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "company": None,
        "valuation": None,
    }
    company_fields = {key: row.get(key) for key in ["name", "industry", "sector", "description", "business_overview", "company_type", "segments_json", "peers_json", "profile_source", "created_at", "updated_at"]}
    if row.get("name"):
        item["company"] = serialize_company({"ticker": row["ticker"], **company_fields})
    item["valuation"] = _valuation_brief(row["ticker"])
    return item


@router.get("")
def list_research_queue(include_ignored: bool = False) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT q.*, c.name, c.industry, c.sector, c.description, c.business_overview,
                   c.company_type, c.segments_json, c.peers_json, c.profile_source
            FROM research_queue q
            LEFT JOIN companies c ON c.ticker = q.ticker
            WHERE (? = 1 OR q.ignored = 0)
            ORDER BY
                CASE q.status
                    WHEN 'candidate' THEN 1
                    WHEN 'initial_review' THEN 2
                    WHEN 'deep_research' THEN 3
                    WHEN 'concluded' THEN 4
                    WHEN 'review' THEN 5
                    ELSE 9
                END,
                COALESCE(q.priority_score, 0) DESC,
                q.updated_at DESC
            """,
            (1 if include_ignored else 0,),
        ).fetchall()
    return [_serialize_queue_row(row_to_dict(row)) for row in rows]


@router.post("")
def upsert_research_queue(payload: ResearchQueueRequest) -> dict[str, Any]:
    ticker = payload.ticker.upper()
    status = _normalize_status(payload.status)
    _ensure_company(ticker, payload.name)
    ts = now_iso()
    with connect() as conn:
        existing = conn.execute("SELECT * FROM research_queue WHERE ticker = ?", (ticker,)).fetchone()
        next_action = payload.next_action or DEFAULT_NEXT_ACTION[status]
        entry_reason = payload.entry_reason or (existing["entry_reason"] if existing else "")
        conn.execute(
            """
            INSERT INTO research_queue
            (ticker, status, tags_json, next_action, entry_reason, source, priority_score,
             discovery_label, ignored, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                status = excluded.status,
                tags_json = excluded.tags_json,
                next_action = excluded.next_action,
                entry_reason = excluded.entry_reason,
                source = excluded.source,
                priority_score = excluded.priority_score,
                discovery_label = excluded.discovery_label,
                ignored = 0,
                updated_at = excluded.updated_at
            """,
            (
                ticker,
                status,
                dumps(payload.tags),
                next_action,
                entry_reason,
                payload.source,
                payload.priority_score,
                payload.discovery_label,
                ts if not existing else existing["created_at"],
                ts,
            ),
        )
    return get_research_queue_item(ticker)


@router.get("/{ticker}")
def get_research_queue_item(ticker: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT q.*, c.name, c.industry, c.sector, c.description, c.business_overview,
                   c.company_type, c.segments_json, c.peers_json, c.profile_source
            FROM research_queue q
            LEFT JOIN companies c ON c.ticker = q.ticker
            WHERE q.ticker = ?
            """,
            (ticker.upper(),),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="研究队列里没有这个 ticker")
    return _serialize_queue_row(row_to_dict(row))


@router.patch("/{ticker}")
def patch_research_queue_item(ticker: str, payload: ResearchQueuePatchRequest) -> dict[str, Any]:
    current = get_research_queue_item(ticker)
    status = _normalize_status(payload.status or current["status"])
    tags = payload.tags if payload.tags is not None else current["tags"]
    next_action = payload.next_action if payload.next_action is not None else current["next_action"]
    entry_reason = payload.entry_reason if payload.entry_reason is not None else current["entry_reason"]
    priority_score = payload.priority_score if payload.priority_score is not None else current["priority_score"]
    discovery_label = payload.discovery_label if payload.discovery_label is not None else current["discovery_label"]
    ignored = current["ignored"] if payload.ignored is None else payload.ignored
    with connect() as conn:
        conn.execute(
            """
            UPDATE research_queue
            SET status = ?, tags_json = ?, next_action = ?, entry_reason = ?,
                priority_score = ?, discovery_label = ?, ignored = ?, updated_at = ?
            WHERE ticker = ?
            """,
            (
                status,
                dumps(tags),
                next_action,
                entry_reason,
                priority_score,
                discovery_label,
                1 if ignored else 0,
                now_iso(),
                ticker.upper(),
            ),
        )
    return get_research_queue_item(ticker)


@router.delete("/{ticker}")
def delete_research_queue_item(ticker: str) -> dict[str, Any]:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM research_queue WHERE ticker = ?", (ticker.upper(),))
    return {"ticker": ticker.upper(), "deleted": cursor.rowcount > 0}
