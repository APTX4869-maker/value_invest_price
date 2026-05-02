import { ArrowRight, LayoutGrid, List, RefreshCcw, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge } from "../components/Badge";
import { EmptyState } from "../components/EmptyState";
import { Stat } from "../components/Stat";
import { TickerSuggestInput } from "../components/TickerSuggestInput";
import { formatMoney } from "../utils/formatters";

const STATUSES = [
  { id: "candidate", label: "候选" },
  { id: "initial_review", label: "初筛通过" },
  { id: "deep_research", label: "深度研究中" },
  { id: "concluded", label: "已形成结论" },
  { id: "review", label: "复盘中" },
];

function confidenceValue(confidence) {
  if (!confidence) return "-";
  return typeof confidence === "string" ? confidence : `${confidence.score}/100 · ${confidence.level}`;
}

function nextStatus(status) {
  const index = STATUSES.findIndex((item) => item.id === status);
  return STATUSES[Math.min(index + 1, STATUSES.length - 1)]?.id || status;
}

function judgementTone(judgement) {
  if (judgement === "偏贵" || judgement === "明显高估") return "warn";
  if (!judgement || judgement === "待分析") return "neutral";
  return "good";
}

function QueueCard({ item, setTicker, setPage, refreshCompany, updateResearchQueueItem, deleteResearchQueueItem, tickerErrors }) {
  const valuation = item.valuation;
  const company = item.company || {};
  const status = item.status || "candidate";

  function openDossier() {
    setTicker(item.ticker);
    setPage("company");
  }

  return (
    <article className="queue-card">
      <div className="card-head">
        <div>
          <h3>{item.ticker}</h3>
          <p>{company.name || item.ticker}</p>
        </div>
        <Badge tone={judgementTone(valuation?.judgement)}>{valuation?.judgement || "待分析"}</Badge>
      </div>

      <div className="queue-tags">
        <Badge>{item.status_label}</Badge>
        {item.discovery_label ? <Badge tone="good">{item.discovery_label}</Badge> : null}
        {(item.tags || []).slice(0, 3).map((tag) => <Badge key={tag} tone="neutral">{tag}</Badge>)}
      </div>

      <div className="mini-stats">
        <Stat label="当前价" value={formatMoney(valuation?.current_price, false)} />
        <Stat label="合理中枢" value={formatMoney(valuation?.fair_value_center, false)} />
        <Stat label="可信度" value={confidenceValue(valuation?.confidence)} />
      </div>

      <p className="plain-callout">{item.entry_reason || "手动加入的研究线索，等待补充入队理由。"}</p>
      <p className="queue-next"><strong>下一步</strong><span>{item.next_action}</span></p>
      {tickerErrors[item.ticker] ? <p className="error-callout">{tickerErrors[item.ticker]}</p> : null}

      <div className="queue-edit-row">
        <label>
          <span>状态</span>
          <select value={status} onChange={(event) => updateResearchQueueItem(item.ticker, { status: event.target.value })}>
            {STATUSES.map((entry) => <option key={entry.id} value={entry.id}>{entry.label}</option>)}
          </select>
        </label>
        <button className="ghost" onClick={() => updateResearchQueueItem(item.ticker, { status: nextStatus(status) })}>
          <ArrowRight size={15} />推进
        </button>
      </div>

      <div className="card-actions">
        <button onClick={openDossier}>打开档案</button>
        <button className="ghost" onClick={() => refreshCompany(item.ticker)}><RefreshCcw size={15} />刷新</button>
        <button className="danger" onClick={() => deleteResearchQueueItem(item.ticker)}><Trash2 size={15} />移出队列</button>
      </div>
    </article>
  );
}

function QueueListRow({ item, setTicker, setPage, refreshCompany, updateResearchQueueItem, deleteResearchQueueItem }) {
  const valuation = item.valuation;
  return (
    <tr>
      <td>
        <strong>{item.ticker}</strong>
        <span>{item.company?.name || item.ticker}</span>
      </td>
      <td>
        <select value={item.status} onChange={(event) => updateResearchQueueItem(item.ticker, { status: event.target.value })}>
          {STATUSES.map((entry) => <option key={entry.id} value={entry.id}>{entry.label}</option>)}
        </select>
      </td>
      <td>{valuation?.judgement || "待分析"}</td>
      <td>{formatMoney(valuation?.current_price, false)} / {formatMoney(valuation?.fair_value_center, false)}</td>
      <td>{item.priority_score ? Math.round(item.priority_score) : "-"}</td>
      <td><span className="table-muted">{item.next_action}</span></td>
      <td>
        <div className="discovery-actions">
          <button className="ghost icon-button" title="打开档案" onClick={() => { setTicker(item.ticker); setPage("company"); }}><ArrowRight size={15} /></button>
          <button className="ghost icon-button" title="刷新" onClick={() => refreshCompany(item.ticker)}><RefreshCcw size={15} /></button>
          <button className="danger icon-button" title="移出队列" onClick={() => deleteResearchQueueItem(item.ticker)}><Trash2 size={15} /></button>
        </div>
      </td>
    </tr>
  );
}

export function Watchlist({
  researchQueue = [],
  setTicker,
  setPage,
  addTicker,
  refreshCompany,
  updateResearchQueueItem,
  deleteResearchQueueItem,
  loading,
  tickerErrors,
}) {
  const [newTicker, setNewTicker] = useState("");
  const [viewMode, setViewMode] = useState("board");
  const [statusFilter, setStatusFilter] = useState("all");
  const isList = viewMode === "list";

  const filtered = useMemo(() => {
    if (statusFilter === "all") return researchQueue;
    return researchQueue.filter((item) => item.status === statusFilter);
  }, [researchQueue, statusFilter]);

  const counts = useMemo(() => {
    return STATUSES.reduce((acc, status) => {
      acc[status.id] = researchQueue.filter((item) => item.status === status.id).length;
      return acc;
    }, {});
  }, [researchQueue]);

  return (
    <section className="page-section">
      <div className="hero-panel">
        <div>
          <p className="eyebrow">从线索到结论</p>
          <h2>研究队列记录每家公司研究到哪一步</h2>
          <p>候选公司先进队列，再逐步推进到初筛、深度研究、形成结论和复盘。它是发现雷达与公司档案之间的工作台。</p>
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
          <button disabled={loading}><Search size={16} />加入</button>
        </form>
      </div>

      <div className="mini-stats">
        {STATUSES.map((status) => (
          <Stat key={status.id} label={status.label} value={`${counts[status.id] || 0} 家`} />
        ))}
      </div>

      <div className="view-toolbar">
        <div>
          <strong>队列视图</strong>
          <span>看板适合推进研究流程，列表适合快速扫描优先级和下一步动作。</span>
        </div>
        <div className="segmented">
          <button className={viewMode === "board" ? "active" : ""} onClick={() => setViewMode("board")}><LayoutGrid size={16} />看板</button>
          <button className={viewMode === "list" ? "active" : ""} onClick={() => setViewMode("list")}><List size={16} />列表</button>
        </div>
      </div>

      <div className="segmented queue-filter">
        <button className={statusFilter === "all" ? "active" : ""} onClick={() => setStatusFilter("all")}>全部</button>
        {STATUSES.map((status) => (
          <button key={status.id} className={statusFilter === status.id ? "active" : ""} onClick={() => setStatusFilter(status.id)}>
            {status.label}
          </button>
        ))}
      </div>

      {filtered.length ? (
        isList ? (
          <div className="peer-table-wrap">
            <table className="peer-table queue-table">
              <thead>
                <tr>
                  <th>公司</th>
                  <th>状态</th>
                  <th>估值判断</th>
                  <th>价格/中枢</th>
                  <th>优先级</th>
                  <th>下一步</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <QueueListRow key={item.ticker} item={item} setTicker={setTicker} setPage={setPage} refreshCompany={refreshCompany} updateResearchQueueItem={updateResearchQueueItem} deleteResearchQueueItem={deleteResearchQueueItem} />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="queue-board">
            {STATUSES.map((status) => {
              const items = filtered.filter((item) => item.status === status.id);
              if (!items.length && statusFilter !== "all") return null;
              return (
                <section key={status.id} className="queue-column">
                  <div className="queue-column-head">
                    <strong>{status.label}</strong>
                    <span>{items.length}</span>
                  </div>
                  <div className="queue-column-body">
                    {items.map((item) => (
                      <QueueCard key={item.ticker} item={item} setTicker={setTicker} setPage={setPage} refreshCompany={refreshCompany} updateResearchQueueItem={updateResearchQueueItem} deleteResearchQueueItem={deleteResearchQueueItem} tickerErrors={tickerErrors} />
                    ))}
                    {!items.length ? <p className="muted empty-column">暂无公司</p> : null}
                  </div>
                </section>
              );
            })}
          </div>
        )
      ) : (
        <EmptyState title="研究队列为空" text="先从发现雷达加入候选公司，或者手动输入 ticker。"/>
      )}
    </section>
  );
}
