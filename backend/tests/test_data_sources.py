import ssl
import urllib.error

import pytest

from backend.data_sources import (
    DataSourceNetworkError,
    build_annual_history,
    build_recent_period_snapshot,
    detect_reporting_currency,
    fetch_alpha_vantage_company_data,
    fetch_company_facts,
    fetch_finnhub_company_data,
    fetch_fmp_company_data,
    fetch_price,
    fetch_qqq_holdings,
    fetch_sp500_holdings,
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


def test_fetch_sp500_holdings_parses_slickcharts_table(monkeypatch):
    html = """
    <table>
      <tr><th>#</th><th>Company</th><th>Symbol</th><th>Weight</th></tr>
      <tr><td>1</td><td>NVIDIA Corp</td><td>NVDA</td><td>7.10%</td></tr>
      <tr><td>2</td><td>Apple Inc</td><td>AAPL</td><td>6.20%</td></tr>
    </table>
    """
    monkeypatch.setattr("backend.data_sources.get_text", lambda url, user_agent: html)

    payload = fetch_sp500_holdings("ua")

    assert payload["pool_id"] == "sp500"
    assert payload["holdings"][0]["ticker"] == "NVDA"
    assert payload["holdings"][0]["weight"] == 0.071
    assert payload["source"] == "Slickcharts S&P 500 companies by weight"


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


def test_build_recent_period_snapshot_uses_latest_quarter_and_ytd():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"form": "10-Q", "start": "2025-08-29", "end": "2025-11-27", "val": 13_643, "filed": "2025-12-18"},
                            {"form": "10-Q", "start": "2025-11-28", "end": "2026-02-26", "val": 23_860, "filed": "2026-03-19"},
                        ]
                    }
                },
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [
                            {"form": "10-Q", "start": "2025-11-28", "end": "2026-02-26", "val": 16_135, "filed": "2026-03-19"}
                        ]
                    }
                },
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {
                        "USD": [
                            {"form": "10-Q", "start": "2025-08-29", "end": "2026-02-26", "val": 20_314, "filed": "2026-03-19"}
                        ]
                    }
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {
                        "USD": [
                            {"form": "10-Q", "start": "2025-08-29", "end": "2026-02-26", "val": -11_776, "filed": "2026-03-19"}
                        ]
                    }
                },
                "WeightedAverageNumberOfDilutedSharesOutstanding": {
                    "units": {
                        "shares": [
                            {"form": "10-Q", "start": "2025-11-28", "end": "2026-02-26", "val": 1_142, "filed": "2026-03-19"}
                        ]
                    }
                },
            }
        }
    }
    fields = {
        "revenue": (["Revenues"], ["USD"]),
        "operating_income": (["OperatingIncomeLoss"], ["USD"]),
        "ocf": (["NetCashProvidedByUsedInOperatingActivities"], ["USD"]),
        "capex": (["PaymentsToAcquirePropertyPlantAndEquipment"], ["USD"]),
        "diluted_shares": (["WeightedAverageNumberOfDilutedSharesOutstanding"], ["shares"]),
    }

    snapshot = build_recent_period_snapshot(facts, fields)

    assert snapshot["latest_quarter"]["revenue"] == 23_860
    assert snapshot["latest_quarter"]["operating_income"] == 16_135
    assert snapshot["latest_quarter"]["diluted_shares"] == 1_142
    assert snapshot["latest_ytd"]["fcf"] == 8_538
    assert snapshot["latest_quarter"]["annualized_revenue"] > 90_000


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


def test_fetch_fmp_company_data_collects_enrichment(monkeypatch):
    def fake_get_json(url, user_agent, timeout=20, retries=2):
        if "income-statement" in url:
            return [{"date": "2025-12-31", "calendarYear": "2025", "revenue": 1000, "operatingIncome": 220, "weightedAverageShsOutDil": 100}]
        if "cash-flow-statement" in url:
            return [{"date": "2025-12-31", "calendarYear": "2025", "operatingCashFlow": 180, "capitalExpenditure": -40, "stockBasedCompensation": 5}]
        if "balance-sheet-statement" in url:
            return [{"date": "2025-12-31", "calendarYear": "2025", "cashAndCashEquivalents": 120, "shortTermDebt": 10, "longTermDebt": 50}]
        if "quote" in url:
            return [{"price": 25}]
        if "analyst-estimates" in url:
            return [{"date": "2026-12-31", "estimatedRevenueAvg": 1120, "estimatedEpsAvg": 2.4, "estimatedEbitdaAvg": 260}]
        if "key-metrics-ttm" in url:
            return [{"roicTTM": 0.18, "evToSalesTTM": 3.2, "freeCashFlowYieldTTM": 0.045}]
        if "ratios-ttm" in url:
            return [{"currentRatioTTM": 1.8, "interestCoverageTTM": 9.5, "grossProfitMarginTTM": 0.55}]
        if "enterprise-values" in url:
            return [{"marketCapitalization": 2500, "enterpriseValue": 2440, "numberOfShares": 100}]
        if "owner-earnings" in url:
            return [{"ownerEarnings": 150, "ownersEarningsPerShare": 1.5, "maintenanceCapex": 25, "growthCapex": 15}]
        if "price-target-consensus" in url:
            return [{"targetLow": 20, "targetMedian": 28, "targetHigh": 35}]
        if "stock-peers" in url:
            return [{"peersList": ["PEER1", "PEER2"]}]
        return []

    monkeypatch.setattr("backend.data_sources.get_json", fake_get_json)

    output = fetch_fmp_company_data("TEST", "demo-key", "ua")

    assert output["latest"]["revenue"] == 1000
    assert output["consensus"]["eps_next_year"] == 2.4
    assert output["enrichment"]["normalized"]["roic"] == 0.18
    assert output["enrichment"]["normalized"]["maintenance_capex"] == 25
    assert output["enrichment"]["price_target"]["target_median"] == 28
    assert output["enrichment"]["peer_tickers"] == ["PEER1", "PEER2"]


def test_fetch_alpha_vantage_company_data_collects_statement_fallback(monkeypatch):
    def fake_get_json(url, user_agent, timeout=20, retries=2):
        if "OVERVIEW" in url:
            return {"Symbol": "TEST", "SharesOutstanding": "100", "AnalystTargetPrice": "31.5", "ReturnOnEquityTTM": "0.21"}
        if "INCOME_STATEMENT" in url:
            return {
                "annualReports": [
                    {"fiscalDateEnding": "2025-12-31", "totalRevenue": "1000", "operatingIncome": "210"},
                ]
            }
        if "BALANCE_SHEET" in url:
            return {
                "annualReports": [
                    {
                        "fiscalDateEnding": "2025-12-31",
                        "cashAndCashEquivalentsAtCarryingValue": "120",
                        "shortTermDebt": "10",
                        "longTermDebt": "50",
                        "commonStockSharesOutstanding": "100",
                    },
                ]
            }
        if "CASH_FLOW" in url:
            return {
                "annualReports": [
                    {"fiscalDateEnding": "2025-12-31", "operatingCashflow": "180", "capitalExpenditures": "-40"},
                ]
            }
        return {}

    monkeypatch.setattr("backend.data_sources.get_json", fake_get_json)

    output = fetch_alpha_vantage_company_data("TEST", "demo-key", "ua")

    assert output["latest"]["revenue"] == 1000
    assert output["latest"]["capex"] == 40
    assert output["latest"]["diluted_shares"] == 100
    assert output["annual_history"][0]["source"] == "Alpha Vantage standardized statements"
    assert output["enrichment"]["price_target"]["target_median"] == 31.5
    assert output["available"]["income_statement"] is True


def test_fetch_finnhub_company_data_collects_metrics_and_peers(monkeypatch):
    def fake_get_json(url, user_agent, timeout=20, retries=2):
        if "quote" in url:
            return {"c": 25.5}
        if "profile2" in url:
            return {"name": "Test Co", "marketCapitalization": 2500}
        if "stock/metric" in url:
            return {
                "metric": {
                    "enterpriseValue": 2600,
                    "evRevenueTTM": 3.1,
                    "evEbitdaTTM": 12.2,
                    "pfcfShareTTM": 25,
                    "roeTTM": 18.0,
                    "currentRatioQuarterly": 1.4,
                }
            }
        if "stock/peers" in url:
            return ["TEST", "PEER1", "PEER2"]
        return {}

    monkeypatch.setattr("backend.data_sources.get_json", fake_get_json)

    output = fetch_finnhub_company_data("TEST", "demo-key", "ua")

    assert output["latest"]["price"] == 25.5
    assert output["enrichment"]["peer_tickers"] == ["PEER1", "PEER2"]
    assert output["enrichment"]["normalized"]["market_cap"] == 2_500_000_000
    assert output["enrichment"]["normalized"]["enterprise_value"] == 2_600_000_000
    assert output["enrichment"]["normalized"]["fcf_yield"] == 0.04
