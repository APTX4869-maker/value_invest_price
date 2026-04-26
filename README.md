# 本地美股估值研究系统

一个面向个人学习和投资分析的本地网站。

它不是交易工具，也不是“给出目标价”的黑箱，而是把我们整理出来的估值方法落成一个可运行的研究工作台：先给白话结论，再展开数据、假设、公式和历史快照，尽量降低非专业投资者的理解成本。

## 现在能做什么

- `观察池`：管理关注公司，查看当前价格、综合合理区间、估值判断和品质分。
- `公司分析`：查看公司业务介绍、营收结构、核心财务、价格校验和多年财务趋势图。
- `估值模型`：运行 `V3.0 multi-model valuation`，综合 DCF、Forward P/E、PEG、EV/Revenue、EV/EBITDA、FCF Yield，输出保守区间、市场合理区间、乐观成长区间和保守买入区。
- `同行比较`：维护同行列表，用同一套估值口径对比相对贵便宜、质量分和现金流收益率。
- `研究笔记`：保存 Markdown 笔记，并支持关键词搜索和高亮。
- `历史与设置`：保存估值快照、做快照对比、维护免费数据源设置。
- `导出`：把单家公司估值分析导出为 Markdown。

## 技术栈

- 前端：`React` + `Vite`
- 后端：`FastAPI`
- 数据库：`SQLite`
- 免费数据源：`SEC companyfacts`、`SEC ticker directory`、`Yahoo chart`、`Alpha Vantage` 兜底、`FRED DGS10`

## 启动方式

### 1. 后端

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

默认地址：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`

## 验证

```bash
.venv/bin/pytest backend/tests -q
cd frontend && npm run build
```

## 项目结构

```text
backend/                 FastAPI 后端、估值引擎、数据源、测试
frontend/                React 前端页面与组件
docs/research/           本地研究 PDF 样本
docs/references/         参考资料与旧版分析页面
估值体系-V2.0.md         原始现金流估值框架
估值体系-V3.0.md         当前多模型综合估值框架
AGENTS.md                当前项目约束、清单和开发说明
```

## 估值方法说明

当前核心方法是 [`估值体系-V3.0.md`](./估值体系-V3.0.md)。

这套方法的重点不是追求一个“精确目标价”，而是：

- 先识别公司类型
- 再选择更贴近市场的估值方法组合
- 用多个模型交叉验证
- 最后输出普通投资者能理解的价格区间和可信度

对高成长科技、平台、软件公司，系统不会再只用单年现金流硬压估值，而会把现金流、forward earnings 和市场常用倍数放在一起看。

## 研究资料

仓库里保留了几份本地研究资料样本，方便后续继续做页面、文档或解析能力：

- `docs/research/pypl202512research.pdf`
- `docs/research/tcehy202512research.pdf`
- `docs/research/tsla202512research.pdf`
- `docs/references/价值投资评分体系-V30.html`

这些资料目前主要作为参考素材和测试样本，不参与应用运行。

## 当前边界

- 只服务本地个人使用
- 不做登录、多用户、交易、券商接入
- 免费数据优先，部分 forward 预期仍是系统估算值
- 输出是研究辅助，不是投资建议

## 后续方向

- 接入或手动维护 forward EPS 共识
- 增加历史估值分位
- 优化深色模式
- 补充更完整的研究报告导出
