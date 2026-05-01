import { useEffect, useMemo, useState } from "react";
import { Download, LineChart, Save } from "lucide-react";
import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { inferValuationTemplate, valuationTemplates } from "../data/valuationTemplates";
import { buildValuationMarkdown, downloadMarkdown } from "../utils/exportMarkdown";
import { ValuationResult } from "./ValuationResult";

const emptyConsensus = {
  eps_next_year: "",
  eps_2y: "",
  revenue_next_year: "",
  revenue_2y: "",
  ebitda_next_year: "",
  operating_income_next_year: "",
  fcf_next_year: "",
  long_term_eps_growth: "",
};

const emptyAnalystTarget = {
  low: "",
  median: "",
  high: "",
  source: "",
};

export function ValuationModel({ ticker, companyData, valuationResult, setValuationResult, saveSnapshot, notify }) {
  const recommendedTemplateId = useMemo(
    () => inferValuationTemplate(companyData?.company || { ticker }),
    [companyData?.company, ticker]
  );
  const [selectedTemplate, setSelectedTemplate] = useState(recommendedTemplateId);
  const [assumptions, setAssumptions] = useState(valuationTemplates[recommendedTemplateId].assumptions);
  const [consensus, setConsensus] = useState(emptyConsensus);
  const [analystTarget, setAnalystTarget] = useState(emptyAnalystTarget);
  const [busy, setBusy] = useState(false);
  const [consensusBusy, setConsensusBusy] = useState(false);

  useEffect(() => {
    applyTemplate(recommendedTemplateId);
  }, [recommendedTemplateId]);

  useEffect(() => {
    let cancelled = false;
    setConsensus(emptyConsensus);
    setAnalystTarget(emptyAnalystTarget);
    async function loadConsensus() {
      try {
        const stored = await api(`/api/valuation/consensus/${ticker}`);
        if (cancelled) return;
        if (!stored) {
          setConsensus(emptyConsensus);
          return;
        }
        setConsensus({
          eps_next_year: stored.eps_next_year ?? "",
          eps_2y: stored.eps_2y ?? "",
          revenue_next_year: stored.revenue_next_year ?? "",
          revenue_2y: stored.revenue_2y ?? "",
          ebitda_next_year: stored.ebitda_next_year ?? "",
          operating_income_next_year: stored.operating_income_next_year ?? "",
          fcf_next_year: stored.fcf_next_year ?? "",
          long_term_eps_growth: stored.long_term_eps_growth !== null && stored.long_term_eps_growth !== undefined ? Number(stored.long_term_eps_growth) * 100 : "",
        });
      } catch (error) {
        if (!cancelled) notify?.(error.message, "error", "读取本地共识失败");
      }
    }
    loadConsensus();
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  function applyTemplate(templateId) {
    const template = valuationTemplates[templateId] || valuationTemplates.conservative;
    setSelectedTemplate(templateId);
    setAssumptions(template.assumptions);
  }

  function applySimplePreset(kind) {
    const presets = {
      conservative: { bear_growth: 1, base_growth: 5, bull_growth: 9, discount_rate: 10, terminal_growth: 2 },
      normal: { bear_growth: 3, base_growth: 9, bull_growth: 15, discount_rate: 9, terminal_growth: 2.5 },
      optimistic: { bear_growth: 6, base_growth: 14, bull_growth: 22, discount_rate: 8.5, terminal_growth: 3 },
    };
    setAssumptions({ ...assumptions, ...presets[kind] });
  }

  async function run() {
    setBusy(true);
    try {
      const pct = (key) => Number(assumptions[key] || 0) / 100;
      const consensusPayload = Object.fromEntries(
        Object.entries(consensus)
          .filter(([, value]) => value !== "" && value !== null && value !== undefined)
          .map(([key, value]) => [key, key.includes("growth") ? Number(value) / 100 : Number(value)])
      );
      const analystPayload = {
        ...(analystTarget.low !== "" ? { analyst_target_low: Number(analystTarget.low) } : {}),
        ...(analystTarget.median !== "" ? { analyst_target_median: Number(analystTarget.median) } : {}),
        ...(analystTarget.high !== "" ? { analyst_target_high: Number(analystTarget.high) } : {}),
        ...(analystTarget.source ? { analyst_target_source: analystTarget.source } : {}),
      };
      const result = await api("/api/valuation/target", {
        method: "POST",
        body: JSON.stringify({
          ticker,
          horizon: "12m",
          consensus: Object.keys(consensusPayload).length ? { ...consensusPayload, source: "manual_consensus" } : null,
          bear: { revenue_cagr_5y: pct("bear_growth") },
          base: {
            revenue_cagr_5y: pct("base_growth"),
            discount_rate: pct("discount_rate"),
            terminal_growth: pct("terminal_growth"),
          },
          bull: { revenue_cagr_5y: pct("bull_growth") },
          use_dynamic_multiples: true,
          use_reverse_dcf: true,
          use_capex_split: true,
          manual_overrides: {
            maintenance_capex_ratio: pct("maintenance_capex_ratio"),
            ...analystPayload,
          },
        }),
      });
      setValuationResult(result);
      notify?.(`${ticker} 目标价已重新计算。`, "success", "估值完成");
    } catch (error) {
      notify?.(error.message, "error", "估值计算失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveConsensus() {
    setConsensusBusy(true);
    try {
      const consensusPayload = Object.fromEntries(
        Object.entries(consensus)
          .filter(([, value]) => value !== "" && value !== null && value !== undefined)
          .map(([key, value]) => [key, key.includes("growth") ? Number(value) / 100 : Number(value)])
      );
      await api(`/api/valuation/consensus/${ticker}`, {
        method: "PUT",
        body: JSON.stringify({ ...consensusPayload, source: "manual_consensus" }),
      });
      notify?.(`${ticker} 的本地共识预期已保存。`, "success", "保存完成");
    } catch (error) {
      notify?.(error.message, "error", "保存共识失败");
    } finally {
      setConsensusBusy(false);
    }
  }

  async function clearConsensus() {
    setConsensusBusy(true);
    try {
      await api(`/api/valuation/consensus/${ticker}`, { method: "DELETE" });
      setConsensus(emptyConsensus);
      notify?.(`${ticker} 的本地共识预期已清空。`, "success", "已清空");
    } catch (error) {
      notify?.(error.message, "error", "清空共识失败");
    } finally {
      setConsensusBusy(false);
    }
  }

  const result = valuationResult || companyData?.valuation;
  function exportMarkdown() {
    if (!result) return;
    const filename = `${ticker}-valuation-${new Date().toISOString().slice(0, 10)}.md`;
    const markdown = buildValuationMarkdown({ ticker, companyData, result });
    downloadMarkdown(filename, markdown);
    notify?.(`${filename} 已生成。`, "success", "导出完成");
  }

  return (
    <section className="page-section">
      <div className="reading-header">
        <div>
          <p className="eyebrow">目标价计算器</p>
          <h2>先看分层目标价区间</h2>
          <p>默认把内在价值、市场倍数和外部目标价拆开解释。你只需要关心：当前价落在哪层假设里。</p>
        </div>
        <div className="header-actions">
          <button onClick={run} disabled={busy}><LineChart size={16} />重新计算</button>
          <button className="ghost" onClick={() => result && saveSnapshot(result)}><Save size={16} />保存快照</button>
          <button className="ghost" disabled={!result} onClick={exportMarkdown}><Download size={16} />导出 Markdown</button>
        </div>
      </div>
      {result ? <ValuationResult result={result} /> : <EmptyState title="还没有估值结果" text="点击重新计算，或先刷新公司数据。" />}
      <div className="panel simple-input-panel">
        <div className="simple-section-heading">
          <div>
            <span className="eyebrow">想试试不同情况</span>
            <h3>改几个容易理解的假设</h3>
          </div>
          <button onClick={run} disabled={busy}><LineChart size={16} />按这些假设重算</button>
        </div>
        <p className="muted">不知道怎么填就直接用“正常”。这里不是预测未来，而是看估值对未来增长和利润的敏感程度。</p>
        <div className="simple-preset-row">
          <button className="ghost" onClick={() => applySimplePreset("conservative")}>保守一点</button>
          <button className="ghost" onClick={() => applySimplePreset("normal")}>正常情况</button>
          <button className="ghost" onClick={() => applySimplePreset("optimistic")}>乐观一点</button>
        </div>
        <div className="simple-assumption-grid">
          {[
            ["base_growth", "未来收入增长", "未来 5 年每年收入大概增长多少。"],
            ["discount_rate", "你要求的回报", "越高代表你越保守，合理价会更低。"],
            ["terminal_growth", "长期稳定增长", "公司成熟后还能慢慢增长多少。"],
            ["maintenance_capex_ratio", "维持生意要花的钱", "比例越高，能留给股东的钱越少。"],
          ].map(([key, label, help]) => (
            <label key={key}>
              <span>{label}</span>
              <input type="number" value={assumptions[key]} onChange={(event) => setAssumptions({ ...assumptions, [key]: event.target.value })} />
              <small>{help}</small>
            </label>
          ))}
        </div>
        <div className="template-strip">
          <label>
            <span>公司类型模板</span>
            <select value={selectedTemplate} onChange={(event) => applyTemplate(event.target.value)}>
              {Object.entries(valuationTemplates).map(([key, template]) => (
                <option value={key} key={key}>{template.label}</option>
              ))}
            </select>
          </label>
          <div>
            <strong>{valuationTemplates[selectedTemplate]?.label}</strong>
            <p>{valuationTemplates[selectedTemplate]?.description}</p>
            {selectedTemplate === recommendedTemplateId ? <small>系统根据公司行业和业务描述自动推荐此模板。</small> : <small>你正在使用手动选择的模板。</small>}
          </div>
        </div>
        <details className="formula-box soft-details">
          <summary>高级设置：我知道 EPS、收入、EBITDA、FCF 或分析师目标价</summary>
          <p className="muted">这些数据如果你从券商、财报或分析师共识里看到，可以手动填。保存后会进入本地共识表；留空时系统会用历史数据估算，并标注“非市场共识”。</p>
          <div className="consensus-actions">
            <button type="button" onClick={saveConsensus} disabled={consensusBusy}>保存本地共识</button>
            <button type="button" className="ghost" onClick={clearConsensus} disabled={consensusBusy}>清空本地共识</button>
          </div>
          <div className="assumption-grid">
            {[
              ["eps_next_year", "明年每股收益 EPS $"],
              ["eps_2y", "后年每股收益 EPS $"],
              ["revenue_next_year", "明年收入 Revenue $"],
              ["revenue_2y", "后年收入 Revenue $"],
              ["ebitda_next_year", "明年 EBITDA $"],
              ["operating_income_next_year", "明年经营利润 $"],
              ["fcf_next_year", "明年自由现金流 FCF $"],
              ["long_term_eps_growth", "长期 EPS 增长 %"],
            ].map(([key, label]) => (
              <label key={key}>
                <span>{label}</span>
                <input type="number" value={consensus[key]} onChange={(event) => setConsensus({ ...consensus, [key]: event.target.value })} placeholder="留空使用系统估算" />
              </label>
            ))}
          </div>
          <div className="analyst-target-box">
            <div>
              <span className="eyebrow">外部目标价</span>
              <h4>可选：把分析师目标价作为单独一层</h4>
              <p>这里不会覆盖系统估值，只会按后端权重混入综合区间。</p>
            </div>
            <div className="assumption-grid">
              {[
                ["low", "目标价低位 $"],
                ["median", "目标价中位数 $"],
                ["high", "目标价高位 $"],
                ["source", "来源备注"],
              ].map(([key, label]) => (
                <label key={key}>
                  <span>{label}</span>
                  <input
                    type={key === "source" ? "text" : "number"}
                    value={analystTarget[key]}
                    onChange={(event) => setAnalystTarget({ ...analystTarget, [key]: event.target.value })}
                    placeholder={key === "source" ? "例如券商共识 / 手动整理" : "留空不使用"}
                  />
                </label>
              ))}
            </div>
          </div>
          <div className="assumption-grid">
            {[
              ["bear_growth", "保守收入增长 %"],
              ["bull_growth", "乐观收入增长 %"],
            ].map(([key, label]) => (
              <label key={key}>
                <span>{label}</span>
                <input type="number" value={assumptions[key]} onChange={(event) => setAssumptions({ ...assumptions, [key]: event.target.value })} />
              </label>
            ))}
          </div>
        </details>
      </div>
    </section>
  );
}
