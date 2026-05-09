from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from ..company_profiles import build_company_profile
from ..data_sources import (
    DataSourceNetworkError,
    DataSourceResponseError,
    UnsupportedTickerError,
    fetch_company_facts,
    search_tickers,
)
from ..db import connect, dumps, loads, now_iso, row_to_dict
from ..dependencies import get_company_or_404, get_facts_or_404, get_setting, serialize_company
from ..llm_research import LLMConfigError, LLMProviderError, generate_company_research_draft, list_research_drafts, update_research_draft
from ..peer_recommendations import (
    CORE_PEER_LIMIT,
    default_core_peer_tickers,
    external_peer_recommendations,
    recommend_peers,
    sanitize_peer_tickers,
)
from ..sec_filings import get_cached_research_package, list_company_filings, refresh_company_research_package
from ..schemas import PeersRequest, PriceOverrideRequest, ResearchDraftPatchRequest
from ..valuation import run_valuation
from ..valuation.assumptions import SPECIAL_PROFILES


router = APIRouter(prefix="/api", tags=["companies"])


def _valuation_ratio(result: dict[str, Any]) -> float | None:
    center = result.get("fair_value_center") or 0
    price = result.get("current_price") or 0
    return price / center if center else None


def _comparison_row(ticker: str, role: str = "peer") -> dict[str, Any]:
    ticker = ticker.upper()
    with connect() as conn:
        company_row = conn.execute("SELECT * FROM companies WHERE ticker = ?", (ticker,)).fetchone()
    company = row_to_dict(company_row)
    if not company:
        return {
            "ticker": ticker,
            "role": role,
            "status": "missing_company",
            "message": "还没有本地公司资料。点击刷新同行数据后，系统会尝试从免费数据源拉取。",
        }
    company = serialize_company(company)
    try:
        facts = get_facts_or_404(ticker)
        result = run_valuation(facts)
    except HTTPException:
        return {
            "ticker": ticker,
            "name": company.get("name", ticker),
            "role": role,
            "status": "missing_facts",
            "message": "还没有可用财务数据。点击刷新同行数据后再比较。",
        }

    ratio = _valuation_ratio(result)
    fcf_yield = result.get("yields", {}).get("fcf_yield")
    ocf_yield = result.get("yields", {}).get("ocf_yield")
    multiples_current = result.get("multiples", {}).get("current", {})
    quality = result.get("quality_breakdown", {})
    forward = result.get("forward_estimates", {})
    revenue_base = facts.get("revenue") or 0
    revenue_next = (forward.get("revenue_next_year") or {}).get("value") or revenue_base
    revenue_growth = (revenue_next / revenue_base - 1) if revenue_base else None
    fcf_margin = ((facts.get("ocf") or 0) - (facts.get("capex") or 0)) / revenue_base if revenue_base else None
    return {
        "ticker": ticker,
        "name": company.get("name", ticker),
        "role": role,
        "status": "ready",
        "industry": company.get("industry") or company.get("sector") or "",
        "company_type": result.get("company_type"),
        "judgement": result["judgement"],
        "quality_score": result["quality_score"],
        "confidence": result["confidence"],
        "current_price": result["current_price"],
        "fair_value_center": result["fair_value_center"],
        "fair_value_range": result["fair_value_range"],
        "price_to_fair": ratio,
        "value_gap": ratio - 1 if ratio is not None else None,
        "fcf_yield": fcf_yield,
        "ocf_yield": ocf_yield,
        "peer_forward_pe": multiples_current.get("forward_pe"),
        "peer_ev_sales": multiples_current.get("ev_sales"),
        "peer_ev_ebitda": multiples_current.get("ev_ebitda"),
        "peer_fcf_yield": multiples_current.get("fcf_yield"),
        "revenue_growth": revenue_growth,
        "operating_margin": quality.get("operating_margin"),
        "fcf_margin": fcf_margin,
        "rule_of_40": (revenue_growth or 0) + (fcf_margin or 0) if revenue_growth is not None else None,
        "reverse_growth": result.get("reverse_dcf", {}).get("implied_5y_growth"),
        "market_cap": result.get("market_cap"),
        "source": facts.get("source"),
        "updated_at": facts.get("updated_at"),
    }


def _save_peer_snapshot(ticker: str, peers: list[dict[str, Any]]) -> None:
    ready_peers = [item for item in peers if item.get("status") == "ready"]
    if not ready_peers:
        return
    ts = now_iso()
    with connect() as conn:
        conn.execute("DELETE FROM peer_valuation_snapshot WHERE ticker = ?", (ticker.upper(),))
        for peer in ready_peers:
            conn.execute(
                """
                INSERT INTO peer_valuation_snapshot
                (ticker, peer_ticker, date, peer_price, peer_market_cap, peer_ev_sales,
                 peer_ev_ebitda, peer_forward_pe, peer_fcf_yield, revenue_growth,
                 operating_margin, fcf_margin, rule_of_40, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker.upper(),
                    peer["ticker"].upper(),
                    ts,
                    peer.get("current_price"),
                    peer.get("market_cap"),
                    peer.get("peer_ev_sales"),
                    peer.get("peer_ev_ebitda"),
                    peer.get("peer_forward_pe"),
                    peer.get("peer_fcf_yield"),
                    peer.get("revenue_growth"),
                    peer.get("operating_margin"),
                    peer.get("fcf_margin"),
                    peer.get("rule_of_40"),
                    "local_peer_compare",
                    ts,
                ),
            )


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _financials_recently_refreshed(ticker: str, max_age_hours: int = 24) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT updated_at FROM financial_facts WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
    refreshed_at = _parse_timestamp(row["updated_at"] if row else None)
    if not refreshed_at:
        return False
    return datetime.now(timezone.utc) - refreshed_at <= timedelta(hours=max_age_hours)


def _peer_refresh_result(ticker: str, message: str, valuation: dict[str, Any] | None = None) -> dict[str, Any]:
    valuation = valuation or {}
    confidence = valuation.get("confidence")
    return {
        "ticker": ticker.upper(),
        "status": "ready",
        "message": message,
        "judgement": valuation.get("judgement"),
        "current_price": valuation.get("current_price"),
        "fair_value_center": valuation.get("fair_value_center"),
        "confidence_score": confidence.get("score") if isinstance(confidence, dict) else None,
    }


def _core_peers_for_company(ticker: str, peers: list[str] | None, persist: bool = False) -> list[str]:
    core_peers = sanitize_peer_tickers(ticker, peers)
    if persist and list(peers or []) != core_peers:
        with connect() as conn:
            conn.execute(
                "UPDATE companies SET peers_json = ?, updated_at = ? WHERE ticker = ?",
                (dumps(core_peers), now_iso(), ticker.upper()),
            )
    return core_peers


def _peer_summary(current: dict[str, Any], peers: list[dict[str, Any]]) -> dict[str, Any]:
    ready_peers = [item for item in peers if item.get("status") == "ready"]
    if current.get("status") != "ready":
        return {
            "headline": "当前公司还没有完整估值，先刷新公司数据。",
            "detail": "同行比较需要当前公司和至少一个同行都有财务数据。",
            "available_count": len(ready_peers),
        }
    if not ready_peers:
        return {
            "headline": "同行还没有可比较数据。",
            "detail": "先点击刷新同行数据，或把已经刷新过的公司加入同行列表。",
            "available_count": 0,
        }

    peer_ratios = [item["price_to_fair"] for item in ready_peers if item.get("price_to_fair") is not None]
    peer_quality = [item["quality_score"] for item in ready_peers if item.get("quality_score") is not None]
    peer_fcf = [item["fcf_yield"] for item in ready_peers if item.get("fcf_yield") is not None]
    avg_ratio = sum(peer_ratios) / len(peer_ratios) if peer_ratios else None
    avg_quality = sum(peer_quality) / len(peer_quality) if peer_quality else None
    avg_fcf_yield = sum(peer_fcf) / len(peer_fcf) if peer_fcf else None
    current_ratio = current.get("price_to_fair")
    current_quality = current.get("quality_score")
    if avg_ratio is None or current_ratio is None:
        relative = "数据不足"
    elif current_ratio > avg_ratio * 1.12:
        relative = "比同行更贵"
    elif current_ratio < avg_ratio * 0.88:
        relative = "比同行更便宜"
    else:
        relative = "与同行接近"

    quality_text = ""
    if avg_quality is not None and current_quality is not None:
        quality_text = "，质量分更高" if current_quality > avg_quality + 4 else "，质量分更低" if current_quality < avg_quality - 4 else "，质量分接近"
    return {
        "headline": f"{current['ticker']} 当前相对同行：{relative}{quality_text}。",
        "detail": "相对比较使用同一套 V2.0 估值口径，重点看价格/合理中枢、现金流收益率和质量分是否互相支持。",
        "available_count": len(ready_peers),
        "peer_average_price_to_fair": avg_ratio,
        "peer_average_quality_score": avg_quality,
        "peer_average_fcf_yield": avg_fcf_yield,
        "relative_label": relative,
    }


def _unsupported_ticker_help(error: Exception) -> str:
    return (
        "刷新失败："
        f"{error}。请确认输入的是上市公司普通股 ticker，而不是 ETF、基金、权证或拼写错误。"
        "例如 Palantir Technologies 的 ticker 是 PLTR；PLTA 是跟踪 PLTR 的杠杆 ETF，当前公司估值模型不支持 ETF。"
    )


def _network_help(error: Exception) -> str:
    return (
        "刷新失败："
        f"{error}。这通常是 SEC/Yahoo/FRED 免费数据源或本地网络的临时连接问题，"
        "不是估值算法错误，也不一定代表 ticker 输错。请稍后重试；如果连续失败，检查网络/代理、SEC User-Agent 设置，"
        "或在设置中配置 Alpha Vantage 作为行情兜底。"
    )


def _source_response_help(error: Exception) -> str:
    return (
        "刷新失败："
        f"{error}。免费数据源返回了不可用内容。可以稍后重试；如果同一个 ticker 长期失败，"
        "通常说明 SEC companyfacts 暂无可用公司财务标签，或该标的不适合当前公司估值模型。"
    )


def _save_fmp_consensus_if_safe(conn: Any, ticker: str, consensus: dict[str, Any] | None, ts: str) -> None:
    if not consensus:
        return
    existing = conn.execute("SELECT source FROM consensus_estimates WHERE ticker = ?", (ticker,)).fetchone()
    existing_source = str(existing["source"] or "") if existing else ""
    if existing_source and not existing_source.lower().startswith("fmp"):
        return
    conn.execute(
        """
        INSERT INTO consensus_estimates
        (ticker, fiscal_year, revenue_next_year, revenue_2y, eps_next_year, eps_2y,
         ebitda_next_year, operating_income_next_year, fcf_next_year, long_term_eps_growth,
         source, updated_at, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            fiscal_year = excluded.fiscal_year,
            revenue_next_year = excluded.revenue_next_year,
            revenue_2y = excluded.revenue_2y,
            eps_next_year = excluded.eps_next_year,
            eps_2y = excluded.eps_2y,
            ebitda_next_year = excluded.ebitda_next_year,
            operating_income_next_year = excluded.operating_income_next_year,
            source = excluded.source,
            updated_at = excluded.updated_at,
            raw_json = excluded.raw_json
        """,
        (
            ticker,
            consensus.get("fiscal_year"),
            consensus.get("revenue_next_year"),
            consensus.get("revenue_2y"),
            consensus.get("eps_next_year"),
            consensus.get("eps_2y"),
            consensus.get("ebitda_next_year"),
            consensus.get("operating_income_next_year"),
            consensus.get("source") or "FMP analyst estimates",
            ts,
            dumps(consensus.get("raw") or {}),
        ),
    )


@router.get("/tickers/search")
def ticker_search(q: str = "", limit: int = 8) -> list[dict[str, str]]:
    user_agent = get_setting("sec_user_agent", "personal-value-study contact@example.com")
    return search_tickers(q, user_agent, max(1, min(limit, 20)))


@router.post("/company/{ticker}/refresh")
def refresh_company(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper()
    user_agent = get_setting("sec_user_agent", "personal-value-study contact@example.com")
    fallback_yield = float(get_setting("default_ten_year_yield", 0.045))
    alpha_vantage_api_key = str(get_setting("alpha_vantage_api_key", "") or "")
    fred_api_key = str(get_setting("fred_api_key", "") or "")
    fmp_api_key = str(get_setting("fmp_api_key", "") or "")
    finnhub_api_key = str(get_setting("finnhub_api_key", "") or "")
    try:
        fetched = fetch_company_facts(
            ticker,
            user_agent,
            fallback_yield,
            alpha_vantage_api_key=alpha_vantage_api_key,
            fred_api_key=fred_api_key,
            fmp_api_key=fmp_api_key,
            finnhub_api_key=finnhub_api_key,
        )
    except UnsupportedTickerError as exc:
        raise HTTPException(status_code=404, detail=_unsupported_ticker_help(exc)) from exc
    except DataSourceNetworkError as exc:
        raise HTTPException(status_code=503, detail=_network_help(exc)) from exc
    except DataSourceResponseError as exc:
        raise HTTPException(status_code=502, detail=_source_response_help(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"刷新失败：{exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_source_response_help(exc)) from exc

    ts = now_iso()
    profile = build_company_profile(ticker, fetched.get("name") or ticker, fetched.get("sec_meta", {}))
    normalization = (fetched.get("raw_json") or {}).get("normalization") or {}
    profile_company_type = (
        "金融 / 金融科技"
        if normalization.get("statement_type") == "financial_services"
        else SPECIAL_PROFILES.get(ticker, {}).get("company_state", "稳定复利公司")
    )
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO companies
            (ticker, name, industry, sector, description, business_overview,
             company_type, segments_json, peers_json, profile_source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                name = excluded.name,
                industry = excluded.industry,
                sector = excluded.sector,
                description = excluded.description,
                business_overview = excluded.business_overview,
                company_type = excluded.company_type,
                segments_json = excluded.segments_json,
                profile_source = excluded.profile_source,
                updated_at = excluded.updated_at
            """,
            (
                ticker,
                fetched.get("name") or ticker,
                profile["industry"],
                profile["sector"],
                profile["description"],
                profile["business_overview"],
                profile_company_type,
                dumps(profile["segments"]),
                profile["profile_source"],
                ts,
                ts,
            ),
        )
        existing = conn.execute(
            "SELECT price, price_override FROM financial_facts WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        price = fetched.get("price") or (existing["price"] if existing else 0)
        shares = fetched.get("diluted_shares") or 0
        conn.execute(
            """
            INSERT INTO financial_facts
            (ticker, fiscal_year, revenue, operating_income, ocf, capex, sbc, cash,
             short_investments, debt_current, debt_long_term, diluted_shares, price,
             price_override, price_source, market_cap, ten_year_yield, ten_year_yield_source, source, updated_at, annual_history_json, raw_json)
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
        company_peer_row = conn.execute("SELECT peers_json FROM companies WHERE ticker = ?", (ticker,)).fetchone()
        existing_peers = []
        if company_peer_row:
            try:
                existing_peers = loads(company_peer_row["peers_json"], [])
            except Exception:
                existing_peers = []
        core_peer_tickers = default_core_peer_tickers(ticker, existing_peers)
        if core_peer_tickers != existing_peers:
            conn.execute(
                "UPDATE companies SET peers_json = ?, updated_at = ? WHERE ticker = ?",
                (dumps(core_peer_tickers), ts, ticker),
            )
        _save_fmp_consensus_if_safe(conn, ticker, ((fetched.get("raw_json") or {}).get("fmp") or {}).get("consensus"), ts)
    return get_company(ticker)


@router.get("/company/{ticker}")
def get_company(ticker: str) -> dict[str, Any]:
    company = get_company_or_404(ticker)
    facts = None
    valuation = None
    try:
        facts = get_facts_or_404(ticker)
        valuation = run_valuation(facts)
    except HTTPException:
        pass
    return {"company": company, "facts": facts, "valuation": valuation}


@router.get("/company/{ticker}/sec-filings")
def company_sec_filings(ticker: str, limit: int = 8) -> dict[str, Any]:
    user_agent = get_setting("sec_user_agent", "personal-value-study contact@example.com")
    try:
        return list_company_filings(ticker, user_agent, limit=max(1, min(int(limit), 20)))
    except UnsupportedTickerError as exc:
        raise HTTPException(status_code=404, detail=_unsupported_ticker_help(exc)) from exc
    except DataSourceNetworkError as exc:
        raise HTTPException(status_code=503, detail=_network_help(exc)) from exc
    except DataSourceResponseError as exc:
        raise HTTPException(status_code=502, detail=_source_response_help(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_source_response_help(exc)) from exc


@router.get("/company/{ticker}/research-package")
def company_research_package(ticker: str) -> dict[str, Any]:
    return get_cached_research_package(ticker)


@router.post("/company/{ticker}/research-package/refresh")
def refresh_research_package(ticker: str, limit: int = 2) -> dict[str, Any]:
    user_agent = get_setting("sec_user_agent", "personal-value-study contact@example.com")
    try:
        return refresh_company_research_package(ticker, user_agent, filings_limit=max(1, min(int(limit), 4)))
    except UnsupportedTickerError as exc:
        raise HTTPException(status_code=404, detail=_unsupported_ticker_help(exc)) from exc
    except DataSourceNetworkError as exc:
        raise HTTPException(status_code=503, detail=_network_help(exc)) from exc
    except DataSourceResponseError as exc:
        raise HTTPException(status_code=502, detail=_source_response_help(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_source_response_help(exc)) from exc


def _all_settings() -> dict[str, Any]:
    from ..db import loads

    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: loads(row["value"]) for row in rows}


@router.get("/company/{ticker}/research-drafts")
def company_research_drafts(ticker: str) -> list[dict[str, Any]]:
    return list_research_drafts(ticker)


@router.post("/company/{ticker}/sec-draft")
def generate_sec_research_draft(ticker: str) -> dict[str, Any]:
    package = get_cached_research_package(ticker)
    if not package.get("packages"):
        raise HTTPException(status_code=422, detail="还没有 SEC 研究包。请先刷新 SEC 研究包，再生成 AI 初稿。")
    try:
        return generate_company_research_draft(ticker, package["packages"], _all_settings())
    except LLMConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.patch("/company/{ticker}/research-drafts/{draft_id}")
def patch_research_draft(ticker: str, draft_id: int, payload: ResearchDraftPatchRequest) -> dict[str, Any]:
    try:
        return update_research_draft(ticker, draft_id, status=payload.status, draft=payload.draft)
    except LLMProviderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/company/{ticker}/peers")
def update_peers(ticker: str, payload: PeersRequest) -> dict[str, Any]:
    get_company_or_404(ticker)
    peers = sanitize_peer_tickers(ticker, payload.peers)
    with connect() as conn:
        conn.execute(
            "UPDATE companies SET peers_json = ?, updated_at = ? WHERE ticker = ?",
            (dumps(peers), now_iso(), ticker.upper()),
        )
        row = conn.execute("SELECT * FROM companies WHERE ticker = ?", (ticker.upper(),)).fetchone()
    return serialize_company(dict(row))


@router.get("/company/{ticker}/peers/compare")
def compare_peers(ticker: str) -> dict[str, Any]:
    company = get_company_or_404(ticker)
    current = _comparison_row(ticker, role="current")
    core_peers = _core_peers_for_company(ticker, company.get("peers", []), persist=True)
    peers = [_comparison_row(peer, role="peer") for peer in core_peers]
    _save_peer_snapshot(ticker, peers)
    return {
        "ticker": ticker.upper(),
        "current": current,
        "peers": peers,
        "summary": _peer_summary(current, peers),
        "peer_policy": {
            "core_peer_limit": CORE_PEER_LIMIT,
            "core_peers": core_peers,
            "note": "只有核心同行会刷新、保存快照并参与估值；外部数据源返回的同行只作为待确认候选。",
        },
        "updated_at": now_iso(),
    }


@router.post("/company/{ticker}/peers/refresh")
def refresh_peers(ticker: str) -> dict[str, Any]:
    company = get_company_or_404(ticker)
    results = []
    core_peers = _core_peers_for_company(ticker, company.get("peers", []), persist=True)
    for peer in core_peers:
        try:
            if _financials_recently_refreshed(peer):
                results.append(_peer_refresh_result(peer, "最近 24 小时已刷新，直接使用本地缓存。"))
                continue
            refreshed = refresh_company(peer)
            results.append(_peer_refresh_result(peer, "已刷新", refreshed.get("valuation")))
        except HTTPException as exc:
            results.append({
                "ticker": peer,
                "status": "error",
                "message": exc.detail,
            })
    return {
        "ticker": ticker.upper(),
        "results": results,
        "comparison": compare_peers(ticker),
    }


@router.put("/company/{ticker}/price-override")
def update_price_override(ticker: str, payload: PriceOverrideRequest) -> dict[str, Any]:
    get_company_or_404(ticker)
    with connect() as conn:
        row = conn.execute(
            "SELECT price, diluted_shares FROM financial_facts WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="还没有财务数据，请先刷新后再手动覆盖价格。")
        market_price = row["price"] or 0
        active_price = payload.price if payload.price is not None else market_price
        diluted_shares = row["diluted_shares"] or 0
        conn.execute(
            """
            UPDATE financial_facts
            SET price_override = ?, market_cap = ?, updated_at = ?
            WHERE ticker = ?
            """,
            (payload.price, active_price * diluted_shares if diluted_shares else 0, now_iso(), ticker.upper()),
        )
    return get_company(ticker)


@router.get("/company/{ticker}/peer-suggestions")
def peer_suggestions(ticker: str) -> list[dict[str, Any]]:
    company = get_company_or_404(ticker)
    existing = set(company.get("peers", []))
    suggestions = recommend_peers(company)
    seen = {company.get("ticker", ticker).upper()}
    seen.update(item["ticker"] for item in suggestions)
    try:
        facts = get_facts_or_404(ticker)
        raw_json = facts.get("raw") or {}
    except HTTPException:
        raw_json = {}
    suggestions.extend(external_peer_recommendations(raw_json, ticker, seen))
    return [{**item, "selected": item["ticker"] in existing} for item in suggestions[:16]]
