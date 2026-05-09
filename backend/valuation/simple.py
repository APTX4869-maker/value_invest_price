from __future__ import annotations

from typing import Any

from .models import Facts, clamp, safe_div


DEFAULT_SIMPLE_DCF_GROWTHS = [0.07, 0.09, 0.11, 0.13, 0.15]


def _recent_average_fcf(facts: Facts) -> float:
    values = [
        float(row.get("ocf") or 0) - abs(float(row.get("capex") or 0))
        for row in facts.annual_history[-5:]
        if row.get("ocf")
    ]
    values = [value for value in values if value > 0]
    return sum(values) / len(values) if values else 0.0


def run_simple_fcf_dcf(facts: Facts, manual_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Excel-style FCF DCF cross-check, not a weighted target-price model."""
    manual_overrides = manual_overrides or {}
    manual_fcf = manual_overrides.get("simple_dcf_fcf")
    avg_fcf = _recent_average_fcf(facts)
    actual_fcf = facts.actual_fcf
    if manual_fcf not in (None, ""):
        anchor_fcf = max(0.0, float(manual_fcf))
        anchor_method = "manual_simple_dcf_fcf"
    elif actual_fcf > 0:
        anchor_fcf = actual_fcf
        anchor_method = "latest_actual_fcf"
    else:
        anchor_fcf = avg_fcf
        anchor_method = "recent_average_fcf"

    raw_growths = manual_overrides.get("simple_dcf_growths") or DEFAULT_SIMPLE_DCF_GROWTHS
    growths = [clamp(float(value), -0.20, 0.40) for value in list(raw_growths)[:5]]
    while len(growths) < 5:
        growths.append(DEFAULT_SIMPLE_DCF_GROWTHS[len(growths)])
    growths = sorted(growths)
    discount_rate = clamp(float(manual_overrides.get("simple_dcf_discount_rate") or 0.15), 0.04, 0.30)
    exit_haircut = clamp(float(manual_overrides.get("simple_dcf_exit_multiple_haircut") or 0.95), 0.50, 1.20)

    first_year_fcf = anchor_fcf * (1 + growths[0])
    exit_multiple = safe_div(facts.market_cap, first_year_fcf)
    scenarios = []
    values = []
    for growth in growths:
        fcf = anchor_fcf
        pv_cash_flows = 0.0
        cash_flows = []
        for year in range(1, 11):
            fcf *= 1 + growth
            pv = fcf / ((1 + discount_rate) ** year)
            pv_cash_flows += pv
            cash_flows.append({"year": year, "fcf": fcf, "pv": pv})
        terminal_value = fcf * exit_multiple * exit_haircut
        terminal_pv = terminal_value / ((1 + discount_rate) ** 10)
        equity_value = pv_cash_flows + terminal_pv
        per_share = safe_div(equity_value, facts.diluted_shares)
        values.append(per_share)
        scenarios.append({
            "growth": growth,
            "per_share": per_share,
            "pv_cash_flows": pv_cash_flows,
            "terminal_value": terminal_value,
            "terminal_pv": terminal_pv,
            "terminal_dependency": safe_div(terminal_pv, equity_value),
            "cash_flows": cash_flows,
        })

    base = sum(values) / len(values) if values else 0.0
    return {
        "label": "Excel 口径简化 FCF DCF",
        "method": "excel_style_fcf_exit_multiple_dcf",
        "anchor_fcf": anchor_fcf,
        "anchor_method": anchor_method,
        "recent_average_fcf": avg_fcf,
        "actual_fcf": actual_fcf,
        "growths": growths,
        "discount_rate": discount_rate,
        "exit_multiple": exit_multiple,
        "exit_multiple_haircut": exit_haircut,
        "range_low": min(values) if values else 0.0,
        "base": base,
        "range_high": max(values) if values else 0.0,
        "upside_base": safe_div(base - facts.price, facts.price),
        "scenarios": scenarios,
        "warning": "该模型用当前市场 FCF 倍数做退出价值，适合作为 Excel 口径交叉校验，不应单独作为最终目标价。",
    }
