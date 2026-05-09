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


def test_layered_target_keeps_reverse_dcf_out_of_weighted_models():
    result = run_target_price_calculator(nvda_facts(130.5e9, 81.5e9, 64.1e9, 3.2e9), ValuationCalculatorRequest(ticker="NVDA"))

    reverse_model = next(model for model in result["model_outputs"] if model["model"] == "reverse_check")

    assert reverse_model["weight"] == 0
    assert result["valuation_layers"]["intrinsic"]["method"] == "deterministic_monte_carlo_dcf"
    assert result["valuation_layers"]["weights"]["market"] > result["valuation_layers"]["weights"]["intrinsic"]
    assert result["target_price"]["base"] > result["valuation_layers"]["intrinsic"]["base"]


def test_manual_analyst_target_can_be_blended_as_a_separate_layer():
    facts = nvda_facts(130.5e9, 81.5e9, 64.1e9, 3.2e9)
    without_analyst = run_target_price_calculator(facts, ValuationCalculatorRequest(ticker="NVDA"))
    with_analyst = run_target_price_calculator(
        facts,
        ValuationCalculatorRequest(
            ticker="NVDA",
            manual_overrides={
                "analyst_target_low": 240,
                "analyst_target_median": 280,
                "analyst_target_high": 330,
                "analyst_target_source": "test_consensus",
            },
        ),
    )

    assert with_analyst["valuation_layers"]["analyst"]["base"] == 280
    assert with_analyst["valuation_layers"]["weights"]["analyst"] > 0
    assert with_analyst["target_price"]["base"] > without_analyst["target_price"]["base"]


def test_high_growth_target_uses_two_year_forward_inputs():
    result = run_target_price_calculator(nvda_facts(130.5e9, 81.5e9, 64.1e9, 3.2e9), ValuationCalculatorRequest(ticker="NVDA"))
    forward_pe = next(model for model in result["model_outputs"] if model["model"] == "forward_pe")
    ev_sales = next(model for model in result["model_outputs"] if model["model"] == "ev_sales")

    assert forward_pe["key_inputs"]["forward_period"] == "fy2"
    assert ev_sales["key_inputs"]["forward_period"] == "fy2"


def test_mu_memory_semiconductor_uses_recent_quarter_forward_anchor():
    facts = {
        "ticker": "MU",
        "price": 517.16,
        "revenue": 37.378e9,
        "operating_income": 9.77e9,
        "ocf": 17.525e9,
        "capex": 15.857e9,
        "sbc": 972e6,
        "cash": 9.642e9,
        "short_investments": 0,
        "debt_current": 224e6,
        "debt_long_term": 11.533e9,
        "diluted_shares": 1.125e9,
        "ten_year_yield": 0.045,
        "annual_history": [
            {"fiscal_year": 2020, "revenue": 21.435e9, "operating_income": 3.003e9, "ocf": 8.306e9, "capex": 8.223e9},
            {"fiscal_year": 2021, "revenue": 27.705e9, "operating_income": 6.283e9, "ocf": 12.468e9, "capex": 10.030e9},
            {"fiscal_year": 2022, "revenue": 30.758e9, "operating_income": 9.702e9, "ocf": 15.181e9, "capex": 12.067e9},
            {"fiscal_year": 2023, "revenue": 15.540e9, "operating_income": -5.745e9, "ocf": 1.559e9, "capex": 7.676e9},
            {"fiscal_year": 2024, "revenue": 25.111e9, "operating_income": 1.304e9, "ocf": 8.507e9, "capex": 8.386e9},
            {"fiscal_year": 2025, "revenue": 37.378e9, "operating_income": 9.770e9, "ocf": 17.525e9, "capex": 15.857e9},
        ],
        "raw": {
            "recent_period": {
                "latest_quarter": {
                    "revenue": 23.860e9,
                    "annualized_revenue": 95.440e9,
                    "operating_income": 16.135e9,
                    "annualized_operating_income": 64.540e9,
                    "diluted_shares": 1.142e9,
                },
                "latest_ytd": {
                    "ocf": 20.314e9,
                    "capex": 11.776e9,
                    "fcf": 8.538e9,
                    "annualized_ocf": 40.628e9,
                    "annualized_capex": 23.552e9,
                    "annualized_fcf": 17.076e9,
                },
            }
        },
    }

    result = run_target_price_calculator(facts, ValuationCalculatorRequest(ticker="MU"))
    models = {model["model"]: model for model in result["model_outputs"]}

    assert result["company_type"] == "memory_semiconductor"
    assert result["forward_estimates"]["revenue_next_year"]["source"] == "sec_recent_quarter_extrapolated"
    assert result["target_price"]["base"] > 350
    assert models["forward_pe"]["key_inputs"]["forward_period"] == "fy2"
    assert models["forward_pe"]["weight"] > models["mid_cycle_earnings"]["weight"]
    assert any("HBM" in risk for risk in result["key_risks"])

    polluted_peers = run_target_price_calculator(
        facts,
        ValuationCalculatorRequest(
            ticker="MU",
            manual_overrides={
                "peer_snapshot": [
                    {"peer_ticker": "ARM", "peer_forward_pe": 806, "peer_ev_sales": 48, "peer_ev_ebitda": 182},
                    {"peer_ticker": "CRM", "peer_forward_pe": 27, "peer_ev_sales": 4, "peer_ev_ebitda": 16},
                    {"peer_ticker": "IBM", "peer_forward_pe": 61, "peer_ev_sales": 4, "peer_ev_ebitda": 20},
                ]
            },
        ),
    )

    assert polluted_peers["multiples"]["sources"]["ev_sales"] == "default_fallback_adjusted"
    assert polluted_peers["target_price"]["base"] < 900


def test_financial_company_uses_earnings_led_market_range():
    facts = {
        "ticker": "SOFI",
        "price": 16.1,
        "revenue": 3.613354e9,
        "operating_income": 525.857e6,
        "ocf": 481.320e6,
        "capex": 242.444e6,
        "sbc": 262.058e6,
        "cash": 2.538293e9,
        "short_investments": 2.454453e9,
        "debt_current": 0,
        "debt_long_term": 3.947983e9,
        "diluted_shares": 1.251767e9,
        "ten_year_yield": 0.045,
        "raw": {
            "sec_meta": {"sic": "6199", "sic_description": "Finance Services"},
            "normalization": {
                "statement_type": "financial_services",
                "notes": ["金融/放贷类公司使用净利息后收入和净利润近似可分配盈利。"],
            },
        },
    }

    result = run_target_price_calculator(facts, ValuationCalculatorRequest(ticker="SOFI"))
    models = {model["model"]: model for model in result["model_outputs"]}

    assert result["company_type"] == "financial"
    assert result["valuation_layers"]["weights"]["intrinsic"] == 0
    assert models["three_stage_dcf"]["weight"] == 0
    assert models["fcf_yield"]["weight"] == 0
    assert models["forward_pe"]["weight"] > models["ev_sales"]["weight"]
    assert 5 < result["target_price"]["base"] < 15


def test_industrial_company_is_not_misclassified_as_platform_compounder():
    facts = {
        "ticker": "GE",
        "price": 286.51,
        "revenue": 45.855e9,
        "operating_income": 22.887e9,
        "ocf": 8.537e9,
        "capex": 1.273e9,
        "sbc": 0,
        "cash": 12.392e9,
        "short_investments": 0,
        "debt_current": 25e6,
        "debt_long_term": 20.469e9,
        "diluted_shares": 1.068e9,
        "ten_year_yield": 0.045,
        "company_profile": {
            "industry": "Electronic & Other Electrical Equipment (No Computer Equip)",
            "sector": "Electronic & Other Electrical Equipment (No Computer Equip)",
            "description": "Aerospace engines and industrial equipment manufacturer.",
        },
        "annual_history": [
            {"fiscal_year": 2023, "revenue": 35.348e9, "ocf": 5.189e9, "capex": 862e6},
            {"fiscal_year": 2024, "revenue": 38.702e9, "ocf": 4.710e9, "capex": 1.032e9},
            {"fiscal_year": 2025, "revenue": 45.855e9, "ocf": 8.537e9, "capex": 1.273e9},
        ],
    }

    result = run_target_price_calculator(facts, ValuationCalculatorRequest(ticker="GE"))
    models = {model["model"]: model for model in result["model_outputs"]}

    assert result["company_type"] == "industrial"
    assert result["assumption_build"]["classification"]["confidence"] == "medium_high"
    assert any("工业" in reason or "电气设备" in reason for reason in result["assumption_build"]["classification"]["reasons"])
    assert result["assumption_build"]["growth_assumptions"]["sources"]["revenue_cagr_3y"] is not None
    assert result["scenarios"]["base"]["revenue_cagr_5y"] > 0.08
    assert result["scenarios"]["base"]["revenue_cagr_5y"] != pytest.approx(0.04)
    assert models["ev_ebitda"]["weight"] > models["ev_sales"]["weight"]
    assert models["forward_pe"]["key_inputs"]["forward_period"] == "fy1"
    assert result["target_price"]["base"] < 300


def test_manual_company_type_override_is_recorded_in_assumptions():
    facts = {
        "ticker": "TYPE",
        "price": 50,
        "revenue": 10e9,
        "operating_income": 1.8e9,
        "ocf": 1.7e9,
        "capex": 600e6,
        "sbc": 100e6,
        "cash": 1e9,
        "short_investments": 0,
        "debt_current": 0,
        "debt_long_term": 2e9,
        "diluted_shares": 500e6,
        "ten_year_yield": 0.045,
        "annual_history": [
            {"fiscal_year": 2022, "revenue": 8e9, "operating_income": 1.1e9, "ocf": 1.2e9, "capex": 500e6},
            {"fiscal_year": 2023, "revenue": 9e9, "operating_income": 1.4e9, "ocf": 1.4e9, "capex": 550e6},
            {"fiscal_year": 2024, "revenue": 10e9, "operating_income": 1.8e9, "ocf": 1.7e9, "capex": 600e6},
        ],
    }

    result = run_target_price_calculator(
        facts,
        ValuationCalculatorRequest(ticker="TYPE", manual_overrides={"company_type": "industrial"}),
    )

    assert result["company_type"] == "industrial"
    assert result["assumption_build"]["classification"]["confidence"] == "high"
    assert "手动覆盖" in result["assumption_build"]["classification"]["reasons"][0]


def test_fmp_enrichment_feeds_analyst_layer_and_capex_split():
    facts = {
        "ticker": "FMPX",
        "price": 80,
        "revenue": 10e9,
        "operating_income": 2e9,
        "ocf": 1.8e9,
        "capex": 600e6,
        "sbc": 100e6,
        "cash": 1e9,
        "short_investments": 0,
        "debt_current": 100e6,
        "debt_long_term": 900e6,
        "diluted_shares": 500e6,
        "ten_year_yield": 0.045,
        "raw": {
            "fmp": {
                "enrichment": {
                    "price_target": {
                        "target_low": 90,
                        "target_median": 110,
                        "target_high": 130,
                        "source": "FMP price target consensus",
                    },
                    "normalized": {
                        "maintenance_capex": 220e6,
                        "growth_capex": 380e6,
                        "roic": 0.16,
                        "current_ratio": 1.6,
                        "interest_coverage": 8,
                    },
                }
            }
        },
    }

    result = run_target_price_calculator(facts, ValuationCalculatorRequest(ticker="FMPX"))

    assert result["valuation_layers"]["analyst"]["base"] == 110
    assert result["valuation_layers"]["analyst"]["source"] == "FMP price target consensus"
    assert result["capex_split"]["method"] == "fmp_owner_earnings"
    assert result["capex_split"]["maintenance_capex"] == pytest.approx(220e6)
    assert result["quality_breakdown"]["fmp_roic"] == 0.16


def test_simple_fcf_dcf_matches_excel_style_cross_check_for_ge():
    facts = {
        "ticker": "GE",
        "price": 286.51,
        "revenue": 45.855e9,
        "operating_income": 22.887e9,
        "ocf": 8.537e9,
        "capex": 1.273e9,
        "sbc": 0,
        "cash": 12.392e9,
        "short_investments": 0,
        "debt_current": 25e6,
        "debt_long_term": 20.469e9,
        "diluted_shares": 1.068e9,
        "ten_year_yield": 0.045,
        "company_profile": {
            "industry": "Electronic & Other Electrical Equipment (No Computer Equip)",
            "sector": "Electronic & Other Electrical Equipment (No Computer Equip)",
        },
    }

    result = run_target_price_calculator(facts, ValuationCalculatorRequest(ticker="GE"))
    simple = result["simple_fcf_dcf"]

    assert simple["method"] == "excel_style_fcf_exit_multiple_dcf"
    assert simple["anchor_method"] == "latest_actual_fcf"
    assert simple["growths"] == pytest.approx([0.07, 0.09, 0.11, 0.13, 0.15])
    assert simple["base"] == pytest.approx(240.6, rel=0.01)
    assert simple["range_low"] == pytest.approx(170.4, rel=0.01)
    assert simple["range_high"] == pytest.approx(322.4, rel=0.01)
