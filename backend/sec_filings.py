from __future__ import annotations

import html
import re
from typing import Any

from .data_sources import SEC_SUBMISSIONS_URL, find_cik, get_json, get_text
from .db import connect, dumps, loads, now_iso, row_to_dict


SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

SECTION_SPECS = {
    "business": {
        "forms": {"10-K", "10-K/A"},
        "title": "Item 1 · Business",
        "patterns": [r"\bITEM\s+1[\.\s:-]+BUSINESS\b"],
    },
    "risk_factors": {
        "forms": {"10-K", "10-K/A", "10-Q", "10-Q/A"},
        "title": "Item 1A · Risk Factors",
        "patterns": [r"\bITEM\s+1A[\.\s:-]+RISK\s+FACTORS\b"],
    },
    "mda": {
        "forms": {"10-K", "10-K/A"},
        "title": "Item 7 · MD&A",
        "patterns": [
            r"\bITEM\s+7[\.\s:-]+MANAGEMENT['’]S\s+DISCUSSION\s+AND\s+ANALYSIS\b",
            r"\bITEM\s+7[\.\s:-]+MD&A\b",
        ],
    },
    "quarterly_mda": {
        "forms": {"10-Q", "10-Q/A"},
        "title": "Item 2 · Quarterly MD&A",
        "patterns": [
            r"\bITEM\s+2[\.\s:-]+MANAGEMENT['’]S\s+DISCUSSION\s+AND\s+ANALYSIS\b",
            r"\bITEM\s+2[\.\s:-]+MD&A\b",
        ],
    },
}

ITEM_HEADING_RE = re.compile(
    r"\bITEM\s+(?:1A|1B|1C|1|2|3|4|5|6|7A|7|8|9A|9B|9C|9|10|11|12|13|14|15|16)[\.\s:-]+",
    re.IGNORECASE,
)


def filing_url(cik: str, accession_no: str, primary_document: str) -> str:
    cik_path = str(int(cik))
    accession_path = accession_no.replace("-", "")
    return f"{SEC_ARCHIVES_BASE}/{cik_path}/{accession_path}/{primary_document}"


def list_company_filings(
    ticker: str,
    user_agent: str,
    forms: set[str] | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    cik, name = find_cik(ticker, user_agent)
    submissions = get_json(SEC_SUBMISSIONS_URL.format(cik=cik), user_agent)
    recent = submissions.get("filings", {}).get("recent", {})
    wanted = forms or {"10-K", "10-Q", "10-K/A", "10-Q/A"}
    count = len(recent.get("accessionNumber", []))
    filings: list[dict[str, Any]] = []
    for index in range(count):
        form = str(_recent_value(recent, "form", index) or "")
        primary_document = str(_recent_value(recent, "primaryDocument", index) or "")
        accession_no = str(_recent_value(recent, "accessionNumber", index) or "")
        if form not in wanted or not primary_document or not accession_no:
            continue
        filing = {
            "ticker": ticker.upper(),
            "company_name": submissions.get("name") or name,
            "cik": cik,
            "accession_no": accession_no,
            "form": form,
            "filing_date": _recent_value(recent, "filingDate", index) or "",
            "report_date": _recent_value(recent, "reportDate", index) or "",
            "primary_document": primary_document,
            "document_url": filing_url(cik, accession_no, primary_document),
            "index_url": f"{SEC_ARCHIVES_BASE}/{int(cik)}/{accession_no.replace('-', '')}/",
        }
        filings.append(filing)
        if len(filings) >= limit:
            break
    return {
        "ticker": ticker.upper(),
        "company_name": submissions.get("name") or name,
        "cik": cik,
        "filings": filings,
        "updated_at": now_iso(),
    }


def _recent_value(recent: dict[str, list[Any]], key: str, index: int) -> Any:
    values = recent.get(key, [])
    return values[index] if index < len(values) else None


def html_to_readable_text(markup: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", markup)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</(p|div|tr|table|section|article|h[1-6])>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_filing_sections(markup_or_text: str, form: str) -> list[dict[str, Any]]:
    text = html_to_readable_text(markup_or_text)
    upper_text = text.upper()
    headings = [match for match in ITEM_HEADING_RE.finditer(upper_text)]
    sections: list[dict[str, Any]] = []
    for key, spec in SECTION_SPECS.items():
        if form not in spec["forms"]:
            continue
        candidates = []
        for pattern in spec["patterns"]:
            for match in re.finditer(pattern, upper_text, re.IGNORECASE):
                end = _next_heading_position(headings, match.start())
                section_text = text[match.start():end].strip()
                word_count = len(section_text.split())
                if word_count >= 80:
                    candidates.append((word_count, section_text))
        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            section_text = _clean_section_text(candidates[0][1])
            sections.append({
                "key": key,
                "title": spec["title"],
                "status": "found",
                "text": section_text[:24000],
                "excerpt": _excerpt(section_text),
                "word_count": len(section_text.split()),
            })
        else:
            sections.append({
                "key": key,
                "title": spec["title"],
                "status": "missing",
                "text": "",
                "excerpt": "",
                "word_count": 0,
            })
    return sections


def _next_heading_position(headings: list[re.Match[str]], start: int) -> int:
    for heading in headings:
        if heading.start() > start + 30:
            return heading.start()
    return 10**12


def _clean_section_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _excerpt(text: str, limit: int = 900) -> str:
    single_line = re.sub(r"\s+", " ", text).strip()
    if len(single_line) <= limit:
        return single_line
    return single_line[:limit].rsplit(" ", 1)[0] + "..."


def build_research_package_for_filing(filing: dict[str, Any], user_agent: str) -> dict[str, Any]:
    markup = get_text(filing["document_url"], user_agent, timeout=30, retries=2)
    sections = extract_filing_sections(markup, filing["form"])
    found_count = len([section for section in sections if section["status"] == "found"])
    return {
        "filing": filing,
        "sections": [
            {
                **section,
                "source_url": filing["document_url"],
                "citation": f"{filing['form']} · {filing.get('filing_date') or filing.get('report_date')} · {section['title']}",
            }
            for section in sections
        ],
        "quality": {
            "found_count": found_count,
            "total": len(sections),
            "missing": [section["title"] for section in sections if section["status"] != "found"],
        },
        "fetched_at": now_iso(),
    }


def refresh_company_research_package(ticker: str, user_agent: str, filings_limit: int = 2) -> dict[str, Any]:
    listing = list_company_filings(ticker, user_agent, forms={"10-K", "10-Q"}, limit=max(1, filings_limit))
    packages = []
    errors = []
    for filing in listing["filings"]:
        try:
            package = build_research_package_for_filing(filing, user_agent)
            save_research_package(ticker, package)
            packages.append(package)
        except Exception as exc:
            errors.append({
                "accession_no": filing.get("accession_no"),
                "form": filing.get("form"),
                "message": str(exc),
            })
    return {
        "ticker": ticker.upper(),
        "company_name": listing.get("company_name", ""),
        "cik": listing.get("cik", ""),
        "filings": listing["filings"],
        "packages": packages,
        "errors": errors,
        "updated_at": now_iso(),
    }


def save_research_package(ticker: str, package: dict[str, Any]) -> None:
    filing = package["filing"]
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sec_filings
            (ticker, accession_no, form, filing_date, report_date, primary_document,
             document_url, sections_json, source, fetched_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, accession_no) DO UPDATE SET
                form = excluded.form,
                filing_date = excluded.filing_date,
                report_date = excluded.report_date,
                primary_document = excluded.primary_document,
                document_url = excluded.document_url,
                sections_json = excluded.sections_json,
                source = excluded.source,
                fetched_at = excluded.fetched_at,
                updated_at = excluded.updated_at
            """,
            (
                ticker.upper(),
                filing["accession_no"],
                filing["form"],
                filing.get("filing_date", ""),
                filing.get("report_date", ""),
                filing.get("primary_document", ""),
                filing.get("document_url", ""),
                dumps(package["sections"]),
                "SEC EDGAR filing document",
                package["fetched_at"],
                ts,
                ts,
            ),
        )


def get_cached_research_package(ticker: str) -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM sec_filings
            WHERE ticker = ?
            ORDER BY filing_date DESC, fetched_at DESC
            """,
            (ticker.upper(),),
        ).fetchall()
    packages = []
    for row in rows:
        item = row_to_dict(row)
        filing = {
            "ticker": item["ticker"],
            "accession_no": item["accession_no"],
            "form": item["form"],
            "filing_date": item["filing_date"],
            "report_date": item["report_date"],
            "primary_document": item["primary_document"],
            "document_url": item["document_url"],
        }
        sections = loads(item.get("sections_json"), [])
        packages.append({
            "filing": filing,
            "sections": sections,
            "quality": {
                "found_count": len([section for section in sections if section.get("status") == "found"]),
                "total": len(sections),
                "missing": [section.get("title") for section in sections if section.get("status") != "found"],
            },
            "fetched_at": item.get("fetched_at"),
        })
    return {
        "ticker": ticker.upper(),
        "packages": packages,
        "updated_at": packages[0]["fetched_at"] if packages else None,
    }
