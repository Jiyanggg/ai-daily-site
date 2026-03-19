/**
 * LIU冀杨的科技日报 - Frontend App v3
 * Multi-topic daily intelligence report viewer.
 */
(function () {
  const BASE = '';
  const reportContent = document.getElementById('reportContent');
  const reportNav = document.getElementById('reportNav');
  const tocList = document.getElementById('tocList');
  const topicTabs = document.getElementById('topicTabs');
  const backToTop = document.getElementById('backToTop');

  let currentReports = [];
  let currentDate = '';
  let currentTopic = 'all';

  marked.setOptions({ breaks: true, gfm: true });

  // ─── Data loading ──────────────────────────────────────────
  async function loadIndex() {
    try {
      const res = await fetch(`${BASE}/data/reports-index.json`);
      if (!res.ok) throw new Error();
      return await res.json();
    } catch { return null; }
  }

  async function loadReport(date) {
    try {
      const res = await fetch(`${BASE}/data/${date}.md`);
      if (!res.ok) throw new Error();
      return await res.text();
    } catch { return null; }
  }

  // ─── Helpers ───────────────────────────────────────────────
  function formatDate(dateStr) {
    const d = new Date(dateStr + 'T00:00:00');
    const m = d.getMonth() + 1, day = d.getDate();
    const wd = ['日','一','二','三','四','五','六'][d.getDay()];
    return `${m}月${day}日 周${wd}`;
  }

  /** Detect topic of an h2 based on its text content */
  function detectTopic(text) {
    const t = text.toLowerCase();
    if (/ai|人工智能|技术|产品|youtube|twitter|开发|编程|模型|gpu|芯片/.test(t)) return 'ai';
    if (/科学|研究|物理|生物|医|化学|太空|量子|nature|science|基因|天文/.test(t)) return 'science';
    if (/地缘|政治|军事|外交|制裁|冲突|战争/.test(t)) return 'geopolitics';
    if (/经济|宏观|金融|市场|央行|gdp|关税|贸易|利率|通胀|股市/.test(t)) return 'economy';
    if (/总结|趋势|更多|关注/.test(t)) return 'summary';
    return '';
  }

  // ─── Date navigation ───────────────────────────────────────
  function renderDateNav(reports, activeDate) {
    reportNav.innerHTML = '';
    reports.forEach(r => {
      const el = document.createElement('a');
      el.className = 'nav-item' + (r.date === activeDate ? ' active' : '');
      el.textContent = formatDate(r.date);
      el.href = `#${r.date}`;
      el.addEventListener('click', e => {
        e.preventDefault();
        showReport(r.date, reports);
        history.pushState(null, '', `#${r.date}`);
      });
      reportNav.appendChild(el);
    });
  }

  // ─── Topic tabs ────────────────────────────────────────────
  function initTopicTabs() {
    topicTabs.querySelectorAll('.topic-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        currentTopic = btn.dataset.topic;
        topicTabs.querySelectorAll('.topic-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        filterSections();
      });
    });
  }

  function filterSections() {
    const sections = reportContent.querySelectorAll('[data-topic]');
    sections.forEach(sec => {
      if (currentTopic === 'all' || sec.dataset.topic === currentTopic || sec.dataset.topic === 'summary') {
        sec.style.display = '';
      } else {
        sec.style.display = 'none';
      }
    });
    // Update TOC visibility
    tocList.querySelectorAll('.toc-link').forEach(link => {
      const topic = link.dataset.topic || '';
      if (currentTopic === 'all' || topic === currentTopic || topic === 'summary') {
        link.style.display = '';
      } else {
        link.style.display = 'none';
      }
    });
  }

  // ─── TOC sidebar ───────────────────────────────────────────
  function buildToc(container) {
    tocList.innerHTML = '';
    const h2s = container.querySelectorAll('h2[id]');
    h2s.forEach(h2 => {
      const a = document.createElement('a');
      a.className = 'toc-link';
      a.textContent = h2.textContent.trim();
      a.href = `#${h2.id}`;
      a.dataset.topic = h2.dataset.topic || '';
      a.addEventListener('click', e => {
        e.preventDefault();
        h2.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      tocList.appendChild(a);
    });
  }

  // Highlight current section in TOC on scroll
  function setupScrollSpy() {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          tocList.querySelectorAll('.toc-link').forEach(l => l.classList.remove('active'));
          const active = tocList.querySelector(`.toc-link[href="#${id}"]`);
          if (active) active.classList.add('active');
        }
      });
    }, { rootMargin: '-80px 0px -70% 0px' });

    reportContent.querySelectorAll('h2[id]').forEach(h2 => observer.observe(h2));
  }

  // ─── Render report ─────────────────────────────────────────
  async function showReport(date, reports) {
    currentDate = date;
    reportContent.innerHTML = '<div class="loading">加载中...</div>';
    tocList.innerHTML = '';
    renderDateNav(reports, date);

    const md = await loadReport(date);
    if (!md) {
      reportContent.innerHTML = '<div class="loading">暂无该日期的日报</div>';
      return;
    }

    let html = marked.parse(md);

    // Style tags
    html = html.replace(/#新闻/g, '<span class="tag tag-news">#新闻</span>');
    html = html.replace(/#干货/g, '<span class="tag tag-deep">#干货</span>');
    html = html.replace(/#吃瓜/g, '<span class="tag tag-drama">#吃瓜</span>');

    // Style "骡子点评" lines
    html = html.replace(/<strong>骡子点评[：:]\s*<\/strong>\s*/g,
      '<strong class="comment-label">骡子点评：</strong>');

    // Style "来源：xxx" lines
    html = html.replace(/<strong>来源[：:]\s*(.*?)<\/strong>/g,
      '<span class="source-badge">$1</span>');

    // Process h2s: add IDs, topic classes, and wrap sections
    const temp = document.createElement('div');
    temp.innerHTML = html;

    const allH2 = temp.querySelectorAll('h2');
    allH2.forEach((h2, i) => {
      const id = 'sec-' + i;
      h2.id = id;
      const topic = detectTopic(h2.textContent);
      if (topic) {
        h2.classList.add('topic-' + topic);
        h2.dataset.topic = topic;
      }
    });

    // Wrap each h2 + its content in a section with data-topic
    const children = Array.from(temp.childNodes);
    const wrapped = document.createElement('div');
    let currentSection = null;

    children.forEach(node => {
      if (node.nodeType === 1 && node.tagName === 'H2') {
        currentSection = document.createElement('section');
        currentSection.dataset.topic = node.dataset.topic || '';
        currentSection.appendChild(node);
        wrapped.appendChild(currentSection);
      } else if (currentSection) {
        currentSection.appendChild(node);
      } else {
        wrapped.appendChild(node);
      }
    });

    reportContent.innerHTML = wrapped.innerHTML;

    // Build TOC & scroll spy
    buildToc(reportContent);
    setupScrollSpy();
    filterSections();
  }

  // ─── Back to top ───────────────────────────────────────────
  window.addEventListener('scroll', () => {
    backToTop.classList.toggle('visible', window.scrollY > 400);
  });
  backToTop.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // ─── Init ──────────────────────────────────────────────────
  async function init() {
    initTopicTabs();

    const index = await loadIndex();
    if (!index || !index.reports || index.reports.length === 0) {
      reportContent.innerHTML = '<div class="loading">暂无日报数据。首篇日报将在明早 07:30 自动发布。</div>';
      return;
    }

    currentReports = index.reports.sort((a, b) => b.date.localeCompare(a.date));
    const hash = location.hash.replace('#', '');
    const target = currentReports.find(r => r.date === hash) ? hash : currentReports[0].date;
    showReport(target, currentReports);
  }

  window.addEventListener('popstate', init);
  init();
})();
