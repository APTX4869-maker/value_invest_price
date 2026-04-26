from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .db import connect, loads, row_to_dict


def get_setting(key: str, default: Any) -> Any:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return loads(row["value"], default) if row else default


def serialize_company(row: dict[str, Any]) -> dict[str, Any]:
    row["peers"] = loads(row.pop("peers_json", "[]"), [])
    row["segments"] = loads(row.pop("segments_json", "[]"), [])
    return row


def get_company_or_404(ticker: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM companies WHERE ticker = ?", (ticker.upper(),)).fetchone()
    company = row_to_dict(row)
    if not company:
        raise HTTPException(status_code=404, detail="公司不在观察池里")
    return serialize_company(company)


def get_facts_or_404(ticker: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM financial_facts WHERE ticker = ?", (ticker.upper(),)).fetchone()
    facts = row_to_dict(row)
    if not facts:
        raise HTTPException(status_code=404, detail="还没有财务数据，请先刷新或手动添加示例")
    facts["market_price"] = facts.get("price")
    facts["market_price_source"] = facts.get("price_source") or facts.get("source") or "未注明"
    facts["price_is_overridden"] = facts.get("price_override") is not None
    facts["active_price_source"] = "手动覆盖价格" if facts["price_is_overridden"] else facts["market_price_source"]
    facts["ten_year_yield_source"] = facts.get("ten_year_yield_source") or "本地默认值"
    if facts["price_is_overridden"]:
        facts["price"] = facts["price_override"]
    facts["annual_history"] = loads(facts.pop("annual_history_json", "[]"), [])
    facts["raw"] = loads(facts.pop("raw_json", "{}"), {})
    return facts


def build_default_note(ticker: str) -> dict[str, Any]:
    return {
        "ticker": ticker.upper(),
        "content": "## 我为什么看这家公司？\n\n\n## 当前价格在赌什么？\n\n\n## 我最可能错在哪里？\n\n",
        "updated_at": None,
    }
