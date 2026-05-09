import pytest

from backend.valuation import run_valuation


def test_goog_seed_valuation_shape():
    result = run_valuation(
        {
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
            "fiscal_year": 2025,
        }
    )
    assert result["fair_value_center"] > 0
    assert result["fair_value_range"]["low"] < result["fair_value_range"]["high"]
    assert 0 < result["terminal_dependency"] < 1
    assert "反向 DCF" in result["formula_notes"]["reverse_dcf"]


def test_overrides_change_value():
    facts = {
        "ticker": "TEST",
        "price": 100,
        "revenue": 1000,
        "operating_income": 250,
        "ocf": 220,
        "capex": 40,
        "sbc": 10,
        "cash": 50,
        "short_investments": 20,
        "debt_current": 5,
        "debt_long_term": 15,
        "diluted_shares": 10,
        "ten_year_yield": 0.04,
    }
    base = run_valuation(facts)
    bull = run_valuation(facts, {"base_growth": 0.16, "bull_growth": 0.2})
    assert bull["fair_value_center"] > base["fair_value_center"]


def test_quality_score_is_derived_from_company_fundamentals():
    strong = run_valuation(
        {
            "ticker": "STRONG",
            "price": 100,
            "revenue": 1000,
            "operating_income": 350,
            "ocf": 380,
            "capex": 30,
            "sbc": 5,
            "cash": 100,
            "short_investments": 20,
            "debt_current": 0,
            "debt_long_term": 10,
            "diluted_shares": 10,
            "ten_year_yield": 0.04,
        }
    )
    weak = run_valuation(
        {
            "ticker": "WEAK",
            "price": 100,
            "revenue": 1000,
            "operating_income": 80,
            "ocf": 90,
            "capex": 80,
            "sbc": 120,
            "cash": 10,
            "short_investments": 0,
            "debt_current": 20,
            "debt_long_term": 100,
            "diluted_shares": 10,
            "ten_year_yield": 0.04,
        }
    )

    assert strong["quality_score"] > weak["quality_score"]
    assert strong["quality_score"] != 82
    assert weak["quality_score"] != 82


def test_sanity_metrics_explain_cash_flow_multiple():
    result = run_valuation(
        {
            "ticker": "TEST",
            "price": 100,
            "revenue": 1000,
            "operating_income": 250,
            "ocf": 220,
            "capex": 20,
            "sbc": 10,
            "cash": 50,
            "short_investments": 20,
            "debt_current": 5,
            "debt_long_term": 15,
            "diluted_shares": 10,
            "ten_year_yield": 0.04,
        }
    )

    assert result["sanity_metrics"]["price_to_actual_fcf"] == 5
    assert "forward PE" in result["plain_language"]["sanity_check"]


def test_v3_uses_market_range_above_cash_flow_for_high_growth_profitable_tech():
    result = run_valuation(
        {
            "ticker": "NVDA",
            "price": 208.27,
            "revenue": 130.497e9,
            "operating_income": 81.453e9,
            "ocf": 64.089e9,
            "capex": 3.236e9,
            "sbc": 4.737e9,
            "cash": 8.589e9,
            "short_investments": 35.280e9,
            "debt_current": 1.250e9,
            "debt_long_term": 8.463e9,
            "diluted_shares": 24.804e9,
            "ten_year_yield": 0.045,
        }
    )

    assert result["methodology_version"].startswith("V3.0")
    assert result["v3_summary"]["style"] == "high_growth_profitable_tech"
    assert result["assumption_build"]["growth_assumptions"]["sources"]["company_prior"] == pytest.approx(0.34)
    assert result["valuation_layers"]["weights"]["market"] > result["valuation_layers"]["weights"]["intrinsic"]
    assert result["fair_value_center"] > result["cash_flow_fair_value_center"]
    assert result["fair_value_range"]["high"] > 150
    assert "不需要你自己判断模型冲突" in result["plain_language"]["sanity_check"]


def test_v3_reports_model_consistency_for_non_professional_user():
    result = run_valuation(
        {
            "ticker": "PLTR",
            "price": 143.09,
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
    )

    consistency = result["v3_summary"]["model_consistency"]
    assert consistency["level"] in {"高", "中", "低"}
    assert "plain_language" in consistency
    assert result["v3_summary"]["market_reasonable_range"]["low"] < result["v3_summary"]["market_reasonable_range"]["high"]
