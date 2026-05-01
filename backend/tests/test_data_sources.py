import ssl
import urllib.error

import pytest

from backend.data_sources import (
    DataSourceNetworkError,
    build_annual_history,
    detect_reporting_currency,
    fetch_company_facts,
    fetch_price,
    fetch_qqq_holdings,
    fetch_ten_year_yield,
    get_json,
    latest_annual_value,
)


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.payload


def test_get_json_retries_transient_ssl_eof(monkeypatch):
    calls = {"count": 0}

    def fake_urlopen(_request, timeout=20):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.URLError(ssl.SSLEOFError("EOF occurred in violation of protocol"))
        return FakeResponse(b'{"ok": true}')

    monkeypatch.setattr("backend.data_sources.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("backend.data_sources.time.sleep", lambda _: None)

    result = get_json("https://data.sec.gov/example.json", "ua", retries=1)

    assert result == {"ok": True}
    assert calls["count"] == 2


def test_get_json_raises_friendly_network_error_after_retries(monkeypatch):
    def fake_urlopen(_request, timeout=20):
        raise urllib.error.URLError(ssl.SSLEOFError("EOF occurred in violation of protocol"))

    monkeypatch.setattr("backend.data_sources.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("backend.data_sources.time.sleep", lambda _: None)

    with pytest.raises(DataSourceNetworkError) as exc_info:
        get_json("https://www.sec.gov/files/company_tickers.json", "ua", retries=1)

    message = str(exc_info.value)
    assert "SEC 数据源" in message
    assert "系统已自动重试" in message
    assert "urlopen error" not in message


def test_fetch_qqq_holdings_normalizes_official_weights(monkeypatch):
    monkeypatch.setattr(
        "backend.data_sources.get_json",
        lambda url, user_agent: {
            "effectiveBusinessDate": "2026-04-29",
            "totalNumberOfHoldings": 105,
            "holdings": [
                {"ticker": "AAPL", "issuerName": "Apple Inc", "percentageOfTotalNetAssets": 7.05, "securityTypeName": "Common Stock", "currency": "USD"},
                {"ticker": "NVDA", "issuerName": "NVIDIA Corp", "percentageOfTotalNetAssets": 9.04, "securityTypeName": "Common Stock", "currency": "USD"},
            ],
        },
    )

    payload = fetch_qqq_holdings("ua")

    assert payload["as_of"] == "2026-04-29"
    assert payload["holdings"][0]["ticker"] == "NVDA"
    assert payload["holdings"][0]["weight"] == 0.0904
    assert payload["source"] == "Invesco QQQ official holdings API"


def test_latest_annual_value_ignores_quarterly_ytd_and_prefers_annual():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "form": "10-Q",
                                "start": "2025-01-01",
                                "end": "2025-09-30",
                                "val": 900,
                                "filed": "2025-11-01",
                            },
                            {
                                "form": "10-K",
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "val": 1200,
                                "filed": "2026-02-15",
                                "frame": "CY2025",
                            },
                        ]
                    }
                }
            }
        }
    }

    value, fiscal_year = latest_annual_value(facts, ["Revenues"], ["USD"])
    assert value == 1200
    assert fiscal_year == 2025


def test_latest_annual_value_supports_ifrs_full_taxonomy():
    facts = {
        "facts": {
            "ifrs-full": {
                "Revenue": {
                    "units": {
                        "USD": [
                            {
                                "form": "20-F",
                                "start": "2024-01-01",
                                "end": "2024-12-31",
                                "val": 456,
                                "filed": "2025-03-01",
                                "frame": "CY2024",
                            }
                        ]
                    }
                }
            }
        }
    }

    value, fiscal_year = latest_annual_value(facts, ["Revenue"], ["USD"])
    assert value == 456
    assert fiscal_year == 2024


def test_latest_annual_value_handles_balance_sheet_items_without_start_date():
    facts = {
        "facts": {
            "ifrs-full": {
                "CashAndCashEquivalents": {
                    "units": {
                        "USD": [
                            {
                                "form": "20-F",
                                "end": "2025-12-31",
                                "val": 321,
                                "filed": "2026-02-20",
                                "frame": "CY2025",
                            }
                        ]
                    }
                }
            }
        }
    }

    value, fiscal_year = latest_annual_value(facts, ["CashAndCashEquivalents"], ["USD"])
    assert value == 321
    assert fiscal_year == 2025


def test_build_annual_history_collects_recent_years():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "start": "2022-01-01", "end": "2022-12-31", "val": 100, "filed": "2023-02-01", "frame": "CY2022"},
                            {"form": "10-K", "start": "2023-01-01", "end": "2023-12-31", "val": 130, "filed": "2024-02-01", "frame": "CY2023"},
                        ]
                    }
                },
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "start": "2023-01-01", "end": "2023-12-31", "val": 40, "filed": "2024-02-01", "frame": "CY2023"}
                        ]
                    }
                },
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "start": "2023-01-01", "end": "2023-12-31", "val": 45, "filed": "2024-02-01", "frame": "CY2023"}
                        ]
                    }
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "start": "2023-01-01", "end": "2023-12-31", "val": -8, "filed": "2024-02-01", "frame": "CY2023"}
                        ]
                    }
                },
                "ShareBasedCompensation": {"units": {"USD": []}},
            }
        }
    }
    fields = {
        "revenue": (["Revenues"], ["USD"]),
        "operating_income": (["OperatingIncomeLoss"], ["USD"]),
        "ocf": (["NetCashProvidedByUsedInOperatingActivities"], ["USD"]),
        "capex": (["PaymentsToAcquirePropertyPlantAndEquipment"], ["USD"]),
        "sbc": (["ShareBasedCompensation"], ["USD"]),
    }

    history = build_annual_history(facts, fields)

    assert history[-1]["fiscal_year"] == 2023
    assert history[-1]["revenue"] == 130
    assert history[-1]["capex"] == 8


def test_detect_reporting_currency_returns_non_usd_unit():
    facts = {
        "facts": {
            "ifrs-full": {
                "Revenue": {
                    "units": {
                        "DKK": [
                            {
                                "form": "20-F",
                                "start": "2024-01-01",
                                "end": "2024-12-31",
                                "val": 100,
                                "filed": "2025-03-01",
                            }
                        ]
                    }
                }
            }
        }
    }

    assert detect_reporting_currency(facts, ["Revenue"]) == "DKK"


def test_fetch_company_facts_rejects_non_usd_reporting(monkeypatch):
    def fake_find_cik(_: str, __: str) -> tuple[str, str]:
        return "0000000001", "Test IFRS"

    def fake_get_json(url: str, _: str, timeout: int = 20) -> dict:
        if "companyfacts" in url:
            return {
                "facts": {
                    "ifrs-full": {
                        "Revenue": {"units": {"DKK": [{"form": "20-F", "start": "2024-01-01", "end": "2024-12-31", "val": 100, "filed": "2025-03-01"}]}},
                        "CashFlowsFromUsedInOperatingActivities": {"units": {"DKK": [{"form": "20-F", "start": "2024-01-01", "end": "2024-12-31", "val": 30, "filed": "2025-03-01"}]}},
                    }
                }
            }
        return {"name": "Test IFRS", "sic": "2834", "sicDescription": "Pharmaceutical", "fiscalYearEnd": "1231", "exchanges": ["NYSE"]}

    monkeypatch.setattr("backend.data_sources.find_cik", fake_find_cik)
    monkeypatch.setattr("backend.data_sources.get_json", fake_get_json)
    monkeypatch.setattr("backend.data_sources.fetch_price", lambda ticker, user_agent: 100.0)

    with pytest.raises(ValueError, match="暂不支持自动汇率转换"):
        fetch_company_facts("TIFRS", "ua", 0.045)


def test_fetch_company_facts_uses_financial_statement_fields(monkeypatch):
    def annual(value: float) -> dict:
        return {
            "form": "10-K",
            "start": "2025-01-01",
            "end": "2025-12-31",
            "val": value,
            "filed": "2026-02-20",
            "frame": "CY2025",
        }

    def instant(value: float) -> dict:
        return {
            "form": "10-K",
            "end": "2025-12-31",
            "val": value,
            "filed": "2026-02-20",
            "frame": "CY2025Q4I",
        }

    def fake_find_cik(_: str, __: str) -> tuple[str, str]:
        return "0001818874", "SoFi Technologies, Inc."

    def fake_get_json(url: str, _: str, timeout: int = 20) -> dict:
        if "companyfacts" not in url:
            return {
                "name": "SoFi Technologies, Inc.",
                "sic": "6199",
                "sicDescription": "Finance Services",
                "fiscalYearEnd": "1231",
                "exchanges": ["Nasdaq"],
            }
        return {
            "facts": {
                "us-gaap": {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [annual(619_353_000)]}},
                    "RevenuesNetOfInterestExpense": {"units": {"USD": [annual(3_613_354_000)]}},
                    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": {"units": {"USD": [annual(525_857_000)]}},
                    "NetIncomeLoss": {"units": {"USD": [annual(481_320_000)]}},
                    "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [annual(-3_742_458_000)]}},
                    "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [annual(-242_444_000)]}},
                    "ShareBasedCompensation": {"units": {"USD": [annual(262_058_000)]}},
                    "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [instant(2_538_293_000)]}},
                    "AvailableForSaleSecuritiesDebtSecurities": {"units": {"USD": [instant(2_454_453_000)]}},
                    "LongTermDebtNoncurrent": {"units": {"USD": [instant(3_947_983_000)]}},
                    "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [annual(1_251_767_000)]}},
                }
            }
        }

    monkeypatch.setattr("backend.data_sources.find_cik", fake_find_cik)
    monkeypatch.setattr("backend.data_sources.get_json", fake_get_json)
    monkeypatch.setattr("backend.data_sources.fetch_price", lambda ticker, user_agent, api_key=None: (16.1, "test"))
    monkeypatch.setattr("backend.data_sources.fetch_ten_year_yield", lambda api_key, fallback, user_agent: (fallback, "test"))

    output = fetch_company_facts("SOFI", "ua", 0.045)

    assert output["revenue"] == 3_613_354_000
    assert output["operating_income"] == 525_857_000
    assert output["ocf"] == 481_320_000
    assert output["short_investments"] == 2_454_453_000
    assert output["raw_json"]["normalization"]["statement_type"] == "financial_services"
    assert output["annual_history"][-1]["revenue"] == 3_613_354_000
    assert output["annual_history"][-1]["ocf"] == 481_320_000


def test_fetch_price_falls_back_to_alpha_vantage(monkeypatch):
    monkeypatch.setattr("backend.data_sources.fetch_price_yahoo", lambda ticker, user_agent: None)
    monkeypatch.setattr("backend.data_sources.fetch_price_alpha_vantage", lambda ticker, api_key, user_agent: 123.45)

    price, source = fetch_price("TEST", "ua", "demo-key")

    assert price == 123.45
    assert source == "Alpha Vantage GLOBAL_QUOTE"


def test_fetch_ten_year_yield_uses_fred_when_available(monkeypatch):
    monkeypatch.setattr(
        "backend.data_sources.get_json",
        lambda url, user_agent, timeout=20: {
            "observations": [
                {"date": "2026-04-24", "value": "."},
                {"date": "2026-04-23", "value": "4.31"},
            ]
        },
    )

    value, source = fetch_ten_year_yield("fred-key", 0.045, "ua")

    assert value == 0.0431
    assert source == "FRED DGS10 (2026-04-23)"
