import backend.db as db_module
from backend.db import connect, dumps, init_db, now_iso
from backend.dependencies import get_facts_or_404
from backend.peer_recommendations import curated_peer_tickers, sanitize_peer_tickers, should_replace_with_curated_peers
from backend.routers.companies import _peer_summary
from backend.routers.companies import compare_peers, peer_suggestions, refresh_company, update_peers
from backend.schemas import PeersRequest, ValuationCalculatorRequest
from backend.valuation import run_target_price_calculator


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()


def _seed_company(ticker: str, peers=None, price=100, revenue=1000, operating_income=250, ocf=240, capex=30):
    ts = now_iso()
    peers = peers or []
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO companies
            (ticker, name, industry, sector, description, business_overview,
             company_type, segments_json, peers_json, profile_source, created_at, updated_at)
            VALUES (?, ?, 'Software', 'Technology', '', '', '稳定复利公司', '[]', ?, '', ?, ?)
            """,
            (ticker, ticker, dumps(peers), ts, ts),
        )
        conn.execute(
            """
            INSERT INTO financial_facts
            (ticker, fiscal_year, revenue, operating_income, ocf, capex, sbc, cash,
             short_investments, debt_current, debt_long_term, diluted_shares, price,
             price_override, price_source, market_cap, ten_year_yield, ten_year_yield_source, source, updated_at, annual_history_json, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                2025,
                revenue,
                operating_income,
                ocf,
                capex,
                5,
                50,
                0,
                0,
                10,
                10,
                price,
                None,
                "test",
                price * 10,
                0.045,
                "test",
                "test",
                ts,
                dumps([]),
                dumps({}),
            ),
        )


def test_peer_summary_labels_current_more_expensive_than_peer_average():
    current = {
        "ticker": "TEST",
        "status": "ready",
        "price_to_fair": 1.4,
        "quality_score": 85,
    }
    peers = [
        {"ticker": "A", "status": "ready", "price_to_fair": 1.0, "quality_score": 80, "fcf_yield": 0.04},
        {"ticker": "B", "status": "ready", "price_to_fair": 1.1, "quality_score": 82, "fcf_yield": 0.03},
    ]

    summary = _peer_summary(current, peers)

    assert summary["relative_label"] == "比同行更贵"
    assert summary["available_count"] == 2


def test_peer_summary_handles_missing_peer_data():
    current = {
        "ticker": "TEST",
        "status": "ready",
        "price_to_fair": 1.0,
        "quality_score": 80,
    }

    summary = _peer_summary(current, [{"ticker": "A", "status": "missing_facts"}])

    assert summary["available_count"] == 0
    assert "还没有可比较数据" in summary["headline"]


def test_peer_compare_saves_snapshot_for_dynamic_multiples(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _seed_company("BASE", peers=["PEER", "PEER2"], price=100)
    _seed_company("PEER", price=140, revenue=1200, operating_income=360, ocf=320, capex=35)
    _seed_company("PEER2", price=120, revenue=1100, operating_income=300, ocf=290, capex=30)

    comparison = compare_peers("BASE")

    assert comparison["summary"]["available_count"] == 2
    with connect() as conn:
        row = conn.execute("SELECT * FROM peer_valuation_snapshot WHERE ticker = 'BASE' AND peer_ticker = 'PEER'").fetchone()
    assert row is not None
    assert row["peer_ev_sales"] > 0

    result = run_target_price_calculator(get_facts_or_404("BASE"), ValuationCalculatorRequest(ticker="BASE"))

    assert result["multiples"]["sources"]["ev_sales"] == "peer_snapshot"


def test_single_peer_snapshot_does_not_drive_market_multiples(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _seed_company("BASE", peers=["PEER"], price=100)
    _seed_company("PEER", price=140, revenue=1200, operating_income=360, ocf=320, capex=35)

    compare_peers("BASE")
    result = run_target_price_calculator(get_facts_or_404("BASE"), ValuationCalculatorRequest(ticker="BASE"))

    assert result["multiples"]["sources"]["ev_sales"] == "default_fallback_adjusted"


def test_mu_curated_peers_replace_broad_provider_list():
    assert curated_peer_tickers("MU")[:2] == ["WDC", "STX"]
    assert should_replace_with_curated_peers("MU", ["AMAT", "ARM", "CRM", "IBM"])
    assert not should_replace_with_curated_peers("MU", ["WDC", "STX", "AMD"])


def test_core_peer_list_is_deduped_and_capped():
    peers = sanitize_peer_tickers("BASE", ["A", "A", "BASE", "B", "C", "D", "E", "F", "G", "H", "I"])

    assert peers == ["A", "B", "C", "D", "E", "F", "G", "H"]


def test_update_peers_caps_selected_core_peers(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _seed_company("BASE")

    company = update_peers("BASE", PeersRequest(peers=["A", "B", "C", "D", "E", "F", "G", "H", "I"]))

    assert company["peers"] == ["A", "B", "C", "D", "E", "F", "G", "H"]


def test_refresh_company_keeps_external_peers_as_candidates(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    def fake_fetch_company_facts(*args, **kwargs):
        return {
            "name": "Test Corp",
            "sec_meta": {"sic_description": "Application Software"},
            "fiscal_year": 2025,
            "revenue": 1000,
            "operating_income": 250,
            "ocf": 220,
            "capex": 30,
            "sbc": 5,
            "cash": 80,
            "short_investments": 0,
            "debt_current": 0,
            "debt_long_term": 10,
            "diluted_shares": 10,
            "price": 100,
            "price_source": "test",
            "ten_year_yield": 0.045,
            "ten_year_yield_source": "test",
            "source": "test",
            "annual_history": [],
            "raw_json": {
                "fmp": {"enrichment": {"peer_tickers": ["ABC", "DEF", "GHI"]}},
                "finnhub": {"enrichment": {"peer_tickers": ["IBM", "ORCL"]}},
            },
        }

    monkeypatch.setattr("backend.routers.companies.fetch_company_facts", fake_fetch_company_facts)

    refreshed = refresh_company("TST")
    suggestions = peer_suggestions("TST")

    assert refreshed["company"]["peers"] == []
    external = [item for item in suggestions if item["source"] == "外部数据源候选"]
    assert [item["ticker"] for item in external[:3]] == ["ABC", "DEF", "GHI"]
    assert not any(item["selected"] for item in external)
