import { useEffect, useMemo, useState } from "react";
import { Download, LineChart, Save } from "lucide-react";
import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { inferValuationTemplate, valuationTemplates } from "../data/valuationTemplates";
import { buildValuationMarkdown, downloadMarkdown } from "../utils/exportMarkdown";
import { ValuationResult } from "./ValuationResult";

export function ValuationModel({ ticker, companyData, valuationResult, setValuationResult, saveSnapshot, notify }) {
  const recommendedTemplateId = useMemo(
    () => inferValuationTemplate(companyData?.company || { ticker }),
    [companyData?.company, ticker]
  );
  const [selectedTemplate, setSelectedTemplate] = useState(recommendedTemplateId);
  const [assumptions, setAssumptions] = useState(valuationTemplates[recommendedTemplateId].assumptions);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    applyTemplate(recommendedTemplateId);
  }, [recommendedTemplateId]);

  function applyTemplate(templateId) {
    const template = valuationTemplates[templateId] || valuationTemplates.conservative;
    setSelectedTemplate(templateId);
    setAssumptions(template.assumptions);
  }

  async function run() {
    setBusy(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(assumptions).map(([key, value]) => [
          key,
          ["quality_score"].includes(key) ? Number(value) : Number(value) / 100,
        ])
      );
      const result = await api("/api/valuation/run", {
        method: "POST",
        body: JSON.stringify({ ticker, assumptions: payload }),
      });
      setValuationResult(result);
      notify?.(`${ticker} 估值已重新计算。`, "success", "估值完成");
    } catch (error) {
      notify?.(error.message, "error", "估值计算失败");
    } finally {
      setBusy(false);
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
          <p className="eyebrow">简化模式</p>
          <h2>先看估值结论，再决定要不要研究公式</h2>
          <p>你可以只调几个关键假设。复杂公式默认收起，但每个结论都能追溯。</p>
        </div>
        <div className="header-actions">
          <button onClick={run} disabled={busy}><LineChart size={16} />重新计算</button>
          <button className="ghost" onClick={() => result && saveSnapshot(result)}><Save size={16} />保存快照</button>
          <button className="ghost" disabled={!result} onClick={exportMarkdown}><Download size={16} />导出 Markdown</button>
        </div>
      </div>
      {result ? <ValuationResult result={result} /> : <EmptyState title="还没有估值结果" text="点击重新计算，或先刷新公司数据。" />}
      <div className="panel">
        <h3>关键假设</h3>
        <p className="muted">不用追求精确。这里的作用是看：结论对哪些假设最敏感。</p>
        <div className="template-strip">
          <label>
            <span>估值模板</span>
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
        <div className="assumption-grid">
          {[
            ["base_growth", "基准增长率 %"],
            ["bear_growth", "熊市增长率 %"],
            ["bull_growth", "牛市增长率 %"],
            ["discount_rate", "折现率 %"],
            ["terminal_growth", "终值增长率 %"],
            ["risk_discount", "风险折扣 %"],
            ["maintenance_capex_ratio", "维护性 CAPEX %"],
            ["sbc_adjustment_ratio", "SBC 调整 %"],
            ["quality_score", "品质分"],
          ].map(([key, label]) => (
            <label key={key}>
              <span>{label}</span>
              <input type="number" value={assumptions[key]} onChange={(event) => setAssumptions({ ...assumptions, [key]: event.target.value })} />
            </label>
          ))}
        </div>
      </div>
    </section>
  );
}
