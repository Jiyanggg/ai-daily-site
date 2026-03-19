#!/usr/bin/env python3
"""
generate_report.py - Multi-topic daily intelligence scraper & report generator.

Scrapes three domains:
  1. AI / Artificial Intelligence (YouTube, TechCrunch, Twitter/X)
  2. Frontier Science (Nature, Science, ArXiv, NASA)
  3. Geopolitics & Macro Economy (Reuters, FT, Bloomberg)

Requirements:  pip install openai requests
Environment:   FIRECRAWL_API_KEY, OPENAI_API_KEY
Output:        reports/YYYY-MM-DD.md
"""
import json, os, sys, datetime, requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
TODAY = datetime.date.today().isoformat()


# ─── Firecrawl helpers ───────────────────────────────────────
def firecrawl_search(query, limit=10, **kwargs):
    url = "https://api.firecrawl.dev/v1/search"
    headers = {"Authorization": f"Bearer {FIRECRAWL_API_KEY}", "Content-Type": "application/json"}
    body = {"query": query, "limit": limit, **kwargs}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("data", data.get("results", []))
    except Exception as e:
        print(f"[search] Error: {e}", file=sys.stderr)
        return []


def firecrawl_scrape(target_url, formats=None, **kwargs):
    url = "https://api.firecrawl.dev/v1/scrape"
    headers = {"Authorization": f"Bearer {FIRECRAWL_API_KEY}", "Content-Type": "application/json"}
    body = {"url": target_url, "formats": formats or ["markdown"], **kwargs}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json().get("data", {})
    except Exception as e:
        print(f"[scrape] Error {target_url}: {e}", file=sys.stderr)
        return {}


# ─── Topic 1: AI ─────────────────────────────────────────────
def collect_ai():
    print("[1/3] Collecting AI news...")
    items = []

    # YouTube AI videos
    yt = firecrawl_search(f"AI artificial intelligence latest news {TODAY[:4]}", limit=6, filter="site:youtube.com")
    for r in yt:
        if "youtube.com/watch" in (r.get("url") or ""):
            items.append({"title": r.get("title",""), "url": r.get("url",""),
                          "description": r.get("description",""), "source": "YouTube"})

    # TechCrunch
    tc = firecrawl_scrape("https://techcrunch.com/category/artificial-intelligence/",
        formats=["json"],
        jsonOptions={"prompt": "Extract latest AI articles with title, url, author, date, description.",
                     "schema": {"type":"object","properties":{"articles":{"type":"array","items":{"type":"object",
                     "properties":{"title":{"type":"string"},"url":{"type":"string"},"author":{"type":"string"},
                     "date":{"type":"string"},"description":{"type":"string"}}}}}}})
    if tc and "json" in tc:
        for a in tc["json"].get("articles", [])[:10]:
            items.append({"title": a.get("title",""), "url": a.get("url",""),
                          "description": a.get("description",""), "source": "TechCrunch"})

    # Twitter/X AI
    tw = firecrawl_search(f"AI artificial intelligence trending {TODAY[:4]}", limit=6, filter="site:x.com")
    for r in tw:
        items.append({"title": r.get("title",""), "url": r.get("url",""),
                      "description": r.get("snippet", r.get("description","")), "source": "Twitter/X"})

    print(f"  AI: {len(items)} items")
    return items


# ─── Topic 2: Frontier Science ───────────────────────────────
def collect_science():
    print("[2/3] Collecting science news...")
    items = []

    sources = [
        ("breakthrough discovery science research 2026", None),
        ("Nature Science new findings physics biology", None),
        ("NASA space discovery 2026", None),
    ]
    for query, filt in sources:
        kwargs = {}
        if filt:
            kwargs["filter"] = filt
        results = firecrawl_search(query, limit=5, **kwargs)
        for r in results:
            items.append({"title": r.get("title",""), "url": r.get("url",""),
                          "description": r.get("snippet", r.get("description","")),
                          "source": r.get("url","").split("/")[2] if r.get("url") else "Web"})

    print(f"  Science: {len(items)} items")
    return items


# ─── Topic 3: Geopolitics & Macro Economy ────────────────────
def collect_geopolitics():
    print("[3/3] Collecting geopolitics & economy news...")
    items = []

    queries = [
        "geopolitics trade sanctions international relations today",
        "Federal Reserve interest rate economy markets today",
        "China US Europe trade policy tariffs 2026",
    ]
    for q in queries:
        results = firecrawl_search(q, limit=5)
        for r in results:
            items.append({"title": r.get("title",""), "url": r.get("url",""),
                          "description": r.get("snippet", r.get("description","")),
                          "source": r.get("url","").split("/")[2] if r.get("url") else "Web"})

    print(f"  Geopolitics: {len(items)} items")
    return items


# ─── LLM report generation ───────────────────────────────────
def generate_report(ai_data, science_data, geo_data):
    print("[4/4] Generating report via LLM...")
    raw = json.dumps({"ai": ai_data, "science": science_data, "geopolitics": geo_data}, ensure_ascii=False, indent=2)

    prompt = f"""你是"LIU冀杨"，一位专业的多领域情报编辑。请根据以下三个领域的原始数据生成中文每日情报。

要求：
1. 标题 "# LIU冀杨的科技日报"，副标题含日期 "{TODAY}"
2. 开头用 blockquote 写三大领域的关键词概要
3. 分为以下板块（每个板块用 ## 标题）：
   - "⚡ AI 人工智能：今日头条"（2-3条重磅AI新闻）
   - "⚡ AI 人工智能：技术与产品"（3-4条技术/产品新闻）
   - "🔬 前沿科学：今日发现"（3条科学突破）
   - "🌍 地缘政治与宏观经济"（3条政经新闻）
   - "🧩 更多值得关注"（表格，含领域列）
   - "📊 今日趋势总结"（分三段总结三个领域）
4. 每条新闻标注 #新闻/#干货/#吃瓜
5. 每条附"骡子点评"，简短犀利
6. 科技媒体风格中文，不过度正式
7. Markdown格式，用 --- 分隔板块
8. 末尾声明：本日报由 LIU冀杨 AI 情报系统自动生成

原始数据：
{raw}"""

    try:
        import openai
        base_url = OPENAI_BASE_URL.rstrip("/")
        # DeepSeek uses https://api.deepseek.com (no /v1 suffix)
        # The openai library appends /chat/completions automatically
        print(f"  LLM: model={OPENAI_MODEL}, base_url={base_url}")
        client = openai.OpenAI(api_key=OPENAI_API_KEY, base_url=base_url)
        resp = client.chat.completions.create(model=OPENAI_MODEL,
            messages=[
                {"role":"system","content":"你是一位专业的中文科技媒体编辑。所有输出必须是中文。"},
                {"role":"user","content":prompt}
            ], temperature=0.7, max_tokens=8192)
        content = resp.choices[0].message.content
        print(f"  LLM: generated {len(content)} chars")
        if len(content) < 200:
            print(f"[LLM] Warning: response too short, using fallback", file=sys.stderr)
            return fallback_report(ai_data, science_data, geo_data)
        return content
    except Exception as e:
        import traceback
        print(f"[LLM] Error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return fallback_report(ai_data, science_data, geo_data)


def fallback_report(ai, sci, geo):
    lines = [f"# LIU冀杨的科技日报\n", f"**{TODAY}**\n", "---\n"]
    lines.append("## ⚡ AI 人工智能：今日头条\n")
    for i, item in enumerate(ai[:5], 1):
        lines.append(f"### {i}. {item['title']} #新闻\n**来源：{item['source']}**\n{item.get('description','')}\n")
    lines.append("---\n\n## 🔬 前沿科学：今日发现\n")
    for i, item in enumerate(sci[:3], 1):
        lines.append(f"### {i}. {item['title']} #干货\n{item.get('description','')}\n")
    lines.append("---\n\n## 🌍 地缘政治与宏观经济\n")
    for i, item in enumerate(geo[:3], 1):
        lines.append(f"### {i}. {item['title']} #新闻\n{item.get('description','')}\n")
    lines.append("\n---\n*本日报由 LIU冀杨 AI 情报系统自动生成*\n")
    return "\n".join(lines)


# ─── Main ────────────────────────────────────────────────────
def main():
    if not FIRECRAWL_API_KEY:
        print("ERROR: FIRECRAWL_API_KEY required.", file=sys.stderr); sys.exit(1)

    ai = collect_ai()
    sci = collect_science()
    geo = collect_geopolitics()

    if not ai and not sci and not geo:
        print("ERROR: No data collected.", file=sys.stderr); sys.exit(1)

    report = generate_report(ai, sci, geo) if OPENAI_API_KEY else fallback_report(ai, sci, geo)

    path = REPORTS_DIR / f"{TODAY}.md"
    path.write_text(report, encoding="utf-8")
    print(f"\nReport saved: {path}")


if __name__ == "__main__":
    main()
