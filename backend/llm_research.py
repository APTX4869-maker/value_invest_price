from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .db import connect, dumps, loads, now_iso, row_to_dict


class LLMConfigError(RuntimeError):
    """Raised when the local LLM provider is not configured."""


class LLMProviderError(RuntimeError):
    """Raised when the LLM provider returns an unusable response."""


@dataclass
class ResearchLLMConfig:
    enabled: bool
    provider_type: str
    base_url: str
    api_key: str
    model: str
    max_tokens: int = 4000
    temperature: float = 0.2


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled", "开启"}


def config_from_settings(settings: dict[str, Any]) -> ResearchLLMConfig:
    return ResearchLLMConfig(
        enabled=truthy(settings.get("llm_enabled", False)),
        provider_type=str(settings.get("llm_provider_type") or "openai_compatible"),
        base_url=str(settings.get("llm_base_url") or "https://api.openai.com/v1").rstrip("/"),
        api_key=str(settings.get("llm_api_key") or ""),
        model=str(settings.get("llm_model") or ""),
        max_tokens=int(settings.get("llm_max_tokens") or 4000),
        temperature=float(settings.get("llm_temperature") if settings.get("llm_temperature") is not None else 0.2),
    )


def validate_config(config: ResearchLLMConfig) -> None:
    if not config.enabled:
        raise LLMConfigError("LLM 研究助手尚未开启。请在设置里把 llm_enabled 设为 true，并配置 API key 与模型。")
    if config.provider_type != "openai_compatible":
        raise LLMConfigError("当前只支持 openai_compatible provider。")
    if not config.api_key:
        raise LLMConfigError("LLM API key 为空。请在设置里填写 llm_api_key。")
    if not config.model:
        raise LLMConfigError("LLM model 为空。请在设置里填写 llm_model。")


def evidence_from_packages(packages: list[dict[str, Any]], max_chars: int = 16000) -> tuple[str, list[str]]:
    blocks = []
    accessions = []
    used = 0
    for package in packages:
        filing = package.get("filing", {})
        accession = filing.get("accession_no")
        if accession:
            accessions.append(accession)
        for section in package.get("sections", []):
            if section.get("status") != "found":
                continue
            text = section.get("text") or section.get("excerpt") or ""
            if not text:
                continue
            block = (
                f"[{filing.get('form')} {filing.get('filing_date') or filing.get('report_date')} "
                f"{section.get('title')}]\n"
                f"source_url: {section.get('source_url') or filing.get('document_url')}\n"
                f"{text[:3500]}"
            )
            if used + len(block) > max_chars:
                break
            blocks.append(block)
            used += len(block)
    return "\n\n---\n\n".join(blocks), accessions


def build_research_messages(ticker: str, packages: list[dict[str, Any]]) -> list[dict[str, str]]:
    evidence, _ = evidence_from_packages(packages)
    if not evidence:
        raise LLMProviderError("没有可用于生成初稿的 SEC 证据。请先刷新 SEC 研究包。")
    schema = {
        "business_model": "公司如何赚钱，用中文，必须引用 evidence",
        "segments": ["业务线或收入来源"],
        "growth_drivers": ["增长驱动"],
        "moat_sources": ["护城河来源及证据"],
        "competition": ["竞争格局与主要对手"],
        "key_risks": ["关键风险"],
        "financial_quality_notes": ["财务质量观察"],
        "follow_up_questions": ["需要人工继续验证的问题"],
        "citations": [{"claim": "结论", "source": "form/date/item/source_url"}],
    }
    return [
        {
            "role": "system",
            "content": (
                "你是一个谨慎的美股基本面研究助理。只基于用户给出的 SEC 证据写结构化中文初稿。"
                "不要给买卖建议。没有证据的判断必须写成“待确认”。只输出 JSON，不要 Markdown。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"请为 {ticker.upper()} 生成公司研究初稿，严格遵守这个 JSON schema：\n"
                f"{json.dumps(schema, ensure_ascii=False)}\n\n"
                f"SEC evidence:\n{evidence}"
            ),
        },
    ]


class OpenAICompatibleProvider:
    def __init__(self, config: ResearchLLMConfig):
        self.config = config

    def generate_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        url = f"{self.config.base_url}/chat/completions"
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            raise LLMProviderError(f"LLM provider 返回 HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMProviderError(f"LLM provider 请求失败：{exc}") from exc

        content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not content:
            raise LLMProviderError("LLM provider 没有返回 message.content。")
        return normalize_research_draft(parse_json_content(content))


def parse_json_content(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise LLMProviderError("模型返回内容不是 JSON。")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMProviderError("模型返回 JSON 无法解析。") from exc


def normalize_research_draft(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "business_model": str(value.get("business_model") or "待确认"),
        "segments": _list_of_strings(value.get("segments")),
        "growth_drivers": _list_of_strings(value.get("growth_drivers")),
        "moat_sources": _list_of_strings(value.get("moat_sources")),
        "competition": _list_of_strings(value.get("competition")),
        "key_risks": _list_of_strings(value.get("key_risks")),
        "financial_quality_notes": _list_of_strings(value.get("financial_quality_notes")),
        "follow_up_questions": _list_of_strings(value.get("follow_up_questions")),
        "citations": value.get("citations") if isinstance(value.get("citations"), list) else [],
    }


def _list_of_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []


def generate_company_research_draft(
    ticker: str,
    packages: list[dict[str, Any]],
    settings: dict[str, Any],
) -> dict[str, Any]:
    config = config_from_settings(settings)
    validate_config(config)
    messages = build_research_messages(ticker, packages)
    draft = OpenAICompatibleProvider(config).generate_json(messages)
    _, accessions = evidence_from_packages(packages)
    return save_research_draft(
        ticker=ticker,
        draft=draft,
        provider=config.provider_type,
        model=config.model,
        accessions=accessions,
    )


def save_research_draft(
    ticker: str,
    draft: dict[str, Any],
    provider: str,
    model: str,
    accessions: list[str],
    draft_type: str = "sec_company_research",
) -> dict[str, Any]:
    ts = now_iso()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO research_drafts
            (ticker, draft_type, status, provider, model, source_accessions_json,
             draft_json, error, created_at, updated_at)
            VALUES (?, ?, 'pending_confirmation', ?, ?, ?, ?, '', ?, ?)
            """,
            (ticker.upper(), draft_type, provider, model, dumps(accessions), dumps(draft), ts, ts),
        )
        draft_id = cursor.lastrowid
    return get_research_draft(draft_id)


def get_research_draft(draft_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM research_drafts WHERE id = ?", (draft_id,)).fetchone()
    item = row_to_dict(row)
    if not item:
        raise LLMProviderError("研究初稿不存在。")
    return serialize_research_draft(item)


def list_research_drafts(ticker: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM research_drafts
            WHERE ticker = ?
            ORDER BY created_at DESC
            """,
            (ticker.upper(),),
        ).fetchall()
    return [serialize_research_draft(row_to_dict(row)) for row in rows]


def serialize_research_draft(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "ticker": row["ticker"],
        "draft_type": row["draft_type"],
        "status": row["status"],
        "provider": row.get("provider", ""),
        "model": row.get("model", ""),
        "source_accessions": loads(row.get("source_accessions_json"), []),
        "draft": loads(row.get("draft_json"), {}),
        "error": row.get("error", ""),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
