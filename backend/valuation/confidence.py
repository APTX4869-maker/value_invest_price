from __future__ import annotations

from typing import Any

from .models import Facts, ModelOutput, clamp, safe_div


BASE_WEIGHTS: dict[str, dict[str, float]] = {
    "high_growth_profitable_tech": {"forward_pe": 0.32, "ev_ebitda": 0.26, "three_stage_dcf": 0.18, "peg": 0.12, "ev_sales": 0.07, "fcf_yield": 0.05, "reverse_check": 0.00},
    "high_growth_software": {"ev_sales": 0.35, "rule_of_40_ev_sales": 0.22, "forward_pe": 0.18, "peg": 0.10, "three_stage_dcf": 0.08, "fcf_yield": 0.04, "ev_ebitda": 0.03, "reverse_check": 0.00},
    "platform_compounder": {"forward_pe": 0.28, "three_stage_dcf": 0.22, "ev_ebitda": 0.20, "fcf_yield": 0.12, "ev_sales": 0.10, "peg": 0.08, "reverse_check": 0.00},
    "mature_compounder": {"fcf_yield": 0.32, "forward_pe": 0.28, "three_stage_dcf": 0.25, "ev_ebitda": 0.15, "reverse_check": 0.00},
    "consumer_staples": {"fcf_yield": 0.32, "forward_pe": 0.28, "three_stage_dcf": 0.20, "ev_ebitda": 0.15, "dividend_growth": 0.05, "reverse_check": 0.00},
    "cyclical": {"mid_cycle_earnings": 0.40, "ev_ebitda": 0.25, "three_stage_dcf": 0.20, "fcf_yield": 0.15, "reverse_check": 0.00},
    "memory_semiconductor": {"forward_pe": 0.28, "ev_ebitda": 0.24, "ev_sales": 0.16, "fcf_yield": 0.12, "three_stage_dcf": 0.12, "mid_cycle_earnings": 0.08, "reverse_check": 0.00},
    "financial": {"forward_pe": 0.82, "ev_sales": 0.18, "three_stage_dcf": 0.00, "ev_ebitda": 0.00, "fcf_yield": 0.00, "reverse_check": 0.00},
    "default": {"three_stage_dcf": 0.30, "forward_pe": 0.25, "fcf_yield": 0.22, "ev_ebitda": 0.18, "ev_sales": 0.05, "reverse_check": 0.00},
}


def normalize_model_weights(models: list[ModelOutput]) -> list[ModelOutput]:
    valid = [model for model in models if model.base > 0 and model.weight > 0]
    total = sum(model.weight for model in valid)
    if total <= 0:
        return models
    for model in valid:
        model.weight = model.weight / total
    for model in models:
        if model not in valid:
            model.weight = 0.0
    return models


def apply_dynamic_model_weights(
    models: list[ModelOutput],
    forward: dict[str, Any],
    multiples: dict[str, Any],
    dcf: dict[str, Any],
) -> list[ModelOutput]:
    """Adjust static model weights for source quality and model fragility."""
    system_estimates = {
        key for key, item in forward.items()
        if isinstance(item, dict) and item.get("source") == "system_estimate"
    }
    multiples_sources = multiples.get("sources", {})
    percentiles = multiples.get("percentiles", {})
    history_available = any(value != "data_missing" for value in percentiles.values())

    for model in models:
        if model.model == "reverse_check":
            model.weight = 0.0
            continue

        multiplier = 1.0
        sources = model.data_sources or {}
        model_forward_keys = {
            key for key, value in sources.items()
            if value == "system_estimate" and key.startswith("forward")
        }
        if model_forward_keys or any(source == "system_estimate" for source in sources.values()):
            multiplier *= 0.82
        if any(source in {"manual_consensus", "db_consensus"} for source in sources.values()):
            multiplier *= 1.12
        if model.model in {"forward_pe", "peg"} and {"eps_next_year", "eps_2y", "long_term_eps_growth"} & system_estimates:
            multiplier *= 0.90
        if model.model in {"ev_sales", "rule_of_40_ev_sales"} and multiples_sources.get("ev_sales") == "default_fallback_adjusted":
            multiplier *= 0.88
        if model.model == "ev_ebitda" and multiples_sources.get("ev_ebitda") == "default_fallback_adjusted":
            multiplier *= 0.90
        if history_available and model.model in {"forward_pe", "ev_sales", "ev_ebitda", "fcf_yield"}:
            multiplier *= 1.08
        if model.model == "three_stage_dcf" and dcf.get("terminal_dependency", 0) > 0.72:
            multiplier *= 0.82

        model.weight *= multiplier

    return normalize_model_weights(models)


def aggregate_targets(models: list[ModelOutput]) -> dict[str, float]:
    valid = [model for model in models if model.base > 0 and model.weight > 0]
    total = sum(model.weight for model in valid)
    if not valid or total <= 0:
        return {"bear": 0.0, "base": 0.0, "bull": 0.0}
    return {
        "bear": sum(model.bear * model.weight for model in valid) / total,
        "base": sum(model.base * model.weight for model in valid) / total,
        "bull": sum(model.bull * model.weight for model in valid) / total,
    }


def confidence_score(
    facts: Facts,
    models: list[ModelOutput],
    data_quality: dict[str, Any],
    dcf: dict[str, Any],
) -> dict[str, Any]:
    bases = [model.base for model in models if model.base > 0 and model.weight > 0]
    reasons: list[str] = []
    score = float(data_quality.get("score", 60))
    if len(bases) >= 2:
        median_base = sorted(bases)[len(bases) // 2]
        spread = safe_div(max(bases) - min(bases), median_base)
        score -= clamp(spread / 1.2, 0, 1) * 20
        if spread > 0.9:
            reasons.append("不同模型输出分歧较大。")
    else:
        score -= 25
        reasons.append("可用估值模型太少。")
    if dcf.get("terminal_dependency", 0) > 0.72:
        score -= 8
        reasons.append("DCF 终值占比较高，长期假设影响很大。")
    if facts.diluted_shares <= 0 or facts.price <= 0:
        score -= 30
        reasons.append("缺少股价或稀释股数。")
    score = clamp(score, 20, 95)
    return {
        "score": round(score),
        "level": "high" if score >= 78 else "medium_high" if score >= 68 else "medium" if score >= 52 else "low",
        "reasons": reasons + data_quality.get("warnings", []),
    }


def rating_from_targets(upside_base: float, confidence: dict[str, Any], reverse_difficulty: str) -> str:
    score = confidence.get("score", 0)
    if score < 40:
        return "too_uncertain"
    if upside_base > 0.30 and score >= 70:
        return "buy"
    if upside_base > 0.10 and score >= 60:
        return "accumulate"
    if -0.10 <= upside_base <= 0.10:
        return "hold"
    if upside_base < -0.20 and reverse_difficulty in {"aggressive", "very_aggressive"}:
        return "sell_or_avoid"
    if upside_base < -0.10:
        return "trim"
    return "hold"
