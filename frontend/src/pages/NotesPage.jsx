import { useEffect, useState } from "react";
import { Save, Search } from "lucide-react";

export function NotesPage({ ticker, note, saveNote }) {
  const [content, setContent] = useState(note?.content || "");
  const [query, setQuery] = useState("");
  useEffect(() => setContent(note?.content || ""), [note?.content]);
  const normalizedQuery = query.trim().toLowerCase();
  const lines = content.split("\n");
  const matchCount = normalizedQuery
    ? lines.filter((line) => line.toLowerCase().includes(normalizedQuery)).length
    : 0;

  return (
    <section className="page-section">
      <div className="reading-header">
        <div>
          <p className="eyebrow">复盘比预测重要</p>
          <h2>{ticker} 研究笔记</h2>
          <p>笔记模板会逼你回答三个问题：为什么看、价格在赌什么、我可能错在哪里。</p>
        </div>
        <button onClick={() => saveNote(content)}><Save size={16} />保存笔记</button>
      </div>
      <div className="search-strip">
        <Search size={17} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索笔记关键词，例如 风险、买入、财报"
        />
        <span>{normalizedQuery ? `${matchCount} 行匹配` : "输入关键词后会在右侧预览高亮"}</span>
      </div>
      <div className="notes-layout">
        <textarea value={content} onChange={(event) => setContent(event.target.value)} />
        <div className="note-preview">
          {lines.map((line, index) => {
            const highlighted = <HighlightedLine line={line || " "} query={normalizedQuery} />;
            if (line.startsWith("## ")) return <h3 key={index}><HighlightedLine line={line.replace("## ", "")} query={normalizedQuery} /></h3>;
            if (line.startsWith("- ")) return <p key={index} className="bullet-preview">{highlighted}</p>;
            return <p key={index}>{highlighted}</p>;
          })}
        </div>
      </div>
    </section>
  );
}

function HighlightedLine({ line, query }) {
  if (!query) return line;
  const lower = line.toLowerCase();
  const parts = [];
  let start = 0;
  let index = lower.indexOf(query);
  while (index !== -1) {
    if (index > start) parts.push(line.slice(start, index));
    parts.push(<mark key={`${index}-${parts.length}`}>{line.slice(index, index + query.length)}</mark>);
    start = index + query.length;
    index = lower.indexOf(query, start);
  }
  if (start < line.length) parts.push(line.slice(start));
  return parts.length ? parts : line;
}
