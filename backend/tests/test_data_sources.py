import pytest

from backend.data_sources import build_annual_history, detect_reporting_currency, fetch_company_facts, latest_annual_value
from backend.data_sources import fetch_price, fetch_ten_year_yield


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
