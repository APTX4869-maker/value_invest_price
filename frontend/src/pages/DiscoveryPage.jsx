import { useEffect, useMemo, useState } from "react";
import { ChevronDown, DatabaseZap, ExternalLink, Plus, RefreshCcw, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { api } from "../api/client";
import { Badge } from "../components/Badge";
import { EmptyState } from "../components/EmptyState";
import { Stat } from "../components/Stat";
import { formatMoney, formatPercent } from "../utils/formatters";

function confidenceText(confidence) {
  if (!confidence) return "-";
  const label = { high: "高", medium_high: "中高", medium: "中", low: "低" }[confidence.level] || confidence.level || "-";
  return `${confidence.score || 0}/100 · ${label}`;
}

function labelTone(label) {
  if (label === "重点研究" || label === "可能低估") return "good";
  if (label === "等待回调" || label === "估值分歧大") return "warn";
  return "neutral";
}

function reasonTitle(key) {
  return {
    valuation: "估值",
    moat: "护城河",
    financials: "财务质量",
    competition: "行业竞争",
    data_quality: "数据质量",
  }[key] || key;
}

function DiscoveryReasons({ row }) {
  const entries = Object.entries(row.reasons || {}).filter(([, items]) => items?.length);
  return (
    <details className="discovery-reasons">
      <summary><ChevronDown size={15} />展开排名原因</summary>
      <div className="discovery-reason-grid">
        {entries.map(([key, items]) => (
          <div key={key}>
            <strong>{reasonTitle(key)}</strong>
            <ul>
              {items.map((item, index) => <li key={`${key}-${index}`}>{item}</li>)}
            </ul>
          </div>
        ))}
      </div>
    </details>
  );
}

function DiscoveryRow({ row, onOpen, onAdd }) {
  const ready = row.status === "ready";
  return (
    <tr className={row.label === "重点研究" ? "discovery-focus-row" : ""}>
      <td>
        <strong>#{row.discovery_rank || "-"} {row.ticker}</strong>
        <span>{row.name}</span>
        <small>QQQ #{row.holding_rank} · 权重 {formatPercent(row.qqq_weight)}</small>
      </td>
      <td><Badge tone={labelTone(row.label)}>{row.label}</Badge></td>
      <td>{ready ? confidenceText(row.confidence) : "-"}</td>
      <td>{ready ? formatPercent(row.undervaluation) : "-"}</td>
      <td>{ready ? `${row.moat_score}/100` : "-"}</td>
      <td>{ready ? `${row.financial_score}/100` : "-"}</td>
      <td>{ready ? `${row.competition_risk_score}/100` : "-"}</td>
      <td>
        <div className="discovery-price-cell">
          <span>{formatMoney(row.current_price, false)}</span>
          <strong>{ready ? formatMoney(row.target_price?.base, false) : "-"}</strong>
        </div>
      </td>
      <td>
        <p className="discovery-summary">{row.summary}</p>
        <DiscoveryReasons row={row} />
      </td>
      <td>
        <div className="discovery-actions">
          <button className="ghost icon-button" onClick={() => onOpen(row)} title="打开公司分析"><ExternalLink size={15} /></button>
          <button className="ghost icon-button" onClick={() => onAdd(row)} title="加入观察池"><Plus size={15} /></button>
        </div>
      </td>
    </tr>
  );
}

export function DiscoveryPage({ setTicker, setPage, addTicker, notify }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("all");

  async function loadDiscovery() {
    setBusy(true);
    try {
      const result = await api("/api/discovery/qqq?limit=30");
      setData(result);
    } catch (error) {
      notify?.(error.message, "error", "发现池加载失败");
    } finally {
      setBusy(false);
    }
  }

  async function refreshScan() {
    setBusy(true);
    try {
      const result = await api("/api/discovery/qqq/scan", {
        method: "POST",
        body: JSON.stringify({ limit: 30, refresh_holdings: true, refresh_financials: true }),
      });
      setData(result);
      notify?.(`已扫描 QQQ 前 30，成功刷新 ${result.refreshed?.length || 0} 家。`, "success", "发现池已更新");
    } catch (error) {
      notify?.(error.message, "error", "发现池刷新失败");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadDiscovery();
  }, []);

  const rows = data?.rows || [];
  const filteredRows = useMemo(() => {
    if (filter === "focus") return rows.filter((row) => row.label === "重点研究" || row.label === "可能低估");
    if (filter === "ready") return rows.filter((row) => row.status === "ready");
    if (filter === "missing") return rows.filter((row) => row.status !== "ready");
    return rows;
  }, [rows, filter]);

  function openCompany(row) {
    setTicker(row.ticker);
    setPage("company");
  }

  async function addToWatchlist(row) {
    const ok = await addTicker(row.ticker, row.name);
    if (ok) setPage("company");
  }

  return (
    <section className="page-section discovery-page">
      <div className="hero-panel discovery-hero">
        <div>
          <div className="section-title-row">
            <Badge tone="neutral">QQQ 前 30</Badge>
            <Badge tone="neutral">{data?.as_of ? `持仓日期 ${data.as_of}` : "等待持仓数据"}</Badge>
          </div>
          <h2>从 QQQ 里找值得继续研究的公司</h2>
          <p>
            排名先看估值置信度，再看目标中枢相对当前价格的折价/溢价，同时把护城河、财务质量和行业竞争放进解释里。
            这里是研究线索，不是买卖建议。
          </p>
        </div>
        <div className="discovery-hero-actions">
          <button onClick={refreshScan} disabled={busy}><RefreshCcw size={16} />{busy ? "扫描中" : "刷新并扫描前 30"}</button>
          <button className="ghost" onClick={loadDiscovery} disabled={busy}><DatabaseZap size={16} />只读取缓存</button>
        </div>
      </div>

      <div className="mini-stats">
        <Stat label="已评估" value={`${data?.summary?.ready || 0}/${data?.summary?.total || 0}`} hint="有本地财务数据并完成估值" />
        <Stat label="重点研究" value={`${data?.summary?.focus || 0} 家`} hint="折价、质量和可信度同时过线" />
        <Stat label="待补数据" value={`${data?.summary?.missing || 0} 家`} hint="刷新前 30 后会尽量补齐" />
      </div>

      <div className="view-toolbar">
        <div>
          <strong>候选排序</strong>
          <span>先按置信度层级，再按低估幅度，最后用质量、护城河和竞争风险微调。</span>
        </div>
        <div className="segmented">
          <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}><SlidersHorizontal size={15} />全部</button>
          <button className={filter === "focus" ? "active" : ""} onClick={() => setFilter("focus")}><ShieldCheck size={15} />低估线索</button>
          <button className={filter === "ready" ? "active" : ""} onClick={() => setFilter("ready")}>已评估</button>
          <button className={filter === "missing" ? "active" : ""} onClick={() => setFilter("missing")}>待补数据</button>
        </div>
      </div>

      {filteredRows.length ? (
        <div className="peer-table-wrap discovery-table-wrap">
          <table className="peer-table discovery-table">
            <thead>
              <tr>
                <th>公司</th>
                <th>标签</th>
                <th>置信度</th>
                <th>低估/高估</th>
                <th>护城河</th>
                <th>财务</th>
                <th>竞争风险</th>
                <th>价格/中枢</th>
                <th>排名原因</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => (
                <DiscoveryRow key={row.ticker} row={row} onOpen={openCompany} onAdd={addToWatchlist} />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="还没有发现结果" text="点击刷新并扫描前 30，系统会从 QQQ 持仓和本地估值体系生成研究队列。" />
      )}
    </section>
  );
}
