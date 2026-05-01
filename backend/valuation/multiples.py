from __future__ import annotations

from statistics import median
from typing import Any

from .models import CompanyType, Facts, clamp, safe_div


FALLBACK_MULTIPLES: dict[str, dict[str, tuple[float, float, float]]] = {
    "high_growth_profitable_tech": {"pe": (32, 45, 60), "ev_ebitda": (26, 38, 52), "ev_sales": (12, 18, 25)},
    "high_growth_software": {"pe": (40, 60, 82), "ev_ebitda": (35, 55, 75), "ev_sales": (12, 20, 30)},
    "platform_compounder": {"pe": (18, 24, 31), "ev_ebitda": (12, 17, 23), "ev_sales": (4, 7, 10)},
    "mature_compounder": {"pe": (16, 22, 28), "ev_ebitda": (11, 15, 19), "ev_sales": (3, 5, 7)},
    "consumer_staples": {"pe": (18, 23, 28), "ev_ebitda": (12, 16, 20), "ev_sales": (3, 5, 7)},
    "cyclical": {"pe": (10, 14, 18), "ev_ebitda": (6, 9, 12), "ev_sales": (1, 2, 3)},
    "memory_semiconductor": {"pe": (8, 11, 15), "ev_ebitda": (5, 8, 12), "ev_sales": (2, 3.5, 5.5)},
    "unprofitable_growth": {"pe": (0, 0, 0), "ev_ebitda": (0, 0, 0), "ev_sales": (5, 9, 14)},
    "financial": {"pe": (9, 12, 15), "ev_ebitda": (0, 0, 0), "ev_sales": (2, 3, 4)},
    "default": {"pe": (14, 20, 26), "ev_ebitda": (8, 12, 16), "ev_sales": (2, 4, 6)},
}


def _triplet(values: list[float], fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    values = sorted(v for v in values if v and v > 0)
    if len(values) < 2:
        return fallback
    mid = median(values)
    return (max(fallback[0] * 0.75, mid * 0.75), mid, max(mid * 1.25, fallback[2] * 0.75))


def _peer_values(peer_snapshot: list[dict[str, Any]] | None, key: str) -> list[float]:
    return [float(item[key]) for item in peer_snapshot or [] if item.get(key)]


def _history_percentile(history: list[dict[str, Any]] | None, key: str, current: float) -> float | str:
    values = sorted(float(item[key]) for item in history or [] if item.get(key))
    if len(values) < 5 or current <= 0:
        return "data_missing"
    below = len([value for value in values if value <= current])
    return below / len(values)


def rule_of_40_adjustment(revenue_growth: float, fcf_margin: float) -> dict[str, Any]:
    rule = revenue_growth + fcf_margin
    if rule < 0.20:
        multiplier = 0.70
        label = "weak"
    elif rule < 0.40:
        multiplier = 1.00
        label = "neutral"
    elif rule < 0.60:
        multiplier = 1.25
        label = "strong"
    else:
        multiplier = 1.45
        label = "premium_sensitive"
    return {
        "rule_of_40": rule,
        "multiple_adjustment": multiplier,
        "label": label,
        "warning": "Rule of 40 超过 60，允许 premium，但估值对增长放缓高度敏感。" if rule >= 0.60 else None,
    }


def derive_reasonable_multiples(
    company_type: CompanyType,
    facts: Facts,
    forward: dict[str, Any],
    peer_snapshot: list[dict[str, Any]] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fallback = FALLBACK_MULTIPLES.get(company_type, FALLBACK_MULTIPLES["default"])
    revenue_next = (forward.get("revenue_next_year") or {}).get("value") or facts.revenue
    fcf_next = (forward.get("fcf_next_year") or {}).get("value") or facts.actual_fcf
    growth = safe_div(revenue_next, facts.revenue) - 1 if facts.revenue else 0
    fcf_margin = safe_div(fcf_next, revenue_next)
    rule = rule_of_40_adjustment(growth, fcf_margin)

    peer_pe = _triplet(_peer_values(peer_snapshot, "peer_forward_pe"), fallback["pe"])
    peer_ev_sales = _triplet(_peer_values(peer_snapshot, "peer_ev_sales"), fallback["ev_sales"])
    peer_ev_ebitda = _triplet(_peer_values(peer_snapshot, "peer_ev_ebitda"), fallback["ev_ebitda"])

    source = {
        "pe": "peer_snapshot" if peer_snapshot and _peer_values(peer_snapshot, "peer_forward_pe") else "default_fallback_adjusted",
        "ev_sales": "peer_snapshot" if peer_snapshot and _peer_values(peer_snapshot, "peer_ev_sales") else "default_fallback_adjusted",
        "ev_ebitda": "peer_snapshot" if peer_snapshot and _peer_values(peer_snapshot, "peer_ev_ebitda") else "default_fallback_adjusted",
    }

    if company_type in {"high_growth_software", "unprofitable_growth"}:
        ev_sales = tuple(value * rule["multiple_adjustment"] for value in peer_ev_sales)
    elif company_type == "memory_semiconductor":
        cycle_adjustment = clamp(1 + (growth - 0.15) * 0.45, 0.70, 1.35)
        ev_sales = tuple(value * cycle_adjustment for value in peer_ev_sales)
    else:
        ev_sales = peer_ev_sales
    pe_growth_adj = clamp(1 + (growth - 0.08), 0.70, 1.45 if company_type == "memory_semiconductor" else 1.30)
    pe = tuple(value * pe_growth_adj if value else 0 for value in peer_pe)
    ev_ebitda = tuple(value * clamp(1 + (facts.operating_margin - 0.20), 0.75, 1.30) if value else 0 for value in peer_ev_ebitda)

    forward_eps = (forward.get("eps_next_year") or {}).get("value") or 0
    forward_ebitda = (forward.get("ebitda_next_year") or {}).get("value") or 0
    current_forward_pe = safe_div(facts.price, forward_eps)
    current_ev_sales = safe_div(facts.enterprise_value, revenue_next)
    current_ev_ebitda = safe_div(facts.enterprise_value, forward_ebitda)
    current_fcf_yield = safe_div(fcf_next, facts.market_cap)

    return {
        "pe": pe,
        "ev_sales": ev_sales,
        "ev_ebitda": ev_ebitda,
        "sources": source,
        "rule_of_40": rule,
        "current": {
            "forward_pe": current_forward_pe,
            "ev_sales": current_ev_sales,
            "ev_ebitda": current_ev_ebitda,
            "fcf_yield": current_fcf_yield,
        },
        "percentiles": {
            "current_forward_pe_percentile": _history_percentile(history, "pe_forward", current_forward_pe),
            "current_ev_sales_percentile": _history_percentile(history, "ev_sales", current_ev_sales),
            "current_ev_ebitda_percentile": _history_percentile(history, "ev_ebitda", current_ev_ebitda),
            "current_fcf_yield_percentile": _history_percentile(history, "fcf_yield", current_fcf_yield),
        },
    }
