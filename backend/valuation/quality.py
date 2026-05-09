from __future__ import annotations

from typing import Any

from .models import Facts, clamp, safe_div


def calculate_quality_score(facts: Facts) -> tuple[float, dict[str, Any]]:
    op_margin = facts.operating_margin
    ocf_margin = safe_div(facts.ocf, facts.revenue)
    fcf_conversion = safe_div(facts.actual_fcf, facts.ocf)
    sbc_revenue = safe_div(facts.sbc, facts.revenue)
    capex_ocf = safe_div(facts.capex, facts.ocf)
    net_cash_market_cap = safe_div(facts.net_cash, facts.market_cap)
    fmp_normalized = (((facts.raw or {}).get("fmp") or {}).get("enrichment") or {}).get("normalized") or {}
    alpha_normalized = (((facts.raw or {}).get("alpha_vantage") or {}).get("enrichment") or {}).get("normalized") or {}
    finnhub_normalized = (((facts.raw or {}).get("finnhub") or {}).get("enrichment") or {}).get("normalized") or {}
    roic = fmp_normalized.get("roic")
    current_ratio = fmp_normalized.get("current_ratio") or finnhub_normalized.get("current_ratio")
    interest_coverage = fmp_normalized.get("interest_coverage")
    net_debt_to_ebitda = fmp_normalized.get("net_debt_to_ebitda")
    roe = fmp_normalized.get("roe") or alpha_normalized.get("roe_ttm") or finnhub_normalized.get("roe")

    score = 45.0
    score += clamp(op_margin / 0.35, 0, 1) * 16
    score += clamp(ocf_margin / 0.35, 0, 1) * 16
    score += clamp(fcf_conversion, 0, 1) * 14
    score += clamp(net_cash_market_cap / 0.08, -1, 1) * 5
    score -= clamp(sbc_revenue / 0.12, 0, 1) * 12
    score -= clamp(capex_ocf / 0.65, 0, 1) * 8
    if roic is not None:
        score += clamp(float(roic) / 0.18, -0.5, 1.0) * 6
    elif roe is not None:
        score += clamp(float(roe) / 0.20, -0.5, 1.0) * 4
    if current_ratio is not None:
        score += clamp((float(current_ratio) - 1.0) / 1.5, -0.5, 1.0) * 3
    if interest_coverage is not None:
        score += clamp(float(interest_coverage) / 12.0, -0.5, 1.0) * 3
    if net_debt_to_ebitda is not None and float(net_debt_to_ebitda) > 3.0:
        score -= clamp((float(net_debt_to_ebitda) - 3.0) / 3.0, 0, 1) * 5

    breakdown = {
        "operating_margin": op_margin,
        "ocf_margin": ocf_margin,
        "fcf_conversion": fcf_conversion,
        "sbc_to_revenue": sbc_revenue,
        "capex_to_ocf": capex_ocf,
        "net_cash_to_market_cap": net_cash_market_cap,
        "fmp_roic": roic,
        "external_roe": roe,
        "fmp_current_ratio": current_ratio,
        "fmp_interest_coverage": interest_coverage,
        "fmp_net_debt_to_ebitda": net_debt_to_ebitda,
        "plain_language": [
            "经营利润率和 OCF 利润率越高，说明商业模式质量更好。",
            "FCF 转化率越高，说明现金流更接近真实可分配价值。",
            "SBC 占收入越高、CAPEX 占 OCF 越高，品质分会被扣分。",
            "如果 FMP 提供 ROIC、流动性和利息覆盖倍数，系统会把它们作为财务质量增强项。",
        ],
    }
    return round(clamp(score, 35, 95), 1), breakdown


def build_data_quality(forward: dict[str, Any], warnings: list[str], facts: Facts) -> dict[str, Any]:
    system_estimates = [
        key for key, item in forward.items()
        if isinstance(item, dict) and item.get("source") == "system_estimate"
    ]
    missing = []
    for key in ["revenue", "operating_income", "ocf", "capex", "diluted_shares", "price"]:
        if getattr(facts, key, 0) in (0, None):
            missing.append(key)
    score = 85
    score -= min(16, len(system_estimates) * 2)
    score -= len(missing) * 12
    score -= min(8, len(warnings) * 2)
    raw_coverage = (facts.raw or {}).get("data_coverage") if isinstance(facts.raw, dict) else {}
    coverage_score = raw_coverage.get("score") if isinstance(raw_coverage, dict) else None
    if coverage_score is not None:
        score = (score * 0.72) + (float(coverage_score) * 0.28)
    output_warnings = list(warnings)
    if system_estimates:
        output_warnings.append("部分 forward 数据为系统估算，非市场共识。")
    if missing:
        output_warnings.append(f"缺少关键财务字段：{', '.join(missing)}。")
    if isinstance(raw_coverage, dict):
        output_warnings.extend(raw_coverage.get("warnings") or [])
    source_summary = {
        "financials": "SEC companyfacts / Alpha Vantage fallback / FMP fallback",
        "price": getattr(facts, "price_source", None) or "Yahoo / Alpha Vantage / Finnhub",
        "forward": "manual_consensus / db_consensus / FMP analyst estimates / system_estimate",
        "multiples": "peer_snapshot / Finnhub metrics / FMP key metrics / system_calculated",
    }
    return {
        "score": int(clamp(score, 20, 95)),
        "level": "high" if score >= 75 else "medium" if score >= 55 else "low",
        "system_estimates": system_estimates,
        "missing_fields": missing,
        "warnings": output_warnings,
        "data_coverage": raw_coverage or {},
        "api_usage": (facts.raw or {}).get("api_usage", {}) if isinstance(facts.raw, dict) else {},
        "source_summary": source_summary,
    }
