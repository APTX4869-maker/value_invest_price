import backend.db as db_module
from backend.db import init_db
from backend.discovery import get_cached_qqq_holdings, get_cached_stock_pool, save_etf_holdings, save_stock_pool_members, score_discovery_row
from backend.routers.discovery import update_custom_pool_members
from backend.schemas import StockPoolMembersRequest


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()


def test_save_and_read_qqq_holdings_cache(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    save_etf_holdings({
        "etf": "QQQ",
        "as_of": "2026-04-29",
        "source": "test",
        "holdings": [
            {"rank": 1, "ticker": "NVDA", "name": "NVIDIA Corp", "weight": 0.09, "security_type": "Common Stock", "raw": {"ticker": "NVDA"}},
            {"rank": 2, "ticker": "AAPL", "name": "Apple Inc", "weight": 0.07, "security_type": "Common Stock", "raw": {"ticker": "AAPL"}},
        ],
    })

    cached = get_cached_qqq_holdings(limit=1)

    assert cached["as_of"] == "2026-04-29"
    assert cached["holdings"][0]["ticker"] == "NVDA"
    assert cached["holdings"][0]["weight"] == 0.09


def test_save_and_read_generic_stock_pool_cache(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    save_stock_pool_members({
        "pool_id": "sp500",
        "name": "S&P 500",
        "as_of": "2026-05-02",
        "source": "test",
        "total_holdings": 2,
        "holdings": [
            {"rank": 1, "ticker": "MSFT", "name": "Microsoft Corp", "weight": 0.06, "sector": "Information Technology", "raw": {}},
            {"rank": 2, "ticker": "GOOG", "name": "Alphabet Inc", "weight": 0.04, "sector": "Communication Services", "raw": {}},
        ],
    })

    cached = get_cached_stock_pool("sp500", limit=1)

    assert cached["name"] == "S&P 500"
    assert cached["holdings"][0]["ticker"] == "MSFT"
    assert cached["holdings"][0]["sector"] == "Information Technology"


def test_update_custom_pool_members_normalizes_tickers(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    update_custom_pool_members("custom", StockPoolMembersRequest(tickers=["brk.b", " msft ", "MSFT"]))
    cached = get_cached_stock_pool("custom", limit=10)

    assert [item["ticker"] for item in cached["holdings"]] == ["BRK-B", "MSFT"]


def test_discovery_score_prefers_confident_undervalued_quality_name():
    holding = {"ticker": "MSFT", "name": "Microsoft Corp", "rank": 3, "weight": 0.055}
    facts = {
        "revenue": 1000,
        "annual_history": [
            {"fiscal_year": 2022, "revenue": 700},
            {"fiscal_year": 2025, "revenue": 1000},
        ],
    }
    result = {
        "current_price": 100,
        "target_price": {"bear": 90, "base": 130, "bull": 155},
        "confidence": {"score": 82, "level": "high", "reasons": ["模型一致性较好。"]},
        "quality_score": 78,
        "company_type": "platform_compounder",
        "quality_breakdown": {
            "operating_margin": 0.32,
            "sbc_to_revenue": 0.04,
            "net_cash_to_market_cap": 0.06,
        },
        "cash_flows": {"actual_fcf": 240},
        "model_outputs": [
            {"base": 128, "weight": 0.5},
            {"base": 132, "weight": 0.5},
        ],
        "reverse_expectations": {"difficulty": "reasonable"},
        "data_quality": {"warnings": []},
    }

    row = score_discovery_row(holding, facts, result)

    assert row["label"] == "重点研究"
    assert row["confidence_rank"] == 4
    assert row["undervaluation"] == 0.3
    assert row["moat_score"] >= 80
    assert "护城河" in row["summary"]
