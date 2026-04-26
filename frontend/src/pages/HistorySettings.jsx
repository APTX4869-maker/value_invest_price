import { useEffect, useState } from "react";
import { Save, Search, Settings } from "lucide-react";
import { Badge } from "../components/Badge";
import { formatMoney } from "../utils/formatters";
import { parseSetting } from "../utils/settings";

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
        <div className="panel">
          <h3><Settings size={18} /> 数据源设置</h3>
          <p className="plain-callout">
            `alpha_vantage_api_key` 用于 Yahoo 行情失败时兜底抓股价；`fred_api_key` 用于自动更新 10 年期美债。没填也能用，只是会退回本地默认值。
          </p>
          {Object.entries(draft).map(([key, value]) => (
            <label className="setting-row" key={key}>
              <span>{key}</span>
              <input value={String(value)} onChange={(event) => setDraft({ ...draft, [key]: parseSetting(event.target.value) })} />
            </label>
          ))}
          <button onClick={() => saveSettings(draft)}><Save size={16} />保存设置</button>
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
