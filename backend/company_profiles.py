from __future__ import annotations

from typing import Any


PROFILE_OVERRIDES: dict[str, dict[str, Any]] = {
    "GOOG": {
        "industry": "互联网内容与信息 / 数字广告 / 云计算",
        "sector": "平台 / 广告 / 云 / AI",
        "description": "Alphabet 是 Google 的母公司，核心资产包括搜索、YouTube、Android、Chrome、Google Cloud 以及 AI 基础设施。",
        "business_overview": "公司主要通过搜索和 YouTube 广告赚钱，同时经营订阅、硬件、应用商店、云计算和其他长期创新业务。对估值最重要的是广告现金流稳定性、Google Cloud 利润率，以及 AI 数据中心投入能否转化为未来现金流。",
        "segments": [
            {"name": "Google Services", "share": 0.87, "description": "搜索、YouTube、Android、Chrome、Google Play、硬件和订阅，贡献绝大部分收入和利润。"},
            {"name": "Google Cloud", "share": 0.12, "description": "云基础设施、数据分析、Workspace 和 AI 云服务，是主要成长业务。"},
            {"name": "Other Bets", "share": 0.01, "description": "Waymo 等长期项目，收入占比较小但带有期权属性。"},
        ],
        "profile_source": "内置业务画像 + 年报分部口径近似",
    },
    "PLTR": {
        "industry": "应用软件 / 数据分析平台",
        "sector": "软件 / AI / 政府与企业数据平台",
        "description": "Palantir 提供数据整合、分析和 AI 平台，客户包括政府机构和商业企业。",
        "business_overview": "公司通过 Gotham、Foundry、Apollo 和 AIP 等平台帮助客户把分散数据转成可操作决策。分析时应重点看商业客户增长、政府业务稳定性、SBC 稀释，以及高估值是否需要非常高的未来增长来兑现。",
        "segments": [
            {"name": "Commercial", "share": 0.55, "description": "企业客户，包括数据平台、AI 工作流和运营决策系统。"},
            {"name": "Government", "share": 0.45, "description": "政府和国防客户，合同周期较长，稳定性较强但受预算和采购节奏影响。"},
        ],
        "profile_source": "内置业务画像 + 近似业务结构",
    },
    "NVDA": {
        "industry": "半导体 / GPU / AI 基础设施",
        "sector": "半导体 / AI 算力 / 数据中心",
        "description": "NVIDIA 设计 GPU、加速计算平台、网络产品和 AI 软件生态，是全球 AI 训练与推理基础设施的核心供应商之一。",
        "business_overview": "公司主要通过数据中心 GPU、网络、系统和软件生态赚钱，也有游戏、专业可视化、汽车等业务。估值关键在于 AI 数据中心需求是否持续、毛利率能否保持、客户资本开支周期是否反转。",
        "segments": [
            {"name": "Data Center", "share": 0.85, "description": "AI GPU、网络和加速计算平台，是收入和利润增长核心。"},
            {"name": "Gaming", "share": 0.09, "description": "游戏 GPU 和相关平台，仍是重要现金流业务。"},
            {"name": "Professional Visualization", "share": 0.02, "description": "工作站图形、设计和仿真场景。"},
            {"name": "Automotive and Other", "share": 0.04, "description": "自动驾驶平台、机器人和其他新兴业务。"},
        ],
        "profile_source": "内置业务画像 + 近似业务结构",
    },
    "MSFT": {
        "industry": "软件 / 云计算 / 企业服务",
        "sector": "软件 / 云 / AI",
        "description": "Microsoft 提供企业软件、云计算、生产力工具、Windows、游戏和 AI 服务。",
        "business_overview": "估值重点是 Azure 增长、Office 和 Dynamics 的订阅稳定性、AI Copilot 变现，以及资本开支能否带来更高云收入。",
        "segments": [
            {"name": "Productivity and Business Processes", "share": 0.33, "description": "Office、LinkedIn、Dynamics 等。"},
            {"name": "Intelligent Cloud", "share": 0.42, "description": "Azure、服务器产品和企业云服务。"},
            {"name": "More Personal Computing", "share": 0.25, "description": "Windows、设备、游戏和搜索广告。"},
        ],
        "profile_source": "内置业务画像 + 近似业务结构",
    },
    "META": {
        "industry": "社交平台 / 数字广告 / AI",
        "sector": "平台 / 广告 / AI",
        "description": "Meta 经营 Facebook、Instagram、WhatsApp、Messenger 和 Reality Labs。",
        "business_overview": "公司主要靠广告赚钱。估值重点是广告加载率、用户参与度、AI 推荐效率、Reality Labs 亏损和资本开支回报。",
        "segments": [
            {"name": "Family of Apps", "share": 0.98, "description": "Facebook、Instagram、WhatsApp 和 Messenger 的广告及相关收入。"},
            {"name": "Reality Labs", "share": 0.02, "description": "VR/AR、元宇宙和长期硬件平台探索。"},
        ],
        "profile_source": "内置业务画像 + 近似业务结构",
    },
}


def build_company_profile(ticker: str, name: str, sec_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    ticker = ticker.upper()
    sec_meta = sec_meta or {}
    override = PROFILE_OVERRIDES.get(ticker, {})
    industry = override.get("industry") or sec_meta.get("sic_description") or "暂未识别行业"
    sector = override.get("sector") or sec_meta.get("sic_description") or ""
    description = override.get("description") or f"{name} 是一家在美国上市的公司。当前系统已识别其基础财报，但还没有足够信息自动生成详细业务介绍。"
    business_overview = override.get("business_overview") or "业务介绍和营收结构暂未自动解析。可以先阅读最新 10-K 的 Business 和 Segment reporting 部分，后续版本会加入年报文本解析或手动编辑入口。"
    segments = override.get("segments") or []
    return {
        "industry": industry,
        "sector": sector,
        "description": description,
        "business_overview": business_overview,
        "segments": segments,
        "profile_source": override.get("profile_source") or ("SEC SIC 行业信息" if sec_meta else "基础 ticker 信息"),
    }

