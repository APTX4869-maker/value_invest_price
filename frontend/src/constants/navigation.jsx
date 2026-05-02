import {
  BarChart3,
  BookOpen,
  Compass,
  FileClock,
  ListChecks,
  NotebookPen,
  SlidersHorizontal,
} from "lucide-react";

export const pages = [
  { id: "discovery", label: "发现雷达", icon: Compass },
  { id: "watchlist", label: "研究队列", icon: ListChecks },
  { id: "company", label: "公司档案", icon: BookOpen },
  { id: "valuation", label: "估值模型", icon: SlidersHorizontal },
  { id: "peers", label: "同行比较", icon: BarChart3 },
  { id: "notes", label: "投资备忘录", icon: NotebookPen },
  { id: "history", label: "历史复盘", icon: FileClock },
];
