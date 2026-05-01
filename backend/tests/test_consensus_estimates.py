import backend.db as db_module
from backend.db import connect, init_db
from backend.routers.valuation import delete_consensus_estimates, get_consensus_estimates, save_consensus_estimates, save_valuation_run
from backend.schemas import ConsensusEstimates
from backend.valuation import run_target_price_calculator


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()


def _nvda_facts():
    return {
        "ticker": "NVDA",
        "price": 208.27,
        "revenue": 130.5e9,
        "operating_income": 81.5e9,
        "ocf": 64.1e9,
        "capex": 3.2e9,
        "sbc": 4.7e9,
        "cash": 8.6e9,
        "short_investments": 35.3e9,
        "debt_current": 1.2e9,
        "debt_long_term": 8.5e9,
        "diluted_shares": 24.8e9,
        "ten_year_yield": 0.045,
    }


def test_consensus_estimates_round_trip_and_feed_valuation(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    baseline = run_target_price_calculator(_nvda_facts())

    saved = save_consensus_estimates(
        "NVDA",
        ConsensusEstimates(
            revenue_next_year=390e9,
            revenue_2y=510e9,
            eps_next_year=8.4,
            eps_2y=11.2,
            ebitda_next_year=260e9,
            fcf_next_year=180e9,
            long_term_eps_growth=0.30,
            source="test_consensus",
        ),
    )
    refreshed = get_consensus_estimates("NVDA")
    with_consensus = run_target_price_calculator(_nvda_facts())

    assert saved["ticker"] == "NVDA"
    assert refreshed["eps_2y"] == 11.2
    assert with_consensus["forward_estimates"]["eps_2y"]["source"] == "db_consensus"
    assert with_consensus["target_price"]["base"] > baseline["target_price"]["base"]

    deleted = delete_consensus_estimates("NVDA")

    assert deleted["deleted"] is True
    assert get_consensus_estimates("NVDA") is None


def test_save_valuation_run_persists_multiples_history(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    facts = _nvda_facts()
    result = run_target_price_calculator(facts)

    save_valuation_run("NVDA", "target_price", facts, {}, result)

    with connect() as conn:
        row = conn.execute("SELECT * FROM valuation_multiples_history WHERE ticker = 'NVDA'").fetchone()

    assert row is not None
    assert row["pe_forward"] > 0
    assert row["ev_sales"] > 0
