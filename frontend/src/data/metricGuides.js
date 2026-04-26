function explain(title, oneLine, standard, impact) {
  return { title, oneLine, standard, impact };
}

export const metricGuides = {
  ocf: explain("OCF", "公司经营活动真正收到的现金。", "长期增长、且高于会计利润，通常说明利润质量更好。", "OCF 越稳定，估值可信度越高。"),
  fcf: explain("实际 FCF", "OCF 扣掉 CAPEX 后剩下的钱。", "FCF Yield 高于 10 年美债越多，价格越有吸引力。", "如果 CAPEX 短期很高，实际 FCF 可能低估长期价值。"),
  owner: explain("Owner Earnings", "估算股东真正能拥有的现金流。", "比实际 FCF 更适合分析高 CAPEX 但投资回报好的公司。", "这是本系统 DCF 的核心现金流口径。"),
  reverse: explain("反向 DCF", "从当前股价倒推市场相信的未来增长。", "如果隐含增长明显高于公司现实能力，价格就偏危险。", "它帮你看清楚当前价格是不是已经太乐观。"),
  terminal: explain("终值依赖度", "估值有多少来自很久以后的价值。", "低于 65% 较正常，高于 75% 说明估值很依赖长期假设。", "终值依赖越高，越需要更大的安全边际。"),
};
