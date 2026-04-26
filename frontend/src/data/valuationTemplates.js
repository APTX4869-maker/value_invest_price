export const valuationTemplates = {
  platform: {
    label: "平台 / 广告 / 网络效应",
    description: "适合 GOOG、META 这类现金流强、规模效应明显、长期护城河较深的公司。",
    assumptions: {
      base_growth: 12,
      bear_growth: 6,
      bull_growth: 17,
      discount_rate: 9,
      terminal_growth: 2.5,
      risk_discount: 3,
      maintenance_capex_ratio: 25,
      sbc_adjustment_ratio: 50,
      quality_score: 82,
    },
  },
  software: {
    label: "软件 / SaaS / 数据平台",
    description: "适合 PLTR、CRM 这类增长更高但 SBC、利润率和客户集中度需要额外检查的公司。",
    assumptions: {
      base_growth: 15,
      bear_growth: 8,
      bull_growth: 22,
      discount_rate: 10,
      terminal_growth: 3,
      risk_discount: 5,
      maintenance_capex_ratio: 18,
      sbc_adjustment_ratio: 70,
      quality_score: 78,
    },
  },
  payments: {
    label: "支付 / 金融科技",
    description: "适合 PYPL、V、MA 这类交易量、费率和竞争格局共同决定增长的公司。",
    assumptions: {
      base_growth: 10,
      bear_growth: 4,
      bull_growth: 15,
      discount_rate: 9.5,
      terminal_growth: 2.5,
      risk_discount: 4,
      maintenance_capex_ratio: 20,
      sbc_adjustment_ratio: 45,
      quality_score: 80,
    },
  },
  consumer: {
    label: "消费品牌 / 稳定现金流",
    description: "适合 KO、PEP 这类增长慢但现金流稳定、品牌和分红属性更强的公司。",
    assumptions: {
      base_growth: 5,
      bear_growth: 2,
      bull_growth: 8,
      discount_rate: 8.5,
      terminal_growth: 2,
      risk_discount: 2,
      maintenance_capex_ratio: 35,
      sbc_adjustment_ratio: 20,
      quality_score: 78,
    },
  },
  hardware: {
    label: "硬件 / 半导体 / 制造",
    description: "适合 NVDA、TSLA 这类周期性、资本开支和竞争变化更重要的公司。",
    assumptions: {
      base_growth: 8,
      bear_growth: 2,
      bull_growth: 14,
      discount_rate: 10,
      terminal_growth: 2.2,
      risk_discount: 5,
      maintenance_capex_ratio: 45,
      sbc_adjustment_ratio: 35,
      quality_score: 74,
    },
  },
  conservative: {
    label: "通用保守模板",
    description: "当公司类型不清楚时，先用更保守的增长和更高的风险折扣，避免模型过度乐观。",
    assumptions: {
      base_growth: 7,
      bear_growth: 2,
      bull_growth: 11,
      discount_rate: 10,
      terminal_growth: 2,
      risk_discount: 6,
      maintenance_capex_ratio: 35,
      sbc_adjustment_ratio: 50,
      quality_score: 70,
    },
  },
};

export function inferValuationTemplate(company = {}) {
  const text = [company.ticker, company.name, company.sector, company.industry, company.description, company.business_overview]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  if (/(beverage|consumer|coca|pepsi|restaurant|retail|brand)/.test(text)) return "consumer";
  if (/(payment|fintech|transaction|credit card|merchant)/.test(text)) return "payments";
  if (/(software|saas|cloud|data platform|analytics|cybersecurity)/.test(text)) return "software";
  if (/(semiconductor|hardware|vehicle|manufactur|automotive|chip|gpu)/.test(text)) return "hardware";
  if (/(advertising|search|social|platform|marketplace|network)/.test(text)) return "platform";
  return "conservative";
}
