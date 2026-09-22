#!/usr/bin/env python3
"""Build the daily Signal Desk report from public, key-free feeds.

The pipeline is deliberately split into three stages:

1. discovery: targeted publisher feeds and Google News queries;
2. analysis: classify the story and extract a reusable narrative signal;
3. validation: merge duplicates, count independent sources, and compare with
   the previous report before assigning a priority.

It is a lead-generation tool for manual review, not a trading signal.
"""

from __future__ import annotations

import difflib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "site" / "data"
NEWS_FILE = DATA_DIR / "news.json"
REPORT_FILE = DATA_DIR / "report.md"
REPORTS_DIR = ROOT / "reports"
ARCHIVE_INDEX_FILE = DATA_DIR / "reports-index.json"
LOCAL_ZONE = ZoneInfo("Asia/Shanghai")
USER_AGENT = "SignalDesk/2.0 (+https://github.com/Jiyanggg/ai-daily-site)"


# Discovery is intentionally redundant. A single broad RSS search is useful
# for recall, but it is a poor basis for ranking or verification.
DISCOVERY_SOURCES: list[dict[str, str]] = [
    {"name": "TechCrunch AI", "kind": "direct", "tier": "主流科技媒体", "category": "AI 科技", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "The Verge AI", "kind": "direct", "tier": "主流科技媒体", "category": "AI 科技", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "MIT Technology Review", "kind": "direct", "tier": "主流科技媒体", "category": "创新突破", "url": "https://www.technologyreview.com/feed/"},
    {"name": "OpenAI News", "kind": "direct", "tier": "官方源", "category": "AI 科技", "url": "https://openai.com/news/rss.xml"},
    {"name": "Google News · agents", "kind": "google", "tier": "聚合发现", "category": "AI 科技", "query": '"AI agent" OR "computer use" OR "desktop assistant" OR "AI assistant"'},
    {"name": "Google News · breakthrough", "kind": "google", "tier": "聚合发现", "category": "创新突破", "query": 'AI breakthrough OR "scientific discovery" OR "重大突破" OR "重大创新"'},
    {"name": "Google News · robots", "kind": "google", "tier": "聚合发现", "category": "AI 科技", "query": 'humanoid robot OR "robot makes robot" OR 机器人 制造 机器人'},
    {"name": "Google News · generated culture", "kind": "google", "tier": "聚合发现", "category": "AI 生成文化", "query": 'AI meme OR AI brainrot OR viral AI character OR "virtual character"'},
    {"name": "Google News · Chinese meme", "kind": "google", "tier": "聚合发现", "category": "中文热梗", "query": '热梗 OR 表情包 OR 网络热词 OR 标语 OR 句式 OR 动物 梗 OR 虚拟人物'},
    {"name": "Google News · Chinese tech", "kind": "google", "tier": "聚合发现", "category": "AI 科技", "query": 'AI 智能体 OR AI Agent OR 机器人 OR 生成式 AI (36氪 OR 量子位 OR InfoQ OR IT之家 OR B站 OR 哔哩哔哩)'},
    {"name": "Google News · narrative watchlist", "kind": "google", "tier": "聚合发现", "category": "中文热梗", "query": '"Meta Muse" OR "Tung Tung Sahur" OR "AI polar bear" OR 爱疯18 OR 胡一菲 OR 负鼠背手'},
]

EXCLUDED_TERMS = (
    "war", "wars", "earthquake", "flood", "fire kills", "election", "terror",
    "killed", "death toll", "disaster", "战争", "地震", "洪水", "火灾",
    "选举", "遇难", "死亡", "灾害", "事故", "爆炸", "公共安全", "治安",
    "政治人物健康", "总统病情", "border", "surveillance", "immigration",
    "migrant", "virtual wall", "san diego border", "death", "deaths",
)

GENERIC_TERMS = (
    "学术规范", "行业观察", "趋势报告", "白皮书", "融资", "招聘", "大会回顾",
    "观点", "评论", "播客上新", "学术", "academic", "scaling law", "标准", "standards",
    "governance", "learning paths", "academy", "advisory", "safeguards", "certainty",
    "what is ai", "ai ethics", "ai policy",
)

LOW_SIGNAL_TERMS = (
    "startup battlefield", "techcrunch disrupt", "venture capital", "vc judging",
    "settlement", "lawsuit", "claims", "fears are overblown", "ready to slow down",
    "keeping a lot of secrets", "newsletter", "podcast", "大会", "融资",
)

AI_TERMS = (
    "ai", "agent", "computer use", "model",
    "人工智能", "智能体", "大模型", "生成式", "机器人", "humanoid", "robot",
)
MEME_TERMS = (
    "meme", "viral", "brainrot", "trend", "热梗", "表情", "爆红", "网络热词",
    "标语", "口号", "句式", "角色", "动物", "拟人", "梗",
)
BREAKTHROUGH_TERMS = (
    "breakthrough", "discovery", "first", "unveiled", "launch", "released",
    "突破", "发现", "首个", "首次", "发布", "登陆", "开源", "制造",
)
OFFICIAL_HINTS = ("openai", "anthropic", "official", "blog.google", "meta.com")
COMMUNITY_HINTS = ("微博", "哔哩哔哩", "b站", "小红书", "抖音", "知乎", "36氪", "量子位", "it之家")


# These profiles turn a vague headline into a concrete, searchable narrative
# when a known meme or product name appears in more than one source.
SIGNAL_PROFILES: list[dict[str, Any]] = [
    {"name": "Meta Muse", "aliases": ("meta muse", "muse ai", "meta ai assistant"), "category": "AI 科技", "keywords": ("META MUSE", "DESKTOP AGENT", "COMPUTER USE"), "summary": "Meta Muse 被描述为可以在桌面环境中执行操作的 AI 助手，叙事重点从‘会聊天’转向‘AI 有手了’。", "why": "‘AI 有手了’是短而直观的产品叙事；桌面操作、文件和应用控制也给二创留下了明确动作。", "chainFit": "高", "risk": "产品名、品牌和功能真伪需核验"},
    {"name": "37,000 AI Agents", "aliases": ("37000 agents", "37,000 agents", "virtual biotech", "ai scientist swarm"), "category": "创新突破", "keywords": ("37,000 AGENTS", "VIRTUAL BIOTECH", "AI SCIENTIST SWARM"), "summary": "报道聚焦数万 AI Agent 协作执行虚拟生物科技任务，形成‘AI 科学家蜂群’的规模化叙事。", "why": "明确数字、蜂群画面和科学发现三种元素可以被压缩成口号，适合跨社区复述。", "chainFit": "高", "risk": "项目规模、研究结果和原始发布方需核验"},
    {"name": "Robot Makes Robots", "aliases": ("robot makes robot", "robots making robots", "机器人制造机器人"), "category": "AI 科技", "keywords": ("ROBOT MAKES ROBOTS", "HUMANOID", "SELF-MANUFACTURING"), "summary": "机器人参与制造机器人的报道，把机器人从工具升级为‘制造者’角色。", "why": "主体、动作和结果都很具体，‘机器人制造机器人’本身就是可复制的标语。", "chainFit": "高", "risk": "演示范围、人工参与程度与商业化时间表需核验"},
    {"name": "AI Polar Bear", "aliases": ("ai polar bear", "ai 北极熊", "remember november"), "category": "AI 生成文化", "keywords": ("AI POLAR BEAR", "REMEMBER NOVEMBER", "AI GENERATED CHARACTER"), "summary": "AI 生成的北极熊形象与固定句式一起传播，形成可识别的视觉角色和未来预言式梗。", "why": "固定口号、单一视觉角色和可翻译的句式同时存在，具备持续再热和跨语言传播条件。", "chainFit": "高", "risk": "原始创作者、版权和图片出处需核验"},
    {"name": "Tung Tung Sahur", "aliases": ("tung tung sahur", "ai brainrot", "脑腐"), "category": "虚拟角色", "keywords": ("TUNG TUNG SAHUR", "AI 脑腐", "BRAINROT"), "summary": "Tung Tung Sahur 等 AI 脑腐角色依靠荒诞造型、短名字和配音在不同语言社区变体传播。", "why": "角色名短、图像强、动作和配音可复制，天然适合头像、贴纸和衍生角色。", "chainFit": "高", "risk": "角色版权、商标和仿冒项目风险"},
    {"name": "爱疯18", "aliases": ("爱疯18", "iphone 18", "胡一菲", "擀面杖手机"), "category": "中文热梗", "keywords": ("爱疯18", "胡一菲", "擀面杖手机", "IPHONE 18 MEME"), "summary": "‘爱疯18’把现实产品发布与《爱情公寓》旧台词、胡一菲擀面杖手机画面重新接在一起。", "why": "旧影视记忆有现成台词、人物和画面，现实事件提供了再次传播的触发点。", "chainFit": "高", "risk": "影视版权、商标和人物形象风险"},
    {"name": "完全澳白大珍珠", "aliases": ("完全澳白大珍珠", "澳白大珍珠", "珍珠拟人"), "category": "中文热梗", "keywords": ("完全澳白大珍珠", "珍珠拟人", "AUSTRALIAN PEARL"), "summary": "‘完全澳白大珍珠’把外观、妆造或人物标签压缩成一句可以直接复述的视觉人设。", "why": "一句话即可完成视觉人格化，适合图片、头像、评论区接龙和二创。", "chainFit": "中", "risk": "名人形象、营销语境和原始出处需核验"},
    {"name": "负鼠背手", "aliases": ("负鼠背手", "opossum meme", "一起毁灭吧"), "category": "动物表情", "keywords": ("负鼠背手", "一起毁灭吧", "OPOSSUM MEME"), "summary": "负鼠背手直立的照片被中文社区配上‘一起毁灭吧’等摆烂句式，形成动物动作与口号的组合梗。", "why": "动物形象、动作和口号已经绑定，图片模板和文字替换的二创门槛都很低。", "chainFit": "中", "risk": "旧梗，需确认报告日是否有重新爆发"},
]


def clean_text(value: str | None) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def rss_url(query: str) -> str:
    params = {"q": f"{query} when:2d", "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"}
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)


def parse_feed(payload: bytes, fallback_source: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return []

    atom = "{http://www.w3.org/2005/Atom}"
    nodes = root.findall("./channel/item") or root.findall(f"./{atom}entry")
    items: list[dict[str, str]] = []
    for node in nodes:
        def text(*paths: str) -> str:
            for path in paths:
                found = node.find(path)
                if found is not None:
                    if path.endswith("link") and found.attrib.get("href"):
                        return clean_text(found.attrib["href"])
                    if found.text:
                        return clean_text(found.text)
            return ""

        source_node = node.find("source")
        source = clean_text(source_node.text if source_node is not None else "") or fallback_source
        title = text("title", f"{atom}title")
        link = text("link", f"{atom}link")
        description = text("description", "summary", f"{atom}summary", "content", f"{atom}content")
        published = text("pubDate", "published", "updated", "date", f"{atom}published", f"{atom}updated")
        if title and link:
            items.append({"title": title, "link": link, "description": description, "published": published, "source": source})
    return items


def fetch_source(source: dict[str, str]) -> list[dict[str, str]]:
    url = rss_url(source["query"]) if source["kind"] == "google" else source["url"]
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/xml"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = response.read()
        return parse_feed(payload, source["name"])
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"warning: failed to fetch {source['name']}: {exc}", file=sys.stderr)
        return []


def item_date(item: dict[str, str]) -> date | None:
    try:
        parsed = parsedate_to_datetime(item.get("published", ""))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(LOCAL_ZONE).date()
    except (TypeError, ValueError, OverflowError):
        try:
            return datetime.fromisoformat(item.get("published", "").replace("Z", "+00:00")).astimezone(LOCAL_ZONE).date()
        except (TypeError, ValueError):
            return None


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())


def contains_any(text: str, terms: tuple[str, ...] | list[str]) -> bool:
    """Match English terms as words so `ai` does not match `claims` or `again`."""
    lowered = text.lower()
    for term in terms:
        if re.fullmatch(r"[a-z0-9 ]+", term):
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                return True
        elif term in lowered:
            return True
    return False


def source_tier(source: str, fallback: str) -> str:
    value = source.lower()
    if any(hint in value for hint in OFFICIAL_HINTS):
        return "官方源"
    if any(hint in value for hint in COMMUNITY_HINTS):
        return "中文社区媒体"
    return fallback


def profile_for(text: str) -> dict[str, Any] | None:
    lowered = text.lower()
    for profile in SIGNAL_PROFILES:
        if any(alias.lower() in lowered for alias in profile["aliases"]):
            return profile
    return None


def category_for(text: str, default: str, profile: dict[str, Any] | None) -> str:
    if profile:
        return str(profile["category"])
    lowered = text.lower()
    if contains_any(lowered, ("brainrot", "meme", "virtual character")) or any(term in lowered for term in ("虚拟角色", "虚拟人物", "ai 生成角色")):
        return "虚拟角色"
    if contains_any(lowered, ("cat", "dog", "bear", "animal")) or any(term in lowered for term in ("动物", "猫", "狗", "熊", "鼠", "负鼠")):
        return "动物表情"
    if any(term in lowered for term in ("热梗", "表情包", "网络热词", "标语", "口号", "句式", "爱疯")):
        return "中文热梗"
    if contains_any(lowered, BREAKTHROUGH_TERMS) and default != "中文热梗":
        return "创新突破"
    return default


def strip_source_suffix(title: str, source: str) -> str:
    result = re.sub(r"\s+[-|｜]\s+[^-|｜]{2,40}$", "", title).strip()
    if source and result.endswith(source):
        result = result[: -len(source)].rstrip(" -|｜")
    return result or title


def narrative_features(text: str) -> list[str]:
    lowered = text.lower()
    features: list[str] = []
    if any(term in lowered for term in ("口号", "标语", "句式", "remember november", "一起毁灭吧")):
        features.append("固定口号")
    if any(term in lowered for term in ("角色", "动物", "熊", "猫", "狗", "虚拟人物", "character", "avatar")):
        features.append("视觉角色")
    if any(term in lowered for term in ("制造", "操作", "背手", "配音", "动作", "makes", "computer use")):
        features.append("明确动作")
    if any(term in lowered for term in ("二创", "衍生", "翻译", "remix", "variant", "viral")):
        features.append("可复制句式")
    if any(term in lowered for term in ("中文", "english", "跨语言", "global", "海外", "international")):
        features.append("跨语言传播")
    return features


def is_relevant(item: dict[str, str], category: str) -> bool:
    text = f"{item['title']} {item['description']}".lower()
    if contains_any(text, EXCLUDED_TERMS):
        return False
    profile = profile_for(text)
    if profile:
        return True
    signal = contains_any(text, AI_TERMS + MEME_TERMS + BREAKTHROUGH_TERMS)
    if any(term in text for term in GENERIC_TERMS) and not any(term in text for term in ("发布", "上线", "推出", "发现", "突破", "首个", "viral", "热梗")):
        return False
    if any(term in text for term in LOW_SIGNAL_TERMS) and not any(term in text for term in ("launched", "launches", "ships", "released", "unveiled", "deployed", "breakthrough", "发布", "上线", "推出", "发现", "突破", "首个", "首次")):
        return False
    if category in ("中文热梗", "动物表情", "虚拟角色", "AI 生成文化"):
        return signal and len(item["title"]) >= 4
    return signal


def event_similarity(left: str, right: str) -> float:
    a, b = normalize(left), normalize(right)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.92
    return difflib.SequenceMatcher(None, a, b).ratio()


def keywords_for(title: str, text: str, profile: dict[str, Any] | None) -> list[str]:
    if profile:
        return list(profile["keywords"])
    parts = [part.strip(" \t\r\n:：,，。！？!?()（）[]【】") for part in re.split(r"[：:，,。！？!?/|（）()\[\]]+", title)]
    result = [part.strip() for part in parts if 2 <= len(part.strip()) <= 32]
    if not result:
        result = [title[:32].rstrip()]
    if any(term in text.lower() for term in ("agent", "智能体")):
        result.append("AI AGENT")
    return list(dict.fromkeys(result))[:5]


def summary_for(title: str, description: str, profile: dict[str, Any] | None) -> str:
    if profile:
        return str(profile["summary"])
    snippet = clean_text(description)
    snippet = re.sub(r"\s+[-|｜]\s+[^-|｜]{2,40}$", "", snippet).strip()
    if not snippet or snippet == title:
        return f"报道围绕“{title}”展开，当前只确认到公开标题和发布时间，原文上下文仍需人工核验。"
    return f"{snippet[:250]}。"


def why_for(title: str, text: str, profile: dict[str, Any] | None, source_count: int) -> str:
    if profile:
        return str(profile["why"])
    features = narrative_features(text) or ["主题明确"]
    evidence = "、".join(features)
    verification = "已有多个独立来源交叉出现" if source_count >= 2 else "目前只有单一来源，先当作待核验线索"
    return f"该条目具备{evidence}，可能形成可复述的社区叙事；{verification}。"


def previous_report() -> dict[str, Any]:
    try:
        return json.loads(NEWS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_report(report_date: date) -> dict[str, Any]:
    discovered: list[dict[str, Any]] = []
    # A slow publisher should not block every other discovery source.
    with ThreadPoolExecutor(max_workers=8) as executor:
        fetched = list(zip(DISCOVERY_SOURCES, executor.map(fetch_source, DISCOVERY_SOURCES)))
    for source, source_items in fetched:
        for item in source_items:
            if item_date(item) != report_date or not is_relevant(item, source["category"]):
                continue
            title = strip_source_suffix(item["title"], item["source"])
            text = f"{title} {item['description']}"
            discovered.append({**item, "title": title, "category": category_for(text, source["category"], profile_for(text)), "tier": source_tier(item["source"], source["tier"]), "discovery": source["name"]})

    groups: list[list[dict[str, Any]]] = []
    for item in discovered:
        profile = profile_for(f"{item['title']} {item['description']}")
        key = profile["name"] if profile else item["title"]
        matching: list[dict[str, Any]] | None = None
        for group in groups:
            existing = group[0]
            existing_profile = profile_for(f"{existing['title']} {existing['description']}")
            existing_key = existing_profile["name"] if existing_profile else existing["title"]
            if key == existing_key or event_similarity(key, existing_key) >= 0.78:
                matching = group
                break
        (matching if matching is not None else groups.append([]) or groups[-1]).append(item)

    old = previous_report()
    old_events = old.get("events", []) if isinstance(old, dict) else []
    old_by_signal = {str(event.get("canonicalSignal") or event.get("title")): event for event in old_events if isinstance(event, dict)}
    events: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        group.sort(key=lambda item: (item["tier"] == "官方源", item["tier"] == "主流科技媒体"), reverse=True)
        lead = group[0]
        text = " ".join(f"{item['title']} {item['description']}" for item in group)
        profile = profile_for(text)
        canonical = str(profile["name"] if profile else lead["title"])
        sources: list[dict[str, str]] = []
        seen_sources: set[str] = set()
        for item in group:
            source_name = item["source"] or item["discovery"]
            source_key = normalize(source_name)
            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)
            sources.append({"name": source_name, "url": item["link"], "tier": item["tier"], "publishedAt": item.get("published", "")})
        independent = sorted({source["name"] for source in sources})
        source_count = len(independent)
        tiers = {source["tier"] for source in sources}
        prior = old_by_signal.get(canonical)
        status = "再热" if prior else "新热"
        if prior and prior.get("status") in ("再热", "持续传播"):
            status = "持续传播"
        first_seen = str((prior or {}).get("firstSeenAt") or (prior or {}).get("occurredAt") or report_date)
        confidence = "高" if source_count >= 2 or "官方源" in tiers else ("中" if "主流科技媒体" in tiers else "低")
        features = narrative_features(text)
        score = 1 + (4 if profile else 0) + (2 if source_count >= 2 else 0) + (2 if "官方源" in tiers else 0) + (1 if "主流科技媒体" in tiers else 0) + min(2, len(features))
        if lead["category"] in ("中文热梗", "动物表情", "虚拟角色", "AI 生成文化"):
            score += 1
        if confidence == "低":
            score -= 1
        priority = "S" if score >= 8 else ("A" if score >= 5 else "B")
        risk = str(profile["risk"]) if profile else ("单一来源，需人工核验原文和传播范围" if confidence == "低" else "自动聚合，仍需核对原始来源与语境")
        chain_fit = str(profile["chainFit"]) if profile else ("中" if features else "待核验")
        event_id = f"{report_date}-{index}-{normalize(canonical)[:42]}"
        events.append({
            "id": event_id, "title": canonical if profile else lead["title"], "canonicalSignal": canonical,
            "category": lead["category"], "priority": priority, "status": status,
            "occurredAt": str(report_date), "firstSeenAt": first_seen, "recentPropagationAt": str(report_date),
            "summary": summary_for(canonical if profile else lead["title"], lead["description"], profile),
            "why": why_for(canonical if profile else lead["title"], text, profile, source_count),
            "keywords": keywords_for(canonical if profile else lead["title"], text, profile), "sources": sources,
            "sourceCount": source_count, "independentSources": independent,
            "verification": f"{source_count} 个独立来源 · {confidence}置信度", "confidence": confidence,
            "risk": risk, "chainFit": chain_fit,
        })

    priority_rank = {"S": 0, "A": 1, "B": 2}
    events.sort(key=lambda event: (priority_rank.get(str(event["priority"]), 3), -int(event["sourceCount"]), str(event["title"])))
    events = events[:40]
    if events:
        top_titles = "；".join(str(event["title"]) for event in events[:3])
        headline = f"昨日捕捉到 {len(events)} 条经过分层验证的 AI 与互联网文化信号"
        summary = f"优先查看：{top_titles}。先核对独立来源、原始发布时间和链上创建时间，再判断是否值得继续追踪。"
    else:
        headline = "昨日暂无足够可靠的新增重点"
        summary = "没有符合主题、日期明确且达到最低相关性的公开条目；系统没有用旧新闻填充。"
    source_count = len({source["name"] for event in events for source in event["sources"]})
    return {"demo": False, "reportDate": str(report_date), "generatedAt": datetime.now(LOCAL_ZONE).isoformat(timespec="seconds"), "headline": headline, "summary": summary, "sourceCount": source_count, "events": events}


def markdown_for_report(report: dict[str, Any]) -> str:
    lines = [f"# Signal Desk · {report['reportDate']}", "", str(report["summary"]), "", "## 今日重点关注", ""]
    events = report["events"]
    if not events:
        lines.append("昨日暂无足够可靠的新增重点。")
    for index, event in enumerate(events, start=1):
        lines.extend([
            f"### {index}. [{event['priority']}级] {event['title']}",
            f"- 类别：{event['category']} · 状态：{event['status']} · 日期：{event['occurredAt']}",
            f"- 摘要：{event['summary']}", f"- 为什么值得看：{event['why']}",
            f"- 验证：{event['verification']}（{', '.join(event['independentSources']) or '无'}）",
            f"- 检索词：{', '.join(event['keywords'])}", f"- 风险：{event['risk']} · 链上适配度：{event['chainFit']}",
            "- 来源：" + ", ".join(f"[{source['name']}]({source['url']})" for source in event["sources"]), "",
        ])
    lines.extend(["## 人工核验提醒", "", "传播度不等于代币价值。请核对代币创建时间、是否有明显龙头、流动性、持仓集中度、部署者历史、撤池风险，以及品牌/IP/人物形象的版权风险。"])
    return "\n".join(lines) + "\n"


def write_markdown(report: dict[str, Any]) -> None:
    """Write the current report and keep a dated copy for the archive UI."""
    content = markdown_for_report(report)
    REPORT_FILE.write_text(content, encoding="utf-8")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = REPORTS_DIR / f"{report['reportDate']}.md"
    archive_path.write_text(content, encoding="utf-8")
    (DATA_DIR / archive_path.name).write_text(content, encoding="utf-8")

    reports: list[dict[str, str]] = []
    for path in sorted(REPORTS_DIR.glob("*.md"), reverse=True):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem):
            continue
        text = path.read_text(encoding="utf-8")
        heading = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
        reports.append({"date": path.stem, "title": heading.group(1).strip() if heading else "Signal Desk 日报"})
    ARCHIVE_INDEX_FILE.write_text(json.dumps({"reports": reports, "lastUpdated": reports[0]["date"] if reports else None}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
