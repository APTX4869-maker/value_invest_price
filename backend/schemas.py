from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AddCompanyRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    name: str | None = None


class ValuationRequest(BaseModel):
    ticker: str
    assumptions: dict[str, Any] = Field(default_factory=dict)


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
