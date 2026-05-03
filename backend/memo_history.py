from __future__ import annotations

from typing import Any

from .db import dumps, loads, row_to_dict


def default_memo(ticker: str) -> dict[str, Any]:
    return {
        "ticker": ticker.upper(),
        "conclusion": "不确定",
        "attention_reason": "",
        "thesis": [],
        "business_moat": "",
        "financial_quality": "",
        "valuation_view": "",
        "bear_case": "",
        "review_triggers": [],
        "free_notes": "",
        "snapshot_id": None,
        "created_at": None,
        "updated_at": None,
    }


def serialize_memo(row: dict[str, Any] | None, ticker: str) -> dict[str, Any]:
    if not row:
        return default_memo(ticker)
    return {
        "ticker": row["ticker"],
        "conclusion": row.get("conclusion") or "不确定",
        "attention_reason": row.get("attention_reason") or "",
        "thesis": loads(row.get("thesis_json"), []),
        "business_moat": row.get("business_moat") or "",
        "financial_quality": row.get("financial_quality") or "",
        "valuation_view": row.get("valuation_view") or "",
        "bear_case": row.get("bear_case") or "",
        "review_triggers": loads(row.get("review_triggers_json"), []),
        "free_notes": row.get("free_notes") or "",
        "snapshot_id": row.get("snapshot_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def record_memo_version(conn, ticker: str, source: str, ts: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM investment_memos WHERE ticker = ?", (ticker.upper(),)).fetchone()
    if not row:
        return None
    memo = serialize_memo(row_to_dict(row), ticker)
    cursor = conn.execute(
        """
        INSERT INTO investment_memo_versions (ticker, source, memo_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (ticker.upper(), source, dumps(memo), ts),
    )
    return {
        "id": cursor.lastrowid,
        "ticker": ticker.upper(),
        "source": source,
        "memo": memo,
        "created_at": ts,
    }


def list_memo_versions(conn, ticker: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM investment_memo_versions
        WHERE ticker = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (ticker.upper(), limit),
    ).fetchall()
    versions = []
    for row in rows:
        item = row_to_dict(row)
        versions.append(
            {
                "id": item["id"],
                "ticker": item["ticker"],
                "source": item.get("source") or "manual",
                "memo": loads(item.get("memo_json"), {}),
                "created_at": item["created_at"],
            }
        )
    return versions
