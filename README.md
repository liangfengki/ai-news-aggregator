# 📡 AI News Aggregator — AI 资讯市场快讯看板

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Railway](https://img.shields.io/badge/Deploy-Railway-8B5CF6.svg)](https://railway.app)

> 一个基于 AI 的金融/科技资讯聚合平台，自动抓取全球 RSS 源，通过 LLM 进行智能分类、情感分析和中英文翻译，提供实时市场快讯看板。

---

## ✨ 功能特性

- **📰 多源聚合** — 同时抓取 19+ 国内外主流资讯源（CNBC、华尔街日报、36氪、财联社、TechCrunch 等）
- **🤖 AI 分类** — 基于 DeepSeek LLM 自动识别资讯所属市场（A股/港股/美股/币圈）和情感倾向（看涨/看跌）
- **📊 影响评分** — AI 自动评估每条资讯的市场影响分（0-100），高分资讯标记为"重点"
- **🌐 自动翻译** — 英文资讯自动翻译为中文，保留原文对照
- **📈 实时行情** — 集成新浪财经接口，展示全球主要指数实时行情
- **🔍 智能搜索** — 支持关键词搜索、按市场/情感/来源多维筛选
- **🌙 暗色主题** — 支持亮色/暗色主题切换，阅读更舒适
- **♻️ 自动刷新** — 后台每 2 分钟抓取新资讯，前端 30 秒自动更新
- **🩹 自愈监控** — 内置健康检查和自动恢复机制

---

## 📸 界面预览

| 资讯看板 | 全球监控 |
|:---:|:---:|
| 市场快讯卡片视图 | 全球指数 + 预警 + 科技资讯 |
| 多维筛选 + 搜索 | 2×2 仪表盘布局 |

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────┐
│                   Frontend (SPA)                 │
│     HTML + CSS + Vanilla JS (暗色/亮色主题)        │
└──────────────────────┬──────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────┐
│              FastAPI Backend (app.py)            │
│         GZip · CORS · Static Files              │
├─────────────────────────────────────────────────┤
│  scraper.py          │    classifier.py          │
│  RSS 抓取 · 去重 · 翻译  │  LLM 分类 · 关键词兜底    │
├─────────────────────────────────────────────────┤
│         sources.py (19+ RSS 源 + 关键词库)        │
├─────────────────────────────────────────────────┤
│              SQLite (aiosqlite)                  │
│         news 表 + classification_cache 表        │
├─────────────────────────────────────────────────┤
│        OpenRouter API (DeepSeek Chat V3)         │
└─────────────────────────────────────────────────┘
```

**数据流：**
1. `sources.py` 定义 RSS 源和关键词库
2. `scraper.py` 并发抓取 → 去重 → 存入 SQLite
3. `classifier.py` LLM 分类（关键词兜底）→ 缓存结果
4. 英文资讯由 LLM 批量翻译为中文
5. `app.py` 提供 REST API + 静态页面服务
6. 前端自动轮询刷新

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- OpenRouter API Key（[获取地址](https://openrouter.ai/keys)）

### 本地运行

```bash
# 1. 克隆仓库
git clone https://github.com/liangfengki/ai-news-aggregator.git
cd ai-news-aggregator

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 OpenRouter API Key

# 5. 启动服务
export OPENROUTER_API_KEY="your-key-here"
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

浏览器访问 `http://localhost:8080` 即可。

### 无 LLM 模式（不需要 API Key）

即使不配置 `OPENROUTER_API_KEY`，项目也能正常运行：
- RSS 抓取正常工作
- 使用关键词进行基础分类（准确度略低）
- 英文资讯不会自动翻译

---

## 🔧 环境变量

| 变量 | 必需 | 说明 |
|---|---|---|
| `OPENROUTER_API_KEY` | 否 | OpenRouter API Key，用于 LLM 分类和翻译 |

---

## 📡 API 接口

| 端点 | 方法 | 说明 |
|---|---|---|
| `/` | GET | 资讯看板首页 |
| `/api/news` | GET | 获取资讯列表（支持筛选） |
| `/api/search?q=` | GET | 关键词搜索 |
| `/api/trending` | GET | 24 小时热门话题 |
| `/api/stats` | GET | 统计数据（总数/重点/情感分布） |
| `/api/sources` | GET | 资讯来源列表 |
| `/api/news/count` | GET | 符合条件的资讯数量 |
| `/api/refresh` | POST | 手动触发刷新（含 LLM 分类） |
| `/api/health` | GET | 健康检查 |
| `/api/market` | GET | 实时全球指数行情 |

### 筛选参数（/api/news）

| 参数 | 示例 | 说明 |
|---|---|---|
| `market` | `A股`, `美股`, `币圈` | 按市场筛选 |
| `sentiment` | `bullish`, `bearish` | 按情感筛选 |
| `source` | `CNBC`, `36氪` | 按来源筛选 |
| `highlight` | `true` | 仅显示重点资讯 |
| `sort` | `impact`, `time` | 排序方式 |
| `hours` | `24` | 时间范围（小时） |
| `page` | `1` | 页码 |
| `page_size` | `20` | 每页数量 |

---

## 📂 项目结构

```
ai-news-aggregator/
├── app.py              # FastAPI 应用入口，路由和中间件
├── scraper.py          # RSS 抓取、数据库操作、翻译
├── classifier.py       # LLM 分类 + 关键词兜底分类
├── sources.py          # RSS 源配置和关键词库
├── auto_improve.py     # 自动监控和自愈脚本
├── check_and_improve.py # 健康检查诊断脚本
├── requirements.txt    # Python 依赖
├── Procfile            # Railway/Heroku 部署配置
├── railway.json        # Railway 部署参数
├── .env.example        # 环境变量模板
├── LICENSE             # MIT 开源协议
└── static/
    ├── index.html      # 主看板页面
    ├── monitor.html    # 全球监控子页面
    ├── css/
    │   └── style.css   # 样式（亮色/暗色主题）
    └── js/
        └── app.js      # 前端逻辑（筛选/搜索/渲染）
```

---

## 🌐 部署

### Railway 部署（推荐）

1. Fork 本仓库
2. 在 [Railway](https://railway.app) 创建新项目
3. 连接你的 GitHub 仓库
4. 添加环境变量 `OPENROUTER_API_KEY`
5. Railway 会自动检测 `railway.json` 并部署

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/ai-news)

### Docker 部署

```bash
docker build -t ai-news .
docker run -p 8080:8080 -e OPENROUTER_API_KEY="your-key" ai-news
```

### 通过 GitHub Actions 自动部署

本项目支持通过 GitHub Actions 自动部署到 Railway。Push 到 `main` 分支即触发部署。

---

## 📊 数据源

### 英文源
| 来源 | 分类 |
|---|---|
| CNBC | 财经 |
| Wall Street Journal | 财经 |
| MarketWatch | 财经 |
| Seeking Alpha | 投资 |
| CoinTelegraph | 加密货币 |
| TechCrunch | 科技 |
| The Verge | 科技 |
| Hacker News | 科技 |

### 中文源
| 来源 | 分类 |
|---|---|
| 36氪 | 科技/商业 |
| 财联社 | 财经 |
| 华尔街见闻 | 财经 |
| 格隆汇 | 港股/投资 |
| 虎嗅 | 科技/商业 |
| 钛媒体 | 科技 |
| IT之家 | 科技 |
| 爱范儿 | 科技/消费 |
| 少数派 | 科技/效率 |
| 澎湃新闻 | 综合 |
| 观察者网 | 综合 |
| 百度热搜 | 热点 |

---

## 🤝 贡献

欢迎贡献！请遵循以下步骤：

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/your-feature`)
3. 提交更改 (`git commit -m 'Add your feature'`)
4. 推送到分支 (`git push origin feature/your-feature`)
5. 创建 Pull Request

### 贡献方向

- 📡 添加新的 RSS 源（编辑 `sources.py`）
- 🎨 改进前端 UI/UX
- 🐛 修复 Bug
- 📝 完善文档
- 🌍 国际化支持

---

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源。

---

## ⚠️ 免责声明

本平台资讯、数据等内容来自网络公开信息，仅供参考，不构成任何投资建议。使用本平台即表示您同意自行承担所有风险。
