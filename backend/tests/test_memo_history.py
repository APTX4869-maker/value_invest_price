import backend.db as db_module
from backend.db import connect, dumps, init_db, loads
from backend.llm_research import update_research_draft
from backend.routers.notes import get_memo_history, put_memo
from backend.schemas import InvestmentMemoRequest


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()


def test_manual_memo_save_records_versions(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    put_memo(
        "MSFT",
        InvestmentMemoRequest(
            conclusion="合理",
            attention_reason="云业务质量高，等待更好价格。",
            thesis=["Azure 利润率改善"],
            review_triggers=["下一季云增长低于预期"],
        ),
    )
    put_memo(
        "MSFT",
        InvestmentMemoRequest(
            conclusion="便宜",
            attention_reason="估值回落后重新进入重点观察。",
            thesis=["AI 需求支撑云增长"],
            review_triggers=["CAPEX 回报低于预期"],
        ),
    )

    versions = get_memo_history("MSFT")

    assert len(versions) == 2
    assert versions[0]["source"] == "manual"
    assert versions[0]["memo"]["conclusion"] == "便宜"
    assert versions[1]["memo"]["conclusion"] == "合理"


def test_confirmed_ai_draft_records_memo_version(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO investment_memos
            (ticker, conclusion, attention_reason, thesis_json, business_moat,
             financial_quality, valuation_view, bear_case, review_triggers_json,
             free_notes, snapshot_id, created_at, updated_at)
            VALUES ('TEST', '不确定', '', '[]', '', '', '', '', '[]', '', NULL,
                    '2026-05-03T00:00:00+00:00', '2026-05-03T00:00:00+00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO research_drafts
            (ticker, draft_type, status, provider, model, source_accessions_json,
             draft_json, error, created_at, updated_at)
            VALUES ('TEST', 'sec_research', 'pending_confirmation', 'openai_compatible',
                    'test-model', '["0001"]', ?, '',
                    '2026-05-03T00:00:00+00:00', '2026-05-03T00:00:00+00:00')
            """,
            (
                dumps(loads(
                    """
                    {"business_model":"广告和云服务","segments":["Cloud"],"growth_drivers":["云增长"],
                    "moat_sources":["生态分发"],"competition":["AI 搜索竞争"],"key_risks":["CAPEX 回报"],
                    "financial_quality_notes":["现金流强"],"follow_up_questions":["云利润率？"],"citations":[]}
                    """
                )),
            ),
        )
        draft_id = conn.execute("SELECT id FROM research_drafts WHERE ticker = 'TEST'").fetchone()["id"]

    update_research_draft("TEST", draft_id, status="confirmed")

    versions = get_memo_history("TEST")

    assert len(versions) == 1
    assert versions[0]["source"] == "ai_confirmed_draft"
    assert versions[0]["memo"]["thesis"] == ["云增长"]
