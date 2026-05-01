import backend.db as db_module
from backend.db import connect, dumps, init_db, now_iso
from backend.dependencies import get_facts_or_404
from backend.routers.companies import _peer_summary
from backend.routers.companies import compare_peers
from backend.schemas import ValuationCalculatorRequest
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
    _seed_company("BASE", peers=["PEER"], price=100)
    _seed_company("PEER", price=140, revenue=1200, operating_income=360, ocf=320, capex=35)

    comparison = compare_peers("BASE")

    assert comparison["summary"]["available_count"] == 1
    with connect() as conn:
        row = conn.execute("SELECT * FROM peer_valuation_snapshot WHERE ticker = 'BASE' AND peer_ticker = 'PEER'").fetchone()
    assert row is not None
    assert row["peer_ev_sales"] > 0

    result = run_target_price_calculator(get_facts_or_404("BASE"), ValuationCalculatorRequest(ticker="BASE"))

    assert result["multiples"]["sources"]["ev_sales"] == "peer_snapshot"
