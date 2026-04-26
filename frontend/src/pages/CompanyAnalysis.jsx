import { RefreshCcw, Save, ShieldCheck, Undo2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "../components/Badge";
import { EmptyState } from "../components/EmptyState";
import { GuidedMetric } from "../components/GuidedMetric";
import { Stat } from "../components/Stat";
import { TrendChart } from "../components/TrendChart";
import { metricGuides } from "../data/metricGuides";
import { formatMoney, formatPercent } from "../utils/formatters";

function confidenceValue(confidence) {
  if (!confidence) return "-";
  return typeof confidence === "string" ? confidence : `${confidence.score}/100 · ${confidence.level}`;
}

export function CompanyAnalysis({ companyData, refreshCompany, savePriceOverride }) {
  if (!companyData?.company) return <EmptyState title="还没有公司数据" text="请先在观察池添加 ticker。" />;
  const { company, facts, valuation } = companyData;
  const segments = company.segments || [];
  const [priceDraft, setPriceDraft] = useState("");

  useEffect(() => {
    setPriceDraft(facts?.price_is_overridden && facts?.price ? String(facts.price) : "");
  }, [facts?.price, facts?.price_is_overridden]);

  return (
    <section className="page-section">
      <div className="reading-header">
        <div>
          <p className="eyebrow">{company.industry || company.sector || "未分类"}</p>
          <h2>{company.name}</h2>
          <p>{company.description || `${company.ticker} 的公司画像还不完整，刷新后会尽量从 SEC 和内置业务画像补充。`}</p>
        </div>
        <button onClick={() => refreshCompany(company.ticker)}><RefreshCcw size={16} />刷新财务数据</button>
      </div>
      <div className="profile-meta">
        <Badge>{company.ticker}</Badge>
        <Badge>{company.sector || "行业待补充"}</Badge>
        <Badge>{company.profile_source || "基础资料"}</Badge>
      </div>
      {valuation ? (
        <div className="decision-strip">
          <Stat label="当前判断" value={valuation.judgement} tone="decision" />
          <Stat label="合理价值中枢" value={formatMoney(valuation.fair_value_center, false)} />
          <Stat label="安全边际买入" value={`${formatMoney(valuation.margin_of_safety_buy_price.low, false)} - ${formatMoney(valuation.margin_of_safety_buy_price.high, false)}`} />
          <Stat label="估值可信度" value={confidenceValue(valuation.confidence)} />
        </div>
      ) : (
        <div className="empty-state compact">
          <ShieldCheck size={24} />
          <h3>这家公司还没有可用财务数据</h3>
          <p>如果这是公司股票，点击刷新会尝试从 SEC 拉取财报。若它是 ETF、基金或 ticker 拼写错误，当前估值模型无法直接分析。</p>
          <button onClick={() => refreshCompany(company.ticker)}><RefreshCcw size={16} />刷新数据</button>
        </div>
      )}
      {valuation?.plain_language.watch?.length ? (
        <div className="tips-bar">
          <strong>我应该看什么</strong>
          <span>{valuation.plain_language.watch.join(" / ")}</span>
        </div>
      ) : null}
      <div className="two-column">
        <div className="panel">
          <h3>业务介绍</h3>
          <p className="business-copy">{company.business_overview || "这家公司还没有详细业务介绍。后续可以通过年报解析或手动编辑补充。"}</p>
        </div>
        <div className="panel">
          <h3>营收结构</h3>
          {segments.length ? (
            <div className="segment-list">
              {segments.map((segment) => (
                <div className="segment-row" key={segment.name}>
                  <div className="segment-top">
                    <strong>{segment.name}</strong>
                    <span>{formatPercent(segment.share)}</span>
                  </div>
                  <div className="segment-bar"><span style={{ width: `${Math.round((segment.share || 0) * 100)}%` }} /></div>
                  <p>{segment.description}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="plain-callout">暂未自动识别分业务营收。建议先看最新 10-K 的 Segment reporting，后续版本会加入年报解析或手动编辑。</p>
          )}
        </div>
      </div>
      {facts ? (
        <div className="panel compact-panel">
          <div className="panel-heading">
            <h3>价格校验</h3>
            <Badge tone={facts.price_is_overridden ? "warn" : "neutral"}>
              {facts.price_is_overridden ? "手动覆盖中" : "使用市场价"}
            </Badge>
          </div>
          <div className="mini-stats">
            <Stat label="市场价格" value={formatMoney(facts.market_price, false)} hint={facts.market_price_source || "未获取到行情"} />
            <Stat label="估值当前使用价" value={formatMoney(facts.price, false)} hint={facts.active_price_source || "未注明"} />
            <Stat label="10 年期美债" value={formatPercent(facts.ten_year_yield)} hint={facts.ten_year_yield_source || "本地默认值"} />
          </div>
          <div className="price-override-row">
            <label className="price-override-input">
              <span>手动覆盖价格</span>
              <input
                type="number"
                step="0.01"
                placeholder="例如 185.50"
                value={priceDraft}
                onChange={(event) => setPriceDraft(event.target.value)}
              />
            </label>
            <button onClick={() => savePriceOverride(company.ticker, priceDraft)}><Save size={16} />保存覆盖价</button>
            <button className="ghost" onClick={() => savePriceOverride(company.ticker, null)}><Undo2 size={16} />恢复市场价</button>
          </div>
          <p className="plain-callout">
            当免费行情源偶尔失效，或者你想按自己记录的收盘价复盘时，可以先手动覆盖价格，再继续跑估值。
          </p>
        </div>
      ) : null}
      <div className="panel compact-panel">
        <h3>核心财务</h3>
        <div className="metric-list compact-metrics">
          <GuidedMetric label="营收" value={formatMoney(facts?.revenue)} text="公司一年卖出了多少产品或服务。" />
          <GuidedMetric label="经营利润" value={formatMoney(facts?.operating_income)} text="主业扣除日常成本后赚了多少钱。" />
          <GuidedMetric label="OCF" value={formatMoney(facts?.ocf)} text="经营活动真正流进来的现金。" guide={metricGuides.ocf} />
          <GuidedMetric label="实际 FCF" value={formatMoney(valuation?.cash_flows?.actual_fcf)} text="扣除资本开支后剩下的现金。" guide={metricGuides.fcf} />
          <GuidedMetric label="Owner Earnings" value={formatMoney(valuation?.cash_flows?.owner_earnings)} text="更接近股东真正拥有的现金流。" guide={metricGuides.owner} />
          <GuidedMetric label="CAPEX" value={formatMoney(facts?.capex)} text="买服务器、设备、工厂等长期资产的钱。" />
          <GuidedMetric label="SBC" value={formatMoney(facts?.sbc)} text="用股票发给员工的薪酬，会稀释股东。" />
        </div>
      </div>
      <div className="panel compact-panel">
        <div className="panel-heading">
          <h3>核心财务趋势</h3>
          <Badge tone="neutral">{facts?.annual_history?.length ? `${facts.annual_history.length} 年` : "等待刷新"}</Badge>
        </div>
        <TrendChart data={facts?.annual_history || []} />
        <p className="plain-callout">
          趋势图优先看方向，不追求精确到每一美元：营收和 OCF 稳定上行通常更可靠；CAPEX 快速上升时，要继续观察它是否带来未来现金流。
        </p>
      </div>
    </section>
  );
}
