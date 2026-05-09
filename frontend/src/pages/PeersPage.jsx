import { useEffect, useState } from "react";
import { RefreshCcw, Save, Scale } from "lucide-react";
import { Badge } from "../components/Badge";
import { Stat } from "../components/Stat";
import { formatMoney, formatPercent } from "../utils/formatters";

export function PeersPage({ companyData, updatePeers, peerSuggestions, refreshPeerSuggestions, peerComparison, refreshPeerComparison }) {
  const peers = companyData?.company?.peers || [];
  const [text, setText] = useState(peers.join(", "));
  useEffect(() => setText(peers.join(", ")), [peers.join(",")]);
  const valuation = companyData?.valuation;
  const peerSet = new Set(peers);
  const readyPeers = peerComparison?.peers?.filter((item) => item.status === "ready") || [];
  const missingPeers = peerComparison?.peers?.filter((item) => item.status !== "ready") || [];

  function addPeer(ticker) {
    const next = Array.from(new Set([...peers, ticker]));
    setText(next.join(", "));
    updatePeers(next);
  }

  function removePeer(ticker) {
    const next = peers.filter((peer) => peer !== ticker);
    setText(next.join(", "));
    updatePeers(next);
  }

  return (
    <section className="page-section">
      <div className="reading-header">
        <div>
          <p className="eyebrow">相对估值</p>
          <h2>先推荐可比公司，再由你手动选择</h2>
          <p>核心同行最多保留 8 家；FMP / Finnhub 返回的列表只作为待确认候选，不会自动参与估值倍数。</p>
        </div>
        <div className="header-actions">
          <button className="ghost" onClick={refreshPeerSuggestions}><RefreshCcw size={16} />刷新推荐</button>
          <button onClick={refreshPeerComparison}><Scale size={16} />刷新同行数据</button>
        </div>
      </div>
      <div className="panel peer-conclusion">
        <div>
          <p className="eyebrow">比较结论</p>
          <h3>{peerComparison?.summary?.headline || "还没有可比较的同行数据"}</h3>
          <p>{peerComparison?.summary?.detail || "先选择同行并刷新同行数据，系统会用同一套估值口径把它们放在一起看。"}</p>
        </div>
        <div className="mini-stats">
          <Stat label="可比较同行" value={`${peerComparison?.summary?.available_count || 0} 家`} />
          <Stat label="同行平均 价格/中枢" value={peerComparison?.summary?.peer_average_price_to_fair ? `${peerComparison.summary.peer_average_price_to_fair.toFixed(2)}x` : "-"} />
          <Stat label="同行平均 FCF Yield" value={formatPercent(peerComparison?.summary?.peer_average_fcf_yield)} />
        </div>
      </div>
      {peerComparison?.current?.status === "ready" ? (
        <div className="peer-table-wrap">
          <table className="peer-table">
            <thead>
              <tr>
                <th>公司</th>
                <th>判断</th>
                <th>当前价</th>
                <th>合理中枢</th>
                <th>价格/中枢</th>
                <th>FCF Yield</th>
                <th>质量分</th>
                <th>市场隐含增长</th>
              </tr>
            </thead>
            <tbody>
              <PeerComparisonRow item={peerComparison.current} current />
              {readyPeers.map((item) => <PeerComparisonRow item={item} key={item.ticker} />)}
            </tbody>
          </table>
        </div>
      ) : null}
      {missingPeers.length ? (
        <div className="plain-callout">
          还有 {missingPeers.length} 个同行缺少本地财务数据：{missingPeers.map((item) => item.ticker).join(", ")}。点击“刷新同行数据”后再看比较结果。
        </div>
      ) : null}
      <div className="two-column wide-left">
        <div className="panel">
          <h3>推荐候选</h3>
          <div className="peer-suggestions">
            {peerSuggestions.length ? peerSuggestions.map((item) => (
              <div className="peer-suggestion" key={item.ticker}>
                <div>
                  <div className="peer-title">
                    <strong>{item.ticker}</strong>
                    <span>{item.name}</span>
                    <Badge tone={item.confidence === "高" || item.confidence === "中高" ? "good" : "neutral"}>{item.confidence}</Badge>
                  </div>
                  <p>{item.reason}</p>
                  <small>{item.source}</small>
                </div>
                {peerSet.has(item.ticker) ? (
                  <button className="danger" onClick={() => removePeer(item.ticker)}>移除</button>
                ) : (
                  <button onClick={() => addPeer(item.ticker)}>加入</button>
                )}
              </div>
            )) : (
              <p className="plain-callout">暂时没有推荐候选。你可以手动输入同行 ticker，后续我们会继续扩充行业映射。</p>
            )}
          </div>
        </div>
        <div className="panel">
          <h3>已选择同行</h3>
          <textarea className="compact-textarea" value={text} onChange={(event) => setText(event.target.value.toUpperCase())} />
          <button onClick={() => updatePeers(text.split(/[,\s]+/).filter(Boolean))}><Save size={16} />保存同行</button>
          <div className="peer-row selected-peers">
            {peers.length ? peers.map((peer) => (
              <button className="peer-chip" key={peer} onClick={() => removePeer(peer)}>{peer} ×</button>
            )) : <span className="muted">还没有选择同行。</span>}
          </div>
          <p className="big-sentence">
            {valuation
              ? `${companyData?.company?.ticker || "当前公司"} 当前被系统判断为「${valuation.judgement}」。同行比较页会用来检查：这个判断是否只是模型偏差，还是同行也支持这个结论。`
              : "先刷新公司数据，再进行同行比较。"}
          </p>
          <p>这里保存的是核心同行篮子。候选公司可以很多，但只有你确认加入后的核心同行才会刷新数据、保存快照并参与相对估值。</p>
        </div>
      </div>
    </section>
  );
}

function PeerComparisonRow({ item, current = false }) {
  const expensive = item.price_to_fair && item.price_to_fair > 1.15;
  const cheap = item.price_to_fair && item.price_to_fair < 0.85;
  return (
    <tr className={current ? "current-peer-row" : ""}>
      <td>
        <strong>{item.ticker}</strong>
        <span>{current ? "当前公司" : item.name}</span>
      </td>
      <td><Badge tone={item.judgement === "偏贵" || item.judgement === "明显高估" ? "warn" : "good"}>{item.judgement}</Badge></td>
      <td>{formatMoney(item.current_price, false)}</td>
      <td>{formatMoney(item.fair_value_center, false)}</td>
      <td>
        <Badge tone={expensive ? "warn" : cheap ? "good" : "neutral"}>
          {item.price_to_fair ? `${item.price_to_fair.toFixed(2)}x` : "-"}
        </Badge>
      </td>
      <td>{formatPercent(item.fcf_yield)}</td>
      <td>{Math.round(item.quality_score || 0)}</td>
      <td>{formatPercent(item.reverse_growth)}</td>
    </tr>
  );
}
