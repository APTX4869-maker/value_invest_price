import pytest

from backend.schemas import ValuationCalculatorRequest
from backend.valuation import run_target_price_calculator


def nvda_facts(revenue, operating_income, ocf, capex, shares=24.8e9):
    return {
        "ticker": "NVDA",
        "price": 208.27,
        "revenue": revenue,
        "operating_income": operating_income,
        "ocf": ocf,
        "capex": capex,
        "sbc": 4.7e9,
        "cash": 8.6e9,
        "short_investments": 35.3e9,
        "debt_current": 1.2e9,
        "debt_long_term": 8.5e9,
        "diluted_shares": shares,
        "ten_year_yield": 0.045,
    }


def test_nvda_newer_data_lifts_target_and_forward_eps():
    old = run_target_price_calculator(nvda_facts(60.9e9, 33.0e9, 28.1e9, 1.1e9), ValuationCalculatorRequest(ticker="NVDA"))
    new = run_target_price_calculator(nvda_facts(130.5e9, 81.5e9, 64.1e9, 3.2e9), ValuationCalculatorRequest(ticker="NVDA"))

    assert new["target_price"]["base"] > old["target_price"]["base"]
    assert new["forward_estimates"]["eps_next_year"]["value"] > old["forward_estimates"]["eps_next_year"]["value"]


def test_goog_capex_split_prevents_ai_capex_from_fully_penalizing_value():
    facts = {
        "ticker": "GOOG",
        "price": 342.32,
        "revenue": 402.836e9,
        "operating_income": 129.039e9,
        "ocf": 164.713e9,
        "capex": 91.447e9,
        "sbc": 24.953e9,
        "cash": 30.708e9,
        "short_investments": 96.135e9,
        "debt_current": 1.996e9,
        "debt_long_term": 46.547e9,
        "diluted_shares": 12.23e9,
        "ten_year_yield": 0.045,
        "annual_history": [
            {"fiscal_year": 2021, "revenue": 257.637e9, "ocf": 91.495e9, "capex": 24.640e9},
            {"fiscal_year": 2022, "revenue": 282.836e9, "ocf": 91.652e9, "capex": 31.485e9},
            {"fiscal_year": 2023, "revenue": 307.394e9, "ocf": 101.746e9, "capex": 32.251e9},
            {"fiscal_year": 2024, "revenue": 350.018e9, "ocf": 125.304e9, "capex": 52.535e9},
            {"fiscal_year": 2025, "revenue": 402.836e9, "ocf": 164.713e9, "capex": 91.447e9},
        ],
    }

    split = run_target_price_calculator(facts, ValuationCalculatorRequest(ticker="GOOG", use_capex_split=True))
    all_maintenance = run_target_price_calculator(facts, ValuationCalculatorRequest(ticker="GOOG", use_capex_split=False))

    assert split["target_price"]["base"] > all_maintenance["target_price"]["base"]
    assert split["capex_split"]["growth_capex"] > 0


def test_pltr_high_ev_sales_reverse_expectations_are_aggressive():
    facts = {
        "ticker": "PLTR",
        "price": 180.0,
        "revenue": 4.475e9,
        "operating_income": 1.414e9,
        "ocf": 2.134e9,
        "capex": 33.8e6,
        "sbc": 684e6,
        "cash": 2.0e9,
        "short_investments": 3.0e9,
        "debt_current": 0,
        "debt_long_term": 0,
        "diluted_shares": 2.565e9,
        "ten_year_yield": 0.045,
    }
    request = ValuationCalculatorRequest(
        ticker="PLTR",
        manual_overrides={
            "peer_snapshot": [
                {"peer_ticker": "CRWD", "peer_ev_sales": 18.0, "peer_forward_pe": 70.0},
                {"peer_ticker": "DDOG", "peer_ev_sales": 14.0, "peer_forward_pe": 55.0},
            ]
        },
    )

    result = run_target_price_calculator(facts, request)
    reverse = result["reverse_expectations"]

    assert reverse["difficulty"] in ["aggressive", "very_aggressive"]
    assert reverse["multiples"]["implied_ev_sales"] > reverse["multiples"]["peer_median_ev_sales"]


def test_missing_consensus_is_flagged_as_system_estimate():
    result = run_target_price_calculator(nvda_facts(130.5e9, 81.5e9, 64.1e9, 3.2e9), ValuationCalculatorRequest(ticker="NVDA"))

    assert result["forward_estimates"]["eps_next_year"]["source"] == "system_estimate"
    assert any("非市场共识" in warning for warning in result["data_quality"]["warnings"])


def test_model_weights_renormalize_when_models_have_missing_inputs():
    facts = {
        "ticker": "LOSS",
        "price": 25.0,
        "revenue": 1.0e9,
        "operating_income": -200e6,
        "ocf": -50e6,
        "capex": 20e6,
        "sbc": 120e6,
        "cash": 400e6,
        "short_investments": 0,
        "debt_current": 10e6,
        "debt_long_term": 50e6,
        "diluted_shares": 100e6,
        "ten_year_yield": 0.045,
    }
    result = run_target_price_calculator(facts, ValuationCalculatorRequest(ticker="LOSS"))
    valid_models = [model for model in result["model_outputs"] if model["base"] > 0 and model["weight"] > 0]

    assert sum(model["weight"] for model in valid_models) == pytest.approx(1.0)
