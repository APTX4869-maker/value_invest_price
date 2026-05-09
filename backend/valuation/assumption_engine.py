from __future__ import annotations

from statistics import median
from typing import Any

from .assumptions import DEFAULT_SCENARIOS, SPECIAL_PROFILES
from .models import CompanyType, Facts, clamp, safe_div


TYPE_PRIORS: dict[str, dict[str, Any]] = {
    "high_growth_profitable_tech": {"growth": 0.18, "growth_bounds": (0.04, 0.30), "op_margin": 0.42, "fcf_margin": 0.30, "risk": 0.010, "terminal_cap": 0.035},
    "high_growth_software": {"growth": 0.20, "growth_bounds": (0.06, 0.34), "op_margin": 0.26, "fcf_margin": 0.24, "risk": 0.018, "terminal_cap": 0.035},
    "platform_compounder": {"growth": 0.10, "growth_bounds": (0.02, 0.18), "op_margin": 0.32, "fcf_margin": 0.24, "risk": 0.003, "terminal_cap": 0.030},
    "mature_compounder": {"growth": 0.04, "growth_bounds": (-0.01, 0.09), "op_margin": 0.25, "fcf_margin": 0.18, "risk": 0.002, "terminal_cap": 0.025},
    "consumer_staples": {"growth": 0.03, "growth_bounds": (-0.01, 0.07), "op_margin": 0.22, "fcf_margin": 0.16, "risk": 0.001, "terminal_cap": 0.023},
    "cyclical": {"growth": 0.03, "growth_bounds": (-0.05, 0.10), "op_margin": 0.14, "fcf_margin": 0.10, "risk": 0.018, "terminal_cap": 0.022},
    "industrial": {"growth": 0.05, "growth_bounds": (-0.02, 0.13), "op_margin": 0.18, "fcf_margin": 0.12, "risk": 0.010, "terminal_cap": 0.026},
    "memory_semiconductor": {"growth": 0.16, "growth_bounds": (-0.08, 0.35), "op_margin": 0.28, "fcf_margin": 0.18, "risk": 0.024, "terminal_cap": 0.025},
    "unprofitable_growth": {"growth": 0.18, "growth_bounds": (0.04, 0.34), "op_margin": 0.12, "fcf_margin": 0.10, "risk": 0.030, "terminal_cap": 0.030},
    "financial": {"growth": 0.04, "growth_bounds": (-0.02, 0.10), "op_margin": 0.22, "fcf_margin": 0.12, "risk": 0.014, "terminal_cap": 0.025},
    "default": {"growth": 0.06, "growth_bounds": (-0.02, 0.14), "op_margin": 0.20, "fcf_margin": 0.14, "risk": 0.012, "terminal_cap": 0.025},
}

COMPANY_GROWTH_PRIORS: dict[str, float] = {
    "NVDA": 0.34,
    "PLTR": 0.38,
    "MSFT": 0.12,
    "META": 0.11,
    "GOOG": 0.10,
    "GOOGL": 0.10,
    "AAPL": 0.05,
    "MU": 0.38,
}


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sorted_rows(annual_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted([row for row in annual_history if row.get("revenue")], key=lambda item: item.get("fiscal_year") or 0)


def _cagr_between(first: float, last: float, years: int) -> float | None:
    if first <= 0 or last <= 0 or years <= 0:
        return None
    return (last / first) ** (1 / years) - 1


def _window_cagr(rows: list[dict[str, Any]], years: int) -> float | None:
    if len(rows) < 2:
        return None
    last = rows[-1]
    target_year = (last.get("fiscal_year") or 0) - years
    candidates = [row for row in rows[:-1] if (row.get("fiscal_year") or 0) <= target_year]
    first = candidates[-1] if candidates else rows[0]
    actual_years = max(1, (last.get("fiscal_year") or len(rows)) - (first.get("fiscal_year") or 1))
    return _cagr_between(float(first["revenue"]), float(last["revenue"]), min(years, actual_years))


def _yoy_growths(rows: list[dict[str, Any]]) -> list[float]:
    growths: list[float] = []
    for prev, curr in zip(rows, rows[1:]):
        growth = safe_div((curr.get("revenue") or 0) - (prev.get("revenue") or 0), prev.get("revenue") or 0)
        if growth:
            growths.append(clamp(growth, -0.80, 1.50))
    return growths


def _recent_annualized_growth(facts: Facts) -> float | None:
    recent_period = facts.raw.get("recent_period") if isinstance(facts.raw, dict) else None
    if not isinstance(recent_period, dict):
        return None
    latest_quarter = recent_period.get("latest_quarter") or {}
    annualized_revenue = _as_float(latest_quarter.get("annualized_revenue"))
    if annualized_revenue and facts.revenue > 0:
        return clamp(annualized_revenue / facts.revenue - 1, -0.50, 1.20)
    return None


def _margin_series(rows: list[dict[str, Any]], numerator_key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        revenue = _as_float(row.get("revenue"))
        numerator = _as_float(row.get(numerator_key))
        if revenue and numerator is not None:
            values.append(clamp(numerator / revenue, -0.50, 0.80))
    return values


def _fcf_margin_series(rows: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        revenue = _as_float(row.get("revenue"))
        ocf = _as_float(row.get("ocf"))
        capex = abs(_as_float(row.get("capex")) or 0)
        if revenue and ocf is not None:
            values.append(clamp((ocf - capex) / revenue, -0.50, 0.80))
    return values


def _blend(parts: list[tuple[float | None, float]], fallback: float) -> float:
    usable = [(value, weight) for value, weight in parts if value is not None and weight > 0]
    total = sum(weight for _, weight in usable)
    if total <= 0:
        return fallback
    return sum(float(value) * weight for value, weight in usable) / total


def _manual_company_type(manual_overrides: dict[str, Any]) -> CompanyType | None:
    value = manual_overrides.get("company_type") or manual_overrides.get("company_type_override")
    if value in DEFAULT_SCENARIOS:
        return value  # type: ignore[return-value]
    return None


def infer_company_type_with_reasons(
    facts: Facts,
    manual_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manual_overrides = manual_overrides or {}
    manual_type = _manual_company_type(manual_overrides)
    if manual_type:
        return {
            "type": manual_type,
            "confidence": "high",
            "reasons": [f"用户手动覆盖公司类型为 {manual_type}。"],
        }

    profile = SPECIAL_PROFILES.get(facts.ticker.upper())
    if profile:
        return {
            "type": profile["company_type"],
            "confidence": "high",
            "reasons": [f"{facts.ticker} 使用内置公司画像：{profile.get('company_state', profile['company_type'])}。"],
        }

    text = " ".join(str(facts.company_profile.get(key, "")) for key in ["industry", "sector", "description", "business_overview"]).lower()
    rows = _sorted_rows(facts.annual_history)
    growth_3y = _window_cagr(rows, 3)
    growth = growth_3y if growth_3y is not None else TYPE_PRIORS["default"]["growth"]
    op_margin = facts.operating_margin
    fcf_margin = facts.fcf_margin
    capex_ocf = safe_div(facts.capex, facts.ocf)
    sbc_revenue = safe_div(facts.sbc, facts.revenue)

    def matched(company_type: CompanyType, confidence: str, reason: str) -> dict[str, Any]:
        return {"type": company_type, "confidence": confidence, "reasons": [reason]}

    if any(word in text for word in ["bank", "insurance", "reit", "financial", "finance", "lending", "loan", "credit", "broker", "mortgage", "deposit"]):
        return matched("financial", "medium_high", "行业文本包含金融/信贷/银行/保险/REIT 等关键词。")
    if any(word in text for word in ["dram", "nand", "memory", "hbm"]) and "semiconductor" in text:
        return matched("memory_semiconductor", "medium_high", "行业文本同时包含存储和半导体关键词。")
    if any(word in text for word in ["aerospace", "aircraft", "aviation", "defense", "electrical equipment", "electronic & other electrical equipment", "engine", "industrial", "machinery", "manufactur", "power systems", "turbine"]):
        return matched("industrial", "medium_high", "行业文本包含航空、工业制造、电气设备、机械或涡轮等工业关键词。")
    if op_margin < 0 and growth >= 0.12:
        return matched("unprofitable_growth", "medium", "公司仍亏损但收入增长较快。")
    if any(word in text for word in ["software", "saas", "cloud", "ai platform"]) and growth >= 0.12:
        return matched("high_growth_software", "medium", "行业文本偏软件/SaaS/云，且历史收入增长较高。")
    if growth >= 0.16 and op_margin >= 0.15:
        return matched("high_growth_profitable_tech", "medium", "收入增长和经营利润率都较高。")
    if op_margin >= 0.25 and fcf_margin >= 0.12:
        return matched("platform_compounder", "medium", "经营利润率和 FCF margin 都较高，但缺少更强行业标签。")
    if capex_ocf > 0.60 or any(word in text for word in ["energy", "materials", "semiconductor", "auto"]):
        return matched("cyclical", "medium", "资本开支占 OCF 较高或行业文本偏周期。")
    if any(word in text for word in ["beverage", "household", "staples", "consumer defensive"]):
        return matched("consumer_staples", "medium", "行业文本偏必选消费。")
    if growth <= 0.07 and op_margin >= 0.15 and sbc_revenue < 0.05:
        return matched("mature_compounder", "medium", "增长较稳、利润率尚可且 SBC 占收入较低。")
    return matched("default", "low", "缺少足够行业标签和历史特征，暂按通用公司处理。")


def _build_growth_assumption(facts: Facts, company_type: CompanyType, warnings: list[str]) -> dict[str, Any]:
    prior = TYPE_PRIORS.get(company_type, TYPE_PRIORS["default"])
    company_prior = COMPANY_GROWTH_PRIORS.get(facts.ticker.upper())
    rows = _sorted_rows(facts.annual_history)
    growth_3y = _window_cagr(rows, 3)
    growth_5y = _window_cagr(rows, 5)
    recent_growth = _recent_annualized_growth(facts)
    yoy = _yoy_growths(rows)
    volatility = (max(yoy) - min(yoy)) if len(yoy) >= 2 else 0.0
    if len(rows) < 4:
        warnings.append("收入历史少于 4 年，增长率会更依赖最近数据和行业先验。")
    if any(abs(item) > 0.40 for item in yoy):
        warnings.append("历史收入存在大幅跳变，可能包含拆分、并购、周期或口径变化，旧年份已降低权重。")

    base = _blend(
        [
            (growth_3y, 0.36),
            (growth_5y, 0.20),
            (recent_growth, 0.18),
            (company_prior, 0.18 if rows else 0.48),
            (prior["growth"], 0.08 if rows else 0.22),
        ],
        company_prior if company_prior is not None else prior["growth"],
    )
    low, high = prior["growth_bounds"]
    if company_prior is not None:
        high = max(high, company_prior + 0.08)
    base = clamp(base, low, high)
    spread = clamp(0.025 + volatility * 0.25, 0.025, 0.10)
    if company_type in {"cyclical", "memory_semiconductor", "unprofitable_growth"}:
        spread = max(spread, 0.07)
    near_term = _blend([(recent_growth, 0.45), (growth_3y, 0.35), (base, 0.20)], base)
    near_term = clamp(near_term, low - 0.03, high + 0.08)
    year_two = clamp((near_term * 0.55) + (base * 0.45), low - 0.02, high + 0.04)
    return {
        "base": base,
        "bear": clamp(base - spread, low - 0.03, high),
        "bull": clamp(base + spread, low, high + 0.08),
        "near_term": near_term,
        "year_two": year_two,
        "spread": spread,
        "sources": {
            "revenue_cagr_3y": growth_3y,
            "revenue_cagr_5y": growth_5y,
            "recent_annualized_growth": recent_growth,
            "company_prior": company_prior,
            "industry_prior": prior["growth"],
            "yoy_volatility_range": volatility,
        },
        "method": "weighted_history_recent_trend_and_industry_prior",
    }


def _build_margin_assumption(facts: Facts, company_type: CompanyType, warnings: list[str]) -> dict[str, Any]:
    prior = TYPE_PRIORS.get(company_type, TYPE_PRIORS["default"])
    rows = _sorted_rows(facts.annual_history)
    op_history = _margin_series(rows, "operating_income")
    fcf_history = _fcf_margin_series(rows)
    op_recent = median(op_history[-3:]) if op_history else None
    fcf_recent = median(fcf_history[-3:]) if fcf_history else None
    if not op_history:
        warnings.append("缺少多年经营利润率历史，经营利润率会更多依赖当前值和行业先验。")
    if not fcf_history:
        warnings.append("缺少多年 FCF margin 历史，现金流率会更多依赖当前值和行业先验。")

    op_current = facts.operating_margin if facts.revenue else None
    fcf_current = facts.fcf_margin if facts.revenue else None
    op_low = min(-0.05, prior["op_margin"] - 0.18)
    op_high = max(prior["op_margin"] + 0.16, 0.12)
    fcf_low = min(-0.05, prior["fcf_margin"] - 0.14)
    fcf_high = max(prior["fcf_margin"] + 0.14, 0.08)
    op_base = clamp(_blend([(op_recent, 0.38), (op_current, 0.34), (prior["op_margin"], 0.28)], prior["op_margin"]), op_low, op_high)
    fcf_base = clamp(_blend([(fcf_recent, 0.45), (fcf_current, 0.35), (prior["fcf_margin"], 0.20)], prior["fcf_margin"]), fcf_low, fcf_high)
    op_start = clamp(_blend([(op_current, 0.55), (op_recent, 0.25), (prior["op_margin"], 0.20)], op_base), op_low, op_high)
    fcf_start = clamp(_blend([(fcf_current, 0.55), (fcf_recent, 0.30), (prior["fcf_margin"], 0.15)], fcf_base), fcf_low, fcf_high)
    return {
        "operating_margin": {
            "base": op_base,
            "bear": clamp(op_base - 0.035, op_low, op_high),
            "bull": clamp(op_base + 0.035, op_low, op_high),
            "start": op_start,
            "sources": {"current": op_current, "history_median_recent": op_recent, "industry_prior": prior["op_margin"]},
        },
        "fcf_margin": {
            "base": fcf_base,
            "bear": clamp(fcf_base - 0.030, fcf_low, fcf_high),
            "bull": clamp(fcf_base + 0.035, fcf_low, fcf_high),
            "start": fcf_start,
            "sources": {"current": fcf_current, "history_median_recent": fcf_recent, "industry_prior": prior["fcf_margin"]},
        },
        "method": "weighted_history_current_and_industry_prior",
    }


def _build_discount_assumption(facts: Facts, company_type: CompanyType, growth: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    prior = TYPE_PRIORS.get(company_type, TYPE_PRIORS["default"])
    risk_free = clamp(facts.ten_year_yield or 0.045, 0.015, 0.070)
    equity_risk_premium = 0.045
    company_risk = float(prior["risk"])
    if len(facts.annual_history) < 4:
        company_risk += 0.004
    if growth["sources"].get("yoy_volatility_range", 0) > 0.35:
        company_risk += 0.006
    if safe_div(facts.debt, facts.enterprise_value) > 0.35:
        company_risk += 0.006
    if facts.operating_income <= 0:
        company_risk += 0.010
    base = clamp(risk_free + equity_risk_premium + company_risk, 0.070, 0.155)
    return {
        "base": base,
        "bear": clamp(base + 0.010, 0.070, 0.165),
        "bull": clamp(base - 0.006, 0.065, 0.150),
        "risk_free_rate": risk_free,
        "equity_risk_premium": equity_risk_premium,
        "company_risk_premium": company_risk,
        "method": "risk_free_plus_equity_and_company_risk_premium",
    }


def _terminal_growth(company_type: CompanyType, growth_base: float, discount_base: float) -> float:
    prior = TYPE_PRIORS.get(company_type, TYPE_PRIORS["default"])
    value = max(0.010, min(growth_base * 0.35, prior["terminal_cap"]))
    return clamp(value, 0.005, max(0.005, discount_base - 0.030))


def _request_overlay(defaults: dict[str, float], override: Any | None, manual_overrides: dict[str, Any]) -> dict[str, float]:
    scenario = dict(defaults)
    if override:
        if hasattr(override, "model_dump"):
            data = override.model_dump(exclude_none=True)
        elif hasattr(override, "__dict__"):
            data = {key: value for key, value in vars(override).items() if value is not None}
        else:
            data = {key: value for key, value in dict(override).items() if value is not None}
        scenario.update({key: float(value) for key, value in data.items() if isinstance(value, (int, float))})
    for key, value in manual_overrides.items():
        if key in scenario and value is not None:
            scenario[key] = float(value)
    scenario["terminal_growth"] = min(scenario["terminal_growth"], scenario["discount_rate"] - 0.010)
    return scenario


def build_assumptions(
    facts: Facts,
    request: Any | None = None,
    manual_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manual_overrides = manual_overrides or {}
    warnings: list[str] = []
    classification = infer_company_type_with_reasons(facts, manual_overrides)
    company_type: CompanyType = classification["type"]
    profile = SPECIAL_PROFILES.get(facts.ticker.upper(), {})
    company_state = profile.get("company_state", company_type)
    growth = _build_growth_assumption(facts, company_type, warnings)
    margins = _build_margin_assumption(facts, company_type, warnings)
    discount = _build_discount_assumption(facts, company_type, growth, warnings)
    terminal_base = _terminal_growth(company_type, growth["base"], discount["base"])

    raw_scenarios = {
        "bear": {
            "revenue_cagr_5y": growth["bear"],
            "revenue_growth_next_year": min(growth["near_term"], growth["bear"] + growth["spread"] * 0.35),
            "revenue_growth_2y": (growth["bear"] + growth["year_two"]) / 2,
            "operating_margin_start": margins["operating_margin"]["start"],
            "operating_margin_terminal": margins["operating_margin"]["bear"],
            "fcf_margin_start": margins["fcf_margin"]["start"],
            "fcf_margin_terminal": margins["fcf_margin"]["bear"],
            "discount_rate": discount["bear"],
            "terminal_growth": max(0.005, terminal_base - 0.005),
            "long_term_eps_growth": max(-0.02, growth["bear"]),
        },
        "base": {
            "revenue_cagr_5y": growth["base"],
            "revenue_growth_next_year": growth["near_term"],
            "revenue_growth_2y": growth["year_two"],
            "operating_margin_start": margins["operating_margin"]["start"],
            "operating_margin_terminal": margins["operating_margin"]["base"],
            "fcf_margin_start": margins["fcf_margin"]["start"],
            "fcf_margin_terminal": margins["fcf_margin"]["base"],
            "discount_rate": discount["base"],
            "terminal_growth": terminal_base,
            "long_term_eps_growth": max(-0.02, (growth["near_term"] + growth["year_two"]) / 2),
        },
        "bull": {
            "revenue_cagr_5y": growth["bull"],
            "revenue_growth_next_year": max(growth["near_term"], growth["bull"] - growth["spread"] * 0.25),
            "revenue_growth_2y": (growth["bull"] + growth["year_two"]) / 2,
            "operating_margin_start": margins["operating_margin"]["start"],
            "operating_margin_terminal": margins["operating_margin"]["bull"],
            "fcf_margin_start": margins["fcf_margin"]["start"],
            "fcf_margin_terminal": margins["fcf_margin"]["bull"],
            "discount_rate": discount["bull"],
            "terminal_growth": min(discount["bull"] - 0.010, terminal_base + 0.004),
            "long_term_eps_growth": max(-0.02, growth["bull"]),
        },
    }
    scenarios = {
        key: _request_overlay(value, getattr(request, key, None), manual_overrides)
        for key, value in raw_scenarios.items()
    }
    return {
        "company_type": company_type,
        "company_state": company_state,
        "classification": classification,
        "growth_assumptions": growth,
        "margin_assumptions": margins,
        "discount_rate": discount,
        "terminal_growth": {"base": terminal_base, "method": "capped_by_growth_type_and_discount_spread"},
        "scenarios": scenarios,
        "warnings": warnings,
        "model_eligibility": {
            "three_stage_fcff_dcf": company_type not in {"financial"},
            "financial_warning": "金融/银行/保险/REIT 不适合机械套普通 FCFF DCF。" if company_type == "financial" else "",
        },
    }
