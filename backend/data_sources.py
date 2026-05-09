from __future__ import annotations

import http.client
import html
import hashlib
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

from .db import connect, dumps, loads, now_iso


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1d"
ALPHA_VANTAGE_QUOTE_URL = "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={api_key}"
ALPHA_VANTAGE_QUERY_URL = "https://www.alphavantage.co/query"
FINNHUB_API_BASE = "https://finnhub.io/api/v1"
FRED_DGS10_URL = "https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={api_key}&file_type=json&sort_order=desc&limit=10"
FMP_API_BASE = "https://financialmodelingprep.com/api/v3"
FMP_STABLE_API_BASE = "https://financialmodelingprep.com/stable"
QQQ_HOLDINGS_URL = "https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/QQQ/holdings/fund?idType=ticker&interval=monthly&productType=ETF&loadType=initial"
SP500_SLICKCHARTS_URL = "https://www.slickcharts.com/sp500"
SP500_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
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
FINANCIAL_SIC_PREFIXES = ("60", "61", "62", "63", "64", "67")
TRANSIENT_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}


class DataSourceError(RuntimeError):
    """Base class for upstream data-source failures."""


class DataSourceNetworkError(DataSourceError):
    """Raised when an upstream source cannot be reached reliably."""


class DataSourceResponseError(DataSourceError):
    """Raised when an upstream source responds with unusable data."""


class UnsupportedTickerError(ValueError):
    """Raised when SEC cannot map a ticker to a supported public company."""


def _source_name(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc or "数据源"
    if "sec.gov" in host:
        return "SEC 数据源"
    if "finance.yahoo.com" in host:
        return "Yahoo 行情源"
    if "alphavantage.co" in host:
        return "Alpha Vantage 行情源"
    if "stlouisfed.org" in host:
        return "FRED 利率源"
    if "financialmodelingprep.com" in host:
        return "FMP 数据源"
    return host


def _sleep_before_retry(attempt: int) -> None:
    time.sleep(0.35 * (attempt + 1))


def _friendly_error_text(error: Exception) -> str:
    reason = getattr(error, "reason", None)
    return str(reason or error)


def is_financial_sec_meta(sec_meta: dict[str, Any]) -> bool:
    sic = str(sec_meta.get("sic") or "")
    description = str(sec_meta.get("sic_description") or sec_meta.get("sicDescription") or "").lower()
    return sic.startswith(FINANCIAL_SIC_PREFIXES) or any(
        word in description
        for word in ["finance", "financial", "bank", "credit", "lending", "loan", "insurance", "broker", "mortgage"]
    )


def get_json(url: str, user_agent: str, timeout: int = 20, retries: int = 2) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Connection": "close",
        },
    )
    source = _source_name(url)
    attempts = max(1, retries + 1)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in TRANSIENT_HTTP_STATUS_CODES and attempt < attempts - 1:
                _sleep_before_retry(attempt)
                continue
            if exc.code in TRANSIENT_HTTP_STATUS_CODES:
                raise DataSourceNetworkError(f"{source} 暂时不可用（HTTP {exc.code}），系统已自动重试。") from exc
            raise DataSourceResponseError(f"{source} 返回 HTTP {exc.code}，当前免费接口没有返回可用数据。") from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError, http.client.HTTPException) as exc:
            last_error = exc
            if attempt < attempts - 1:
                _sleep_before_retry(attempt)
                continue
            raise DataSourceNetworkError(f"{source} 连接中断或超时，系统已自动重试：{_friendly_error_text(exc)}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise DataSourceResponseError(f"{source} 返回的数据不是有效 JSON。") from exc
    detail = _friendly_error_text(last_error) if last_error else "未知错误"
    raise DataSourceNetworkError(f"{source} 连接失败，系统已自动重试：{detail}")


def _external_cache_key(provider: str, endpoint: str, params: dict[str, Any]) -> str:
    clean_params = {key: value for key, value in params.items() if key.lower() not in {"apikey", "token"}}
    raw = json.dumps({"provider": provider, "endpoint": endpoint, "params": clean_params}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _record_api_usage(provider: str, endpoint: str, cache_key: str, cache_hit: bool, status: str) -> None:
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO external_api_usage
                (provider, endpoint, cache_key, cache_hit, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (provider, endpoint, cache_key, 1 if cache_hit else 0, status, now_iso()),
            )
    except Exception:
        pass


def _cached_provider_json(
    provider: str,
    endpoint: str,
    params: dict[str, Any],
    url: str,
    user_agent: str,
    ttl_seconds: int = 24 * 60 * 60,
) -> Any:
    cache_key = _external_cache_key(provider, endpoint, params)
    now_ts = time.time()
    if not any(value == "demo-key" for value in params.values()):
        try:
            with connect() as conn:
                row = conn.execute(
                    """
                    SELECT payload_json, status, expires_at
                    FROM external_api_cache
                    WHERE provider = ? AND cache_key = ?
                    """,
                    (provider, cache_key),
                ).fetchone()
                if row:
                    expires_at = datetime.fromisoformat(row["expires_at"]).timestamp()
                    if expires_at > now_ts:
                        payload = loads(row["payload_json"], {})
                        _record_api_usage(provider, endpoint, cache_key, True, row["status"] or "cache")
                        if row["status"] == "ok":
                            return payload
                        raise DataSourceResponseError(str((payload or {}).get("error") or f"{provider} cached error"))
        except DataSourceError:
            raise
        except Exception:
            pass

    try:
        data = get_json(url, user_agent, timeout=25, retries=1)
    except DataSourceError as exc:
        fetched_at = now_iso()
        expires_at = datetime.fromtimestamp(now_ts + ttl_seconds, timezone.utc).isoformat(timespec="seconds")
        try:
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO external_api_cache
                    (provider, cache_key, endpoint, status, payload_json, fetched_at, expires_at)
                    VALUES (?, ?, ?, 'error', ?, ?, ?)
                    ON CONFLICT(provider, cache_key) DO UPDATE SET
                        endpoint = excluded.endpoint,
                        status = excluded.status,
                        payload_json = excluded.payload_json,
                        fetched_at = excluded.fetched_at,
                        expires_at = excluded.expires_at
                    """,
                    (provider, cache_key, endpoint, dumps({"error": str(exc)}), fetched_at, expires_at),
                )
        except Exception:
            pass
        _record_api_usage(provider, endpoint, cache_key, False, "error")
        raise

    fetched_at = now_iso()
    expires_at = datetime.fromtimestamp(now_ts + ttl_seconds, timezone.utc).isoformat(timespec="seconds")
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO external_api_cache
                (provider, cache_key, endpoint, status, payload_json, fetched_at, expires_at)
                VALUES (?, ?, ?, 'ok', ?, ?, ?)
                ON CONFLICT(provider, cache_key) DO UPDATE SET
                    endpoint = excluded.endpoint,
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    fetched_at = excluded.fetched_at,
                    expires_at = excluded.expires_at
                """,
                (provider, cache_key, endpoint, dumps(data), fetched_at, expires_at),
            )
    except Exception:
        pass
    _record_api_usage(provider, endpoint, cache_key, False, "ok")
    return data


def external_api_usage_summary(hours: int = 24) -> dict[str, Any]:
    cutoff = datetime.fromtimestamp(time.time() - hours * 3600, timezone.utc).isoformat(timespec="seconds")
    summary: dict[str, Any] = {}
    try:
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT provider,
                       SUM(CASE WHEN cache_hit = 0 THEN 1 ELSE 0 END) AS network_calls,
                       SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) AS cache_hits,
                       SUM(CASE WHEN cache_hit = 0 AND status = 'error' THEN 1 ELSE 0 END) AS network_errors,
                       SUM(CASE WHEN cache_hit = 1 AND status = 'error' THEN 1 ELSE 0 END) AS cached_error_hits,
                       MAX(created_at) AS last_used_at
                FROM external_api_usage
                WHERE created_at >= ?
                GROUP BY provider
                """,
                (cutoff,),
            ).fetchall()
        for row in rows:
            summary[row["provider"]] = {
                "network_calls_24h": int(row["network_calls"] or 0),
                "cache_hits_24h": int(row["cache_hits"] or 0),
                "errors_24h": int(row["network_errors"] or 0),
                "cached_error_hits_24h": int(row["cached_error_hits"] or 0),
                "last_used_at": row["last_used_at"],
            }
    except Exception:
        pass
    return {"window_hours": hours, "providers": summary}


def get_text(url: str, user_agent: str, timeout: int = 20, retries: int = 2) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,text/plain",
            "Accept-Encoding": "identity",
            "Connection": "close",
        },
    )
    source = _source_name(url)
    attempts = max(1, retries + 1)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in TRANSIENT_HTTP_STATUS_CODES and attempt < attempts - 1:
                _sleep_before_retry(attempt)
                continue
            if exc.code in TRANSIENT_HTTP_STATUS_CODES:
                raise DataSourceNetworkError(f"{source} 暂时不可用（HTTP {exc.code}），系统已自动重试。") from exc
            raise DataSourceResponseError(f"{source} 返回 HTTP {exc.code}，当前免费接口没有返回可用页面。") from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError, http.client.HTTPException) as exc:
            last_error = exc
            if attempt < attempts - 1:
                _sleep_before_retry(attempt)
                continue
            raise DataSourceNetworkError(f"{source} 连接中断或超时，系统已自动重试：{_friendly_error_text(exc)}") from exc
    detail = _friendly_error_text(last_error) if last_error else "未知错误"
    raise DataSourceNetworkError(f"{source} 连接失败，系统已自动重试：{detail}")


def find_cik(ticker: str, user_agent: str) -> tuple[str, str]:
    wanted = ticker.upper()
    for row in get_ticker_directory(user_agent):
        if row["ticker"] == wanted:
            return row["cik"], row["name"]
    raise UnsupportedTickerError(f"SEC 没找到 ticker: {ticker}")


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
                    if is_balance_sheet_item:
                        frame_matches_period = not frame or frame.startswith(f"CY{end_year}")
                    else:
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


def latest_duration_value(
    facts: dict[str, Any],
    tag_candidates: list[str],
    unit_candidates: list[str],
    min_days: int,
    max_days: int,
    taxonomy_candidates: tuple[str, ...] = PRIMARY_TAXONOMIES,
) -> dict[str, Any] | None:
    all_facts = facts.get("facts", {})
    best: tuple[str, str, float, str, int, int | None, str] | None = None
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
                    if form not in {"10-Q", "10-K", "20-F", "40-F"} or value is None or not end or not start:
                        continue
                    duration_days = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
                    if not (min_days <= duration_days <= max_days):
                        continue
                    key = (end, item.get("filed", ""))
                    if best is None or key > (best[0], best[1]):
                        best = (
                            end,
                            item.get("filed", ""),
                            float(value),
                            start,
                            duration_days,
                            item.get("fy"),
                            item.get("fp", ""),
                        )
    if best is None:
        return None
    end, filed, value, start, duration_days, fiscal_year, fiscal_period = best
    return {
        "value": value,
        "start": start,
        "end": end,
        "filed": filed,
        "duration_days": duration_days,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
    }


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


def build_recent_period_snapshot(facts: dict[str, Any], fields: dict[str, tuple[list[str], list[str]]]) -> dict[str, Any]:
    revenue_q = latest_duration_value(facts, *fields["revenue"], min_days=70, max_days=115)
    operating_income_q = latest_duration_value(facts, *fields["operating_income"], min_days=70, max_days=115)
    shares_q = latest_duration_value(facts, *fields["diluted_shares"], min_days=70, max_days=115)
    ocf_ytd = latest_duration_value(facts, *fields["ocf"], min_days=150, max_days=285)
    capex_ytd = latest_duration_value(facts, *fields["capex"], min_days=150, max_days=285)

    latest_quarter: dict[str, Any] = {}
    if revenue_q:
        scale = 365 / max(1, revenue_q["duration_days"])
        latest_quarter.update({
            "revenue": revenue_q["value"],
            "annualized_revenue": revenue_q["value"] * scale,
            "start": revenue_q["start"],
            "end": revenue_q["end"],
            "filed": revenue_q["filed"],
            "duration_days": revenue_q["duration_days"],
            "fiscal_year": revenue_q.get("fiscal_year"),
            "fiscal_period": revenue_q.get("fiscal_period"),
        })
    if operating_income_q:
        scale = 365 / max(1, operating_income_q["duration_days"])
        latest_quarter["operating_income"] = operating_income_q["value"]
        latest_quarter["annualized_operating_income"] = operating_income_q["value"] * scale
    if shares_q:
        latest_quarter["diluted_shares"] = shares_q["value"]
    if latest_quarter.get("revenue"):
        latest_quarter["operating_margin"] = (latest_quarter.get("operating_income") or 0) / latest_quarter["revenue"]

    latest_ytd: dict[str, Any] = {}
    if ocf_ytd:
        scale = 365 / max(1, ocf_ytd["duration_days"])
        latest_ytd.update({
            "ocf": ocf_ytd["value"],
            "annualized_ocf": ocf_ytd["value"] * scale,
            "start": ocf_ytd["start"],
            "end": ocf_ytd["end"],
            "filed": ocf_ytd["filed"],
            "duration_days": ocf_ytd["duration_days"],
            "fiscal_year": ocf_ytd.get("fiscal_year"),
            "fiscal_period": ocf_ytd.get("fiscal_period"),
        })
    if capex_ytd:
        scale = 365 / max(1, capex_ytd["duration_days"])
        capex_value = abs(capex_ytd["value"])
        latest_ytd["capex"] = capex_value
        latest_ytd["annualized_capex"] = capex_value * scale
    if latest_ytd.get("ocf") is not None and latest_ytd.get("capex") is not None:
        latest_ytd["fcf"] = latest_ytd["ocf"] - latest_ytd["capex"]
        latest_ytd["annualized_fcf"] = latest_ytd["annualized_ocf"] - latest_ytd["annualized_capex"]

    return {
        "latest_quarter": latest_quarter,
        "latest_ytd": latest_ytd,
        "source": "SEC companyfacts recent 10-Q/10-K periods",
    }


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
    except (DataSourceError, urllib.error.URLError, KeyError, ValueError, TypeError):
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
    except (DataSourceError, urllib.error.URLError, KeyError, ValueError, TypeError):
        return None


def fetch_price(ticker: str, user_agent: str, alpha_vantage_api_key: str | None = None) -> tuple[float | None, str]:
    yahoo_price = fetch_price_yahoo(ticker, user_agent)
    if yahoo_price is not None:
        return yahoo_price, "Yahoo chart"
    alpha_price = fetch_price_alpha_vantage(ticker, alpha_vantage_api_key, user_agent)
    if alpha_price is not None:
        return alpha_price, "Alpha Vantage GLOBAL_QUOTE"
    return None, "未获取到行情"


def _alpha_vantage_url(function: str, ticker: str, api_key: str) -> str:
    return f"{ALPHA_VANTAGE_QUERY_URL}?{urllib.parse.urlencode({'function': function, 'symbol': ticker.upper(), 'apikey': api_key})}"


def _record_alpha_warning(warnings: list[str] | None, label: str, detail: str) -> None:
    if warnings is not None:
        warnings.append(f"Alpha Vantage {label} 不可用：{detail}")


def _alpha_vantage_get(
    function: str,
    ticker: str,
    api_key: str | None,
    user_agent: str,
    warnings: list[str] | None = None,
) -> dict[str, Any] | None:
    if not api_key:
        return None
    try:
        params = {"function": function, "symbol": ticker.upper()}
        data = _cached_provider_json(
            "alpha_vantage",
            function,
            params,
            _alpha_vantage_url(function, ticker, api_key),
            user_agent,
        )
    except DataSourceError as exc:
        _record_alpha_warning(warnings, function, str(exc))
        return None
    if not isinstance(data, dict) or not data:
        _record_alpha_warning(warnings, function, "返回空数据")
        return None
    for key in ["Note", "Information", "Error Message"]:
        if data.get(key):
            _record_alpha_warning(warnings, function, str(data.get(key)))
            return None
    return data


def _alpha_num(row: dict[str, Any] | None, *keys: str) -> float | None:
    if not row:
        return None
    for key in keys:
        value = row.get(key)
        if value in (None, "", "None"):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _alpha_year(row: dict[str, Any] | None) -> int | None:
    if not row:
        return None
    raw = row.get("fiscalDateEnding")
    if raw is None:
        return None
    try:
        return int(str(raw)[:4])
    except ValueError:
        return None


def _alpha_reports_by_year(payload: dict[str, Any] | None, key: str = "annualReports") -> dict[int, dict[str, Any]]:
    rows = (payload or {}).get(key)
    if not isinstance(rows, list):
        return {}
    output: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        year = _alpha_year(row)
        if year is not None:
            output[year] = row
    return output


def _build_alpha_vantage_annual_history(
    income: dict[str, Any] | None,
    balance: dict[str, Any] | None,
    cash: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    income_by_year = _alpha_reports_by_year(income)
    balance_by_year = _alpha_reports_by_year(balance)
    cash_by_year = _alpha_reports_by_year(cash)
    years = sorted(set(income_by_year) | set(balance_by_year) | set(cash_by_year))[-6:]
    history: list[dict[str, Any]] = []
    for year in years:
        income_row = income_by_year.get(year)
        cash_row = cash_by_year.get(year)
        row = {
            "fiscal_year": year,
            "revenue": _alpha_num(income_row, "totalRevenue"),
            "operating_income": _alpha_num(income_row, "operatingIncome"),
            "ocf": _alpha_num(cash_row, "operatingCashflow"),
            "capex": abs(_alpha_num(cash_row, "capitalExpenditures") or 0) or None,
            "sbc": _alpha_num(cash_row, "shareBasedCompensation", "stockBasedCompensation"),
            "source": "Alpha Vantage standardized statements",
        }
        if any(row.get(key) is not None for key in ["revenue", "operating_income", "ocf", "capex", "sbc"]):
            history.append(row)
    return history


def _build_alpha_vantage_enrichment(overview: dict[str, Any] | None) -> dict[str, Any]:
    target = _alpha_num(overview, "AnalystTargetPrice")
    return {
        "overview": overview or {},
        "normalized": {
            "market_cap": _alpha_num(overview, "MarketCapitalization"),
            "shares_outstanding": _alpha_num(overview, "SharesOutstanding"),
            "beta": _alpha_num(overview, "Beta"),
            "pe_ratio": _alpha_num(overview, "PERatio"),
            "peg_ratio": _alpha_num(overview, "PEGRatio"),
            "eps": _alpha_num(overview, "EPS", "DilutedEPSTTM"),
            "profit_margin": _alpha_num(overview, "ProfitMargin"),
            "operating_margin_ttm": _alpha_num(overview, "OperatingMarginTTM"),
            "roe_ttm": _alpha_num(overview, "ReturnOnEquityTTM"),
            "roa_ttm": _alpha_num(overview, "ReturnOnAssetsTTM"),
            "quarterly_revenue_growth_yoy": _alpha_num(overview, "QuarterlyRevenueGrowthYOY"),
            "quarterly_earnings_growth_yoy": _alpha_num(overview, "QuarterlyEarningsGrowthYOY"),
            "analyst_target_price": target,
        },
        "price_target": {
            "target_low": target,
            "target_median": target,
            "target_consensus": target,
            "target_high": target,
            "source": "Alpha Vantage OVERVIEW AnalystTargetPrice",
        } if target else None,
    }


def fetch_alpha_vantage_company_data(ticker: str, api_key: str | None, user_agent: str) -> dict[str, Any] | None:
    if not api_key:
        return None
    warnings: list[str] = []
    overview = _alpha_vantage_get("OVERVIEW", ticker, api_key, user_agent, warnings)
    income = _alpha_vantage_get("INCOME_STATEMENT", ticker, api_key, user_agent, warnings)
    balance = _alpha_vantage_get("BALANCE_SHEET", ticker, api_key, user_agent, warnings)
    cash = _alpha_vantage_get("CASH_FLOW", ticker, api_key, user_agent, warnings)

    income_latest = ((income or {}).get("annualReports") or [{}])[0]
    balance_latest = ((balance or {}).get("annualReports") or [{}])[0]
    cash_latest = ((cash or {}).get("annualReports") or [{}])[0]
    latest = {
        "fiscal_year": _alpha_year(income_latest) or _alpha_year(balance_latest) or _alpha_year(cash_latest),
        "revenue": _alpha_num(income_latest, "totalRevenue"),
        "operating_income": _alpha_num(income_latest, "operatingIncome"),
        "ocf": _alpha_num(cash_latest, "operatingCashflow"),
        "capex": abs(_alpha_num(cash_latest, "capitalExpenditures") or 0) or None,
        "sbc": _alpha_num(cash_latest, "shareBasedCompensation", "stockBasedCompensation"),
        "cash": _alpha_num(balance_latest, "cashAndCashEquivalentsAtCarryingValue", "cashAndShortTermInvestments"),
        "short_investments": _alpha_num(balance_latest, "shortTermInvestments"),
        "debt_current": _alpha_num(balance_latest, "shortTermDebt", "currentDebt"),
        "debt_long_term": _alpha_num(balance_latest, "longTermDebt", "longTermDebtNoncurrent"),
        "diluted_shares": _alpha_num(balance_latest, "commonStockSharesOutstanding") or _alpha_num(overview, "SharesOutstanding"),
    }
    annual_history = _build_alpha_vantage_annual_history(income, balance, cash)
    enrichment = _build_alpha_vantage_enrichment(overview)
    available = {
        "overview": bool(overview),
        "income_statement": bool((income or {}).get("annualReports")),
        "balance_sheet": bool((balance or {}).get("annualReports")),
        "cash_flow": bool((cash or {}).get("annualReports")),
    }
    if not annual_history and not any(value for value in latest.values()) and not any(value is not None for value in (enrichment.get("normalized") or {}).values()):
        if warnings:
            return {
                "latest": latest,
                "annual_history": [],
                "enrichment": enrichment,
                "source": "Alpha Vantage configured but unavailable",
                "available": available,
                "warnings": warnings,
            }
        return None
    source_parts = []
    if any(available[key] for key in ["income_statement", "balance_sheet", "cash_flow"]):
        source_parts.append("Alpha Vantage standardized statements")
    if available["overview"]:
        source_parts.append("Alpha Vantage overview")
    return {
        "latest": latest,
        "annual_history": annual_history,
        "enrichment": enrichment,
        "source": " + ".join(source_parts) or "Alpha Vantage",
        "available": available,
        "warnings": warnings or None,
    }


def _finnhub_url(path: str, api_key: str, **params: Any) -> str:
    query = {"token": api_key, **params}
    encoded = urllib.parse.urlencode({key: value for key, value in query.items() if value is not None})
    return f"{FINNHUB_API_BASE}/{path}?{encoded}"


def _record_finnhub_warning(warnings: list[str] | None, label: str, detail: str) -> None:
    if warnings is not None:
        warnings.append(f"Finnhub {label} 不可用：{detail}")


def _finnhub_get(
    path: str,
    api_key: str | None,
    user_agent: str,
    warnings: list[str] | None = None,
    **params: Any,
) -> Any | None:
    if not api_key:
        return None
    try:
        data = _cached_provider_json(
            "finnhub",
            path,
            params,
            _finnhub_url(path, api_key, **params),
            user_agent,
        )
    except DataSourceError as exc:
        _record_finnhub_warning(warnings, path, str(exc))
        return None
    if isinstance(data, dict) and data.get("error"):
        _record_finnhub_warning(warnings, path, str(data.get("error")))
        return None
    return data if data not in (None, {}, []) else None


def _finnhub_num(row: dict[str, Any] | None, key: str) -> float | None:
    if not row:
        return None
    value = row.get(key)
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_to_decimal(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100 if abs(value) > 1 else value


def _finnhub_market_value(value: float | None) -> float | None:
    if value is None:
        return None
    return value * 1_000_000


def _build_finnhub_peer_tickers(peers: Any, ticker: str) -> list[str]:
    if not isinstance(peers, list):
        return []
    output = []
    for item in peers:
        peer = str(item or "").strip().upper()
        if peer and peer != ticker.upper():
            output.append(peer)
    return output[:12]


def _build_finnhub_enrichment(profile: Any, metric_payload: Any, peers: Any, ticker: str) -> dict[str, Any]:
    profile_row = profile if isinstance(profile, dict) else {}
    metric = (metric_payload or {}).get("metric") if isinstance(metric_payload, dict) else {}
    metric = metric if isinstance(metric, dict) else {}
    pfcf = _finnhub_num(metric, "pfcfShareTTM") or _finnhub_num(metric, "pfcfShareAnnual")
    return {
        "profile": profile_row,
        "metric": metric,
        "peer_tickers": _build_finnhub_peer_tickers(peers, ticker),
        "normalized": {
            "market_cap": _finnhub_market_value(_finnhub_num(profile_row, "marketCapitalization")),
            "enterprise_value": _finnhub_market_value(_finnhub_num(metric, "enterpriseValue")),
            "ev_to_sales": _finnhub_num(metric, "evRevenueTTM"),
            "ev_to_ebitda": _finnhub_num(metric, "evEbitdaTTM"),
            "pe_ttm": _finnhub_num(metric, "peTTM"),
            "forward_pe": _finnhub_num(metric, "forwardPE"),
            "peg": _finnhub_num(metric, "pegTTM") or _finnhub_num(metric, "forwardPEG"),
            "ps_ttm": _finnhub_num(metric, "psTTM"),
            "pb": _finnhub_num(metric, "pb"),
            "pfcf": pfcf,
            "fcf_yield": (1 / pfcf) if pfcf and pfcf > 0 else None,
            "gross_margin": _pct_to_decimal(_finnhub_num(metric, "grossMarginTTM")),
            "operating_margin": _pct_to_decimal(_finnhub_num(metric, "operatingMarginTTM")),
            "net_margin": _pct_to_decimal(_finnhub_num(metric, "netProfitMarginTTM")),
            "roe": _pct_to_decimal(_finnhub_num(metric, "roeTTM")),
            "roa": _pct_to_decimal(_finnhub_num(metric, "roaTTM")),
            "current_ratio": _finnhub_num(metric, "currentRatioQuarterly") or _finnhub_num(metric, "currentRatioAnnual"),
            "debt_to_equity": _finnhub_num(metric, "totalDebt/totalEquityQuarterly") or _finnhub_num(metric, "totalDebt/totalEquityAnnual"),
            "beta": _finnhub_num(metric, "beta"),
            "revenue_growth_ttm_yoy": _pct_to_decimal(_finnhub_num(metric, "revenueGrowthTTMYoy")),
            "eps_growth_ttm_yoy": _pct_to_decimal(_finnhub_num(metric, "epsGrowthTTMYoy")),
        },
    }


def fetch_finnhub_company_data(ticker: str, api_key: str | None, user_agent: str) -> dict[str, Any] | None:
    if not api_key:
        return None
    warnings: list[str] = []
    quote = _finnhub_get("quote", api_key, user_agent, warnings, symbol=ticker.upper())
    profile = _finnhub_get("stock/profile2", api_key, user_agent, warnings, symbol=ticker.upper())
    metric = _finnhub_get("stock/metric", api_key, user_agent, warnings, symbol=ticker.upper(), metric="all")
    peers = _finnhub_get("stock/peers", api_key, user_agent, warnings, symbol=ticker.upper())
    enrichment = _build_finnhub_enrichment(profile, metric, peers, ticker)
    latest = {
        "price": _finnhub_num(quote if isinstance(quote, dict) else {}, "c"),
    }
    available = {
        "quote": bool(quote),
        "profile": bool(profile),
        "metric": bool(metric),
        "peers": bool(enrichment.get("peer_tickers")),
    }
    normalized = enrichment.get("normalized") or {}
    if not any(latest.values()) and not enrichment.get("peer_tickers") and not any(value is not None for value in normalized.values()):
        if warnings:
            return {
                "latest": latest,
                "enrichment": enrichment,
                "source": "Finnhub configured but unavailable",
                "available": available,
                "warnings": warnings,
            }
        return None
    source_parts = []
    if available["quote"]:
        source_parts.append("Finnhub quote")
    if available["profile"]:
        source_parts.append("Finnhub profile")
    if available["metric"]:
        source_parts.append("Finnhub metrics")
    if available["peers"]:
        source_parts.append("Finnhub peers")
    return {
        "latest": latest,
        "enrichment": enrichment,
        "source": " + ".join(source_parts) or "Finnhub",
        "available": available,
        "warnings": warnings or None,
    }


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
    except (DataSourceError, urllib.error.URLError, KeyError, ValueError, TypeError):
        pass
    return fallback_yield, "本地默认值"


def _fmp_url(path: str, ticker: str, api_key: str, **params: Any) -> str:
    query = {"apikey": api_key, **params}
    encoded = urllib.parse.urlencode({key: value for key, value in query.items() if value is not None})
    return f"{FMP_API_BASE}/{path}/{urllib.parse.quote(ticker.upper())}?{encoded}"


def _fmp_stable_url(endpoint: str, api_key: str, **params: Any) -> str:
    query = {"apikey": api_key, **params}
    encoded = urllib.parse.urlencode({key: value for key, value in query.items() if value is not None})
    return f"{FMP_STABLE_API_BASE}/{endpoint}?{encoded}"


def _record_fmp_warning(warnings: list[str] | None, label: str, detail: str) -> None:
    if warnings is not None:
        warnings.append(f"FMP {label} 不可用：{detail}")


def _fmp_get(
    path: str,
    ticker: str,
    api_key: str,
    user_agent: str,
    warnings: list[str] | None = None,
    label: str | None = None,
    **params: Any,
) -> Any | None:
    if not api_key:
        return None
    try:
        data = _cached_provider_json(
            "fmp",
            f"v3/{path}",
            {"ticker": ticker.upper(), **params},
            _fmp_url(path, ticker, api_key, **params),
            user_agent,
        )
    except DataSourceError as exc:
        _record_fmp_warning(warnings, label or path, str(exc))
        return None
    if isinstance(data, dict) and any(key in data for key in ["Error Message", "Note", "Information"]):
        _record_fmp_warning(warnings, label or path, str(data))
        return None
    return data or None


def _fmp_stable_get(
    endpoint: str,
    api_key: str,
    user_agent: str,
    warnings: list[str] | None = None,
    label: str | None = None,
    **params: Any,
) -> Any | None:
    if not api_key:
        return None
    try:
        data = _cached_provider_json(
            "fmp",
            f"stable/{endpoint}",
            {"endpoint": endpoint, **params},
            _fmp_stable_url(endpoint, api_key, **params),
            user_agent,
        )
    except DataSourceError as exc:
        _record_fmp_warning(warnings, label or endpoint, str(exc))
        return None
    if isinstance(data, dict) and any(key in data for key in ["Error Message", "Note", "Information"]):
        _record_fmp_warning(warnings, label or endpoint, str(data))
        return None
    return data or None


def _fmp_year(row: dict[str, Any]) -> int | None:
    raw = row.get("calendarYear") or row.get("fiscalYear") or row.get("date") or row.get("fiscalDateEnding")
    if raw is None:
        return None
    try:
        return int(str(raw)[:4])
    except ValueError:
        return None


def _rows_by_year(rows: Any) -> dict[int, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    output: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        year = _fmp_year(row)
        if year is None:
            continue
        current_date = str(row.get("date") or row.get("fiscalDateEnding") or "")
        existing_date = str(output.get(year, {}).get("date") or output.get(year, {}).get("fiscalDateEnding") or "")
        if year not in output or current_date > existing_date:
            output[year] = row
    return output


def _num(row: dict[str, Any] | None, key: str) -> float | None:
    if not row:
        return None
    value = row.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_row(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    if isinstance(payload, dict):
        return payload
    return {}


def _first_annual_row(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        for row in payload:
            if isinstance(row, dict) and str(row.get("period") or "").upper() in {"FY", "ANNUAL"}:
                return row
    return _first_row(payload)


def _num_any(row: dict[str, Any] | None, keys: list[str]) -> float | None:
    for key in keys:
        value = _num(row, key)
        if value is not None:
            return value
    return None


def _build_fmp_annual_history(income_rows: Any, cash_rows: Any, balance_rows: Any) -> list[dict[str, Any]]:
    income_by_year = _rows_by_year(income_rows)
    cash_by_year = _rows_by_year(cash_rows)
    balance_by_year = _rows_by_year(balance_rows)
    years = sorted(set(income_by_year) | set(cash_by_year) | set(balance_by_year))[-6:]
    history: list[dict[str, Any]] = []
    for year in years:
        income = income_by_year.get(year)
        cash = cash_by_year.get(year)
        row = {
            "fiscal_year": year,
            "revenue": _num(income, "revenue"),
            "operating_income": _num(income, "operatingIncome"),
            "ocf": _num(cash, "operatingCashFlow"),
            "capex": abs(_num(cash, "capitalExpenditure") or 0) or None,
            "sbc": _num(cash, "stockBasedCompensation"),
            "source": "FMP standardized statements",
        }
        if any(row.get(key) is not None for key in ["revenue", "operating_income", "ocf", "capex", "sbc"]):
            history.append(row)
    return history


def _merge_annual_history(sec_history: list[dict[str, Any]], fmp_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for row in fmp_history:
        year = row.get("fiscal_year")
        if year:
            rows[int(year)] = dict(row)
    for row in sec_history:
        year = row.get("fiscal_year")
        if not year:
            continue
        merged = rows.get(int(year), {})
        merged.update({key: value for key, value in row.items() if value is not None})
        if rows.get(int(year), {}).get("source") and row:
            merged["source"] = "SEC companyfacts + FMP standardized statements"
        rows[int(year)] = merged
    return [rows[year] for year in sorted(rows)[-6:]]


def _build_fmp_consensus(estimates: Any) -> dict[str, Any] | None:
    if not isinstance(estimates, list):
        return None
    rows = [row for row in estimates if isinstance(row, dict)]
    rows.sort(key=lambda item: str(item.get("date") or ""))
    today = datetime.now(timezone.utc).date().isoformat()
    future = [row for row in rows if str(row.get("date") or "") >= today] or rows[:2]
    if not future:
        return None
    first = future[0]
    second = future[1] if len(future) > 1 else {}
    consensus = {
        "fiscal_year": _fmp_year(first),
        "revenue_next_year": _num_any(first, ["estimatedRevenueAvg", "revenueAvg"]),
        "revenue_2y": _num_any(second, ["estimatedRevenueAvg", "revenueAvg"]),
        "eps_next_year": _num_any(first, ["estimatedEpsAvg", "epsAvg"]),
        "eps_2y": _num_any(second, ["estimatedEpsAvg", "epsAvg"]),
        "ebitda_next_year": _num_any(first, ["estimatedEbitdaAvg", "ebitdaAvg"]),
        "operating_income_next_year": _num_any(first, ["estimatedEbitAvg", "ebitAvg"]),
        "net_income_next_year": _num_any(first, ["estimatedNetIncomeAvg", "netIncomeAvg"]),
        "analyst_count": _num_any(first, ["numberAnalystEstimatedRevenue", "numberAnalystsEstimatedRevenue", "numberAnalystEstimatedEps", "numAnalystsRevenue", "numAnalystsEps"]),
        "source": "FMP analyst estimates",
        "raw": future[:2],
    }
    if consensus["revenue_next_year"] is None and consensus["eps_next_year"] is None:
        return None
    return consensus


def _build_fmp_price_target(price_target: Any) -> dict[str, Any] | None:
    row = _first_row(price_target)
    low = _num_any(row, ["targetLow", "priceTargetLow", "low"])
    median = _num_any(row, ["targetMedian", "priceTargetMedian", "median"])
    consensus = _num_any(row, ["targetConsensus", "priceTargetConsensus", "targetAvg", "priceTargetAverage", "consensus"])
    high = _num_any(row, ["targetHigh", "priceTargetHigh", "high"])
    base = median or consensus
    if base is None:
        return None
    return {
        "target_low": low,
        "target_median": base,
        "target_consensus": consensus or base,
        "target_high": high,
        "source": "FMP price target consensus",
        "raw": row,
    }


def _build_fmp_peer_tickers(peers: Any) -> list[str]:
    row = _first_row(peers)
    raw = row.get("peersList") or row.get("peers") or peers
    if isinstance(raw, str):
        raw = [item.strip() for item in raw.split(",")]
    if not isinstance(raw, list):
        return []
    output = []
    for item in raw:
        ticker = item.get("symbol") if isinstance(item, dict) else item
        if str(ticker).strip():
            output.append(str(ticker).strip().upper())
    return output


def _build_fmp_enrichment(
    key_metrics_ttm: Any,
    ratios_ttm: Any,
    enterprise_values: Any,
    owner_earnings: Any,
    price_target: Any,
    peers: Any,
) -> dict[str, Any]:
    key_metrics = _first_row(key_metrics_ttm)
    ratios = _first_row(ratios_ttm)
    ev = _first_row(enterprise_values)
    owner = _first_annual_row(owner_earnings)
    return {
        "key_metrics_ttm": key_metrics,
        "ratios_ttm": ratios,
        "enterprise_values": ev,
        "owner_earnings": owner,
        "price_target": _build_fmp_price_target(price_target),
        "peer_tickers": _build_fmp_peer_tickers(peers),
        "normalized": {
            "roic": _num_any(key_metrics, ["roicTTM", "roic"]),
            "roe": _num_any(ratios, ["returnOnEquityTTM", "returnOnEquity"]),
            "gross_margin": _num_any(ratios, ["grossProfitMarginTTM", "grossProfitMargin"]),
            "operating_margin": _num_any(ratios, ["operatingProfitMarginTTM", "operatingProfitMargin"]),
            "net_margin": _num_any(ratios, ["netProfitMarginTTM", "netProfitMargin"]),
            "current_ratio": _num_any(ratios, ["currentRatioTTM", "currentRatio"]),
            "quick_ratio": _num_any(ratios, ["quickRatioTTM", "quickRatio"]),
            "interest_coverage": _num_any(ratios, ["interestCoverageTTM", "interestCoverage"]),
            "debt_to_equity": _num_any(ratios, ["debtEquityRatioTTM", "debtEquityRatio"]),
            "net_debt_to_ebitda": _num_any(key_metrics, ["netDebtToEBITDATTM", "netDebtToEBITDA"]),
            "ev_to_sales": _num_any(key_metrics, ["evToSalesTTM", "evToSales"]),
            "ev_to_ebitda": _num_any(key_metrics, ["enterpriseValueOverEBITDATTM", "evToEBITDATTM", "evToEBITDA"]),
            "fcf_yield": _num_any(key_metrics, ["freeCashFlowYieldTTM", "freeCashFlowYield"]),
            "earnings_yield": _num_any(key_metrics, ["earningsYieldTTM", "earningsYield"]),
            "market_cap": _num_any(ev, ["marketCapitalization", "marketCap"]),
            "enterprise_value": _num_any(ev, ["enterpriseValue"]),
            "ev_shares": _num_any(ev, ["numberOfShares"]),
            "owner_earnings": _num_any(owner, ["ownerEarnings", "ownersEarnings"]),
            "owner_earnings_per_share": _num_any(owner, ["ownersEarningsPerShare", "ownerEarningsPerShare"]),
            "maintenance_capex": abs(_num_any(owner, ["maintenanceCapex", "maintenanceCapitalExpenditure"]) or 0) or None,
            "growth_capex": abs(_num_any(owner, ["growthCapex", "growthCapitalExpenditure"]) or 0) or None,
        },
    }


def fetch_fmp_company_data(ticker: str, api_key: str | None, user_agent: str) -> dict[str, Any] | None:
    if not api_key:
        return None
    warnings: list[str] = []
    statement_warnings: list[str] = []
    income_rows = _fmp_stable_get(
        "income-statement",
        api_key,
        user_agent,
        warnings=statement_warnings,
        label="stable income-statement",
        symbol=ticker.upper(),
        period="annual",
        limit=6,
    )
    cash_rows = _fmp_stable_get(
        "cash-flow-statement",
        api_key,
        user_agent,
        warnings=statement_warnings,
        label="stable cash-flow-statement",
        symbol=ticker.upper(),
        period="annual",
        limit=6,
    )
    balance_rows = _fmp_stable_get(
        "balance-sheet-statement",
        api_key,
        user_agent,
        warnings=statement_warnings,
        label="stable balance-sheet-statement",
        symbol=ticker.upper(),
        period="annual",
        limit=6,
    )
    quote_rows = _fmp_stable_get("quote-short", api_key, user_agent, warnings=warnings, label="stable quote-short", symbol=ticker.upper())
    estimates = _fmp_stable_get(
        "analyst-estimates",
        api_key,
        user_agent,
        warnings=warnings,
        label="stable analyst-estimates",
        symbol=ticker.upper(),
        period="annual",
        page=0,
        limit=8,
    )
    if not income_rows:
        income_rows = _fmp_get(
            "income-statement",
            ticker,
            api_key,
            user_agent,
            warnings=statement_warnings,
            label="v3 income-statement",
            period="annual",
            limit=6,
        )
    if not cash_rows:
        cash_rows = _fmp_get(
            "cash-flow-statement",
            ticker,
            api_key,
            user_agent,
            warnings=statement_warnings,
            label="v3 cash-flow-statement",
            period="annual",
            limit=6,
        )
    if not balance_rows:
        balance_rows = _fmp_get(
            "balance-sheet-statement",
            ticker,
            api_key,
            user_agent,
            warnings=statement_warnings,
            label="v3 balance-sheet-statement",
            period="annual",
            limit=6,
        )
    if not quote_rows:
        quote_rows = _fmp_get("quote", ticker, api_key, user_agent, warnings=warnings, label="v3 quote")
    if not estimates:
        estimates = _fmp_get("analyst-estimates", ticker, api_key, user_agent, warnings=warnings, label="v3 analyst-estimates", limit=8)
    key_metrics_ttm = _fmp_stable_get("key-metrics-ttm", api_key, user_agent, warnings=warnings, label="stable key-metrics-ttm", symbol=ticker.upper())
    ratios_ttm = _fmp_stable_get("ratios-ttm", api_key, user_agent, warnings=warnings, label="stable ratios-ttm", symbol=ticker.upper())
    enterprise_values = _fmp_stable_get(
        "enterprise-values",
        api_key,
        user_agent,
        warnings=warnings,
        label="stable enterprise-values",
        symbol=ticker.upper(),
        limit=4,
    )
    owner_earnings = _fmp_stable_get("owner-earnings", api_key, user_agent, warnings=warnings, label="stable owner-earnings", symbol=ticker.upper())
    price_target = _fmp_stable_get(
        "price-target-consensus",
        api_key,
        user_agent,
        warnings=warnings,
        label="stable price-target-consensus",
        symbol=ticker.upper(),
    )
    peers = _fmp_stable_get("stock-peers", api_key, user_agent, warnings=warnings, label="stable stock-peers", symbol=ticker.upper())

    income_latest = income_rows[0] if isinstance(income_rows, list) and income_rows else {}
    cash_latest = cash_rows[0] if isinstance(cash_rows, list) and cash_rows else {}
    balance_latest = balance_rows[0] if isinstance(balance_rows, list) and balance_rows else {}
    quote = quote_rows[0] if isinstance(quote_rows, list) and quote_rows else {}
    latest = {
        "fiscal_year": _fmp_year(income_latest),
        "revenue": _num(income_latest, "revenue"),
        "operating_income": _num(income_latest, "operatingIncome"),
        "ocf": _num(cash_latest, "operatingCashFlow"),
        "capex": abs(_num(cash_latest, "capitalExpenditure") or 0) or None,
        "sbc": _num(cash_latest, "stockBasedCompensation"),
        "cash": _num(balance_latest, "cashAndCashEquivalents"),
        "short_investments": _num(balance_latest, "shortTermInvestments"),
        "debt_current": _num(balance_latest, "shortTermDebt"),
        "debt_long_term": _num(balance_latest, "longTermDebt"),
        "diluted_shares": _num(income_latest, "weightedAverageShsOutDil"),
        "price": _num(quote, "price"),
    }
    annual_history = _build_fmp_annual_history(income_rows, cash_rows, balance_rows)
    consensus = _build_fmp_consensus(estimates)
    enrichment = _build_fmp_enrichment(key_metrics_ttm, ratios_ttm, enterprise_values, owner_earnings, price_target, peers)
    available = {
        "income_statement": isinstance(income_rows, list) and bool(income_rows),
        "cash_flow_statement": isinstance(cash_rows, list) and bool(cash_rows),
        "balance_sheet_statement": isinstance(balance_rows, list) and bool(balance_rows),
        "quote": isinstance(quote_rows, list) and bool(quote_rows),
        "analyst_estimates": isinstance(estimates, list) and bool(estimates),
        "key_metrics_ttm": bool(_first_row(key_metrics_ttm)),
        "ratios_ttm": bool(_first_row(ratios_ttm)),
        "enterprise_values": bool(_first_row(enterprise_values)),
        "owner_earnings": bool(_first_row(owner_earnings)),
        "price_target_consensus": bool(enrichment.get("price_target")),
        "stock_peers": bool(enrichment.get("peer_tickers")),
    }
    if statement_warnings and not any(available[key] for key in ["income_statement", "cash_flow_statement", "balance_sheet_statement"]):
        warnings.extend(statement_warnings)
    normalized = enrichment.get("normalized") or {}
    has_enrichment = bool(enrichment.get("price_target") or enrichment.get("peer_tickers") or any(value is not None for value in normalized.values()))
    if not annual_history and not any(value for value in latest.values()) and not consensus and not has_enrichment:
        if warnings:
            return {
                "latest": latest,
                "annual_history": [],
                "consensus": None,
                "enrichment": enrichment,
                "source": "FMP configured but unavailable",
                "available": available,
                "warnings": warnings,
            }
        return None
    source_parts = []
    if annual_history:
        source_parts.append("FMP standardized statements")
    if available["analyst_estimates"]:
        source_parts.append("FMP analyst estimates")
    if any(available[key] for key in ["key_metrics_ttm", "ratios_ttm", "enterprise_values", "owner_earnings", "price_target_consensus", "stock_peers"]):
        source_parts.append("FMP metrics/price targets/peers")
    return {
        "latest": latest,
        "annual_history": annual_history,
        "consensus": consensus,
        "enrichment": enrichment,
        "source": " + ".join(source_parts) or "FMP",
        "available": available,
        "warnings": warnings or None,
    }


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            if self._table_depth == 0:
                self._current_table = []
            self._table_depth += 1
        elif self._table_depth and tag == "tr":
            self._current_row = []
        elif self._table_depth and tag in {"td", "th"}:
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            text = html.unescape(" ".join(self._current_cell))
            text = re.sub(r"\s+", " ", text).strip()
            self._current_row.append(text)
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None and self._current_table is not None:
            if any(cell for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None


def _parse_html_tables(markup: str) -> list[list[list[str]]]:
    parser = _HTMLTableParser()
    parser.feed(markup)
    return parser.tables


def _parse_percent(text: str) -> float | None:
    cleaned = text.replace("%", "").replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned) / 100
    except ValueError:
        return None


def _normalize_listed_ticker(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-")


def _payload_from_slickcharts(markup: str, limit: int | None = None) -> dict[str, Any]:
    for table in _parse_html_tables(markup):
        if not table:
            continue
        headers = [cell.lower() for cell in table[0]]
        if "company" not in headers or "symbol" not in headers or "weight" not in headers:
            continue
        company_idx = headers.index("company")
        symbol_idx = headers.index("symbol")
        weight_idx = headers.index("weight")
        rank_idx = headers.index("#") if "#" in headers else None
        holdings = []
        for fallback_rank, row in enumerate(table[1:], start=1):
            if len(row) <= max(company_idx, symbol_idx, weight_idx):
                continue
            ticker = _normalize_listed_ticker(row[symbol_idx])
            if not ticker:
                continue
            rank = fallback_rank
            if rank_idx is not None and len(row) > rank_idx:
                try:
                    rank = int(row[rank_idx].replace(",", ""))
                except ValueError:
                    rank = fallback_rank
            holdings.append({
                "rank": rank,
                "ticker": ticker,
                "name": row[company_idx],
                "weight": _parse_percent(row[weight_idx]) or 0,
                "security_type": "Common Stock",
                "sector": "",
                "industry": "",
                "raw": {"source_row": row},
            })
        holdings.sort(key=lambda row: row["rank"])
        if limit:
            holdings = holdings[:limit]
        if holdings:
            return {
                "pool_id": "sp500",
                "name": "S&P 500",
                "as_of": datetime.now(timezone.utc).date().isoformat(),
                "total_holdings": len(holdings),
                "source": "Slickcharts S&P 500 companies by weight",
                "holdings": holdings,
            }
    raise DataSourceResponseError("Slickcharts 页面没有解析到 S&P 500 成分股表格。")


def _payload_from_wikipedia_sp500(markup: str, limit: int | None = None) -> dict[str, Any]:
    for table in _parse_html_tables(markup):
        if not table:
            continue
        headers = [cell.lower() for cell in table[0]]
        if "symbol" not in headers or "security" not in headers:
            continue
        symbol_idx = headers.index("symbol")
        name_idx = headers.index("security")
        sector_idx = headers.index("gics sector") if "gics sector" in headers else None
        industry_idx = headers.index("gics sub-industry") if "gics sub-industry" in headers else None
        holdings = []
        for rank, row in enumerate(table[1:], start=1):
            if len(row) <= max(symbol_idx, name_idx):
                continue
            ticker = _normalize_listed_ticker(row[symbol_idx])
            if not ticker:
                continue
            holdings.append({
                "rank": rank,
                "ticker": ticker,
                "name": row[name_idx],
                "weight": 0,
                "security_type": "Common Stock",
                "sector": row[sector_idx] if sector_idx is not None and len(row) > sector_idx else "",
                "industry": row[industry_idx] if industry_idx is not None and len(row) > industry_idx else "",
                "raw": {"source_row": row},
            })
        if limit:
            holdings = holdings[:limit]
        if holdings:
            return {
                "pool_id": "sp500",
                "name": "S&P 500",
                "as_of": datetime.now(timezone.utc).date().isoformat(),
                "total_holdings": len(holdings),
                "source": "Wikipedia List of S&P 500 companies",
                "holdings": holdings,
            }
    raise DataSourceResponseError("Wikipedia 页面没有解析到 S&P 500 成分股表格。")


def fetch_sp500_holdings(user_agent: str, limit: int | None = None) -> dict[str, Any]:
    try:
        markup = get_text(SP500_SLICKCHARTS_URL, user_agent)
        return _payload_from_slickcharts(markup, limit)
    except DataSourceError:
        markup = get_text(SP500_WIKIPEDIA_URL, user_agent)
        return _payload_from_wikipedia_sp500(markup, limit)


def fetch_qqq_holdings(user_agent: str, limit: int | None = None) -> dict[str, Any]:
    data = get_json(QQQ_HOLDINGS_URL, user_agent)
    holdings = []
    for index, item in enumerate(data.get("holdings", []), start=1):
        ticker = str(item.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        security_type = str(item.get("securityTypeName") or "")
        raw_weight = float(item.get("percentageOfTotalNetAssets") or 0)
        holdings.append({
            "rank": index,
            "ticker": ticker.replace(".", "-"),
            "name": item.get("issuerName") or ticker,
            "weight": raw_weight / 100 if raw_weight > 1 else raw_weight,
            "security_type": security_type,
            "currency": item.get("currency") or "USD",
            "raw": item,
        })
    holdings.sort(key=lambda row: row["weight"], reverse=True)
    for index, item in enumerate(holdings, start=1):
        item["rank"] = index
    if limit:
        holdings = holdings[:limit]
    return {
        "etf": "QQQ",
        "as_of": data.get("effectiveBusinessDate") or data.get("effectiveDate"),
        "total_holdings": int(data.get("totalNumberOfHoldings") or len(holdings)),
        "source": "Invesco QQQ official holdings API",
        "holdings": holdings,
    }


def _coverage_status(ok: bool, partial: bool = False) -> str:
    if ok:
        return "ok"
    if partial:
        return "partial"
    return "missing"


def _coverage_item(label: str, status: str, source: str, detail: str) -> dict[str, str]:
    return {"label": label, "status": status, "source": source, "detail": detail}


def build_data_coverage(
    output: dict[str, Any],
    fmp_data: dict[str, Any] | None,
    alpha_data: dict[str, Any] | None,
    finnhub_data: dict[str, Any] | None,
) -> dict[str, Any]:
    history = output.get("annual_history") or []
    raw_recent = output.get("recent_period") or {}
    fmp_available = (fmp_data or {}).get("available", {})
    alpha_available = (alpha_data or {}).get("available", {})
    finnhub_available = (finnhub_data or {}).get("available", {})
    fmp_enrichment = (fmp_data or {}).get("enrichment") or {}
    alpha_enrichment = (alpha_data or {}).get("enrichment") or {}
    finnhub_enrichment = (finnhub_data or {}).get("enrichment") or {}

    financial_fields = ["revenue", "operating_income", "ocf", "capex", "diluted_shares"]
    present_financials = [key for key in financial_fields if output.get(key) not in (None, 0)]
    balance_fields = ["cash", "debt_current", "debt_long_term"]
    present_balance = [key for key in balance_fields if output.get(key) not in (None, 0)]
    normalized_sources = [
        name for name, payload in [
            ("FMP", (fmp_enrichment.get("normalized") or {})),
            ("Alpha Vantage", (alpha_enrichment.get("normalized") or {})),
            ("Finnhub", (finnhub_enrichment.get("normalized") or {})),
        ]
        if any(value is not None for value in payload.values())
    ]
    forward_source = "FMP analyst estimates" if (fmp_data or {}).get("consensus") else "system/manual required"
    peer_source = "FMP peers" if (fmp_enrichment.get("peer_tickers") or []) else "Finnhub peers" if (finnhub_enrichment.get("peer_tickers") or []) else "local/manual"
    items = {
        "financial_statements": _coverage_item(
            "历史财报字段",
            _coverage_status(len(present_financials) >= 5, len(present_financials) >= 3),
            "SEC companyfacts + Alpha/FMP fallback",
            f"{len(present_financials)}/{len(financial_fields)} 个核心字段可用，年度历史 {len(history)} 年。",
        ),
        "balance_sheet": _coverage_item(
            "资产负债表字段",
            _coverage_status(len(present_balance) >= 2, len(present_balance) >= 1),
            "SEC companyfacts + Alpha/FMP fallback",
            f"{len(present_balance)}/{len(balance_fields)} 个现金/债务字段可用。",
        ),
        "recent_period": _coverage_item(
            "最近季度/YTD",
            _coverage_status(bool(raw_recent.get("latest_quarter") or raw_recent.get("latest_ytd"))),
            "SEC companyfacts",
            "用于判断最近趋势和避免只看旧年报。" if raw_recent.get("latest_quarter") or raw_recent.get("latest_ytd") else "未抽到最近季度或 YTD 口径。",
        ),
        "market_price_rate": _coverage_item(
            "价格与无风险利率",
            _coverage_status(bool(output.get("price") and output.get("ten_year_yield"))),
            f"{output.get('price_source') or 'price missing'} + {output.get('ten_year_yield_source') or 'rate missing'}",
            "股价和 10 年期美债会影响所有目标价与贴现率。",
        ),
        "forward_expectations": _coverage_item(
            "前瞻共识",
            _coverage_status(bool((fmp_data or {}).get("consensus")), False),
            forward_source,
            "有外部收入/EPS/EBITDA 预期。" if (fmp_data or {}).get("consensus") else "缺外部共识时会使用历史、最近季度和行业先验估算。",
        ),
        "peer_multiples": _coverage_item(
            "同行和当前倍数",
            _coverage_status(bool((fmp_enrichment.get("peer_tickers") or []) or (finnhub_enrichment.get("peer_tickers") or [])), bool((fmp_enrichment.get("normalized") or {}) or (finnhub_enrichment.get("normalized") or {}))),
            peer_source,
            f"FMP peers={len(fmp_enrichment.get('peer_tickers') or [])}，Finnhub peers={len(finnhub_enrichment.get('peer_tickers') or [])}。",
        ),
        "quality_metrics": _coverage_item(
            "质量指标",
            _coverage_status(bool(normalized_sources), False),
            " + ".join(normalized_sources) or "system calculated",
            "ROE/ROIC、流动性、EV 倍数、利润率等增强指标。" if normalized_sources else "仅使用财报字段计算质量分。",
        ),
    }
    weights = {
        "financial_statements": 24,
        "balance_sheet": 10,
        "recent_period": 10,
        "market_price_rate": 14,
        "forward_expectations": 18,
        "peer_multiples": 14,
        "quality_metrics": 10,
    }
    score = 0.0
    for key, item in items.items():
        multiplier = 1.0 if item["status"] == "ok" else 0.55 if item["status"] == "partial" else 0.0
        score += weights[key] * multiplier
    warnings = [
        item["detail"]
        for item in items.values()
        if item["status"] != "ok"
    ]
    return {
        "score": round(score, 1),
        "level": "high" if score >= 78 else "medium" if score >= 58 else "low",
        "items": items,
        "warnings": warnings,
        "provider_available": {
            "fmp": fmp_available,
            "alpha_vantage": alpha_available,
            "finnhub": finnhub_available,
        },
    }


def fetch_company_facts(
    ticker: str,
    user_agent: str,
    fallback_yield: float,
    alpha_vantage_api_key: str | None = None,
    fred_api_key: str | None = None,
    fmp_api_key: str | None = None,
    finnhub_api_key: str | None = None,
) -> dict[str, Any]:
    cik, name = find_cik(ticker, user_agent)
    facts = get_json(SEC_FACTS_URL.format(cik=cik), user_agent)
    submissions = get_json(SEC_SUBMISSIONS_URL.format(cik=cik), user_agent)
    sec_meta = {
        "sic": submissions.get("sic"),
        "sic_description": submissions.get("sicDescription"),
        "fiscal_year_end": submissions.get("fiscalYearEnd"),
        "exchanges": submissions.get("exchanges", []),
    }
    is_financial = is_financial_sec_meta(sec_meta)
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
    if is_financial:
        fields["revenue"] = (
            [
                "RevenuesNetOfInterestExpense",
                "InterestIncomeExpenseNet",
                "InterestIncomeOperating",
                "RevenueNotFromContractWithCustomerExcludingInterestIncome",
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
            ],
            ["USD"],
        )
        fields["operating_income"] = (
            [
                "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
                "NetIncomeLossAvailableToCommonStockholdersDiluted",
                "NetIncomeLoss",
            ],
            ["USD"],
        )
        fields["ocf"] = (
            [
                "NetIncomeLossAvailableToCommonStockholdersDiluted",
                "NetIncomeLossAvailableToCommonStockholdersBasic",
                "NetIncomeLoss",
            ],
            ["USD"],
        )
        fields["short_investments"] = (
            [
                "AvailableForSaleSecuritiesDebtSecurities",
                "MarketableSecuritiesCurrent",
                "ShortTermInvestments",
            ],
            ["USD"],
        )
    output: dict[str, Any] = {
        "ticker": ticker.upper(),
        "name": submissions.get("name") or name,
        "cik": cik,
        "sec_meta": sec_meta,
    }
    fiscal_years: list[int] = []
    for key, (tags, units) in fields.items():
        value, fy = latest_annual_value(facts, tags, units)
        output[key] = abs(value) if key == "capex" and value is not None else value
        if fy:
            fiscal_years.append(fy)
    output["annual_history"] = build_annual_history(facts, fields)
    output["recent_period"] = build_recent_period_snapshot(facts, fields)
    output["fiscal_year"] = max(fiscal_years) if fiscal_years else None
    fmp_data = fetch_fmp_company_data(ticker, fmp_api_key, user_agent)
    fmp_filled_fields: list[str] = []
    if fmp_data:
        latest = fmp_data.get("latest") or {}
        for key in [
            "fiscal_year",
            "revenue",
            "operating_income",
            "ocf",
            "capex",
            "sbc",
            "cash",
            "short_investments",
            "debt_current",
            "debt_long_term",
            "diluted_shares",
        ]:
            if output.get(key) in (None, 0) and latest.get(key) not in (None, 0):
                output[key] = latest[key]
                fmp_filled_fields.append(key)
        output["annual_history"] = _merge_annual_history(output["annual_history"], fmp_data.get("annual_history") or [])
    alpha_data = fetch_alpha_vantage_company_data(ticker, alpha_vantage_api_key, user_agent)
    alpha_filled_fields: list[str] = []
    if alpha_data:
        latest = alpha_data.get("latest") or {}
        for key in [
            "fiscal_year",
            "revenue",
            "operating_income",
            "ocf",
            "capex",
            "sbc",
            "cash",
            "short_investments",
            "debt_current",
            "debt_long_term",
            "diluted_shares",
        ]:
            if output.get(key) in (None, 0) and latest.get(key) not in (None, 0):
                output[key] = latest[key]
                alpha_filled_fields.append(key)
        output["annual_history"] = _merge_annual_history(output["annual_history"], alpha_data.get("annual_history") or [])
    finnhub_data = fetch_finnhub_company_data(ticker, finnhub_api_key, user_agent)
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
    if fmp_data and output["price"] is None and (fmp_data.get("latest") or {}).get("price"):
        output["price"] = (fmp_data.get("latest") or {}).get("price")
        output["price_source"] = "FMP quote"
    if finnhub_data and output["price"] is None and (finnhub_data.get("latest") or {}).get("price"):
        output["price"] = (finnhub_data.get("latest") or {}).get("price")
        output["price_source"] = "Finnhub quote"
    output["ten_year_yield"], output["ten_year_yield_source"] = fetch_ten_year_yield(fred_api_key, fallback_yield, user_agent)
    source_parts = ["SEC companyfacts", "免费行情/利率源"]
    if fmp_data:
        source_parts.append(fmp_data.get("source") or "FMP")
    if alpha_data:
        source_parts.append(alpha_data.get("source") or "Alpha Vantage")
    if finnhub_data:
        source_parts.append(finnhub_data.get("source") or "Finnhub")
    output["source"] = f"{' + '.join(source_parts)}，刷新于 {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    data_coverage = build_data_coverage(output, fmp_data, alpha_data, finnhub_data)
    output["raw_json"] = {
        "cik": cik,
        "sec_name": output["name"],
        "sec_meta": output["sec_meta"],
        "reporting_currency": reporting_currency or "USD",
        "recent_period": output.get("recent_period", {}),
        "normalization": {
            "statement_type": "financial_services" if is_financial else "operating_company",
            "notes": [
                "金融/放贷类公司使用净利息后收入和净利润近似可分配盈利，不使用经营现金流作为 FCF。"
            ] if is_financial else [],
        },
        "fmp": {
            "enabled": bool(fmp_api_key),
            "available": (fmp_data or {}).get("available", {}),
            "filled_fields": fmp_filled_fields,
            "consensus": (fmp_data or {}).get("consensus"),
            "enrichment": (fmp_data or {}).get("enrichment"),
            "source": (fmp_data or {}).get("source"),
            "warnings": (fmp_data or {}).get("warnings"),
        },
        "alpha_vantage": {
            "enabled": bool(alpha_vantage_api_key),
            "available": (alpha_data or {}).get("available", {}),
            "filled_fields": alpha_filled_fields,
            "enrichment": (alpha_data or {}).get("enrichment"),
            "source": (alpha_data or {}).get("source"),
            "warnings": (alpha_data or {}).get("warnings"),
        },
        "finnhub": {
            "enabled": bool(finnhub_api_key),
            "available": (finnhub_data or {}).get("available", {}),
            "enrichment": (finnhub_data or {}).get("enrichment"),
            "source": (finnhub_data or {}).get("source"),
            "warnings": (finnhub_data or {}).get("warnings"),
        },
        "data_coverage": data_coverage,
        "api_usage": external_api_usage_summary(),
    }
    return output
