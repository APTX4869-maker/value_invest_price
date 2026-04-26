# 本地美股估值研究系统

面向个人学习和投资分析的本地网站。它把 `估值体系-V2.0.md` 落成一个可运行的研究工作台：观察池、公司分析、估值模型、同行比较、研究笔记、历史与设置。

## 启动

### 后端

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

打开 Vite 输出的本地地址，默认后端地址是 `http://127.0.0.1:8000`。

## 设计重点

- 默认照顾非专业投资者：先显示白话结论，再展开数据和公式。
- 数据半自动：SEC/免费行情可刷新，关键估值假设可手动覆盖。
- 每次估值可保存为快照，方便复盘当时的判断。
- 输出不是投资建议，而是帮助理解当前价格隐含了什么预期。

