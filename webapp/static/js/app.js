'use strict';

/* ─── TELEGRAM ─── */
const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }

const TG_ID = (
  tg?.initDataUnsafe?.user?.id ||
  (tg?.initData && (() => {
    try { return JSON.parse(new URLSearchParams(tg.initData).get('user'))?.id; } catch { return null; }
  })()) ||
  new URLSearchParams(window.location.search).get('telegram_id') ||
  null
);

console.log('[TradePlanner] TG_ID:', TG_ID);

/* ─── GLOBAL MODE ─── */
window._mode = 'strategy';

function applyMode(mode) {
  window._mode = mode || 'strategy';
  const stratTab = document.querySelector('.tab[data-tab="strategy"]');
  if (stratTab) stratTab.style.display = mode === 'journal' ? 'none' : '';
  const chip = document.querySelector('.header-chip');
  if (chip) chip.textContent = mode === 'journal' ? 'JURNAL' : 'LIVE';
}

/* ─── DEMO DATA ─── */
const mkRng = (seed) => { let x = seed; return () => { x = (x*9301+49297)%233280; return x/233280; }; };

let JOURNAL = (() => {
  const r = []; let bal = 2000; const rnd = mkRng(42);
  for (let i = 1; i <= 20; i++) {
    const tgt = +(bal * 0.035).toFixed(2);
    const pnl = +(tgt * (0.6 + rnd() * 0.9) * (rnd() > 0.15 ? 1 : -1)).toFixed(2);
    const d = new Date(2025, 3, i);
    const done = rnd() > 0.05;
    r.push({
      day_number: i,
      date: `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}`,
      target: tgt, net_pnl: pnl, is_completed: done,
      is_rolled_over: done && pnl < tgt * 0.5
    });
    if (done) bal += pnl;
  }
  return r;
})();

const PROGRESSION = (() => {
  const r = []; let bal = 2000, plan = 2000; const rnd = mkRng(7);
  for (let i = 1; i <= 20; i++) {
    const tgt = +(bal * 0.035).toFixed(2);
    const pnl = +(tgt * (0.6 + rnd() * 0.9) * (rnd() > 0.15 ? 1 : -1)).toFixed(2);
    r.push({ day:i, date:`2025-04-${String(i).padStart(2,'0')}`, start_balance:bal, final_balance:+(plan*1.035).toFixed(2), target_profit:tgt, actual_pnl:pnl, is_completed:true });
    bal += pnl; plan *= 1.035;
  }
  return r;
})();

let OV = {
  current_balance: 2847.50, planned_balance: 3124.00,
  settings: { starting_balance: 2000, daily_profit_rate: 0.035, total_days: 30, start_date: '2025-04-01', broker_name: 'MetaTrader 5' },
  summary: { total_days: 20, win_days: 15, loss_days: 3, total_pnl: 847.50, total_trades: 20 }
};

let SUM = {
  total_trades:20, wins:15, losses:3, break_even:2,
  biggest_win:124.50, biggest_loss:47.20, avg_hold_win:0, avg_hold_loss:0,
  wins_gross:1290, wins_swap:25.80, wins_commission:-13.54, wins_net:1302, wins_pct:96.42, wins_rr:100.33,
  be_gross:13.47, be_swap:.26, be_commission:-.21, be_net:13.52, be_pct:1.27, be_rr:.03,
  loss_gross:-534.65, loss_swap:-10.69, loss_commission:-5.34, loss_net:-547.41, loss_pct:-38.47, loss_rr:-37.45,
  total_gross:769.80, total_swap:15.39, total_commission:-19.11, total_net:847, total_pct:59.22, total_rr:62.91,
};

/* ─── HELPERS ─── */
async function apiFetch(ep, extra='') {
  if (!TG_ID) {
    console.warn(`apiFetch: TG_ID yo'q, demo data ishlatiladi (${ep})`);
    return null;
  }
  try {
    const url = `${ep}?telegram_id=${TG_ID}${extra}`;
    const r = await fetch(url);
    if (!r.ok) { console.error(`apiFetch xato [${ep}]: HTTP ${r.status}`); return null; }
    return await r.json();
  } catch (err) {
    console.error(`apiFetch xato [${ep}]:`, err);
    return null;
  }
}

const fm = (v, sign=true) => {
  if (v == null) return '—';
  const n = Number(v), s = sign ? (n >= 0 ? '+' : '') : '';
  return `${s}${n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}$`;
};
const fp = v => v == null ? '—' : Number(v).toLocaleString('en-US',{minimumFractionDigits:3,maximumFractionDigits:5});
const fa = v => v != null ? `$${Math.abs(Number(v)).toFixed(2)}` : '—';
const getEl = id => document.getElementById(id);
const txt = (id, v) => { const e = getEl(id); if (e) e.textContent = v ?? '—'; };

function haptic(t='light') { try { tg?.HapticFeedback?.impactOccurred?.(t); } catch {} }

function showToast(msg) {
  let el = getEl('__toast');
  if (!el) { el = document.createElement('div'); el.id = '__toast'; el.className = 'toast'; document.body.appendChild(el); }
  el.textContent = msg; el.classList.add('show');
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove('show'), 2400);
}

function countUp(el, target, dur=900) {
  if (!el) return;
  const t0 = Date.now();
  const tick = () => {
    const p = Math.min((Date.now()-t0)/dur, 1);
    const e = 1 - Math.pow(1-p, 3);
    el.textContent = (target*e).toFixed(2) + '$';
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function animateRing(id, pct) {
  const el = getEl(id); if (!el) return;
  const C = 2 * Math.PI * 37;
  setTimeout(() => { el.style.strokeDashoffset = C - (Math.min(Math.max(pct,0),100)/100)*C; }, 300);
}

/* ─── TABS ─── */
const tabLoaded = { overview:true, strategy:false, journal:false, analiz:false };

// Tab switching — asosiy logika
function switchTab(name) {
  haptic();
  // Barcha tab buttonlardan active ni olib tashla
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  // Barcha tab contentlarni yashir
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  // Active tab buttonni belgilash
  const tabBtn = document.querySelector(`.tab[data-tab="${name}"]`);
  if (tabBtn) tabBtn.classList.add('active');

  // Active contentni ko'rsatish
  const tabContent = document.getElementById(`tab-${name}`);
  if (tabContent) tabContent.classList.add('active');

  // Lazy load
  if (name === 'strategy' && !tabLoaded.strategy) { loadStrategy(); tabLoaded.strategy = true; }
  if (name === 'journal'  && !tabLoaded.journal)  { loadJournal();  tabLoaded.journal  = true; }
  if (name === 'analiz'   && !tabLoaded.analiz)   { loadAnaliz();   tabLoaded.analiz   = true; }
}

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    const name = btn.dataset.tab;
    if (name) switchTab(name);
  });
});

/* ══════════════════════════════════
   HEX HEATMAP — SVG hexbin
══════════════════════════════════ */
function renderHexMapTo(svgId, journal, totalDays) {
  const svg = getEl(svgId);
  if (!svg) return;

  // totalDays: parametrdan keladi yoki fallback
  const TOTAL = totalDays || journal.length || 30;

  const HEX_R = 18;
  const GAP   = 2;
  const COLS  = 7;

  const journalMap = {};
  journal.forEach(j => { journalMap[j.day_number] = j; });

  // JOURNAL mavjud bo'lsa shu kunlarni, yo'qsa totalDays ta placeholder
  const allDays = Array.from({ length: TOTAL }, (_, i) => {
    const d = i + 1;
    return journalMap[d] || { day_number:d, is_completed:false, is_rolled_over:false, net_pnl:null, target:null, _future:true };
  });

  const rows  = Math.ceil(allDays.length / COLS);
  const HW    = HEX_R * Math.sqrt(3) + GAP;
  const HH    = HEX_R * 2;
  const PAD   = 8;
  const svgW  = COLS * HW + HEX_R + PAD * 2;
  const svgH  = rows * (HH * 0.75 + GAP / 2) + HEX_R * 1.5 + PAD * 2;

  const hexPts = (cx, cy, r) =>
    Array.from({length:6}, (_,i) => {
      const a = (Math.PI/3)*i - Math.PI/6;
      return `${(cx+r*Math.cos(a)).toFixed(2)},${(cy+r*Math.sin(a)).toFixed(2)}`;
    }).join(' ');

  const getColors = (j) => {
    const pnl = j.net_pnl != null ? Math.round((j.net_pnl/(j.target||40))*100) : null;
    if (!j.is_completed) return { face:'rgba(20,18,45,0.7)', faceH:'rgba(30,25,60,0.85)', edge:'rgba(255,255,255,0.08)', text:'rgba(255,255,255,0.2)', glow:null };
    if (j.is_rolled_over) return { face:'rgba(180,20,50,0.55)', faceH:'rgba(220,30,65,0.75)', edge:'#ff3060', text:'#ff8099', glow:'gl' };
    if (pnl !== null && pnl > 80) return { face:'rgba(0,140,80,0.55)', faceH:'rgba(0,180,100,0.75)', edge:'#06ffa5', text:'#39ffac', glow:'gw_hi' };
    return { face:'rgba(0,80,50,0.45)', faceH:'rgba(0,110,70,0.65)', edge:'#00c870', text:'#5dffc0', glow:'gw_lo' };
  };

  let defs = `<defs>
  <filter id="gw_hi_${svgId}" x="-80%" y="-80%" width="260%" height="260%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="5" result="b"/>
    <feFlood flood-color="rgb(0,200,120)" flood-opacity="0.9" result="c"/>
    <feComposite in="c" in2="b" operator="in" result="g"/>
    <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="gw_lo_${svgId}" x="-80%" y="-80%" width="260%" height="260%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="b"/>
    <feFlood flood-color="rgb(0,200,120)" flood-opacity="0.65" result="c"/>
    <feComposite in="c" in2="b" operator="in" result="g"/>
    <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="gl_${svgId}" x="-80%" y="-80%" width="260%" height="260%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="b"/>
    <feFlood flood-color="rgb(255,40,80)" flood-opacity="0.8" result="c"/>
    <feComposite in="c" in2="b" operator="in" result="g"/>
    <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <linearGradient id="glSh_${svgId}" x1="15%" y1="0%" x2="85%" y2="100%">
    <stop offset="0%" stop-color="rgba(255,255,255,0.22)"/>
    <stop offset="40%" stop-color="rgba(255,255,255,0.05)"/>
    <stop offset="100%" stop-color="rgba(255,255,255,0.00)"/>
  </linearGradient>
  </defs>`;

  // hexAppear animatsiyasi
  if (!document.getElementById('hx-style')) {
    const st = document.createElement('style');
    st.id = 'hx-style';
    st.textContent = `
      @keyframes hexAppear {
        from { opacity:0; transform:scale(0.6); transform-origin:center; }
        to   { opacity:1; transform:scale(1); }
      }
    `;
    document.head.appendChild(st);
  }

  let body = '';
  allDays.forEach((j, idx) => {
    const col  = idx % COLS;
    const row  = Math.floor(idx / COLS);
    const cx   = col * HW + HEX_R + PAD + (row % 2 === 1 ? HW/2 : 0);
    const cy   = row * (HH*0.75 + GAP/2) + HEX_R + PAD;

    const { face, faceH, edge, text, glow } = getColors(j);
    // Filter ID larni svgId bilan birlashtirish (conflict oldini olish)
    const glowRef = glow ? glow + '_' + svgId : null;
    const fAttr = glowRef ? ` filter="url(#${glowRef})"` : '';
    const pnl   = j.net_pnl != null ? Math.round((j.net_pnl/(j.target||40))*100) : null;
    const lbl   = pnl != null ? `${pnl>=0?'+':''}${pnl}%` : '';
    const delay = (idx * 0.035).toFixed(3);
    const done  = j.is_completed ? '1' : '0';
    const ptsOuter = hexPts(cx, cy, HEX_R - 1);
    const ptsInner = hexPts(cx, cy, HEX_R - 2.5);

    body += `<g${fAttr} style="opacity:0;animation:hexAppear 0.4s ease forwards ${delay}s">
      <polygon
        class="hx"
        points="${ptsOuter}"
        fill="${face}"
        stroke="${edge}"
        stroke-width="1"
        data-cx="${cx.toFixed(2)}"
        data-cy="${cy.toFixed(2)}"
        data-done="${done}"
        data-face="${face}"
        data-faceh="${faceH}"
        style="cursor:${j.is_completed?'pointer':'default'}"
      />
      <polygon points="${ptsInner}" fill="url(#glSh_${svgId})" opacity="${j.is_completed?0.55:0.3}" style="pointer-events:none"/>
      ${j.is_completed && lbl ? `
      <text x="${cx.toFixed(1)}" y="${(cy-2.5).toFixed(1)}"
        text-anchor="middle" dominant-baseline="middle"
        font-family="Space Mono" font-size="6.5" font-weight="700"
        fill="${text}" style="pointer-events:none">${lbl}</text>` : ''}
      <text x="${cx.toFixed(1)}" y="${(j.is_completed?cy+6.5:cy+1).toFixed(1)}"
        text-anchor="middle" dominant-baseline="middle"
        font-family="Space Mono" font-size="${j.is_completed?'5.2':'6.5'}" font-weight="400"
        fill="${j.is_completed?'rgba(255,255,255,0.45)':'rgba(255,255,255,0.18)'}"
        style="pointer-events:none">${j.day_number}</text>
    </g>`;
  });

  svg.innerHTML = defs + body;
  svg.setAttribute('viewBox', `0 0 ${svgW.toFixed(1)} ${svgH.toFixed(1)}`);
  svg.removeAttribute('width');
  svg.removeAttribute('height');
  svg.style.width    = '100%';
  svg.style.height   = 'auto';
  svg.style.overflow = 'visible';
  svg.style.webkitTapHighlightColor = 'transparent';

  // Polygon hover events
  requestAnimationFrame(() => {
    svg.querySelectorAll('polygon.hx').forEach(poly => {
      if (poly.dataset.done !== '1') return;

      const cx    = parseFloat(poly.dataset.cx);
      const cy    = parseFloat(poly.dataset.cy);
      const faceN = poly.dataset.face;
      const faceH = poly.dataset.faceh;
      let   sc    = 1;
      let   raf   = null;

      const animTo = (target, dur = 160) => {
        if (raf) cancelAnimationFrame(raf);
        const t0 = performance.now(), from = sc;
        const tick = now => {
          const p = Math.min((now-t0)/dur, 1);
          const e = 1 - Math.pow(1-p, 3);
          sc = from + (target - from) * e;
          poly.setAttribute('transform',
            `translate(${cx},${cy}) scale(${sc.toFixed(4)}) translate(${-cx},${-cy})`
          );
          poly.setAttribute('stroke-width', sc > 1.04 ? '2' : '1');
          poly.setAttribute('fill', sc > 1.04 ? faceH : faceN);
          if (p < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      };

      let isTouch = false;
      let scaleTimeout = null;
      const resetScale = () => {
        clearTimeout(scaleTimeout);
        scaleTimeout = setTimeout(() => animTo(1.0, 220), 320);
      };

      poly.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') animTo(1.18); });
      poly.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') animTo(1.0); });
      poly.addEventListener('pointerdown', e => {
        e.preventDefault();
        clearTimeout(scaleTimeout);
        isTouch = e.pointerType === 'touch';
        animTo(1.12, 80);
        haptic('light');
      });
      poly.addEventListener('pointerup', e => {
        e.preventDefault();
        animTo(1.18, 100);
        if (isTouch) resetScale();
      });
      poly.addEventListener('pointercancel', () => {
        clearTimeout(scaleTimeout);
        animTo(1.0, 150);
      });
    });
  });
}

/* ─── Swipe between tabs on header ─── */
(() => {
  const tabs   = ['overview','strategy','journal','analiz'];
  const header = getEl('main-header');
  if (!header) return;

  let sx=0, sy=0, locked=false;
  header.addEventListener('touchstart', e => {
    sx=e.touches[0].clientX; sy=e.touches[0].clientY; locked=false;
  }, {passive:true});
  header.addEventListener('touchmove', e => {
    if(!locked && Math.abs(e.touches[0].clientY-sy) > Math.abs(e.touches[0].clientX-sx)) locked=true;
  }, {passive:true});
  header.addEventListener('touchend', e => {
    if (locked) return;
    const dx = e.changedTouches[0].clientX - sx;
    if (Math.abs(dx) < 40) return;
    const cur  = document.querySelector('.tab.active')?.dataset?.tab;
    const idx  = tabs.indexOf(cur);
    // journal rejimida strategy tabini skip
    let next = dx < 0 ? idx+1 : idx-1;
    while (next >= 0 && next < tabs.length) {
      const tabEl = document.querySelector(`.tab[data-tab="${tabs[next]}"]`);
      if (tabEl && tabEl.style.display !== 'none') break;
      next = dx < 0 ? next+1 : next-1;
    }
    if (next >= 0 && next < tabs.length) {
      switchTab(tabs[next]);
    }
  }, {passive:true});
})();

/* ══════════════════════════════════
   MONTH NAVIGATOR
══════════════════════════════════ */
const MONTHS_UZ = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentabr','Oktabr','Noyabr','Dekabr'];

window._hexNav = { year: 2025, month: 3, panelOpen: false };

function getJournalYearsMonths() {
  const map = {};
  JOURNAL.forEach(j => {
    if (!j.date) return;
    const parts = j.date.split('.');
    if (parts.length < 2) return;
    const m = parseInt(parts[1]) - 1;
    const y = parseInt(OV?.settings?.start_date?.split('-')[0] || 2025);
    if (!map[y]) map[y] = new Set();
    map[y].add(m);
  });
  return map;
}

function getJournalForMonth(year, month) {
  return JOURNAL.filter(j => {
    if (!j.date) return false;
    const parts = j.date.split('.');
    const m = parseInt(parts[1]) - 1;
    return m === month;
  });
}

function updateMonthLabel() {
  const { year, month } = window._hexNav;
  const el = getEl('mnav-label');
  if (el) el.textContent = `${year} ${MONTHS_UZ[month]}`;
}

function hexNavMonth(dir) {
  haptic('light');
  let { year, month } = window._hexNav;
  month += dir;
  if (month > 11) { month = 0; year++; }
  if (month < 0)  { month = 11; year--; }
  window._hexNav.year  = year;
  window._hexNav.month = month;
  updateMonthLabel();
  refreshHexOv();
  if (window._hexNav.panelOpen) toggleMonthPanel();
}

function toggleMonthPanel() {
  haptic('light');
  window._hexNav.panelOpen = !window._hexNav.panelOpen;
  const panel = getEl('month-panel');
  const caret = getEl('mnav-caret');
  if (!panel) return;
  if (window._hexNav.panelOpen) {
    panel.style.display = '';
    caret?.classList.add('open');
    buildMonthPanel();
  } else {
    panel.style.display = 'none';
    caret?.classList.remove('open');
  }
}

function buildMonthPanel() {
  const { year, month } = window._hexNav;
  const dataMap = getJournalYearsMonths();
  const years   = Object.keys(dataMap).map(Number).sort();
  if (!years.includes(year)) years.push(year);

  const yWrap = getEl('mpanel-years');
  if (yWrap) {
    yWrap.innerHTML = years.map(y =>
      `<button class="mpy-btn${y===year?' sel':''}" onclick="selectYear(${y})">${y}</button>`
    ).join('');
  }

  const mWrap = getEl('mpanel-months');
  if (mWrap) {
    const monthsWithData = dataMap[year] || new Set();
    mWrap.innerHTML = MONTHS_UZ.map((name, i) => {
      const hasData = monthsWithData.has(i);
      const isSel   = i === month;
      const cls     = `mpm-btn${isSel?' sel':''}${hasData?' has-data':' empty'}`;
      return `<button class="${cls}" onclick="selectMonth(${i})">${name}</button>`;
    }).join('');
  }
}

function selectYear(y) {
  haptic('light');
  window._hexNav.year = y;
  updateMonthLabel();
  buildMonthPanel();
  refreshHexOv();
}

function selectMonth(m) {
  haptic('light');
  window._hexNav.month = m;
  updateMonthLabel();
  refreshHexOv();
  toggleMonthPanel();
}

function refreshHexOv() {
  const { month } = window._hexNav;
  const filtered  = getJournalForMonth(window._hexNav.year, month);
  const total     = OV?.settings?.total_days || filtered.length || 30;
  renderHexMapTo('hex-svg-ov', filtered, total);
}

document.addEventListener('click', e => {
  if (!window._hexNav?.panelOpen) return;
  const panel = getEl('month-panel');
  const nav   = document.querySelector('.month-nav');
  if (panel && nav && !panel.contains(e.target) && !nav.contains(e.target)) {
    toggleMonthPanel();
  }
}, { capture: false });

/* ══════════════════════════════════
   OVERVIEW
══════════════════════════════════ */
async function loadOverview() {
  const [ovData, jData] = await Promise.all([
    apiFetch('/api/overview'),
    apiFetch('/api/journal'),
  ]);

  if (ovData) OV = ovData;
  if (jData?.journal?.length) JOURNAL = jData.journal;

  const d   = OV;
  const cur = d.current_balance || 0;
  const sum = d.summary;
  const mode = d.mode || 'strategy';

  applyMode(mode);

  // Balance countup
  const abEl = getEl('ov-balance');
  if (abEl) countUp(abEl, cur, 900);

  // Today PnL
  const lastDay  = [...JOURNAL].reverse().find(j => j.is_completed);
  const todayPnl = sum?.today_pnl ?? lastDay?.net_pnl ?? 0;
  const todayPct = cur > 0 ? ((todayPnl / cur) * 100) : 0;

  const tpEl = getEl('ov-today-pnl');
  if (tpEl) {
    tpEl.textContent = fm(todayPnl);
    tpEl.className = `bd-val ${todayPnl >= 0 ? 'pos' : 'neg'}`;
  }
  const pctEl = getEl('ov-today-pct');
  if (pctEl) {
    pctEl.textContent = `${todayPct >= 0 ? '+' : ''}${todayPct.toFixed(2)}%`;
    pctEl.style.color = todayPct >= 0 ? 'var(--green-hi)' : 'var(--red-hi)';
  }

  // KPI
  const comp     = JOURNAL.filter(j => j.is_completed);
  const wins     = comp.filter(j => !j.is_rolled_over).length;
  const wr       = comp.length > 0 ? Math.round((wins / comp.length) * 100) : 0;
  const totalPnl = sum?.total_pnl ?? comp.reduce((s, j) => s + (j.net_pnl || 0), 0);
  const totalTrades = sum?.total_trades ?? JOURNAL.length;

  txt('ov-total-trades', totalTrades);

  const wrEl = getEl('ov-winrate');
  if (wrEl) {
    wrEl.textContent = mode === 'journal' ? '—' : `${wr}%`;
    wrEl.className = `kpi-val ${wr >= 50 ? 'up' : 'dn'}`;
  }
  const tpnlEl = getEl('ov-total-pnl');
  if (tpnlEl) {
    tpnlEl.textContent = `${totalPnl >= 0 ? '+' : ''}${Number(totalPnl).toFixed(0)}$`;
    tpnlEl.className = `kpi-val ${totalPnl >= 0 ? 'up' : 'dn'}`;
  }

  // Hex map
  const startDate = d?.settings?.start_date || '2025-04-01';
  const parts = startDate.split('-');
  window._hexNav.year  = parseInt(parts[0]);
  window._hexNav.month = parseInt(parts[1]) - 1;
  updateMonthLabel();
  refreshHexOv();

  // Streak
  if (mode === 'strategy') {
    let streak = 0;
    for (let i = JOURNAL.length - 1; i >= 0; i--) {
      if (JOURNAL[i].is_completed && !JOURNAL[i].is_rolled_over) streak++;
      else break;
    }
    const sw = getEl('ov-streak-wrap');
    if (sw && streak > 0) {
      sw.innerHTML = `<div class="streak">
        <span class="streak-icon">🔥</span>
        <span class="streak-txt">Joriy ketma-ket gʻalaba</span>
        <span class="streak-num">${streak} kun</span>
      </div>`;
    }
  }
}

/* ══════════════════════════════════
   STRATEGY
══════════════════════════════════ */
async function loadStrategy() {
  let d = await apiFetch('/api/overview');
  if (!d) d = OV;
  else OV = d;

  const { settings:s, current_balance:cur, planned_balance:plan, summary:sum } = d;

  const abEl = getEl('actual-balance');
  if (abEl) countUp(abEl, cur || 0, 1100);
  txt('planned-balance', fm(plan, false));

  const diff = (cur||0) - (plan||0);
  const de = getEl('bal-diff');
  if (de) { de.textContent = fm(diff); de.className = `bd-val ${diff >= 0 ? 'pos' : 'neg'}`; }

  const totalDays = s?.total_days||0, doneDays = sum?.total_days||0;
  const dpct = totalDays > 0 ? (doneDays/totalDays)*100 : 0;
  setTimeout(() => { const b = getEl('prog-days-bar'); if(b) b.style.width=`${Math.min(dpct,100)}%`; }, 100);
  txt('prog-days-txt', `${doneDays} / ${totalDays}`);

  const startBal = s?.starting_balance||0;
  const balPct = (plan||0) > startBal ? ((cur-startBal)/(plan-startBal))*100 : 0;
  setTimeout(() => { const b = getEl('prog-bal-bar'); if(b) b.style.width=`${Math.min(Math.max(balPct,0),100)}%`; }, 100);
  txt('prog-bal-txt', `${Math.max(0, Math.round(balPct))}%`);

  const pnl = sum?.total_pnl||0, winsD = sum?.win_days||0, losses = sum?.loss_days||0;
  const wr = doneDays > 0 ? Math.round((winsD/doneDays)*100) : 0;
  const pe = getEl('total-pnl');
  if (pe) { pe.textContent = fm(pnl); pe.className = `sbv ${pnl >= 0 ? 'green' : 'red'}`; }
  txt('win-rate',  `${wr}%`);
  txt('win-days',  String(winsD));
  txt('loss-days', String(losses));

  txt('s-startbal', s?.starting_balance ? `${Number(s.starting_balance).toLocaleString()}$` : '—');
  txt('s-rate',     s?.daily_profit_rate ? `${(s.daily_profit_rate*100).toFixed(1)}%` : '—');
  txt('s-days',     s?.total_days ? `${s.total_days} kun` : '—');
  txt('s-date',     s?.start_date || '—');
  txt('s-broker',   s?.broker_name || '—');

  const comp = JOURNAL.filter(j => j.is_completed && j.net_pnl != null);
  if (comp.length) {
    const pnls = comp.map(j => j.net_pnl);
    const avg  = pnls.reduce((a,b) => a+b, 0) / pnls.length;
    const best = Math.max(...pnls), worst = Math.min(...pnls);
    const fmt  = v => (v>=0?'+':'')+v.toFixed(0)+'$';
    txt('kpi-avg', fmt(avg)); txt('kpi-best', fmt(best)); txt('kpi-worst', fmt(worst));
  }

  txt('flow-total',  SUM.total_trades);
  txt('flow-wins',   SUM.wins);
  txt('flow-losses', SUM.losses);
  txt('flow-bwin',   fa(SUM.biggest_win));
  txt('flow-bloss',  fa(SUM.biggest_loss));
  txt('flow-hwins',  (SUM.avg_hold_win||0)+'d');
  txt('flow-hloss',  (SUM.avg_hold_loss||0)+'d');

  // Hex map — strategy tab da 'hex-svg' ID
  const hexSvg = getEl('hex-svg');
  if (hexSvg) renderHexMapTo('hex-svg', JOURNAL, totalDays || 30);

  let streak = 0;
  for (let i = JOURNAL.length-1; i >= 0; i--) {
    if (JOURNAL[i].is_completed && !JOURNAL[i].is_rolled_over) streak++;
    else break;
  }
  const sw = getEl('streak-wrap');
  if (sw && streak > 0) {
    sw.innerHTML = `<div class="streak">
      <span class="streak-icon">🔥</span>
      <span class="streak-txt">Joriy ketma-ket gʻalaba</span>
      <span class="streak-num">${streak} kun</span>
    </div>`;
  }
}

/* ══════════════════════════════════
   JOURNAL
══════════════════════════════════ */
async function loadJournal() {
  const jb = getEl('journal-tbody');
  if (!jb) return;
  jb.innerHTML = '<tr><td colspan="5"><div class="loading-box"><div class="spinner"></div></div></td></tr>';

  const [jData, statsData] = await Promise.all([
    apiFetch('/api/journal'),
    apiFetch('/api/stats'),
  ]);

  if (jData?.journal?.length) JOURNAL = jData.journal;

  if (!JOURNAL.length) {
    jb.innerHTML = '<tr><td colspan="5"><div class="empty-box">Ma\'lumot topilmadi</div></td></tr>';
    return;
  }

  window._journalData   = JOURNAL;
  window._journalSort   = 'desc';
  window._journalFilter = 'all';
  renderJournalTable();

  if (statsData) {
    SUM = {
      total_trades:    statsData.total_trades    || 0,
      wins:            statsData.wins            || 0,
      losses:          statsData.losses          || 0,
      break_even:      statsData.break_even      || 0,
      biggest_win:     statsData.biggest_win     || 0,
      biggest_loss:    statsData.biggest_loss    || 0,
      avg_hold_win:    statsData.avg_hold_win    || 0,
      avg_hold_loss:   statsData.avg_hold_loss   || 0,
      wins_gross:      statsData.wins_gross      || 0,
      wins_swap:       statsData.wins_swap       || 0,
      wins_commission: statsData.wins_commission || 0,
      wins_net:        statsData.wins_net        || 0,
      wins_pct:        statsData.wins_pct        || 0,
      wins_rr:         statsData.wins_rr         || 0,
      be_gross:        statsData.be_gross        || 0,
      be_swap:         statsData.be_swap         || 0,
      be_commission:   statsData.be_commission   || 0,
      be_net:          statsData.be_net          || 0,
      be_pct:          statsData.be_pct          || 0,
      be_rr:           statsData.be_rr           || 0,
      loss_gross:      statsData.loss_gross      || 0,
      loss_swap:       statsData.loss_swap       || 0,
      loss_commission: statsData.loss_commission || 0,
      loss_net:        statsData.loss_net        || 0,
      loss_pct:        statsData.loss_pct        || 0,
      loss_rr:         statsData.loss_rr         || 0,
      total_gross:     statsData.total_gross     || 0,
      total_swap:      statsData.total_swap      || 0,
      total_commission:statsData.total_commission|| 0,
      total_net:       statsData.total_net       || 0,
      total_pct:       statsData.total_pct       || 0,
      total_rr:        statsData.total_rr        || 0,
    };
  }

  // Result table
  const rtb = getEl('result-tbody');
  if (rtb) {
    const rows = [
      { l:'Wins',        c:'trw',   gross:SUM.wins_gross,  swap:SUM.wins_swap,  comm:SUM.wins_commission,  net:SUM.wins_net,  pct:SUM.wins_pct,  rr:SUM.wins_rr,  rc:'rr-w' },
      { l:'Break Evens', c:'',      gross:SUM.be_gross,    swap:SUM.be_swap,    comm:SUM.be_commission,    net:SUM.be_net,    pct:SUM.be_pct,    rr:SUM.be_rr,    rc:'rr-b' },
      { l:'Losses',      c:'trl',   gross:SUM.loss_gross,  swap:SUM.loss_swap,  comm:SUM.loss_commission,  net:SUM.loss_net,  pct:SUM.loss_pct,  rr:SUM.loss_rr,  rc:'rr-l' },
      { l:'Total',       c:'trtot', gross:SUM.total_gross, swap:SUM.total_swap, comm:SUM.total_commission, net:SUM.total_net, pct:SUM.total_pct, rr:SUM.total_rr, rc:'rr-w' },
    ];
    rtb.innerHTML = rows.map(r => {
      const nc  = (r.net||0) >= 0 ? 'pp' : 'pn';
      const pa  = (r.pct||0) >= 0 ? '▲' : '▼';
      const pc  = (r.pct||0) >= 0 ? 'ppos' : 'pneg';
      const rrt = r.rr != null ? ((r.rr>=0?'+':'')+r.rr.toFixed(2)+'R:R') : '—';
      const f   = v => v != null ? fm(v, v<0) : '—';
      return `<tr class="${r.c}">
        <td class="rl">${r.l}</td>
        <td>${f(r.gross)}</td>
        <td class="${(r.swap||0)<0?'pn':''}">${f(r.swap)}</td>
        <td class="${(r.comm||0)<0?'pn':''}">${f(r.comm)}</td>
        <td class="${nc}">${f(r.net)}</td>
        <td class="${pc}">${r.pct!=null?`${pa} ${Math.abs(r.pct).toFixed(2)}%`:'—'}</td>
        <td><span class="rr-tag ${r.rc}">${rrt}</span></td>
      </tr>`;
    }).join('');
  }

  txt('rs-total', SUM.total_trades);
  txt('rs-wins',  SUM.wins);
  txt('rs-be',    SUM.break_even);
  txt('rs-losses',SUM.losses);

  renderCustomPie();
}

function renderCustomPie() {
  const SEGMENTS = [
    { name:'Wins',  key:'wins',       color:'#06ffa5', bg:'rgba(6,255,165,0.08)',  border:'rgba(6,255,165,0.3)',  glow:'rgba(6,255,165,0.5)'  },
    { name:'BE',    key:'break_even', color:'#ffb020', bg:'rgba(255,176,32,0.08)', border:'rgba(255,176,32,0.3)', glow:'rgba(255,176,32,0.5)' },
    { name:'Loss',  key:'losses',     color:'#ff3060', bg:'rgba(255,48,96,0.08)',  border:'rgba(255,48,96,0.3)',  glow:'rgba(255,48,96,0.5)'  },
  ];
  const GAP=4, CX=60, CY=60, INNER=30, OUTER=52, OUTER_ACTIVE=58;
  const values = SEGMENTS.map(s => SUM[s.key] || 0);
  const total  = values.reduce((a,b) => a+b, 0);
  const pct    = v => total > 0 ? ((v/total)*100).toFixed(1) : '0';
  let activeIdx = null;

  function polarToXY(cx, cy, r, angleDeg) {
    const rad = (angleDeg - 90) * Math.PI / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }
  function describeSlice(cx, cy, innerR, outerR, startDeg, endDeg) {
    const s1 = polarToXY(cx, cy, outerR, startDeg);
    const e1 = polarToXY(cx, cy, outerR, endDeg);
    const s2 = polarToXY(cx, cy, innerR, endDeg);
    const e2 = polarToXY(cx, cy, innerR, startDeg);
    const large = endDeg - startDeg > 180 ? 1 : 0;
    return [`M ${s1.x} ${s1.y}`,`A ${outerR} ${outerR} 0 ${large} 1 ${e1.x} ${e1.y}`,`L ${s2.x} ${s2.y}`,`A ${innerR} ${innerR} 0 ${large} 0 ${e2.x} ${e2.y}`,'Z'].join(' ');
  }

  const slices = [];
  let angle = 0;
  values.forEach((val, i) => {
    const sweep = total > 0 ? (val/total)*(360-SEGMENTS.length*GAP) : 0;
    slices.push({ startDeg:angle+GAP/2, endDeg:angle+GAP/2+sweep, idx:i });
    angle += sweep + GAP;
  });

  const animRadii  = slices.map(() => OUTER);
  const animOpacity= slices.map(() => 1.0);
  let   animRaf    = null;

  function animatePie(targetIdx) {
    if (animRaf) cancelAnimationFrame(animRaf);
    const targetR = slices.map((_,i) => targetIdx===i ? OUTER_ACTIVE : OUTER);
    const targetO = slices.map((_,i) => targetIdx===null||targetIdx===i ? 1.0 : 0.28);
    const t0=performance.now();
    const tick = now => {
      const p=Math.min((now-t0)/380,1), ease=1-Math.pow(1-p,3);
      let done=true;
      slices.forEach((_,i) => {
        animRadii[i]  += (targetR[i]-animRadii[i])*ease;
        animOpacity[i]+= (targetO[i]-animOpacity[i])*ease;
        if (Math.abs(animRadii[i]-targetR[i])>0.05) done=false;
      });
      rebuildPaths();
      if (!done||p<1) animRaf=requestAnimationFrame(tick);
    };
    animRaf=requestAnimationFrame(tick);
  }

  let pieSvg = null;
  const legendWrap = getEl('pie-legend');

  function rebuildPaths() {
    if (!pieSvg) return;
    const pg = pieSvg.querySelector('.pie-paths');
    const cg = pieSvg.querySelector('.pie-center');
    if (!pg||!cg) return;
    pg.innerHTML = slices.map(({startDeg,endDeg,idx}) => {
      const d=describeSlice(CX,CY,INNER,animRadii[idx],startDeg,endDeg);
      return `<path d="${d}" fill="${SEGMENTS[idx].color}" opacity="${animOpacity[idx].toFixed(3)}" ${activeIdx===idx?`filter="url(#gp-${idx})"`:''}  data-idx="${idx}" class="pie-slice" style="cursor:pointer"/>`;
    }).join('');
    pg.querySelectorAll('.pie-slice').forEach(p => {
      const i=parseInt(p.dataset.idx);
      p.addEventListener('pointerdown', e=>{e.preventDefault();toggleSlice(i);},{passive:false});
    });
    if (activeIdx!==null) {
      const s=SEGMENTS[activeIdx];
      cg.innerHTML=`<text x="${CX}" y="${CY-5}" text-anchor="middle" dominant-baseline="middle" font-size="15" font-weight="700" font-family="Space Mono,monospace" fill="${s.color}">${values[activeIdx]}</text><text x="${CX}" y="${CY+11}" text-anchor="middle" dominant-baseline="middle" font-size="8" font-family="Space Mono,monospace" fill="${s.color}" opacity="0.7">${pct(values[activeIdx])}%</text>`;
    } else {
      cg.innerHTML=`<text x="${CX}" y="${CY-5}" text-anchor="middle" dominant-baseline="middle" font-size="16" font-weight="700" font-family="Space Mono,monospace" fill="white">${total}</text><text x="${CX}" y="${CY+11}" text-anchor="middle" dominant-baseline="middle" font-size="7" font-weight="700" font-family="Space Mono,monospace" fill="rgba(255,255,255,0.3)" letter-spacing="2">JAMI</text>`;
    }
  }

  function toggleSlice(i) { haptic('light'); activeIdx=activeIdx===i?null:i; animatePie(activeIdx); updateLegend(); }

  function updateLegend() {
    if (!legendWrap) return;
    legendWrap.innerHTML = SEGMENTS.map((s,i) => {
      const a=activeIdx===i;
      return `<div class="pie-leg-row" data-idx="${i}" style="cursor:pointer;display:flex;align-items:center;gap:8px;font-size:11px;padding:3px 6px;border-radius:8px;background:${a?s.bg:'transparent'};border:1px solid ${a?s.border:'transparent'};box-shadow:${a?`0 0 14px ${s.glow}`:'none'}">
        <span style="background:${s.color};width:7px;height:7px;border-radius:2px;flex-shrink:0;box-shadow:${a?`0 0 6px ${s.color}`:'none'}"></span>
        <span style="flex:1;color:${a?'white':'var(--ink2)'}">${s.name}</span>
        <span style="font-family:var(--mono);font-size:12px;font-weight:700;color:${a?s.color:'var(--ink0)'}">
          ${values[i]}<em style="font-style:normal;font-size:9px;margin-left:3px;color:${a?s.color:'var(--ink2)'}"> ${pct(values[i])}%</em>
        </span>
      </div>`;
    }).join('');
    legendWrap.querySelectorAll('.pie-leg-row').forEach(row => {
      const i=parseInt(row.dataset.idx);
      row.addEventListener('pointerdown', e=>{e.preventDefault();toggleSlice(i);},{passive:false});
    });
  }

  const defs = SEGMENTS.map((_,i) => `<filter id="gp-${i}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`).join('');
  const track = `<circle cx="${CX}" cy="${CY}" r="${(INNER+OUTER)/2}" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="${OUTER-INNER}"/>`;

  const svgWrap = document.createElement('div');
  svgWrap.style.cssText = 'position:relative;flex-shrink:0;width:120px;height:120px';
  svgWrap.innerHTML = `<svg width="120" height="120" viewBox="0 0 120 120" style="display:block;overflow:visible;background:transparent"><defs>${defs}</defs>${track}<g class="pie-paths"></g><g class="pie-center"></g></svg>`;
  pieSvg = svgWrap.querySelector('svg');

  const oldCanvas = getEl('pie-chart');
  if (oldCanvas) oldCanvas.replaceWith(svgWrap);

  rebuildPaths();
  updateLegend();
}

/* ══════════════════════════════════
   JOURNAL FILTER / SORT
══════════════════════════════════ */
function renderJournalTable() {
  const jb = getEl('journal-tbody'); if (!jb) return;
  let rows = window._journalData || [];
  const filter   = window._journalFilter || 'all';
  const sort     = window._journalSort   || 'desc';
  const isJournal = window._mode === 'journal';

  if (filter === 'win')  rows = rows.filter(j => j.is_completed && !j.is_rolled_over);
  if (filter === 'loss') rows = rows.filter(j => j.is_completed &&  j.is_rolled_over);
  if (filter === 'pend') rows = rows.filter(j => !j.is_completed);

  rows = [...rows].sort((a,b) => sort === 'desc' ? b.day_number - a.day_number : a.day_number - b.day_number);

  if (!rows.length) {
    jb.innerHTML = `<tr><td colspan="5"><div class="empty-box">Ma'lumot topilmadi</div></td></tr>`;
    return;
  }

  jb.innerHTML = rows.map(j => {
    const pc    = (j.net_pnl||0) >= 0 ? 'pp' : 'pn';
    const rc    = !j.is_completed ? '' : j.is_rolled_over ? 'jl' : 'jw';
    const badge = !j.is_completed
      ? '<span class="badge bp">Davom</span>'
      : j.is_rolled_over
        ? '<span class="badge bl">Rollover</span>'
        : '<span class="badge bw">✓ Bajarildi</span>';
    const targetCell = isJournal ? '' : `<td class="mono" style="font-size:11px">${fm(j.target,false)}</td>`;
    return `<tr class="${rc}" onclick="haptic();openDay(${j.day_number})" style="cursor:pointer">
      <td>${j.day_number}</td>
      <td class="mono" style="font-size:11px">${j.date}</td>
      ${targetCell}
      <td class="${pc}">${fm(j.net_pnl)}</td>
      <td>${badge}</td>
    </tr>`;
  }).join('');
}

function setJFilter(btn, filter) {
  haptic();
  window._journalFilter = filter;
  document.querySelectorAll('.jfbtn').forEach(b => b.classList.remove('active','win-f','loss-f','pend-f'));
  btn.classList.add('active');
  if (filter === 'win')  btn.classList.add('win-f');
  if (filter === 'loss') btn.classList.add('loss-f');
  if (filter === 'pend') btn.classList.add('pend-f');
  renderJournalTable();
}

function toggleJSort() {
  haptic();
  window._journalSort = window._journalSort === 'desc' ? 'asc' : 'desc';
  const lbl = getEl('jsort-lbl'); const arr = getEl('jsort-arr');
  if (lbl) lbl.textContent = window._journalSort === 'desc' ? 'Yangi → Eski' : 'Eski → Yangi';
  if (arr) arr.classList.toggle('up', window._journalSort === 'asc');
  renderJournalTable();
}

/* ══════════════════════════════════
   DAY DETAIL
══════════════════════════════════ */
async function openDay(dayNum) {
  haptic('medium');
  getEl('main-header').style.display  = 'none';
  getEl('detail-header').style.display = '';
  getEl('main-view').style.display    = 'none';
  getEl('detail-view').style.display  = '';
  txt('detail-badge', `${dayNum}-KUN`);
  getEl('day-card').innerHTML    = '<div class="loading-box"><div class="spinner"></div></div>';
  getEl('trades-list').innerHTML = '<div class="loading-box"><div class="spinner"></div></div>';

  const data = await apiFetch('/api/day_detail', `&day_number=${dayNum}`);
  if (!data) {
    getEl('day-card').innerHTML    = '<div class="empty-box">Ma\'lumot topilmadi</div>';
    getEl('trades-list').innerHTML = '';
    return;
  }

  const { journal:j, trades } = data;
  const isWin  = j.is_completed && !j.is_rolled_over;
  const isLoss = j.is_completed &&  j.is_rolled_over;
  const rc = isWin ? 'win' : isLoss ? 'loss' : 'neutral';
  const rt = isWin ? '✅ Maqsad bajarildi' : isLoss ? '❌ Rollover' : '⏳ Davom etmoqda';

  getEl('day-card').innerHTML = `
    <div class="card-title"><span class="ctdot"></span>${j.day_number}-kun — ${j.date}</div>
    <div class="day-grid">
      <div class="stat-box"><div class="sbl">Boshlang'ich</div><div class="sbv" style="font-size:16px">${fm(j.start_balance,false)}</div></div>
      <div class="stat-box"><div class="sbl">Yakuniy</div><div class="sbv ${(j.net_pnl||0)>=0?'green':'red'}" style="font-size:16px">${fm(j.end_balance,false)}</div></div>
      <div class="stat-box"><div class="sbl">Maqsad</div><div class="sbv blue" style="font-size:16px">${fm(j.total_target,false)}</div></div>
      <div class="stat-box"><div class="sbl">Net PnL</div><div class="sbv ${(j.net_pnl||0)>=0?'green':'red'}" style="font-size:16px">${fm(j.net_pnl)}</div></div>
    </div>
    <div class="day-result ${rc}">
      <span style="font-weight:600">${rt}</span>
      <span class="mono" style="font-size:11px">${(trades||[]).length} savdo</span>
    </div>`;

  if (!trades || !trades.length) {
    getEl('trades-list').innerHTML = '<div class="empty-box">Savdolar yo\'q</div>';
    return;
  }
  window._trades = trades;
  getEl('trades-list').innerHTML = trades.map((t,i) => {
    const sc = {tp:'tp',sl:'sl',be:'be'}[t.exit_type] || 'manual';
    const pc = (t.net_pnl||0) >= 0 ? 'pp' : 'pn';
    return `<div class="trade-item fade-in" style="animation-delay:${i*0.05}s" onclick="haptic();openModal(${i})">
      <div class="tbar ${sc}"></div>
      <div class="tbody2">
        <div class="tr1"><span class="tsym">${t.symbol||'—'}</span><span class="tpnl ${pc}">${fm(t.net_pnl)}</span></div>
        <div class="tr2"><span class="tprice">${fp(t.open_price)} → ${fp(t.close_price)}</span><span class="tlot">${t.quantity} lot</span></div>
      </div>
      ${t.direction?`<span class="dir ${t.direction.toLowerCase()}">${t.direction.toUpperCase()}</span>`:''}
    </div>`;
  }).join('');
}

function openModal(i) {
  haptic();
  const t = (window._trades||[])[i]; if (!t) return;
  getEl('modal-body').innerHTML = `
    <div class="mhandle"></div>
    <div class="mtitle">${t.symbol||'—'} ${t.direction?`<span class="dir ${t.direction.toLowerCase()}">${t.direction.toUpperCase()}</span>`:''}</div>
    <div class="mrow"><span class="ml">Kirish narxi</span><span class="mv">${fp(t.open_price)}</span></div>
    <div class="mrow"><span class="ml">Chiqish narxi</span><span class="mv">${fp(t.close_price)}</span></div>
    <div class="mrow"><span class="ml">Hajm (lot)</span><span class="mv">${t.quantity}</span></div>
    <div class="msep"></div>
    <div class="mrow"><span class="ml">Gross PnL</span><span class="mv ${(t.pnl||0)>=0?'pp':'pn'}">${fm(t.pnl)}</span></div>
    ${t.swap  ? `<div class="mrow"><span class="ml">Swap</span><span class="mv ${(t.swap||0)>=0?'pp':'pn'}">${fm(t.swap)}</span></div>` : ''}
    ${t.commission ? `<div class="mrow"><span class="ml">Komissiya</span><span class="mv pn">${fm(t.commission)}</span></div>` : ''}
    <div class="mrow"><span class="ml">Net PnL</span><span class="mv ${(t.net_pnl||0)>=0?'pp':'pn'}" style="font-size:15px">${fm(t.net_pnl)}</span></div>
    ${t.sl_price||t.tp_price ? '<div class="msep"></div>' : ''}
    ${t.sl_price  ? `<div class="mrow"><span class="ml">Stop Loss</span><span class="mv pn">${fp(t.sl_price)}</span></div>` : ''}
    ${t.tp_price  ? `<div class="mrow"><span class="ml">Take Profit</span><span class="mv pp">${fp(t.tp_price)}</span></div>` : ''}
    ${t.open_time ? `<div class="mrow"><span class="ml">Ochilish</span><span class="mv">${t.open_time}</span></div>` : ''}
    ${t.close_time? `<div class="mrow"><span class="ml">Yopilish</span><span class="mv">${t.close_time}</span></div>` : ''}
    ${t.order_id  ? `<div class="mrow"><span class="ml">Order ID</span><span class="mv" style="font-size:11px">#${t.order_id}</span></div>` : ''}`;
  getEl('trade-modal').style.display = '';
}

const modalBg = getEl('modal-bg');
if (modalBg) modalBg.addEventListener('click', () => { haptic(); getEl('trade-modal').style.display = 'none'; });

const backBtn = getEl('back-btn');
if (backBtn) backBtn.addEventListener('click', () => {
  haptic();
  getEl('main-header').style.display   = '';
  getEl('detail-header').style.display = 'none';
  getEl('main-view').style.display     = '';
  getEl('detail-view').style.display   = 'none';
  window._trades = [];
});

/* ══════════════════════════════════
   ANALIZ
══════════════════════════════════ */
let pnlChart=null, balChart=null;

async function loadAnaliz() {
  const pw = getEl('chart-pnl-wrap');
  const bw = getEl('chart-balance-wrap');
  if (pw) pw.innerHTML = '<div class="loading-box"><div class="spinner"></div></div>';
  if (bw) bw.innerHTML = '<div class="loading-box"><div class="spinner"></div></div>';

  // Chart.js yuklanganini tekshirish
  if (typeof Chart === 'undefined') {
    if (pw) pw.innerHTML = '<div class="empty-box">Chart yuklanmoqda...</div>';
    setTimeout(loadAnaliz, 500);
    return;
  }

  let [chartData, analData] = await Promise.all([
    apiFetch('/api/chart_data'),
    apiFetch('/api/analiz'),
  ]);

  // Fallback demo data
  if (!chartData) {
    chartData = {
      actual_dates:  PROGRESSION.map(d=>d.date.slice(5)),
      actual:        PROGRESSION.map(d=>d.start_balance+d.actual_pnl),
      pnl:           PROGRESSION.map(d=>d.actual_pnl),
      planned_dates: PROGRESSION.map(d=>d.date.slice(5)),
      planned:       PROGRESSION.map(d=>d.final_balance),
    };
  }

  const grid = 'rgba(255,255,255,0.04)', hint = '#546278';
  const BASE = {
    responsive:true, maintainAspectRatio:false,
    interaction:{ mode:'index', intersect:false },
    plugins:{
      legend:{ labels:{ color:'#a0aec4', font:{size:10}, boxWidth:10, padding:14 } },
      tooltip:{
        backgroundColor:'#07070f', borderColor:'rgba(61,127,255,0.2)', borderWidth:1,
        titleColor:'#f0f4ff', bodyColor:'#8fa4c8',
        callbacks:{ label: ctx => {
          if(ctx.raw==null) return null;
          const v=Number(ctx.raw);
          return ` ${ctx.dataset.label}: ${v>=0?'+':''}$${v.toLocaleString('en-US',{minimumFractionDigits:2})}`;
        }}
      },
    },
    scales:{
      x:{ ticks:{color:hint,font:{size:9,family:"'Space Mono'"},maxRotation:45,maxTicksLimit:10}, grid:{color:grid,drawBorder:false} },
      y:{ ticks:{color:hint,font:{size:9,family:"'Space Mono'"},callback:v=>`$${Number(v).toLocaleString()}`}, grid:{color:grid,drawBorder:false} },
    },
  };

  // PnL Bar chart
  const pnlD = chartData.pnl || [];
  const pnlLabels = chartData.actual_dates || [];
  if (pw) pw.innerHTML = '<canvas id="pnl-canvas" height="200"></canvas>';
  const pctx = getEl('pnl-canvas')?.getContext('2d');
  if (pctx) {
    if (pnlChart) { pnlChart.destroy(); pnlChart=null; }
    pnlChart = new Chart(pctx, {
      type:'bar',
      data:{ labels:pnlLabels, datasets:[{
        label:'Kunlik PnL', data:pnlD,
        backgroundColor:pnlD.map(v=>v>=0?'rgba(0,232,122,0.72)':'rgba(255,45,85,0.68)'),
        borderColor:pnlD.map(v=>v>=0?'#39ffac':'#ff6080'),
        borderWidth:1, borderRadius:5
      }]},
      options:{ ...BASE, plugins:{...BASE.plugins, legend:{display:false}} }
    });
  }

  // Balance Line chart
  if (bw) bw.innerHTML = '<canvas id="bal-canvas" height="220"></canvas>';
  const bctx = getEl('bal-canvas')?.getContext('2d');
  if (bctx) {
    if (balChart) { balChart.destroy(); balChart=null; }
    const datasets = [];
    if ((chartData.planned||[]).length) {
      datasets.push({
        label:'Rejalangan', data:chartData.planned,
        borderColor:'#00b4ff', borderWidth:1.5, borderDash:[5,5],
        pointRadius:0, fill:false, tension:.3, spanGaps:true
      });
    }
    datasets.push({
      label:'Haqiqiy', data:chartData.actual,
      borderColor:'#00e87a', backgroundColor:'rgba(0,232,122,0.1)',
      borderWidth:2, pointRadius:3, pointBackgroundColor:'#39ffac',
      fill:true, tension:.3, spanGaps:false
    });
    balChart = new Chart(bctx, {
      type:'line',
      data:{ labels: chartData.actual_dates || chartData.planned_dates || [], datasets },
      options:{ ...BASE, maintainAspectRatio:false }
    });
  }

  // Performance rings
  const done      = JOURNAL.filter(j => j.is_completed);
  const winsCount = done.filter(j => !j.is_rolled_over).length;
  const wr        = done.length > 0 ? (winsCount/done.length)*100 : 0;
  const s         = OV?.settings?.starting_balance || 0;
  const c         = OV?.current_balance || 0;
  const p         = OV?.planned_balance || 0;
  const progPct   = p > s ? ((c-s)/(p-s))*100 : 0;
  const grossWin  = Math.abs(SUM.wins_gross  || 0);
  const grossLoss = Math.abs(SUM.loss_gross  || 0);
  const pf        = grossLoss > 0 ? grossWin/grossLoss : grossWin>0 ? 99 : 0;
  const pfPct     = Math.min((pf/4)*100, 100);

  animateRing('ring-wr',   wr);
  animateRing('ring-prog', Math.max(0, progPct));
  animateRing('ring-pf',   pfPct);
  txt('ring-wr-val',   wr.toFixed(0)+'%');
  txt('ring-prog-val', Math.max(0,Math.round(progPct))+'%');
  txt('ring-pf-val',   pf.toFixed(2));

  buildRadar(analData?.evaluation ?? null);
}

/* AI tahlil */
async function runAI() {
  const btn = getEl('ai-btn');
  const body = getEl('ai-body');
  if (!btn || !body) return;
  haptic('medium');
  btn.classList.add('busy');
  txt('ai-btn-txt', 'Tahlil qilinmoqda...');

  body.innerHTML = `<div class="ai-typing"><div class="ai-dots"><span></span><span></span><span></span></div><span>AI tahlil qilmoqda...</span></div>`;

  try {
    // Ma'lumotlarni to'plash
    const comp = JOURNAL.filter(j => j.is_completed);
    const wins = comp.filter(j => !j.is_rolled_over).length;
    const wr   = comp.length > 0 ? Math.round((wins/comp.length)*100) : 0;
    const totalPnl = comp.reduce((s,j) => s+(j.net_pnl||0), 0);

    const prompt = `Men bir trader haqida ma'lumot beraman. Quyidagi ko'rsatkichlar asosida qisqa, amaliy va motivatsion tahlil ber (o'zbek tilida, 3-4 paragraf):

📊 Statistika:
- Jami kunlar: ${comp.length}
- Win Rate: ${wr}%
- Jami PnL: $${totalPnl.toFixed(2)}
- G'alaba kunlar: ${wins}
- Rollover kunlar: ${comp.length - wins}
- Eng katta g'alaba: $${SUM.biggest_win?.toFixed(2)||0}
- Eng katta zarar: $${Math.abs(SUM.biggest_loss||0).toFixed(2)}

Tahlil qil va maslahat ber. Qisqa va aniq bo'l.`;

    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "claude-sonnet-4-20250514",
        max_tokens: 1000,
        messages: [{ role: "user", content: prompt }]
      })
    });

    const data = await response.json();
    const text = data.content?.map(i => i.text||'').join('\n') || "Tahlil qilishda xatolik yuz berdi.";

    const positives = [];
    const negatives = [];
    if (wr >= 60) positives.push('Win rate yaxshi'); else negatives.push('Win rate past');
    if (totalPnl > 0) positives.push('Musbat PnL'); else negatives.push('Manfiy PnL');

    body.innerHTML = `
      <div class="ai-tags">
        ${positives.map(t=>`<span class="ai-tag atp">✓ ${t}</span>`).join('')}
        ${negatives.map(t=>`<span class="ai-tag atn">✗ ${t}</span>`).join('')}
      </div>
      <div class="ai-result">${text.split('\n').filter(Boolean).map(p=>`<p>${p}</p>`).join('')}</div>
      <button class="ai-retry" onclick="resetAI()">🔄 Qayta tahlil</button>`;
  } catch (err) {
    body.innerHTML = `
      <div class="ai-placeholder">
        <div class="ai-icon">⚠️</div>
        <div class="ai-hint">AI tahlil vaqtincha mavjud emas</div>
        <button class="ai-btn" onclick="resetAI()">Qayta urinib ko'ring</button>
      </div>`;
  }
}

function resetAI() {
  const body = getEl('ai-body');
  if (body) body.innerHTML = `
    <div class="ai-placeholder">
      <div class="ai-icon">🤖</div>
      <div class="ai-hint">Trading natijalari asosida shaxsiy tahlil va maslahat olish uchun bosing</div>
      <button class="ai-btn" id="ai-btn" onclick="runAI()"><span id="ai-btn-txt">Tahlil qilish</span></button>
    </div>`;
}

/* ══════════════════════════════════
   SVG RADAR CHART
══════════════════════════════════ */
function buildRadar(ev) {
  const svgEl      = getEl('radar-svg');
  const metricsWrap= getEl('radar-metrics');
  const tooltip    = getEl('radar-tooltip');
  const scoreNum   = getEl('radar-score-num');
  if (!svgEl) return;

  const d = ev ?? { rte_ratio:72, profit_factor:85, sharpe_ratio:60, recovery_factor:74, consistency:52, score:80.53 };
  const norm = (v,m) => Math.min(100, Math.round((v/m)*100));

  const METRICS = [
    { label:'R.T.E Ratio',     key:'rte_ratio',       max:5,   color:'#00d4ff', glow:'rgba(0,212,255,0.55)', bg:'rgba(0,212,255,0.08)',  border:'rgba(0,212,255,0.28)', desc:'Risk/Trade/Equity nisbati' },
    { label:'Profit Factor',   key:'profit_factor',   max:5,   color:'#a78bfa', glow:'rgba(167,139,250,0.55)', bg:'rgba(167,139,250,0.08)', border:'rgba(167,139,250,0.28)', desc:'Jami foyda/zarar nisbati' },
    { label:'Sharpe Ratio',    key:'sharpe_ratio',    max:3,   color:'#34d399', glow:'rgba(52,211,153,0.55)', bg:'rgba(52,211,153,0.08)', border:'rgba(52,211,153,0.28)', desc:'Xatarni hisobga olgan daromad' },
    { label:'Recovery Factor', key:'recovery_factor', max:30,  color:'#fb923c', glow:'rgba(251,146,60,0.55)', bg:'rgba(251,146,60,0.08)', border:'rgba(251,146,60,0.28)', desc:'Tiklanuvchanlik koʻrsatkichi' },
    { label:'Consistency',     key:'consistency',     max:100, color:'#f472b6', glow:'rgba(244,114,182,0.55)', bg:'rgba(244,114,182,0.08)', border:'rgba(244,114,182,0.28)', desc:'Barqarorlik darajasi' },
  ];

  const vals  = METRICS.map(m => ev ? norm(d[m.key], m.max) : d[m.key] || 0);
  const score = Number(d.score ?? 0).toFixed(2);
  if (scoreNum) scoreNum.textContent = score;

  const N=METRICS.length, CX=150, CY=150, R=100;
  const LEVELS=[25,50,75,100];
  const angle = i => (2*Math.PI*i/N) - Math.PI/2;
  const polarPt = (r,i) => ({ x: CX+r*Math.cos(angle(i)), y: CY+r*Math.sin(angle(i)) });
  const polyPts = r => Array.from({length:N},(_,i)=>{ const p=polarPt(r,i); return `${p.x.toFixed(2)},${p.y.toFixed(2)}`; }).join(' ');
  const dataRadii = vals.map(v=>(v/100)*R);
  const dataPts   = METRICS.map((_,i)=>{ const p=polarPt(dataRadii[i],i); return `${p.x.toFixed(2)},${p.y.toFixed(2)}`; }).join(' ');

  if (!document.getElementById('radar-anim-style')) {
    const st = document.createElement('style');
    st.id = 'radar-anim-style';
    st.textContent = `
      @keyframes radarFill { from{opacity:0} to{opacity:1} }
      @keyframes vertexPop { from{r:0;opacity:0} to{r:5px;opacity:1} }
      .r-metric-card { background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:10px 12px;cursor:pointer;transition:all .25s;flex:1;min-width:0; }
      .r-metric-card.active { transform:translateY(-2px); }
      .r-metric-card.dimmed { opacity:.3; }
      .r-metric-top { display:flex;justify-content:space-between;align-items:center;margin-bottom:6px; }
      .r-metric-dot { width:7px;height:7px;border-radius:50%;flex-shrink:0; }
      .r-metric-pct { font-family:var(--mono);font-size:14px;font-weight:700; }
      .r-metric-bar-track { height:3px;background:rgba(255,255,255,0.07);border-radius:99px;overflow:hidden;margin-bottom:5px; }
      .r-metric-bar-fill { height:100%;border-radius:99px;transition:width 1s cubic-bezier(.4,0,.2,1);width:0%; }
      .r-metric-name { font-size:9px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--ink2);margin-bottom:2px; }
      .r-metric-desc { font-size:8px;color:var(--ink3);line-height:1.4; }
      .r-tooltip { position:absolute;background:rgba(10,5,28,0.95);border:1px solid rgba(0,180,255,0.3);border-radius:10px;padding:8px 12px;font-size:11px;pointer-events:none;opacity:0;transition:opacity .2s;z-index:10; }
      .r-tooltip.show { opacity:1; }
      .r-tt-name { font-weight:700;font-size:12px;margin-bottom:3px; }
      .r-tt-val { font-family:var(--mono);font-size:20px;font-weight:700; }
      .r-tt-desc { color:var(--ink2);font-size:10px;margin-top:3px; }
      .r-score-row { display:flex;justify-content:center;margin-bottom:10px; }
      .r-score-badge { display:flex;align-items:baseline;gap:4px; }
      .r-score-lbl { font-size:11px;color:var(--ink2); }
      .r-score-num { font-family:var(--mono);font-size:28px;font-weight:700;background:linear-gradient(135deg,#5cd3ff,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text; }
      .r-svg-wrap { position:relative;width:100%;padding-bottom:8px; }
      .r-metrics-grid { display:flex;gap:6px;flex-wrap:wrap;margin-top:10px; }
    `;
    document.head.appendChild(st);
  }

  const svgContent = `<defs>
    <linearGradient id="rg-fill" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="rgba(0,212,255,0.32)"/>
      <stop offset="50%" stop-color="rgba(167,139,250,0.22)"/>
      <stop offset="100%" stop-color="rgba(244,114,182,0.18)"/>
    </linearGradient>
    <filter id="rg-glow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="3.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="rg-glow-hi" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="7" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    ${METRICS.map((m,i)=>`<radialGradient id="vg-${i}" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="${m.color}" stop-opacity="0.9"/><stop offset="100%" stop-color="${m.color}" stop-opacity="0"/></radialGradient>`).join('')}
  </defs>
  <circle cx="${CX}" cy="${CY}" r="80" fill="url(#rg-fill)" opacity="0.15"/>
  ${LEVELS.map((lvl,li)=>{
    const r=(lvl/100)*R, pts=polyPts(r), alpha=[0.06,0.09,0.13,0.22][li];
    return `<polygon points="${pts}" fill="none" stroke="rgba(255,255,255,${alpha})" stroke-width="${li===3?1.5:0.75}" ${li===3?'filter="url(#rg-glow)"':''}/>`;
  }).join('')}
  ${METRICS.map((_,i)=>{ const p=polarPt(R,i), p0=polarPt(14,i); return `<line x1="${p0.x.toFixed(2)}" y1="${p0.y.toFixed(2)}" x2="${p.x.toFixed(2)}" y2="${p.y.toFixed(2)}" stroke="rgba(168,85,247,0.18)" stroke-width="0.8"/>`; }).join('')}
  <polygon id="rg-data-fill" points="${dataPts}" fill="url(#rg-fill)" opacity="0" style="animation:radarFill 0.7s ease forwards 0.4s"/>
  <polygon id="rg-data-border" points="${dataPts}" fill="none" stroke="rgba(92,211,255,0.75)" stroke-width="2" stroke-linejoin="round" filter="url(#rg-glow)" opacity="0" style="animation:radarFill 0.5s ease forwards 0.5s"/>
  ${METRICS.map((m,i)=>{ const p=polarPt(dataRadii[i],i); return `<circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="12" fill="url(#vg-${i})" opacity="0.45" class="rg-halo" data-idx="${i}"/>`; }).join('')}
  ${METRICS.map((m,i)=>{ const p=polarPt(dataRadii[i],i), delay=0.55+i*0.08; return `<circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="0" fill="${m.color}" stroke="rgba(6,4,15,0.9)" stroke-width="2" class="rg-vertex" data-idx="${i}" style="animation:vertexPop 0.45s cubic-bezier(.4,0,.2,1) forwards ${delay}s;cursor:pointer;filter:url(#rg-glow-hi)"/>`; }).join('')}
  ${METRICS.map((m,i)=>{ const p=polarPt(dataRadii[i],i); return `<circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="20" fill="transparent" class="rg-hit" data-idx="${i}" style="cursor:pointer"/>`; }).join('')}
  ${METRICS.map((m,i)=>{ const LABEL_R=R+24, p=polarPt(LABEL_R,i), a=angle(i), anchor=Math.abs(Math.cos(a))<0.15?'middle':Math.cos(a)>0?'start':'end', dy=Math.sin(a)>0.6?10:Math.sin(a)<-0.6?-4:4; return `<g class="rg-label" data-idx="${i}"><text x="${p.x.toFixed(1)}" y="${(p.y+dy).toFixed(1)}" text-anchor="${anchor}" dominant-baseline="middle" font-family="Sora,sans-serif" font-size="9.5" font-weight="700" fill="${m.color}" opacity="0.72">${m.label}</text><text x="${p.x.toFixed(1)}" y="${(p.y+dy+11).toFixed(1)}" text-anchor="${anchor}" dominant-baseline="middle" font-family="Space Mono,monospace" font-size="10" font-weight="700" fill="${m.color}">${vals[i]}%</text></g>`; }).join('')}`;

  svgEl.innerHTML = svgContent;

  if (metricsWrap) {
    metricsWrap.innerHTML = METRICS.map((m,i) => `
      <div class="r-metric-card" data-idx="${i}">
        <div class="r-metric-top">
          <span class="r-metric-dot" style="background:${m.color};box-shadow:0 0 5px ${m.glow}"></span>
          <span class="r-metric-pct" style="color:${m.color}">${vals[i]}%</span>
        </div>
        <div class="r-metric-bar-track">
          <div class="r-metric-bar-fill" id="rbar-${i}" style="background:${m.color};max-width:${vals[i]}%"></div>
        </div>
        <div class="r-metric-name">${m.label}</div>
        <div class="r-metric-desc">${m.desc}</div>
      </div>`).join('');

    requestAnimationFrame(() => { METRICS.forEach((_,i) => { const bar=getEl(`rbar-${i}`); if(bar) bar.style.width=vals[i]+'%'; }); });
  }

  let _active = null;

  function toggleRadarMetric(i) { _active = _active===i ? null : i; updateRadarActive(); }

  function updateRadarActive() {
    const cards    = metricsWrap?.querySelectorAll('.r-metric-card') || [];
    const vertices = svgEl.querySelectorAll('.rg-vertex');
    const halos    = svgEl.querySelectorAll('.rg-halo');
    const labels   = svgEl.querySelectorAll('.rg-label');
    const fill     = svgEl.querySelector('#rg-data-fill');
    const border   = svgEl.querySelector('#rg-data-border');

    cards.forEach((c,ci) => {
      c.classList.remove('active','dimmed');
      if (_active===null) { c.style.background='rgba(255,255,255,0.03)'; c.style.borderColor='rgba(255,255,255,0.07)'; c.style.boxShadow=''; return; }
      if (ci===_active) { c.classList.add('active'); c.style.background=METRICS[ci].bg; c.style.borderColor=METRICS[ci].border; c.style.boxShadow=`0 0 18px ${METRICS[ci].glow}`; }
      else { c.classList.add('dimmed'); c.style.background='rgba(255,255,255,0.03)'; c.style.borderColor='rgba(255,255,255,0.03)'; c.style.boxShadow=''; }
    });

    vertices.forEach((v,vi) => {
      if (_active===null) { v.style.opacity='1'; v.setAttribute('r','5'); }
      else if (vi===_active) { v.setAttribute('r','7.5'); v.style.opacity='1'; }
      else { v.setAttribute('r','4'); v.style.opacity='0.25'; }
    });

    halos.forEach((h,hi) => { h.style.opacity=(_active===null)?'0.45':(hi===_active)?'0.85':'0.08'; });
    labels.forEach((l,li) => { l.querySelectorAll('text').forEach(t => { t.style.opacity=(_active===null)?'1':(li===_active)?'1':'0.22'; }); });

    if (fill&&border) {
      if (_active!==null) { fill.style.fill=METRICS[_active].bg; fill.style.opacity='0.7'; border.style.stroke=METRICS[_active].color; border.style.strokeWidth='2.5'; }
      else { fill.style.fill='url(#rg-fill)'; fill.style.opacity='1'; border.style.stroke='rgba(92,211,255,0.75)'; border.style.strokeWidth='2'; }
    }

    if (tooltip) {
      if (_active!==null) {
        const m=METRICS[_active];
        const ttName=getEl('rtt-name'), ttVal=getEl('rtt-val'), ttDesc=getEl('rtt-desc');
        if (ttName) { ttName.textContent=m.label; ttName.style.color=m.color; }
        if (ttVal)  { ttVal.textContent=vals[_active]+'%'; ttVal.style.color=m.color; }
        if (ttDesc) ttDesc.textContent=m.desc;
        const p=polarPt(dataRadii[_active],_active);
        tooltip.style.left = Math.max(5,Math.min(55,(p.x/300)*100-18))+'%';
        tooltip.style.top  = Math.max(5,Math.min(80,(p.y/300)*100-22))+'%';
        tooltip.style.borderColor = m.border;
        tooltip.classList.add('show');
      } else { tooltip.classList.remove('show'); }
    }
  }

  svgEl.querySelectorAll('.rg-hit').forEach(hit => {
    const i=parseInt(hit.dataset.idx);
    hit.addEventListener('pointerdown', e=>{e.preventDefault();e.stopPropagation();haptic('light');toggleRadarMetric(i);},{passive:false});
  });

  metricsWrap?.querySelectorAll('.r-metric-card').forEach(card => {
    const i=parseInt(card.dataset.idx);
    card.addEventListener('pointerdown', e=>{e.preventDefault();haptic('light');toggleRadarMetric(i);},{passive:false});
  });

  svgEl.addEventListener('pointerdown', e=>{
    if (!e.target.classList.contains('rg-hit') && !e.target.classList.contains('rg-vertex')) {
      if (_active!==null) { _active=null; updateRadarActive(); haptic('light'); }
    }
  },{passive:false});
}

/* ── START ── */
loadOverview();
