import { Badge } from "../components/Badge";
import { Stat } from "../components/Stat";
import { formatMoney, formatPercent } from "../utils/formatters";

function confidenceText(confidence) {
  if (!confidence) return "数据不足";
  if (typeof confidence === "string") return confidence;
  if (confidence.score >= 75) return "较可靠";
  if (confidence.score >= 55) return "中等";
  return "偏低";
}

function confidenceDetail(confidence) {
  if (!confidence || typeof confidence === "string") return "";
  return `${confidence.score}/100 · ${confidence.level}`;
}

function ratingLabel(rating) {
  const labels = {
    buy: "有吸引力",
    accumulate: "可继续观察/分批",
    hold: "大致合理",
    trim: "偏贵",
    sell_or_avoid: "偏贵，谨慎",
    too_uncertain: "不确定性太高",
  };
  return labels[rating] || rating || "待判断";
}

function sourceLabel(source) {
  const labels = {
    manual_consensus: "你手动填的",
    db_consensus: "本地保存的共识",
    system_estimate: "系统估算，非市场共识",
    reported: "真实财报",
    peer_snapshot: "本地同行快照",
    default_fallback_adjusted: "系统默认倍数",
    local_setting_or_fred: "本地利率设置",
    market_price: "当前市场价格",
    system_calculated: "系统反推",
  };
  return labels[source] || source || "未注明";
}

function pricePosition(target, current) {
  if (!target?.base || !current) return "数据不足";
  if (current <= target.bear) return "低于保守价，价格比较有吸引力";
  if (current <= target.base * 0.95) return "低于基准价，略偏便宜";
  if (current <= target.base * 1.10) return "接近基准价，大致合理";
  if (current <= target.bull) return "靠近乐观价，需要未来兑现";
  return "超过乐观价，要求比较高";
}

function TargetRange({ target, current }) {
  const low = Math.min(target.range_low, current);
  const high = Math.max(target.range_high, current);
  const pos = (value) => `${Math.max(0, Math.min(100, ((value - low) / Math.max(high - low, 1)) * 100))}%`;
  return (
    <div className="target-range simple-range">
      <div className="range-track">
        <span className="range-fill" style={{ left: pos(target.bear), width: `${Math.max(2, ((target.bull - target.bear) / Math.max(high - low, 1)) * 100)}%` }} />
        <i className="range-marker bear" style={{ left: pos(target.bear) }} />
        <i className="range-marker base" style={{ left: pos(target.base) }} />
        <i className="range-marker bull" style={{ left: pos(target.bull) }} />
        <i className="range-marker current" style={{ left: pos(current) }} />
      </div>
      <div className="range-labels">
        <span>保守 {formatMoney(target.bear, false)}</span>
        <strong>合理中枢 {formatMoney(target.base, false)}</strong>
        <span>乐观 {formatMoney(target.bull, false)}</span>
        <span>当前 {formatMoney(current, false)}</span>
      </div>
    </div>
  );
}

function layerTitle(key) {
  const labels = {
    intrinsic: "内在价值区间",
    market: "12个月市场目标价",
    analyst: "外部分析师目标价",
  };
  return labels[key] || key;
}

function layerHelp(key, layer) {
  if (key === "intrinsic") return `DCF 概率区间，样本 ${layer?.sample_count || 0} 组，取 P10/P50/P90。`;
  if (key === "market") return "用 Forward P/E、EV/Sales、EV/EBITDA、FCF Yield 等市场口径综合。";
  if (key === "analyst") return `来自 ${layer?.source || "手动输入"}，只作为一层参考，不覆盖系统模型。`;
  return "";
}

function formatRange(range) {
  return `${formatMoney(range?.low, false)} - ${formatMoney(range?.high, false)}`;
}

function LayerCard({ name, layer, weight }) {
  if (!layer?.base) return null;
  return (
    <div className="valuation-layer-card">
      <div>
        <span>{layerTitle(name)}</span>
        <strong>{formatMoney(layer.base, false)}</strong>
      </div>
      <p>{formatRange({ low: layer.range_low, high: layer.range_high })}</p>
      <small>{layerHelp(name, layer)} 本次综合权重 {formatPercent(weight || 0)}。</small>
    </div>
  );
}

function ComparisonCard({ subtitle, range, base, current, note }) {
  const upside = current && base ? (base - current) / current : 0;
  return (
    <div className="valuation-comparison-card">
      <span>{subtitle}</span>
      <strong>{formatMoney(base, false)}</strong>
      <p>{formatRange(range)}</p>
      <small>相对当前价 {formatPercent(upside)}。{note}</small>
    </div>
  );
}

function AssumptionCard({ title, value, range, detail }) {
  return (
    <div className="assumption-card">
      <span>{title}</span>
      <strong>{value}</strong>
      {range ? <p>{range}</p> : null}
      <small>{detail}</small>
    </div>
  );
}

function sourcePercent(value) {
  return value === null || value === undefined ? "缺失" : formatPercent(value);
}

function coverageText(status) {
  if (status === "ok") return "已覆盖";
  if (status === "partial") return "部分覆盖";
  return "缺口";
}

function coverageTone(status) {
  if (status === "ok") return "good";
  if (status === "partial") return "neutral";
  return "warn";
}

function DataCoveragePanel({ dataQuality }) {
  const coverage = dataQuality?.data_coverage || {};
  const items = coverage.items || {};
  const apiUsage = dataQuality?.api_usage?.providers || {};
  const sourceSummary = dataQuality?.source_summary || {};
  if (!Object.keys(items).length && !Object.keys(sourceSummary).length) return null;
  return (
    <div className="panel simple-panel">
      <div className="simple-section-heading">
        <div>
          <span className="eyebrow">数据来源</span>
          <h3>这次估值的数据够不够？</h3>
        </div>
        <Badge tone={coverage.level === "high" ? "good" : coverage.level === "medium" ? "neutral" : "warn"}>
          覆盖评分 {coverage.score ?? dataQuality.score}/100
        </Badge>
      </div>
      <div className="coverage-grid">
        {Object.entries(items).map(([key, item]) => (
          <div className={`coverage-card ${item.status || "missing"}`} key={key}>
            <div>
              <strong>{item.label}</strong>
              <Badge tone={coverageTone(item.status)}>{coverageText(item.status)}</Badge>
            </div>
            <p>{item.detail}</p>
            <small>来源：{item.source}</small>
          </div>
        ))}
      </div>
      <div className="source-summary-grid">
        {Object.entries(sourceSummary).map(([key, value]) => (
          <div key={key}>
            <span>{key}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      {Object.keys(apiUsage).length ? (
        <div className="api-budget-list">
          {Object.entries(apiUsage).map(([provider, usage]) => (
            <span key={provider}>
              {provider}: 24h 网络 {usage.network_calls_24h || 0} 次，缓存命中 {usage.cache_hits_24h || 0} 次，网络失败 {usage.errors_24h || 0} 次，失败缓存 {usage.cached_error_hits_24h || 0} 次
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function plainModelText(item) {
  const key = item.model || item.key;
  const base = formatMoney(item.base, false);
  const inputs = item.key_inputs || {};
  const period = inputs.forward_period === "fy2" ? "后年" : inputs.forward_period === "fy2_proxy" ? "后年近似" : "明年";
  if (key === "forward_pe") {
    return `盈利法：如果${period}每股收益约 ${formatMoney(inputs.forward_eps, false)}，再乘上合理 PE，得到的中间价约 ${base}。`;
  }
  if (key === "three_stage_dcf") {
    return `现金流法：把未来能赚到的现金折算回今天，得到的中间价约 ${base}。`;
  }
  if (key === "ev_sales" || key === "rule_of_40_ev_sales") {
    return `收入法：用${period}收入和类似成长公司的收入倍数做参照，得到的中间价约 ${base}。`;
  }
  if (key === "ev_ebitda") {
    return `经营利润法：用${period} EBITDA 和企业价值倍数做参照，得到的中间价约 ${base}。`;
  }
  if (key === "fcf_yield") {
    return `现金收益率法：把公司当成一项现金流资产，得到的中间价约 ${base}。`;
  }
  if (key === "reverse_check") {
    return `反向检查：看当前价格要求未来做到什么，用来防止过度乐观。`;
  }
  return `${item.label}：中间价约 ${base}。`;
}

export function ValuationResult({ result }) {
  const target = result.target_price || {
    bear: result.fair_value_range?.low,
    base: result.fair_value_center,
    bull: result.fair_value_range?.high,
    range_low: result.fair_value_range?.low,
    range_high: result.fair_value_range?.high,
    upside_base: result.current_price && result.fair_value_center ? (result.fair_value_center - result.current_price) / result.current_price : 0,
  };
  const modelRows = result.model_outputs || result.valuation_models || [];
  const reverse = result.reverse_expectations || result.reverse_dcf || {};
  const reverseMultiples = reverse.multiples || {};
  const dataQuality = result.data_quality || {};
  const forward = result.forward_estimates || {};
  const valuationLayers = result.valuation_layers || {};
  const layerWeights = valuationLayers.weights || {};
  const rating = result.rating || result.judgement;
  const topModels = modelRows.filter((item) => item.weight > 0).slice(0, 4);
  const dcfModel = modelRows.find((item) => (item.model || item.key) === "three_stage_dcf");
  const fcffDcfTarget = dcfModel?.base
    ? {
        base: dcfModel.base,
        range: { low: dcfModel.bear ?? dcfModel.low, high: dcfModel.bull ?? dcfModel.high },
      }
    : result.intrinsic_value_3y?.base
      ? {
          base: result.intrinsic_value_3y.base,
          range: { low: result.intrinsic_value_3y.range_low, high: result.intrinsic_value_3y.range_high },
        }
      : null;
  const simpleDcf = result.simple_fcf_dcf;
  const assumptionBuild = result.assumption_build || {};
  const classification = assumptionBuild.classification || {};
  const growthAssumptions = assumptionBuild.growth_assumptions || {};
  const marginAssumptions = assumptionBuild.margin_assumptions || {};
  const discountAssumption = assumptionBuild.discount_rate || {};
  const opMargin = marginAssumptions.operating_margin || {};
  const fcfMargin = marginAssumptions.fcf_margin || {};
  const simpleDcfTarget = simpleDcf?.base
    ? {
        base: simpleDcf.base,
        range: { low: simpleDcf.range_low, high: simpleDcf.range_high },
      }
    : null;
  const finalVsDcfGap = fcffDcfTarget?.base ? (target.base - fcffDcfTarget.base) / fcffDcfTarget.base : 0;
  const warningCount = (dataQuality.warnings || []).length;

  return (
    <>
      <div className="simple-valuation-hero">
        <div className="simple-hero-copy">
          <Badge tone={["buy", "accumulate", "有吸引力", "偏便宜"].includes(rating) ? "good" : ["trim", "sell_or_avoid", "偏贵", "高风险高估"].includes(rating) ? "warn" : "neutral"}>
            {ratingLabel(rating)}
          </Badge>
          <h2>{result.ticker} 的综合目标价区间</h2>
          <p className="big-sentence">
            分层模型给出的 12 个月参考区间是 <strong>{formatMoney(target.bear, false)} - {formatMoney(target.bull, false)}</strong>，
            中间判断约 <strong>{formatMoney(target.base, false)}</strong>。
          </p>
          <p>{pricePosition(target, result.current_price)}。这不是买卖建议，而是把内在价值、市场倍数和外部目标价拆开后再合成。</p>
        </div>
        <div className="simple-price-card">
          <span>当前价格</span>
          <strong>{formatMoney(result.current_price, false)}</strong>
          <small>相对中间价 {formatPercent(target.upside_base)}</small>
        </div>
      </div>

      <div className="panel simple-panel">
        <div className="simple-section-heading">
          <div>
            <span className="eyebrow">先看结论</span>
            <h3>现在到底贵不贵？</h3>
          </div>
          <Badge tone={target.upside_base > 0.1 ? "good" : target.upside_base < -0.1 ? "warn" : "neutral"}>
            {pricePosition(target, result.current_price)}
          </Badge>
        </div>
        <TargetRange target={target} current={result.current_price} />
        <div className="simple-stat-row">
          <Stat label="保守情况" value={formatMoney(target.bear, false)} hint="未来不太顺时的参考价" />
          <Stat label="正常情况" value={formatMoney(target.base, false)} hint="系统目前最看重的中间价" />
          <Stat label="乐观情况" value={formatMoney(target.bull, false)} hint="增长和利润率都兑现时" />
          <Stat label="可信度" value={confidenceText(result.confidence)} hint={confidenceDetail(result.confidence)} />
        </div>
      </div>

      {fcffDcfTarget?.base || simpleDcfTarget?.base ? (
        <div className="panel simple-panel">
          <div className="simple-section-heading">
            <div>
              <span className="eyebrow">交叉对比</span>
              <h3>最终目标价体系 vs 两种 DCF</h3>
            </div>
            {fcffDcfTarget?.base ? <Badge tone={Math.abs(finalVsDcfGap) > 0.25 ? "warn" : "neutral"}>
              两者差异 {formatPercent(finalVsDcfGap)}
            </Badge> : null}
          </div>
          <div className="valuation-comparison-grid">
            <ComparisonCard
              subtitle="分层综合结果"
              base={target.base}
              range={{ low: target.bear, high: target.bull }}
              current={result.current_price}
              note="综合 DCF 概率区间、市场倍数层和可选外部目标价。"
            />
            {fcffDcfTarget?.base ? (
              <ComparisonCard
                subtitle="三阶段 FCFF DCF"
                base={fcffDcfTarget.base}
                range={fcffDcfTarget.range}
                current={result.current_price}
                note="用收入、利润率、FCF margin、贴现率和永续增长重建现金流。"
              />
            ) : null}
            {simpleDcfTarget?.base ? (
              <ComparisonCard
                subtitle="Excel 口径简化 DCF"
                base={simpleDcfTarget.base}
                range={simpleDcfTarget.range}
                current={result.current_price}
                note="用最新 FCF、7%-15% 增长阶梯、15% 折现和当前 FCF 倍数退出价值。"
              />
            ) : null}
          </div>
          <p className="muted">
            三阶段 FCFF DCF 更适合严肃建模；Excel 口径简化 DCF 更适合和表格快速对表。简化 DCF 用当前市场 FCF 倍数做退出价值，所以只作为交叉校验，不直接参与最终目标价。
          </p>
        </div>
      ) : null}

      {valuationLayers.intrinsic || valuationLayers.market || valuationLayers.analyst ? (
        <div className="panel simple-panel">
          <div className="simple-section-heading">
            <div>
              <span className="eyebrow">拆开看</span>
              <h3>这个区间由三层估值合成</h3>
            </div>
          </div>
          <div className="valuation-layer-grid">
            <LayerCard name="intrinsic" layer={valuationLayers.intrinsic} weight={layerWeights.intrinsic} />
            <LayerCard name="market" layer={valuationLayers.market} weight={layerWeights.market} />
            <LayerCard name="analyst" layer={valuationLayers.analyst} weight={layerWeights.analyst} />
          </div>
        </div>
      ) : null}

      <DataCoveragePanel dataQuality={dataQuality} />

      {assumptionBuild.scenarios ? (
        <div className="panel simple-panel">
          <div className="simple-section-heading">
            <div>
              <span className="eyebrow">关键假设</span>
              <h3>这些参数是怎么来的？</h3>
            </div>
            <Badge tone={classification.confidence === "high" || classification.confidence === "medium_high" ? "good" : "warn"}>
              类型判断：{result.company_state || result.company_type}
            </Badge>
          </div>
          <div className="assumption-grid">
            <AssumptionCard
              title="5 年收入 CAGR"
              value={formatPercent(growthAssumptions.base)}
              range={`${formatPercent(growthAssumptions.bear)} / ${formatPercent(growthAssumptions.base)} / ${formatPercent(growthAssumptions.bull)}`}
              detail={`3年历史 ${sourcePercent(growthAssumptions.sources?.revenue_cagr_3y)}，5年历史 ${sourcePercent(growthAssumptions.sources?.revenue_cagr_5y)}，最近季度 ${sourcePercent(growthAssumptions.sources?.recent_annualized_growth)}，公司先验 ${sourcePercent(growthAssumptions.sources?.company_prior)}，行业先验 ${sourcePercent(growthAssumptions.sources?.industry_prior)}。`}
            />
            <AssumptionCard
              title="终局经营利润率"
              value={formatPercent(opMargin.base)}
              range={`${formatPercent(opMargin.bear)} / ${formatPercent(opMargin.base)} / ${formatPercent(opMargin.bull)}`}
              detail={`当前 ${sourcePercent(opMargin.sources?.current)}，历史中位 ${sourcePercent(opMargin.sources?.history_median_recent)}，行业先验 ${sourcePercent(opMargin.sources?.industry_prior)}。`}
            />
            <AssumptionCard
              title="终局 FCF margin"
              value={formatPercent(fcfMargin.base)}
              range={`${formatPercent(fcfMargin.bear)} / ${formatPercent(fcfMargin.base)} / ${formatPercent(fcfMargin.bull)}`}
              detail={`当前 ${sourcePercent(fcfMargin.sources?.current)}，历史中位 ${sourcePercent(fcfMargin.sources?.history_median_recent)}，行业先验 ${sourcePercent(fcfMargin.sources?.industry_prior)}。`}
            />
            <AssumptionCard
              title="贴现率"
              value={formatPercent(discountAssumption.base)}
              range={`${formatPercent(discountAssumption.bear)} / ${formatPercent(discountAssumption.base)} / ${formatPercent(discountAssumption.bull)}`}
              detail={`无风险 ${formatPercent(discountAssumption.risk_free_rate)} + 股权风险溢价 ${formatPercent(discountAssumption.equity_risk_premium)} + 公司风险 ${formatPercent(discountAssumption.company_risk_premium)}。`}
            />
          </div>
          <div className="assumption-notes">
            {(classification.reasons || []).map((reason) => <p className="muted" key={reason}>{reason}</p>)}
            {(assumptionBuild.warnings || []).slice(0, 3).map((warning) => <p className="muted" key={warning}>{warning}</p>)}
          </div>
        </div>
      ) : null}

      <div className="two-column simple-two-column">
        <div className="panel simple-panel">
          <div className="simple-section-heading">
            <div>
              <span className="eyebrow">反过来看</span>
              <h3>当前价格在赌什么？</h3>
            </div>
          </div>
          <p className="plain-callout">{reverse.plain_language || "当前数据不足，暂时无法反推出市场隐含预期。"}</p>
          <div className="simple-stat-row compact">
            <Stat label="需要的收入增速" value={formatPercent(reverse.implied_revenue_cagr_5y)} hint="未来 5 年年化" />
            <Stat label="需要的现金流率" value={formatPercent(reverse.implied_terminal_fcf_margin)} hint="终局 FCF margin" />
            <Stat label="当前 PE 口径" value={`${(reverseMultiples.implied_forward_pe || 0).toFixed(1)}x`} hint="越高越依赖增长" />
          </div>
          <p className="muted">{reverseMultiples.plain_language}</p>
        </div>

        <div className="panel simple-panel">
          <div className="simple-section-heading">
            <div>
              <span className="eyebrow">别过度相信数字</span>
              <h3>这次估值有多可靠？</h3>
            </div>
          </div>
          <p className="plain-callout">
            可信度：{confidenceText(result.confidence)}。{warningCount ? `系统发现 ${warningCount} 个需要注意的地方。` : "关键数据暂时没有明显异常。"}
          </p>
          {(dataQuality.warnings || []).slice(0, 3).map((warning) => <p className="muted" key={warning}>{warning}</p>)}
        </div>
      </div>

      <div className="panel simple-panel">
        <div className="simple-section-heading">
          <div>
            <span className="eyebrow">白话版</span>
            <h3>系统是怎么算出这个区间的？</h3>
          </div>
        </div>
        <div className="plain-model-list">
          {topModels.map((item) => (
            <div className="plain-model-card" key={item.model || item.key}>
              <strong>{item.label}</strong>
              <p>{plainModelText(item)}</p>
              <small>这个方法在本次估值里占 {formatPercent(item.weight)}。</small>
            </div>
          ))}
        </div>
      </div>

      <details className="formula-box">
        <summary>高级详情：模型、输入来源、分层权重、CAPEX 拆分和 DCF 敏感性</summary>
        <div className="model-table">
          <div className="model-table-head">
            <span>模型</span>
            <span>保守 / 正常 / 乐观</span>
            <span>权重</span>
            <span>数据来源</span>
          </div>
          {modelRows.filter((item) => item.weight > 0).map((item) => (
            <div className="model-table-row" key={item.model || item.key}>
              <strong>{item.label}</strong>
              <span>{formatMoney(item.bear ?? item.low, false)} / {formatMoney(item.base, false)} / {formatMoney(item.bull ?? item.high, false)}</span>
              <span>{formatPercent(item.weight)}</span>
              <small>{Object.entries(item.data_sources || {}).map(([key, value]) => `${key}: ${sourceLabel(value)}`).join(" · ")}</small>
              <p>{item.weight_reason || item.explanation}</p>
            </div>
          ))}
        </div>
        <div className="formula-grid">
          {Object.entries(forward).map(([key, item]) => (
            <Stat key={key} label={`${key} · ${sourceLabel(item.source)}`} value={key.includes("growth") ? formatPercent(item.value) : formatMoney(item.value)} />
          ))}
        </div>
        <pre>{JSON.stringify({ assumption_build: result.assumption_build, valuation_layers: result.valuation_layers, simple_fcf_dcf: result.simple_fcf_dcf, model_weighted_aggregate: result.model_weighted_aggregate, capex_split: result.capex_split, dcf_sensitivity: result.dcf?.sensitivity, key_risks: result.key_risks }, null, 2)}</pre>
      </details>
    </>
  );
}
