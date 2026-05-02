from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..discovery import (
    list_stock_pools,
    refresh_qqq_holdings_cache,
    refresh_stock_pool_cache,
    scan_qqq_candidates,
    scan_stock_pool_candidates,
)
from ..schemas import DiscoveryScanRequest
from ..schemas import StockPoolMembersRequest


router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.get("/pools")
def stock_pools() -> list[dict[str, Any]]:
    return list_stock_pools()


@router.get("/latest")
def latest_discovery(pool_id: str = "sp500", limit: int = 50) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 520))
    try:
        return scan_stock_pool_candidates(pool_id=pool_id, limit=safe_limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"发现雷达加载失败：{exc}") from exc


@router.post("/scan")
def scan_pool(payload: DiscoveryScanRequest) -> dict[str, Any]:
    try:
        return scan_stock_pool_candidates(
            pool_id=payload.pool_id,
            limit=payload.limit,
            refresh_holdings=payload.refresh_holdings,
            refresh_financials=payload.refresh_financials,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"发现雷达扫描失败：{exc}") from exc


@router.post("/pools/{pool_id}/refresh")
def refresh_pool(pool_id: str, limit: int = 50) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 520))
    try:
        return refresh_stock_pool_cache(pool_id=pool_id, limit=safe_limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"股票池成分刷新失败：{exc}") from exc


@router.put("/pools/{pool_id}/members")
def update_custom_pool_members(pool_id: str, payload: StockPoolMembersRequest) -> dict[str, Any]:
    normalized_tickers = []
    seen = set()
    for raw in payload.tickers:
        ticker = raw.strip().upper().replace(".", "-")
        if ticker and ticker not in seen:
            normalized_tickers.append(ticker)
            seen.add(ticker)
    if not normalized_tickers:
        raise HTTPException(status_code=422, detail="自定义股票池至少需要 1 个 ticker")
    pool = pool_id.lower()
    holdings = [
        {
            "rank": index,
            "ticker": ticker,
            "name": ticker,
            "weight": 0,
            "security_type": "Common Stock",
            "raw": {"manual": True},
        }
        for index, ticker in enumerate(normalized_tickers, start=1)
    ]
    try:
        refresh_payload = {
            "pool_id": pool,
            "name": payload.name or ("自定义池" if pool == "custom" else pool.upper()),
            "as_of": "",
            "source": "manual",
            "total_holdings": len(holdings),
            "default_limit": min(50, len(holdings)),
            "holdings": holdings,
        }
        from ..discovery import save_stock_pool_members

        save_stock_pool_members(refresh_payload)
        return refresh_payload
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"自定义股票池保存失败：{exc}") from exc


@router.get("/qqq")
def qqq_discovery(limit: int = 30) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 105))
    try:
        return scan_qqq_candidates(limit=safe_limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"发现池加载失败：{exc}") from exc


@router.post("/qqq/holdings/refresh")
def refresh_qqq_holdings(limit: int = 30) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 105))
    try:
        return refresh_qqq_holdings_cache(limit=safe_limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"QQQ 持仓刷新失败：{exc}") from exc


@router.post("/qqq/scan")
def scan_qqq(payload: DiscoveryScanRequest) -> dict[str, Any]:
    try:
        return scan_qqq_candidates(
            limit=payload.limit,
            refresh_holdings=payload.refresh_holdings,
            refresh_financials=payload.refresh_financials,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"QQQ 发现扫描失败：{exc}") from exc
