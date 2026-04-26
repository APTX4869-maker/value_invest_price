# AGENTS.md

## 项目概览

这是一个本地运行的美股估值研究网站，面向个人学习和业余投资分析。核心目标不是给出买卖指令，而是把 `估值体系-V3.0.md` 变成可复盘的分析流程：

- 观察池：管理关注公司，查看当前估值判断。
- 公司分析：用白话解释核心财务指标和关键风险。
- 估值模型：运行 DCF、Owner Earnings、反向 DCF 和三情景估值。
- 同行比较：维护同行列表并辅助校验估值判断。
- 研究笔记：保存投资假设、风险清单和复盘。
- 历史与设置：保存估值快照，维护数据源和默认参数。

本项目只服务本地个人使用，不做登录、多用户、交易、券商接入或自动买卖提醒。

## 技术栈

- 后端：Python、FastAPI、SQLite。
- 前端：React、Vite、lucide-react。
- 数据源：SEC companyfacts / company tickers、Yahoo chart 免费行情通道、手动设置项。
- 本地数据：`data/value_invest.db`，不应提交到仓库。

## 常用命令

后端：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

验证：

```bash
.venv/bin/pytest backend/tests -q
cd frontend && npm run build
```

默认访问：

- 前端：`http://127.0.0.1:5173/`
- 后端健康检查：`http://127.0.0.1:8000/api/health`

## 代码结构

- `backend/app.py`：FastAPI 应用入口、生命周期和 router 注册。
- `backend/routers/`：按职责拆分的接口层，包含 health、watchlist、companies、valuation、notes、settings。
- `backend/schemas.py`：请求体 schema。
- `backend/dependencies.py`：共享查询和序列化工具。
- `backend/data_sources.py`：SEC ticker 搜索、SEC companyfacts、免费行情抓取。
- `backend/db.py`：SQLite 初始化、默认设置、GOOG 种子数据。
- `backend/valuation.py`：估值 V3.0 的核心计算逻辑。
- `backend/tests/test_valuation.py`：估值公式基础测试。
- `frontend/src/main.jsx`：前端入口，保留应用状态、数据加载和页面切换。
- `frontend/src/pages/`：六个核心页面。
- `frontend/src/components/`：通用 UI 组件，例如 Shell、Ticker 输入提示、指标解释、徽章和空状态。
- `frontend/src/api/`、`frontend/src/utils/`、`frontend/src/data/`：本地 API 客户端、格式化工具、指标解释和估值模板。
- `frontend/src/styles.css`：视觉样式、响应式布局、卡片/列表视图。
- `估值体系-V2.0.md`：原始现金流估值方法论。
- `估值体系-V3.0.md`：当前核心估值方法论，采用多模型综合区间，默认面向非专业个人投资者展示白话结论。

## 开发原则

- 先照顾非专业投资者理解成本：默认展示白话结论，公式和专业指标放在可展开区域。
- 数据接口失败时必须给出可理解原因，例如 ticker 错误、ETF/基金不支持、SEC 字段缺失。
- 不要把估值输出写成投资建议。表达应是“当前价格隐含什么预期”和“哪些假设最敏感”。
- 新增估值公式必须加后端单元测试。
- 修改前端主要流程后，至少运行 `npm run build`。
- 不要提交 `.venv/`、`node_modules/`、`frontend/dist/`、`data/*.db`。

## 当前已知优化清单

### 高优先级

- 前端拆分：已完成第一轮拆分，`frontend/src/main.jsx` 只保留应用状态和页面路由；页面、通用组件、API、格式化工具和数据配置已拆到 `frontend/src/pages/`、`frontend/src/components/`、`frontend/src/api/`、`frontend/src/utils/`、`frontend/src/data/`。
- 后端拆分：已完成第一轮拆分，`backend/app.py` 只保留应用创建和 router 注册；接口按职责拆到 `backend/routers/`，共享 schema 和依赖放到 `backend/schemas.py`、`backend/dependencies.py`。后续可继续抽离 service 层，把数据库写入和外部数据抓取从 router 中再下沉一层。
- 数据源健壮性：已完成第一轮增强，补了 `ifrs-full` 标签兜底和针对季度/YTD/20-F/资产负债表项目的单元测试；对于非美元申报公司，当前会明确提示“需要手动汇率转换”，避免静默生成失真估值。后续仍需继续补金融公司、更多 ADR 样本和自动汇率转换。
- 删除策略：已完成第一轮增强，观察池支持“删除观察池”和“彻底删除”两级操作；前者保留笔记和快照，后者连研究笔记与历史快照一起清除，并带双重确认。后续可再补批量清理和快照数量提示。
- 估值参数模板：已完成前端第一版，支持平台/广告、软件/SaaS、支付、消费品牌、硬件/制造、通用保守模板，并会根据公司画像自动推荐。后续可把模板下沉到后端并允许本地保存自定义模板。

### 中优先级

- 行情源兜底：已完成第一轮增强，支持 `Yahoo chart -> Alpha Vantage` 的股价兜底链路，并可在公司分析页对单个公司手动覆盖价格。后续可继续增加更多免费源和行情时间戳展示。
- 10 年期美债：已完成第一轮增强，设置中可填 `fred_api_key` 自动拉取 FRED 的 `DGS10`；未配置时继续使用本地默认值。后续可补缓存时间和最近更新时间展示。
- 快照对比：已完成第一轮增强，历史页支持选择两个快照并排比较合理中枢、当前价和关键估值假设。后续可继续补更多差异字段和图形化展示。
- 同行比较：已完成第一轮增强，支持批量刷新已选同行、返回同口径估值相对比较，并在同行页展示白话结论、价格/合理中枢、FCF Yield、质量分和隐含增长。后续可继续补更多相对估值指标、行业专属比较口径和图形化展示。
- 估值体系 V3.0：已完成第一轮升级，后端从单一现金流 DCF 中枢升级为多模型综合区间，包含保守现金流 DCF、Forward P/E、PEG 成长调整、EV/Revenue、EV/EBITDA、FCF Yield；前端默认展示综合合理区间、保守买入区、高风险高估区、模型一致性和普通投资者结论。后续可接入分析师 EPS 共识和历史估值分位，减少高成长公司对本地默认假设的依赖。
- 错误提示：已完成第一轮增强，前端新增全局 toast，用于添加/刷新/删除/保存/导出等操作的成功和失败提示；顶部状态仍保留为轻量连接状态。

### 低优先级

- 增加导出：已完成第一轮增强，估值模型页支持把单家公司估值分析导出为 Markdown。后续可补 PDF 导出和包含研究笔记/快照对比的完整报告。
- 增加页面内搜索：已完成第一轮增强，研究笔记支持关键词搜索并在预览中高亮；历史快照支持按标题、日期、判断、结论和价格过滤。
- 增加轻量图表：已完成第一轮增强，刷新公司时会从 SEC companyfacts 保存最近最多 6 年的营收、经营利润、OCF、CAPEX、SBC 历史，公司分析页用原生 SVG 展示核心财务趋势。后续可补 FCF、利润率、同比增长和估值区间图。
- 增加深色模式，但不要牺牲阅读舒适度。

## 数据与估值注意事项

- SEC companyfacts 是免费且可靠的主数据源，但不同公司字段命名不完全一致。
- ETF、基金、杠杆产品没有公司经营财报，不适用当前公司估值模型。
- 当前估值内核已调整为 `V3.0 multi-model valuation`：品质分继续动态计算，但合理价值中枢改为多模型综合结果，不再由单一现金流 DCF 决定。
- V3.0 默认输出三层区间：保守价值区间、市场合理区间、乐观成长区间，并额外给出保守买入区、高风险高估区、模型一致性和白话结论。
- DCF 在 V3.0 中是保守锚点之一，不等同于最终合理区间。NVDA、PLTR 等高成长公司会默认使用前瞻盈利/收入窗口，并结合 Forward P/E、PEG、EV multiples 来避免单年 FCF 过度压低估值。
- 免费数据下的 forward EPS 仍是系统估算值，不是分析师共识。后续如接入免费/手动共识 EPS，应优先替换估算值。
- 当前 DCF 默认假设不能机械套到银行、保险、REIT 或强周期公司。
- 估值结果应被视为“假设检查器”，不是目标价承诺。
