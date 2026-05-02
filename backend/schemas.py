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
    pool_id: str = "sp500"
    limit: int = Field(default=50, ge=1, le=520)
    refresh_holdings: bool = False
    refresh_financials: bool = False


class StockPoolMembersRequest(BaseModel):
    name: str | None = None
    tickers: list[str] = Field(default_factory=list)


class ResearchQueueRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    name: str | None = None
    status: str = "candidate"
    tags: list[str] = Field(default_factory=list)
    next_action: str = ""
    entry_reason: str = ""
    source: str = "manual"
    priority_score: float | None = None
    discovery_label: str = ""


class ResearchQueuePatchRequest(BaseModel):
    status: str | None = None
    tags: list[str] | None = None
    next_action: str | None = None
    entry_reason: str | None = None
    priority_score: float | None = None
    discovery_label: str | None = None
    ignored: bool | None = None


class InvestmentMemoRequest(BaseModel):
    conclusion: str = "不确定"
    attention_reason: str = ""
    thesis: list[str] = Field(default_factory=list)
    business_moat: str = ""
    financial_quality: str = ""
    valuation_view: str = ""
    bear_case: str = ""
    review_triggers: list[str] = Field(default_factory=list)
    free_notes: str = ""
    snapshot_id: int | None = None
