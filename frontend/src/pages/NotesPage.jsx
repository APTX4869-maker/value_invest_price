import { Clock3, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "../components/Badge";

const CONCLUSIONS = ["便宜", "合理", "偏贵", "不确定"];

function normalizeMemo(memo, note) {
  return {
    conclusion: memo?.conclusion || "不确定",
    attention_reason: memo?.attention_reason || "",
    thesis: memo?.thesis?.length ? memo.thesis : [""],
    business_moat: memo?.business_moat || "",
    financial_quality: memo?.financial_quality || "",
    valuation_view: memo?.valuation_view || "",
    bear_case: memo?.bear_case || "",
    review_triggers: memo?.review_triggers?.length ? memo.review_triggers : [""],
    free_notes: memo?.free_notes || note?.content || "",
    snapshot_id: memo?.snapshot_id || null,
  };
}

function DynamicList({ label, items, setItems, placeholder }) {
  function updateItem(index, value) {
    setItems(items.map((item, itemIndex) => (itemIndex === index ? value : item)));
  }

  function removeItem(index) {
    const next = items.filter((_, itemIndex) => itemIndex !== index);
    setItems(next.length ? next : [""]);
  }

  return (
    <div className="memo-field full">
      <div className="memo-field-head">
        <span>{label}</span>
        <button className="ghost icon-button" type="button" onClick={() => setItems([...items, ""])} title="添加一条">
          <Plus size={15} />
        </button>
      </div>
      <div className="memo-list-editor">
        {items.map((item, index) => (
          <div key={index} className="memo-list-row">
            <input value={item} onChange={(event) => updateItem(index, event.target.value)} placeholder={placeholder} />
            <button className="danger icon-button" type="button" onClick={() => removeItem(index)} title="删除">
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export function NotesPage({ ticker, note, memo, memoHistory = [], saveMemo }) {
  const [draft, setDraft] = useState(() => normalizeMemo(memo, note));

  useEffect(() => {
    setDraft(normalizeMemo(memo, note));
  }, [memo?.updated_at, note?.updated_at, ticker]);

  function setField(key, value) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function save() {
    saveMemo({
      ...draft,
      thesis: draft.thesis.map((item) => item.trim()).filter(Boolean),
      review_triggers: draft.review_triggers.map((item) => item.trim()).filter(Boolean),
    });
  }

  return (
    <section className="page-section">
      <div className="reading-header">
        <div>
          <p className="eyebrow">结论必须能复盘</p>
          <h2>{ticker} 投资备忘录</h2>
          <p>把“为什么关注、核心假设、我可能错在哪里、什么时候复盘”结构化保存，后续判断变化才有上下文。</p>
        </div>
        <button onClick={save}><Save size={16} />保存备忘录</button>
      </div>

      <div className="memo-layout">
        <div className="memo-form panel">
          <label className="memo-field">
            <span>当前结论</span>
            <select value={draft.conclusion} onChange={(event) => setField("conclusion", event.target.value)}>
              {CONCLUSIONS.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>

          <label className="memo-field full">
            <span>为什么关注</span>
            <textarea value={draft.attention_reason} onChange={(event) => setField("attention_reason", event.target.value)} placeholder="来自发现雷达的入队理由，或者你自己的研究动机。" />
          </label>

          <DynamicList
            label="核心投资假设"
            items={draft.thesis}
            setItems={(items) => setField("thesis", items)}
            placeholder="例如：云业务利润率继续改善。"
          />

          <label className="memo-field full">
            <span>业务与护城河判断</span>
            <textarea value={draft.business_moat} onChange={(event) => setField("business_moat", event.target.value)} placeholder="公司怎么赚钱，护城河来自哪里，证据是什么。" />
          </label>

          <label className="memo-field full">
            <span>财务质量判断</span>
            <textarea value={draft.financial_quality} onChange={(event) => setField("financial_quality", event.target.value)} placeholder="增长、利润率、FCF、CAPEX、SBC、负债质量。" />
          </label>

          <label className="memo-field full">
            <span>估值判断</span>
            <textarea value={draft.valuation_view} onChange={(event) => setField("valuation_view", event.target.value)} placeholder="当前价格隐含什么预期，哪些假设最敏感。" />
          </label>

          <label className="memo-field full">
            <span>我可能错在哪里</span>
            <textarea value={draft.bear_case} onChange={(event) => setField("bear_case", event.target.value)} placeholder="写反证，不写口号。什么情况出现说明原假设错了？" />
          </label>

          <DynamicList
            label="复盘触发条件"
            items={draft.review_triggers}
            setItems={(items) => setField("review_triggers", items)}
            placeholder="例如：下一季 FCF margin 低于 15%。"
          />

          <label className="memo-field full">
            <span>自由补充</span>
            <textarea value={draft.free_notes} onChange={(event) => setField("free_notes", event.target.value)} placeholder="保留 Markdown 式补充记录。" />
          </label>
        </div>

        <aside className="memo-preview panel">
          <div className="panel-heading">
            <h3>备忘录预览</h3>
            <Badge tone={draft.conclusion === "偏贵" ? "warn" : draft.conclusion === "不确定" ? "neutral" : "good"}>{draft.conclusion}</Badge>
          </div>
          <section>
            <strong>为什么关注</strong>
            <p>{draft.attention_reason || "待补充"}</p>
          </section>
          <section>
            <strong>核心假设</strong>
            <ul>{draft.thesis.filter(Boolean).map((item, index) => <li key={index}>{item}</li>)}</ul>
          </section>
          <section>
            <strong>我可能错在哪里</strong>
            <p>{draft.bear_case || "待补充"}</p>
          </section>
          <section>
            <strong>复盘触发</strong>
            <ul>{draft.review_triggers.filter(Boolean).map((item, index) => <li key={index}>{item}</li>)}</ul>
          </section>
          <section>
            <strong><Clock3 size={15} /> 版本记录</strong>
            {memoHistory.length ? (
              <div className="memo-version-list">
                {memoHistory.slice(0, 6).map((version) => (
                  <div className="memo-version-row" key={version.id}>
                    <span>{memoSourceLabel(version.source)}</span>
                    <small>{new Date(version.created_at).toLocaleString()}</small>
                    <p>{version.memo?.conclusion || "不确定"} · {version.memo?.attention_reason || "暂无关注理由"}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p>保存后会自动留下版本。</p>
            )}
          </section>
        </aside>
      </div>
    </section>
  );
}

function memoSourceLabel(source) {
  if (source === "ai_confirmed_draft") return "AI 初稿确认";
  return "手动保存";
}
