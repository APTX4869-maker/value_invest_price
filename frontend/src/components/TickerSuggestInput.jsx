import { useEffect, useState } from "react";
import { api } from "../api/client";

export function TickerSuggestInput({ value, onDraftChange, onSelect, placeholder = "输入 ticker", compact = false }) {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    const query = value.trim();
    if (!query) {
      setSuggestions([]);
      return;
    }
    const timer = window.setTimeout(async () => {
      setSearching(true);
      try {
        const result = await api(`/api/tickers/search?q=${encodeURIComponent(query)}&limit=8`);
        setSuggestions(result);
        setOpen(true);
      } catch {
        setSuggestions([]);
      } finally {
        setSearching(false);
      }
    }, 180);
    return () => window.clearTimeout(timer);
  }, [value]);

  function choose(item) {
    const ticker = item.ticker || value.trim().toUpperCase();
    if (!ticker) return;
    onDraftChange(ticker);
    setOpen(false);
    onSelect({ ticker, name: item.name || ticker });
  }

  return (
    <div className={`ticker-suggest ${compact ? "compact" : ""}`}>
      <input
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        onFocus={() => value && setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 130)}
        onChange={(event) => {
          onDraftChange(event.target.value.toUpperCase().replace(/\s+/g, ""));
          setOpen(true);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            choose(suggestions[0] || { ticker: value.trim().toUpperCase(), name: "" });
          }
        }}
      />
      {open && value.trim() ? (
        <div className="ticker-menu">
          {searching ? <div className="ticker-option muted-option">正在匹配 ticker...</div> : null}
          {!searching && suggestions.length === 0 ? (
            <div className="ticker-option muted-option">没有找到公司股票。请检查是否为 ETF/基金或拼写错误。</div>
          ) : null}
          {suggestions.map((item) => (
            <button type="button" className="ticker-option" key={item.ticker} onMouseDown={() => choose(item)}>
              <strong>{item.ticker}</strong>
              <span>{item.name}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
