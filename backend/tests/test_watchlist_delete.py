import backend.db as db_module
from backend.db import connect, dumps, init_db, now_iso
from backend.routers.watchlist import delete_company_from_watchlist, purge_company_from_storage


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()


def _seed_company(ticker: str):
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO companies
            (ticker, name, industry, sector, description, business_overview,
             company_type, segments_json, peers_json, profile_source, created_at, updated_at)
            VALUES (?, ?, '', '', '', '', '稳定复利公司', '[]', '[]', '', ?, ?)
            """,
            (ticker, ticker, ts, ts),
        )
        conn.execute(
            """
            INSERT INTO financial_facts
            (ticker, fiscal_year, revenue, operating_income, ocf, capex, sbc, cash,
             short_investments, debt_current, debt_long_term, diluted_shares, price,
             price_override, price_source, market_cap, ten_year_yield, ten_year_yield_source, source, updated_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ticker, 2025, 100, 20, 30, 5, 1, 10, 0, 0, 0, 10, 10, None, "test", 100, 0.045, "test", "test", ts, dumps({})),
        )
        conn.execute("INSERT INTO notes (ticker, content, updated_at) VALUES (?, ?, ?)", (ticker, "note", ts))
        conn.execute(
            "INSERT INTO valuation_snapshots (ticker, title, inputs_json, result_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (ticker, "snap", dumps({}), dumps({"fair_value_center": 10}), ts),
        )


def test_delete_watchlist_keeps_notes_and_snapshots(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _seed_company("TESTKEEP")

    result = delete_company_from_watchlist("TESTKEEP")

    assert result["purged"] is False
    with connect() as conn:
        assert conn.execute("SELECT 1 FROM companies WHERE ticker = 'TESTKEEP'").fetchone() is None
        assert conn.execute("SELECT 1 FROM financial_facts WHERE ticker = 'TESTKEEP'").fetchone() is None
        assert conn.execute("SELECT 1 FROM notes WHERE ticker = 'TESTKEEP'").fetchone() is not None
        assert conn.execute("SELECT 1 FROM valuation_snapshots WHERE ticker = 'TESTKEEP'").fetchone() is not None


def test_purge_watchlist_removes_notes_and_snapshots(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    _seed_company("TESTPURGE")

    result = purge_company_from_storage("TESTPURGE")

    assert result["purged"] is True
    with connect() as conn:
        assert conn.execute("SELECT 1 FROM companies WHERE ticker = 'TESTPURGE'").fetchone() is None
        assert conn.execute("SELECT 1 FROM financial_facts WHERE ticker = 'TESTPURGE'").fetchone() is None
        assert conn.execute("SELECT 1 FROM notes WHERE ticker = 'TESTPURGE'").fetchone() is None
        assert conn.execute("SELECT 1 FROM valuation_snapshots WHERE ticker = 'TESTPURGE'").fetchone() is None
