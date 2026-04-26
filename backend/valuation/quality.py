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

    score = 45.0
    score += clamp(op_margin / 0.35, 0, 1) * 16
    score += clamp(ocf_margin / 0.35, 0, 1) * 16
    score += clamp(fcf_conversion, 0, 1) * 14
    score += clamp(net_cash_market_cap / 0.08, -1, 1) * 5
    score -= clamp(sbc_revenue / 0.12, 0, 1) * 12
    score -= clamp(capex_ocf / 0.65, 0, 1) * 8

    breakdown = {
        "operating_margin": op_margin,
        "ocf_margin": ocf_margin,
        "fcf_conversion": fcf_conversion,
        "sbc_to_revenue": sbc_revenue,
        "capex_to_ocf": capex_ocf,
        "net_cash_to_market_cap": net_cash_market_cap,
        "plain_language": [
            "经营利润率和 OCF 利润率越高，说明商业模式质量更好。",
            "FCF 转化率越高，说明现金流更接近真实可分配价值。",
            "SBC 占收入越高、CAPEX 占 OCF 越高，品质分会被扣分。",
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
    output_warnings = list(warnings)
    if system_estimates:
        output_warnings.append("部分 forward 数据为系统估算，非市场共识。")
    if missing:
        output_warnings.append(f"缺少关键财务字段：{', '.join(missing)}。")
    return {
        "score": int(clamp(score, 20, 95)),
        "level": "high" if score >= 75 else "medium" if score >= 55 else "low",
        "system_estimates": system_estimates,
        "missing_fields": missing,
        "warnings": output_warnings,
        "source_summary": {
            "financials": "SEC companyfacts / local cache",
            "price": "Yahoo/override/local cache",
            "forward": "manual_consensus/db_consensus/system_estimate",
        },
    }
