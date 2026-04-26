import { AlertTriangle, LayoutGrid, List, RefreshCcw, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "../components/Badge";
import { Stat } from "../components/Stat";
import { TickerSuggestInput } from "../components/TickerSuggestInput";
import { formatMoney } from "../utils/formatters";

function confidenceValue(confidence) {
  if (!confidence) return "-";
  return typeof confidence === "string" ? confidence : `${confidence.score}/100 · ${confidence.level}`;
}

export function Watchlist({ watchlist, setTicker, setPage, addTicker, refreshCompany, deleteTicker, purgeTicker, loading, tickerErrors }) {
  const [newTicker, setNewTicker] = useState("");
  const [viewMode, setViewMode] = useState("cards");
  const isList = viewMode === "list";

  function openCompany(item) {
    setTicker(item.ticker);
    setPage("company");
  }

  async function openWithRefresh(item, valuation) {
    setTicker(item.ticker);
    if (!valuation) {
      await refreshCompany(item.ticker, true);
    }
    setPage("company");
  }

  return (
    <section className="page-section">
      <div className="hero-panel">
        <div>
          <p className="eyebrow">第一眼只回答一个问题</p>
          <h2>这家公司现在是便宜、合理，还是偏贵？</h2>
          <p>观察池用自然语言标签展示估值状态。你可以点进公司，再逐层看数据、假设和公式。</p>
        </div>
        <form
          className="add-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (newTicker.trim()) addTicker(newTicker.trim()).then((ok) => ok && setNewTicker(""));
          }}
        >
          <TickerSuggestInput
            value={newTicker}
            onDraftChange={setNewTicker}
            onSelect={(item) => addTicker(item.ticker, item.name).then((ok) => ok && setNewTicker(""))}
            placeholder="输入公司名或 ticker，例如 nv"
          />
          <button disabled={loading}><Search size={16} />添加</button>
        </form>
      </div>
      <div className="view-toolbar">
        <div>
          <strong>观察池格式</strong>
          <span>卡片适合阅读，列表适合快速扫描。</span>
        </div>
        <div className="segmented">
          <button className={viewMode === "cards" ? "active" : ""} onClick={() => setViewMode("cards")}><LayoutGrid size={16} />卡片</button>
          <button className={viewMode === "list" ? "active" : ""} onClick={() => setViewMode("list")}><List size={16} />列表</button>
        </div>
      </div>
      <div className="delete-guide">
        <strong>删除说明</strong>
        <span>删除观察池：移除公司和财务缓存，但保留笔记与快照。彻底删除：连研究笔记和历史快照也一起清除。</span>
      </div>
      <div className={isList ? "watchlist-list" : "watchlist-grid"}>
        {watchlist.map((item) => {
          const valuation = item.valuation;
          return (
            <article key={item.ticker} className={isList ? "company-card list-row" : "company-card"}>
              <div className="card-head">
                <div>
                  <h3>{item.ticker}</h3>
                  <p>{item.name}</p>
                </div>
                <Badge tone={valuation?.judgement === "偏贵" || valuation?.judgement === "明显高估" ? "warn" : "good"}>
                  {valuation?.judgement || "待分析"}
                </Badge>
              </div>
              <div className="mini-stats">
                <Stat label="当前价" value={formatMoney(valuation?.current_price, false)} />
                <Stat label="合理中枢" value={formatMoney(valuation?.fair_value_center, false)} />
                <Stat label="品质分" value={valuation ? `${valuation.quality_score}/100` : "-"} />
              </div>
              {valuation ? (
                <p className="plain-callout">
                  合理区间约 {formatMoney(valuation.fair_value_range.low, false)} - {formatMoney(valuation.fair_value_range.high, false)}，可信度 {confidenceValue(valuation.confidence)}。
                </p>
              ) : (
                <p className="plain-callout">还没有足够数据。先刷新，或者进入估值模型手动补假设。</p>
              )}
              {tickerErrors[item.ticker] ? <p className="error-callout">{tickerErrors[item.ticker]}</p> : null}
              <div className="card-actions">
                <button onClick={() => openWithRefresh(item, valuation)}>查看分析</button>
                <button className="ghost" onClick={() => refreshCompany(item.ticker)}><RefreshCcw size={15} />刷新</button>
                {isList ? <button className="ghost" onClick={() => openCompany(item)}>选择</button> : null}
                <button className="danger" onClick={() => deleteTicker(item.ticker)}><Trash2 size={15} />删除观察池</button>
                <button className="danger ghost-danger" onClick={() => purgeTicker(item.ticker)}><AlertTriangle size={15} />彻底删除</button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
