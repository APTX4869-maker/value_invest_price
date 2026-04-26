from __future__ import annotations

import json
import urllib.parse
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1d"
ALPHA_VANTAGE_QUOTE_URL = "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={api_key}"
FRED_DGS10_URL = "https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={api_key}&file_type=json&sort_order=desc&limit=10"
PRIMARY_TAXONOMIES = ("us-gaap", "ifrs-full")
_ticker_cache: dict[str, Any] = {"loaded_at": 0.0, "items": []}
COMMON_COMPANY_TICKERS = {
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOG",
    "GOOGL",
    "AMZN",
    "META",
    "TSLA",
    "NFLX",
    "AMD",
    "AVGO",
    "CRM",
    "ORCL",
    "ADBE",
    "PYPL",
    "PLTR",
    "SHOP",
    "UBER",
    "ABNB",
    "COST",
    "V",
    "MA",
    "UNH",
    "JPM",
}
FUND_NAME_HINTS = ("FUND", "TRUST", "ETF", "INCOME", "MUNICIPAL", "CLOSED-END")


def get_json(url: str, user_agent: str, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def find_cik(ticker: str, user_agent: str) -> tuple[str, str]:
    wanted = ticker.upper()
    for row in get_ticker_directory(user_agent):
        if row["ticker"] == wanted:
            return row["cik"], row["name"]
    raise ValueError(f"SEC 没找到 ticker: {ticker}")


def get_ticker_directory(user_agent: str) -> list[dict[str, str]]:
    now = time.time()
    if _ticker_cache["items"] and now - _ticker_cache["loaded_at"] < 24 * 60 * 60:
        return _ticker_cache["items"]
    data = get_json(SEC_TICKERS_URL, user_agent)
    items = [
        {
            "ticker": str(row.get("ticker", "")).upper(),
            "name": row.get("title", ""),
            "cik": str(row.get("cik_str", "")).zfill(10),
        }
        for row in data.values()
        if row.get("ticker")
    ]
    _ticker_cache["items"] = items
    _ticker_cache["loaded_at"] = now
    return items


def search_tickers(query: str, user_agent: str, limit: int = 8) -> list[dict[str, str]]:
    text = query.strip().upper()
    if not text:
        return []
    items = get_ticker_directory(user_agent)

    def score(item: dict[str, str]) -> tuple[int, int, int, str]:
        ticker = item["ticker"]
        name = item["name"].upper()
        fund_penalty = 1 if any(hint in name for hint in FUND_NAME_HINTS) else 0
        if ticker == text:
            bucket = 0
        elif ticker in COMMON_COMPANY_TICKERS and ticker.startswith(text):
            bucket = 1
        elif ticker.startswith(text):
            bucket = 2
        elif text in ticker:
            bucket = 3
        elif name.startswith(text):
            bucket = 4
        elif text in name:
            bucket = 5
        else:
            bucket = 9
        return bucket, fund_penalty, len(ticker), ticker

    matches = [item for item in items if score(item)[0] < 9]
    matches.sort(key=score)
    return matches[:limit]


def latest_annual_value(
    facts: dict[str, Any],
    tag_candidates: list[str],
    unit_candidates: list[str],
    taxonomy_candidates: tuple[str, ...] = PRIMARY_TAXONOMIES,
) -> tuple[float | None, int | None]:
    all_facts = facts.get("facts", {})
    best: tuple[str, str, float, int] | None = None
    for taxonomy in taxonomy_candidates:
        taxonomy_facts = all_facts.get(taxonomy, {})
        for tag in tag_candidates:
            tag_data = taxonomy_facts.get(tag, {})
            units = tag_data.get("units", {})
            for unit in unit_candidates:
                for item in units.get(unit, []):
                    form = item.get("form", "")
                    value = item.get("val")
                    end = item.get("end")
                    start = item.get("start")
                    frame = item.get("frame", "")
                    if value is None or not end:
                        continue
                    end_year = int(end[:4])
                    is_balance_sheet_item = not start
                    duration_days = 0
                    if start:
                        duration_days = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
                    annual_duration = is_balance_sheet_item or duration_days >= 330
                    frame_matches_period = not frame or frame == f"CY{end_year}"
                    is_annual = form in {"10-K", "20-F", "40-F"} and annual_duration and frame_matches_period
                    if not is_annual:
                        continue
                    key = (end, item.get("filed", ""))
                    if best is None or key > (best[0], best[1]):
                        best = (end, item.get("filed", ""), float(value), end_year)
    if best is None:
        return None, None
    return best[2], best[3]


def annual_values(
    facts: dict[str, Any],
    tag_candidates: list[str],
    unit_candidates: list[str],
    taxonomy_candidates: tuple[str, ...] = PRIMARY_TAXONOMIES,
) -> dict[int, float]:
    values: dict[int, tuple[str, str, float]] = {}
    all_facts = facts.get("facts", {})
    for taxonomy in taxonomy_candidates:
        taxonomy_facts = all_facts.get(taxonomy, {})
        for tag in tag_candidates:
            tag_data = taxonomy_facts.get(tag, {})
            units = tag_data.get("units", {})
            for unit in unit_candidates:
                for item in units.get(unit, []):
                    form = item.get("form", "")
                    value = item.get("val")
                    end = item.get("end")
                    start = item.get("start")
                    frame = item.get("frame", "")
                    if value is None or not end or not start:
                        continue
                    end_year = int(end[:4])
                    duration_days = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
                    frame_matches_period = not frame or frame == f"CY{end_year}"
                    is_annual = form in {"10-K", "20-F", "40-F"} and duration_days >= 330 and frame_matches_period
                    if not is_annual:
                        continue
                    key = (end, item.get("filed", ""))
                    if end_year not in values or key > (values[end_year][0], values[end_year][1]):
                        values[end_year] = (end, item.get("filed", ""), float(value))
    return {year: value for year, (_, _, value) in values.items()}


def build_annual_history(facts: dict[str, Any], fields: dict[str, tuple[list[str], list[str]]]) -> list[dict[str, Any]]:
    series_by_key: dict[str, dict[int, float]] = {}
    years: set[int] = set()
    for key in ["revenue", "operating_income", "ocf", "capex", "sbc"]:
        tags, units = fields[key]
        values = annual_values(facts, tags, units)
        if key == "capex":
            values = {year: abs(value) for year, value in values.items()}
        series_by_key[key] = values
        years.update(values.keys())

    history: list[dict[str, Any]] = []
    for year in sorted(years)[-6:]:
        row = {"fiscal_year": year}
        has_any = False
        for key, values in series_by_key.items():
            value = values.get(year)
            row[key] = value
            has_any = has_any or value is not None
        if has_any:
            history.append(row)
    return history


def detect_reporting_currency(
    facts: dict[str, Any],
    tag_candidates: list[str],
    taxonomy_candidates: tuple[str, ...] = PRIMARY_TAXONOMIES,
) -> str | None:
    all_facts = facts.get("facts", {})
    for taxonomy in taxonomy_candidates:
        taxonomy_facts = all_facts.get(taxonomy, {})
        for tag in tag_candidates:
            units = taxonomy_facts.get(tag, {}).get("units", {})
            if units:
                return next(iter(units.keys()))
    return None


def fetch_price_yahoo(ticker: str, user_agent: str) -> float | None:
    try:
        data = get_json(YAHOO_CHART_URL.format(ticker=ticker), user_agent)
        result = data.get("chart", {}).get("result", [{}])[0]
        price = result.get("meta", {}).get("regularMarketPrice")
        return float(price) if price is not None else None
    except (urllib.error.URLError, KeyError, ValueError, TypeError):
        return None


def fetch_price_alpha_vantage(ticker: str, api_key: str | None, user_agent: str) -> float | None:
    if not api_key:
        return None
    try:
        url = ALPHA_VANTAGE_QUOTE_URL.format(
            ticker=urllib.parse.quote(ticker),
            api_key=urllib.parse.quote(api_key),
        )
        data = get_json(url, user_agent)
        quote = data.get("Global Quote", {})
        price = quote.get("05. price")
        return float(price) if price not in (None, "") else None
    except (urllib.error.URLError, KeyError, ValueError, TypeError):
        return None


def fetch_price(ticker: str, user_agent: str, alpha_vantage_api_key: str | None = None) -> tuple[float | None, str]:
    yahoo_price = fetch_price_yahoo(ticker, user_agent)
    if yahoo_price is not None:
        return yahoo_price, "Yahoo chart"
    alpha_price = fetch_price_alpha_vantage(ticker, alpha_vantage_api_key, user_agent)
    if alpha_price is not None:
        return alpha_price, "Alpha Vantage GLOBAL_QUOTE"
    return None, "未获取到行情"


def fetch_ten_year_yield(api_key: str | None, fallback_yield: float, user_agent: str) -> tuple[float, str]:
    if not api_key:
        return fallback_yield, "本地默认值"
    try:
        url = FRED_DGS10_URL.format(api_key=urllib.parse.quote(api_key))
        data = get_json(url, user_agent)
        observations = data.get("observations", [])
        for observation in observations:
            value = observation.get("value")
            if value and value != ".":
                return float(value) / 100.0, f"FRED DGS10 ({observation.get('date')})"
    except (urllib.error.URLError, KeyError, ValueError, TypeError):
        pass
    return fallback_yield, "本地默认值"


def fetch_company_facts(
    ticker: str,
    user_agent: str,
    fallback_yield: float,
    alpha_vantage_api_key: str | None = None,
    fred_api_key: str | None = None,
) -> dict[str, Any]:
    cik, name = find_cik(ticker, user_agent)
    facts = get_json(SEC_FACTS_URL.format(cik=cik), user_agent)
    submissions = get_json(SEC_SUBMISSIONS_URL.format(cik=cik), user_agent)
    fields = {
        "revenue": (["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet", "Revenue"], ["USD"]),
        "operating_income": (["OperatingIncomeLoss", "ProfitLossFromOperatingActivities"], ["USD"]),
        "ocf": (["NetCashProvidedByUsedInOperatingActivities", "CashFlowsFromUsedInOperatingActivities"], ["USD"]),
        "capex": (
            [
                "PaymentsToAcquirePropertyPlantAndEquipment",
                "PaymentsToAcquireProductiveAssets",
                "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
            ],
            ["USD"],
        ),
        "sbc": (["ShareBasedCompensation", "ExpenseFromSharebasedPaymentTransactionsWithEmployees"], ["USD"]),
        "cash": (
            [
                "CashAndCashEquivalentsAtCarryingValue",
                "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                "CashAndCashEquivalents",
            ],
            ["USD"],
        ),
        "short_investments": (["MarketableSecuritiesCurrent", "ShortTermInvestments"], ["USD"]),
        "debt_current": (["LongTermDebtCurrent", "ShortTermBorrowings", "CurrentPortionOfLongtermBorrowings"], ["USD"]),
        "debt_long_term": (["LongTermDebtNoncurrent", "LongTermDebt", "LongtermBorrowings", "Borrowings"], ["USD"]),
        "diluted_shares": (
            [
                "WeightedAverageNumberOfDilutedSharesOutstanding",
                "AdjustedWeightedAverageShares",
                "WeightedAverageShares",
                "NumberOfSharesOutstanding",
            ],
            ["shares"],
        ),
    }
    output: dict[str, Any] = {
        "ticker": ticker.upper(),
        "name": submissions.get("name") or name,
        "cik": cik,
        "sec_meta": {
            "sic": submissions.get("sic"),
            "sic_description": submissions.get("sicDescription"),
            "fiscal_year_end": submissions.get("fiscalYearEnd"),
            "exchanges": submissions.get("exchanges", []),
        },
    }
    fiscal_years: list[int] = []
    for key, (tags, units) in fields.items():
        value, fy = latest_annual_value(facts, tags, units)
        output[key] = abs(value) if key == "capex" and value is not None else value
        if fy:
            fiscal_years.append(fy)
    output["annual_history"] = build_annual_history(facts, fields)
    output["fiscal_year"] = max(fiscal_years) if fiscal_years else None
    reporting_currency = detect_reporting_currency(
        facts,
        [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "Revenue",
            "CashFlowsFromUsedInOperatingActivities",
            "CashAndCashEquivalents",
        ],
    )
    if reporting_currency and reporting_currency != "USD" and not output["revenue"] and not output["ocf"]:
        raise ValueError(
            f"{ticker.upper()} 使用 {reporting_currency} 披露财报。当前免费版估值模型暂不支持自动汇率转换，"
            "请先手动换算关键财务数据后再分析，或优先选择以美元披露的公司。"
        )
    output["price"], output["price_source"] = fetch_price(ticker, user_agent, alpha_vantage_api_key)
    output["ten_year_yield"], output["ten_year_yield_source"] = fetch_ten_year_yield(fred_api_key, fallback_yield, user_agent)
    output["source"] = f"SEC companyfacts + 免费行情/利率源，刷新于 {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    output["raw_json"] = {
        "cik": cik,
        "sec_name": output["name"],
        "sec_meta": output["sec_meta"],
        "reporting_currency": reporting_currency or "USD",
    }
    return output
