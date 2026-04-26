from __future__ import annotations

from typing import Any

from .models import CompanyType, Facts, clamp, safe_div


BASE_MAINTENANCE_RATIOS: dict[str, float] = {
    "high_growth_profitable_tech": 0.45,
    "high_growth_software": 0.15,
    "platform_compounder": 0.42,
    "mature_compounder": 0.65,
    "consumer_staples": 0.75,
    "cyclical": 0.55,
    "financial": 0.30,
    "unprofitable_growth": 0.25,
    "default": 0.50,
}


def _recent_capex_ratio(annual_history: list[dict[str, Any]]) -> tuple[float, float]:
    rows = [row for row in sorted(annual_history, key=lambda item: item.get("fiscal_year") or 0) if row.get("ocf")]
    if len(rows) < 3:
        return 0.0, 0.0
    older = rows[:-2]
    recent = rows[-2:]
    older_ratio = sum(safe_div(abs(r.get("capex") or 0), r.get("ocf") or 0) for r in older) / max(1, len(older))
    recent_ratio = sum(safe_div(abs(r.get("capex") or 0), r.get("ocf") or 0) for r in recent) / 2
    return older_ratio, recent_ratio


def split_capex(
    facts: Facts,
    annual_history: list[dict[str, Any]],
    company_type: CompanyType,
    user_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if user_override and user_override.get("maintenance_capex") is not None:
        maintenance = max(0.0, float(user_override["maintenance_capex"]))
        return {
            "maintenance_capex": min(maintenance, facts.capex),
            "growth_capex": max(0.0, facts.capex - maintenance),
            "maintenance_ratio": safe_div(maintenance, facts.capex),
            "method": "user_override",
            "confidence": "high",
            "warnings": [],
        }
    if user_override and user_override.get("maintenance_capex_ratio") is not None:
        ratio = clamp(float(user_override["maintenance_capex_ratio"]), 0, 1)
    else:
        ratio = BASE_MAINTENANCE_RATIOS.get(company_type, BASE_MAINTENANCE_RATIOS["default"])

    older_ratio, recent_ratio = _recent_capex_ratio(annual_history)
    warnings: list[str] = []
    confidence = "medium"
    method = f"default_{company_type}_ratio"
    if older_ratio and recent_ratio > older_ratio * 1.45 and recent_ratio > 0.30:
        ratio *= 0.72
        confidence = "medium"
        method = "capex_spike_adjusted"
        warnings.append("近两年 CAPEX/OCF 明显上升，系统将一部分识别为成长 CAPEX 或 AI CAPEX 周期。")
    if company_type in {"high_growth_software", "unprofitable_growth"}:
        confidence = "medium_high"
    if not annual_history:
        confidence = "low"
        warnings.append("缺少多年 CAPEX 历史，维护性 CAPEX 拆分可信度较低。")

    ratio = clamp(ratio, 0.05, 0.90)
    maintenance = facts.capex * ratio
    return {
        "maintenance_capex": maintenance,
        "growth_capex": max(0.0, facts.capex - maintenance),
        "maintenance_ratio": ratio,
        "method": method,
        "confidence": confidence,
        "warnings": warnings,
    }
