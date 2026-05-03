import backend.db as db_module
from backend.db import connect, init_db, loads
from backend.llm_research import generate_company_research_draft, list_research_drafts, parse_json_content, truthy, update_research_draft


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()


def test_parse_json_content_extracts_object():
    parsed = parse_json_content('Here is JSON:\n{"business_model":"abc","segments":["Ads"]}')

    assert parsed["business_model"] == "abc"
    assert parsed["segments"] == ["Ads"]


def test_truthy_accepts_setting_strings():
    assert truthy("true")
    assert truthy("开启")
    assert not truthy("false")


def test_generate_company_research_draft_saves_pending_draft(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO companies
            (ticker, name, industry, sector, description, business_overview,
             company_type, segments_json, peers_json, research_summary_json, profile_source, created_at, updated_at)
            VALUES ('TEST', 'Test Corp', '', '', '', '', '稳定复利公司', '[]', '[]', '{}', '', '2026-05-03T00:00:00+00:00', '2026-05-03T00:00:00+00:00')
            """
        )
    monkeypatch.setattr(
        "backend.llm_research.OpenAICompatibleProvider.generate_json",
        lambda self, messages: {
            "business_model": "通过广告和云业务赚钱。",
            "segments": ["Google Services", "Google Cloud"],
            "growth_drivers": ["AI 搜索", "云计算"],
            "moat_sources": ["分发入口"],
            "competition": ["AI 入口竞争"],
            "key_risks": ["CAPEX 回报不确定"],
            "financial_quality_notes": ["现金流强"],
            "follow_up_questions": ["Cloud 利润率能否继续改善？"],
            "citations": [{"claim": "广告是核心业务", "source": "10-K Item 1"}],
        },
    )
    packages = [
        {
            "filing": {"accession_no": "0001", "form": "10-K", "filing_date": "2026-02-01", "document_url": "https://sec.example/filing"},
            "sections": [{"title": "Item 1 · Business", "status": "found", "text": "Alphabet business evidence", "source_url": "https://sec.example/filing"}],
        }
    ]
    settings = {
        "llm_enabled": True,
        "llm_provider_type": "openai_compatible",
        "llm_base_url": "https://api.example/v1",
        "llm_api_key": "test-key",
        "llm_model": "test-model",
    }

    draft = generate_company_research_draft("TEST", packages, settings)

    assert draft["status"] == "pending_confirmation"
    assert draft["draft"]["business_model"] == "通过广告和云业务赚钱。"
    assert list_research_drafts("TEST")[0]["source_accessions"] == ["0001"]

    confirmed = update_research_draft("TEST", draft["id"], status="confirmed")

    assert confirmed["status"] == "confirmed"
    with connect() as conn:
        company = conn.execute("SELECT research_summary_json FROM companies WHERE ticker = 'TEST'").fetchone()
        memo = conn.execute("SELECT thesis_json, business_moat, bear_case FROM investment_memos WHERE ticker = 'TEST'").fetchone()
    assert loads(company["research_summary_json"], {})["business_model"] == "通过广告和云业务赚钱。"
    assert "分发入口" in memo["business_moat"]
    assert loads(memo["thesis_json"], []) == ["AI 搜索", "云计算"]
