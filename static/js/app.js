/* ═══════════════════════════════════════
   AI News Aggregator — Main JS
   ═══════════════════════════════════════ */

const API = '';
let currentFilters = { market: null, sentiment: null, source: null, highlight: false };
let currentSort = 'impact'; // 'impact' or 'time'
let autoRefreshTimer = null;
let marketRefreshTimer = null;
const REFRESH_INTERVAL = 30 * 1000; // 30 seconds
let searchDebounce = null;
let currentSearch = '';

// ── State ──────────────────────────
const state = {
  news: [],
  stats: null,
  sources: [],
  trending: [],
  loading: false,
  lastRefresh: 0,
};

// ── Source Colors ──────────────────
const SOURCE_COLORS = {
  "CNBC": "#005594",
  "Wall Street Journal": "#000000",
  "CoinTelegraph": "#F7931A",
  "TechCrunch": "#0A9B0A",
  "The Verge": "#EA4C89",
  "Hacker News": "#FF6600",
  "Yahoo Finance": "#7B0099",
  "36氪": "#0088FF",
  "IT之家": "#D4213D",
  "少数派": "#D71A1B",
};

function getSourceColor(source) {
  return SOURCE_COLORS[source] || '#6b6560';
}

// ── Theme ──────────────────────────
function initTheme() {
  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
  updateThemeIcon(theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = theme === 'dark' ? '☀' : '◐';
}

// ── API Calls ──────────────────────
async function fetchNews() {
  state.loading = true;
  renderSkeleton();

  try {
    const params = new URLSearchParams();
    params.set('limit', '100');
    if (currentFilters.market) params.set('market', currentFilters.market);
    if (currentFilters.sentiment) params.set('sentiment', currentFilters.sentiment);
    if (currentFilters.source) params.set('source', currentFilters.source);
    if (currentFilters.highlight) params.set('highlight', 'true');
    if (currentSearch) params.set('search', currentSearch);
    if (currentSort) params.set('sort', currentSort);

    const [newsRes, statsRes, trendingRes] = await Promise.all([
      fetch(`${API}/api/news?${params}`),
      fetch(`${API}/api/stats`),
      fetch(`${API}/api/trending`),
    ]);

    const newsData = await newsRes.json();
    const statsData = await statsRes.json();
    const trendingData = await trendingRes.json();

    state.news = newsData.items;
    state.stats = statsData;
    state.trending = trendingData.topics || [];
    state.lastRefresh = Date.now();

    renderStats();
    renderTrending();
    renderNews();
    renderSidebar();
    updateRefreshTime();
    updateLastUpdateIndicator();
  } catch (err) {
    console.error('Failed to fetch:', err);
    renderError('加载失败，请稍后重试');
  } finally {
    state.loading = false;
  }
}

async function fetchSources() {
  try {
    const res = await fetch(`${API}/api/sources`);
    const data = await res.json();
    state.sources = data.sources;
    renderSidebar();
  } catch (err) {
    console.error('Failed to fetch sources:', err);
  }
}

async function triggerRefresh() {
  const btn = document.getElementById('refreshBtn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="loading-spinner" style="width:14px;height:14px;border-width:2px;margin:0"></span> 刷新中...';
  }
  try {
    await fetch(`${API}/api/refresh`, { method: 'POST' });
    await fetchNews();
    await fetchSources();
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '⟳ 刷新';
    }
  }
}

// ── Search ─────────────────────────
function initSearch() {
  const input = document.getElementById('searchInput');
  const clearBtn = document.getElementById('searchClear');

  if (input) {
    input.addEventListener('input', (e) => {
      const value = e.target.value.trim();
      clearBtn.style.display = value ? 'block' : 'none';

      // Debounce search
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => {
        if (value !== currentSearch) {
          currentSearch = value;
          fetchNews();
        }
      }, 400);
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        input.value = '';
        clearBtn.style.display = 'none';
        if (currentSearch) {
          currentSearch = '';
          fetchNews();
        }
      }
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      input.value = '';
      clearBtn.style.display = 'none';
      if (currentSearch) {
        currentSearch = '';
        fetchNews();
      }
      input.focus();
    });
  }
}

// ── Modal ──────────────────────────
function openModal(item) {
  const modal = document.getElementById('articleModal');
  if (!modal) return;

  document.getElementById('modalSource').textContent = item.source;
  document.getElementById('modalTime').textContent = formatTimeAgo(item.published_at);
  document.getElementById('modalTitle').textContent = item.title_zh || item.title;
  document.getElementById('modalSummary').textContent = item.summary_zh || item.summary || '暂无摘要';

  // Tags
  const tagsEl = document.getElementById('modalTags');
  const markets = (item.markets || '').split(',').filter(Boolean);
  const tags = (item.tags || '').split(',').filter(Boolean);
  const topicTags = tags.filter(t => !markets.includes(t));

  tagsEl.innerHTML = [
    ...markets.map(t => `<span class="tag tag-market">${escapeHtml(t)}</span>`),
    ...topicTags.map(t => `<span class="tag tag-topic">${escapeHtml(t)}</span>`),
  ].join('');

  // Sentiment
  const sentimentEl = document.getElementById('modalSentiment');
  const sentimentMap = { bullish: '📈 看涨', bearish: '📉 看跌', neutral: '➖ 中性' };
  sentimentEl.textContent = sentimentMap[item.sentiment] || '➖ 中性';
  sentimentEl.className = `modal-sentiment ${item.sentiment}`;

  // Impact
  const impactEl = document.getElementById('modalImpact');
  const impactLevel = item.impact_score >= 60 ? 'high' : item.impact_score >= 35 ? 'medium' : 'low';
  impactEl.textContent = `影响力: ${item.impact_score}`;
  impactEl.className = `modal-impact impact-${impactLevel}`;

  // Link
  document.getElementById('modalLink').href = item.link;

  // Show modal
  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  const modal = document.getElementById('articleModal');
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
}

function initModal() {
  const modal = document.getElementById('articleModal');
  const closeBtn = document.getElementById('modalClose');

  if (closeBtn) {
    closeBtn.addEventListener('click', closeModal);
  }

  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });
}

// ── Rendering ──────────────────────
function renderStats() {
  const el = document.getElementById('statsBar');
  if (!el || !state.stats) return;

  const s = state.stats;
  const sentiment = s.sentiments || {};

  el.innerHTML = `
    <div class="stat-chip">
      <div><div class="value">${s.total || 0}</div><div class="label">总新闻</div></div>
    </div>
    <div class="stat-chip">
      <div><div class="value" style="color:var(--amber)">${s.highlights || 0}</div><div class="label">重要快讯</div></div>
    </div>
    <div class="stat-chip">
      <div><div class="value" style="color:var(--red)">${sentiment.bullish || 0}</div><div class="label">看涨</div></div>
    </div>
    <div class="stat-chip">
      <div><div class="value" style="color:var(--green)">${sentiment.bearish || 0}</div><div class="label">看跌</div></div>
    </div>
    <div class="stat-chip">
      <div><div class="value">${Object.keys(s.sources || {}).length}</div><div class="label">信息源</div></div>
    </div>
  `;
}

function renderTrending() {
  const container = document.getElementById('newsContainer');
  if (!container || !state.trending.length || currentSearch) return;

  // We'll render trending inside the news container, before news
  // Store for later use in renderNews
}

function renderSkeleton() {
  const container = document.getElementById('newsContainer');
  if (!container) return;

  const skeletons = Array(6).fill(0).map(() => `
    <div class="skeleton-card">
      <div style="display:flex;justify-content:space-between">
        <div class="skeleton skeleton-line w-60 h-8" style="width:80px;height:8px"></div>
        <div class="skeleton" style="width:18px;height:18px;border-radius:50%"></div>
      </div>
      <div class="skeleton skeleton-line w-100"></div>
      <div class="skeleton skeleton-line w-80"></div>
      <div class="skeleton skeleton-line w-60" style="height:10px"></div>
    </div>
  `).join('');

  container.innerHTML = `<div class="news-grid">${skeletons}</div>`;
}

function renderNews() {
  const container = document.getElementById('newsContainer');
  if (!container) return;

  let html = '';

  // Active filter indicator
  const hasFilter = currentFilters.market || currentFilters.sentiment || currentFilters.source || currentFilters.highlight;
  if (hasFilter) {
    const filterLabels = [];
    if (currentFilters.market) filterLabels.push(currentFilters.market);
    if (currentFilters.sentiment) filterLabels.push(currentFilters.sentiment === 'bullish' ? '看涨' : currentFilters.sentiment === 'bearish' ? '看跌' : '中性');
    if (currentFilters.source) filterLabels.push(currentFilters.source);
    if (currentFilters.highlight) filterLabels.push('重要快讯');
    html += `
      <div class="filter-indicator">
        <span class="filter-label">筛选: ${filterLabels.join(' + ')}</span>
        <span class="filter-count">${state.news.length} 条</span>
        <button class="filter-clear-btn" onclick="clearFilters()">✕ 清除筛选</button>
      </div>
    `;
  }

  // Search results indicator
  if (currentSearch) {
    html += `
      <div class="search-results-info">
        🔍 搜索 "<strong>${escapeHtml(currentSearch)}</strong>" — 找到 ${state.news.length} 条结果
        <button class="filter-clear-btn" onclick="clearFilters()">✕ 清除</button>
      </div>
    `;
  }

  // Trending topics
  if (state.trending.length && !currentSearch) {
    html += `
      <div class="trending-section">
        <div class="trending-title">🔥 热门话题</div>
        <div class="trending-tags">
          ${state.trending.slice(0, 12).map(t => `
            <div class="trending-tag" onclick="searchByTopic('${escapeHtml(t.topic)}')">
              ${escapeHtml(t.topic)}
              <span class="trending-count">${t.count}</span>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  if (!state.news.length) {
    html += `
      <div class="empty-state">
        <div style="font-size:2rem;margin-bottom:12px">📭</div>
        <div>${currentSearch ? '没有找到匹配的新闻' : '暂无新闻数据'}</div>
        <div style="margin-top:8px;font-size:0.8rem">${currentSearch ? '试试其他关键词' : '点击刷新按钮获取最新资讯'}</div>
      </div>
    `;
    container.innerHTML = html;
    return;
  }

  // Split into highlights and regular
  const highlights = state.news.filter(n => n.is_highlight);
  const regular = state.news.filter(n => !n.is_highlight);

  if (highlights.length && !currentFilters.highlight) {
    html += `
      <div class="section-header">
        <div class="section-title">⚡ 重要快讯</div>
        <div class="section-badge">${highlights.length}</div>
      </div>
      <div class="news-grid">${highlights.map(renderCard).join('')}</div>
    `;
  }

  if (regular.length || currentFilters.highlight) {
    const items = currentFilters.highlight ? highlights : regular;
    if (items.length) {
      html += `
        <div class="section-header">
          <div class="section-title">📰 最新资讯</div>
        </div>
        <div class="news-grid">${items.map(renderCard).join('')}</div>
      `;
    }
  }

  container.innerHTML = html;
}

function renderCard(item) {
  const sentimentClass = `sentiment-${item.sentiment}`;
  const sentimentIcon = item.sentiment === 'bullish' ? '▲' : item.sentiment === 'bearish' ? '▼' : '—';

  const impactLevel = item.impact_score >= 60 ? 'high' : item.impact_score >= 35 ? 'medium' : 'low';

  const markets = (item.markets || '').split(',').filter(Boolean);
  const tags = (item.tags || '').split(',').filter(Boolean);

  const timeAgo = formatTimeAgo(item.published_at);
  const cardClass = `news-card ${item.is_highlight ? 'highlight' : ''} ${item.sentiment !== 'neutral' ? item.sentiment : ''}`;

  const topicTags = tags.filter(t => !markets.includes(t));
  const marketTags = markets;

  const sourceColor = getSourceColor(item.source);

  // Use onclick to open modal instead of direct link
  const displayTitle = item.title_zh || item.title;
  const displaySummary = item.summary_zh || item.summary;
  const isTranslated = !!item.title_zh;
  const langBadge = (!isTranslated && item.lang === 'en') ? ' <span class="lang-badge" title="未翻译">🌐 EN</span>' : '';

  return `
    <div class="${cardClass}" onclick='openModal(${JSON.stringify(item).replace(/'/g, "&#39;")})'>
      <div class="news-card-header">
        <span class="news-source-badge">
          <span class="news-source-dot" style="background:${sourceColor}"></span>
          ${escapeHtml(item.source)}${langBadge}
        </span>
        <div class="sentiment-icon ${sentimentClass}">${sentimentIcon}</div>
      </div>
      <div class="news-title">${escapeHtml(displayTitle)}</div>
      ${displaySummary ? `<div class="news-summary">${escapeHtml(displaySummary.slice(0, 150))}${displaySummary.length > 150 ? '...' : ''}</div>` : ''}
      <div class="news-meta">
        <div class="news-tags">
          ${marketTags.map(t => `<span class="tag tag-market">${escapeHtml(t)}</span>`).join('')}
          ${item.sentiment === 'bullish' ? '<span class="tag tag-bullish">看涨</span>' : ''}
          ${item.sentiment === 'bearish' ? '<span class="tag tag-bearish">看跌</span>' : ''}
          ${topicTags.slice(0, 2).map(t => `<span class="tag tag-topic">${escapeHtml(t)}</span>`).join('')}
        </div>
        <span class="impact-badge impact-${impactLevel}">${item.impact_score}</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span class="news-time">${timeAgo}</span>
      </div>
    </div>
  `;
}

function renderSidebar() {
  const el = document.getElementById('sidebarContent');
  if (!el || !state.stats) return;

  const markets = state.stats.markets || {};
  const sources = state.stats.sources || {};

  const marketItems = [
    { key: null, label: '全部', icon: '🌐' },
    { key: 'A股', label: 'A股', icon: '🇨🇳' },
    { key: '港股', label: '港股', icon: '🇭🇰' },
    { key: '美股', label: '美股', icon: '🇺🇸' },
    { key: '币圈', label: '币圈', icon: '₿' },
    { key: '综合', label: '综合', icon: '📊' },
  ];

  const sentimentItems = [
    { key: null, label: '全部情绪', icon: '' },
    { key: 'bullish', label: '看涨', icon: '', dotClass: 'dot-bullish' },
    { key: 'bearish', label: '看跌', icon: '', dotClass: 'dot-bearish' },
    { key: 'neutral', label: '中性', icon: '', dotClass: 'dot-neutral' },
  ];

  el.innerHTML = `
    <div class="sidebar-section">
      <div class="sidebar-section-title">市场</div>
      ${marketItems.map(m => `
        <div class="sidebar-item ${currentFilters.market === m.key ? 'active' : ''}"
             onclick="setFilter('market', ${m.key ? `'${m.key}'` : 'null'})">
          <span>${m.icon}</span>
          <span>${m.label}</span>
          ${m.key && markets[m.key] ? `<span class="count">${markets[m.key]}</span>` : ''}
        </div>
      `).join('')}
    </div>

    <div class="sidebar-section">
      <div class="sidebar-section-title">情绪</div>
      ${sentimentItems.map(s => `
        <div class="sidebar-item ${currentFilters.sentiment === s.key ? 'active' : ''}"
             onclick="setFilter('sentiment', ${s.key ? `'${s.key}'` : 'null'})">
          ${s.dotClass ? `<span class="dot ${s.dotClass}"></span>` : '<span style="width:7px"></span>'}
          <span>${s.label}</span>
        </div>
      `).join('')}
    </div>

    <div class="sidebar-section">
      <div class="sidebar-section-title">特殊筛选</div>
      <div class="sidebar-item ${currentFilters.highlight ? 'active' : ''}"
           onclick="toggleHighlight()">
        <span>⚡</span>
        <span>仅看重要快讯</span>
        ${state.stats.highlights ? `<span class="count">${state.stats.highlights}</span>` : ''}
      </div>
    </div>

    ${Object.keys(sources).length ? `
      <div class="sidebar-section">
        <div class="sidebar-section-title">信息源</div>
        ${Object.entries(sources).slice(0, 15).map(([name, count]) => `
          <div class="sidebar-item ${currentFilters.source === name ? 'active' : ''}"
               onclick="setFilter('source', ${currentFilters.source === name ? 'null' : `'${name}'`})">
            <span class="news-source-dot" style="background:${getSourceColor(name)};width:6px;height:6px;border-radius:50%;flex-shrink:0"></span>
            <span style="font-size:0.82rem">${escapeHtml(name)}</span>
            <span class="count">${count}</span>
          </div>
        `).join('')}
      </div>
    ` : ''}
  `;
}

function renderLoading() {
  const el = document.getElementById('newsContainer');
  if (el) {
    el.innerHTML = `
      <div class="loading-state">
        <div class="loading-spinner"></div>
        <div>正在加载最新资讯...</div>
      </div>
    `;
  }
}

function renderError(msg) {
  const el = document.getElementById('newsContainer');
  if (el) {
    el.innerHTML = `<div class="empty-state"><div style="font-size:2rem;margin-bottom:12px">⚠️</div><div>${msg}</div></div>`;
  }
}

// ── Page Switching ─────────────────
function switchPage(page) {
  console.log('Switching to page:', page);
  document.querySelectorAll('.page-tab').forEach(t => t.classList.toggle('active', t.dataset.page === page));
  const newsEl = document.getElementById('newsContainer');
  const statsEl = document.getElementById('statsBar');
  const monitorEl = document.getElementById('monitorPage');
  const marketEl = document.getElementById('marketBar');
  const headerRight = document.querySelector('.header-right');

  if (page === 'monitor') {
    newsEl.style.display = 'none';
    statsEl.style.display = 'none';
    marketEl.style.display = 'none';
    headerRight.style.display = 'none';
    monitorEl.style.display = 'block';
    monitorEl.style.height = 'calc(100vh - 120px)';
    const frame = document.getElementById('monitorFrame');
    const src = frame.getAttribute('src');
    console.log('Frame src:', src);
    if (!src || src === '' || src === 'about:blank') {
      frame.src = '/static/monitor.html';
      console.log('Setting frame src to /static/monitor.html');
    }
  } else {
    newsEl.style.display = '';
    statsEl.style.display = '';
    marketEl.style.display = '';
    headerRight.style.display = '';
    monitorEl.style.display = 'none';
  }
}

// ── Market Data ────────────────────
async function fetchMarket() {
  try {
    const resp = await fetch('/api/market?t=' + Date.now());
    const data = await resp.json();
    renderMarket(data.indices || []);
  } catch (e) {
    console.warn('Market fetch failed:', e);
  }
}

function renderMarket(indices) {
  const el = document.getElementById('marketBar');
  if (!el || !indices.length) return;

  el.innerHTML = indices.map(idx => {
    const isUp = idx.change >= 0;
    const sign = isUp ? '+' : '';
    const cls = isUp ? 'market-up' : 'market-down';
    // 中国市场红涨绿跌
    const color = isUp ? 'var(--red)' : 'var(--green)';
    return `
      <div class="market-item">
        <span class="market-name">${idx.name}</span>
        <span class="market-price" style="color:${color}">${idx.price.toLocaleString()}</span>
        <span class="market-change ${cls}">${sign}${idx.change.toFixed(2)} (${sign}${idx.change_pct.toFixed(2)}%)</span>
      </div>
    `;
  }).join('');
}

// ── Filters ────────────────────────
function setFilter(type, value) {
  if (type === 'market') currentFilters.market = value;
  if (type === 'sentiment') currentFilters.sentiment = value;
  if (type === 'source') currentFilters.source = value;
  fetchNews();
}

function toggleHighlight() {
  currentFilters.highlight = !currentFilters.highlight;
  fetchNews();
}

function setSort(sort) {
  currentSort = sort;
  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.sort === sort);
  });
  fetchNews();
}

function clearFilters() {
  currentFilters = { market: null, sentiment: null, source: null, highlight: false };
  currentSearch = '';
  currentSort = 'impact';
  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.sort === 'impact');
  });
  const input = document.getElementById('searchInput');
  if (input) input.value = '';
  const clearBtn = document.getElementById('searchClear');
  if (clearBtn) clearBtn.style.display = 'none';
  fetchNews();
}

function searchByTopic(topic) {
  const input = document.getElementById('searchInput');
  if (input) {
    input.value = topic;
    const clearBtn = document.getElementById('searchClear');
    if (clearBtn) clearBtn.style.display = 'block';
  }
  currentSearch = topic;
  fetchNews();
}

// ── Utilities ──────────────────────
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatTimeAgo(dateStr) {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMin = Math.floor(diffMs / 60000);
    const diffHr = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);

    if (diffMin < 1) return '刚刚';
    if (diffMin < 60) return `${diffMin}分钟前`;
    if (diffHr < 24) return `${diffHr}小时前`;
    if (diffDay < 7) return `${diffDay}天前`;
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

function updateRefreshTime() {
  const el = document.getElementById('refreshTime');
  if (el && state.lastRefresh) {
    const d = new Date(state.lastRefresh);
    el.textContent = `更新于 ${d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`;
  }
}

function updateLastUpdateIndicator() {
  const el = document.getElementById('lastUpdateIndicator');
  if (el && state.lastRefresh) {
    const d = new Date(state.lastRefresh);
    el.textContent = `最后更新: ${d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
  }
}

// ── Auto Refresh ───────────────────
function startAutoRefresh() {
  const bar = document.querySelector('.auto-refresh-bar .progress');
  let elapsed = 0;

  if (autoRefreshTimer) clearInterval(autoRefreshTimer);

  autoRefreshTimer = setInterval(() => {
    elapsed += 1000;
    const pct = (elapsed / REFRESH_INTERVAL) * 100;
    if (bar) bar.style.width = `${pct}%`;

    if (elapsed >= REFRESH_INTERVAL) {
      elapsed = 0;
      if (bar) bar.style.width = '0%';
      fetchNews();
    }
  }, 1000);
}

// ── Mobile Sidebar ─────────────────
function toggleSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  sidebar.classList.toggle('open');
  overlay.classList.toggle('open');
}

// ── Init ───────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initSearch();
  initModal();
  fetchMarket();
  // 大盘数据独立刷新，每 10 秒
  clearInterval(marketRefreshTimer);
  marketRefreshTimer = setInterval(fetchMarket, 10 * 1000);
  fetchNews();
  fetchSources();
  startAutoRefresh();

  // Theme toggle
  const themeBtn = document.getElementById('themeToggle');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

  // Refresh button
  const refreshBtn = document.getElementById('refreshBtn');
  if (refreshBtn) refreshBtn.addEventListener('click', triggerRefresh);

  // Sidebar toggle (mobile)
  const sidebarBtn = document.getElementById('sidebarToggle');
  if (sidebarBtn) sidebarBtn.addEventListener('click', toggleSidebar);

  const overlay = document.querySelector('.sidebar-overlay');
  if (overlay) overlay.addEventListener('click', toggleSidebar);
});
