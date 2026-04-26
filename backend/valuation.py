from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


TICKER_PROFILES: dict[str, dict[str, Any]] = {
    "AAPL": {
        "company_state": "成熟消费科技",
        "valuation_style": "mature_compounder",
        "base_growth": 0.05,
        "near_term_growth": 0.06,
        "eps_growth": 0.08,
        "bear_growth": 0.01,
        "bull_growth": 0.09,
        "discount_rate": 0.085,
        "terminal_growth": 0.02,
        "risk_discount": 0.02,
        "maintenance_capex_ratio": 0.35,
        "sbc_adjustment_ratio": 0.35,
        "pe_multiples": (22, 28, 34),
        "peg_targets": (1.6, 2.0, 2.4),
        "ev_ebitda_multiples": (16, 21, 26),
        "ev_sales_multiples": (6, 8, 10),
    },
    "GOOG": {
        "company_state": "平台 / 广告 / 云",
        "valuation_style": "platform_compounder",
        "base_growth": 0.10,
        "near_term_growth": 0.13,
        "eps_growth": 0.15,
        "bear_growth": 0.04,
        "bull_growth": 0.15,
        "discount_rate": 0.09,
        "terminal_growth": 0.025,
        "risk_discount": 0.035,
        "maintenance_capex_ratio": 0.35,
        "sbc_adjustment_ratio": 0.55,
        "pe_multiples": (20, 25, 31),
        "peg_targets": (1.2, 1.6, 2.0),
        "ev_ebitda_multiples": (14, 18, 23),
        "ev_sales_multiples": (5, 7, 9),
    },
    "GOOGL": {
        "company_state": "平台 / 广告 / 云",
        "valuation_style": "platform_compounder",
        "base_growth": 0.10,
        "near_term_growth": 0.13,
        "eps_growth": 0.15,
        "bear_growth": 0.04,
        "bull_growth": 0.15,
        "discount_rate": 0.09,
        "terminal_growth": 0.025,
        "risk_discount": 0.035,
        "maintenance_capex_ratio": 0.35,
        "sbc_adjustment_ratio": 0.55,
        "pe_multiples": (20, 25, 31),
        "peg_targets": (1.2, 1.6, 2.0),
        "ev_ebitda_multiples": (14, 18, 23),
        "ev_sales_multiples": (5, 7, 9),
    },
    "MSFT": {
        "company_state": "平台软件 / 云",
        "valuation_style": "platform_compounder",
        "base_growth": 0.10,
        "near_term_growth": 0.14,
        "eps_growth": 0.15,
        "bear_growth": 0.04,
        "bull_growth": 0.15,
        "discount_rate": 0.09,
        "terminal_growth": 0.025,
        "risk_discount": 0.03,
        "maintenance_capex_ratio": 0.30,
        "sbc_adjustment_ratio": 0.50,
        "pe_multiples": (24, 30, 36),
        "peg_targets": (1.4, 1.8, 2.2),
        "ev_ebitda_multiples": (18, 24, 30),
        "ev_sales_multiples": (8, 10, 13),
    },
    "META": {
        "company_state": "平台 / 广告 / AI",
        "valuation_style": "platform_compounder",
        "base_growth": 0.09,
        "near_term_growth": 0.12,
        "eps_growth": 0.14,
        "bear_growth": 0.03,
        "bull_growth": 0.15,
        "discount_rate": 0.095,
        "terminal_growth": 0.025,
        "risk_discount": 0.04,
        "maintenance_capex_ratio": 0.35,
        "sbc_adjustment_ratio": 0.55,
        "pe_multiples": (18, 24, 30),
        "peg_targets": (1.1, 1.5, 1.9),
        "ev_ebitda_multiples": (12, 16, 21),
        "ev_sales_multiples": (5, 7, 9),
    },
    "PLTR": {
        "company_state": "高成长软件 / AI 平台",
        "valuation_style": "high_growth_software",
        "base_growth": 0.18,
        "near_term_growth": 0.28,
        "eps_growth": 0.35,
        "projection_years": 2,
        "bear_growth": 0.08,
        "bull_growth": 0.28,
        "discount_rate": 0.105,
        "terminal_growth": 0.03,
        "risk_discount": 0.08,
        "maintenance_capex_ratio": 0.10,
        "sbc_adjustment_ratio": 0.85,
        "pe_multiples": (45, 65, 85),
        "peg_targets": (1.2, 1.7, 2.2),
        "ev_ebitda_multiples": (45, 65, 85),
        "ev_sales_multiples": (16, 24, 34),
    },
    "NVDA": {
        "company_state": "半导体 / AI 周期成长",
        "valuation_style": "high_growth_profitable_tech",
        "base_growth": 0.12,
        "near_term_growth": 0.34,
        "eps_growth": 0.40,
        "projection_years": 2,
        "bear_growth": 0.03,
        "bull_growth": 0.22,
        "discount_rate": 0.105,
        "terminal_growth": 0.025,
        "risk_discount": 0.08,
        "maintenance_capex_ratio": 0.45,
        "sbc_adjustment_ratio": 0.45,
        "pe_multiples": (28, 38, 50),
        "peg_targets": (0.9, 1.2, 1.6),
        "ev_ebitda_multiples": (24, 34, 44),
        "ev_sales_multiples": (16, 22, 28),
    },
}


STYLE_WEIGHTS: dict[str, dict[str, float]] = {
    "high_growth_profitable_tech": {
        "cash_flow_dcf": 0.15,
        "forward_pe": 0.30,
        "peg_adjusted": 0.20,
        "ev_ebitda": 0.25,
        "ev_sales": 0.05,
        "fcf_yield": 0.05,
    },
    "high_growth_software": {
        "cash_flow_dcf": 0.18,
        "forward_pe": 0.18,
        "peg_adjusted": 0.14,
        "ev_sales": 0.34,
        "fcf_yield": 0.08,
        "ev_ebitda": 0.08,
    },
    "platform_compounder": {
        "cash_flow_dcf": 0.28,
        "forward_pe": 0.25,
        "peg_adjusted": 0.12,
        "ev_ebitda": 0.20,
        "fcf_yield": 0.15,
    },
    "mature_compounder": {
        "cash_flow_dcf": 0.30,
        "forward_pe": 0.25,
        "ev_ebitda": 0.15,
        "fcf_yield": 0.25,
        "peg_adjusted": 0.05,
    },
    "consumer_staples": {
        "cash_flow_dcf": 0.20,
        "forward_pe": 0.25,
        "ev_ebitda": 0.20,
        "fcf_yield": 0.30,
        "peg_adjusted": 0.05,
    },
    "default": {
        "cash_flow_dcf": 0.35,
        "forward_pe": 0.20,
        "ev_ebitda": 0.20,
        "fcf_yield": 0.20,
        "peg_adjusted": 0.05,
    },
}


@dataclass
class Facts:
    ticker: str
    price: float
    revenue: float
    operating_income: float
    ocf: float
    capex: float
    sbc: float
    cash: float
    short_investments: float
    debt_current: float
    debt_long_term: float
    diluted_shares: float
    ten_year_yield: float
    fiscal_year: int | None = None

    @property
    def market_cap(self) -> float:
        return self.price * self.diluted_shares

    @property
    def debt(self) -> float:
        return self.debt_current + self.debt_long_term

    @property
    def net_cash(self) -> float:
        return self.cash + self.short_investments - self.debt


def dcf_value(
    starting_cash_flow: float,
    shares: float,
    net_cash: float,
    growth_5y: float,
    discount_rate: float,
    terminal_growth: float,
    risk_discount: float,
) -> dict[str, float]:
    cash_flows: list[float] = []
    value = 0.0
    current = starting_cash_flow
    for year in range(1, 11):
        if year <= 5:
            growth = growth_5y
        else:
            fade = (year - 5) / 5
            growth = growth_5y * (1 - fade) + terminal_growth * fade
        current *= 1 + growth
        pv = current / ((1 + discount_rate) ** year)
        cash_flows.append(pv)
        value += pv

    terminal_cash_flow = current * (1 + terminal_growth)
    terminal_value = terminal_cash_flow / max(discount_rate - terminal_growth, 0.01)
    terminal_pv = terminal_value / ((1 + discount_rate) ** 10)
    enterprise_value = value + terminal_pv
    equity_value = (enterprise_value + net_cash) * (1 - risk_discount)
    per_share = safe_div(equity_value, shares)
    terminal_dependency = safe_div(terminal_pv, enterprise_value)
    return {
        "per_share": per_share,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "terminal_dependency": terminal_dependency,
        "pv_cash_flows": value,
        "terminal_pv": terminal_pv,
    }


def implied_growth_for_price(
    target_price: float,
    starting_cash_flow: float,
    shares: float,
    net_cash: float,
    discount_rate: float,
    terminal_growth: float,
    risk_discount: float,
) -> float:
    low, high = -0.1, 0.35
    for _ in range(70):
        mid = (low + high) / 2
        price = dcf_value(
            starting_cash_flow,
            shares,
            net_cash,
            mid,
            discount_rate,
            terminal_growth,
            risk_discount,
        )["per_share"]
        if price < target_price:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def calculate_quality_score(facts: Facts) -> tuple[float, dict[str, Any]]:
    op_margin = safe_div(facts.operating_income, facts.revenue)
    ocf_margin = safe_div(facts.ocf, facts.revenue)
    actual_fcf = facts.ocf - facts.capex
    fcf_conversion = safe_div(actual_fcf, facts.ocf)
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


def default_assumptions(facts: Facts, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    op_margin = safe_div(facts.operating_income, facts.revenue)
    profile = TICKER_PROFILES.get(facts.ticker.upper(), {})
    base_growth = profile.get("base_growth", 0.08)
    if op_margin > 0.28 and facts.ocf > facts.operating_income:
        base_growth = max(base_growth, 0.10)
    if safe_div(facts.capex, facts.ocf) > 0.45:
        base_growth = max(0.02, base_growth - 0.01)
    quality_score, _ = calculate_quality_score(facts)
    assumptions = {
        "quality_score": quality_score,
        "company_state": profile.get("company_state", "稳定复利公司"),
        "valuation_style": profile.get("valuation_style"),
        "discount_rate": profile.get("discount_rate", 0.09),
        "terminal_growth": profile.get("terminal_growth", 0.025),
        "risk_discount": profile.get("risk_discount", 0.03),
        "maintenance_capex_ratio": profile.get("maintenance_capex_ratio", 0.25),
        "sbc_adjustment_ratio": profile.get("sbc_adjustment_ratio", 0.5),
        "near_term_growth": profile.get("near_term_growth", base_growth),
        "eps_growth": profile.get("eps_growth", max(base_growth, 0.08)),
        "projection_years": profile.get("projection_years", 1),
        "tax_rate": profile.get("tax_rate", 0.18),
        "pe_multiples": profile.get("pe_multiples"),
        "peg_targets": profile.get("peg_targets"),
        "ev_ebitda_multiples": profile.get("ev_ebitda_multiples"),
        "ev_sales_multiples": profile.get("ev_sales_multiples"),
        "bear_growth": profile.get("bear_growth", max(0.02, base_growth - 0.06)),
        "base_growth": base_growth,
        "bull_growth": profile.get("bull_growth", min(0.18, base_growth + 0.05)),
        "bear_probability": 0.2,
        "base_probability": 0.6,
        "bull_probability": 0.2,
    }
    assumptions.update({k: v for k, v in overrides.items() if v is not None})
    return assumptions


def judge_valuation(price: float, center: float) -> str:
    if center <= 0:
        return "数据不足"
    gap = safe_div(price - center, center)
    if gap <= -0.30:
        return "明显低估"
    if gap <= -0.15:
        return "有吸引力"
    if gap <= 0.15:
        return "合理"
    if gap <= 0.40:
        return "偏贵"
    return "明显高估"


def confidence_label(terminal_dependency: float, capex_ocf: float, risk_discount: float) -> str:
    if terminal_dependency > 0.75 or risk_discount >= 0.18:
        return "低"
    if terminal_dependency > 0.65 or capex_ocf > 0.55:
        return "中"
    if terminal_dependency > 0.55 or capex_ocf > 0.35:
        return "中高"
    return "高"


def infer_valuation_style(facts: Facts, assumptions: dict[str, Any]) -> str:
    profile_style = assumptions.get("valuation_style")
    if profile_style:
        return str(profile_style)
    op_margin = safe_div(facts.operating_income, facts.revenue)
    fcf_margin = safe_div(facts.ocf - facts.capex, facts.revenue)
    growth = float(assumptions.get("base_growth", 0.08))
    if growth >= 0.16 and op_margin >= 0.15:
        return "high_growth_profitable_tech"
    if growth >= 0.14:
        return "high_growth_software"
    if op_margin >= 0.25 and fcf_margin >= 0.12:
        return "platform_compounder"
    return "default"


def tuple_assumption(assumptions: dict[str, Any], key: str, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    value = assumptions.get(key, fallback)
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return float(value[0]), float(value[1]), float(value[2])
    return fallback


def valuation_model(
    key: str,
    label: str,
    low: float,
    base: float,
    high: float,
    weight: float,
    explanation: str,
) -> dict[str, Any]:
    low, base, high = sorted([max(0.0, low), max(0.0, base), max(0.0, high)])
    return {
        "key": key,
        "label": label,
        "low": low,
        "base": base,
        "high": high,
        "weight": weight,
        "explanation": explanation,
    }


def weighted_models(models: list[dict[str, Any]]) -> dict[str, float]:
    valid = [item for item in models if item["weight"] > 0 and item["base"] > 0]
    total_weight = sum(item["weight"] for item in valid)
    if not valid or total_weight <= 0:
        return {"low": 0.0, "base": 0.0, "high": 0.0}
    return {
        "low": sum(item["low"] * item["weight"] for item in valid) / total_weight,
        "base": sum(item["base"] * item["weight"] for item in valid) / total_weight,
        "high": sum(item["high"] * item["weight"] for item in valid) / total_weight,
    }


def model_consistency(models: list[dict[str, Any]], current_price: float, market_range: dict[str, float]) -> dict[str, Any]:
    bases = sorted(item["base"] for item in models if item["base"] > 0)
    if len(bases) < 2:
        return {
            "level": "低",
            "score": 35,
            "plain_language": "可用估值模型太少，区间只能作为粗略参考。",
        }
    median = bases[len(bases) // 2] if len(bases) % 2 else (bases[len(bases) // 2 - 1] + bases[len(bases) // 2]) / 2
    spread = safe_div(max(bases) - min(bases), median)
    price_position = (
        "低于市场合理区间"
        if current_price < market_range["low"]
        else "高于市场合理区间"
        if current_price > market_range["high"]
        else "位于市场合理区间"
    )
    if spread <= 0.45:
        level, score = "高", 85
        text = f"多数估值方法集中在相近区间，当前价格{price_position}，结论可信度较高。"
    elif spread <= 0.95:
        level, score = "中", 65
        text = f"不同模型有分歧，但仍能形成可用价格带；当前价格{price_position}。"
    else:
        level, score = "低", 45
        text = f"模型分歧较大，说明这家公司很依赖未来假设；当前价格{price_position}。"
    return {
        "level": level,
        "score": score,
        "spread": spread,
        "price_position": price_position,
        "plain_language": text,
    }


def judge_v3(price: float, buy_range: dict[str, float], market_range: dict[str, float], optimistic_range: dict[str, float]) -> str:
    if market_range["base"] <= 0:
        return "数据不足"
    if price <= buy_range["high"]:
        return "有吸引力"
    if price < market_range["low"]:
        return "偏便宜"
    if price <= market_range["high"]:
        return "合理"
    if price <= optimistic_range["high"]:
        return "偏贵但可解释"
    return "高风险高估"


def build_v3_models(
    facts: Facts,
    assumptions: dict[str, Any],
    scenarios: dict[str, Any],
    weighted_cash_flow_center: float,
    owner_earnings: float,
    actual_fcf: float,
) -> dict[str, Any]:
    style = infer_valuation_style(facts, assumptions)
    weights = STYLE_WEIGHTS.get(style, STYLE_WEIGHTS["default"])
    tax_rate = float(assumptions.get("tax_rate", 0.18))
    near_growth = float(assumptions.get("near_term_growth", assumptions.get("base_growth", 0.08)))
    eps_growth = float(assumptions.get("eps_growth", max(near_growth, assumptions.get("base_growth", 0.08))))
    projection_years = max(1.0, float(assumptions.get("projection_years", 1)))
    forward_multiplier = (1 + near_growth) ** projection_years
    forward_revenue = facts.revenue * forward_multiplier
    normalized_after_tax_income = max(facts.operating_income, owner_earnings * 0.85, actual_fcf) * (1 - tax_rate)
    forward_eps = safe_div(normalized_after_tax_income * forward_multiplier, facts.diluted_shares)
    forward_ebitda = max(facts.operating_income + facts.capex * 0.25, facts.operating_income, 0) * forward_multiplier

    pe_multiples = tuple_assumption(assumptions, "pe_multiples", (16, 22, 28))
    peg_targets = tuple_assumption(assumptions, "peg_targets", (1.0, 1.4, 1.8))
    ev_ebitda_multiples = tuple_assumption(assumptions, "ev_ebitda_multiples", (10, 14, 18))
    ev_sales_multiples = tuple_assumption(assumptions, "ev_sales_multiples", (3, 5, 7))

    peg_pe = tuple(max(8.0, eps_growth * 100 * peg) for peg in peg_targets)
    fcf_per_share = safe_div(max(owner_earnings, actual_fcf), facts.diluted_shares)
    fcf_yield_targets = (
        max(facts.ten_year_yield + 0.05, 0.075),
        max(facts.ten_year_yield + 0.03, 0.055),
        max(facts.ten_year_yield + 0.015, 0.045),
    )

    models = [
        valuation_model(
            "cash_flow_dcf",
            "保守现金流 DCF",
            scenarios["bear"]["per_share"],
            weighted_cash_flow_center,
            scenarios["bull"]["per_share"],
            weights.get("cash_flow_dcf", 0),
            "只相信当前现金流和较保守成长，是系统的保守底线。",
        ),
        valuation_model(
            "forward_pe",
            "Forward P/E",
            forward_eps * pe_multiples[0],
            forward_eps * pe_multiples[1],
            forward_eps * pe_multiples[2],
            weights.get("forward_pe", 0),
            "用未来一年盈利能力乘以合理市盈率，更接近市场看成熟科技和高增长盈利公司的方式。",
        ),
        valuation_model(
            "peg_adjusted",
            "PEG 成长调整",
            forward_eps * peg_pe[0],
            forward_eps * peg_pe[1],
            forward_eps * peg_pe[2],
            weights.get("peg_adjusted", 0),
            "检查高估值是否能被 EPS 增长解释，适合利润快速增长的公司。",
        ),
        valuation_model(
            "ev_ebitda",
            "EV/EBITDA",
            safe_div(forward_ebitda * ev_ebitda_multiples[0] + facts.net_cash, facts.diluted_shares),
            safe_div(forward_ebitda * ev_ebitda_multiples[1] + facts.net_cash, facts.diluted_shares),
            safe_div(forward_ebitda * ev_ebitda_multiples[2] + facts.net_cash, facts.diluted_shares),
            weights.get("ev_ebitda", 0),
            "用企业价值倍数估算，适合盈利能力已经较清楚的公司。",
        ),
        valuation_model(
            "ev_sales",
            "EV/Revenue",
            safe_div(forward_revenue * ev_sales_multiples[0] + facts.net_cash, facts.diluted_shares),
            safe_div(forward_revenue * ev_sales_multiples[1] + facts.net_cash, facts.diluted_shares),
            safe_div(forward_revenue * ev_sales_multiples[2] + facts.net_cash, facts.diluted_shares),
            weights.get("ev_sales", 0),
            "软件和平台公司常用收入倍数，但必须结合增长、利润率和现金流质量。",
        ),
        valuation_model(
            "fcf_yield",
            "FCF Yield",
            safe_div(fcf_per_share, fcf_yield_targets[0]),
            safe_div(fcf_per_share, fcf_yield_targets[1]),
            safe_div(fcf_per_share, fcf_yield_targets[2]),
            weights.get("fcf_yield", 0),
            "把公司当作现金流资产看，要求的现金流收益率越高，合理价格越低。",
        ),
    ]

    market_range = weighted_models(models)
    conservative_range = {
        "low": min(scenarios["bear"]["per_share"], weighted_cash_flow_center * 0.85),
        "base": weighted_cash_flow_center,
        "high": max(scenarios["bull"]["per_share"], weighted_cash_flow_center * 1.15),
    }
    optimistic_range = {
        "low": max(market_range["base"], market_range["high"] * 0.92),
        "base": max(market_range["high"], scenarios["bull"]["per_share"]),
        "high": max(item["high"] for item in models if item["high"] > 0),
    }
    consistency = model_consistency(models, facts.price, market_range)
    margin = 0.78 if consistency["level"] == "低" else 0.82 if consistency["level"] == "中" else 0.87
    buy_range = {
        "low": market_range["low"] * margin,
        "high": market_range["low"] * 0.95,
    }
    high_risk_price = optimistic_range["high"] * 1.05
    return {
        "style": style,
        "style_label": assumptions.get("company_state", "稳定复利公司"),
        "models": models,
        "conservative_range": conservative_range,
        "market_range": market_range,
        "optimistic_range": optimistic_range,
        "buy_range": buy_range,
        "high_risk_price": high_risk_price,
        "consistency": consistency,
        "forward_inputs": {
            "near_term_growth": near_growth,
            "eps_growth": eps_growth,
            "projection_years": projection_years,
            "forward_eps_estimate": forward_eps,
            "forward_revenue": forward_revenue,
            "forward_ebitda_proxy": forward_ebitda,
            "pe_multiples": pe_multiples,
            "ev_ebitda_multiples": ev_ebitda_multiples,
            "ev_sales_multiples": ev_sales_multiples,
        },
    }


def run_valuation(facts_dict: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    facts = Facts(
        ticker=facts_dict["ticker"],
        price=float(facts_dict.get("price") or 0),
        revenue=float(facts_dict.get("revenue") or 0),
        operating_income=float(facts_dict.get("operating_income") or 0),
        ocf=float(facts_dict.get("ocf") or 0),
        capex=abs(float(facts_dict.get("capex") or 0)),
        sbc=float(facts_dict.get("sbc") or 0),
        cash=float(facts_dict.get("cash") or 0),
        short_investments=float(facts_dict.get("short_investments") or 0),
        debt_current=float(facts_dict.get("debt_current") or 0),
        debt_long_term=float(facts_dict.get("debt_long_term") or 0),
        diluted_shares=float(facts_dict.get("diluted_shares") or 0),
        ten_year_yield=float(facts_dict.get("ten_year_yield") or 0.045),
        fiscal_year=facts_dict.get("fiscal_year"),
    )
    assumptions = default_assumptions(facts, overrides)
    actual_fcf = facts.ocf - facts.capex
    normalized_fcf = facts.ocf - facts.capex * 0.8
    owner_earnings = facts.ocf - facts.capex * assumptions["maintenance_capex_ratio"] - facts.sbc * assumptions["sbc_adjustment_ratio"]
    owner_earnings = max(owner_earnings, actual_fcf * 0.75)
    price_to_actual_fcf = safe_div(facts.market_cap, actual_fcf)
    price_to_owner_earnings = safe_div(facts.market_cap, owner_earnings)
    price_to_sales = safe_div(facts.market_cap, facts.revenue)

    scenario_inputs = {
        "bear": {
            "label": "熊市",
            "cash_flow": max(actual_fcf, owner_earnings * 0.65),
            "growth": assumptions["bear_growth"],
            "probability": assumptions["bear_probability"],
        },
        "base": {
            "label": "基准",
            "cash_flow": owner_earnings,
            "growth": assumptions["base_growth"],
            "probability": assumptions["base_probability"],
        },
        "bull": {
            "label": "牛市",
            "cash_flow": max(owner_earnings, normalized_fcf) * 1.08,
            "growth": assumptions["bull_growth"],
            "probability": assumptions["bull_probability"],
        },
    }

    scenarios: dict[str, Any] = {}
    weighted_center = 0.0
    terminal_dependency = 0.0
    for key, item in scenario_inputs.items():
        dcf = dcf_value(
            item["cash_flow"],
            facts.diluted_shares,
            facts.net_cash,
            item["growth"],
            assumptions["discount_rate"],
            assumptions["terminal_growth"],
            assumptions["risk_discount"],
        )
        scenarios[key] = {**item, **dcf}
        weighted_center += dcf["per_share"] * item["probability"]
        if key == "base":
            terminal_dependency = dcf["terminal_dependency"]

    fair_low = min(scenarios["bear"]["per_share"], weighted_center * 0.85)
    fair_high = max(scenarios["bull"]["per_share"], weighted_center * 1.15)
    quality_score = float(assumptions["quality_score"])
    _, quality_breakdown = calculate_quality_score(facts)
    safety_discount = 0.85 if quality_score >= 80 else 0.8 if quality_score >= 70 else 0.72
    buy_price = weighted_center * safety_discount
    overvalued_price = weighted_center * 1.4

    fcf_yield = safe_div(actual_fcf, facts.market_cap)
    ocf_yield = safe_div(facts.ocf, facts.market_cap)
    normalized_fcf_yield = safe_div(normalized_fcf, facts.market_cap)
    target_fcf_yield = facts.ten_year_yield + 0.03
    cash_flow_anchor_price = safe_div(owner_earnings, facts.diluted_shares) / target_fcf_yield if facts.diluted_shares else 0
    reverse_growth = implied_growth_for_price(
        facts.price,
        max(owner_earnings, 1),
        facts.diluted_shares,
        facts.net_cash,
        assumptions["discount_rate"],
        assumptions["terminal_growth"],
        assumptions["risk_discount"],
    )
    reverse_growth_capped = reverse_growth > 0.349

    capex_ocf = safe_div(facts.capex, facts.ocf)
    cash_flow_confidence = confidence_label(terminal_dependency, capex_ocf, assumptions["risk_discount"])
    v3 = build_v3_models(facts, assumptions, scenarios, weighted_center, owner_earnings, actual_fcf)
    fair_low = v3["market_range"]["low"]
    fair_high = v3["market_range"]["high"]
    fair_center = v3["market_range"]["base"]
    buy_price = (v3["buy_range"]["low"] + v3["buy_range"]["high"]) / 2
    overvalued_price = v3["high_risk_price"]
    confidence = v3["consistency"]["level"]
    judgement = judge_v3(facts.price, v3["buy_range"], v3["market_range"], v3["optimistic_range"])
    most_sensitive = "未来现金流增长率" if reverse_growth > assumptions["base_growth"] + 0.03 else "CAPEX 是否能转化为现金流"
    if v3["style"] in {"high_growth_profitable_tech", "high_growth_software"}:
        most_sensitive = "未来 1-3 年收入增速和利润率是否兑现"

    return {
        "ticker": facts.ticker,
        "fiscal_year": facts.fiscal_year,
        "methodology_version": "V3.0 multi-model valuation",
        "valuation_lens": "多模型综合估值",
        "assumptions": assumptions,
        "quality_score": quality_score,
        "confidence": confidence,
        "cash_flow_confidence": cash_flow_confidence,
        "current_price": facts.price,
        "market_cap": facts.market_cap,
        "net_cash": facts.net_cash,
        "quality_breakdown": quality_breakdown,
        "cash_flows": {
            "actual_fcf": actual_fcf,
            "normalized_fcf": normalized_fcf,
            "owner_earnings": owner_earnings,
            "ocf": facts.ocf,
        },
        "yields": {
            "fcf_yield": fcf_yield,
            "normalized_fcf_yield": normalized_fcf_yield,
            "ocf_yield": ocf_yield,
            "target_fcf_yield": target_fcf_yield,
            "cash_flow_anchor_price": cash_flow_anchor_price,
        },
        "sanity_metrics": {
            "price_to_sales": price_to_sales,
            "price_to_actual_fcf": price_to_actual_fcf,
            "price_to_owner_earnings": price_to_owner_earnings,
            "operating_margin": safe_div(facts.operating_income, facts.revenue),
            "sbc_to_revenue": safe_div(facts.sbc, facts.revenue),
            "capex_to_ocf": capex_ocf,
        },
        "scenarios": scenarios,
        "cash_flow_fair_value_center": weighted_center,
        "fair_value_center": fair_center,
        "fair_value_range": {"low": fair_low, "high": fair_high},
        "margin_of_safety_buy_price": {"single": buy_price, "low": v3["buy_range"]["low"], "high": v3["buy_range"]["high"]},
        "overvalued_price": overvalued_price,
        "judgement": judgement,
        "v3_summary": {
            "style": v3["style"],
            "style_label": v3["style_label"],
            "conservative_range": v3["conservative_range"],
            "market_reasonable_range": v3["market_range"],
            "optimistic_growth_range": v3["optimistic_range"],
            "buy_range": v3["buy_range"],
            "high_risk_overvaluation_price": v3["high_risk_price"],
            "model_consistency": v3["consistency"],
            "forward_inputs": v3["forward_inputs"],
        },
        "valuation_models": v3["models"],
        "reverse_dcf": {
            "implied_5y_growth": reverse_growth,
            "plain_language": f"当前价格大约要求未来 5 年股东现金流年化增长 {reverse_growth * 100:.1f}%。",
            "requires_bull_case": reverse_growth > assumptions["base_growth"] + 0.04,
            "is_capped": reverse_growth_capped,
        },
        "terminal_dependency": terminal_dependency,
        "plain_language": {
            "headline": f"{facts.ticker} 当前综合估值判断：{judgement}。",
            "expectation": (
                "当前价格高到已经超过现金流模型反推增长上限，说明它非常依赖未来盈利兑现和市场成长股口径。"
                if reverse_growth_capped
                else f"系统把现金流、forward earnings、成长调整和市场倍数放在一起看，当前价格处在“{v3['consistency']['price_position']}”。"
            ),
            "conservative_action": f"如果你偏保守，可以重点观察 ${v3['buy_range']['low']:.0f} - ${v3['buy_range']['high']:.0f} 的保守买入区。",
            "watch": [
                "OCF 是否继续增长，而不是只看利润表利润。",
                "CAPEX 增加后，未来两三年是否带来更高现金流。",
                "监管、技术替代或竞争是否让长期增长假设变差。",
            ],
            "most_sensitive": most_sensitive,
            "sanity_check": (
                f"按当前市值计算，P/FCF 约 {price_to_actual_fcf:.1f}x，P/S 约 {price_to_sales:.1f}x。"
                f"系统估算的 forward EPS 约 ${v3['forward_inputs']['forward_eps_estimate']:.2f}，并纳入 forward PE 等市场口径自动综合，不需要你自己判断模型冲突。"
            ),
            "model_limits": [
                "V3.0 会把现金流 DCF、forward PE、PEG、EV multiples 放在一起看，但免费数据下的 forward EPS 仍是系统估算值。",
                "高成长公司最关键的是未来收入增速、利润率和竞争格局，单个公式不能替代跟踪。",
                "成熟回购型公司需要结合回购、EPS 增长和股东回报一起看。",
            ],
            "v3_conclusion": (
                f"综合合理区间约 ${fair_low:.0f} - ${fair_high:.0f}，保守买入区约 "
                f"${v3['buy_range']['low']:.0f} - ${v3['buy_range']['high']:.0f}，"
                f"高于 ${v3['high_risk_price']:.0f} 后需要非常乐观的未来假设。"
            ),
            "model_consistency": v3["consistency"]["plain_language"],
        },
        "formula_notes": {
            "actual_fcf": "实际 FCF = OCF - CAPEX，代表当年扣除资本开支后的剩余现金。",
            "owner_earnings": "Owner Earnings = OCF - 维护性 CAPEX - SBC 调整，更接近股东真正拥有的现金。",
            "dcf": "DCF 把未来 10 年现金流和终值折现回今天，再加上净现金；V3.0 中它是保守锚点之一。",
            "forward_pe": "Forward P/E = 未来一年估算 EPS × 合理市盈率，更接近市场看科技和消费复利公司的方式。",
            "ev_multiples": "EV/Revenue 与 EV/EBITDA 是市场同行估值口径，适合校验成长股和软件公司的价格是否仍可解释。",
            "reverse_dcf": "反向 DCF 不是预测未来，而是反推当前股价要求未来做到什么。",
        },
    }
