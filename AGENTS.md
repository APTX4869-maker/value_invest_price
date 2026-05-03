# AGENTS.md

## 项目概览

这是一个本地运行的美股估值研究网站，面向个人学习和业余投资分析。核心目标不是给出买卖指令，而是把 `估值体系-V3.0.md` 变成可复盘的研究流程。

后续产品方向已升级为“发现雷达 + 公司研究档案”的双引擎工作台，详细设计见 `docs/product/value-study-redesign-prd.md`：

- 发现雷达：默认扫描 S&P 500，QQQ 和自定义股票池作为可选池，按综合研究优先级寻找可能低于实际价值且值得继续研究的公司；第一版通用股票池 API 和前端入口已落地。
- 研究队列：承接发现雷达筛出的公司，使用“候选、初筛通过、深度研究中、已形成结论、复盘中”五个状态和多标签管理研究进度；第一版状态推进与列表/看板已落地。
- 公司研究档案：围绕单家公司整合一页纸结论、业务与护城河、财务质量、估值、同行比较、投资备忘录和历史复盘；第一版 tabs 骨架已落地。
- SEC + LLM 研究助手：SEC 研究包底座已落地，可抓取 10-K/10-Q 并抽取 Business、Risk Factors、MD&A 等关键章节；OpenAI-compatible LLM 初稿生成已接入，输出默认是待确认 draft。
- 投资备忘录：从自由笔记升级为结构化 memo，沉淀投资假设、反证清单、估值判断和复盘触发条件；第一版结构化表单与本地存储已落地。

当前已实现的功能基础包括：

- 观察池：管理关注公司，查看当前估值判断。
- 公司分析：用白话解释核心财务指标和关键风险。
- 估值模型：运行分层目标价、DCF 概率区间、Forward P/E、PEG、EV multiples、FCF Yield、反向 DCF 和三情景估值。
- 同行比较：维护同行列表并辅助校验估值判断。
- 发现雷达：已从 QQQ 专用页升级为通用股票池扫描，默认 S&P 500，保留 QQQ 和自定义池。
- 研究笔记：保存投资假设、风险清单和复盘。
- 历史与设置：保存估值快照，维护数据源和默认参数。

本项目只服务本地个人使用，不做登录、多用户、交易、券商接入或自动买卖提醒。

## 技术栈

- 后端：Python、FastAPI、SQLite。
- 前端：React、Vite、lucide-react。
- 数据源：SEC companyfacts / company tickers、SEC filing 文本、Yahoo chart 免费行情通道、S&P 500 成分股免费源或手动 CSV 覆盖、Invesco QQQ 官方持仓 API、FRED 10 年期美债、Alpha Vantage 可选兜底、OpenAI-compatible LLM Provider、手动设置项。
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
- `backend/routers/`：按职责拆分的接口层，包含 health、watchlist、companies、valuation、discovery、notes、settings。
- `backend/schemas.py`：请求体 schema。
- `backend/dependencies.py`：共享查询和序列化工具。
- `backend/data_sources.py`：SEC ticker 搜索、SEC companyfacts 年报/最近季度解析、Invesco QQQ holdings、免费行情/利率抓取和网络重试。
- `backend/db.py`：SQLite 初始化、默认设置、GOOG 种子数据。
- `backend/discovery.py`：S&P 500 / QQQ / 自定义池通用发现雷达、候选股评分、护城河/财务/竞争/数据质量原因生成。
- `backend/valuation/`：估值 V3.0/V4.1 的核心计算逻辑，包含 assumptions、capex、confidence、dcf、engine、models、multiples、quality、range_engine、reverse。
- `backend/tests/`：后端测试，覆盖估值公式、目标价计算、数据源解析、金融公司口径、共识预期、错误提示、同行比较和发现池。
- `frontend/src/main.jsx`：前端入口，保留应用状态、数据加载和页面切换。
- `frontend/src/pages/`：核心页面，包括研究队列（Watchlist 文件名保留）、公司档案、ValuationModel、ValuationResult、PeersPage、DiscoveryPage、NotesPage、HistorySettings。
- `frontend/src/components/`：通用 UI 组件，例如 Shell、Ticker 输入提示、指标解释、徽章和空状态。
- `frontend/src/api/`、`frontend/src/utils/`、`frontend/src/data/`：本地 API 客户端、格式化工具、指标解释和估值模板。
- `frontend/src/styles.css`：视觉样式、响应式布局、卡片/列表视图。
- `估值体系-V2.0.md`：原始现金流估值方法论。
- `估值体系-V3.0.md`：当前核心估值方法论，采用多模型综合区间，默认面向非专业个人投资者展示白话结论。

## 开发原则

- 先照顾非专业投资者理解成本：默认展示白话结论，公式和专业指标放在可展开区域。
- 后续新功能必须优先服务“双引擎”主线：先大范围发现研究线索，再进入公司档案做深度研究。
- 发现雷达的排序必须可解释，不允许只展示黑箱分数。每个候选应解释估值、可信度、财务质量、护城河、竞争风险和数据缺口。
- 公司档案的一页纸结论必须回答“当前便宜、合理、偏贵还是不确定”，并展示原因、可信度和下一步建议。
- SEC + LLM 生成内容只能作为“待确认初稿”，必须保留证据出处或标记为系统推断；用户确认/编辑后的内容优先。
- 结构化投资备忘录是形成结论和后续复盘的主入口，不能只依赖自由 Markdown 笔记。
- 数据接口失败时必须给出可理解原因，例如 ticker 错误、ETF/基金不支持、SEC 字段缺失。
- 不要把估值输出写成投资建议。表达应是“当前价格隐含什么预期”和“哪些假设最敏感”。
- 新增估值公式必须加后端单元测试。
- 修改前端主要流程后，至少运行 `npm run build`。
- 不要提交 `.venv/`、`node_modules/`、`frontend/dist/`、`data/*.db`、`.superpowers/`。

## 当前已知优化清单

### 高优先级

- 双引擎产品重构：已完成第一版骨架，将入口升级为“发现雷达 + 研究队列 + 公司档案 + 投资备忘录 + 历史复盘”。后续继续补 SEC/LLM、行业热力图、矩阵视图和更完整的复盘版本链。
- S&P 500 发现雷达：已把 QQQ 前 30 扫描泛化为股票池扫描。默认池为 S&P 500，保留 QQQ 和自定义池；支持成分缓存、Top 50/Top 100/全部扫描、失败解释、综合研究优先级和入队理由。后续补行业热力图与低估幅度 × 可信度矩阵。
- 研究队列：已把“观察池”产品心智升级为研究队列，支持候选、初筛通过、深度研究中、已形成结论、复盘中五个状态，多标签、下一步动作和入队理由。后续可补拖拽排序和更细的待办清单。
- 公司研究档案：已把公司分析收敛为公司档案 tabs，顶部固定一页纸结论，并提供业务、财务、估值、同行、memo、历史入口。后续可继续把估值/同行/memo 深度内容内嵌得更完整。
- 结构化投资备忘录：已新增 memo 本地存储和前端表单，覆盖当前结论、为什么关注、核心投资假设、业务与护城河、财务质量、估值判断、我可能错在哪里、复盘触发条件；保留自由补充区。后续可补 memo 版本历史。
- SEC + LLM 研究助手：已完成 SEC filing 文本解析和 OpenAI-compatible Provider 第一版，支持在公司档案内刷新 SEC 研究包、查看关键章节证据、生成待确认 AI 初稿，并可编辑、确认、驳回。确认后会保守写入公司档案 `research_summary`，并只填补结构化 memo 的空字段。后续补更细的引用管理。
- 估值内核 V4.1：已完成分层概率目标价。最终目标价不再由单一 DCF 决定，而是组合内在价值层、市场倍数层和可选分析师目标价层；反向 DCF 只做解释校验，不参与加权目标价。
- 高成长公司估值修正：NVDA、PLTR 等高成长/平台型公司会优先使用 FY2 或 FY2 proxy 的 forward EPS / revenue / EBITDA / FCF，避免单年 FCF 或旧财务数据把估值中枢压得过低。
- 动态模型权重：已完成基于 forward 数据来源、同行快照、历史估值分位和 DCF 终值依赖度的权重调整。系统估算值会降权，手动/本地共识和同行数据会提高可信度。
- 本地共识预期：估值模型页已支持录入、保存、清空本地 EPS、收入、EBITDA、FCF、长期 EPS 增速和分析师目标价区间；后端提供 `/api/valuation/consensus/{ticker}`。
- 金融公司口径：已完成第一轮金融/放贷类公司识别。SOFI 这类 Finance Services 公司会用 `RevenuesNetOfInterestExpense`、税前/净利润等金融口径重建收入和盈利，不再机械使用经营现金流 FCFF 模型。
- 存储半导体口径：已完成 MU 第一版修正。系统会把 MU 识别为 `memory_semiconductor`，用 SEC 最近 10-Q 单季营收/经营利润和 YTD FCF 外推前瞻锚点，估值权重改为 Forward P/E、EV/EBITDA、EV/Sales 为主，中周期利润只保留为周期风险折价，避免把 AI/HBM 上行周期机械压成传统周期股中周期估值。
- 前端拆分：已完成第一轮拆分，`frontend/src/main.jsx` 只保留应用状态和页面路由；页面、通用组件、API、格式化工具和数据配置已拆到 `frontend/src/pages/`、`frontend/src/components/`、`frontend/src/api/`、`frontend/src/utils/`、`frontend/src/data/`。
- 后端拆分：已完成第一轮拆分，`backend/app.py` 只保留应用创建和 router 注册；接口按职责拆到 `backend/routers/`，共享 schema 和依赖放到 `backend/schemas.py`、`backend/dependencies.py`。估值核心已拆到 `backend/valuation/`，发现池逻辑在 `backend/discovery.py`。后续可继续抽离 service 层，把数据库写入和外部数据抓取从 router 中再下沉一层。
- 数据源健壮性：已完成多轮增强，补了 `ifrs-full` 标签兜底、季度/YTD/20-F/资产负债表项目测试、最近季度和 YTD 现金流快照、资产负债表 `CY2025Q4I` frame 支持、SSL EOF/超时/HTTP 429/5xx 重试和错误分类。对于非美元申报公司，当前会明确提示“需要手动汇率转换”，避免静默生成失真估值。后续仍需继续补更多 ADR 样本和自动汇率转换。
- 删除策略：已完成第一轮增强，观察池支持“删除观察池”和“彻底删除”两级操作；前者保留笔记和快照，后者连研究笔记与历史快照一起清除，并带双重确认。后续可再补批量清理和快照数量提示。
- 估值参数模板：已完成前端第一版，支持平台/广告、软件/SaaS、支付、消费品牌、硬件/制造、通用保守模板，并会根据公司画像自动推荐。后续可把模板下沉到后端并允许本地保存自定义模板。
- QQQ 子池：原 QQQ 发现逻辑已保留为发现雷达里的可选科技成长子池，并兼容旧 `/api/discovery/qqq` 接口。

### 中优先级

- 行情源兜底：已完成第一轮增强，支持 `Yahoo chart -> Alpha Vantage` 的股价兜底链路，并可在公司档案对单个公司手动覆盖价格。后续可继续增加更多免费源和行情时间戳展示。
- 10 年期美债：已完成第一轮增强，设置中可填 `fred_api_key` 自动拉取 FRED 的 `DGS10`；未配置时继续使用本地默认值。后续可补缓存时间和最近更新时间展示。
- 快照对比：已完成第一轮增强，历史页支持选择两个快照并排比较合理中枢、当前价和关键估值假设。后续可继续补更多差异字段和图形化展示。
- 同行比较：已完成增强，支持批量刷新已选同行、返回同口径估值相对比较，并在同行页展示白话结论、价格/合理中枢、FCF Yield、质量分和隐含增长。同行估值快照会写入 `peer_valuation_snapshot`，供后续动态倍数估值使用。后续可继续补更多相对估值指标、行业专属比较口径和图形化展示。
- 估值体系 V3.0/V4.1：已完成从单一现金流 DCF 中枢到多模型、分层目标价区间的升级，包含 DCF 概率区间、Forward P/E、PEG、EV/Revenue、EV/EBITDA、FCF Yield、Rule of 40 EV/Sales、可选分析师目标价；前端默认展示综合目标价区间、分层权重、模型一致性、普通投资者结论和高级详情。后续可接入真实分析师 EPS 共识和更长历史估值分位。
- 错误提示：已完成增强，前端新增全局 toast，用于添加/刷新/删除/保存/导出等操作的成功和失败提示；后端会区分网络/SSL 临时故障、数据源返回异常、ticker/ETF 不支持，避免把 SEC/Yahoo 连接问题误报为 ticker 错误。

### 低优先级

- 增加导出：已完成第一轮增强，估值模型页支持把单家公司估值分析导出为 Markdown。后续可补 PDF 导出和包含研究笔记/快照对比的完整报告。
- 增加页面内搜索：已完成第一轮增强，研究笔记支持关键词搜索并在预览中高亮；历史快照支持按标题、日期、判断、结论和价格过滤。
- 增加轻量图表：已完成第一轮增强，刷新公司时会从 SEC companyfacts 保存最近最多 6 年的营收、经营利润、OCF、CAPEX、SBC 历史，公司档案用原生 SVG 展示核心财务趋势。金融公司会优先保存金融口径收入和盈利历史。后续可补 FCF、利润率、同比增长和估值区间图。
- 发现雷达后续增强：当前第一版已支持 S&P 500 / QQQ / 自定义池。后续可继续补行业热力图、低估幅度 × 可信度矩阵、历史发现记录、批量导出、护城河自定义打分和外部共识数据导入。
- 增加深色模式，但不要牺牲阅读舒适度。

## 数据与估值注意事项

- SEC companyfacts 是免费且可靠的主数据源，但不同公司字段命名不完全一致。
- S&P 500 是后续默认发现池；由于免费稳定的官方机器可读成分接口不一定可得，应支持免费源抓取和手动 CSV 覆盖。S&P 500 成分会变化，且可能包含多股权类别。
- Invesco QQQ 官方持仓 API 用于 QQQ 子池，持仓会变化；发现页展示的是研究线索，不是买卖推荐。
- ETF、基金、杠杆产品没有公司经营财报，不适用当前公司估值模型。
- 当前估值内核已调整为 `V3.0/V4.1 layered probability target price calculator`：品质分继续动态计算，但合理价值中枢改为分层目标价，不再由单一现金流 DCF 决定。
- V4.1 默认输出三层目标价：内在价值层、市场倍数层、可选分析师目标价层。DCF 在结果里是内在价值锚之一，不等同于最终目标价。
- NVDA、PLTR 等高成长公司会默认使用前瞻盈利/收入窗口，并结合 Forward P/E、PEG、EV multiples 来避免单年 FCF 过度压低估值。
- MU/存储半导体使用 `memory_semiconductor` 模板：最近季度的收入和经营利润用于前瞻估算，DCF 和中周期利润只做风险折价；结论应重点解释 HBM 需求、DRAM/NAND 价格、CAPEX 和周期回落风险。
- 免费数据下的 forward EPS 仍是系统估算值，不是分析师共识；如果用户手动录入本地共识或分析师目标价，应优先替换系统估算值。
- 金融/放贷类公司不能机械套普通 FCFF DCF。当前已支持第一版金融服务口径：优先使用净利息后收入、税前/净利润和 Forward P/E 主锚；银行、保险、REIT 仍需更专门的估值模型。
- SOFI 这类 Finance Services 公司此前会因收入字段和 OCF 口径错配导致估值严重失真；当前已修正为金融口径，但仍建议补充真实分析师 EPS 共识和资产质量指标。
- 发现雷达的护城河、财务质量、行业竞争分是启发式研究排序，不是最终投资结论。它应该帮助决定“先研究谁”，而不是替代完整研究。
- SEC 研究包提供 10-K/10-Q 原文证据摘录；LLM 生成的业务、护城河和风险分析只能作为带出处的待确认研究初稿，不能直接作为最终结论；用户确认和结构化 memo 才是后续复盘依据。
- 估值结果应被视为“假设检查器”，不是目标价承诺。
