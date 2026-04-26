import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api/client";
import { Shell } from "./components/Shell";
import { ToastStack } from "./components/ToastStack";
import { CompanyAnalysis } from "./pages/CompanyAnalysis";
import { HistorySettings } from "./pages/HistorySettings";
import { NotesPage } from "./pages/NotesPage";
import { PeersPage } from "./pages/PeersPage";
import { ValuationModel } from "./pages/ValuationModel";
import { Watchlist } from "./pages/Watchlist";
import "./styles.css";

function App() {
  const [page, setPage] = useState("watchlist");
  const [ticker, setTicker] = useState("GOOG");
  const [watchlist, setWatchlist] = useState([]);
  const [companyData, setCompanyData] = useState(null);
  const [valuationResult, setValuationResult] = useState(null);
  const [note, setNote] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [settings, setSettings] = useState({});
  const [peerSuggestions, setPeerSuggestions] = useState([]);
  const [peerComparison, setPeerComparison] = useState(null);
  const [status, setStatus] = useState("连接中");
  const [toasts, setToasts] = useState([]);
  const [tickerErrors, setTickerErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const normalizedTicker = useMemo(() => ticker.trim().toUpperCase() || "GOOG", [ticker]);

  function dismissToast(id) {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }

  function notify(message, type = "info", title = type === "error" ? "操作失败" : "已完成") {
    setStatus(message);
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((current) => [...current.slice(-3), { id, type, title, message }]);
    window.setTimeout(() => dismissToast(id), type === "error" ? 6500 : 4200);
  }

  async function loadAll(target = normalizedTicker) {
    setLoading(true);
    try {
      const [watch, company, noteData, snaps, peerSuggestionData, peerComparisonData, settingData] = await Promise.all([
        api("/api/watchlist"),
        api(`/api/company/${target}`).catch(() => null),
        api(`/api/notes/${target}`).catch(() => null),
        api(`/api/snapshots/${target}`).catch(() => []),
        api(`/api/company/${target}/peer-suggestions`).catch(() => []),
        api(`/api/company/${target}/peers/compare`).catch(() => null),
        api("/api/settings").catch(() => ({})),
      ]);
      setWatchlist(watch);
      setCompanyData(company);
      setNote(noteData);
      setSnapshots(snaps);
      setPeerSuggestions(peerSuggestionData);
      setPeerComparison(peerComparisonData);
      setSettings(settingData);
      setValuationResult(null);
      setStatus("本地后端已连接");
    } catch (error) {
      notify(error.message, "error", "连接失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll(normalizedTicker);
  }, [normalizedTicker]);

  async function addTicker(nextTicker, name) {
    const target = nextTicker.toUpperCase();
    try {
      await api("/api/watchlist", { method: "POST", body: JSON.stringify({ ticker: target, name }) });
      setTicker(target);
      await loadAll(target);
      await refreshCompany(target, true);
      notify(`${target} 已加入观察池。`, "success", "添加成功");
      return true;
    } catch (error) {
      notify(error.message, "error", `${target} 添加失败`);
      return false;
    }
  }

  async function refreshCompany(target = normalizedTicker, quiet = false) {
    setLoading(true);
    try {
      await api(`/api/company/${target}/refresh`, { method: "POST" });
      setTickerErrors((current) => {
        const next = { ...current };
        delete next[target];
        return next;
      });
      await loadAll(target);
    } catch (error) {
      setTickerErrors((current) => ({ ...current, [target]: error.message }));
      notify(error.message, "error", `${target} 刷新失败`);
      if (!quiet) {
        await loadAll(target);
      }
    } finally {
      setLoading(false);
    }
  }

  async function deleteTicker(target, options = {}) {
    const purge = options.purge === true;
    const message = purge
      ? `确定要彻底删除 ${target} 吗？\n\n这会移除观察池条目、本地财务缓存、研究笔记和历史快照。这个操作主要用于清理输错的 ticker 或你不再需要的研究记录。`
      : `确定要从观察池删除 ${target} 吗？\n\n这会移除观察池条目并清除本地财务缓存；历史快照和研究笔记会保留。`;
    const ok = window.confirm(message);
    if (!ok) return;
    if (purge) {
      const secondOk = window.confirm(`请再次确认：彻底删除 ${target} 后，研究笔记和历史快照也会一起清除。`);
      if (!secondOk) return;
    }
    setLoading(true);
    try {
      const result = await api(`/api/watchlist/${target}${purge ? "/purge" : ""}`, { method: "DELETE" });
      setTickerErrors((current) => {
        const next = { ...current };
        delete next[target];
        return next;
      });
      const nextAvailable = watchlist.find((item) => item.ticker !== target)?.ticker || "GOOG";
      const nextTicker = target === normalizedTicker ? nextAvailable : normalizedTicker;
      setTicker(nextTicker);
      await loadAll(nextTicker);
      notify(result.message, "success", purge ? "彻底删除完成" : "已从观察池删除");
    } catch (error) {
      notify(error.message, "error", "删除失败");
    } finally {
      setLoading(false);
    }
  }

  async function saveSnapshot(result) {
    try {
      await api("/api/valuation/snapshot", {
        method: "POST",
        body: JSON.stringify({ ticker: normalizedTicker, title: `${normalizedTicker} 估值快照`, inputs: result.assumptions, result }),
      });
      await loadAll(normalizedTicker);
      notify(`${normalizedTicker} 估值快照已保存。`, "success", "快照已保存");
      setPage("history");
    } catch (error) {
      notify(error.message, "error", "快照保存失败");
    }
  }

  async function saveNote(content) {
    try {
      const saved = await api(`/api/notes/${normalizedTicker}`, { method: "PUT", body: JSON.stringify({ content }) });
      setNote(saved);
      notify(`${normalizedTicker} 研究笔记已保存。`, "success", "笔记已保存");
    } catch (error) {
      notify(error.message, "error", "笔记保存失败");
    }
  }

  async function saveSettings(next) {
    try {
      const saved = await api("/api/settings", { method: "PUT", body: JSON.stringify({ settings: next }) });
      setSettings(saved);
      notify("设置已保存。", "success", "设置已保存");
    } catch (error) {
      notify(error.message, "error", "设置保存失败");
    }
  }

  async function savePriceOverride(target, price) {
    const normalizedPrice = price === null || price === "" ? null : Number(price);
    if (normalizedPrice !== null && Number.isNaN(normalizedPrice)) {
      notify("请输入有效价格后再保存。", "error", "价格无效");
      return;
    }
    try {
      const result = await api(`/api/company/${target}/price-override`, {
        method: "PUT",
        body: JSON.stringify({ price: normalizedPrice }),
      });
      setCompanyData(result);
      setValuationResult(null);
      notify(normalizedPrice === null ? "已恢复使用市场价。" : `已把 ${target} 的估值价格改为 ${normalizedPrice.toFixed(2)}。`, "success", "价格设置已保存");
      await loadAll(target);
    } catch (error) {
      notify(error.message, "error", "价格设置失败");
    }
  }

  async function updatePeers(peers) {
    try {
      await api(`/api/company/${normalizedTicker}/peers`, { method: "PUT", body: JSON.stringify({ peers }) });
      await loadAll(normalizedTicker);
      notify(`${normalizedTicker} 同行列表已更新。`, "success", "同行已更新");
    } catch (error) {
      notify(error.message, "error", "同行更新失败");
    }
  }

  async function refreshPeerSuggestions() {
    try {
      const suggestions = await api(`/api/company/${normalizedTicker}/peer-suggestions`);
      setPeerSuggestions(suggestions);
      notify("同行推荐已刷新。", "success", "推荐已刷新");
    } catch (error) {
      notify(error.message, "error", "推荐刷新失败");
    }
  }

  async function refreshPeerComparison() {
    setLoading(true);
    try {
      const result = await api(`/api/company/${normalizedTicker}/peers/refresh`, { method: "POST" });
      setPeerComparison(result.comparison);
      notify(`已刷新 ${result.results.filter((item) => item.status === "ready").length} 个同行。`, "success", "同行数据已刷新");
      await loadAll(normalizedTicker);
    } catch (error) {
      notify(error.message, "error", "同行刷新失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Shell page={page} setPage={setPage} ticker={ticker} setTicker={setTicker} status={status}>
        {page === "watchlist" && <Watchlist watchlist={watchlist} setTicker={setTicker} setPage={setPage} addTicker={addTicker} refreshCompany={refreshCompany} deleteTicker={deleteTicker} purgeTicker={(target) => deleteTicker(target, { purge: true })} loading={loading} tickerErrors={tickerErrors} />}
        {page === "company" && <CompanyAnalysis companyData={companyData} refreshCompany={refreshCompany} savePriceOverride={savePriceOverride} />}
        {page === "valuation" && <ValuationModel ticker={normalizedTicker} companyData={companyData} valuationResult={valuationResult} setValuationResult={setValuationResult} saveSnapshot={saveSnapshot} notify={notify} />}
        {page === "peers" && <PeersPage companyData={companyData} updatePeers={updatePeers} peerSuggestions={peerSuggestions} refreshPeerSuggestions={refreshPeerSuggestions} peerComparison={peerComparison} refreshPeerComparison={refreshPeerComparison} />}
        {page === "notes" && <NotesPage ticker={normalizedTicker} note={note} saveNote={saveNote} />}
        {page === "history" && <HistorySettings ticker={normalizedTicker} snapshots={snapshots} settings={settings} saveSettings={saveSettings} />}
      </Shell>
      <ToastStack toasts={toasts} dismissToast={dismissToast} />
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
