# Signal Desk · 每日叙事雷达

这是一个静态新闻聚合器，聚焦 AI 科技、重大创新突破、AI 生成文化，以及中文社区传播度高的热梗、标语、表情、动物和虚拟角色。

项目主动排除战争、灾害、事故、选举、政治人物健康和公共安全等重大社会公共事件。它只整理可验证的叙事线索，不提供买卖建议。

## 自动更新

`.github/workflows/daily-report.yml` 每天 **UTC 00:00（北京时间 08:00）** 运行：

1. 发现层从 TechCrunch、The Verge、MIT Technology Review、OpenAI News 和定向 Google News 查询获取前一天的条目；
2. 分析层按 AI Agent、创新突破、AI 生成文化、中文热梗、动物表情和虚拟角色生成具体事件摘要、别名、检索词与传播特征；
3. 验证层合并同一事件的转载，统计独立来源、官方/主流/社区来源层级，并与上一期比较新热、再热和持续传播；
4. 过滤重大社会公共事件并按 S/A/B 优先级整理；
5. 写入 `site/data/news.json` 和 `site/data/report.md`；
6. 自动提交数据更新；
7. 将 `site/` 部署到 GitHub Pages。

首页的“历史报告”区域读取 `site/data/reports-index.json`，每天保留一份日期归档到 `reports/YYYY-MM-DD.md` 和 `site/data/YYYY-MM-DD.md`，可从网页直接回看过去报告。

不需要 Firecrawl、OpenAI 或其他 API Key。网络源不可用时，报告会明确显示“暂无足够可靠的新增重点”，不会使用旧新闻填充。

## 本地运行

```bash
python scripts/fetch_news.py
```

直接打开 `site/index.html` 可以查看前端；开发预览可运行：

```bash
python -m http.server 4173 --directory site
```

## 人工核验

“有传播度”不等于“有代币价值”。请自行核对代币创建时间、是否有明显龙头、流动性、持仓集中度、部署者历史和撤池风险。IP、品牌、名人和影视角色相关线索还要额外考虑版权与仿冒风险。
