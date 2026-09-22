const bootstrapData = {
  demo: true,
  reportDate: "2026-09-20",
  generatedAt: "2026-09-21T00:00:00+08:00",
  headline: "演示快照：AI Agent、中文热梗与动物表情正在争夺注意力",
  summary: "这是项目首次发布时的演示数据。GitHub Actions 首次运行后，会自动替换为前一天的公开 RSS 新闻；没有可靠新增时不会用旧新闻填充。",
  events: [
    { id: "demo-muse", title: "Meta Muse：能在电脑上执行操作的 AI 助手", category: "AI 科技", priority: "S", status: "演示快照", occurredAt: "2026-09-19", summary: "AI 助手从聊天窗口走进桌面环境，可以处理文件、消息、日历和笔记。", why: "‘AI 有手了’是容易跨圈传播的产品叙事。", keywords: ["META MUSE", "DESKTOP AGENT", "COMPUTER USE"], sources: [{ name: "TechCrunch", url: "https://techcrunch.com/" }], risk: "产品名与商标风险", chainFit: "高" },
    { id: "demo-agents", title: "37,000 个 AI Agent 运行虚拟生物科技实验室", category: "AI 科技", priority: "S", status: "演示快照", occurredAt: "2026-09-18", summary: "大规模 Agent 协作执行生物科技研究任务，形成‘AI 科学家蜂群’叙事。", why: "数字规模明确，容易转化为口号和社区二创。", keywords: ["37000 AGENTS", "VIRTUAL BIOTECH", "AI SCIENTIST SWARM"], sources: [{ name: "HPCwire", url: "https://www.hpcwire.com/" }], risk: "研究结论需核验", chainFit: "高" },
    { id: "demo-iphone18", title: "爱疯18：胡一菲擀面杖手机梗被现实召回", category: "中文热梗", priority: "S", status: "再热", occurredAt: "2026-09-19", summary: "《爱情公寓》里‘爱疯18怎么用’的旧桥段，因为现实产品发布重新进入中文社区。", why: "旧影视记忆与现实事件重叠，具备现成台词、人物和画面。", keywords: ["爱疯18", "胡一菲", "擀面杖手机", "IPHONE 18 MEME"], sources: [{ name: "新浪财经", url: "https://finance.sina.com.cn/" }], risk: "影视版权与品牌风险", chainFit: "高" },
    { id: "demo-pearl", title: "完全澳白大珍珠 / 珍珠拟人", category: "中文热梗", priority: "A", status: "新热", occurredAt: "2026-09-19", summary: "网友用‘完全澳白大珍珠’形容人物妆造，形成可复制的人设标签。", why: "一句话即可完成视觉人格化，适合图片、头像和二创。", keywords: ["完全澳白大珍珠", "珍珠拟人", "AUSTRALIAN PEARL"], sources: [{ name: "新浪财经", url: "https://finance.sina.com.cn/" }], risk: "名人形象与营销争议", chainFit: "中" },
    { id: "demo-opossum", title: "负鼠背手 / 一起毁灭吧", category: "动物表情", priority: "A", status: "常驻再启动", occurredAt: "2026-05-29", summary: "北美负鼠背手直立的照片，被中文社区改写成社畜和摆烂表情。", why: "动物形象、动作和口号三者已经绑定，二创门槛低。", keywords: ["负鼠背手", "一起毁灭吧", "OPOSSUM MEME"], sources: [{ name: "腾讯新闻", url: "https://news.qq.com/" }], risk: "旧梗，需确认是否重新爆发", chainFit: "中" },
    { id: "demo-brainrot", title: "Tung Tung Sahur / AI 脑腐角色", category: "虚拟角色", priority: "A", status: "持续传播", occurredAt: "2026-09-18", summary: "AI 生成的荒诞角色继续在中文社区被翻译、配音和重新命名。", why: "角色名短、图像强、可衍生多个变体，适合跨语言传播。", keywords: ["TUNG TUNG SAHUR", "AI 脑腐", "BRAINROT"], sources: [{ name: "Law360", url: "https://www.law360.com/" }], risk: "版权与商标争议", chainFit: "高" }
  ]
};

const state = { data: bootstrapData, priority: "all", category: "all", query: "" };
const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function formatDate(value) {
  if (!value || value === "demo") return "演示快照";
  const date = new Date(`${value}T00:00:00+08:00`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(date);
}

function formatGeneratedAt(value) {
  if (!value) return "等待自动更新";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `更新于 ${new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date)}`;
}

function filteredEvents() {
  const query = state.query.trim().toLowerCase();
  return (state.data.events || []).filter((event) => {
    const matchesPriority = state.priority === "all" || event.priority === state.priority;
    const matchesCategory = state.category === "all" || event.category === state.category;
    const haystack = [event.title, event.category, event.status, event.summary, event.why, ...(event.keywords || [])].join(" ").toLowerCase();
    return matchesPriority && matchesCategory && (!query || haystack.includes(query));
  });
}

function eventCard(event) {
  const sources = (event.sources || []).map((source) => `<a class="source-link" href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.name)}</a>`).join("");
  const keywords = (event.keywords || []).map((keyword) => `<span class="keyword">${escapeHtml(keyword)}</span>`).join("");
  return `<article class="event-card priority-${escapeHtml(event.priority)}">
    <div class="event-topline"><div class="event-meta"><span class="priority-badge">${escapeHtml(event.priority)} 级</span><span class="category-badge">${escapeHtml(event.category)}</span><span class="status-badge">${escapeHtml(event.status)}</span></div><time class="event-date">${escapeHtml(formatDate(event.occurredAt))}</time></div>
    <h3>${escapeHtml(event.title)}</h3>
    <p class="event-summary">${escapeHtml(event.summary)}</p>
    <div class="event-details"><div><span class="detail-label">为什么值得看</span><p class="detail-text">${escapeHtml(event.why)}</p></div><div><span class="detail-label">检索词</span><div class="keyword-list">${keywords}</div></div></div>
    <div class="event-footer"><span class="risk-label">风险：${escapeHtml(event.risk || "待人工核验")}</span><div class="source-list">${sources}</div></div>
  </article>`;
}

function render() {
  const events = filteredEvents();
  const counts = { S: 0, A: 0, B: 0 };
  const sources = new Set();
  (state.data.events || []).forEach((event) => { if (counts[event.priority] !== undefined) counts[event.priority] += 1; (event.sources || []).forEach((source) => sources.add(source.name)); });
  $("#report-date").textContent = formatDate(state.data.reportDate);
  $("#generated-time").textContent = formatGeneratedAt(state.data.generatedAt);
  $("#report-headline").textContent = state.data.headline || "昨日暂无明确新增重点";
  $("#report-summary").textContent = state.data.summary || "没有足够可靠的新信息。";
  $("#metric-total").textContent = (state.data.events || []).length;
  $("#metric-s").textContent = counts.S;
  $("#metric-a").textContent = counts.A;
  $("#metric-b").textContent = counts.B;
  $("#metric-sources").textContent = sources.size;
  $("#result-count").textContent = `${events.length} 条`;
  $("#event-list").innerHTML = events.map(eventCard).join("");
  $("#empty-state").hidden = events.length > 0;
  document.title = `${state.data.headline || "每日叙事雷达"} · Signal Desk`;
}

function bindFilters() {
  $("#search-input").addEventListener("input", (event) => { state.query = event.target.value; render(); });
  $("#clear-filters").addEventListener("click", () => { state.priority = "all"; state.category = "all"; state.query = ""; $("#search-input").value = ""; document.querySelectorAll(".filter-button").forEach((button) => button.classList.toggle("is-active", button.dataset.priority === "all" || button.dataset.category === "all")); render(); });
  document.querySelectorAll("[data-priority]").forEach((button) => button.addEventListener("click", () => { state.priority = button.dataset.priority; document.querySelectorAll("[data-priority]").forEach((item) => item.classList.toggle("is-active", item === button)); render(); }));
  document.querySelectorAll("[data-category]").forEach((button) => button.addEventListener("click", () => { state.category = button.dataset.category; document.querySelectorAll("[data-category]").forEach((item) => item.classList.toggle("is-active", item === button)); render(); }));
}

async function loadData() {
  try {
    const response = await fetch(`./data/news.json?ts=${Date.now()}`);
    if (!response.ok) throw new Error("news.json unavailable");
    state.data = await response.json();
  } catch (error) {
    console.warn("Using bootstrap data:", error);
  }
  render();
}

bindFilters();
loadData();
