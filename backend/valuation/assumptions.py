from __future__ import annotations

from typing import Any

from .models import CompanyType, Facts, ForwardEstimates, SourcedValue, clamp, safe_div


SPECIAL_PROFILES: dict[str, dict[str, Any]] = {
    "AAPL": {"company_type": "mature_compounder", "company_state": "成熟消费科技"},
    "GOOG": {"company_type": "platform_compounder", "company_state": "平台 / 广告 / 云"},
    "GOOGL": {"company_type": "platform_compounder", "company_state": "平台 / 广告 / 云"},
    "MSFT": {"company_type": "platform_compounder", "company_state": "平台软件 / 云"},
    "META": {"company_type": "platform_compounder", "company_state": "平台 / 广告 / AI"},
    "NVDA": {"company_type": "high_growth_profitable_tech", "company_state": "半导体 / AI 周期成长"},
    "PLTR": {"company_type": "high_growth_software", "company_state": "高成长软件 / AI 平台"},
}


DEFAULT_SCENARIOS: dict[CompanyType, dict[str, dict[str, float]]] = {
    "high_growth_profitable_tech": {
        "bear": {"revenue_cagr_5y": 0.10, "operating_margin_terminal": 0.42, "fcf_margin_terminal": 0.30, "discount_rate": 0.105, "terminal_growth": 0.025},
        "base": {"revenue_cagr_5y": 0.18, "operating_margin_terminal": 0.48, "fcf_margin_terminal": 0.36, "discount_rate": 0.10, "terminal_growth": 0.03},
        "bull": {"revenue_cagr_5y": 0.25, "operating_margin_terminal": 0.52, "fcf_margin_terminal": 0.40, "discount_rate": 0.095, "terminal_growth": 0.035},
    },
    "high_growth_software": {
        "bear": {"revenue_cagr_5y": 0.12, "operating_margin_terminal": 0.24, "fcf_margin_terminal": 0.22, "discount_rate": 0.11, "terminal_growth": 0.025},
        "base": {"revenue_cagr_5y": 0.22, "operating_margin_terminal": 0.30, "fcf_margin_terminal": 0.28, "discount_rate": 0.105, "terminal_growth": 0.03},
        "bull": {"revenue_cagr_5y": 0.32, "operating_margin_terminal": 0.36, "fcf_margin_terminal": 0.34, "discount_rate": 0.10, "terminal_growth": 0.035},
    },
    "platform_compounder": {
        "bear": {"revenue_cagr_5y": 0.05, "operating_margin_terminal": 0.28, "fcf_margin_terminal": 0.20, "discount_rate": 0.095, "terminal_growth": 0.02},
        "base": {"revenue_cagr_5y": 0.10, "operating_margin_terminal": 0.32, "fcf_margin_terminal": 0.25, "discount_rate": 0.09, "terminal_growth": 0.025},
        "bull": {"revenue_cagr_5y": 0.15, "operating_margin_terminal": 0.36, "fcf_margin_terminal": 0.30, "discount_rate": 0.0875, "terminal_growth": 0.03},
    },
    "mature_compounder": {
        "bear": {"revenue_cagr_5y": 0.01, "operating_margin_terminal": 0.22, "fcf_margin_terminal": 0.16, "discount_rate": 0.09, "terminal_growth": 0.015},
        "base": {"revenue_cagr_5y": 0.04, "operating_margin_terminal": 0.25, "fcf_margin_terminal": 0.19, "discount_rate": 0.085, "terminal_growth": 0.02},
        "bull": {"revenue_cagr_5y": 0.07, "operating_margin_terminal": 0.28, "fcf_margin_terminal": 0.22, "discount_rate": 0.0825, "terminal_growth": 0.025},
    },
    "consumer_staples": {
        "bear": {"revenue_cagr_5y": 0.00, "operating_margin_terminal": 0.20, "fcf_margin_terminal": 0.14, "discount_rate": 0.085, "terminal_growth": 0.015},
        "base": {"revenue_cagr_5y": 0.03, "operating_margin_terminal": 0.23, "fcf_margin_terminal": 0.17, "discount_rate": 0.08, "terminal_growth": 0.02},
        "bull": {"revenue_cagr_5y": 0.05, "operating_margin_terminal": 0.25, "fcf_margin_terminal": 0.19, "discount_rate": 0.0775, "terminal_growth": 0.0225},
    },
    "cyclical": {
        "bear": {"revenue_cagr_5y": -0.02, "operating_margin_terminal": 0.10, "fcf_margin_terminal": 0.08, "discount_rate": 0.11, "terminal_growth": 0.01},
        "base": {"revenue_cagr_5y": 0.03, "operating_margin_terminal": 0.14, "fcf_margin_terminal": 0.10, "discount_rate": 0.10, "terminal_growth": 0.015},
        "bull": {"revenue_cagr_5y": 0.08, "operating_margin_terminal": 0.18, "fcf_margin_terminal": 0.13, "discount_rate": 0.095, "terminal_growth": 0.02},
    },
    "unprofitable_growth": {
        "bear": {"revenue_cagr_5y": 0.08, "operating_margin_terminal": 0.10, "fcf_margin_terminal": 0.08, "discount_rate": 0.13, "terminal_growth": 0.02},
        "base": {"revenue_cagr_5y": 0.18, "operating_margin_terminal": 0.18, "fcf_margin_terminal": 0.16, "discount_rate": 0.12, "terminal_growth": 0.025},
        "bull": {"revenue_cagr_5y": 0.30, "operating_margin_terminal": 0.26, "fcf_margin_terminal": 0.24, "discount_rate": 0.11, "terminal_growth": 0.03},
    },
    "financial": {
        "bear": {"revenue_cagr_5y": 0.00, "operating_margin_terminal": 0.18, "fcf_margin_terminal": 0.12, "discount_rate": 0.11, "terminal_growth": 0.015},
        "base": {"revenue_cagr_5y": 0.03, "operating_margin_terminal": 0.22, "fcf_margin_terminal": 0.15, "discount_rate": 0.10, "terminal_growth": 0.02},
        "bull": {"revenue_cagr_5y": 0.06, "operating_margin_terminal": 0.26, "fcf_margin_terminal": 0.18, "discount_rate": 0.095, "terminal_growth": 0.025},
    },
    "default": {
        "bear": {"revenue_cagr_5y": 0.02, "operating_margin_terminal": 0.16, "fcf_margin_terminal": 0.10, "discount_rate": 0.10, "terminal_growth": 0.015},
        "base": {"revenue_cagr_5y": 0.06, "operating_margin_terminal": 0.20, "fcf_margin_terminal": 0.14, "discount_rate": 0.095, "terminal_growth": 0.02},
        "bull": {"revenue_cagr_5y": 0.10, "operating_margin_terminal": 0.24, "fcf_margin_terminal": 0.18, "discount_rate": 0.09, "terminal_growth": 0.025},
    },
}


def historical_revenue_cagr(annual_history: list[dict[str, Any]], fallback: float = 0.06) -> float:
    rows = [r for r in annual_history if r.get("revenue")]
    if len(rows) < 2:
        return fallback
    rows = sorted(rows, key=lambda item: item.get("fiscal_year") or 0)
    first, last = rows[0], rows[-1]
    years = max(1, (last.get("fiscal_year") or len(rows)) - (first.get("fiscal_year") or 1))
    if first["revenue"] <= 0:
        return fallback
    return clamp((last["revenue"] / first["revenue"]) ** (1 / years) - 1, -0.15, 0.60)


def infer_company_type(facts: Facts, company_profile: dict[str, Any] | None = None, annual_history: list[dict[str, Any]] | None = None) -> CompanyType:
    profile = SPECIAL_PROFILES.get(facts.ticker.upper())
    if profile:
        return profile["company_type"]  # type: ignore[return-value]

    company_profile = company_profile or {}
    text = " ".join(str(company_profile.get(key, "")) for key in ["industry", "sector", "description", "business_overview"]).lower()
    growth = historical_revenue_cagr(annual_history or facts.annual_history)
    op_margin = facts.operating_margin
    fcf_margin = facts.fcf_margin
    capex_ocf = safe_div(facts.capex, facts.ocf)
    sbc_revenue = safe_div(facts.sbc, facts.revenue)

    if any(word in text for word in ["bank", "insurance", "reit", "financial", "finance", "lending", "loan", "credit", "broker", "mortgage", "deposit"]):
        return "financial"
    if op_margin < 0 and growth >= 0.12:
        return "unprofitable_growth"
    if any(word in text for word in ["software", "saas", "cloud", "ai platform"]) and growth >= 0.12:
        return "high_growth_software"
    if growth >= 0.16 and op_margin >= 0.15:
        return "high_growth_profitable_tech"
    if op_margin >= 0.25 and fcf_margin >= 0.12:
        return "platform_compounder"
    if capex_ocf > 0.60 or any(word in text for word in ["energy", "materials", "semiconductor", "auto"]):
        return "cyclical"
    if any(word in text for word in ["beverage", "household", "staples", "consumer defensive"]):
        return "consumer_staples"
    if growth <= 0.07 and op_margin >= 0.15 and sbc_revenue < 0.05:
        return "mature_compounder"
    return "default"


def _scenario_overlay(defaults: dict[str, float], override: Any | None, manual_overrides: dict[str, Any]) -> dict[str, float]:
    scenario = dict(defaults)
    if override:
        if hasattr(override, "model_dump"):
            data = override.model_dump(exclude_none=True)
        elif hasattr(override, "__dict__"):
            data = {k: v for k, v in vars(override).items() if v is not None}
        else:
            data = {k: v for k, v in dict(override).items() if v is not None}
        scenario.update({k: float(v) for k, v in data.items() if isinstance(v, (int, float))})
    for key, value in manual_overrides.items():
        if key in scenario and value is not None:
            scenario[key] = float(value)
    return scenario


def build_scenarios(company_type: CompanyType, request: Any | None, manual_overrides: dict[str, Any] | None = None) -> dict[str, dict[str, float]]:
    defaults = DEFAULT_SCENARIOS.get(company_type, DEFAULT_SCENARIOS["default"])
    manual_overrides = manual_overrides or {}
    return {
        "bear": _scenario_overlay(defaults["bear"], getattr(request, "bear", None), manual_overrides),
        "base": _scenario_overlay(defaults["base"], getattr(request, "base", None), manual_overrides),
        "bull": _scenario_overlay(defaults["bull"], getattr(request, "bull", None), manual_overrides),
    }


def resolve_forward_estimates(
    facts: Facts,
    consensus: Any | None = None,
    annual_history: list[dict[str, Any]] | None = None,
    db_consensus: dict[str, Any] | None = None,
    company_type: CompanyType | None = None,
    scenarios: dict[str, dict[str, float]] | None = None,
) -> ForwardEstimates:
    annual_history = annual_history or facts.annual_history
    ticker_growth = {
        "NVDA": 0.34,
        "PLTR": 0.38,
        "MSFT": 0.12,
        "META": 0.11,
        "GOOG": 0.10,
        "GOOGL": 0.10,
        "AAPL": 0.05,
    }
    type_growth = {
        "high_growth_profitable_tech": 0.24,
        "high_growth_software": 0.28,
        "platform_compounder": 0.10,
        "mature_compounder": 0.04,
        "consumer_staples": 0.03,
        "cyclical": 0.03,
        "unprofitable_growth": 0.22,
        "financial": 0.04,
        "default": 0.07,
    }
    fallback_growth = ticker_growth.get(facts.ticker.upper(), type_growth.get(company_type or "default", 0.08))
    history_growth = historical_revenue_cagr(annual_history, fallback=fallback_growth)
    base_scenario = (scenarios or {}).get("base", {})
    five_year_growth = float(base_scenario.get("revenue_cagr_5y", history_growth))
    growth = clamp(max(history_growth, fallback_growth, five_year_growth), -0.05, 0.45)
    near_term_lift = {
        "high_growth_software": 1.45,
        "high_growth_profitable_tech": 1.30,
        "unprofitable_growth": 1.35,
        "platform_compounder": 1.10,
    }.get(company_type or "default", 1.0)
    next_growth = clamp(max(growth, five_year_growth * near_term_lift), -0.05, 0.65)
    year_two_growth = clamp((next_growth + five_year_growth) / 2, -0.05, 0.55)
    margin = clamp(facts.operating_margin, -0.10, 0.65)
    terminal_margin = float(base_scenario.get("operating_margin_terminal", margin))
    margin_next = clamp(margin + (terminal_margin - margin) * 0.30, -0.10, 0.70)
    margin_2y = clamp(margin + (terminal_margin - margin) * 0.50, -0.10, 0.70)
    tax_rate = 0.18
    fcf_margin = clamp(max(facts.fcf_margin, safe_div(facts.ocf, facts.revenue) * 0.65), -0.05, 0.45)
    terminal_fcf_margin = float(base_scenario.get("fcf_margin_terminal", fcf_margin))
    fcf_margin_next = clamp(fcf_margin + (terminal_fcf_margin - fcf_margin) * 0.25, -0.05, 0.55)
    revenue_next = facts.revenue * (1 + next_growth)
    revenue_2y = revenue_next * (1 + year_two_growth)

    system = {
        "revenue_next_year": revenue_next,
        "revenue_2y": revenue_2y,
        "eps_next_year": safe_div(revenue_next * margin_next * (1 - tax_rate), facts.diluted_shares),
        "eps_2y": safe_div(revenue_2y * margin_2y * (1 - tax_rate), facts.diluted_shares),
        "ebitda_next_year": revenue_next * min(0.70, max(margin_next + 0.05, margin_next)),
        "operating_income_next_year": revenue_next * margin_next,
        "fcf_next_year": revenue_next * fcf_margin_next,
        "long_term_eps_growth": max(min((next_growth + year_two_growth) / 2, 0.45), 0.06),
    }

    def read_manual(key: str) -> float | None:
        if consensus is None:
            return None
        if hasattr(consensus, key):
            value = getattr(consensus, key)
        else:
            value = dict(consensus).get(key)
        return float(value) if value is not None else None

    def read_db(key: str) -> float | None:
        if not db_consensus:
            return None
        value = db_consensus.get(key)
        return float(value) if value is not None else None

    output: dict[str, SourcedValue] = {}
    for key, fallback in system.items():
        manual_value = read_manual(key)
        if manual_value is not None:
            output[key] = SourcedValue(manual_value, "manual_consensus", "high")
            continue
        db_value = read_db(key)
        if db_value is not None:
            output[key] = SourcedValue(db_value, "db_consensus", "medium_high")
            continue
        output[key] = SourcedValue(float(fallback), "system_estimate", "low")

    return ForwardEstimates(**output)
