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

function DiscoveryReasonsPanel({ row }) {
  const entries = Object.entries(row.reasons || {}).filter(([, items]) => items?.length);
  return (
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
  );
}

function DiscoveryRow({ row, poolName, onOpen, onAdd }) {
  const [expanded, setExpanded] = useState(false);
  const ready = row.status === "ready";
  const hasReasons = Object.values(row.reasons || {}).some((items) => items?.length);
  return (
    <>
      <tr className={row.label === "重点研究" ? "discovery-focus-row" : ""}>
        <td>
          <div className="discovery-company-cell">
            <strong>#{row.discovery_rank || "-"} {row.ticker}</strong>
            <span>{row.name}</span>
            <small>{poolName} #{row.pool_rank || row.holding_rank || "-"} · 权重 {row.pool_weight ? formatPercent(row.pool_weight) : "-"}</small>
            {row.sector || row.industry ? <small>{row.sector || row.industry}</small> : null}
          </div>
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
          {hasReasons ? (
            <button className={`reason-toggle ${expanded ? "open" : ""}`} type="button" onClick={() => setExpanded(!expanded)}>
              <ChevronDown size={15} />{expanded ? "收起排名原因" : "展开排名原因"}
            </button>
          ) : null}
        </td>
        <td>
          <div className="discovery-actions">
            <button className="ghost icon-button" onClick={() => onOpen(row)} title="打开公司档案"><ExternalLink size={15} /></button>
            <button className="ghost icon-button" onClick={() => onAdd(row)} title="加入研究队列"><Plus size={15} /></button>
          </div>
        </td>
      </tr>
      {expanded ? (
        <tr className={`discovery-reasons-row ${row.label === "重点研究" ? "discovery-focus-row" : ""}`}>
          <td colSpan={10}>
            <DiscoveryReasonsPanel row={row} />
          </td>
        </tr>
      ) : null}
    </>
  );
}

export function DiscoveryPage({ setTicker, setPage, addToResearchQueue, notify }) {
  const [data, setData] = useState(null);
  const [pools, setPools] = useState([]);
  const [poolId, setPoolId] = useState("sp500");
  const [scanLimit, setScanLimit] = useState(50);
  const [customTickers, setCustomTickers] = useState("");
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("all");

  async function loadDiscovery() {
    setBusy(true);
    try {
      const [poolData, result] = await Promise.all([
        api("/api/discovery/pools").catch(() => []),
        api(`/api/discovery/latest?pool_id=${poolId}&limit=${scanLimit}`),
      ]);
      setPools(poolData);
      setData(result);
    } catch (error) {
      notify?.(error.message, "error", "发现雷达加载失败");
    } finally {
      setBusy(false);
    }
  }

  async function refreshScan() {
    setBusy(true);
    try {
      const result = await api("/api/discovery/scan", {
        method: "POST",
        body: JSON.stringify({ pool_id: poolId, limit: scanLimit, refresh_holdings: true, refresh_financials: true }),
      });
      setData(result);
      notify?.(`已扫描 ${result.universe} 前 ${scanLimit}，成功刷新 ${result.refreshed?.length || 0} 家。`, "success", "发现雷达已更新");
    } catch (error) {
      notify?.(error.message, "error", "发现雷达刷新失败");
    } finally {
      setBusy(false);
    }
  }

  async function refreshMembersOnly() {
    setBusy(true);
    try {
      await api(`/api/discovery/pools/${poolId}/refresh?limit=${scanLimit}`, { method: "POST" });
      await loadDiscovery();
      notify?.(`${data?.universe || "股票池"} 成分股已刷新。`, "success", "成分已更新");
    } catch (error) {
      notify?.(error.message, "error", "成分刷新失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveCustomPool() {
    const tickers = customTickers.split(/[\s,;，；]+/).map((item) => item.trim()).filter(Boolean);
    if (!tickers.length) {
      notify?.("请输入至少 1 个 ticker。", "error", "自定义池为空");
      return;
    }
    setBusy(true);
    try {
      await api("/api/discovery/pools/custom/members", {
        method: "PUT",
        body: JSON.stringify({ name: "自定义池", tickers }),
      });
      setPoolId("custom");
      const [poolData, result] = await Promise.all([
        api("/api/discovery/pools").catch(() => []),
        api(`/api/discovery/latest?pool_id=custom&limit=${scanLimit}`),
      ]);
      setPools(poolData);
      setData(result);
      notify?.(`已保存 ${tickers.length} 个自定义 ticker。`, "success", "自定义池已保存");
    } catch (error) {
      notify?.(error.message, "error", "自定义池保存失败");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadDiscovery();
  }, [poolId, scanLimit]);

  const rows = data?.rows || [];
  const filteredRows = useMemo(() => {
    if (filter === "focus") return rows.filter((row) => row.label === "重点研究" || row.label === "可能低估");
    if (filter === "ready") return rows.filter((row) => row.status === "ready");
    if (filter === "missing") return rows.filter((row) => row.status !== "ready");
    return rows;
  }, [rows, filter]);

  function openCompany(row) {
    addToResearchQueue?.({ ...row, pool_id: data?.pool_id }, { open: true });
  }

  async function addToQueue(row) {
    await addToResearchQueue?.({ ...row, pool_id: data?.pool_id });
  }

  const poolName = data?.universe || pools.find((pool) => pool.id === poolId)?.name || "股票池";

  return (
    <section className="page-section discovery-page">
      <div className="hero-panel discovery-hero">
        <div>
          <div className="section-title-row">
            <Badge tone="neutral">{poolName} 前 {scanLimit === 520 ? "全部" : scanLimit}</Badge>
            <Badge tone="neutral">{data?.as_of ? `成分日期 ${data.as_of}` : "等待成分数据"}</Badge>
          </div>
          <h2>从 S&P 500 或主题池里找值得继续研究的公司</h2>
          <p>
            排名先看估值置信度，再看目标中枢相对当前价格的折价/溢价，同时把护城河、财务质量、竞争风险和数据缺口放进解释里。
            这里是研究线索，不是买卖建议。
          </p>
        </div>
        <div className="discovery-hero-actions">
          <button onClick={refreshScan} disabled={busy}><RefreshCcw size={16} />{busy ? "扫描中" : "刷新并扫描"}</button>
          <button className="ghost" onClick={loadDiscovery} disabled={busy}><DatabaseZap size={16} />只读取缓存</button>
          <button className="ghost" onClick={refreshMembersOnly} disabled={busy}>刷新成分股</button>
        </div>
      </div>

      <div className="radar-controls">
        <label>
          <span>股票池</span>
          <select value={poolId} onChange={(event) => setPoolId(event.target.value)}>
            {(pools.length ? pools : [{ id: "sp500", name: "S&P 500" }, { id: "qqq", name: "QQQ" }]).map((pool) => (
              <option key={pool.id} value={pool.id}>{pool.name}</option>
            ))}
          </select>
        </label>
        <div>
          <span>扫描范围</span>
          <div className="segmented">
            <button className={scanLimit === 50 ? "active" : ""} onClick={() => setScanLimit(50)}>Top 50</button>
            <button className={scanLimit === 100 ? "active" : ""} onClick={() => setScanLimit(100)}>Top 100</button>
            <button className={scanLimit === 520 ? "active" : ""} onClick={() => setScanLimit(520)}>全部</button>
          </div>
        </div>
        <p>{data?.source || "免费源与本地缓存会优先保证可用性；缺数据的公司会保留在待补数据里。"}</p>
      </div>

      {poolId === "custom" ? (
        <div className="custom-pool-editor">
          <label>
            <span>自定义 ticker</span>
            <textarea value={customTickers} onChange={(event) => setCustomTickers(event.target.value)} placeholder="例如：NVDA, MSFT, AVGO, AMD" />
          </label>
          <button onClick={saveCustomPool} disabled={busy}>保存自定义池</button>
        </div>
      ) : null}

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
                <th>公司 / 股票池位置</th>
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
                <DiscoveryRow key={row.ticker} row={row} poolName={poolName} onOpen={openCompany} onAdd={addToQueue} />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="还没有发现结果" text="点击刷新并扫描，系统会从股票池成分和本地估值体系生成研究队列线索。" />
      )}
    </section>
  );
}
