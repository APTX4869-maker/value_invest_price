from __future__ import annotations

from typing import Any

from .models import Facts, clamp, safe_div


def _project_margin(start_margin: float, terminal_margin: float, year: int, first_stage_years: int = 5, total_years: int = 10) -> float:
    if year <= first_stage_years:
        progress = year / first_stage_years * 0.55
    else:
        progress = 0.55 + ((year - first_stage_years) / (total_years - first_stage_years)) * 0.45
    return start_margin + (terminal_margin - start_margin) * progress


def run_three_stage_dcf(
    facts: Facts,
    scenario: dict[str, float],
    capex_split: dict[str, Any],
    tax_rate: float = 0.18,
    use_fcff: bool = True,
) -> dict[str, Any]:
    revenue = facts.revenue
    growth_5y = float(scenario["revenue_cagr_5y"])
    terminal_growth = float(scenario["terminal_growth"])
    discount_rate = float(scenario["discount_rate"])
    terminal_fcf_margin = float(scenario["fcf_margin_terminal"])
    terminal_operating_margin = float(scenario["operating_margin_terminal"])
    start_fcf_margin = float(scenario.get("fcf_margin_start", safe_div(facts.ocf - capex_split["maintenance_capex"], facts.revenue)))
    start_op_margin = float(scenario.get("operating_margin_start", facts.operating_margin))

    cash_flows: list[dict[str, float]] = []
    pv_cash_flows = 0.0
    fallback = False
    for year in range(1, 11):
        if year <= 5:
            growth = growth_5y
        else:
            fade = (year - 5) / 5
            growth = growth_5y * (1 - fade) + terminal_growth * fade
        revenue *= 1 + growth
        op_margin = _project_margin(start_op_margin, terminal_operating_margin, year)
        fcf_margin = _project_margin(start_fcf_margin, terminal_fcf_margin, year)
        if use_fcff and facts.operating_income > 0:
            nopat = revenue * op_margin * (1 - tax_rate)
            fcff_by_nopat = nopat + max(0.0, facts.capex * 0.18) - capex_split["maintenance_capex"]
            fcff_by_margin = revenue * fcf_margin
            fcff = max(0.0, (fcff_by_nopat * 0.45) + (fcff_by_margin * 0.55))
        else:
            fallback = True
            fcff = max(0.0, revenue * fcf_margin)
        pv = fcff / ((1 + discount_rate) ** year)
        pv_cash_flows += pv
        cash_flows.append({"year": year, "revenue": revenue, "growth": growth, "fcff": fcff, "pv": pv, "fcf_margin": fcf_margin, "operating_margin": op_margin})

    terminal_cash_flow = cash_flows[-1]["fcff"] * (1 + terminal_growth)
    spread = max(discount_rate - terminal_growth, 0.01)
    terminal_value = terminal_cash_flow / spread
    terminal_pv = terminal_value / ((1 + discount_rate) ** 10)
    enterprise_value = pv_cash_flows + terminal_pv
    equity_value = enterprise_value + facts.net_cash
    per_share = safe_div(equity_value, facts.diluted_shares)
    return {
        "per_share": per_share,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "pv_cash_flows": pv_cash_flows,
        "terminal_value": terminal_value,
        "terminal_pv": terminal_pv,
        "terminal_dependency": safe_div(terminal_pv, enterprise_value),
        "implied_terminal_growth": terminal_growth,
        "cash_flows": cash_flows,
        "method": "standard_fcff" if not fallback else "ocf_less_maintenance_capex_fallback",
        "fallback_notes": [] if not fallback else ["缺少足够 EBIT/D&A/营运资本拆分，FCFF 降级为 OCF - maintenance CAPEX 近似。"],
    }


def dcf_sensitivity_table(facts: Facts, scenario: dict[str, float], capex_split: dict[str, Any]) -> dict[str, Any]:
    base_discount = float(scenario["discount_rate"])
    base_terminal = float(scenario["terminal_growth"])
    base_op_margin = float(scenario["operating_margin_terminal"])
    base_fcf_margin = float(scenario["fcf_margin_terminal"])

    def price_with(**changes: float) -> float:
        next_scenario = dict(scenario)
        next_scenario.update(changes)
        next_scenario["terminal_growth"] = min(next_scenario["terminal_growth"], next_scenario["discount_rate"] - 0.01)
        return run_three_stage_dcf(facts, next_scenario, capex_split)["per_share"]

    discount_terminal = []
    for discount in [base_discount - 0.01, base_discount, base_discount + 0.01]:
        row = {"discount_rate": discount, "values": []}
        for terminal in [base_terminal - 0.005, base_terminal, base_terminal + 0.005]:
            row["values"].append({
                "terminal_growth": terminal,
                "price": price_with(discount_rate=max(0.04, discount), terminal_growth=clamp(terminal, 0.0, 0.05)),
            })
        discount_terminal.append(row)

    margin_sensitivity = [
        {"metric": "operating_margin", "down": price_with(operating_margin_terminal=max(0, base_op_margin - 0.03)), "base": price_with(), "up": price_with(operating_margin_terminal=base_op_margin + 0.03)},
        {"metric": "fcf_margin", "down": price_with(fcf_margin_terminal=max(0, base_fcf_margin - 0.03)), "base": price_with(), "up": price_with(fcf_margin_terminal=base_fcf_margin + 0.03)},
    ]
    return {"discount_terminal": discount_terminal, "margin_sensitivity": margin_sensitivity}
