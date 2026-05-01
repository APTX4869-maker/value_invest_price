from __future__ import annotations

from statistics import median
from typing import Any

from .db import connect, dumps, loads, now_iso, row_to_dict
from .dependencies import get_setting
from .data_sources import fetch_company_facts, fetch_qqq_holdings
from .valuation import run_target_price_calculator


MOAT_BY_TYPE = {
    "platform_compounder": (86, "平台生态、网络效应或分发入口通常更强，护城河评分较高。"),
    "high_growth_profitable_tech": (78, "盈利型高成长科技公司通常有产品、规模或技术壁垒，但需要继续验证周期性。"),
    "high_growth_software": (74, "软件/数据平台有较好的扩展性，护城河取决于客户粘性和替换成本。"),
    "memory_semiconductor": (64, "存储半导体在 HBM 等高端产品上可能有技术壁垒，但价格和产能周期会削弱稳定性。"),
    "mature_compounder": (76, "成熟复利型公司通常有品牌、渠道或生态优势。"),
    "consumer_staples": (72, "消费稳定型公司护城河主要来自品牌、渠道和定价权。"),
    "cyclical": (56, "周期类公司的护城河更容易被价格周期和产能周期冲淡。"),
    "financial": (58, "金融类公司护城河要看资金成本、风控和监管牌照，当前版本只能做粗略判断。"),
    "unprofitable_growth": (48, "未盈利成长公司需要用客户留存、单位经济和现金消耗验证护城河。"),
    "default": (60, "公司画像不足，先按普通经营公司处理，护城河结论需要人工补充。"),
}

COMPETITION_BY_TYPE = {
    "platform_compounder": (44, "平台公司也会面对监管、AI 入口变化和生态竞争，但规模优势能缓冲一部分压力。"),
    "high_growth_profitable_tech": (58, "高成长科技行业竞争强，估值对技术路线和需求周期变化敏感。"),
    "high_growth_software": (62, "软件行业竞争和产品替代风险较高，需要看客户留存和净收入扩张。"),
    "memory_semiconductor": (78, "存储半导体竞争和供需周期都很强，需要防止用景气峰值利润外推。"),
    "mature_compounder": (42, "成熟复利行业竞争较可控，但增长放缓会压缩估值倍数。"),
    "consumer_staples": (36, "消费稳定行业竞争相对温和，主要关注品牌力和成本传导。"),
    "cyclical": (70, "周期行业竞争和供需波动都强，不能只看单年利润。"),
    "financial": (66, "金融公司竞争来自资金成本、信用周期和监管变化。"),
    "unprofitable_growth": (72, "未盈利成长行业竞争激烈，融资环境和现金消耗会放大风险。"),
    "default": (55, "行业竞争信息不足，按中等竞争强度处理。"),
}


def save_etf_holdings(payload: dict[str, Any]) -> None:
    ts = now_iso()
    with connect() as conn:
        conn.execute("DELETE FROM etf_holdings WHERE etf = ?", (payload["etf"],))
        for item in payload["holdings"]:
            conn.execute(
                """
                INSERT INTO etf_holdings
                (etf, ticker, name, rank, weight, security_type, as_of, source, raw_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["etf"],
                    item["ticker"],
                    item["name"],
                    item["rank"],
                    item["weight"],
                    item.get("security_type", ""),
                    payload.get("as_of", ""),
                    payload.get("source", ""),
                    dumps(item.get("raw", {})),
                    ts,
                ),
            )


def refresh_qqq_holdings_cache(limit: int | None = None) -> dict[str, Any]:
    user_agent = get_setting("sec_user_agent", "personal-value-study contact@example.com")
    payload = fetch_qqq_holdings(user_agent)
    save_etf_holdings(payload)
    if limit:
        payload = {**payload, "holdings": payload["holdings"][:limit]}
    return payload


def get_cached_qqq_holdings(limit: int = 30) -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM etf_holdings WHERE etf = 'QQQ' ORDER BY rank ASC LIMIT ?",
            (limit,),
        ).fetchall()
        meta = conn.execute("SELECT as_of, source, updated_at FROM etf_holdings WHERE etf = 'QQQ' ORDER BY updated_at DESC LIMIT 1").fetchone()
    holdings = []
    for row in rows:
        item = row_to_dict(row)
        item["raw"] = loads(item.pop("raw_json", "{}"), {})
        holdings.append(item)
    return {
        "etf": "QQQ",
        "as_of": meta["as_of"] if meta else None,
        "source": meta["source"] if meta else "未缓存",
        "updated_at": meta["updated_at"] if meta else None,
        "holdings": holdings,
    }


def ensure_qqq_holdings(limit: int = 30, refresh: bool = False) -> dict[str, Any]:
    cached = get_cached_qqq_holdings(limit)
    if refresh or not cached["holdings"]:
        return refresh_qqq_holdings_cache(limit)
    return cached


def _save_financial_facts(ticker: str, fetched: dict[str, Any], fallback_yield: float) -> None:
    ts = now_iso()
    with connect() as conn:
        existing = conn.execute(
            "SELECT price, price_override FROM financial_facts WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        price = fetched.get("price") or (existing["price"] if existing else 0) or 0
        shares = fetched.get("diluted_shares") or 0
        conn.execute(
            """
            INSERT INTO financial_facts
            (ticker, fiscal_year, revenue, operating_income, ocf, capex, sbc, cash,
             short_investments, debt_current, debt_long_term, diluted_shares, price,
             price_override, price_source, market_cap, ten_year_yield, ten_year_yield_source,
             source, updated_at, annual_history_json, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                fiscal_year = excluded.fiscal_year,
                revenue = excluded.revenue,
                operating_income = excluded.operating_income,
                ocf = excluded.ocf,
                capex = excluded.capex,
                sbc = excluded.sbc,
                cash = excluded.cash,
                short_investments = excluded.short_investments,
                debt_current = excluded.debt_current,
                debt_long_term = excluded.debt_long_term,
                diluted_shares = excluded.diluted_shares,
                price = excluded.price,
                price_source = excluded.price_source,
                market_cap = excluded.market_cap,
                ten_year_yield = excluded.ten_year_yield,
                ten_year_yield_source = excluded.ten_year_yield_source,
                source = excluded.source,
                updated_at = excluded.updated_at,
                annual_history_json = excluded.annual_history_json,
                raw_json = excluded.raw_json
            """,
            (
                ticker,
                fetched.get("fiscal_year"),
                fetched.get("revenue") or 0,
                fetched.get("operating_income") or 0,
                fetched.get("ocf") or 0,
                fetched.get("capex") or 0,
                fetched.get("sbc") or 0,
                fetched.get("cash") or 0,
                fetched.get("short_investments") or 0,
                fetched.get("debt_current") or 0,
                fetched.get("debt_long_term") or 0,
                shares,
                price,
                existing["price_override"] if existing else None,
                fetched.get("price_source") or "未获取到行情",
                price * shares if price and shares else 0,
                fetched.get("ten_year_yield") or fallback_yield,
                fetched.get("ten_year_yield_source") or "本地默认值",
                fetched.get("source") or "SEC",
                ts,
                dumps(fetched.get("annual_history", [])),
                dumps(fetched.get("raw_json", {})),
            ),
        )


def refresh_discovery_financials(ticker: str) -> None:
    ticker = ticker.upper()
    user_agent = get_setting("sec_user_agent", "personal-value-study contact@example.com")
    fallback_yield = float(get_setting("default_ten_year_yield", 0.045))
    alpha_vantage_api_key = str(get_setting("alpha_vantage_api_key", "") or "")
    fred_api_key = str(get_setting("fred_api_key", "") or "")
    fetched = fetch_company_facts(
        ticker,
        user_agent,
        fallback_yield,
        alpha_vantage_api_key=alpha_vantage_api_key,
        fred_api_key=fred_api_key,
    )
    _save_financial_facts(ticker, fetched, fallback_yield)


def _facts_for_ticker(ticker: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM financial_facts WHERE ticker = ?", (ticker.upper(),)).fetchone()
    facts = row_to_dict(row)
    if not facts:
        return None
    facts["market_price"] = facts.get("price")
    if facts.get("price_override") is not None:
        facts["price"] = facts["price_override"]
    facts["annual_history"] = loads(facts.pop("annual_history_json", "[]"), [])
    facts["raw"] = loads(facts.pop("raw_json", "{}"), {})
    return facts


def _history_revenue_cagr(history: list[dict[str, Any]]) -> float | None:
    rows = [row for row in history if row.get("revenue")]
    if len(rows) < 2:
        return None
    rows = sorted(rows, key=lambda row: row.get("fiscal_year") or 0)
    first, last = rows[0], rows[-1]
    years = max(1, (last.get("fiscal_year") or len(rows)) - (first.get("fiscal_year") or 1))
    if first["revenue"] <= 0:
        return None
    return (last["revenue"] / first["revenue"]) ** (1 / years) - 1


def _score_financials(facts: dict[str, Any], result: dict[str, Any]) -> tuple[int, list[str]]:
    quality = result.get("quality_breakdown", {})
    op_margin = quality.get("operating_margin") or 0
    fcf_margin = result.get("cash_flows", {}).get("actual_fcf", 0) / facts["revenue"] if facts.get("revenue") else 0
    net_cash_ratio = quality.get("net_cash_to_market_cap") or 0
    sbc_ratio = quality.get("sbc_to_revenue") or 0
    growth = _history_revenue_cagr(facts.get("annual_history") or [])
    score = 45
    score += min(22, max(0, op_margin) / 0.35 * 22)
    score += min(18, max(0, fcf_margin) / 0.25 * 18)
    score += min(12, max(0, growth or 0) / 0.15 * 12)
    score += min(8, max(-0.05, net_cash_ratio) / 0.10 * 8)
    score -= min(14, max(0, sbc_ratio) / 0.12 * 14)
    notes = [
        f"经营利润率约 {op_margin * 100:.1f}%，FCF margin 约 {fcf_margin * 100:.1f}%。",
        f"SBC 占收入约 {sbc_ratio * 100:.1f}%，净现金/市值约 {net_cash_ratio * 100:.1f}%。",
    ]
    if growth is not None:
        notes.append(f"历史收入年化增长约 {growth * 100:.1f}%。")
    return int(max(20, min(95, round(score)))), notes


def _score_moat(result: dict[str, Any], facts: dict[str, Any], holding: dict[str, Any]) -> tuple[int, list[str]]:
    company_type = result.get("company_type", "default")
    base, note = MOAT_BY_TYPE.get(company_type, MOAT_BY_TYPE["default"])
    weight = holding.get("weight") or 0
    quality_score = result.get("quality_score") or 50
    score = base + min(6, weight * 80) + max(-8, min(8, (quality_score - 60) / 5))
    notes = [note]
    if weight >= 0.03:
        notes.append("QQQ 权重较高，说明它在指数里的规模和流动性地位靠前。")
    if quality_score >= 72:
        notes.append("质量分较高，财务表现对护城河判断有支撑。")
    return int(max(20, min(95, round(score)))), notes


def _score_competition(result: dict[str, Any]) -> tuple[int, list[str]]:
    company_type = result.get("company_type", "default")
    score, note = COMPETITION_BY_TYPE.get(company_type, COMPETITION_BY_TYPE["default"])
    reverse = result.get("reverse_expectations", {})
    notes = [note]
    if reverse.get("difficulty") in {"aggressive", "very_aggressive"}:
        score += 8
        notes.append("当前价格隐含的增长/利润率要求偏高，行业竞争一旦加剧会放大估值压力。")
    return int(max(20, min(95, round(score)))), notes


def _confidence_rank(confidence: dict[str, Any]) -> int:
    return {"high": 4, "medium_high": 3, "medium": 2, "low": 1}.get(confidence.get("level"), 0)


def _unique_text(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item and item not in seen:
            output.append(item)
            seen.add(item)
    return output


def _label_for_row(upside: float, confidence: dict[str, Any], quality_score: float, model_spread: float) -> str:
    if confidence.get("score", 0) < 45:
        return "数据待确认"
    if model_spread > 1.0:
        return "估值分歧大"
    if upside >= 0.15 and quality_score >= 58:
        return "重点研究"
    if upside >= 0.05:
        return "可能低估"
    if upside <= -0.10 and quality_score >= 70:
        return "等待回调"
    return "继续观察"


def score_discovery_row(holding: dict[str, Any], facts: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    target = result.get("target_price", {})
    current_price = result.get("current_price") or 0
    target_base = target.get("base") or 0
    upside = (target_base - current_price) / current_price if current_price else 0
    confidence = result.get("confidence", {})
    model_bases = [model.get("base") for model in result.get("model_outputs", []) if model.get("base") and model.get("weight", 0) > 0]
    model_spread = ((max(model_bases) - min(model_bases)) / median(model_bases)) if len(model_bases) >= 2 and median(model_bases) else 0
    moat_score, moat_notes = _score_moat(result, facts, holding)
    financial_score, financial_notes = _score_financials(facts, result)
    competition_score, competition_notes = _score_competition(result)
    quality_score = result.get("quality_score") or 0
    label = _label_for_row(upside, confidence, quality_score, model_spread)
    confidence_rank = _confidence_rank(confidence)
    discovery_score = (
        confidence_rank * 1000
        + max(0, upside) * 180
        + quality_score * 0.9
        + moat_score * 0.45
        + financial_score * 0.35
        - competition_score * 0.25
        - model_spread * 18
    )
    summary = (
        f"{label}：置信度 {confidence.get('score', 0)}/100，"
        f"目标中枢相对现价 {upside * 100:+.1f}%，护城河 {moat_score}/100，财务 {financial_score}/100。"
    )
    valuation_notes = [
        f"当前价约 {current_price:.2f}，目标中枢约 {target_base:.2f}，区间约 {target.get('bear', 0):.2f} - {target.get('bull', 0):.2f}。",
        f"可用模型分歧度约 {model_spread * 100:.1f}%，分歧越高越需要手动复核假设。",
    ]
    data_notes = _unique_text(list(confidence.get("reasons") or []) + list(result.get("data_quality", {}).get("warnings") or []))
    return {
        "ticker": holding["ticker"],
        "name": holding.get("name", holding["ticker"]),
        "holding_rank": holding.get("rank"),
        "qqq_weight": holding.get("weight", 0),
        "status": "ready",
        "label": label,
        "rank_score": discovery_score,
        "confidence_rank": confidence_rank,
        "undervaluation": upside,
        "current_price": current_price,
        "target_price": target,
        "confidence": confidence,
        "quality_score": quality_score,
        "moat_score": moat_score,
        "financial_score": financial_score,
        "competition_risk_score": competition_score,
        "company_type": result.get("company_type"),
        "summary": summary,
        "reasons": {
            "valuation": valuation_notes,
            "moat": moat_notes,
            "financials": financial_notes,
            "competition": competition_notes,
            "data_quality": data_notes or ["暂无额外数据质量警告。"],
        },
    }


def scan_qqq_candidates(limit: int = 30, refresh_holdings: bool = False, refresh_financials: bool = False) -> dict[str, Any]:
    holdings_payload = ensure_qqq_holdings(limit, refresh_holdings)
    holdings = holdings_payload["holdings"][:limit]
    refreshed = []
    errors = []
    if refresh_financials:
        for holding in holdings:
            try:
                refresh_discovery_financials(holding["ticker"])
                refreshed.append(holding["ticker"])
            except Exception as exc:
                errors.append({"ticker": holding["ticker"], "message": str(exc)})

    rows = []
    for holding in holdings:
        facts = _facts_for_ticker(holding["ticker"])
        if not facts:
            rows.append({
                "ticker": holding["ticker"],
                "name": holding.get("name", holding["ticker"]),
                "holding_rank": holding.get("rank"),
                "qqq_weight": holding.get("weight", 0),
                "status": "missing_facts",
                "label": "数据不足",
                "summary": "还没有本地财务数据。点击刷新前 30 后，系统会从 SEC 和行情源补齐。",
                "reasons": {
                    "data_quality": ["缺少本地财务缓存，无法运行估值体系。"],
                    "valuation": [],
                    "moat": [],
                    "financials": [],
                    "competition": [],
                },
                "confidence": {"score": 0, "level": "low"},
                "undervaluation": None,
                "rank_score": -1,
                "confidence_rank": 0,
            })
            continue
        try:
            result = run_target_price_calculator(facts)
            rows.append(score_discovery_row(holding, facts, result))
        except Exception as exc:
            rows.append({
                "ticker": holding["ticker"],
                "name": holding.get("name", holding["ticker"]),
                "holding_rank": holding.get("rank"),
                "qqq_weight": holding.get("weight", 0),
                "status": "error",
                "label": "估值失败",
                "summary": f"估值计算失败：{exc}",
                "reasons": {"data_quality": [str(exc)], "valuation": [], "moat": [], "financials": [], "competition": []},
                "confidence": {"score": 0, "level": "low"},
                "undervaluation": None,
                "rank_score": -2,
                "confidence_rank": 0,
            })

    rows.sort(key=lambda row: (row.get("confidence_rank", 0), row.get("undervaluation") or -9, row.get("rank_score", 0)), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["discovery_rank"] = index
    ready_rows = [row for row in rows if row.get("status") == "ready"]
    return {
        "universe": "QQQ",
        "limit": limit,
        "as_of": holdings_payload.get("as_of"),
        "source": holdings_payload.get("source"),
        "updated_at": holdings_payload.get("updated_at"),
        "refreshed": refreshed,
        "errors": errors,
        "summary": {
            "total": len(rows),
            "ready": len(ready_rows),
            "focus": len([row for row in ready_rows if row.get("label") == "重点研究"]),
            "missing": len([row for row in rows if row.get("status") != "ready"]),
        },
        "rows": rows,
    }
