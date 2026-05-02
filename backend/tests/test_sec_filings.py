import backend.db as db_module
from backend.db import init_db
from backend.sec_filings import extract_filing_sections, get_cached_research_package, list_company_filings, save_research_package


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    init_db()


def _words(seed: str, count: int = 120) -> str:
    return " ".join(f"{seed}{index}" for index in range(count))


def test_extract_10k_sections_from_html():
    html = f"""
    <html><body>
      <h1>Item 1. Business</h1><p>{_words("business")}</p>
      <h1>Item 1A. Risk Factors</h1><p>{_words("risk")}</p>
      <h1>Item 7. Management's Discussion and Analysis</h1><p>{_words("mda")}</p>
      <h1>Item 7A. Quantitative and Qualitative Disclosures</h1><p>stop here</p>
    </body></html>
    """

    sections = extract_filing_sections(html, "10-K")
    found = {section["key"]: section for section in sections if section["status"] == "found"}

    assert set(found) == {"business", "risk_factors", "mda"}
    assert found["business"]["excerpt"].startswith("Item 1. Business")
    assert "mda1" in found["mda"]["text"]
    assert "stop here" not in found["mda"]["text"]


def test_list_company_filings_builds_sec_urls(monkeypatch):
    monkeypatch.setattr("backend.sec_filings.find_cik", lambda ticker, user_agent: ("0001652044", "Alphabet Inc."))
    monkeypatch.setattr(
        "backend.sec_filings.get_json",
        lambda url, user_agent: {
            "name": "Alphabet Inc.",
            "filings": {
                "recent": {
                    "accessionNumber": ["0001652044-26-000001", "0001652044-26-000002"],
                    "form": ["10-K", "8-K"],
                    "filingDate": ["2026-02-01", "2026-02-02"],
                    "reportDate": ["2025-12-31", "2026-01-31"],
                    "primaryDocument": ["goog-20251231.htm", "goog-8k.htm"],
                }
            },
        },
    )

    result = list_company_filings("GOOG", "ua", forms={"10-K"}, limit=4)

    assert len(result["filings"]) == 1
    assert result["filings"][0]["document_url"].endswith("/1652044/000165204426000001/goog-20251231.htm")


def test_save_and_read_cached_research_package(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    package = {
        "filing": {
            "ticker": "GOOG",
            "accession_no": "0001652044-26-000001",
            "form": "10-K",
            "filing_date": "2026-02-01",
            "report_date": "2025-12-31",
            "primary_document": "goog-20251231.htm",
            "document_url": "https://www.sec.gov/example.htm",
        },
        "sections": [{"key": "business", "title": "Item 1 · Business", "status": "found", "text": "abc", "excerpt": "abc", "word_count": 1}],
        "fetched_at": "2026-05-02T00:00:00+00:00",
    }

    save_research_package("GOOG", package)
    cached = get_cached_research_package("GOOG")

    assert cached["packages"][0]["filing"]["form"] == "10-K"
    assert cached["packages"][0]["quality"]["found_count"] == 1
