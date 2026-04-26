from __future__ import annotations

from typing import Any

from .models import Facts, ModelOutput, clamp, safe_div


BASE_WEIGHTS: dict[str, dict[str, float]] = {
    "high_growth_profitable_tech": {"forward_pe": 0.30, "ev_ebitda": 0.25, "three_stage_dcf": 0.25, "peg": 0.10, "fcf_yield": 0.05, "reverse_check": 0.05, "ev_sales": 0.00},
    "high_growth_software": {"ev_sales": 0.35, "rule_of_40_ev_sales": 0.20, "forward_pe": 0.15, "three_stage_dcf": 0.10, "reverse_check": 0.10, "fcf_yield": 0.05, "peg": 0.05},
    "platform_compounder": {"three_stage_dcf": 0.30, "forward_pe": 0.25, "ev_ebitda": 0.20, "fcf_yield": 0.15, "reverse_check": 0.05, "peg": 0.05},
    "mature_compounder": {"fcf_yield": 0.30, "forward_pe": 0.25, "three_stage_dcf": 0.25, "ev_ebitda": 0.15, "reverse_check": 0.05},
    "consumer_staples": {"fcf_yield": 0.30, "forward_pe": 0.25, "three_stage_dcf": 0.20, "ev_ebitda": 0.15, "reverse_check": 0.05, "dividend_growth": 0.05},
    "cyclical": {"mid_cycle_earnings": 0.35, "three_stage_dcf": 0.20, "ev_ebitda": 0.20, "fcf_yield": 0.15, "reverse_check": 0.10},
    "default": {"three_stage_dcf": 0.35, "forward_pe": 0.20, "ev_ebitda": 0.15, "fcf_yield": 0.20, "reverse_check": 0.10},
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
