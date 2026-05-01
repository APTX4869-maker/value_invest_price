from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..discovery import refresh_qqq_holdings_cache, scan_qqq_candidates
from ..schemas import DiscoveryScanRequest


router = APIRouter(prefix="/api/discovery", tags=["discovery"])


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
