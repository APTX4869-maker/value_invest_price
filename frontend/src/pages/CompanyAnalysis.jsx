import { ArrowRight, BarChart3, ExternalLink, FileClock, FileSearch, NotebookPen, RefreshCcw, Save, ShieldCheck, SlidersHorizontal, Undo2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "../components/Badge";
import { EmptyState } from "../components/EmptyState";
import { GuidedMetric } from "../components/GuidedMetric";
import { Stat } from "../components/Stat";
import { TrendChart } from "../components/TrendChart";
import { metricGuides } from "../data/metricGuides";
import { formatMoney, formatPercent } from "../utils/formatters";

const TABS = [
  { id: "overview", label: "概览" },
  { id: "business", label: "业务与护城河" },
  { id: "financials", label: "财务质量" },
  { id: "sec", label: "SEC 证据" },
  { id: "valuation", label: "估值" },
  { id: "peers", label: "同行比较" },
  { id: "memo", label: "投资备忘录" },
  { id: "history", label: "历史复盘" },
];

function confidenceValue(confidence) {
  if (!confidence) return "-";
  return typeof confidence === "string" ? confidence : `${confidence.score}/100 · ${confidence.level}`;
}

function conclusionTone(conclusion) {
  if (conclusion === "偏贵" || conclusion === "明显高估") return "warn";
  if (!conclusion || conclusion === "不确定") return "neutral";
  return "good";
}

function DossierCard({ title, children }) {
  return (
    <article className="dossier-card">
      <strong>{title}</strong>
      <div>{children}</div>
    </article>
  );
}

function DraftList({ title, items = [] }) {
  return (
    <div>
      <strong>{title}</strong>
      {items.length ? (
        <ul>
          {items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}
        </ul>
      ) : (
        <p>待确认</p>
      )}
    </div>
  );
}

function DraftTextarea({ label, value, onChange }) {
  return (
    <label>
      <span>{label}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} placeholder="每行一条" />
    </label>
  );
}

function draftToForm(draft = {}) {
  return {
    business_model: draft.business_model || "",
    growth_drivers: (draft.growth_drivers || []).join("\n"),
    moat_sources: (draft.moat_sources || []).join("\n"),
    competition: (draft.competition || []).join("\n"),
    key_risks: (draft.key_risks || []).join("\n"),
    financial_quality_notes: (draft.financial_quality_notes || []).join("\n"),
    follow_up_questions: (draft.follow_up_questions || []).join("\n"),
  };
}

function formToDraft(form, original = {}) {
  const lines = (text) => String(text || "").split("\n").map((item) => item.trim()).filter(Boolean);
  return {
    ...original,
    business_model: form.business_model,
    growth_drivers: lines(form.growth_drivers),
    moat_sources: lines(form.moat_sources),
    competition: lines(form.competition),
    key_risks: lines(form.key_risks),
    financial_quality_notes: lines(form.financial_quality_notes),
    follow_up_questions: lines(form.follow_up_questions),
  };
}

export function CompanyAnalysis({ companyData, queueItem, memo, secPackage, researchDrafts = [], snapshots = [], peerComparison, setPage, refreshCompany, refreshSecPackage, generateSecDraft, updateResearchDraft, savePriceOverride }) {
  const [priceDraft, setPriceDraft] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [editingDraft, setEditingDraft] = useState(false);
  const [draftForm, setDraftForm] = useState(draftToForm());
  const company = companyData?.company;
  const facts = companyData?.facts;
  const valuation = companyData?.valuation;

  useEffect(() => {
    setPriceDraft(facts?.price_is_overridden && facts?.price ? String(facts.price) : "");
  }, [facts?.price, facts?.price_is_overridden]);

  useEffect(() => {
    setEditingDraft(false);
    setDraftForm(draftToForm(researchDrafts[0]?.draft || {}));
  }, [researchDrafts[0]?.id]);

  if (!company) {
    return <EmptyState title="还没有公司档案" text="请先在研究队列选择公司，或者从发现雷达加入一个候选。"/>;
  }

  const segments = company.segments || [];
  const watchPoints = valuation?.plain_language?.watch || valuation?.data_quality?.warnings || [];
  const memoConclusion = memo?.conclusion || "不确定";
  const confirmedSummary = company.research_summary || {};
  const secPackages = secPackage?.packages || [];
  const latestDraftItem = researchDrafts[0] || null;
  const latestDraft = latestDraftItem?.draft || null;

  return (
    <section className="page-section dossier-page">
      <div className="reading-header">
        <div>
          <p className="eyebrow">{company.industry || company.sector || "未分类"}</p>
          <h2>{company.name}</h2>
          <p>{company.description || `${company.ticker} 的公司画像还不完整，刷新后会尽量从 SEC 和内置业务画像补充。`}</p>
        </div>
        <div className="header-actions">
          <button className="ghost" onClick={() => setPage("notes")}><NotebookPen size={16} />写备忘录</button>
          <button onClick={() => refreshCompany(company.ticker)}><RefreshCcw size={16} />刷新研究包</button>
        </div>
      </div>

      <div className="profile-meta">
        <Badge>{company.ticker}</Badge>
        <Badge>{queueItem?.status_label || "未入队"}</Badge>
        <Badge>{company.sector || "行业待补充"}</Badge>
        <Badge>{company.profile_source || "基础资料"}</Badge>
      </div>

      <div className="dossier-onepager panel">
        <div>
          <p className="eyebrow">一页纸结论</p>
          <h3>{valuation?.judgement || memoConclusion}</h3>
          <p>
            {valuation
              ? `当前价格约 ${formatMoney(valuation.current_price, false)}，合理价值中枢约 ${formatMoney(valuation.fair_value_center, false)}，估值可信度 ${confidenceValue(valuation.confidence)}。`
              : "还没有足够财务数据。先刷新公司数据，再判断便宜、合理、偏贵还是不确定。"}
          </p>
          <p className="queue-next"><strong>下一步</strong><span>{queueItem?.next_action || "补齐财务数据、业务护城河和结构化 memo。"}</span></p>
        </div>
        <div className="mini-stats">
          <Stat label="当前判断" value={valuation?.judgement || memoConclusion} tone="decision" />
          <Stat label="当前价" value={formatMoney(valuation?.current_price, false)} />
          <Stat label="合理中枢" value={formatMoney(valuation?.fair_value_center, false)} />
          <Stat label="可信度" value={confidenceValue(valuation?.confidence)} />
        </div>
      </div>

      <div className="dossier-tabs">
        {TABS.map((tab) => (
          <button key={tab.id} className={activeTab === tab.id ? "active" : ""} onClick={() => setActiveTab(tab.id)}>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "overview" ? (
        <>
          <div className="dossier-card-grid">
            <DossierCard title="业务与护城河">
              <p>{confirmedSummary.business_model || company.business_overview || "待补业务模式、收入结构和护城河证据。"}</p>
            </DossierCard>
            <DossierCard title="财务质量">
              <p>
                {confirmedSummary.financial_quality_notes?.length
                  ? confirmedSummary.financial_quality_notes.join(" / ")
                  : facts
                  ? `营收 ${formatMoney(facts.revenue)}，OCF ${formatMoney(facts.ocf)}，CAPEX ${formatMoney(facts.capex)}。`
                  : "待刷新财务数据。"}
              </p>
            </DossierCard>
            <DossierCard title="关键风险">
              <p>{confirmedSummary.key_risks?.length ? confirmedSummary.key_risks.join(" / ") : watchPoints.length ? watchPoints.join(" / ") : "待补竞争、监管、周期、技术替代和估值假设风险。"}</p>
            </DossierCard>
          </div>
          {valuation?.plain_language?.watch?.length ? (
            <div className="tips-bar">
              <strong>我应该看什么</strong>
              <span>{valuation.plain_language.watch.join(" / ")}</span>
            </div>
          ) : null}
        </>
      ) : null}

      {activeTab === "business" ? (
        <div className="two-column">
          <div className="panel">
            <h3>业务介绍</h3>
            <p className="business-copy">{confirmedSummary.business_model || company.business_overview || "这家公司还没有详细业务介绍。后续可以通过年报解析或手动编辑补充。"}</p>
            {confirmedSummary.moat_sources?.length ? (
              <div className="confirmed-summary-list">
                <strong>已确认护城河线索</strong>
                <ul>{confirmedSummary.moat_sources.map((item, index) => <li key={`moat-${index}`}>{item}</li>)}</ul>
              </div>
            ) : null}
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
      ) : null}

      {activeTab === "financials" ? (
        <>
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
                  <input type="number" step="0.01" placeholder="例如 185.50" value={priceDraft} onChange={(event) => setPriceDraft(event.target.value)} />
                </label>
                <button onClick={() => savePriceOverride(company.ticker, priceDraft)}><Save size={16} />保存覆盖价</button>
                <button className="ghost" onClick={() => savePriceOverride(company.ticker, null)}><Undo2 size={16} />恢复市场价</button>
              </div>
            </div>
          ) : (
            <div className="empty-state compact">
              <ShieldCheck size={24} />
              <h3>这家公司还没有可用财务数据</h3>
              <p>如果这是公司股票，点击刷新会尝试从 SEC 拉取财报。若它是 ETF、基金或 ticker 拼写错误，当前估值模型无法直接分析。</p>
              <button onClick={() => refreshCompany(company.ticker)}><RefreshCcw size={16} />刷新数据</button>
            </div>
          )}
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
          </div>
        </>
      ) : null}

      {activeTab === "sec" ? (
        <div className="sec-evidence-layout">
          <div className="panel sec-evidence-intro">
            <FileSearch size={28} />
            <div>
              <h3>SEC 研究证据</h3>
              <p>
                从最新 10-K / 10-Q 里提取 Business、Risk Factors、MD&A 等章节。这里是后续 LLM 初稿的证据底座，任何结论都应该能回到 filing 来源。
              </p>
            </div>
            <div className="sec-evidence-actions">
              <button onClick={() => refreshSecPackage(company.ticker)}><RefreshCcw size={16} />刷新 SEC 研究包</button>
              <button className="ghost" onClick={() => generateSecDraft(company.ticker)}>生成 AI 初稿</button>
            </div>
          </div>

          {latestDraft ? (
            <article className="panel ai-draft-panel">
              <div className="panel-heading">
                <div>
                  <h3>AI 初稿 · {latestDraftItem.status === "confirmed" ? "已确认" : latestDraftItem.status === "rejected" ? "已驳回" : "待确认"}</h3>
                  <p className="muted">只基于已提取的 SEC 证据生成。确认前不要把它当作最终结论。</p>
                </div>
                <div className="draft-actions">
                  <Badge tone={latestDraftItem.status === "confirmed" ? "good" : latestDraftItem.status === "rejected" ? "neutral" : "warn"}>{latestDraftItem.status}</Badge>
                  <button className="ghost" onClick={() => { setDraftForm(draftToForm(latestDraft)); setEditingDraft(!editingDraft); }}>{editingDraft ? "取消编辑" : "编辑"}</button>
                  <button className="ghost" onClick={() => updateResearchDraft(latestDraftItem.id, { status: "confirmed" })}>确认</button>
                  <button className="danger" onClick={() => updateResearchDraft(latestDraftItem.id, { status: "rejected" })}>驳回</button>
                </div>
              </div>
              {editingDraft ? (
                <div className="ai-draft-editor">
                  <label className="full">
                    <span>业务模式</span>
                    <textarea value={draftForm.business_model} onChange={(event) => setDraftForm({ ...draftForm, business_model: event.target.value })} />
                  </label>
                  <DraftTextarea label="增长驱动" value={draftForm.growth_drivers} onChange={(value) => setDraftForm({ ...draftForm, growth_drivers: value })} />
                  <DraftTextarea label="护城河来源" value={draftForm.moat_sources} onChange={(value) => setDraftForm({ ...draftForm, moat_sources: value })} />
                  <DraftTextarea label="竞争格局" value={draftForm.competition} onChange={(value) => setDraftForm({ ...draftForm, competition: value })} />
                  <DraftTextarea label="关键风险" value={draftForm.key_risks} onChange={(value) => setDraftForm({ ...draftForm, key_risks: value })} />
                  <DraftTextarea label="财务质量观察" value={draftForm.financial_quality_notes} onChange={(value) => setDraftForm({ ...draftForm, financial_quality_notes: value })} />
                  <DraftTextarea label="继续验证" value={draftForm.follow_up_questions} onChange={(value) => setDraftForm({ ...draftForm, follow_up_questions: value })} />
                  <div className="draft-editor-actions">
                    <button onClick={() => { updateResearchDraft(latestDraftItem.id, { status: "edited", draft: formToDraft(draftForm, latestDraft) }); setEditingDraft(false); }}>保存编辑</button>
                  </div>
                </div>
              ) : (
                <div className="ai-draft-grid">
                  <div>
                    <strong>业务模式</strong>
                    <p>{latestDraft.business_model || "待确认"}</p>
                  </div>
                  <DraftList title="增长驱动" items={latestDraft.growth_drivers} />
                  <DraftList title="护城河来源" items={latestDraft.moat_sources} />
                  <DraftList title="竞争格局" items={latestDraft.competition} />
                  <DraftList title="关键风险" items={latestDraft.key_risks} />
                  <DraftList title="继续验证" items={latestDraft.follow_up_questions} />
                </div>
              )}
              <div className="ai-citation-panel">
                <div>
                  <strong>来源文件</strong>
                  <p>{latestDraftItem.source_accessions?.length ? latestDraftItem.source_accessions.join(" / ") : "未记录 accession"}</p>
                </div>
                <div>
                  <strong>引用线索</strong>
                  {latestDraft.citations?.length ? (
                    <ul>
                      {latestDraft.citations.slice(0, 8).map((citation, index) => (
                        <li key={`citation-${index}`}>
                          <span>{citation.claim || "研究结论"}</span>
                          <small>{citation.source || "来源待确认"}</small>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>模型没有返回结构化引用，确认前需要人工复核 SEC 证据。</p>
                  )}
                </div>
              </div>
            </article>
          ) : null}

          {secPackages.length ? (
            <div className="sec-package-list">
              {secPackages.map((packageItem) => (
                <article className="panel sec-package" key={packageItem.filing.accession_no}>
                  <div className="panel-heading">
                    <div>
                      <h3>{packageItem.filing.form} · {packageItem.filing.filing_date || packageItem.filing.report_date}</h3>
                      <p className="muted">Accession {packageItem.filing.accession_no}</p>
                    </div>
                    <a className="text-link" href={packageItem.filing.document_url} target="_blank" rel="noreferrer">
                      <ExternalLink size={15} />SEC 原文
                    </a>
                  </div>
                  <div className="mini-stats">
                    <Stat label="已提取章节" value={`${packageItem.quality?.found_count || 0}/${packageItem.quality?.total || 0}`} />
                    <Stat label="文档类型" value={packageItem.filing.form} />
                    <Stat label="提取时间" value={packageItem.fetched_at ? packageItem.fetched_at.slice(0, 10) : "-"} />
                  </div>
                  <div className="sec-section-grid">
                    {(packageItem.sections || []).map((section) => (
                      <details className="sec-section" key={`${packageItem.filing.accession_no}-${section.key}`} open={section.status === "found"}>
                        <summary>
                          <span>{section.title}</span>
                          <Badge tone={section.status === "found" ? "good" : "neutral"}>{section.status === "found" ? `${section.word_count} words` : "未提取"}</Badge>
                        </summary>
                        {section.status === "found" ? (
                          <>
                            <p>{section.excerpt}</p>
                            <small>{section.citation}</small>
                          </>
                        ) : (
                          <p className="plain-callout">这个章节没有在当前 filing 中稳定识别出来，建议打开 SEC 原文人工确认。</p>
                        )}
                      </details>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="还没有 SEC 研究包" text="点击刷新 SEC 研究包后，系统会抓取最近 10-K / 10-Q 并抽取关键章节。" />
          )}
        </div>
      ) : null}

      {activeTab === "valuation" ? (
        <div className="panel dossier-action-panel">
          <SlidersHorizontal size={26} />
          <div>
            <h3>估值判断</h3>
            <p>{valuation ? `当前判断 ${valuation.judgement}，合理区间约 ${formatMoney(valuation.fair_value_range.low, false)} - ${formatMoney(valuation.fair_value_range.high, false)}。` : "先刷新公司财务数据，再运行分层目标价估值。"}</p>
          </div>
          <button onClick={() => setPage("valuation")}><ArrowRight size={16} />打开估值模型</button>
        </div>
      ) : null}

      {activeTab === "peers" ? (
        <div className="panel dossier-action-panel">
          <BarChart3 size={26} />
          <div>
            <h3>同行比较</h3>
            <p>{peerComparison?.summary?.headline || "选择同行并刷新后，这里会展示相对估值结论。"}</p>
          </div>
          <button onClick={() => setPage("peers")}><ArrowRight size={16} />打开同行比较</button>
        </div>
      ) : null}

      {activeTab === "memo" ? (
        <div className="panel dossier-action-panel">
          <NotebookPen size={26} />
          <div>
            <h3>结构化投资备忘录</h3>
            <p>当前 memo 结论：{memoConclusion}。核心假设 {memo?.thesis?.length || 0} 条，复盘触发条件 {memo?.review_triggers?.length || 0} 条。</p>
          </div>
          <button onClick={() => setPage("notes")}><ArrowRight size={16} />编辑备忘录</button>
        </div>
      ) : null}

      {activeTab === "history" ? (
        <div className="panel">
          <div className="panel-heading">
            <h3>历史复盘</h3>
            <button className="ghost" onClick={() => setPage("history")}><FileClock size={16} />打开历史页</button>
          </div>
          <div className="snapshot-list">
            {snapshots.slice(0, 3).map((snapshot) => (
              <div key={snapshot.id} className="snapshot">
                <strong>{snapshot.title}</strong>
                <span>{snapshot.created_at}</span>
                <p>{snapshot.result?.judgement || snapshot.result?.plain_language?.headline || "估值快照"}</p>
              </div>
            ))}
            {!snapshots.length ? <p className="plain-callout">还没有估值快照。运行估值后保存快照，后续可以对比判断变化。</p> : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
