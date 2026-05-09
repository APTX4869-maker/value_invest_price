# AGENTS.md

## 项目概览

这是一个本地运行的美股估值研究网站，面向个人学习和业余投资分析。核心目标不是给出买卖指令，而是把 `估值体系-V3.0.md` 变成可复盘的研究流程。

后续产品方向已升级为“发现雷达 + 公司研究档案”的双引擎工作台，详细设计见 `docs/product/value-study-redesign-prd.md`：

- 发现雷达：默认扫描 S&P 500，QQQ 和自定义股票池作为可选池，按综合研究优先级寻找可能低于实际价值且值得继续研究的公司；第一版通用股票池 API 和前端入口已落地。
- 研究队列：承接发现雷达筛出的公司，使用“候选、初筛通过、深度研究中、已形成结论、复盘中”五个状态和多标签管理研究进度；第一版状态推进与列表/看板已落地。
- 公司研究档案：围绕单家公司整合一页纸结论、业务与护城河、财务质量、估值、同行比较、SEC 证据、AI 待确认初稿、投资备忘录和历史复盘；第一版深度研究工作流已落地。
- SEC + LLM 研究助手：SEC 研究包底座已落地，可抓取 10-K/10-Q 并抽取 Business、Risk Factors、MD&A 等关键章节；OpenAI-compatible LLM 初稿生成已接入，输出默认是待确认 draft。
- 投资备忘录：从自由笔记升级为结构化 memo，沉淀投资假设、反证清单、估值判断和复盘触发条件；结构化表单、本地存储、版本链和版本对比已落地。

当前已实现的功能基础包括：

- 研究队列 / 观察池：管理关注公司、发现雷达入队公司、研究状态、标签、下一步动作和当前估值判断。
- 公司研究档案：用白话解释核心财务指标、关键风险、SEC 证据、AI 待确认初稿、同行和投资备忘录。
- 估值模型：运行分层目标价、三阶段 FCFF DCF、Excel 口径简化 FCF DCF、DCF 概率区间、Forward P/E、PEG、EV multiples、FCF Yield、反向 DCF 和三情景估值。
- 同行比较：维护同行列表、自动推荐可比公司、批量刷新同行估值并辅助校验估值判断。
- 发现雷达：已从 QQQ 专用页升级为通用股票池扫描，默认 S&P 500，保留 QQQ 和自定义池。
- 研究笔记 / 投资备忘录：保存投资假设、风险清单、结构化 memo、版本链和复盘触发条件。
- 历史与设置：保存估值快照，维护数据源、默认参数、FMP / Alpha Vantage / Finnhub / FRED / OpenAI-compatible LLM 配置。

本项目只服务本地个人使用，不做登录、多用户、交易、券商接入或自动买卖提醒。

## 技术栈

- 后端：Python、FastAPI、SQLite。
- 前端：React、Vite、lucide-react。
- 数据源：SEC companyfacts / company tickers、SEC filing 文本、FMP 标准化财报与分析师数据、Alpha Vantage 标准化财报兜底、Finnhub 公司画像/指标/同行兜底、Yahoo chart 免费行情通道、S&P 500 成分股免费源或手动 CSV 覆盖、Invesco QQQ 官方持仓 API、FRED 10 年期美债、OpenAI-compatible LLM Provider、手动设置项。
- 本地数据：`data/value_invest.db`，不应提交到仓库。

## 常用命令

后端：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --port 8000
```

如果在 Codex/受限沙箱里遇到 `--reload` 文件监听或端口绑定权限问题，优先改用：

```bash
.venv/bin/uvicorn backend.app:app --port 8000
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

本地排障：

- 估值模型点击“重新计算”后出现 `Failed to fetch` 或连接失败时，先检查后端是否在 `127.0.0.1:8000` 运行：`curl -sS http://127.0.0.1:8000/api/health`。
- `http://127.0.0.1:5173/` 打不开时，通常是 Vite 前端没有运行，进入 `frontend` 后执行 `npm run dev`。
- 前端 API 默认连接 `http://127.0.0.1:8000`；如需改后端地址，使用 `VITE_API_BASE`。
- 当前项目没有单独的前端 lint/test 脚本，前端主要验证方式是 `npm run build`；浏览器点击级验证需要额外 Playwright 或浏览器插件环境。

## 代码结构

- `backend/app.py`：FastAPI 应用入口、生命周期和 router 注册。
- `backend/routers/`：按职责拆分的接口层，包含 health、watchlist、companies、valuation、discovery、research_queue、notes、settings。
- `backend/schemas.py`：请求体 schema。
- `backend/dependencies.py`：共享查询和序列化工具。
- `backend/data_sources.py`：SEC ticker 搜索、SEC companyfacts 年报/最近季度解析、Invesco QQQ holdings、免费行情/利率抓取和网络重试。
- `backend/db.py`：SQLite 初始化、默认设置、GOOG 种子数据。
- `backend/discovery.py`：S&P 500 / QQQ / 自定义池通用发现雷达、候选股评分、护城河/财务/竞争/数据质量原因生成。
- `backend/sec_filings.py`：SEC submissions / filing 文本抓取、10-K/10-Q 章节抽取和本地研究包缓存。
- `backend/llm_research.py`：OpenAI-compatible LLM 配置校验、SEC 证据组装、AI 研究初稿生成、确认/驳回和 memo 合并。
- `backend/memo_history.py`：结构化投资备忘录默认值、序列化和版本链记录。
- `backend/peer_recommendations.py`：基于公司画像、行业和内置规则的同行推荐。
- `backend/valuation/`：估值 V3.0/V4.1 的核心计算逻辑，包含 assumption_engine、assumptions、capex、confidence、dcf、engine、models、multiples、quality、range_engine、reverse。
- `backend/tests/`：后端测试，覆盖估值公式、目标价计算、数据源解析、金融公司口径、共识预期、错误提示、同行比较、发现池、研究队列、SEC filing、LLM draft 和 memo 版本链。
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
- 前端网络层失败不能只暴露浏览器原始 `Failed to fetch`；应提示后端未启动、地址错误或 `VITE_API_BASE` 配置问题。
- 不要把估值输出写成投资建议。表达应是“当前价格隐含什么预期”和“哪些假设最敏感”。
- 新增估值公式必须加后端单元测试。
- 修改前端主要流程后，至少运行 `npm run build`。
- 不要提交 `.venv/`、`node_modules/`、`frontend/dist/`、`data/*.db`、`.superpowers/`。

## 当前已知优化清单

### 高优先级

- 双引擎产品重构：已完成第一版骨架，将入口升级为“发现雷达 + 研究队列 + 公司档案 + 投资备忘录 + 历史复盘”。SEC/LLM、memo 版本链和同行推荐第一版已接入；后续继续补行业热力图、矩阵视图、更细引用管理和更完整的复盘版本链。
- S&P 500 发现雷达：已把 QQQ 前 30 扫描泛化为股票池扫描。默认池为 S&P 500，保留 QQQ 和自定义池；支持成分缓存、Top 50/Top 100/全部扫描、失败解释、综合研究优先级和入队理由。后续补行业热力图与低估幅度 × 可信度矩阵。
- 研究队列：已把“观察池”产品心智升级为研究队列，支持候选、初筛通过、深度研究中、已形成结论、复盘中五个状态，多标签、下一步动作和入队理由。后续可补拖拽排序和更细的待办清单。
- 公司研究档案：已把公司分析收敛为公司档案 tabs，顶部固定一页纸结论，并提供业务、财务、估值、同行、memo、历史、SEC 研究包和 AI 初稿入口。后续可继续把估值/同行/memo 深度内容内嵌得更完整。
- 结构化投资备忘录：已新增 memo 本地存储、前端表单和第一版版本链，覆盖当前结论、为什么关注、核心投资假设、业务与护城河、财务质量、估值判断、我可能错在哪里、复盘触发条件；保留自由补充区。每次手动保存和 AI 初稿确认写入都会记录 `investment_memo_versions`，备忘录页展示最近版本，支持选择两个版本对比结构化字段差异，并可把某个历史版本载入编辑区后手动保存。后续可补更细的逐字 diff。
- SEC + LLM 研究助手：已完成 SEC filing 文本解析和 OpenAI-compatible Provider 第一版，支持在公司档案内刷新 SEC 研究包、查看关键章节证据、生成待确认 AI 初稿，并可编辑、确认、驳回。AI 初稿会展示来源 accession 和引用线索，并在可匹配时跳转到对应 SEC 章节；确认后会保守写入公司档案 `research_summary`，并只填补结构化 memo 的空字段。历史与配置页已提供专门的 AI 研究助手设置面板。后续补更细的引用管理和版本链。
- 估值内核 V4.1：已完成分层概率目标价。最终目标价不再由单一 DCF 决定，而是组合内在价值层、市场倍数层和可选分析师目标价层；反向 DCF 只做解释校验，不参与加权目标价。估值结果页会并排展示最终目标价体系、三阶段 FCFF DCF 和 Excel 口径简化 FCF DCF，方便交叉对比。
- 公司粒度假设引擎：已新增 `backend/valuation/assumption_engine.py` 统一生成估值关键假设。核心原则是不能用固定模板直接决定基准增长率、利润率、贴现率、永续增长和资本开支口径；必须优先读取公司历史收入/利润/FCF、最近季度趋势、公司级先验、行业先验、数据质量和公司类型置信度，并在结果里解释每个关键假设的来源、权重、截断范围和风险提示。
- 高成长公司估值修正：NVDA、PLTR 等高成长/平台型公司会优先使用 FY2 或 FY2 proxy 的 forward EPS / revenue / EBITDA / FCF，避免单年 FCF 或旧财务数据把估值中枢压得过低。
- 动态模型权重：已完成基于 forward 数据来源、同行快照、历史估值分位和 DCF 终值依赖度的权重调整。系统估算值会降权，手动/本地共识和同行数据会提高可信度。
- 本地共识预期：估值模型页已支持录入、保存、清空本地 EPS、收入、EBITDA、FCF、长期 EPS 增速和分析师目标价区间；后端提供 `/api/valuation/consensus/{ticker}`。
- 金融公司口径：已完成第一轮金融/放贷类公司识别。SOFI 这类 Finance Services 公司会用 `RevenuesNetOfInterestExpense`、税前/净利润等金融口径重建收入和盈利，不再机械使用经营现金流 FCFF 模型。
- 工业制造公司口径：已新增 `industrial` 分类，GE 这类航空/电气设备/工业制造公司不再因短期高利润率被误判为平台型公司；估值会使用更保守的工业增长、EV/EBITDA、Forward P/E、DCF 和 FCF Yield 权重。
- 存储半导体口径：已完成 MU 第一版修正。系统会把 MU 识别为 `memory_semiconductor`，用 SEC 最近 10-Q 单季营收/经营利润和 YTD FCF 外推前瞻锚点，估值权重改为 Forward P/E、EV/EBITDA、EV/Sales 为主，中周期利润只保留为周期风险折价，避免把 AI/HBM 上行周期机械压成传统周期股中周期估值。
- 前端拆分：已完成第一轮拆分，`frontend/src/main.jsx` 只保留应用状态和页面路由；页面、通用组件、API、格式化工具和数据配置已拆到 `frontend/src/pages/`、`frontend/src/components/`、`frontend/src/api/`、`frontend/src/utils/`、`frontend/src/data/`。
- 后端拆分：已完成第一轮拆分，`backend/app.py` 只保留应用创建和 router 注册；接口按职责拆到 `backend/routers/`，共享 schema 和依赖放到 `backend/schemas.py`、`backend/dependencies.py`。估值核心已拆到 `backend/valuation/`，发现池逻辑在 `backend/discovery.py`。后续可继续抽离 service 层，把数据库写入和外部数据抓取从 router 中再下沉一层。
- 数据源健壮性：已完成多轮增强，补了 `ifrs-full` 标签兜底、季度/YTD/20-F/资产负债表项目测试、最近季度和 YTD 现金流快照、资产负债表 `CY2025Q4I` frame 支持、SSL EOF/超时/HTTP 429/5xx 重试和错误分类。对于非美元申报公司，当前会明确提示“需要手动汇率转换”，避免静默生成失真估值。后续仍需继续补更多 ADR 样本和自动汇率转换。
- FMP 数据增强：已接入 `fmp_api_key` 本地设置。刷新公司时会在 SEC 权威底稿之外按实际权限补 FMP 标准化三表、分析师收入/EPS/EBITDA 预期、key metrics TTM、ratios TTM、enterprise values、owner earnings、price target consensus 和 peer tickers。FMP 数据用于补缺失字段、增强质量评分、CAPEX 拆分、当前倍数校验、analyst layer 和初始同行列表；用户手动共识和手动同行列表优先，不被 FMP 覆盖。FMP 免费 key 对不同接口权限不稳定，后端必须记录 `raw_json.fmp.available` 和 `raw_json.fmp.warnings`，不能把 401/403 或空响应静默当成“无数据”。
- Alpha Vantage / Finnhub 数据增强：已接入 `alpha_vantage_api_key` 和 `finnhub_api_key` 本地设置。Alpha Vantage 当前用于行情、OVERVIEW 和三张标准化财报兜底；Finnhub 当前免费权限下用于 quote、profile2、metric 和 peers，分析师目标价与预期类接口可能返回 403，因此不能作为共识预期主源。两者都必须写入 `raw_json.*.available` 和 `raw_json.*.warnings`，只补缺失字段，不覆盖 SEC/FMP/手动输入。
- 数据覆盖与 API 预算：刷新公司后会写入 `raw_json.data_coverage`，按历史财报、资产负债表、最近季度、价格/利率、前瞻共识、同行倍数和质量指标打覆盖评分。FMP、Alpha Vantage、Finnhub 请求会写入 SQLite `external_api_cache`，默认 24 小时内同 endpoint/ticker 参数走缓存；成功和失败响应都会缓存，避免免费 API 被重复刷新打爆。`raw_json.api_usage` 展示最近 24 小时网络调用、缓存命中、网络失败和失败缓存命中。
- 删除策略：已完成第一轮增强，观察池支持“删除观察池”和“彻底删除”两级操作；前者保留笔记和快照，后者连研究笔记与历史快照一起清除，并带双重确认。后续可再补批量清理和快照数量提示。
- 估值参数模板：已完成前端第一版，支持平台/广告、软件/SaaS、支付、消费品牌、硬件/制造、通用保守模板，并会根据公司画像自动推荐。后续可把模板下沉到后端并允许本地保存自定义模板。
- QQQ 子池：原 QQQ 发现逻辑已保留为发现雷达里的可选科技成长子池，并兼容旧 `/api/discovery/qqq` 接口。

### 中优先级

- 行情源兜底：已完成第一轮增强，支持 `Yahoo chart -> Alpha Vantage` 的股价兜底链路，并可在公司档案对单个公司手动覆盖价格。后续可继续增加更多免费源和行情时间戳展示。
- 10 年期美债：已完成第一轮增强，设置中可填 `fred_api_key` 自动拉取 FRED 的 `DGS10`；未配置时继续使用本地默认值。后续可补缓存时间和最近更新时间展示。
- 快照对比：已完成第一轮增强，历史页支持选择两个快照并排比较合理中枢、当前价和关键估值假设。后续可继续补更多差异字段和图形化展示。
- 同行比较：已完成增强，支持批量刷新已选同行、返回同口径估值相对比较，并在同行页展示白话结论、价格/合理中枢、FCF Yield、质量分和隐含增长。同行估值快照会写入 `peer_valuation_snapshot`，供后续动态倍数估值使用。后续可继续补更多相对估值指标、行业专属比较口径和图形化展示。
- 估值体系 V3.0/V4.1：已完成从单一现金流 DCF 中枢到多模型、分层目标价区间的升级，包含三阶段 FCFF DCF、Excel 口径简化 FCF DCF、DCF 概率区间、Forward P/E、PEG、EV/Revenue、EV/EBITDA、FCF Yield、Rule of 40 EV/Sales、可选分析师目标价；前端默认展示综合目标价区间、分层权重、模型一致性、普通投资者结论和高级详情。后续可接入真实分析师 EPS 共识和更长历史估值分位。
- 错误提示：已完成增强，前端新增全局 toast，用于添加/刷新/删除/保存/导出等操作的成功和失败提示；后端会区分网络/SSL 临时故障、数据源返回异常、ticker/ETF 不支持，避免把 SEC/Yahoo 连接问题误报为 ticker 错误。前端 API 客户端也会把后端未启动或 `VITE_API_BASE` 地址错误翻译成明确的中文排障提示。

### 低优先级

- 增加导出：已完成第一轮增强，估值模型页支持把单家公司估值分析导出为 Markdown。后续可补 PDF 导出和包含研究笔记/快照对比的完整报告。
- 增加页面内搜索：已完成第一轮增强，研究笔记支持关键词搜索并在预览中高亮；历史快照支持按标题、日期、判断、结论和价格过滤。
- 增加轻量图表：已完成第一轮增强，刷新公司时会从 SEC companyfacts 保存最近最多 6 年的营收、经营利润、OCF、CAPEX、SBC 历史，公司档案用原生 SVG 展示核心财务趋势。金融公司会优先保存金融口径收入和盈利历史。后续可补 FCF、利润率、同比增长和估值区间图。
- 发现雷达后续增强：当前第一版已支持 S&P 500 / QQQ / 自定义池。后续可继续补行业热力图、低估幅度 × 可信度矩阵、历史发现记录、批量导出、护城河自定义打分和外部共识数据导入。
- QQQ 池本地缓存：默认 S&P 500 池已有种子/缓存；QQQ 和自定义池在新库里可能为空，需要先在发现雷达刷新成分或手动维护自定义池。
- 增加深色模式，但不要牺牲阅读舒适度。

## 数据与估值注意事项

- SEC companyfacts 是免费且可靠的主数据源，但不同公司字段命名不完全一致。
- FMP 是 SEC 之外的增强源，不替代 SEC 权威底稿。FMP 标准化三表、key metrics、ratios、enterprise values、owner earnings、analyst estimates、price target 和 peers 可用于提高估值输入质量，但每个字段仍应在结果中标记来源，并在与 SEC 或手动输入冲突时优先保留手动输入和原始 SEC 证据。
- 当前 FMP provider 优先使用 `/stable/*` 接口，并对旧 `/api/v3/*` 做兜底。若三张标准化财报不可用但分析师预期、价格目标、TTM 指标或同行可用，仍应保留这些增强输入；若全部不可用，应返回 `FMP configured but unavailable` 诊断，方便用户判断是 key 权限、额度还是接口变化。
- Alpha Vantage 免费 key 实测可访问 `GLOBAL_QUOTE`、`OVERVIEW`、`INCOME_STATEMENT`、`BALANCE_SHEET`、`CASH_FLOW` 和 `EARNINGS`。当前系统用它补标准化财报和 overview，不把它视为分析师共识源。
- Finnhub 免费 key 实测可访问 `quote`、`stock/profile2`、`stock/metric` 和 `stock/peers`；`stock/price-target`、`stock/revenue-estimate`、`stock/eps-estimate`、`stock/ebitda-estimate` 和 `stock/ebit-estimate` 当前返回 403。当前系统只使用可用接口做画像、指标、同行和行情兜底。
- S&P 500 是后续默认发现池；由于免费稳定的官方机器可读成分接口不一定可得，应支持免费源抓取和手动 CSV 覆盖。S&P 500 成分会变化，且可能包含多股权类别。
- Invesco QQQ 官方持仓 API 用于 QQQ 子池，持仓会变化；发现页展示的是研究线索，不是买卖推荐。
- ETF、基金、杠杆产品没有公司经营财报，不适用当前公司估值模型。
- 当前估值内核已调整为 `V3.0/V4.1 layered probability target price calculator`：品质分继续动态计算，但合理价值中枢改为分层目标价，不再由单一现金流 DCF 决定。
- V4.1 默认输出三层目标价：内在价值层、市场倍数层、可选分析师目标价层。DCF 在结果里是内在价值锚之一，不等同于最终目标价。
- 三阶段 FCFF DCF 和 Excel 口径简化 FCF DCF 是两种不同现金流模型。前者用收入、利润率、FCF margin、贴现率和永续增长重建现金流；后者用最新/手动 FCF、7%-15% 增长阶梯、15% 折现率和当前 FCF 倍数退出价值做快速交叉校验。简化 DCF 不参与最终目标价加权。
- 关键估值假设必须公司粒度化：增长率应来自 3/5 年收入 CAGR、最近季度年化趋势、公司生命周期和行业先验的加权组合，不能用 `max(历史增长, 模板增长)` 这类单向乐观规则；利润率应参考历史中位数、最近年度/季度和行业正常区间，并对异常年份降权；贴现率应拆成无风险利率、股权风险溢价和公司风险溢价；永续增长必须低于贴现率且不高于长期经济增速假设。
- 估值输出必须展示“假设从哪里来”：包括公司类型判定原因、关键历史指标、行业先验、手动覆盖项、数据缺口、模型适用性警告和置信度。缺少足够历史数据时，估值结论应主动降置信度，而不是用模板参数伪装成精确估值。
- NVDA、PLTR 等高成长公司会默认使用前瞻盈利/收入窗口，并结合 Forward P/E、PEG、EV multiples 来避免单年 FCF 过度压低估值。
- MU/存储半导体使用 `memory_semiconductor` 模板：最近季度的收入和经营利润用于前瞻估算，DCF 和中周期利润只做风险折价；结论应重点解释 HBM 需求、DRAM/NAND 价格、CAPEX 和周期回落风险。
- 免费数据下的 forward EPS 仍是系统估算值，不是分析师共识；如果用户手动录入本地共识或分析师目标价，应优先替换系统估算值。
- 金融/放贷类公司不能机械套普通 FCFF DCF。当前已支持第一版金融服务口径：优先使用净利息后收入、税前/净利润和 Forward P/E 主锚；银行、保险、REIT 仍需更专门的估值模型。
- SOFI 这类 Finance Services 公司此前会因收入字段和 OCF 口径错配导致估值严重失真；当前已修正为金融口径，但仍建议补充真实分析师 EPS 共识和资产质量指标。
- GE 这类工业制造公司不能只按高利润率识别成平台型复利公司。当前 `industrial` 会优先匹配 aerospace、aviation、electrical equipment、industrial、machinery、manufacturing、turbine 等行业文本；后续仍应支持手动公司类型覆盖和分类原因展示。
- 发现雷达的护城河、财务质量、行业竞争分是启发式研究排序，不是最终投资结论。它应该帮助决定“先研究谁”，而不是替代完整研究。
- SEC 研究包提供 10-K/10-Q 原文证据摘录；LLM 生成的业务、护城河和风险分析只能作为带出处的待确认研究初稿，不能直接作为最终结论；用户确认和结构化 memo 才是后续复盘依据。
- 估值结果应被视为“假设检查器”，不是目标价承诺。
