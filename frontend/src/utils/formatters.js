export function formatMoney(value, compact = true) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const abs = Math.abs(value);
  if (!compact) return `$${Number(value).toFixed(2)}`;
  if (abs >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${Number(value).toFixed(2)}`;
}

export function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(1)}%`;
}
