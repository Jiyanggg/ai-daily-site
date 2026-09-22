#!/usr/bin/env python3
"""Fetch yesterday's public RSS signals and write the static report files."""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "site" / "data"
NEWS_FILE = DATA_DIR / "news.json"
REPORT_FILE = DATA_DIR / "report.md"
LOCAL_ZONE = ZoneInfo("Asia/Shanghai")

FEEDS = [
    {"query": "AI agent OR humanoid robot innovation", "category": "AI 科技"},
    {"query": "AI breakthrough OR AI discovery OR AI research", "category": "AI 科技"},
    {"query": "AI meme OR AI brainrot OR viral AI character", "category": "虚拟角色"},
    {"query": "热梗 表情包 动物 虚拟人物", "category": "中文热梗"},
    {"query": "网络热词 标语 句式 表情包", "category": "中文热梗"},
]

EXCLUDED = ("war", "earthquake", "flood", "fire", "election", "terror", "killed", "death toll", "disaster", "战争", "地震", "洪水", "火灾", "选举", "遇难", "死亡")
AI_TERMS = ("ai", "agent", "robot", "humanoid", "model", "openai", "anthropic", "人工智能", "智能体", "机器人", "大模型")
MEME_TERMS = ("meme", "viral", "brainrot", "hot", "trend", "热梗", "表情", "爆红", "网络", "角色", "动物", "标语")


def clean_text(value: str | None) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def rss_url(query: str) -> str:
    params = {"q": query, "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"}
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)


def fetch_feed(query: str) -> list[dict[str, str]]:
    request = urllib.request.Request(rss_url(query), headers={"User-Agent": "SignalDesk/1.0 (+https://github.com/)"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
        root = ET.fromstring(payload)
    except (OSError, ET.ParseError) as exc:
        print(f"warning: failed to fetch {query!r}: {exc}", file=sys.stderr)
        return []

    items: list[dict[str, str]] = []
    for node in root.findall("./channel/item"):
        title = clean_text(node.findtext("title"))
        link = clean_text(node.findtext("link"))
        description = clean_text(node.findtext("description"))
        published = clean_text(node.findtext("pubDate"))
        source_node = node.find("source")
        source = clean_text(source_node.text if source_node is not None else "")
        if title and link:
            items.append({"title": title, "link": link, "description": description, "published": published, "source": source})
    return items


def item_date(item: dict[str, str]) -> date | None:
    try:
        parsed = parsedate_to_datetime(item["published"])
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(LOCAL_ZONE).date()
    except (TypeError, ValueError, OverflowError):
        return None


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", title.lower())


def score(item: dict[str, str], category: str) -> int:
    text = f"{item['title']} {item['description']}".lower()
    value = 1
    if any(term in text for term in AI_TERMS):
        value += 2
    if any(term in text for term in MEME_TERMS):
        value += 2
    if category in ("中文热梗", "动物表情", "虚拟角色"):
        value += 1
    if len(item["title"]) <= 72:
        value += 1
    return value


def priority(value: int) -> str:
    if value >= 6:
        return "S"
    if value >= 4:
        return "A"
    return "B"


def category_for(item: dict[str, str], default: str) -> str:
    title = item["title"].lower()
    if any(term in title for term in ("动物", "猫", "狗", "熊", "鼠", "cat", "dog", "bear", "animal")):
        return "动物表情"
    if any(term in title for term in ("meme", "brainrot", "热梗", "表情", "标语", "网络热词")):
        return "中文热梗" if default != "AI 科技" else "虚拟角色"
    return default


def to_event(item: dict[str, str], default_category: str, index: int) -> dict[str, object]:
    text = f"{item['title']} {item['description']}"
    value = score(item, default_category)
    category = category_for(item, default_category)
    title = item["title"].split(" - ", 1)[0]
    summary = item["description"] or "公开 RSS 条目，建议打开来源核验原文和上下文。"
    keywords = [part for part in re.split(r"[：:，,。()（）/|]+", title) if 2 <= len(part) <= 28][:4]
    if not keywords:
        keywords = [title[:30]]
    event_id = f"{item_date(item) or 'unknown'}-{index}-{normalize_title(title)[:36]}"
    return {
        "id": event_id,
        "title": title,
        "category": category,
        "priority": priority(value),
        "status": "新热",
        "occurredAt": str(item_date(item) or ""),
        "summary": summary[:320],
        "why": "标题在公开 RSS 中出现，并具备可复述或可二创的传播信号；需要人工确认是否形成社区共识。",
        "keywords": keywords,
        "sources": [{"name": item["source"] or "Google News RSS", "url": item["link"]}],
        "risk": "自动聚合，需人工核验",
        "chainFit": "待核验",
        "_score": value,
        "_text": text,
    }


def build_report(report_date: date) -> dict[str, object]:
    raw: list[tuple[dict[str, str], str]] = []
    for feed in FEEDS:
        for item in fetch_feed(feed["query"]):
            if item_date(item) != report_date:
                continue
            text = f"{item['title']} {item['description']}".lower()
            if any(term in text for term in EXCLUDED):
                continue
            raw.append((item, feed["category"]))

    events: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, (item, category) in enumerate(raw):
        event = to_event(item, category, index)
        key = normalize_title(str(event["title"]))
        if not key or key in seen:
            continue
        seen.add(key)
        events.append(event)

    events.sort(key=lambda event: (-int(event["_score"]), str(event["title"])))
    events = events[:36]
    for event in events:
        event.pop("_score", None)
        event.pop("_text", None)

    source_count = len({source["name"] for event in events for source in event["sources"]})
    if events:
        headline = f"昨日捕捉到 {len(events)} 条可验证的 AI 与互联网文化信号"
        summary = "；".join(str(event["title"]) for event in events[:3]) + "。建议先核验 S 级条目的原始来源和链上创建时间。"
    else:
        headline = "昨日暂无足够可靠的新增重点"
        summary = "本次没有符合筛选条件且日期明确的公开 RSS 条目，系统没有使用旧新闻填充。"

    return {
        "demo": False,
        "reportDate": str(report_date),
        "generatedAt": datetime.now(LOCAL_ZONE).isoformat(timespec="seconds"),
        "headline": headline,
        "summary": summary,
        "sourceCount": source_count,
        "events": events,
    }


def write_markdown(report: dict[str, object]) -> None:
    lines = [f"# Signal Desk · {report['reportDate']}", "", str(report["summary"]), "", "## 今日重点关注", ""]
    events = report["events"]
    if not events:
        lines.append("昨日暂无足够可靠的新增重点。")
    else:
        for index, event in enumerate(events, start=1):
            lines.extend([
                f"### {index}. [{event['priority']}级] {event['title']}",
                f"- 类别：{event['category']} · 状态：{event['status']} · 日期：{event['occurredAt']}",
                f"- 摘要：{event['summary']}",
                f"- 为什么值得看：{event['why']}",
                f"- 检索词：{', '.join(event['keywords'])}",
                f"- 风险：{event['risk']}",
                f"- 来源：" + ", ".join(f"[{source['name']}]({source['url']})" for source in event["sources"]),
                "",
            ])
    lines.extend(["## 人工核验提醒", "", "不要把新闻热度直接等同于代币价值。请核对代币创建时间、是否有明显龙头、流动性、持仓集中度、部署者历史和撤池风险。"])
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report_date = datetime.now(LOCAL_ZONE).date() - timedelta(days=1)
    report = build_report(report_date)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    NEWS_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report)
    print(f"wrote {NEWS_FILE} and {REPORT_FILE}: {len(report['events'])} events for {report_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
