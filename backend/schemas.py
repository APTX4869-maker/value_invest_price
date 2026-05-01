from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AddCompanyRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    name: str | None = None


class ValuationRequest(BaseModel):
    ticker: str
    assumptions: dict[str, Any] = Field(default_factory=dict)


class ConsensusEstimates(BaseModel):
    revenue_next_year: float | None = None
    revenue_2y: float | None = None
    eps_next_year: float | None = None
    eps_2y: float | None = None
    ebitda_next_year: float | None = None
    operating_income_next_year: float | None = None
    fcf_next_year: float | None = None
    long_term_eps_growth: float | None = None
    source: str = "manual_or_unknown"
    updated_at: str | None = None


class ValuationScenarioInput(BaseModel):
    revenue_cagr_5y: float | None = None
    operating_margin_terminal: float | None = None
    fcf_margin_terminal: float | None = None
    discount_rate: float | None = None
    terminal_growth: float | None = None
    exit_pe: float | None = None
    exit_ev_ebitda: float | None = None
    exit_ev_sales: float | None = None
    probability: float | None = None


class ValuationCalculatorRequest(BaseModel):
    ticker: str
    horizon: Literal["12m", "3y", "5y"] = "12m"
    consensus: ConsensusEstimates | None = None
    bear: ValuationScenarioInput | None = None
    base: ValuationScenarioInput | None = None
    bull: ValuationScenarioInput | None = None
    use_dynamic_multiples: bool = True
    use_reverse_dcf: bool = True
    use_capex_split: bool = True
    manual_overrides: dict[str, Any] = Field(default_factory=dict)


class SnapshotRequest(BaseModel):
    ticker: str
    title: str = "估值快照"
    inputs: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any]


class NoteRequest(BaseModel):
    content: str


class SettingsRequest(BaseModel):
    settings: dict[str, Any]


class PeersRequest(BaseModel):
    peers: list[str]


class PriceOverrideRequest(BaseModel):
    price: float | None = None


class DiscoveryScanRequest(BaseModel):
    limit: int = Field(default=30, ge=1, le=105)
    refresh_holdings: bool = False
    refresh_financials: bool = False
