from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "value_invest.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    return json.loads(value)


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS companies (
                ticker TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                industry TEXT DEFAULT '',
                sector TEXT DEFAULT '',
                description TEXT DEFAULT '',
                business_overview TEXT DEFAULT '',
                company_type TEXT DEFAULT '稳定复利公司',
                segments_json TEXT DEFAULT '[]',
                peers_json TEXT DEFAULT '[]',
                profile_source TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS financial_facts (
                ticker TEXT PRIMARY KEY,
                fiscal_year INTEGER,
                revenue REAL,
                operating_income REAL,
                ocf REAL,
                capex REAL,
                sbc REAL,
                cash REAL,
                short_investments REAL,
                debt_current REAL,
                debt_long_term REAL,
                diluted_shares REAL,
                price REAL,
                price_override REAL,
                price_source TEXT DEFAULT '',
                market_cap REAL,
                ten_year_yield REAL,
                ten_year_yield_source TEXT DEFAULT '',
                source TEXT,
                updated_at TEXT NOT NULL,
                annual_history_json TEXT DEFAULT '[]',
                raw_json TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS valuation_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                title TEXT NOT NULL,
                inputs_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                ticker TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS consensus_estimates (
                ticker TEXT PRIMARY KEY,
                fiscal_year INTEGER,
                revenue_next_year REAL,
                revenue_2y REAL,
                eps_next_year REAL,
                eps_2y REAL,
                ebitda_next_year REAL,
                operating_income_next_year REAL,
                fcf_next_year REAL,
                long_term_eps_growth REAL,
                source TEXT,
                updated_at TEXT,
                raw_json TEXT
            );

            CREATE TABLE IF NOT EXISTS valuation_multiples_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                date TEXT,
                price REAL,
                market_cap REAL,
                enterprise_value REAL,
                pe_ttm REAL,
                pe_forward REAL,
                ev_sales REAL,
                ev_ebitda REAL,
                fcf_yield REAL,
                ps_ratio REAL,
                source TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS peer_valuation_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                peer_ticker TEXT,
                date TEXT,
                peer_price REAL,
                peer_market_cap REAL,
                peer_ev_sales REAL,
                peer_ev_ebitda REAL,
                peer_forward_pe REAL,
                peer_fcf_yield REAL,
                revenue_growth REAL,
                operating_margin REAL,
                fcf_margin REAL,
                rule_of_40 REAL,
                source TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS valuation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                run_type TEXT,
                price_at_run REAL,
                target_bear REAL,
                target_base REAL,
                target_bull REAL,
                upside_base REAL,
                confidence_score REAL,
                inputs_json TEXT,
                outputs_json TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS etf_holdings (
                etf TEXT NOT NULL,
                ticker TEXT NOT NULL,
                name TEXT DEFAULT '',
                rank INTEGER,
                weight REAL,
                security_type TEXT DEFAULT '',
                as_of TEXT DEFAULT '',
                source TEXT DEFAULT '',
                raw_json TEXT DEFAULT '{}',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (etf, ticker)
            );
            """
        )
        migrate_db(conn)
        seed_defaults(conn)


def migrate_db(conn: sqlite3.Connection) -> None:
    company_columns = {row["name"] for row in conn.execute("PRAGMA table_info(companies)").fetchall()}
    company_additions = {
        "industry": "TEXT DEFAULT ''",
        "description": "TEXT DEFAULT ''",
        "business_overview": "TEXT DEFAULT ''",
        "segments_json": "TEXT DEFAULT '[]'",
        "profile_source": "TEXT DEFAULT ''",
    }
    for name, definition in company_additions.items():
        if name not in company_columns:
            conn.execute(f"ALTER TABLE companies ADD COLUMN {name} {definition}")
    facts_columns = {row["name"] for row in conn.execute("PRAGMA table_info(financial_facts)").fetchall()}
    facts_additions = {
        "price_override": "REAL",
        "price_source": "TEXT DEFAULT ''",
        "ten_year_yield_source": "TEXT DEFAULT ''",
        "annual_history_json": "TEXT DEFAULT '[]'",
    }
    for name, definition in facts_additions.items():
        if name not in facts_columns:
            conn.execute(f"ALTER TABLE financial_facts ADD COLUMN {name} {definition}")


def seed_defaults(conn: sqlite3.Connection) -> None:
    ts = now_iso()
    defaults = {
        "sec_user_agent": "personal-value-study contact@example.com",
        "default_discount_rate": 0.09,
        "default_terminal_growth": 0.025,
        "default_ten_year_yield": 0.045,
        "default_risk_discount": 0.03,
        "alpha_vantage_api_key": "",
        "fred_api_key": "",
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, dumps(value)),
        )

    conn.execute(
        """
        INSERT OR IGNORE INTO companies
        (ticker, name, industry, sector, description, business_overview, company_type,
         segments_json, peers_json, profile_source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "GOOG",
            "Alphabet Inc.",
            "互联网内容与信息 / 数字广告 / 云计算",
            "平台 / 广告 / 云 / AI",
            "Alphabet 是 Google 的母公司，核心资产包括搜索、YouTube、Android、Chrome、Google Cloud 以及 AI 基础设施。",
            "公司主要通过搜索和 YouTube 广告赚钱，同时经营订阅、硬件、应用商店、云计算和其他长期创新业务。对估值最重要的是广告现金流稳定性、Google Cloud 利润率，以及 AI 数据中心投入能否转化为未来现金流。",
            "稳定复利公司",
            dumps([
                {"name": "Google Services", "share": 0.87, "description": "搜索、YouTube、Android、Chrome、Google Play、硬件和订阅，贡献绝大部分收入和利润。"},
                {"name": "Google Cloud", "share": 0.12, "description": "云基础设施、数据分析、Workspace 和 AI 云服务，是主要成长业务。"},
                {"name": "Other Bets", "share": 0.01, "description": "Waymo 等长期项目，收入占比较小但带有期权属性。"},
            ]),
            dumps(["MSFT", "META", "AMZN", "AAPL"]),
            "内置业务画像 + 年报分部口径近似",
            ts,
            ts,
        ),
    )
    conn.execute(
        """
        UPDATE companies
        SET industry = COALESCE(NULLIF(industry, ''), ?),
            sector = COALESCE(NULLIF(sector, ''), ?),
            description = COALESCE(NULLIF(description, ''), ?),
            business_overview = COALESCE(NULLIF(business_overview, ''), ?),
            segments_json = CASE WHEN segments_json = '[]' OR segments_json = '' THEN ? ELSE segments_json END,
            profile_source = COALESCE(NULLIF(profile_source, ''), ?)
        WHERE ticker = 'GOOG'
        """,
        (
            "互联网内容与信息 / 数字广告 / 云计算",
            "平台 / 广告 / 云 / AI",
            "Alphabet 是 Google 的母公司，核心资产包括搜索、YouTube、Android、Chrome、Google Cloud 以及 AI 基础设施。",
            "公司主要通过搜索和 YouTube 广告赚钱，同时经营订阅、硬件、应用商店、云计算和其他长期创新业务。对估值最重要的是广告现金流稳定性、Google Cloud 利润率，以及 AI 数据中心投入能否转化为未来现金流。",
            dumps([
                {"name": "Google Services", "share": 0.87, "description": "搜索、YouTube、Android、Chrome、Google Play、硬件和订阅，贡献绝大部分收入和利润。"},
                {"name": "Google Cloud", "share": 0.12, "description": "云基础设施、数据分析、Workspace 和 AI 云服务，是主要成长业务。"},
                {"name": "Other Bets", "share": 0.01, "description": "Waymo 等长期项目，收入占比较小但带有期权属性。"},
            ]),
            "内置业务画像 + 年报分部口径近似",
        ),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO financial_facts
        (ticker, fiscal_year, revenue, operating_income, ocf, capex, sbc, cash,
         short_investments, debt_current, debt_long_term, diluted_shares, price,
         price_override, price_source, market_cap, ten_year_yield, ten_year_yield_source, source, updated_at, annual_history_json, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "GOOG",
            2025,
            402.836e9,
            129.039e9,
            164.713e9,
            91.447e9,
            24.953e9,
            30.708e9,
            96.135e9,
            1.996e9,
            46.547e9,
            12.23e9,
            342.32,
            None,
            "内置示例价格",
            342.32 * 12.23e9,
            0.045,
            "默认设置",
            "内置 GOOG 示例数据，可用刷新按钮替换为实时数据",
            ts,
            dumps([
                {"fiscal_year": 2021, "revenue": 257.637e9, "operating_income": 78.714e9, "ocf": 91.495e9, "capex": 24.640e9, "sbc": 15.376e9},
                {"fiscal_year": 2022, "revenue": 282.836e9, "operating_income": 74.842e9, "ocf": 91.652e9, "capex": 31.485e9, "sbc": 19.525e9},
                {"fiscal_year": 2023, "revenue": 307.394e9, "operating_income": 84.293e9, "ocf": 101.746e9, "capex": 32.251e9, "sbc": 22.460e9},
                {"fiscal_year": 2024, "revenue": 350.018e9, "operating_income": 112.390e9, "ocf": 125.304e9, "capex": 52.535e9, "sbc": 22.721e9},
                {"fiscal_year": 2025, "revenue": 402.836e9, "operating_income": 129.039e9, "ocf": 164.713e9, "capex": 91.447e9, "sbc": 24.953e9},
            ]),
            dumps({"seed": True}),
        ),
    )
    conn.execute(
        """
        UPDATE financial_facts
        SET annual_history_json = CASE
            WHEN annual_history_json IS NULL OR annual_history_json = '[]' OR annual_history_json = '' THEN ?
            ELSE annual_history_json
        END
        WHERE ticker = 'GOOG'
        """,
        (
            dumps([
                {"fiscal_year": 2021, "revenue": 257.637e9, "operating_income": 78.714e9, "ocf": 91.495e9, "capex": 24.640e9, "sbc": 15.376e9},
                {"fiscal_year": 2022, "revenue": 282.836e9, "operating_income": 74.842e9, "ocf": 91.652e9, "capex": 31.485e9, "sbc": 19.525e9},
                {"fiscal_year": 2023, "revenue": 307.394e9, "operating_income": 84.293e9, "ocf": 101.746e9, "capex": 32.251e9, "sbc": 22.460e9},
                {"fiscal_year": 2024, "revenue": 350.018e9, "operating_income": 112.390e9, "ocf": 125.304e9, "capex": 52.535e9, "sbc": 22.721e9},
                {"fiscal_year": 2025, "revenue": 402.836e9, "operating_income": 129.039e9, "ocf": 164.713e9, "capex": 91.447e9, "sbc": 24.953e9},
            ]),
        ),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO notes (ticker, content, updated_at)
        VALUES (?, ?, ?)
        """,
        (
            "GOOG",
            "## 我为什么看这家公司？\n\n- 搜索、YouTube、Android、Cloud 和 AI 基础设施形成强平台。\n\n"
            "## 当前价格在赌什么？\n\n- 市场相信 AI / 数据中心 CAPEX 未来能转化为更高 OCF。\n\n"
            "## 我最可能错在哪里？\n\n- 把防守性 CAPEX 当成高回报成长投资。",
            ts,
        ),
    )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)
