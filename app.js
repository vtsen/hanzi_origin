/* ===================================================
   Hanzi Learning Plan — Single-page app
   Hash routing: #home | #day/N | #search | #overview
   =================================================== */

'use strict';

// ---- Global state ----
let plan = null;       // the loaded plan JSON
let rankMap = null;    // char -> 1-based rank (from char_freq_rank.json)
let freqList = null;   // raw array from char_freq_rank.json
let charInfo = null;   // char -> {senses, edges, formation, deps} from char_info.json

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
    const [planRes, rankRes, infoRes] = await Promise.all([
      fetch('data/learning_plan/learning_plan_50days_additive_gap0.3.json'),
      fetch('data/char_freq_rank.json'),
      fetch('data/char_info.json'),
    ]);

    if (!planRes.ok) throw new Error('Failed to load learning_plan_50days_additive_gap0.3.json');
    if (!rankRes.ok) throw new Error('Failed to load char_freq_rank.json');
    // char_info is optional — don't hard-fail if missing
    if (infoRes.ok) charInfo = await infoRes.json();

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

    // Build meaning snippet from first sense (2c: use new senses[0].m schema)
    let snippetHtml = '';
    const info = charInfo && charInfo[ch];
    if (info && info.senses && info.senses.length > 0) {
      let snippet = info.senses[0].m;
      if (snippet.length > 30) snippet = snippet.slice(0, 30) + '…';
      snippetHtml = `<span class="char-meaning-snippet">${snippet}</span>`;
    }

    card.innerHTML = `
      <span class="char-glyph">${ch}</span>
      <span class="char-rank">${rank ? '#' + rank.toLocaleString() : '—'}</span>
      ${snippetHtml}
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

  // Populate detail panel — core fields
  document.getElementById('detail-glyph').textContent = ch;
  document.getElementById('detail-char-text').textContent = `Character: ${ch}`;
  document.getElementById('detail-rank-text').textContent =
    rank ? `Frequency rank: #${rank.toLocaleString()} out of ${freqList.length.toLocaleString()}` : 'Rank: unknown';
  document.getElementById('detail-day-text').textContent = `Scheduled on: Day ${dayNum}`;

  // Populate etymology fields from charInfo
  const info = charInfo && charInfo[ch];

  const meaningsEl = document.getElementById('detail-meanings');
  const depsEl = document.getElementById('detail-deps');

  // Formation text + historical script images rendered together
  renderHistoricalForms(ch, info && info.formation || '');

  // 2b: Render full meaning forest from senses + edges
  if (info && info.senses && info.senses.length > 0) {
    meaningsEl.innerHTML = renderMeaningForest(info.senses, info.edges || []);
    meaningsEl.style.display = '';
  } else {
    meaningsEl.innerHTML = '';
    meaningsEl.style.display = 'none';
  }

  // 2a: Dep cards with day links
  if (info && info.deps && info.deps.length > 0) {
    depsEl.innerHTML = `<span class="deps-label">Builds on:</span>` +
      `<div class="dep-cards">` +
      info.deps.map(dep => renderDepCard(dep)).join('') +
      `</div>`;
    depsEl.style.display = '';
  } else {
    depsEl.innerHTML = '';
    depsEl.style.display = 'none';
  }

  detail.classList.add('visible');
  detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ---- Historical script forms (Track-A: char-based Wikimedia URLs) ----

const HIST_SCRIPTS = [
  { suffix: '-oracle',         label: '甲骨文', title: 'Oracle bone script (Shang)' },
  { suffix: '-bronze-shang',   label: '金文',   title: 'Bronze inscription (Shang)' },
  { suffix: '-bronze-warring', label: '战国金文', title: 'Bronze inscription (Warring States)' },
  { suffix: '-silk',           label: '帛书',   title: 'Silk script (Chu)' },
  { suffix: '-slip',           label: '竹简',   title: 'Slip script' },
];
const WIKIMEDIA_PATH = 'https://commons.wikimedia.org/wiki/Special:FilePath/';
const WIKIMEDIA_FILE_PAGE = 'https://commons.wikimedia.org/wiki/File:';

function renderHistoricalForms(ch, formation) {
  const el = document.getElementById('detail-historical');
  el.innerHTML = '';
  el.style.display = 'none';

  // Formation text (construction logic) — always show if present, images appear below
  if (formation) {
    const formEl = document.createElement('p');
    formEl.className = 'hist-formation';
    formEl.textContent = formation;
    el.appendChild(formEl);
    el.style.display = '';
  }

  const strip = document.createElement('div');
  strip.className = 'hist-strip';

  HIST_SCRIPTS.forEach(({ suffix, label, title }) => {
    const filename = ch + suffix + '.svg';
    const imgUrl = WIKIMEDIA_PATH + encodeURIComponent(filename);
    const pageUrl = WIKIMEDIA_FILE_PAGE + encodeURIComponent(filename);

    const form = document.createElement('a');
    form.className = 'hist-form';
    form.href = pageUrl;
    form.target = '_blank';
    form.rel = 'noopener noreferrer';
    form.title = title;
    form.style.display = 'none'; // shown only on successful load

    const img = new Image();
    img.className = 'hist-img';
    img.alt = label;

    img.addEventListener('load', () => {
      form.style.display = 'flex';
      // Append strip to container on first successful image
      if (!strip.parentNode) {
        el.appendChild(strip);
        el.style.display = '';
      }
    });

    img.src = imgUrl;
    form.appendChild(img);
    form.appendChild(Object.assign(document.createElement('span'), {
      className: 'hist-label', textContent: label,
    }));
    strip.appendChild(form);
  });
}

// Navigate to search page and run a search for a dependency character
function searchDep(ch) {
  window.location.hash = 'search';
  // Small delay to let the page render before filling the input
  setTimeout(() => {
    const input = document.getElementById('search-input');
    if (input) {
      input.value = ch;
      runSearch(ch);
    }
  }, 60);
}

// ---- Dep day lookup (2a) ----
function getDayForChar(ch) {
  // Build reverse map on first use
  if (!window._dayForChar) {
    window._dayForChar = {};
    Object.entries(plan.schedule).forEach(([day, chars]) => {
      chars.forEach(c => { window._dayForChar[c] = parseInt(day, 10); });
    });
  }
  return window._dayForChar[ch]; // undefined if not in plan
}

// Render a dep card: shows glyph + day badge. Clicking navigates to day or search.
function renderDepCard(dep) {
  const day = getDayForChar(dep);
  if (day !== undefined) {
    // In plan — navigate directly to that day
    return `<a class="dep-card" href="#day/${day}" title="Day ${day}">
      <span class="dep-card-glyph">${dep}</span>
      <span class="dep-card-day">Day ${day}</span>
    </a>`;
  } else {
    // Not in plan — search for it
    return `<button class="dep-card dep-card-unscheduled" onclick="searchDep('${dep}')" title="Not in plan">
      <span class="dep-card-glyph">${dep}</span>
      <span class="dep-card-day">—</span>
    </button>`;
  }
}

// ---- Meaning forest renderer (2b) ----

// Color map for POS badges
const POS_COLORS = {
  verb:        '#3b82f6', // blue
  noun:        '#16a34a', // green
  adjective:   '#ea580c', // orange
  adverb:      '#7c3aed', // purple
  conjunction: '#0891b2', // cyan
  preposition: '#b45309', // amber
  particle:    '#db2777', // pink
  numeral:     '#059669', // emerald
  pronoun:     '#dc2626', // red
  interjection:'#65a30d', // lime
};

function posColor(pos) {
  return POS_COLORS[pos] || '#6b7280'; // gray fallback
}

// Color map for evolution edge types
const EDGE_COLORS = {
  semantic_extension: '#0d9488', // teal
  semantic_shift:     '#7c3aed', // purple
  metaphor:           '#9333ea', // violet
  metonymy:           '#d97706', // amber
  amelioration:       '#16a34a', // green
  pejoration:         '#dc2626', // red
  function_word:      '#0891b2', // cyan
  grammaticalization: '#2563eb', // blue
  synecdoche:         '#f59e0b', // yellow
  unknown:            '#9ca3af', // gray
};

function edgeColor(type) {
  return EDGE_COLORS[type] || '#6b7280';
}

// Render sense node HTML recursively
function renderSenseNode(sense, children, allSenses, depth) {
  const posCol = posColor(sense.pos);
  const exHtml = sense.ex && sense.ex.length > 0
    ? `<span class="sense-examples">例：${sense.ex.join('；')}</span>`
    : '';

  let childrenHtml = '';
  if (children && children.length > 0) {
    childrenHtml = `<div class="sense-children">` +
      children.map(({ target, type, note }) => {
        const childSense = allSenses.find(s => s.i === target);
        if (!childSense) return '';
        const col = edgeColor(type);
        const edgeHtml = `<div class="sense-edge">
          <span class="edge-type" style="color:${col}">→ ${type.replace(/_/g, ' ')}</span>
          ${note ? `<span class="edge-note">${note}</span>` : ''}
        </div>`;
        return edgeHtml + renderSenseNode(childSense, childSense._children, allSenses, depth + 1);
      }).join('') +
      `</div>`;
  }

  return `<div class="sense-node">
    <span class="sense-pos" style="background:${posCol}">${sense.pos || '?'}</span>
    <span class="sense-meaning">${sense.m}</span>
    ${exHtml}
    ${childrenHtml}
  </div>`;
}

// Build and return the full forest HTML from senses + edges arrays
function renderMeaningForest(senses, edges) {
  if (!senses || senses.length === 0) return '';

  // Build a set of sense indices that have incoming edges (not roots)
  const hasIncoming = new Set(edges.map(e => e.t));

  // Attach children list to each sense for easy traversal
  const childrenMap = {};
  edges.forEach(e => {
    if (!childrenMap[e.s]) childrenMap[e.s] = [];
    childrenMap[e.s].push({ target: e.t, type: e.type, note: e.note || '' });
  });
  senses.forEach(s => { s._children = childrenMap[s.i] || []; });

  // Roots: senses with no incoming edges
  const roots = senses.filter(s => !hasIncoming.has(s.i));
  // Fallback: if all have incoming edges (cycle), show all as roots
  const renderRoots = roots.length > 0 ? roots : senses;

  const html = renderRoots.map(s => renderSenseNode(s, s._children, senses, 0)).join('');
  return `<div class="meaning-forest">${html}</div>`;
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
