from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Literal


CompanyType = Literal[
    "high_growth_profitable_tech",
    "high_growth_software",
    "platform_compounder",
    "mature_compounder",
    "consumer_staples",
    "cyclical",
    "financial",
    "unprofitable_growth",
    "default",
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_div(a: float | int | None, b: float | int | None) -> float:
    if not a or not b:
        return 0.0
    return float(a) / float(b)


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
    annual_history: list[dict[str, Any]] = field(default_factory=list)
    company_profile: dict[str, Any] = field(default_factory=dict)

    @property
    def market_cap(self) -> float:
        return self.price * self.diluted_shares

    @property
    def debt(self) -> float:
        return self.debt_current + self.debt_long_term

    @property
    def net_cash(self) -> float:
        return self.cash + self.short_investments - self.debt

    @property
    def enterprise_value(self) -> float:
        return max(0.0, self.market_cap - self.net_cash)

    @property
    def actual_fcf(self) -> float:
        return self.ocf - self.capex

    @property
    def operating_margin(self) -> float:
        return safe_div(self.operating_income, self.revenue)

    @property
    def fcf_margin(self) -> float:
        return safe_div(self.actual_fcf, self.revenue)


@dataclass
class SourcedValue:
    value: float | None
    source: str
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "source": self.source, "confidence": self.confidence}


@dataclass
class ForwardEstimates:
    revenue_next_year: SourcedValue
    revenue_2y: SourcedValue
    eps_next_year: SourcedValue
    eps_2y: SourcedValue
    ebitda_next_year: SourcedValue
    operating_income_next_year: SourcedValue
    fcf_next_year: SourcedValue
    long_term_eps_growth: SourcedValue

    def to_dict(self) -> dict[str, Any]:
        return {
            "revenue_next_year": self.revenue_next_year.to_dict(),
            "revenue_2y": self.revenue_2y.to_dict(),
            "eps_next_year": self.eps_next_year.to_dict(),
            "eps_2y": self.eps_2y.to_dict(),
            "ebitda_next_year": self.ebitda_next_year.to_dict(),
            "operating_income_next_year": self.operating_income_next_year.to_dict(),
            "fcf_next_year": self.fcf_next_year.to_dict(),
            "long_term_eps_growth": self.long_term_eps_growth.to_dict(),
        }


@dataclass
class ModelOutput:
    model: str
    label: str
    bear: float
    base: float
    bull: float
    weight: float
    key_inputs: dict[str, Any]
    data_sources: dict[str, str]
    weight_reason: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "key": self.model,
            "label": self.label,
            "bear": self.bear,
            "base": self.base,
            "bull": self.bull,
            "low": self.bear,
            "high": self.bull,
            "weight": self.weight,
            "key_inputs": self.key_inputs,
            "data_sources": self.data_sources,
            "weight_reason": self.weight_reason,
            "warnings": self.warnings,
            "explanation": self.weight_reason,
        }


def build_facts(facts_dict: dict[str, Any]) -> Facts:
    raw = facts_dict.get("raw") or facts_dict.get("raw_json") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    company_profile = dict(facts_dict.get("company_profile") or {})
    if not company_profile and isinstance(raw, dict):
        sec_meta = raw.get("sec_meta") or {}
        sic_description = sec_meta.get("sic_description") or sec_meta.get("sicDescription") or ""
        company_profile = {
            "industry": sic_description,
            "sector": sic_description,
            "description": raw.get("sec_name") or "",
            "business_overview": " ".join((raw.get("normalization") or {}).get("notes") or []),
        }
    return Facts(
        ticker=str(facts_dict["ticker"]).upper(),
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
        annual_history=list(facts_dict.get("annual_history") or []),
        company_profile=company_profile,
    )
