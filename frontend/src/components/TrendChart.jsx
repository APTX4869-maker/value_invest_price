import { formatMoney } from "../utils/formatters";

const colors = {
  revenue: "#355e4b",
  operating_income: "#287c77",
  ocf: "#b78935",
  capex: "#b85c4a",
  sbc: "#66736d",
};

const labels = {
  revenue: "营收",
  operating_income: "经营利润",
  ocf: "OCF",
  capex: "CAPEX",
  sbc: "SBC",
};

export function TrendChart({ data = [], metrics = ["revenue", "operating_income", "ocf", "capex"] }) {
  const rows = data.filter((item) => item?.fiscal_year).slice(-6);
  const values = rows.flatMap((row) => metrics.map((metric) => Number(row[metric] || 0))).filter((value) => Number.isFinite(value));
  const max = Math.max(...values, 1);
  const width = 720;
  const height = 260;
  const padding = { top: 20, right: 24, bottom: 38, left: 58 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  if (rows.length < 2) {
    return <p className="plain-callout">历史财务数据不足。刷新公司后，如果 SEC 有多年 companyfacts，系统会自动生成趋势图。</p>;
  }

  function x(index) {
    return padding.left + (innerWidth * index) / Math.max(rows.length - 1, 1);
  }

  function y(value) {
    return padding.top + innerHeight - (Number(value || 0) / max) * innerHeight;
  }

  function pathFor(metric) {
    return rows.map((row, index) => `${index === 0 ? "M" : "L"} ${x(index)} ${y(row[metric])}`).join(" ");
  }

  return (
    <div className="trend-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="核心财务趋势图">
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const yPos = padding.top + innerHeight - tick * innerHeight;
          return (
            <g key={tick}>
              <line x1={padding.left} x2={width - padding.right} y1={yPos} y2={yPos} />
              <text x={padding.left - 10} y={yPos + 4}>{formatMoney(max * tick)}</text>
            </g>
          );
        })}
        {metrics.map((metric) => (
          <path key={metric} d={pathFor(metric)} stroke={colors[metric]} />
        ))}
        {rows.map((row, index) => (
          <g key={row.fiscal_year}>
            <text className="year-label" x={x(index)} y={height - 12}>{row.fiscal_year}</text>
            {metrics.map((metric) => (
              <circle key={metric} cx={x(index)} cy={y(row[metric])} r="3.4" fill={colors[metric]} />
            ))}
          </g>
        ))}
      </svg>
      <div className="trend-legend">
        {metrics.map((metric) => (
          <span key={metric}><i style={{ background: colors[metric] }} />{labels[metric]}</span>
        ))}
      </div>
    </div>
  );
}
