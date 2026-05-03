import { useEffect, useState } from "react";
import { Bot, KeyRound, Save, Search, Settings } from "lucide-react";
import { Badge } from "../components/Badge";
import { formatMoney } from "../utils/formatters";
import { parseSetting } from "../utils/settings";

const LLM_SETTING_KEYS = new Set([
  "llm_enabled",
  "llm_provider_type",
  "llm_base_url",
  "llm_api_key",
  "llm_model",
  "llm_max_tokens",
  "llm_temperature",
]);

export function HistorySettings({ ticker, snapshots, settings, saveSettings }) {
  const [draft, setDraft] = useState({});
  const [compareLeftId, setCompareLeftId] = useState(null);
  const [compareRightId, setCompareRightId] = useState(null);
  const [snapshotQuery, setSnapshotQuery] = useState("");
  useEffect(() => setDraft(settings || {}), [settings]);
  useEffect(() => {
    setCompareLeftId(snapshots[0]?.id || null);
    setCompareRightId(snapshots[1]?.id || null);
  }, [ticker, snapshots]);

  const compareLeft = snapshots.find((item) => item.id === compareLeftId) || null;
  const compareRight = snapshots.find((item) => item.id === compareRightId) || null;
  const normalizedSnapshotQuery = snapshotQuery.trim().toLowerCase();
  const filteredSnapshots = normalizedSnapshotQuery
    ? snapshots.filter((snap) => snapshotSearchText(snap).includes(normalizedSnapshotQuery))
    : snapshots;
  const marketSettings = Object.entries(draft).filter(([key]) => !LLM_SETTING_KEYS.has(key));
  const llmEnabled = Boolean(draft.llm_enabled);
  const llmReady = llmEnabled && draft.llm_api_key && draft.llm_model;

  function updateSetting(key, value) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  return (
    <section className="page-section">
      <div className="reading-header">
        <div>
          <p className="eyebrow">历史与配置</p>
          <h2>把每次判断留下来，未来才知道自己哪里错了</h2>
          <p>快照保存的是当时的数据、假设和结论，不会被下一次刷新覆盖。</p>
        </div>
      </div>
      <div className="two-column wide-left">
        <div className="panel">
          <h3>{ticker} 历史快照</h3>
          <div className="search-strip compact-search">
            <Search size={17} />
            <input
              value={snapshotQuery}
              onChange={(event) => setSnapshotQuery(event.target.value)}
              placeholder="搜索快照：判断、结论、日期或价格"
            />
            <span>{normalizedSnapshotQuery ? `${filteredSnapshots.length}/${snapshots.length} 条` : `${snapshots.length} 条快照`}</span>
          </div>
          <div className="snapshot-list">
            {filteredSnapshots.length ? filteredSnapshots.map((snap) => (
              <div className="snapshot" key={snap.id}>
                <div>
                  <strong><HighlightedText text={snap.title} query={normalizedSnapshotQuery} /></strong>
                  <span>{new Date(snap.created_at).toLocaleString()}</span>
                </div>
                <Badge>{snap.result?.judgement || "已保存"}</Badge>
                <small>中枢 {formatMoney(snap.result?.fair_value_center, false)} / 当前价 {formatMoney(snap.result?.current_price, false)}</small>
                <p>{snap.result?.plain_language?.headline || "暂无结论摘要"}</p>
                <div className="snapshot-actions">
                  <button className={compareLeftId === snap.id ? "ghost active-soft" : "ghost"} onClick={() => setCompareLeftId(snap.id)}>对比 A</button>
                  <button className={compareRightId === snap.id ? "ghost active-soft" : "ghost"} onClick={() => setCompareRightId(snap.id)}>对比 B</button>
                </div>
              </div>
            )) : <p className="muted">{snapshots.length ? "没有匹配的快照，可以换个关键词。" : "还没有快照。去估值模型页保存一次。"}</p>}
          </div>
          {compareLeft && compareRight ? (
            <div className="snapshot-compare">
              <div className="panel compare-card">
                <div className="compare-head">
                  <strong>对比 A</strong>
                  <span>{new Date(compareLeft.created_at).toLocaleString()}</span>
                </div>
                <Badge>{compareLeft.result?.judgement || "已保存"}</Badge>
                <div className="mini-stats">
                  <div className="stat">
                    <span>合理中枢</span>
                    <strong>{formatMoney(compareLeft.result?.fair_value_center, false)}</strong>
                  </div>
                  <div className="stat">
                    <span>当前价</span>
                    <strong>{formatMoney(compareLeft.result?.current_price, false)}</strong>
                  </div>
                </div>
                <p className="plain-callout">{compareLeft.result?.plain_language?.headline || "暂无结论摘要"}</p>
              </div>
              <div className="panel compare-card">
                <div className="compare-head">
                  <strong>对比 B</strong>
                  <span>{new Date(compareRight.created_at).toLocaleString()}</span>
                </div>
                <Badge>{compareRight.result?.judgement || "已保存"}</Badge>
                <div className="mini-stats">
                  <div className="stat">
                    <span>合理中枢</span>
                    <strong>{formatMoney(compareRight.result?.fair_value_center, false)}</strong>
                  </div>
                  <div className="stat">
                    <span>当前价</span>
                    <strong>{formatMoney(compareRight.result?.current_price, false)}</strong>
                  </div>
                </div>
                <p className="plain-callout">{compareRight.result?.plain_language?.headline || "暂无结论摘要"}</p>
              </div>
              <div className="panel compare-delta">
                <h3>快照差异</h3>
                <div className="metric-list">
                  <CompareRow label="合理中枢变化" left={compareLeft.result?.fair_value_center} right={compareRight.result?.fair_value_center} money />
                  <CompareRow label="当前价格变化" left={compareLeft.result?.current_price} right={compareRight.result?.current_price} money />
                  <CompareRow label="折现率" left={compareLeft.inputs?.discount_rate} right={compareRight.inputs?.discount_rate} percent />
                  <CompareRow label="基准增长率" left={compareLeft.inputs?.base_growth} right={compareRight.inputs?.base_growth} percent />
                  <CompareRow label="风险折扣" left={compareLeft.inputs?.risk_discount} right={compareRight.inputs?.risk_discount} percent />
                </div>
              </div>
            </div>
          ) : null}
        </div>
        <div className="settings-stack">
          <div className="panel ai-settings-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">AI research</p>
                <h3><Bot size={18} /> AI 研究助手</h3>
                <p>SEC 摘录会发送到你配置的 LLM 服务；AI 输出必须人工确认才写入备忘录。</p>
              </div>
              <Badge tone={llmReady ? "good" : "warn"}>{llmReady ? "已配置" : "待配置"}</Badge>
            </div>
            <label className="toggle-row">
              <span>
                <strong>启用 AI 研究初稿</strong>
                <small>关闭后仍可查看 SEC 证据和手写研究笔记。</small>
              </span>
              <input
                type="checkbox"
                checked={llmEnabled}
                onChange={(event) => updateSetting("llm_enabled", event.target.checked)}
              />
            </label>
            <div className="setting-grid">
              <label className="setting-row">
                <span>Provider</span>
                <select
                  value={draft.llm_provider_type || "openai_compatible"}
                  onChange={(event) => updateSetting("llm_provider_type", event.target.value)}
                >
                  <option value="openai_compatible">OpenAI compatible</option>
                </select>
              </label>
              <label className="setting-row">
                <span>Base URL</span>
                <input
                  value={draft.llm_base_url || ""}
                  onChange={(event) => updateSetting("llm_base_url", event.target.value)}
                  placeholder="https://api.openai.com/v1"
                />
              </label>
              <label className="setting-row full">
                <span><KeyRound size={15} /> API key</span>
                <input
                  type="password"
                  value={draft.llm_api_key || ""}
                  onChange={(event) => updateSetting("llm_api_key", event.target.value)}
                  placeholder="保存在本地 SQLite"
                />
              </label>
              <label className="setting-row">
                <span>Model</span>
                <input
                  value={draft.llm_model || ""}
                  onChange={(event) => updateSetting("llm_model", event.target.value)}
                  placeholder="例如 gpt-4.1 或本地兼容模型"
                />
              </label>
              <label className="setting-row">
                <span>Max tokens</span>
                <input
                  type="number"
                  min="1000"
                  step="500"
                  value={draft.llm_max_tokens ?? 4000}
                  onChange={(event) => updateSetting("llm_max_tokens", Number(event.target.value))}
                />
              </label>
              <label className="setting-row">
                <span>Temperature</span>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  value={draft.llm_temperature ?? 0.2}
                  onChange={(event) => updateSetting("llm_temperature", Number(event.target.value))}
                />
              </label>
            </div>
            <button onClick={() => saveSettings(draft)}><Save size={16} />保存 AI 设置</button>
          </div>

          <div className="panel">
            <h3><Settings size={18} /> 市场数据源设置</h3>
            <p className="plain-callout">
              `alpha_vantage_api_key` 用于 Yahoo 行情失败时兜底抓股价；`fred_api_key` 用于自动更新 10 年期美债。没填也能用，只是会退回本地默认值。
            </p>
            {marketSettings.map(([key, value]) => (
              <label className="setting-row" key={key}>
                <span>{key}</span>
                <input value={String(value)} onChange={(event) => setDraft({ ...draft, [key]: parseSetting(event.target.value) })} />
              </label>
            ))}
            <button onClick={() => saveSettings(draft)}><Save size={16} />保存设置</button>
          </div>
        </div>
      </div>
    </section>
  );
}

function snapshotSearchText(snap) {
  return [
    snap.title,
    snap.created_at,
    snap.result?.judgement,
    typeof snap.result?.confidence === "string" ? snap.result?.confidence : snap.result?.confidence?.level,
    snap.result?.plain_language?.headline,
    snap.result?.plain_language?.v3_conclusion,
    snap.result?.fair_value_center,
    snap.result?.current_price,
  ].filter(Boolean).join(" ").toLowerCase();
}

function HighlightedText({ text, query }) {
  if (!query || !text) return text || "";
  const source = String(text);
  const lower = source.toLowerCase();
  const parts = [];
  let start = 0;
  let index = lower.indexOf(query);
  while (index !== -1) {
    if (index > start) parts.push(source.slice(start, index));
    parts.push(<mark key={`${index}-${parts.length}`}>{source.slice(index, index + query.length)}</mark>);
    start = index + query.length;
    index = lower.indexOf(query, start);
  }
  if (start < source.length) parts.push(source.slice(start));
  return parts.length ? parts : source;
}

function CompareRow({ label, left, right, money = false, percent = false }) {
  const formatter = money
    ? (value) => formatMoney(value, false)
    : percent
      ? (value) => (value === null || value === undefined ? "-" : `${(Number(value) * 100).toFixed(1)}%`)
      : (value) => value ?? "-";
  const delta = left !== null && left !== undefined && right !== null && right !== undefined
    ? right - left
    : null;
  const deltaText = delta === null
    ? "-"
    : money
      ? formatMoney(delta, false)
      : percent
        ? `${(delta * 100).toFixed(1)}%`
        : String(delta);

  return (
    <div className="compare-row">
      <strong>{label}</strong>
      <span>{formatter(left)} {"->"} {formatter(right)}</span>
      <b>{deltaText}</b>
    </div>
  );
}
