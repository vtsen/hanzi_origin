/* ===================================================
   Hanzi Learning Plan — Single-page app
   Hash routing: #home | #day/N | #search | #overview
   =================================================== */

'use strict';

// ---- Global state ----
let plan = null;       // the loaded plan JSON
let rankMap = null;    // char -> 1-based rank (from char_freq_rank.json)
let freqList = null;   // raw array from char_freq_rank.json

// ---- Bootstrap ----
document.addEventListener('DOMContentLoaded', () => {
  loadData().then(() => {
    initRouter();
    initSearch();
  });
});

// ---- Data loading ----
async function loadData() {
  showLoading(true);
  try {
    const [planRes, rankRes] = await Promise.all([
      fetch('data/plan.json'),
      fetch('data/char_freq_rank.json'),
    ]);

    if (!planRes.ok) throw new Error('Failed to load plan.json');
    if (!rankRes.ok) throw new Error('Failed to load char_freq_rank.json');

    plan = await planRes.json();
    freqList = await rankRes.json();

    // Build char -> rank map (1-based)
    rankMap = {};
    freqList.forEach((ch, i) => { rankMap[ch] = i + 1; });

    showLoading(false);
  } catch (err) {
    document.body.innerHTML = `<div style="padding:3rem;text-align:center;color:#c0392b;">
      <h2>Failed to load data</h2><p>${err.message}</p>
      <p style="margin-top:1rem;color:#666;">Make sure you are serving this folder via HTTP (not file://).</p>
    </div>`;
  }
}

function showLoading(on) {
  const el = document.getElementById('loading-screen');
  if (el) el.style.display = on ? 'flex' : 'none';
}

// ---- Router ----
function initRouter() {
  window.addEventListener('hashchange', route);
  route(); // run on load
}

function route() {
  const hash = window.location.hash.replace('#', '') || 'home';
  updateNavActive(hash);

  if (hash === 'home' || hash === '') {
    showPage('page-home');
    renderHome();
  } else if (hash.startsWith('day/')) {
    const n = parseInt(hash.split('/')[1], 10);
    showPage('page-day');
    renderDay(n);
  } else if (hash === 'search') {
    showPage('page-search');
    focusSearch();
  } else if (hash === 'overview') {
    showPage('page-overview');
    renderOverview();
  } else {
    // Unknown route — go home
    window.location.hash = 'home';
  }
}

function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const el = document.getElementById(id);
  if (el) el.classList.add('active');
  window.scrollTo(0, 0);
}

function updateNavActive(hash) {
  document.querySelectorAll('.nav-links a').forEach(a => {
    a.classList.remove('active');
    const href = a.getAttribute('href').replace('#', '');
    if (hash === href || (href === 'home' && (hash === '' || hash === 'home')) ||
        (href === 'day/1' && hash.startsWith('day/'))) {
      a.classList.add('active');
    }
  });
}

// ---- Home page ----
function renderHome() {
  if (!plan) return;
  const s = plan.stats;

  document.getElementById('stat-chars').textContent = s.total_chars_scheduled.toLocaleString();
  document.getElementById('stat-days').textContent = s.days_used;
  document.getElementById('stat-avg').textContent = plan.params.M;
  document.getElementById('stat-coherence').textContent =
    (s.avg_daily_coherence * 100).toFixed(1) + '%';
}

// ---- Day View ----
let selectedChar = null;

function renderDay(dayNum) {
  if (!plan) return;
  const days = plan.stats.days_used;

  // Clamp to valid range
  if (isNaN(dayNum) || dayNum < 1) dayNum = 1;
  if (dayNum > days) dayNum = days;

  const chars = plan.schedule[String(dayNum)] || [];
  const perDay = plan.stats.per_day.find(d => d.day === dayNum) || {};
  const coherence = perDay.coherence ?? null;

  // Title
  document.getElementById('day-title').textContent = `Day ${dayNum}`;
  document.getElementById('day-input').value = dayNum;

  // Prev/Next buttons
  document.getElementById('btn-prev-day').disabled = dayNum <= 1;
  document.getElementById('btn-next-day').disabled = dayNum >= days;
  document.getElementById('btn-prev-day').onclick = () => goToDay(dayNum - 1);
  document.getElementById('btn-next-day').onclick = () => goToDay(dayNum + 1);

  // Day input handler
  const input = document.getElementById('day-input');
  input.onchange = () => {
    const v = parseInt(input.value, 10);
    if (!isNaN(v)) goToDay(v);
  };
  input.onkeydown = e => { if (e.key === 'Enter') input.dispatchEvent(new Event('change')); };

  // Coherence badge
  const badge = document.getElementById('coherence-badge');
  if (coherence !== null) {
    badge.textContent = `Coherence: ${(coherence * 100).toFixed(1)}%`;
    badge.style.cssText = coherenceBadgeStyle(coherence);
  } else {
    badge.textContent = '';
  }

  // Char count
  document.getElementById('char-count-badge').textContent = `${chars.length} characters`;

  // Hide detail panel on day change
  selectedChar = null;
  document.getElementById('char-detail').classList.remove('visible');

  // Render character grid
  const grid = document.getElementById('char-grid');
  grid.innerHTML = '';
  chars.forEach((ch, idx) => {
    const rank = rankMap[ch] ?? null;
    const card = document.createElement('div');
    card.className = 'char-card';
    card.innerHTML = `
      <span class="char-glyph">${ch}</span>
      <span class="char-rank">${rank ? '#' + rank.toLocaleString() : '—'}</span>
    `;
    card.addEventListener('click', () => selectChar(ch, card, rank, dayNum));
    grid.appendChild(card);
  });
}

function selectChar(ch, card, rank, dayNum) {
  // Toggle selection
  const wasSelected = card.classList.contains('selected');
  document.querySelectorAll('.char-card').forEach(c => c.classList.remove('selected'));

  const detail = document.getElementById('char-detail');
  if (wasSelected) {
    detail.classList.remove('visible');
    selectedChar = null;
    return;
  }

  card.classList.add('selected');
  selectedChar = ch;

  // Populate detail panel
  document.getElementById('detail-glyph').textContent = ch;
  document.getElementById('detail-char-text').textContent = `Character: ${ch}`;
  document.getElementById('detail-rank-text').textContent =
    rank ? `Frequency rank: #${rank.toLocaleString()} out of ${freqList.length.toLocaleString()}` : 'Rank: unknown';
  document.getElementById('detail-day-text').textContent = `Scheduled on: Day ${dayNum}`;
  detail.classList.add('visible');
  detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function goToDay(n) {
  window.location.hash = `day/${n}`;
}

// ---- Coherence color helpers ----
function coherenceColor(coh) {
  // Map coherence 0..1 to a color. We use a blue-based scale.
  // Low coherence (chars unrelated) = lighter; high = deeper blue-green.
  const t = Math.min(1, Math.max(0, coh));
  // Interpolate between #c8e6c9 (low) and #1b5e20 (high) in HSL
  // Low = hsl(120, 40%, 88%)  High = hsl(145, 72%, 22%)
  const hue = 120 + t * 25;
  const sat = 38 + t * 36;
  const lgt = 88 - t * 62;
  return `hsl(${hue}, ${sat}%, ${lgt}%)`;
}

function coherenceBadgeStyle(coh) {
  const bg = coherenceColor(coh);
  // Text: dark for light background, light for dark
  const lgt = 88 - coh * 62;
  const textColor = lgt > 50 ? '#1b5e20' : '#e8f5e9';
  return `background:${bg};color:${textColor};display:inline-flex;align-items:center;
    gap:.4rem;padding:.3rem .75rem;border-radius:20px;font-size:.85rem;font-weight:600;`;
}

// ---- Search ----
function initSearch() {
  const input = document.getElementById('search-input');
  if (!input) return;
  input.addEventListener('input', () => runSearch(input.value.trim()));
  document.getElementById('search-form').addEventListener('submit', e => {
    e.preventDefault();
    runSearch(input.value.trim());
  });
}

function focusSearch() {
  setTimeout(() => {
    const el = document.getElementById('search-input');
    if (el) el.focus();
  }, 50);
}

function runSearch(query) {
  const resultsEl = document.getElementById('search-results');
  if (!query || !plan) {
    resultsEl.innerHTML = '';
    return;
  }

  // Case: numeric — treat as day number
  const dayNum = parseInt(query, 10);
  if (!isNaN(dayNum) && String(dayNum) === query) {
    const chars = plan.schedule[String(dayNum)];
    if (chars) {
      const perDay = plan.stats.per_day.find(d => d.day === dayNum) || {};
      const coh = perDay.coherence != null ? `${(perDay.coherence*100).toFixed(1)}%` : '—';
      resultsEl.innerHTML = `
        <div class="search-result">
          <h3>Day ${dayNum}</h3>
          <p class="result-day">${chars.length} characters &nbsp;|&nbsp; Coherence: ${coh}</p>
          <p style="font-size:1.4rem;letter-spacing:.12em;margin:.75rem 0;line-height:1.8">${chars.join(' ')}</p>
          <a href="#day/${dayNum}" class="btn btn-sm btn-primary">View Day ${dayNum}</a>
        </div>`;
    } else {
      resultsEl.innerHTML = noResultsHtml(`Day ${dayNum} not found (valid range: 1–${plan.stats.days_used}).`);
    }
    return;
  }

  // Case: single character lookup (could be multi-char but we search each)
  // Build a reverse map on first use
  if (!window._dayForChar) {
    window._dayForChar = {};
    Object.entries(plan.schedule).forEach(([day, chars]) => {
      chars.forEach(ch => { window._dayForChar[ch] = parseInt(day, 10); });
    });
  }

  // Search for each character in query
  const results = [];
  for (const ch of query) {
    if (ch.trim() === '') continue;
    const day = window._dayForChar[ch];
    if (day !== undefined) {
      const rank = rankMap[ch] ?? null;
      results.push({ ch, day, rank });
    }
  }

  if (results.length === 0) {
    resultsEl.innerHTML = noResultsHtml(
      query.length === 1
        ? `"${query}" is not in the learning plan.`
        : `None of the characters in "${query}" are in the learning plan.`
    );
    return;
  }

  resultsEl.innerHTML = results.map(({ ch, day, rank }) => `
    <div class="search-result">
      <div class="big-char">${ch}</div>
      <p class="result-day">Scheduled on <a href="#day/${day}">Day ${day}</a></p>
      <p style="color:var(--text-muted);font-size:.88rem;">
        ${rank ? `Frequency rank: #${rank.toLocaleString()}` : 'Rank: unknown'}
      </p>
    </div>
  `).join('');
}

function noResultsHtml(msg) {
  return `<div class="search-empty">${msg}</div>`;
}

// ---- Overview grid ----
let tooltipEl = null;

function renderOverview() {
  if (!plan) return;

  const container = document.getElementById('overview-grid');
  if (container.dataset.rendered === 'true') return; // already built

  const perDayMap = {};
  plan.stats.per_day.forEach(d => { perDayMap[d.day] = d; });

  // Create tooltip element once
  tooltipEl = document.getElementById('grid-tooltip');

  container.innerHTML = '';
  for (let day = 1; day <= plan.stats.days_used; day++) {
    const info = perDayMap[day] || {};
    const coh = info.coherence ?? 0;
    const bg = coherenceColor(coh);

    const cell = document.createElement('div');
    cell.className = 'day-cell';
    cell.style.background = bg;
    cell.textContent = day;
    cell.dataset.day = day;

    // Tooltip on hover
    cell.addEventListener('mouseenter', e => showTooltip(e, day, info));
    cell.addEventListener('mousemove', e => moveTooltip(e));
    cell.addEventListener('mouseleave', hideTooltip);

    // Click navigates to day
    cell.addEventListener('click', () => { window.location.hash = `day/${day}`; });

    container.appendChild(cell);
  }

  container.dataset.rendered = 'true';
}

function showTooltip(e, day, info) {
  if (!tooltipEl) return;
  const chars = (plan.schedule[String(day)] || []).slice(0, 5).join(' ');
  const coh = info.coherence != null ? (info.coherence * 100).toFixed(1) + '%' : '—';
  tooltipEl.innerHTML = `
    <div class="tip-day">Day ${day}</div>
    <div style="font-size:.78rem;color:rgba(255,255,255,.7);margin-bottom:.2rem">
      ${info.n_chars || '?'} chars &nbsp;|&nbsp; coherence ${coh}
    </div>
    <div class="tip-chars">${chars}</div>
    ${info.n_chars > 5 ? `<div style="font-size:.72rem;color:rgba(255,255,255,.55);margin-top:.1rem">+${info.n_chars - 5} more</div>` : ''}
  `;
  moveTooltip(e);
  tooltipEl.classList.add('visible');
}

function moveTooltip(e) {
  if (!tooltipEl) return;
  const offset = 14;
  let x = e.clientX + offset;
  let y = e.clientY + offset;
  // Keep within viewport
  const tw = tooltipEl.offsetWidth || 180;
  const th = tooltipEl.offsetHeight || 80;
  if (x + tw > window.innerWidth - 8) x = e.clientX - tw - offset;
  if (y + th > window.innerHeight - 8) y = e.clientY - th - offset;
  tooltipEl.style.left = x + 'px';
  tooltipEl.style.top = y + 'px';
}

function hideTooltip() {
  if (tooltipEl) tooltipEl.classList.remove('visible');
}
