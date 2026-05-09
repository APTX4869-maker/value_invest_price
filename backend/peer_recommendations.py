from __future__ import annotations

from typing import Any


CORE_PEER_LIMIT = 8
PEER_CANDIDATE_LIMIT = 16


CURATED_PEERS: dict[str, list[dict[str, Any]]] = {
    "KO": [
        {"ticker": "PEP", "name": "PepsiCo, Inc.", "reason": "同为全球饮料龙头，并且有直接可比的碳酸饮料与非碳酸饮料业务。", "confidence": "高"},
        {"ticker": "KDP", "name": "Keurig Dr Pepper Inc.", "reason": "北美饮料和咖啡平台，和可口可乐在饮料货架、渠道和品牌组合上可比。", "confidence": "中高"},
        {"ticker": "MNST", "name": "Monster Beverage Corp.", "reason": "能量饮料公司，适合作为高增长饮料细分对照。", "confidence": "中"},
        {"ticker": "CELH", "name": "Celsius Holdings, Inc.", "reason": "成长型功能饮料公司，可用于观察饮料行业成长溢价。", "confidence": "中"},
    ],
    "PEP": [
        {"ticker": "KO", "name": "The Coca-Cola Company", "reason": "全球饮料龙头，是百事最核心的可比公司。", "confidence": "高"},
        {"ticker": "KDP", "name": "Keurig Dr Pepper Inc.", "reason": "饮料和咖啡组合与渠道有可比性。", "confidence": "中高"},
        {"ticker": "MDLZ", "name": "Mondelez International, Inc.", "reason": "包装食品和零食业务可与百事的 Frito-Lay 形成部分可比。", "confidence": "中"},
    ],
    "GOOG": [
        {"ticker": "META", "name": "Meta Platforms, Inc.", "reason": "同为数字广告平台，广告收入和 AI 推荐效率是核心可比项。", "confidence": "高"},
        {"ticker": "MSFT", "name": "Microsoft Corp.", "reason": "云计算和 AI 基础设施是重要可比项。", "confidence": "中高"},
        {"ticker": "AMZN", "name": "Amazon.com, Inc.", "reason": "云业务和广告业务均有可比性，但零售业务会影响整体倍数。", "confidence": "中"},
        {"ticker": "AAPL", "name": "Apple Inc.", "reason": "生态入口和平台能力可作为质量参照，但商业模式差异较大。", "confidence": "中"},
    ],
    "META": [
        {"ticker": "GOOG", "name": "Alphabet Inc.", "reason": "同为数字广告平台，最直接可比。", "confidence": "高"},
        {"ticker": "SNAP", "name": "Snap Inc.", "reason": "社交广告平台，可用于观察广告周期和用户参与度。", "confidence": "中"},
        {"ticker": "PINS", "name": "Pinterest, Inc.", "reason": "社交/兴趣图谱广告平台，适合做广告变现效率对照。", "confidence": "中"},
        {"ticker": "TTD", "name": "The Trade Desk, Inc.", "reason": "程序化广告平台，可用于观察广告技术估值溢价。", "confidence": "中"},
    ],
    "NVDA": [
        {"ticker": "AMD", "name": "Advanced Micro Devices, Inc.", "reason": "GPU/CPU 和 AI 加速芯片直接竞争。", "confidence": "高"},
        {"ticker": "AVGO", "name": "Broadcom Inc.", "reason": "AI 网络、定制芯片和半导体平台可比。", "confidence": "中高"},
        {"ticker": "MRVL", "name": "Marvell Technology, Inc.", "reason": "数据中心半导体和网络芯片可比。", "confidence": "中"},
        {"ticker": "TSM", "name": "Taiwan Semiconductor Manufacturing Company", "reason": "AI 芯片制造供应链关键公司，但商业模式是代工而非设计。", "confidence": "中"},
    ],
    "MU": [
        {"ticker": "WDC", "name": "Western Digital Corp.", "reason": "存储与 NAND 周期直接相关，可对照存储价格和资本开支周期。", "confidence": "高"},
        {"ticker": "STX", "name": "Seagate Technology Holdings plc", "reason": "数据存储硬件公司，可作为存储需求和周期弹性的参照。", "confidence": "中高"},
        {"ticker": "AMD", "name": "Advanced Micro Devices, Inc.", "reason": "AI 服务器需求链条相关，可用来对照 AI 半导体景气度，但不是直接存储同行。", "confidence": "中"},
        {"ticker": "AVGO", "name": "Broadcom Inc.", "reason": "数据中心半导体平台，可作为 AI 基础设施半导体估值参照。", "confidence": "中"},
        {"ticker": "QCOM", "name": "QUALCOMM Inc.", "reason": "成熟半导体公司，可对照利润率、现金流和市场倍数。", "confidence": "中"},
    ],
    "PLTR": [
        {"ticker": "SNOW", "name": "Snowflake Inc.", "reason": "数据平台公司，可比较数据基础设施和企业客户增长。", "confidence": "中高"},
        {"ticker": "DDOG", "name": "Datadog, Inc.", "reason": "企业软件平台，高增长和高估值属性可比。", "confidence": "中"},
        {"ticker": "MDB", "name": "MongoDB, Inc.", "reason": "开发者/数据平台，可作为软件估值和增长质量参照。", "confidence": "中"},
        {"ticker": "CRM", "name": "Salesforce, Inc.", "reason": "成熟企业软件平台，可作为利润率和现金流质量参照。", "confidence": "中"},
    ],
    "MSFT": [
        {"ticker": "GOOG", "name": "Alphabet Inc.", "reason": "云计算、AI 基础设施和平台生态可比。", "confidence": "中高"},
        {"ticker": "AMZN", "name": "Amazon.com, Inc.", "reason": "AWS 与 Azure 是云计算核心可比。", "confidence": "中高"},
        {"ticker": "ORCL", "name": "Oracle Corp.", "reason": "企业软件、数据库和云基础设施可比。", "confidence": "中"},
        {"ticker": "CRM", "name": "Salesforce, Inc.", "reason": "企业软件订阅和客户关系管理可比。", "confidence": "中"},
    ],
    "PYPL": [
        {"ticker": "SQ", "name": "Block, Inc.", "reason": "数字支付和商户服务可比。", "confidence": "高"},
        {"ticker": "V", "name": "Visa Inc.", "reason": "支付网络龙头，可作为高质量支付资产参照。", "confidence": "中高"},
        {"ticker": "MA", "name": "Mastercard Inc.", "reason": "支付网络龙头，可比较支付行业利润率和估值上限。", "confidence": "中高"},
        {"ticker": "ADYEN", "name": "Adyen N.V.", "reason": "全球支付处理平台，可比较商户支付增长。", "confidence": "中"},
    ],
    "TSLA": [
        {"ticker": "GM", "name": "General Motors Company", "reason": "汽车制造业务可比，但成长性和软件属性差异较大。", "confidence": "中"},
        {"ticker": "F", "name": "Ford Motor Company", "reason": "传统车企参照，可比较汽车周期和制造利润率。", "confidence": "中"},
        {"ticker": "RIVN", "name": "Rivian Automotive, Inc.", "reason": "电动车成长公司，可比较电动车需求和产能扩张。", "confidence": "中"},
        {"ticker": "LI", "name": "Li Auto Inc.", "reason": "电动车公司，可作为中国市场和新能源车盈利能力参照。", "confidence": "中"},
    ],
}

DIRECT_REQUIRED_PEERS: dict[str, set[str]] = {
    "MU": {"WDC", "STX"},
}


def curated_peer_tickers(ticker: str, limit: int = 8) -> list[str]:
    return [item["ticker"] for item in CURATED_PEERS.get(ticker.upper(), [])[:limit]]


def sanitize_peer_tickers(ticker: str, peers: list[str] | None, limit: int = CORE_PEER_LIMIT) -> list[str]:
    base_ticker = ticker.upper()
    normalized: list[str] = []
    seen = {base_ticker}
    for peer in peers or []:
        peer_ticker = str(peer or "").strip().upper()
        if not peer_ticker or peer_ticker in seen:
            continue
        normalized.append(peer_ticker)
        seen.add(peer_ticker)
        if len(normalized) >= limit:
            break
    return normalized


def should_replace_with_curated_peers(ticker: str, existing_peers: list[str]) -> bool:
    ticker = ticker.upper()
    curated = curated_peer_tickers(ticker)
    if not curated:
        return False
    if not existing_peers:
        return True
    required = DIRECT_REQUIRED_PEERS.get(ticker)
    existing = {peer.upper() for peer in existing_peers}
    return bool(required and len(existing) >= 4 and not existing.intersection(required))


def default_core_peer_tickers(ticker: str, existing_peers: list[str] | None) -> list[str]:
    sanitized = sanitize_peer_tickers(ticker, existing_peers)
    if should_replace_with_curated_peers(ticker, sanitized):
        return sanitize_peer_tickers(ticker, curated_peer_tickers(ticker))
    return sanitized


def external_peer_tickers_from_raw(
    raw_json: dict[str, Any] | None,
    ticker: str,
    limit: int = PEER_CANDIDATE_LIMIT,
) -> list[str]:
    raw_json = raw_json or {}
    candidates: list[str] = []
    for provider in ("fmp", "finnhub"):
        enrichment = ((raw_json.get(provider) or {}).get("enrichment") or {})
        candidates.extend(enrichment.get("peer_tickers") or [])
    return sanitize_peer_tickers(ticker, candidates, limit=limit)


def external_peer_recommendations(
    raw_json: dict[str, Any] | None,
    ticker: str,
    existing_tickers: set[str] | None = None,
    limit: int = PEER_CANDIDATE_LIMIT,
) -> list[dict[str, Any]]:
    existing_tickers = existing_tickers or set()
    recommendations: list[dict[str, Any]] = []
    for peer in external_peer_tickers_from_raw(raw_json, ticker, limit=limit):
        if peer in existing_tickers:
            continue
        recommendations.append(
            {
                "ticker": peer,
                "name": peer,
                "reason": "外部数据源返回的同行候选，需要人工确认；未加入核心同行前不会参与估值倍数。",
                "confidence": "待确认",
                "source": "外部数据源候选",
            }
        )
    return recommendations[:limit]


SECTOR_PEERS: list[tuple[tuple[str, ...], list[dict[str, Any]]]] = [
    (
        ("饮料", "BEVERAGE", "SOFT DRINK", "BOTTL"),
        [
            {"ticker": "KO", "name": "The Coca-Cola Company", "reason": "饮料行业核心龙头。", "confidence": "中高"},
            {"ticker": "PEP", "name": "PepsiCo, Inc.", "reason": "饮料和食品行业核心龙头。", "confidence": "中高"},
            {"ticker": "KDP", "name": "Keurig Dr Pepper Inc.", "reason": "北美饮料与咖啡平台。", "confidence": "中"},
            {"ticker": "MNST", "name": "Monster Beverage Corp.", "reason": "能量饮料细分龙头。", "confidence": "中"},
        ],
    ),
    (
        ("广告", "社交", "互联网内容", "PLATFORM", "INTERNET"),
        [
            {"ticker": "GOOG", "name": "Alphabet Inc.", "reason": "数字广告和平台生态参照。", "confidence": "中高"},
            {"ticker": "META", "name": "Meta Platforms, Inc.", "reason": "社交广告平台参照。", "confidence": "中高"},
            {"ticker": "AMZN", "name": "Amazon.com, Inc.", "reason": "广告和云业务均可作为参照。", "confidence": "中"},
            {"ticker": "TTD", "name": "The Trade Desk, Inc.", "reason": "广告技术平台参照。", "confidence": "中"},
        ],
    ),
    (
        ("半导体", "SEMICONDUCTOR", "GPU", "芯片"),
        [
            {"ticker": "NVDA", "name": "NVIDIA Corp.", "reason": "AI 半导体龙头。", "confidence": "中高"},
            {"ticker": "AMD", "name": "Advanced Micro Devices, Inc.", "reason": "CPU/GPU 设计公司。", "confidence": "中高"},
            {"ticker": "AVGO", "name": "Broadcom Inc.", "reason": "半导体和基础设施软件平台。", "confidence": "中"},
            {"ticker": "MRVL", "name": "Marvell Technology, Inc.", "reason": "数据中心芯片参照。", "confidence": "中"},
        ],
    ),
    (
        ("软件", "SAAS", "CLOUD", "云", "APPLICATION"),
        [
            {"ticker": "MSFT", "name": "Microsoft Corp.", "reason": "成熟软件和云平台参照。", "confidence": "中高"},
            {"ticker": "CRM", "name": "Salesforce, Inc.", "reason": "企业软件订阅参照。", "confidence": "中"},
            {"ticker": "NOW", "name": "ServiceNow, Inc.", "reason": "企业工作流 SaaS 参照。", "confidence": "中"},
            {"ticker": "ADBE", "name": "Adobe Inc.", "reason": "高利润软件平台参照。", "confidence": "中"},
        ],
    ),
    (
        ("支付", "PAYMENT", "金融科技"),
        [
            {"ticker": "PYPL", "name": "PayPal Holdings, Inc.", "reason": "数字钱包和支付平台参照。", "confidence": "中高"},
            {"ticker": "SQ", "name": "Block, Inc.", "reason": "商户支付和金融科技参照。", "confidence": "中"},
            {"ticker": "V", "name": "Visa Inc.", "reason": "支付网络龙头参照。", "confidence": "中"},
            {"ticker": "MA", "name": "Mastercard Inc.", "reason": "支付网络龙头参照。", "confidence": "中"},
        ],
    ),
]


def recommend_peers(company: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    ticker = company.get("ticker", "").upper()
    direct = CURATED_PEERS.get(ticker, [])
    text = " ".join(
        [
            company.get("industry") or "",
            company.get("sector") or "",
            company.get("description") or "",
            company.get("business_overview") or "",
        ]
    ).upper()
    recommendations: list[dict[str, Any]] = []
    seen = {ticker}

    for item in direct:
        if item["ticker"] not in seen:
            recommendations.append({**item, "source": "精选映射"})
            seen.add(item["ticker"])

    for keywords, peers in SECTOR_PEERS:
        if any(keyword.upper() in text for keyword in keywords):
            for item in peers:
                if item["ticker"] not in seen:
                    recommendations.append({**item, "source": "行业关键词匹配"})
                    seen.add(item["ticker"])

    return recommendations[:limit]
