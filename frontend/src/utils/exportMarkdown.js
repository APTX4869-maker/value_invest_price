import { formatMoney, formatPercent } from "./formatters";

function line(label, value) {
  return `- ${label}: ${value ?? "-"}`;
}

function tableRow(cells) {
  return `| ${cells.map((cell) => cell ?? "-").join(" | ")} |`;
}

export function buildValuationMarkdown({ ticker, companyData, result }) {
  const company = companyData?.company || {};
  const facts = companyData?.facts || {};
  const summary = result?.v3_summary || {};
  const marketRange = summary.market_reasonable_range || result?.fair_value_range || {};
  const conservativeRange = summary.conservative_range || {};
  const optimisticRange = summary.optimistic_growth_range || {};
  const models = result?.valuation_models || [];
  const watch = result?.plain_language?.watch || [];

  return [
    `# ${ticker} 估值研究导出`,
    "",
    `导出时间: ${new Date().toLocaleString()}`,
    "",
    "## 一句话结论",
    "",
    result?.plain_language?.headline || "暂无估值结论。",
    "",
    result?.plain_language?.v3_conclusion || result?.plain_language?.expectation || "",
    "",
    "## 核心价格区间",
    "",
    line("当前价", formatMoney(result?.current_price, false)),
    line("综合合理区间", `${formatMoney(marketRange.low, false)} - ${formatMoney(marketRange.high, false)}`),
    line("合理中枢", formatMoney(marketRange.base || result?.fair_value_center, false)),
    line("保守买入区", `${formatMoney(result?.margin_of_safety_buy_price?.low, false)} - ${formatMoney(result?.margin_of_safety_buy_price?.high, false)}`),
    line("高风险高估区", `高于 ${formatMoney(result?.overvalued_price, false)}`),
    line("当前判断", result?.judgement),
    line("估值可信度", result?.confidence),
    "",
    "## 三层估值区间",
    "",
    tableRow(["区间", "低位", "中枢", "高位", "含义"]),
    tableRow(["---", "---:", "---:", "---:", "---"]),
    tableRow(["保守价值", formatMoney(conservativeRange.low, false), formatMoney(conservativeRange.base, false), formatMoney(conservativeRange.high, false), "只相信现金流和保守成长"]),
    tableRow(["市场合理", formatMoney(marketRange.low, false), formatMoney(marketRange.base, false), formatMoney(marketRange.high, false), "综合市场常用估值口径"]),
    tableRow(["乐观成长", formatMoney(optimisticRange.low, false), formatMoney(optimisticRange.base, false), formatMoney(optimisticRange.high, false), "需要成长故事继续兑现"]),
    "",
    "## 公司与业务",
    "",
    line("公司名称", company.name),
    line("行业", company.industry || company.sector),
    line("公司类型", summary.style_label || result?.assumptions?.company_state),
    "",
    company.business_overview || company.description || "暂无业务介绍。",
    "",
    "## 核心财务",
    "",
    line("营收", formatMoney(facts.revenue)),
    line("经营利润", formatMoney(facts.operating_income)),
    line("OCF", formatMoney(facts.ocf)),
    line("实际 FCF", formatMoney(result?.cash_flows?.actual_fcf)),
    line("Owner Earnings", formatMoney(result?.cash_flows?.owner_earnings)),
    line("CAPEX", formatMoney(facts.capex)),
    line("SBC", formatMoney(facts.sbc)),
    "",
    "## 我应该看什么",
    "",
    watch.length ? watch.map((item) => `- ${item}`).join("\n") : "- 暂无重点观察项。",
    "",
    "## 估值模型锚点",
    "",
    tableRow(["模型", "低位", "中枢", "高位", "权重"]),
    tableRow(["---", "---:", "---:", "---:", "---:"]),
    ...models.filter((item) => item.weight > 0).map((item) => tableRow([
      item.label,
      formatMoney(item.low, false),
      formatMoney(item.base, false),
      formatMoney(item.high, false),
      formatPercent(item.weight),
    ])),
    "",
    "## 重要提醒",
    "",
    "- 这份导出不是买卖建议，只用于复盘假设。",
    "- 免费数据下的 forward EPS 可能是系统估算值，最好结合财报和外部资料校验。",
    "- 高成长公司估值区间会更宽，可信度低时要优先看关键假设是否兑现。",
    "",
  ].join("\n");
}

export function downloadMarkdown(filename, content) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
