import { useEffect, useState } from "react";
import { api } from "../api/client";

export function TickerSuggestInput({ value, onDraftChange, onSelect, placeholder = "输入 ticker", compact = false }) {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    const query = value.trim();
    if (!query) {
      setSuggestions([]);
      setOpen(false);
      setSearching(false);
      return;
    }
    if (!focused) {
      setOpen(false);
      setSearching(false);
      return;
    }
    setSearching(true);
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const result = await api(`/api/tickers/search?q=${encodeURIComponent(query)}&limit=8`);
        if (cancelled) return;
        setSuggestions(result);
        setOpen(true);
      } catch {
        if (cancelled) return;
        setSuggestions([]);
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 180);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [focused, value]);

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
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false);
          setOpen(false);
          setSearching(false);
        }}
        onChange={(event) => {
          onDraftChange(event.target.value.toUpperCase().replace(/\s+/g, ""));
          setFocused(true);
          setSearching(true);
          setOpen(true);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setFocused(false);
            setOpen(false);
            setSearching(false);
            event.currentTarget.blur();
            return;
          }
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
