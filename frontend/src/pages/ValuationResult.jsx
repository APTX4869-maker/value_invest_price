import { GuidanceCard } from "../components/GuidanceCard";
import { GuidedMetric } from "../components/GuidedMetric";
import { Badge } from "../components/Badge";
import { Stat } from "../components/Stat";
import { metricGuides } from "../data/metricGuides";
import { formatMoney, formatPercent } from "../utils/formatters";

export function ValuationResult({ result }) {
  const summary = result.v3_summary || {};
  const marketRange = summary.market_reasonable_range || { low: result.fair_value_range.low, base: result.fair_value_center, high: result.fair_value_range.high };
  const conservativeRange = summary.conservative_range;
  const optimisticRange = summary.optimistic_growth_range;
  const consistency = summary.model_consistency;
  const modelRows = result.valuation_models?.filter((item) => item.weight > 0) || [];

  return (
    <>
      <div className="valuation-hero">
        <div>
          <Badge tone={["偏贵", "明显高估", "高风险高估", "偏贵但可解释"].includes(result.judgement) ? "warn" : "good"}>{result.judgement}</Badge>
          <h2>{result.plain_language.headline}</h2>
          <p>{result.plain_language.expectation}</p>
        </div>
        <div className="range-card">
          <span>综合合理区间</span>
          <strong>{formatMoney(marketRange.low, false)} - {formatMoney(marketRange.high, false)}</strong>
          <small>中枢 {formatMoney(marketRange.base || result.fair_value_center, false)} · {summary.style_label || result.valuation_lens}</small>
        </div>
      </div>
      <div className="decision-strip">
        <Stat label="当前价" value={formatMoney(result.current_price, false)} />
        <Stat label="安全边际买入" value={`${formatMoney(result.margin_of_safety_buy_price.low, false)} - ${formatMoney(result.margin_of_safety_buy_price.high, false)}`} />
        <Stat label="高风险高估区" value={`>${formatMoney(result.overvalued_price, false)}`} />
        <Stat label="可信度" value={result.confidence} />
      </div>
      <div className="panel decision-panel">
        <div>
          <h3>普通投资者结论</h3>
          <p className="plain-callout">{result.plain_language.v3_conclusion || result.plain_language.conservative_action}</p>
          <p>{result.plain_language.model_consistency || "系统会自动综合不同估值口径，不需要你自己判断哪个模型更专业。"}</p>
        </div>
        <div className="decision-note">
          <span>最关键的不确定性</span>
          <strong>{result.plain_language.most_sensitive}</strong>
        </div>
      </div>
      {conservativeRange && optimisticRange ? (
        <div className="value-band-grid">
          <div className="value-band">
            <span>保守价值区间</span>
            <strong>{formatMoney(conservativeRange.low, false)} - {formatMoney(conservativeRange.high, false)}</strong>
            <small>只相信现金流和保守成长</small>
          </div>
          <div className="value-band primary">
            <span>市场合理区间</span>
            <strong>{formatMoney(marketRange.low, false)} - {formatMoney(marketRange.high, false)}</strong>
            <small>综合 forward PE、PEG、EV multiples 和 DCF</small>
          </div>
          <div className="value-band">
            <span>乐观成长区间</span>
            <strong>{formatMoney(optimisticRange.low, false)} - {formatMoney(optimisticRange.high, false)}</strong>
            <small>需要成长故事继续兑现</small>
          </div>
        </div>
      ) : null}
      <div className="two-column">
        <div className="panel">
          <h3>三种现金流口径</h3>
          <GuidedMetric label="实际 FCF" value={formatMoney(result.cash_flows.actual_fcf)} text="最保守，当年真正剩下的钱。" />
          <GuidedMetric label="Normalized FCF" value={formatMoney(result.cash_flows.normalized_fcf)} text="平滑高 CAPEX 年份后的现金流。" />
          <GuidedMetric label="Owner Earnings" value={formatMoney(result.cash_flows.owner_earnings)} text="更接近股东可拥有的现金流。" />
        </div>
        <div className="panel accent-panel">
          <h3>反向 DCF</h3>
          <p className="big-sentence">{result.reverse_dcf.plain_language}</p>
          <p>{result.reverse_dcf.is_capped ? "这说明当前价格已经超过本模型能稳定反推的增长范围，需要用未来 EPS 或收入增速另行校验。" : result.reverse_dcf.requires_bull_case ? "这说明当前价格更依赖牛市情景兑现。" : "这个隐含预期没有明显脱离基准情景。"}</p>
        </div>
      </div>
      <div className="panel compact-panel">
        <h3>估值口径校验</h3>
        <p className="plain-callout">{result.plain_language.sanity_check}</p>
        <div className="formula-grid">
          <Stat label="P/FCF" value={`${(result.sanity_metrics?.price_to_actual_fcf || 0).toFixed(1)}x`} />
          <Stat label="P/Owner Earnings" value={`${(result.sanity_metrics?.price_to_owner_earnings || 0).toFixed(1)}x`} />
          <Stat label="P/S" value={`${(result.sanity_metrics?.price_to_sales || 0).toFixed(1)}x`} />
          <Stat label="SBC / 收入" value={formatPercent(result.sanity_metrics?.sbc_to_revenue)} />
          {summary.forward_inputs ? <Stat label="估算 Forward EPS" value={formatMoney(summary.forward_inputs.forward_eps_estimate, false)} hint={`${summary.forward_inputs.projection_years || 1} 年前瞻窗口`} /> : null}
          {consistency ? <Stat label="模型一致性" value={consistency.level} hint={consistency.price_position} /> : null}
        </div>
      </div>
      {modelRows.length ? (
        <details className="formula-box">
          <summary>查看各估值模型的价格锚点</summary>
          <div className="model-grid">
            {modelRows.map((item) => (
              <div className="model-card" key={item.key}>
                <div>
                  <span>{item.label}</span>
                  <small>权重 {formatPercent(item.weight)}</small>
                </div>
                <strong>{formatMoney(item.low, false)} - {formatMoney(item.high, false)}</strong>
                <p>{item.explanation}</p>
              </div>
            ))}
          </div>
        </details>
      ) : null}
      <div className="scenario-grid">
        {Object.entries(result.scenarios).map(([key, item]) => (
          <div className="scenario" key={key}>
            <span>{item.label}</span>
            <strong>{formatMoney(item.per_share, false)}</strong>
            <small>概率 {formatPercent(item.probability)} / 增长 {formatPercent(item.growth)}</small>
          </div>
        ))}
      </div>
      <details className="formula-box">
        <summary>展开公式和专业指标</summary>
        <div className="guide-grid">
          <GuidanceCard guide={metricGuides.reverse} />
          <GuidanceCard guide={metricGuides.terminal} />
        </div>
        <div className="formula-grid">
          <Stat label="FCF Yield" value={formatPercent(result.yields.fcf_yield)} />
          <Stat label="OCF Yield" value={formatPercent(result.yields.ocf_yield)} />
          <Stat label="终值依赖度" value={formatPercent(result.terminal_dependency)} />
          <Stat label="现金流锚定价" value={formatMoney(result.yields.cash_flow_anchor_price, false)} />
        </div>
        <div className="guide-grid">
          <GuidanceCard guide={{
            title: "模型局限",
            oneLine: result.valuation_lens || "现金流 DCF 视角",
            standard: result.plain_language.model_limits?.join(" "),
            impact: "如果 forward PE 与 DCF 结论差异很大，应该把它当成需要进一步核验的分歧，而不是直接忽略其中一个。"
          }} />
        </div>
        <pre>{JSON.stringify(result.formula_notes, null, 2)}</pre>
      </details>
    </>
  );
}
