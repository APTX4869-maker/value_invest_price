from __future__ import annotations

from typing import Any

from .dcf import run_three_stage_dcf
from .models import Facts, clamp, safe_div


def _difficulty(revenue_cagr: float, fcf_margin: float, ev_sales: float) -> str:
    points = 0
    if revenue_cagr > 0.18:
        points += 1
    if revenue_cagr > 0.28:
        points += 1
    if fcf_margin > 0.30:
        points += 1
    if ev_sales > 15:
        points += 1
    if points >= 4:
        return "very_aggressive"
    if points >= 2:
        return "aggressive"
    if points == 1:
        return "demanding"
    return "reasonable"


def reverse_dcf(facts: Facts, base_scenario: dict[str, float], capex_split: dict[str, Any]) -> dict[str, Any]:
    target = facts.price
    low, high = -0.05, 0.55
    scenario = dict(base_scenario)
    for _ in range(70):
        mid = (low + high) / 2
        scenario["revenue_cagr_5y"] = mid
        price = run_three_stage_dcf(facts, scenario, capex_split)["per_share"]
        if price < target:
            low = mid
        else:
            high = mid
    implied_growth = (low + high) / 2

    implied_fcf_margin = float(base_scenario["fcf_margin_terminal"])
    scenario = dict(base_scenario)
    scenario["revenue_cagr_5y"] = float(base_scenario["revenue_cagr_5y"])
    margin_low, margin_high = 0.02, 0.55
    for _ in range(60):
        mid = (margin_low + margin_high) / 2
        scenario["fcf_margin_terminal"] = mid
        price = run_three_stage_dcf(facts, scenario, capex_split)["per_share"]
        if price < target:
            margin_low = mid
        else:
            margin_high = mid
    implied_fcf_margin = (margin_low + margin_high) / 2
    implied_op_margin = max(float(base_scenario["operating_margin_terminal"]), implied_fcf_margin + 0.04)

    terminal_low, terminal_high = 0.0, min(0.05, float(base_scenario["discount_rate"]) - 0.01)
    scenario = dict(base_scenario)
    for _ in range(50):
        mid = (terminal_low + terminal_high) / 2
        scenario["terminal_growth"] = mid
        price = run_three_stage_dcf(facts, scenario, capex_split)["per_share"]
        if price < target:
            terminal_low = mid
        else:
            terminal_high = mid
    implied_terminal_growth = (terminal_low + terminal_high) / 2
    return {
        "implied_revenue_cagr_5y": implied_growth,
        "implied_terminal_fcf_margin": implied_fcf_margin,
        "implied_terminal_operating_margin": implied_op_margin,
        "implied_terminal_growth": implied_terminal_growth,
        "difficulty": _difficulty(implied_growth, implied_fcf_margin, safe_div(facts.enterprise_value, facts.revenue)),
        "plain_language": f"当前股价要求未来 5 年收入年化增长约 {implied_growth * 100:.1f}%，且终局 FCF margin 接近 {implied_fcf_margin * 100:.1f}%。",
    }


def reverse_multiples(facts: Facts, forward: dict[str, Any], multiples: dict[str, Any], peer_snapshot: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    eps = (forward.get("eps_next_year") or {}).get("value") or 0
    revenue = (forward.get("revenue_next_year") or {}).get("value") or facts.revenue
    ebitda = (forward.get("ebitda_next_year") or {}).get("value") or 0
    fcf = (forward.get("fcf_next_year") or {}).get("value") or facts.actual_fcf
    implied_forward_pe = safe_div(facts.price, eps)
    implied_ev_sales = safe_div(facts.enterprise_value, revenue)
    implied_ev_ebitda = safe_div(facts.enterprise_value, ebitda)
    implied_fcf_yield = safe_div(fcf, facts.market_cap)
    peer_ev_sales = [float(item["peer_ev_sales"]) for item in peer_snapshot or [] if item.get("peer_ev_sales")]
    peer_forward_pe = [float(item["peer_forward_pe"]) for item in peer_snapshot or [] if item.get("peer_forward_pe")]
    peer_median_ev_sales = sorted(peer_ev_sales)[len(peer_ev_sales) // 2] if peer_ev_sales else multiples["ev_sales"][1]
    peer_median_forward_pe = sorted(peer_forward_pe)[len(peer_forward_pe) // 2] if peer_forward_pe else multiples["pe"][1]
    pe_text = f"forward PE 约 {implied_forward_pe:.1f}x"
    sales_text = f"EV/Sales 约 {implied_ev_sales:.1f}x"
    if peer_median_forward_pe:
        pe_text += f"，同行中位数约 {peer_median_forward_pe:.1f}x"
    if peer_median_ev_sales:
        sales_text += f"，同行中位数约 {peer_median_ev_sales:.1f}x"
    return {
        "implied_forward_pe": implied_forward_pe,
        "implied_ev_sales": implied_ev_sales,
        "implied_ev_ebitda": implied_ev_ebitda,
        "implied_fcf_yield": implied_fcf_yield,
        "peer_median_ev_sales": peer_median_ev_sales,
        "peer_median_forward_pe": peer_median_forward_pe,
        "percentiles": multiples.get("percentiles", {}),
        "plain_language": f"当前股价对应 {pe_text}；{sales_text}。",
        "is_above_peer_ev_sales": implied_ev_sales > peer_median_ev_sales if peer_median_ev_sales else None,
    }
