import pytest
from fastapi import HTTPException

from backend.data_sources import DataSourceNetworkError, UnsupportedTickerError
from backend.routers.companies import refresh_company


def _use_default_settings(monkeypatch):
    monkeypatch.setattr("backend.routers.companies.get_setting", lambda _key, default=None: default)


def test_refresh_company_network_error_is_not_reported_as_ticker_error(monkeypatch):
    _use_default_settings(monkeypatch)

    def fail_fetch(*_args, **_kwargs):
        raise DataSourceNetworkError("SEC 数据源连接中断或超时，系统已自动重试：EOF occurred in violation of protocol")

    monkeypatch.setattr("backend.routers.companies.fetch_company_facts", fail_fetch)

    with pytest.raises(HTTPException) as exc_info:
        refresh_company("PLTR")

    assert exc_info.value.status_code == 503
    detail = exc_info.value.detail
    assert "临时连接问题" in detail
    assert "不一定代表 ticker 输错" in detail
    assert "PLTA" not in detail
    assert "杠杆 ETF" not in detail


def test_refresh_company_unsupported_ticker_keeps_security_type_guidance(monkeypatch):
    _use_default_settings(monkeypatch)

    def fail_fetch(*_args, **_kwargs):
        raise UnsupportedTickerError("SEC 没找到 ticker: PLTA")

    monkeypatch.setattr("backend.routers.companies.fetch_company_facts", fail_fetch)

    with pytest.raises(HTTPException) as exc_info:
        refresh_company("PLTA")

    assert exc_info.value.status_code == 404
    assert "上市公司普通股 ticker" in exc_info.value.detail
    assert "PLTA 是跟踪 PLTR 的杠杆 ETF" in exc_info.value.detail
