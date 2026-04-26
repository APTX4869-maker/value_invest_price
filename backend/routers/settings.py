from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..db import connect, dumps, loads
from ..schemas import SettingsRequest


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def settings() -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
    return {row["key"]: loads(row["value"]) for row in rows}


@router.put("")
def put_settings(payload: SettingsRequest) -> dict[str, Any]:
    with connect() as conn:
        for key, value in payload.settings.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, dumps(value)),
            )
        rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
    return {row["key"]: loads(row["value"]) for row in rows}
