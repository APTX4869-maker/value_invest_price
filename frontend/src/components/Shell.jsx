import { useEffect, useState } from "react";
import { Database, Sparkles, TrendingUp } from "lucide-react";
import { pages } from "../constants/navigation";
import { TickerSuggestInput } from "./TickerSuggestInput";

export function Shell({ page, setPage, ticker, setTicker, children, status }) {
  const [tickerDraft, setTickerDraft] = useState(ticker);

  useEffect(() => {
    setTickerDraft(ticker);
  }, [ticker]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><TrendingUp size={20} /></div>
          <div>
            <strong>Value Study</strong>
            <span>本地估值研究</span>
          </div>
        </div>
        <label className="ticker-picker">
          <span>当前公司</span>
          <TickerSuggestInput
            value={tickerDraft}
            onDraftChange={setTickerDraft}
            onSelect={(item) => setTicker(item.ticker)}
            placeholder="例如 NVDA"
            compact
          />
        </label>
        <nav>
          {pages.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}>
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-note">
          <Sparkles size={16} />
          <p>先看白话结论，再展开公式。这个工具是帮你复盘假设，不是替你下单。</p>
        </div>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Personal investing research</p>
            <h1>{pages.find((item) => item.id === page)?.label}</h1>
          </div>
          <div className="status-pill"><Database size={16} />{status}</div>
        </header>
        {children}
      </main>
    </div>
  );
}
