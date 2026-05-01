from __future__ import annotations

from typing import Any

from .dcf import run_three_stage_dcf
from .models import Facts, ModelOutput, clamp, safe_div


MARKET_MODEL_KEYS = {"forward_pe", "peg", "ev_ebitda", "ev_sales", "rule_of_40_ev_sales", "fcf_yield", "mid_cycle_earnings"}

LAYER_WEIGHTS: dict[str, dict[str, float]] = {
    "high_growth_software": {"intrinsic": 0.15, "market": 0.75, "analyst": 0.10},
    "high_growth_profitable_tech": {"intrinsic": 0.20, "market": 0.70, "analyst": 0.10},
    "platform_compounder": {"intrinsic": 0.30, "market": 0.60, "analyst": 0.10},
    "mature_compounder": {"intrinsic": 0.40, "market": 0.50, "analyst": 0.10},
    "consumer_staples": {"intrinsic": 0.42, "market": 0.48, "analyst": 0.10},
    "cyclical": {"intrinsic": 0.30, "market": 0.60, "analyst": 0.10},
    "financial": {"intrinsic": 0.00, "market": 0.85, "analyst": 0.15},
    "default": {"intrinsic": 0.35, "market": 0.55, "analyst": 0.10},
}


def percentile(values: list[float], pct: float) -> float:
    values = sorted(value for value in values if value > 0)
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(values) - 1)
    fraction = rank - low
    return values[low] * (1 - fraction) + values[high] * fraction


def aggregate_model_range(models: list[ModelOutput], allowed: set[str] | None = None) -> dict[str, Any]:
    valid = [
        model for model in models
        if model.base > 0 and model.weight > 0 and (allowed is None or model.model in allowed)
    ]
    total = sum(model.weight for model in valid)
    if not valid or total <= 0:
        return {"range_low": 0.0, "base": 0.0, "range_high": 0.0, "models": []}
    return {
        "range_low": sum(model.bear * model.weight for model in valid) / total,
        "base": sum(model.base * model.weight for model in valid) / total,
        "range_high": sum(model.bull * model.weight for model in valid) / total,
        "models": [model.model for model in valid],
        "total_model_weight": total,
    }


def build_intrinsic_probability_range(
    facts: Facts,
    base_scenario: dict[str, float],
    capex_split: dict[str, Any],
    company_type: str,
) -> dict[str, Any]:
    growth_vol = 0.08 if company_type in {"high_growth_software", "high_growth_profitable_tech", "unprofitable_growth"} else 0.05
    margin_vol = 0.05 if company_type in {"high_growth_software", "unprofitable_growth"} else 0.035
    discount_vol = 0.014 if company_type in {"high_growth_software", "high_growth_profitable_tech"} else 0.010
    terminal_vol = 0.006

    values: list[float] = []
    for growth_step in [-1.0, -0.5, 0.0, 0.5, 1.0]:
        for margin_step in [-1.0, 0.0, 1.0]:
            for discount_step in [-1.0, 0.0, 1.0]:
                for terminal_step in [-1.0, 0.0, 1.0]:
                    scenario = dict(base_scenario)
                    scenario["revenue_cagr_5y"] = clamp(
                        float(base_scenario["revenue_cagr_5y"]) + growth_step * growth_vol,
                        -0.15,
                        0.60,
                    )
                    scenario["fcf_margin_terminal"] = clamp(
                        float(base_scenario["fcf_margin_terminal"]) + margin_step * margin_vol,
                        0.02,
                        0.60,
                    )
                    scenario["operating_margin_terminal"] = clamp(
                        float(base_scenario["operating_margin_terminal"]) + margin_step * margin_vol,
                        0.0,
                        0.70,
                    )
                    scenario["discount_rate"] = max(0.055, float(base_scenario["discount_rate"]) + discount_step * discount_vol)
                    terminal_growth = float(base_scenario["terminal_growth"]) + terminal_step * terminal_vol
                    scenario["terminal_growth"] = clamp(terminal_growth, 0.0, min(0.055, scenario["discount_rate"] - 0.012))
                    values.append(run_three_stage_dcf(facts, scenario, capex_split)["per_share"])

    low = percentile(values, 0.10)
    base = percentile(values, 0.50)
    high = percentile(values, 0.90)
    return {
        "range_low": min(low, base),
        "base": base,
        "range_high": max(high, base),
        "p10": low,
        "p50": base,
        "p90": high,
        "sample_count": len(values),
        "method": "deterministic_monte_carlo_dcf",
        "key_uncertainties": ["revenue_cagr_5y", "fcf_margin_terminal", "discount_rate", "terminal_growth"],
    }


def extract_analyst_target_range(manual_overrides: dict[str, Any]) -> dict[str, Any] | None:
    raw = manual_overrides.get("analyst_target") or manual_overrides.get("analyst_price_target")
    if isinstance(raw, dict):
        base = raw.get("target_median") or raw.get("target_consensus") or raw.get("base") or raw.get("median")
        low = raw.get("target_low") or raw.get("low")
        high = raw.get("target_high") or raw.get("high")
    else:
        base = manual_overrides.get("analyst_target_median") or manual_overrides.get("analyst_target_consensus")
        low = manual_overrides.get("analyst_target_low")
        high = manual_overrides.get("analyst_target_high")
    if base in (None, "", 0):
        return None
    base = float(base)
    low = float(low) if low not in (None, "") else base * 0.85
    high = float(high) if high not in (None, "") else base * 1.15
    return {
        "range_low": min(low, base),
        "base": base,
        "range_high": max(high, base),
        "method": "manual_or_external_analyst_consensus",
        "source": manual_overrides.get("analyst_target_source", "manual_or_external"),
    }


def _available_layer_weights(
    company_type: str,
    intrinsic: dict[str, Any],
    market: dict[str, Any],
    analyst: dict[str, Any] | None,
    data_quality: dict[str, Any],
) -> dict[str, float]:
    weights = dict(LAYER_WEIGHTS.get(company_type, LAYER_WEIGHTS["default"]))
    if not intrinsic.get("base"):
        weights["intrinsic"] = 0.0
    if not market.get("base"):
        weights["market"] = 0.0
    if not analyst:
        weights["analyst"] = 0.0
    if data_quality.get("system_estimates") and not analyst and weights.get("intrinsic", 0) > 0:
        shift = min(0.08, weights.get("market", 0) * 0.15)
        weights["market"] = max(0.0, weights.get("market", 0) - shift)
        weights["intrinsic"] = weights.get("intrinsic", 0) + shift
    total = sum(weights.values())
    if total <= 0:
        return {"intrinsic": 1.0, "market": 0.0, "analyst": 0.0}
    return {key: value / total for key, value in weights.items()}


def combine_layered_target(
    facts: Facts,
    company_type: str,
    models: list[ModelOutput],
    base_scenario: dict[str, float],
    capex_split: dict[str, Any],
    manual_overrides: dict[str, Any],
    data_quality: dict[str, Any],
) -> tuple[dict[str, float], dict[str, Any]]:
    intrinsic = build_intrinsic_probability_range(facts, base_scenario, capex_split, company_type)
    market = aggregate_model_range(models, MARKET_MODEL_KEYS)
    analyst = extract_analyst_target_range(manual_overrides)
    weights = _available_layer_weights(company_type, intrinsic, market, analyst, data_quality)
    layers = {"intrinsic": intrinsic, "market": market, "analyst": analyst, "weights": weights}

    def combined(key: str) -> float:
        value = intrinsic.get(key, 0) * weights["intrinsic"]
        value += market.get(key, 0) * weights["market"]
        if analyst:
            value += analyst.get(key, 0) * weights["analyst"]
        return value

    base = combined("base")
    low = min(combined("range_low"), base)
    high = max(combined("range_high"), base)
    target = {
        "bear": low,
        "base": base,
        "bull": high,
        "range_low": low,
        "range_high": high,
        "upside_base": safe_div(base - facts.price, facts.price),
        "upside_bull": safe_div(high - facts.price, facts.price),
        "downside_bear": safe_div(low - facts.price, facts.price),
    }
    return target, layers
