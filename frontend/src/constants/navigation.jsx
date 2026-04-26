import {
  BarChart3,
  BookOpen,
  FileClock,
  NotebookPen,
  Search,
  SlidersHorizontal,
} from "lucide-react";

export const pages = [
  { id: "watchlist", label: "观察池", icon: Search },
  { id: "company", label: "公司分析", icon: BookOpen },
  { id: "valuation", label: "估值模型", icon: SlidersHorizontal },
  { id: "peers", label: "同行比较", icon: BarChart3 },
  { id: "notes", label: "研究笔记", icon: NotebookPen },
  { id: "history", label: "历史与设置", icon: FileClock },
];
