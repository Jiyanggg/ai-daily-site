# LIU冀杨的 AI 日报 - 自动化网站

每日 20:30 (CST) 自动抓取 YouTube / TechCrunch / Twitter 上的 AI 热点新闻，翻译成中文并生成日报。

## 快速部署

### 1. 创建 GitHub 仓库

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/你的用户名/ai-daily.git
git push -u origin main
```

### 2. 设置 GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 必需 | 说明 |
|---|---|---|
| `FIRECRAWL_API_KEY` | 是 | [Firecrawl](https://firecrawl.dev) API 密钥，用于网页抓取 |
| `OPENAI_API_KEY` | 是 | OpenAI API 密钥，用于生成中文日报 |
| `OPENAI_BASE_URL` | 否 | 自定义 API 地址（默认 `https://api.openai.com/v1`） |
| `OPENAI_MODEL` | 否 | 模型名称（默认 `gpt-4o`） |

### 3. 部署到 Vercel

1. 登录 [vercel.com](https://vercel.com)，点击 "Import Project"
2. 选择你的 GitHub 仓库
3. 设置：
   - **Framework Preset**: Other
   - **Root Directory**: `site`
   - **Build Command**: 留空
   - **Output Directory**: `.`
4. 部署完成后会获得一个 `xxx.vercel.app` 域名

### 4. 手动触发测试

在 GitHub 仓库 → Actions → "Generate AI Daily Report" → Run workflow

## 项目结构

```
ai-daily-site/
├── .github/workflows/
│   └── daily-report.yml    # GitHub Actions 定时任务
├── reports/                 # 生成的 Markdown 日报 (按日期命名)
│   └── 2026-03-18.md
├── scripts/
│   ├── generate_report.py   # 抓取 + AI 生成脚本
│   └── build.py             # 构建网站数据
├── site/                    # 静态网站 (部署到 Vercel)
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── data/                # 构建后的数据文件
│       ├── reports-index.json
│       └── 2026-03-18.md
└── vercel.json              # Vercel 配置
```

## 工作流程

1. 每天 20:30 CST，GitHub Actions 自动执行
2. `generate_report.py` 通过 Firecrawl 抓取三个数据源
3. 调用 OpenAI 将原始数据翻译整理成中文日报
4. `build.py` 将 Markdown 复制到 `site/data/` 并更新索引
5. 自动 commit + push，Vercel 检测到更新后自动部署

## 自定义

- 修改 `scripts/generate_report.py` 中的 prompt 来调整日报风格
- 修改 `site/style.css` 来调整网站外观
- 修改 cron 表达式 `30 12 * * *` 来调整发布时间（UTC 时区）
