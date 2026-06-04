'use strict';

/* ─── TELEGRAM ─── */
const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }
const TG_ID = tg?.initDataUnsafe?.user?.id || null;

/* ─── GLOBAL MODE ─── */
// 'strategy' yoki 'journal' — API dan olinadi
window._mode = 'strategy';

function applyMode(mode) {
  window._mode = mode || 'strategy';
  // Journal rejimida "Strategiya" tab yashiriladi
  const stratTab = document.querySelector('.tab[data-tab="strategy"]');
  if (stratTab) stratTab.style.display = mode === 'journal' ? 'none' : '';
  // Header chip matn
  const chip = document.querySelector('.header-chip');
  if (chip) chip.textContent = mode === 'journal' ? 'JURNAL' : 'LIVE';
}

/* ─── DEMO DATA ─── */
const mkRng = (seed) => { let x = seed; return () => { x = (x*9301+49297)%233280; return x/233280; }; };

const JOURNAL = (() => {
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

const OV = {
  current_balance: 2847.50, planned_balance: 3124.00,
  settings: { starting_balance: 2000, daily_profit_rate: 0.20, total_days: 30, start_date: '2025-04-01', broker_name: 'MetaTrader 5' },
  summary: { total_days: 20, win_days: 15, loss_days: 3, total_pnl: 847.50 }
};

const SUM = {
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
    if (!r.ok) {
      console.error(`apiFetch xato [${ep}]: HTTP ${r.status}`);
      return null;
    }
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
const $  = id => document.getElementById(id);
const txt = (id, v) => { const e = $(id); if (e) e.textContent = v ?? '—'; };

function haptic(t='light') { try { tg?.HapticFeedback?.impactOccurred?.(t); } catch {} }

function showToast(msg) {
  let el = $('__toast');
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
  const el = $(id); if (!el) return;
  const C = 2 * Math.PI * 37; // r=37
  setTimeout(() => { el.style.strokeDashoffset = C - (Math.min(Math.max(pct,0),100)/100)*C; }, 300);
}

/* ─── TABS ─── */
const tabLoaded = { overview:true, strategy:false, journal:false, analiz:false };

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    const name = btn.dataset.tab; haptic();
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    $(`tab-${name}`)?.classList.add('active');
    if (name === 'strategy'&& !tabLoaded.strategy){ loadStrategy(); tabLoaded.strategy= true; }
    if (name === 'journal' && !tabLoaded.journal) { loadJournal(); tabLoaded.journal = true; }
    if (name === 'analiz'  && !tabLoaded.analiz)  { loadAnaliz();  tabLoaded.analiz  = true; }
  });
});

/* ══════════════════════════════════
   HEX HEATMAP — true SVG hexbin
   Perfect offset grid like the reference image
══════════════════════════════════ */
function renderHexMapTo(svgId, journal) {
  const svg = $(svgId);
  if (!svg) return;

  const HEX_R = 18;
  const GAP   = 2;
  const COLS  = 8;
  const totalDays = OV?.settings?.total_days || 30;

  const journalMap = {};
  journal.forEach(j => { journalMap[j.day_number] = j; });
  const allDays = Array.from({ length: totalDays }, (_, i) => {
    const d = i + 1;
    return journalMap[d] || { day_number:d, is_completed:false, is_rolled_over:false, net_pnl:null, target:null, _future:true };
  });

  const rows  = Math.ceil(allDays.length / COLS);
  const HW    = HEX_R * Math.sqrt(3) + GAP;
  const HH    = HEX_R * 2;
  const PAD   = 6;
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

  // ── Defs ──
  let defs = `<defs>
  <filter id="gw_hi" x="-80%" y="-80%" width="260%" height="260%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="5" result="b"/>
    <feFlood flood-color="rgb(0,200,120)" flood-opacity="0.9" result="c"/>
    <feComposite in="c" in2="b" operator="in" result="g"/>
    <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="gw_lo" x="-80%" y="-80%" width="260%" height="260%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="b"/>
    <feFlood flood-color="rgb(0,200,120)" flood-opacity="0.65" result="c"/>
    <feComposite in="c" in2="b" operator="in" result="g"/>
    <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="gl" x="-80%" y="-80%" width="260%" height="260%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="b"/>
    <feFlood flood-color="rgb(255,40,80)" flood-opacity="0.8" result="c"/>
    <feComposite in="c" in2="b" operator="in" result="g"/>
    <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <linearGradient id="glSh" x1="15%" y1="0%" x2="85%" y2="100%">
    <stop offset="0%" stop-color="rgba(255,255,255,0.22)"/>
    <stop offset="40%" stop-color="rgba(255,255,255,0.05)"/>
    <stop offset="100%" stop-color="rgba(255,255,255,0.00)"/>
  </linearGradient>
  </defs>`;

  let body = '';
  allDays.forEach((j, idx) => {
    const col  = idx % COLS;
    const row  = Math.floor(idx / COLS);
    const cx   = col * HW + HEX_R + PAD + (row % 2 === 1 ? HW/2 : 0);
    const cy   = row * (HH*0.75 + GAP/2) + HEX_R + PAD;
    const { face, faceH, edge, text, glow } = getColors(j);
    const fAttr = glow ? ` filter="url(#${glow})"` : '';
    const pnl   = j.net_pnl != null ? Math.round((j.net_pnl/(j.target||40))*100) : null;
    const lbl   = pnl != null ? `${pnl>=0?'+':''}${pnl}%` : '';
    const delay = (idx * 0.045).toFixed(3);
    const done  = j.is_completed ? '1' : '0';
    const ptsOuter = hexPts(cx, cy, HEX_R - 1);
    const ptsInner = hexPts(cx, cy, HEX_R - 2.5);

    body += `<g${fAttr} style="opacity:0;animation:hexAppear 0.4s ease forwards;animation-delay:${delay}s">
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
      <polygon points="${ptsInner}" fill="url(#glSh)" opacity="${j.is_completed?0.55:0.3}" style="pointer-events:none"/>
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

  if (!document.getElementById('hx-style')) {
    const st = document.createElement('style');
    st.id = 'hx-style';
    st.textContent = `
      @keyframes hexAppear {
        from { opacity:0; transform:scale(0.6) translateY(8px); }
        to   { opacity:1; transform:scale(1) translateY(0); }
      }
    `;
    document.head.appendChild(st);
  }

  svg.innerHTML = defs + body;
  svg.setAttribute('viewBox', `0 0 ${svgW.toFixed(1)} ${svgH.toFixed(1)}`);
  svg.removeAttribute('width');
  svg.removeAttribute('height');
  svg.style.width    = '100%';
  svg.style.height   = 'auto';
  svg.style.overflow = 'visible';
  svg.style.webkitTapHighlightColor = 'transparent';

  // ── Attach events to each POLYGON.hx ──────────────────────────────
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
          const e = 1 - Math.pow(1-p, 3); // easeOutCubic — snappy
          sc = from + (target - from) * e;
          // SVG-native scale from center
          poly.setAttribute('transform',
            `translate(${cx},${cy}) scale(${sc.toFixed(4)}) translate(${-cx},${-cy})`
          );
          poly.setAttribute('stroke-width', sc > 1.04 ? '2' : '1');
          poly.setAttribute('fill', sc > 1.04 ? faceH : faceN);
          if (p < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      };

      // ── Pointer events ──
      let isTouch = false;
      let scaleTimeout = null;

      const resetScale = () => {
        clearTimeout(scaleTimeout);
        scaleTimeout = setTimeout(() => animTo(1.0, 220), 320);
      };

      poly.addEventListener('pointerenter', e => {
        if (e.pointerType === 'mouse') animTo(1.18);
      });
      poly.addEventListener('pointerleave', e => {
        if (e.pointerType === 'mouse') animTo(1.0);
      });
      poly.addEventListener('pointerdown', e => {
        e.preventDefault();
        clearTimeout(scaleTimeout);
        isTouch = e.pointerType === 'touch';
        animTo(1.12, 80);
        haptic('light');
      });
      poly.addEventListener('pointerup', e => {
        e.preventDefault();
        // Single tap — scale up to 1.18, hold briefly, then return
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

function renderHexMap(journal) { renderHexMapTo('hex-svg', journal); }

/* Swipe between tabs — ONLY on header, not content */
(() => {
  const tabs   = ['overview','strategy','journal','analiz'];
  const header = $('main-header');
  if (!header) return;

  let sx=0, sy=0, locked=false;

  // Only attach swipe to the HEADER (tabs area)
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
    const next = dx < 0 ? idx+1 : idx-1;
    if (next >= 0 && next < tabs.length) {
      haptic('light');
      document.querySelector(`.tab[data-tab="${tabs[next]}"]`)?.click();
    }
  }, {passive:true});
})();

/* ══════════════════════════════════
   NEW OVERVIEW
══════════════════════════════════ */
// ── Month Navigator State ──
const MONTHS_UZ = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentabr','Oktabr','Noyabr','Dekabr'];

window._hexNav = {
  year: 2025,
  month: 3, // 0-based: 3 = April
  panelOpen: false,
};

function getJournalYearsMonths() {
  // Build map of {year: Set<month>} from JOURNAL dates
  const map = {};
  JOURNAL.forEach(j => {
    if (!j.date) return;
    // date format: "DD.MM" — use OV start_date year
    const parts = j.date.split('.');
    if (parts.length < 2) return;
    const m = parseInt(parts[1]) - 1; // 0-based month
    const y = parseInt(OV?.settings?.start_date?.split('-')[0] || 2025);
    if (!map[y]) map[y] = new Set();
    map[y].add(m);
  });
  // Also add current nav year/month if not present
  return map;
}

function getJournalForMonth(year, month) {
  // Filter JOURNAL by month
  // JOURNAL dates: "DD.MM", year from OV.settings.start_date
  const startYear = parseInt(OV?.settings?.start_date?.split('-')[0] || 2025);
  return JOURNAL.filter(j => {
    if (!j.date) return false;
    const parts = j.date.split('.');
    const m = parseInt(parts[1]) - 1;
    // Simple: same month index
    return m === month;
  });
}

function updateMonthLabel() {
  const { year, month } = window._hexNav;
  const el = $('mnav-label');
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
  // Close panel if open
  if (window._hexNav.panelOpen) toggleMonthPanel();
}

function toggleMonthPanel() {
  haptic('light');
  window._hexNav.panelOpen = !window._hexNav.panelOpen;
  const panel  = $('month-panel');
  const caret  = $('mnav-caret');
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
  // Always include current nav year
  if (!years.includes(year)) years.push(year);

  // Years row
  const yWrap = $('mpanel-years');
  if (yWrap) {
    yWrap.innerHTML = years.map(y =>
      `<button class="mpy-btn${y===year?' sel':''}" onclick="selectYear(${y})">${y}</button>`
    ).join('');
  }

  // Months grid
  const mWrap = $('mpanel-months');
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
  buildMonthPanel(); // refresh panel
  refreshHexOv();
}

function selectMonth(m) {
  haptic('light');
  window._hexNav.month = m;
  updateMonthLabel();
  refreshHexOv();
  toggleMonthPanel(); // close panel
}

function refreshHexOv() {
  const { month } = window._hexNav;
  const filtered = getJournalForMonth(window._hexNav.year, month);
  renderHexMapTo('hex-svg-ov', filtered);
}

// Close month panel on outside tap
document.addEventListener('click', e => {
  if (!window._hexNav?.panelOpen) return;
  const panel = $('month-panel');
  const nav   = document.querySelector('.month-nav');
  if (panel && nav && !panel.contains(e.target) && !nav.contains(e.target)) {
    toggleMonthPanel();
  }
}, { capture: false });

async function loadOverview() {
  const d = await apiFetch('/api/overview') || OV;
  const { current_balance:cur, summary:sum, mode } = d;

  // Rejimni UI ga qo'llash
  applyMode(mode || 'strategy');

  // Balance
  const abEl = $('ov-balance');
  if (abEl) countUp(abEl, cur, 900);

  // Journal rejimida bugungi PnL — real APIdan
  const todayPnl = sum?.today_pnl ?? ((() => {
    const lastDay = [...JOURNAL].reverse().find(j => j.is_completed);
    return lastDay?.net_pnl || 0;
  })());
  const todayPct = cur > 0 ? ((todayPnl / cur) * 100) : 0;

  const tpEl = $('ov-today-pnl');
  if (tpEl) {
    tpEl.textContent = fm(todayPnl);
    tpEl.className = `bd-val ${todayPnl >= 0 ? 'pos' : 'neg'}`;
  }
  const pctEl = $('ov-today-pct');
  if (pctEl) {
    pctEl.textContent = `${todayPct >= 0 ? '+' : ''}${todayPct.toFixed(2)}%`;
    pctEl.style.color = todayPct >= 0 ? 'var(--green-hi)' : 'var(--red-hi)';
  }

  // KPI
  const comp = JOURNAL.filter(j => j.is_completed);
  const wins = comp.filter(j => !j.is_rolled_over).length;
  const wr   = comp.length > 0 ? Math.round((wins/comp.length)*100) : 0;
  const totalPnl = sum?.total_pnl ?? comp.reduce((s,j) => s+(j.net_pnl||0), 0);

  txt('ov-total-trades', sum?.total_trades || SUM.total_trades || comp.length);
  // Journal rejimida win rate ko'rsatilmaydi (maqsad yo'q)
  const wrEl = $('ov-winrate');
  if (wrEl) {
    if (window._mode === 'journal') {
      wrEl.textContent = '—';
      wrEl.className = 'kpi-val';
    } else {
      wrEl.textContent = `${wr}%`;
      wrEl.className = `kpi-val ${wr >= 50 ? 'up' : 'dn'}`;
    }
  }
  const tpnlEl = $('ov-total-pnl');
  if (tpnlEl) {
    tpnlEl.textContent = `${totalPnl >= 0 ? '+' : ''}${Number(totalPnl).toFixed(0)}$`;
    tpnlEl.className = `kpi-val ${totalPnl >= 0 ? 'up' : 'dn'}`;
  }

  // Init month nav
  const startDate = d?.settings?.start_date || OV?.settings?.start_date || '2025-04-01';
  const parts = startDate.split('-');
  window._hexNav.year  = parseInt(parts[0]);
  window._hexNav.month = parseInt(parts[1]) - 1;
  updateMonthLabel();
  refreshHexOv();

  // Streak — faqat strategy rejimida
  if (window._mode === 'strategy') {
    let streak = 0;
    for (let i = JOURNAL.length-1; i >= 0; i--) {
      if (JOURNAL[i].is_completed && !JOURNAL[i].is_rolled_over) streak++; else break;
    }
    const sw = $('ov-streak-wrap');
    if (sw && streak > 0) {
      sw.innerHTML = `<div class="streak">
        <span class="streak-icon">🔥</span>
        <span class="streak-txt">Joriy ketma-ket gʺalaba</span>
        <span class="streak-num">${streak} kun</span>
      </div>`;
    }
  }
}

/* ══════════════════════════════════
   STRATEGY (old overview)
══════════════════════════════════ */
async function loadStrategy() {
  let d = await apiFetch('/api/overview'); if (!d) d = OV;
  const { settings:s, current_balance:cur, planned_balance:plan, summary:sum } = d;

  /* Balance */
  const abEl = $('actual-balance');
  if (abEl) countUp(abEl, cur, 1100);
  txt('planned-balance', fm(plan, false));

  const diff = (cur||0) - (plan||0);
  const de = $('bal-diff');
  if (de) { de.textContent = fm(diff); de.className = `bd-val ${diff >= 0 ? 'pos' : 'neg'}`; }

  /* Progress bars */
  const totalDays = s?.total_days||0, doneDays = sum?.total_days||0;
  const dpct = totalDays > 0 ? (doneDays/totalDays)*100 : 0;
  setTimeout(() => { const b = $('prog-days-bar'); if(b) b.style.width=`${Math.min(dpct,100)}%`; }, 100);
  txt('prog-days-txt', `${doneDays} / ${totalDays}`);

  const startBal = s?.starting_balance||0;
  const balPct = plan > startBal ? ((cur-startBal)/(plan-startBal))*100 : 0;
  setTimeout(() => { const b = $('prog-bal-bar'); if(b) b.style.width=`${Math.min(Math.max(balPct,0),100)}%`; }, 100);
  txt('prog-bal-txt', `${Math.max(0, Math.round(balPct))}%`);

  /* Stats */
  const pnl = sum?.total_pnl||0, wins = sum?.win_days||0, losses = sum?.loss_days||0;
  const wr = doneDays > 0 ? Math.round((wins/doneDays)*100) : 0;
  const pe = $('total-pnl');
  if (pe) { pe.textContent = fm(pnl); pe.className = `sbv ${pnl >= 0 ? 'green' : 'red'}`; }
  txt('win-rate',  `${wr}%`);
  txt('win-days',  String(wins));
  txt('loss-days', String(losses));

  /* Settings */
  txt('s-startbal', s?.starting_balance ? `${Number(s.starting_balance).toLocaleString()}$` : '—');
  txt('s-rate',     s?.daily_profit_rate ? `${(s.daily_profit_rate*100).toFixed(0)}%` : '—');
  txt('s-days',     s?.total_days ? `${s.total_days} kun` : '—');
  txt('s-date',     s?.start_date || '—');
  txt('s-broker',   s?.broker_name || '—');

  /* KPI */
  const comp = JOURNAL.filter(j => j.is_completed && j.net_pnl != null);
  if (comp.length) {
    const pnls = comp.map(j => j.net_pnl);
    const avg  = pnls.reduce((a,b) => a+b, 0) / pnls.length;
    const best = Math.max(...pnls), worst = Math.min(...pnls);
    const fmt  = v => (v>=0?'+':'')+v.toFixed(0)+'$';
    txt('kpi-avg', fmt(avg)); txt('kpi-best', fmt(best)); txt('kpi-worst', fmt(worst));
  }

  /* Flow */
  txt('flow-total',  SUM.total_trades);
  txt('flow-wins',   SUM.wins);
  txt('flow-losses', SUM.losses);
  txt('flow-bwin',   fa(SUM.biggest_win));
  txt('flow-bloss',  fa(SUM.biggest_loss));
  txt('flow-hwins',  (SUM.avg_hold_win||0)+'d');
  txt('flow-hloss',  (SUM.avg_hold_loss||0)+'d');

  /* Hex Heatmap — SVG true hexbin */
  renderHexMapTo('hex-svg', JOURNAL);

  /* Streak */
  let streak = 0;
  for (let i = JOURNAL.length-1; i >= 0; i--) {
    if (JOURNAL[i].is_completed && !JOURNAL[i].is_rolled_over) streak++;
    else break;
  }
  const sw = $('streak-wrap');
  if (sw && streak > 0) {
    sw.innerHTML = `<div class="streak">
      <span class="streak-icon">🔥</span>
      <span class="streak-txt">Joriy ketma-ket gʺalaba</span>
      <span class="streak-num">${streak} kun</span>
    </div>`;
  }
}

/* ══════════════════════════════════
   JOURNAL
══════════════════════════════════ */
async function loadJournal() {
  const jb = $('journal-tbody'); if (!jb) return;
  jb.innerHTML = '<tr><td colspan="5"><div class="loading-box"><div class="spinner"></div></div></td></tr>';

  let d = await apiFetch('/api/journal'); if (!d) d = { journal: JOURNAL };
  if (!d?.journal?.length) {
    jb.innerHTML = '<tr><td colspan="5"><div class="empty-box">Ma\'lumot topilmadi</div></td></tr>';
    return;
  }

  // Store journal data globally for filter/sort
  window._journalData = d.journal;
  window._journalSort = 'desc'; // desc = Yangi→Eski
  window._journalFilter = 'all';
  renderJournalTable();

  /* Result table */
  const rtb = $('result-tbody');
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

  txt('rs-total', SUM.total_trades); txt('rs-wins', SUM.wins);
  txt('rs-be', SUM.break_even);      txt('rs-losses', SUM.losses);

  /* Custom SVG Donut — exact React PieChart.jsx replica */
  renderCustomPie();
}

function renderCustomPie() {
  const SEGMENTS = [
    { name:'Wins',  key:'wins',       color:'#06ffa5', bg:'rgba(6,255,165,0.08)',  border:'rgba(6,255,165,0.3)',  glow:'rgba(6,255,165,0.5)'  },
    { name:'BE',    key:'break_even', color:'#ffb020', bg:'rgba(255,176,32,0.08)', border:'rgba(255,176,32,0.3)', glow:'rgba(255,176,32,0.5)' },
    { name:'Loss',  key:'losses',     color:'#ff3060', bg:'rgba(255,48,96,0.08)',  border:'rgba(255,48,96,0.3)',  glow:'rgba(255,48,96,0.5)'  },
  ];

  const GAP          = 4;
  const CX           = 60;
  const CY           = 60;
  const INNER        = 30;
  const OUTER        = 52;
  const OUTER_ACTIVE = 58;

  const values = SEGMENTS.map(s => SUM[s.key] || 0);
  const total  = values.reduce((a,b) => a+b, 0);
  const pct    = v => total > 0 ? ((v/total)*100).toFixed(1) : '0';

  // State
  let activeIdx = null;

  function polarToXY(cx, cy, r, angleDeg) {
    const rad = (angleDeg - 90) * Math.PI / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }

  function describeArc(cx, cy, r, startDeg, endDeg) {
    const s = polarToXY(cx, cy, r, startDeg);
    const e = polarToXY(cx, cy, r, endDeg);
    const large = endDeg - startDeg > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
  }

  function describeSlice(cx, cy, innerR, outerR, startDeg, endDeg) {
    const s1 = polarToXY(cx, cy, outerR, startDeg);
    const e1 = polarToXY(cx, cy, outerR, endDeg);
    const s2 = polarToXY(cx, cy, innerR, endDeg);
    const e2 = polarToXY(cx, cy, innerR, startDeg);
    const large = endDeg - startDeg > 180 ? 1 : 0;
    return [
      `M ${s1.x} ${s1.y}`,
      `A ${outerR} ${outerR} 0 ${large} 1 ${e1.x} ${e1.y}`,
      `L ${s2.x} ${s2.y}`,
      `A ${innerR} ${innerR} 0 ${large} 0 ${e2.x} ${e2.y}`,
      'Z'
    ].join(' ');
  }

  // Build slices
  const slices = [];
  let angle = 0;
  values.forEach((val, i) => {
    const sweep = total > 0 ? (val/total) * (360 - SEGMENTS.length*GAP) : 0;
    slices.push({ startDeg: angle + GAP/2, endDeg: angle + GAP/2 + sweep, idx: i });
    angle += sweep + GAP;
  });

  // Animated outer radius per segment
  const animRadii  = slices.map(() => OUTER); // current animated radius
  const animOpacity= slices.map(() => 1.0);   // current animated opacity
  let   animRaf    = null;

  function animatePie(targetIdx) {
    if (animRaf) cancelAnimationFrame(animRaf);
    const targetRadii   = slices.map((_, i) => targetIdx === i ? OUTER_ACTIVE : OUTER);
    const targetOpacity = slices.map((_, i) => targetIdx === null || targetIdx === i ? 1.0 : 0.28);
    const dur = 380; // ms — smooth float-in
    const t0  = performance.now();

    const tick = now => {
      const p    = Math.min((now - t0) / dur, 1);
      const ease = 1 - Math.pow(1 - p, 3); // easeOutCubic
      let   done = true;
      slices.forEach((_, i) => {
        animRadii[i]   = animRadii[i]   + (targetRadii[i]   - animRadii[i])   * ease;
        animOpacity[i] = animOpacity[i] + (targetOpacity[i] - animOpacity[i]) * ease;
        if (Math.abs(animRadii[i] - targetRadii[i]) > 0.05) done = false;
      });
      rebuildPaths();
      if (!done || p < 1) animRaf = requestAnimationFrame(tick);
    };
    animRaf = requestAnimationFrame(tick);
  }

  function rebuildPaths() {
    // Only update paths + center text, not defs/track
    const pathGroup = pieSvg.querySelector('.pie-paths');
    const centerGroup= pieSvg.querySelector('.pie-center');
    if (!pathGroup || !centerGroup) return;

    pathGroup.innerHTML = slices.map(({ startDeg, endDeg, idx }) => {
      const r   = animRadii[idx];
      const opc = animOpacity[idx];
      const d   = describeSlice(CX, CY, INNER, r, startDeg, endDeg);
      const seg = SEGMENTS[idx];
      const isActive = activeIdx === idx;
      return `<path
        d="${d}"
        fill="${seg.color}"
        opacity="${opc.toFixed(3)}"
        filter="${isActive ? `url(#glow-pie-${idx})` : ''}"
        style="cursor:pointer"
        data-idx="${idx}"
        class="pie-slice"
      />`;
    }).join('');

    // Re-attach events
    pathGroup.querySelectorAll('.pie-slice').forEach(path => {
      const i = parseInt(path.dataset.idx);
      path.addEventListener('pointerdown', e => { e.preventDefault(); toggleSlice(i); }, { passive:false });
    });

    // Center text
    if (activeIdx !== null) {
      const seg = SEGMENTS[activeIdx];
      centerGroup.innerHTML = `
        <text x="${CX}" y="${CY-5}" text-anchor="middle" dominant-baseline="middle"
          font-size="15" font-weight="700" font-family="Space Mono,monospace"
          fill="${seg.color}">${values[activeIdx]}</text>
        <text x="${CX}" y="${CY+11}" text-anchor="middle" dominant-baseline="middle"
          font-size="8" font-weight="400" font-family="Space Mono,monospace"
          fill="${seg.color}" opacity="0.7">${pct(values[activeIdx])}%</text>`;
    } else {
      centerGroup.innerHTML = `
        <text x="${CX}" y="${CY-5}" text-anchor="middle" dominant-baseline="middle"
          font-size="16" font-weight="700" font-family="Space Mono,monospace"
          fill="white">${total}</text>
        <text x="${CX}" y="${CY+11}" text-anchor="middle" dominant-baseline="middle"
          font-size="7" font-weight="700" font-family="Space Mono,monospace"
          fill="rgba(255,255,255,0.3)" letter-spacing="2">JAMI</text>`;
    }
  }

  function buildSVG() {
    const defs = SEGMENTS.map((seg, i) => `
      <filter id="glow-pie-${i}" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
        <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>`).join('');

    const trackRing = `<circle cx="${CX}" cy="${CY}" r="${(INNER+OUTER)/2}"
      fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="${OUTER-INNER}"/>`;

    return `<defs>${defs}</defs>${trackRing}
      <g class="pie-paths"></g>
      <g class="pie-center"></g>`;
  }

  // ── Render pie + legend ──
  const container = $('pie-chart')?.parentElement;
  if (!container) return;

  // Replace canvas with svg
  const svgWrap = document.createElement('div');
  svgWrap.style.cssText = 'position:relative;flex-shrink:0;width:120px;height:120px';
  svgWrap.innerHTML = `<svg width="120" height="120" viewBox="0 0 120 120"
    style="display:block;overflow:visible;background:transparent"></svg>`;
  const pieSvg = svgWrap.querySelector('svg');

  const legendWrap = $('pie-legend');

  function toggleSlice(i) {
    haptic('light');
    activeIdx = activeIdx === i ? null : i;
    animatePie(activeIdx);
    updateLegend();
  }

  function updateLegend() {
    if (!legendWrap) return;
    legendWrap.innerHTML = SEGMENTS.map((seg, i) => {
      const isActive = activeIdx === i;
      const val      = values[i];
      return `<div class="pie-leg-row" data-idx="${i}"
        style="transition:background .3s,border .3s,box-shadow .3s;cursor:pointer;
          display:flex;align-items:center;gap:8px;font-size:11px;
          padding:3px 6px;border-radius:8px;
          background:${isActive ? seg.bg : 'transparent'};
          border:1px solid ${isActive ? seg.border : 'transparent'};
          box-shadow:${isActive ? `0 0 14px ${seg.glow}` : 'none'}">
        <span class="pie-dot" style="background:${seg.color};width:7px;height:7px;
          border-radius:2px;flex-shrink:0;transition:box-shadow .3s;
          box-shadow:${isActive ? `0 0 6px ${seg.color}` : 'none'}"></span>
        <span style="flex:1;color:${isActive?'white':'var(--ink2)'};transition:color .3s">${seg.name}</span>
        <span style="font-family:var(--mono);font-size:12px;font-weight:700;
          color:${isActive?seg.color:'var(--ink0)'};transition:color .3s">${val}
          <em style="font-style:normal;font-size:9px;margin-left:3px;
            color:${isActive?seg.color:'var(--ink2)'};opacity:${isActive?1:0.7}">${pct(val)}%</em>
        </span>
      </div>`;
    }).join('');

    legendWrap.querySelectorAll('.pie-leg-row').forEach(row => {
      const i = parseInt(row.dataset.idx);
      row.addEventListener('pointerdown', e => { e.preventDefault(); toggleSlice(i); }, {passive:false});
    });
  }

  function renderAll() {
    pieSvg.innerHTML = buildSVG();
    rebuildPaths();
    updateLegend();
  }

  // Replace old canvas
  const oldCanvas = $('pie-chart');
  if (oldCanvas) oldCanvas.replaceWith(svgWrap);

  renderAll();
}

/* ══════════════════════════════════
   JOURNAL FILTER / SORT
══════════════════════════════════ */
function renderJournalTable() {
  const jb = $('journal-tbody'); if (!jb) return;
  let rows = window._journalData || [];
  const filter = window._journalFilter || 'all';
  const sort   = window._journalSort   || 'desc';
  const isJournal = window._mode === 'journal';

  // Maqsad ustunini yashirish/ko'rsatish
  const jtbl = document.querySelector('.jtbl');
  if (jtbl) {
    const headers = jtbl.querySelectorAll('th');
    // 3-chi ustun = "Maqsad"
    if (headers[2]) headers[2].style.display = isJournal ? 'none' : '';
  }

  // Filter
  if (filter === 'win')  rows = rows.filter(j => j.is_completed && !j.is_rolled_over);
  if (filter === 'loss') rows = rows.filter(j => j.is_completed &&  j.is_rolled_over);
  if (filter === 'pend') rows = rows.filter(j => !j.is_completed);

  // Sort
  rows = [...rows].sort((a,b) => sort === 'desc' ? b.day_number - a.day_number : a.day_number - b.day_number);

  if (!rows.length) {
    jb.innerHTML = `<tr><td colspan="${isJournal ? 4 : 5}"><div class="empty-box">Ma'lumot topilmadi</div></td></tr>`;
    return;
  }

  jb.innerHTML = rows.map(j => {
    const pc    = j.net_pnl >= 0 ? 'pp' : 'pn';
    const rc    = !j.is_completed ? '' : j.is_rolled_over ? 'jl' : 'jw';
    const badge = !j.is_completed
      ? '<span class="badge bp">Davom</span>'
      : j.is_rolled_over
        ? '<span class="badge bl">Rollover</span>'
        : '<span class="badge bw">✓ Bajarildi</span>';
    // Journal rejimida Maqsad ustuni yashiriladi
    const targetCell = isJournal ? '' : `<td class="mono" style="font-size:11px;display:${isJournal?'none':''}">${fm(j.target,false)}</td>`;
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
  // Update active button styles
  document.querySelectorAll('.jfbtn').forEach(b => {
    b.classList.remove('active','win-f','loss-f','pend-f');
  });
  btn.classList.add('active');
  if (filter === 'win')  btn.classList.add('win-f');
  if (filter === 'loss') btn.classList.add('loss-f');
  if (filter === 'pend') btn.classList.add('pend-f');
  renderJournalTable();
}

function toggleJSort() {
  haptic();
  window._journalSort = window._journalSort === 'desc' ? 'asc' : 'desc';
  const lbl = $('jsort-lbl'); const arr = $('jsort-arr');
  if (lbl) lbl.textContent = window._journalSort === 'desc' ? 'Yangi → Eski' : 'Eski → Yangi';
  if (arr) arr.classList.toggle('up', window._journalSort === 'asc');
  renderJournalTable();
}

/* ══════════════════════════════════
   DAY DETAIL
══════════════════════════════════ */
async function openDay(day) {
  haptic('medium');
  $('main-header').style.display = 'none';  $('detail-header').style.display = '';
  $('main-view').style.display   = 'none';  $('detail-view').style.display   = '';
  $('detail-badge').textContent  = `${day}-KUN`;
  $('day-card').innerHTML    = '<div class="loading-box"><div class="spinner"></div></div>';
  $('trades-list').innerHTML = '<div class="loading-box"><div class="spinner"></div></div>';

  const data = await apiFetch('/api/day_detail', `&day_number=${day}`);
  if (!data) {
    $('day-card').innerHTML    = '<div class="empty-box">Ma\'lumot topilmadi</div>';
    $('trades-list').innerHTML = ''; return;
  }

  const { journal:j, trades } = data;
  const isWin  = j.is_completed && !j.is_rolled_over;
  const isLoss = j.is_completed &&  j.is_rolled_over;
  const rc = isWin ? 'win' : isLoss ? 'loss' : 'neutral';
  const rt = isWin ? '✅ Maqsad bajarildi' : isLoss ? '❌ Rollover' : '⏳ Davom etmoqda';

  $('day-card').innerHTML = `
    <div class="card-title"><span class="ctdot"></span>${j.day_number}-kun — ${j.date}</div>
    <div class="day-grid">
      <div class="stat-box"><div class="sbl">Boshlang'ich</div><div class="sbv" style="font-size:16px">${fm(j.start_balance,false)}</div></div>
      <div class="stat-box"><div class="sbl">Yakuniy</div><div class="sbv ${j.net_pnl>=0?'green':'red'}" style="font-size:16px">${fm(j.end_balance,false)}</div></div>
      <div class="stat-box"><div class="sbl">Maqsad</div><div class="sbv blue" style="font-size:16px">${fm(j.total_target,false)}</div></div>
      <div class="stat-box"><div class="sbl">Net PnL</div><div class="sbv ${j.net_pnl>=0?'green':'red'}" style="font-size:16px">${fm(j.net_pnl)}</div></div>
    </div>
    <div class="day-result ${rc}">
      <span style="font-weight:600">${rt}</span>
      <span class="mono" style="font-size:11px">${trades.length} savdo</span>
    </div>`;

  if (!trades.length) {
    $('trades-list').innerHTML = '<div class="empty-box">Savdolar yo\'q</div>'; return;
  }
  window._trades = trades;
  $('trades-list').innerHTML = trades.map((t,i) => {
    const sc = {tp:'tp',sl:'sl',be:'be'}[t.exit_type] || 'manual';
    const pc = t.net_pnl >= 0 ? 'pp' : 'pn';
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
  $('modal-body').innerHTML = `
    <div class="mhandle"></div>
    <div class="mtitle">${t.symbol||'—'} ${t.direction?`<span class="dir ${t.direction.toLowerCase()}">${t.direction.toUpperCase()}</span>`:''}</div>
    <div class="mrow"><span class="ml">Kirish narxi</span><span class="mv">${fp(t.open_price)}</span></div>
    <div class="mrow"><span class="ml">Chiqish narxi</span><span class="mv">${fp(t.close_price)}</span></div>
    <div class="mrow"><span class="ml">Hajm (lot)</span><span class="mv">${t.quantity}</span></div>
    <div class="msep"></div>
    <div class="mrow"><span class="ml">Gross PnL</span><span class="mv ${t.pnl>=0?'pp':'pn'}">${fm(t.pnl)}</span></div>
    ${t.swap  ? `<div class="mrow"><span class="ml">Swap</span><span class="mv ${t.swap>=0?'pp':'pn'}">${fm(t.swap)}</span></div>` : ''}
    ${t.commission ? `<div class="mrow"><span class="ml">Komissiya</span><span class="mv pn">${fm(t.commission)}</span></div>` : ''}
    <div class="mrow"><span class="ml">Net PnL</span><span class="mv ${t.net_pnl>=0?'pp':'pn'}" style="font-size:15px">${fm(t.net_pnl)}</span></div>
    ${t.sl_price||t.tp_price ? '<div class="msep"></div>' : ''}
    ${t.sl_price  ? `<div class="mrow"><span class="ml">Stop Loss</span><span class="mv pn">${fp(t.sl_price)}</span></div>` : ''}
    ${t.tp_price  ? `<div class="mrow"><span class="ml">Take Profit</span><span class="mv pp">${fp(t.tp_price)}</span></div>` : ''}
    ${t.open_time ? `<div class="mrow"><span class="ml">Ochilish</span><span class="mv">${t.open_time}</span></div>` : ''}
    ${t.close_time? `<div class="mrow"><span class="ml">Yopilish</span><span class="mv">${t.close_time}</span></div>` : ''}
    ${t.order_id  ? `<div class="mrow"><span class="ml">Order ID</span><span class="mv" style="font-size:11px">#${t.order_id}</span></div>` : ''}`;
  $('trade-modal').style.display = '';
}

$('modal-bg')?.addEventListener('click', () => { haptic(); $('trade-modal').style.display = 'none'; });
$('back-btn')?.addEventListener('click', () => {
  haptic();
  $('main-header').style.display   = ''; $('detail-header').style.display = 'none';
  $('main-view').style.display     = ''; $('detail-view').style.display   = 'none';
  window._trades = [];
});

/* ══════════════════════════════════
   ANALIZ
══════════════════════════════════ */
let pnlChart=null, balChart=null;

async function loadAnaliz() {
  $('chart-pnl-wrap').innerHTML     = '<div class="loading-box"><div class="spinner"></div></div>';
  $('chart-balance-wrap').innerHTML = '<div class="loading-box"><div class="spinner"></div></div>';

  let data = await apiFetch('/api/progression'); if (!data) data = { progression: PROGRESSION };

  if (!data?.progression?.length) {
    $('chart-balance-wrap').innerHTML = '<div class="empty-box">Ma\'lumot yetarli emas</div>';
    $('chart-pnl-wrap').innerHTML = ''; buildRadar(null); return;
  }

  const prog = data.progression;
  const grid = 'rgba(255,255,255,0.04)', hint = '#546278';
  const BASE = {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode:'index', intersect:false },
    plugins: {
      legend: { labels:{ color:'#a0aec4', font:{size:10}, boxWidth:10, padding:14 } },
      tooltip: {
        backgroundColor:'#07070f', borderColor:'rgba(61,127,255,0.2)', borderWidth:1,
        titleColor:'#f0f4ff', bodyColor:'#8fa4c8',
        callbacks: { label: ctx => { if(ctx.raw==null) return null; const v=Number(ctx.raw); return ` ${ctx.dataset.label}: ${v>=0?'+':''}$${v.toLocaleString('en-US',{minimumFractionDigits:2})}`; } }
      },
    },
    scales: {
      x: { ticks:{color:hint,font:{size:9,family:"'Space Mono'"},maxRotation:45,maxTicksLimit:10}, grid:{color:grid,drawBorder:false} },
      y: { ticks:{color:hint,font:{size:9,family:"'Space Mono'"},callback:v=>`$${Number(v).toLocaleString()}`}, grid:{color:grid,drawBorder:false} },
    },
  };

  /* PnL Bar */
  const comp = prog.filter(d => d.is_completed && d.actual_pnl != null);
  const pnlD = comp.map(d => d.actual_pnl);
  $('chart-pnl-wrap').innerHTML = '<canvas id="pnl-canvas" height="200"></canvas>';
  const pctx = $('pnl-canvas')?.getContext('2d');
  if (pctx) {
    if (pnlChart) pnlChart.destroy();
    pnlChart = new Chart(pctx, {
      type: 'bar',
      data: { labels:comp.map(d=>d.date.slice(5)), datasets:[{ label:'Kunlik PnL', data:pnlD, backgroundColor:pnlD.map(v=>v>=0?'rgba(0,232,122,0.72)':'rgba(255,45,85,0.68)'), borderColor:pnlD.map(v=>v>=0?'#39ffac':'#ff6080'), borderWidth:1, borderRadius:5 }] },
      options: { ...BASE, plugins:{...BASE.plugins, legend:{display:false}} }
    });
  }

  /* Balance Line */
  $('chart-balance-wrap').innerHTML = '<canvas id="bal-canvas" height="220"></canvas>';
  const bctx = $('bal-canvas')?.getContext('2d');
  if (bctx) {
    if (balChart) balChart.destroy();
    balChart = new Chart(bctx, {
      type: 'line',
      data: { labels:prog.map(d=>d.date.slice(5)), datasets:[
        { label:'Rejalangan', data:prog.map(d=>d.final_balance), borderColor:'#00b4ff', borderWidth:1.5, borderDash:[5,5], pointRadius:0, fill:false, tension:.3, spanGaps:true },
        { label:'Haqiqiy', data:prog.map(d=>(!d.is_completed||d.actual_pnl==null)?null:d.start_balance+d.actual_pnl), borderColor:'#00e87a', backgroundColor:'rgba(0,232,122,0.1)', borderWidth:2, pointRadius:3, pointBackgroundColor:'#39ffac', fill:true, tension:.3, spanGaps:false },
      ] },
      options: { ...BASE, maintainAspectRatio:false }
    });
  }

  /* Rings */
  const done = JOURNAL.filter(j => j.is_completed);
  const winsCount = done.filter(j => !j.is_rolled_over).length;
  const wr = done.length > 0 ? (winsCount/done.length)*100 : 0;
  const s  = OV.settings.starting_balance, c = OV.current_balance, p = OV.planned_balance;
  const progPct = p > s ? ((c-s)/(p-s))*100 : 0;
  const pfPct   = Math.min((2.38/4)*100, 100);

  animateRing('ring-wr',   wr);
  animateRing('ring-prog', Math.max(0, progPct));
  animateRing('ring-pf',   pfPct);
  txt('ring-wr-val',   wr.toFixed(0)+'%');
  txt('ring-prog-val', Math.max(0,Math.round(progPct))+'%');
  txt('ring-pf-val',   '2.38');

  buildRadar(data.evaluation ?? null);
}

/* ══════════════════════════════════
   CUSTOM SVG RADAR — full rewrite
   No Chart.js — pure SVG geometry
══════════════════════════════════ */
function buildRadar(ev) {
  const svgEl      = $('radar-svg');
  const metricsWrap= $('radar-metrics');
  const tooltip    = $('radar-tooltip');
  const scoreNum   = $('radar-score-num');
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

  /* ── Geometry ── */
  const N   = METRICS.length; // 5
  const CX  = 150, CY = 150;
  const R   = 108;  // max radius
  const LEVELS = [25, 50, 75, 100];

  const angle = (i) => (2 * Math.PI * i / N) - Math.PI / 2;

  const polarPt = (r, i) => ({
    x: CX + r * Math.cos(angle(i)),
    y: CY + r * Math.sin(angle(i)),
  });

  const polyPts = (r, offset=0) =>
    Array.from({length:N}, (_,i) => {
      const p = polarPt(r, i+offset);
      return `${p.x.toFixed(2)},${p.y.toFixed(2)}`;
    }).join(' ');

  // Data polygon — normalized to radius
  const dataRadii = vals.map(v => (v / 100) * R);
  const dataPts   = METRICS.map((_,i) => {
    const p = polarPt(dataRadii[i], i);
    return `${p.x.toFixed(2)},${p.y.toFixed(2)}`;
  }).join(' ');

  /* ── Build SVG ── */
  let svgContent = `<defs>
    <!-- Gradient fill for data polygon -->
    <linearGradient id="rg-fill" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="rgba(0,212,255,0.32)"/>
      <stop offset="50%"  stop-color="rgba(167,139,250,0.22)"/>
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
    <filter id="rg-outer-glow" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="10" result="blur"/>
      <feFlood flood-color="rgba(0,180,255,0.25)" result="color"/>
      <feComposite in="color" in2="blur" operator="in" result="glow"/>
      <feMerge><feMergeNode in="glow"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <radialGradient id="rg-center" cx="50%" cy="50%" r="50%">
      <stop offset="0%"   stop-color="rgba(168,85,247,0.15)"/>
      <stop offset="60%"  stop-color="rgba(0,180,255,0.04)"/>
      <stop offset="100%" stop-color="transparent"/>
    </radialGradient>
    <!-- Per-metric vertex glows -->
    ${METRICS.map((m,i) => `
    <radialGradient id="vg-${i}" cx="50%" cy="50%" r="50%">
      <stop offset="0%"   stop-color="${m.color}" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="${m.color}" stop-opacity="0"/>
    </radialGradient>`).join('')}
  </defs>

  <!-- Center glow -->
  <circle cx="${CX}" cy="${CY}" r="85" fill="url(#rg-center)"/>

  <!-- Grid levels -->
  ${LEVELS.map((lvl, li) => {
    const r = (lvl/100)*R;
    const pts = polyPts(r);
    const alpha = [0.06, 0.09, 0.13, 0.22][li];
    const isOuter = li === LEVELS.length-1;
    return `<polygon points="${pts}" fill="none"
      stroke="rgba(255,255,255,${alpha})"
      stroke-width="${isOuter ? 1.5 : 0.75}"
      ${isOuter ? 'filter="url(#rg-glow)"' : ''}
    />`;
  }).join('')}

  <!-- Axis lines (spokes) -->
  ${METRICS.map((_,i) => {
    const p  = polarPt(R, i);
    const p0 = polarPt(14, i);
    return `<line x1="${p0.x.toFixed(2)}" y1="${p0.y.toFixed(2)}" x2="${p.x.toFixed(2)}" y2="${p.y.toFixed(2)}"
      stroke="rgba(168,85,247,0.18)" stroke-width="0.8"/>`;
  }).join('')}

  <!-- Grid level value labels -->
  ${LEVELS.slice(0,-1).map(lvl => {
    const r = (lvl/100)*R;
    const p = polarPt(r, 2.25); // place near axis 2
    return `<text x="${p.x.toFixed(1)}" y="${(p.y+3).toFixed(1)}" text-anchor="middle"
      font-family="Space Mono" font-size="6.5" fill="rgba(255,255,255,0.2)">${lvl}</text>`;
  }).join('')}

  <!-- DATA polygon filled area (animated) -->
  <polygon id="rg-data-fill" points="${dataPts}"
    fill="url(#rg-fill)"
    opacity="0"
    style="animation:radarFill 0.7s ease forwards 0.4s"
  />

  <!-- DATA polygon border (animated) -->
  <polygon id="rg-data-border" points="${dataPts}"
    fill="none"
    stroke="rgba(92,211,255,0.75)"
    stroke-width="2"
    stroke-linejoin="round"
    filter="url(#rg-glow)"
    opacity="0"
    style="animation:radarFill 0.5s ease forwards 0.5s"
  />

  <!-- Vertex glow halos -->
  ${METRICS.map((m,i) => {
    const p = polarPt(dataRadii[i], i);
    return `<circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="12"
      fill="url(#vg-${i})" opacity="0.45" class="rg-halo" data-idx="${i}"/>`;
  }).join('')}

  <!-- Vertex dots (interactive) -->
  ${METRICS.map((m,i) => {
    const p = polarPt(dataRadii[i], i);
    const delay = 0.55 + i * 0.08;
    return `<circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="0"
      fill="${m.color}" stroke="rgba(6,4,15,0.9)" stroke-width="2"
      class="rg-vertex" data-idx="${i}"
      style="animation:vertexPop 0.45s cubic-bezier(.4,0,.2,1) forwards ${delay}s;cursor:pointer;filter:url(#rg-glow-hi)"
    />`;
  }).join('')}

  <!-- Hit areas (larger tap targets) -->
  ${METRICS.map((m,i) => {
    const p = polarPt(dataRadii[i], i);
    return `<circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="20"
      fill="transparent" class="rg-hit" data-idx="${i}" style="cursor:pointer"/>`;
  }).join('')}

  <!-- Axis labels -->
  ${METRICS.map((m,i) => {
    const LABEL_R = R + 22;
    const p = polarPt(LABEL_R, i);
    const a = angle(i);
    // Adjust anchor based on angle
    const anchor = Math.abs(Math.cos(a)) < 0.15 ? 'middle' : Math.cos(a) > 0 ? 'start' : 'end';
    const dy = Math.sin(a) > 0.6 ? 10 : Math.sin(a) < -0.6 ? -4 : 4;
    const lines = m.label.split(' ');
    return `<g class="rg-label" data-idx="${i}">
      ${lines.map((line, li) => `
        <text x="${p.x.toFixed(1)}" y="${(p.y + dy + li*10).toFixed(1)}"
          text-anchor="${anchor}" dominant-baseline="middle"
          font-family="Sora,sans-serif" font-size="9.5" font-weight="700"
          fill="${m.color}" opacity="0.72"
        >${line}</text>`).join('')}
      <text x="${p.x.toFixed(1)}" y="${(p.y + dy + lines.length*10).toFixed(1)}"
        text-anchor="${anchor}" dominant-baseline="middle"
        font-family="Space Mono,monospace" font-size="10" font-weight="700"
        fill="${m.color}"
      >${vals[i]}%</text>
    </g>`;
  }).join('')}
  `;

  svgEl.innerHTML = svgContent;

  /* ── Build metric cards ── */
  if (metricsWrap) {
    metricsWrap.innerHTML = METRICS.map((m,i) => `
      <div class="r-metric-card" data-idx="${i}" style="--mc:${m.color};--mc-bg:${m.bg};--mc-border:${m.border}">
        <div class="r-metric-top">
          <span class="r-metric-dot" style="background:${m.color};box-shadow:0 0 6px ${m.glow}"></span>
          <span class="r-metric-pct" style="color:${m.color}">${vals[i]}%</span>
        </div>
        <div class="r-metric-bar-track">
          <div class="r-metric-bar-fill" id="rbar-${i}" style="background:${m.color};max-width:${vals[i]}%"></div>
        </div>
        <div class="r-metric-name">${m.label}</div>
        <div class="r-metric-desc">${m.desc}</div>
      </div>`).join('');

    // Animate bar fills after mount
    requestAnimationFrame(() => {
      METRICS.forEach((_,i) => {
        const bar = $(`rbar-${i}`); if (bar) bar.style.width = vals[i] + '%';
      });
    });

    // Card interaction
    metricsWrap.querySelectorAll('.r-metric-card').forEach(card => {
      const i = parseInt(card.dataset.idx);
      card.addEventListener('pointerdown', e => {
        e.preventDefault();
        haptic('light');
        toggleRadarMetric(i);
      }, {passive:false});
    });
  }

  /* ── Active state management ── */
  let _active = null;
  const ttEl   = tooltip;
  const tName  = $('rtt-name');
  const tVal   = $('rtt-val');
  const tDesc  = $('rtt-desc');

  function toggleRadarMetric(i) {
    _active = _active === i ? null : i;
    updateRadarActive();
  }

  function updateRadarActive() {
    const cards    = metricsWrap?.querySelectorAll('.r-metric-card') || [];
    const vertices = svgEl.querySelectorAll('.rg-vertex');
    const halos    = svgEl.querySelectorAll('.rg-halo');
    const labels   = svgEl.querySelectorAll('.rg-label');
    const fill     = svgEl.querySelector('#rg-data-fill');
    const border   = svgEl.querySelector('#rg-data-border');

    cards.forEach((c,ci) => {
      c.classList.remove('active','dimmed');
      if (_active === null) return;
      if (ci === _active) c.classList.add('active');
      else c.classList.add('dimmed');
    });
    // Style active card bg/border
    metricsWrap?.querySelectorAll('.r-metric-card').forEach((c,ci) => {
      if (ci === _active) {
        c.style.background  = METRICS[ci].bg;
        c.style.borderColor = METRICS[ci].border;
        c.style.boxShadow   = `0 0 18px ${METRICS[ci].glow}`;
      } else {
        c.style.background  = 'rgba(255,255,255,0.03)';
        c.style.borderColor = _active === null ? 'rgba(255,255,255,0.07)' : 'rgba(255,255,255,0.03)';
        c.style.boxShadow   = '';
      }
    });

    vertices.forEach((v,vi) => {
      if (_active === null) {
        v.style.opacity = '1'; v.style.r = '5';
      } else if (vi === _active) {
        v.setAttribute('r','7.5');
        v.style.opacity = '1';
        v.style.filter  = 'url(#rg-glow-hi)';
      } else {
        v.setAttribute('r','4');
        v.style.opacity = '0.25';
        v.style.filter  = '';
      }
    });

    halos.forEach((h,hi) => {
      h.style.opacity = (_active === null) ? '0.45' : (hi === _active) ? '0.85' : '0.08';
    });

    labels.forEach((l,li) => {
      l.querySelectorAll('text').forEach(t => {
        t.style.opacity = (_active === null) ? '1' : (li === _active) ? '1' : '0.22';
      });
    });

    if (fill && border) {
      if (_active !== null) {
        // Highlight the active segment visually (change fill tint)
        fill.style.fill   = METRICS[_active].bg;
        fill.style.opacity= '0.7';
        border.style.stroke = METRICS[_active].color;
        border.style.strokeWidth = '2.5';
      } else {
        fill.style.fill   = 'url(#rg-fill)';
        fill.style.opacity= '1';
        border.style.stroke = 'rgba(92,211,255,0.75)';
        border.style.strokeWidth = '2';
      }
    }

    // Update tooltip
    if (_active !== null && ttEl) {
      const m = METRICS[_active];
      const p = polarPt(dataRadii[_active], _active);
      // Position tooltip near vertex in SVG units → percent
      const wrap = $('radar-svg-wrap');
      const wRect = wrap?.getBoundingClientRect();
      const svgRect = svgEl?.getBoundingClientRect();
      if (tName) { tName.textContent = m.label; tName.style.color = m.color; }
      if (tVal)  { tVal.textContent  = vals[_active] + '%'; tVal.style.color = m.color; }
      if (tDesc) tDesc.textContent = m.desc;
      // Use SVG pct positioning
      const svgW = 300, svgH = 300;
      const xPct = (p.x / svgW) * 100;
      const yPct = (p.y / svgH) * 100;
      // Clamp so tooltip doesn't go off card
      const left = Math.max(5, Math.min(55, xPct - 18));
      const top  = Math.max(5, Math.min(80, yPct - 22));
      ttEl.style.left = left + '%';
      ttEl.style.top  = top + '%';
      ttEl.style.borderColor = m.border;
      ttEl.classList.add('show');
    } else if (ttEl) {
      ttEl.classList.remove('show');
    }
  }

  /* ── Hit area events ── */
  svgEl.querySelectorAll('.rg-hit').forEach(hit => {
    const i = parseInt(hit.dataset.idx);
    hit.addEventListener('pointerdown', e => {
      e.preventDefault(); e.stopPropagation();
      haptic('light');
      toggleRadarMetric(i);
    }, {passive:false});
  });

  /* ── Tap on SVG background clears ── */
  svgEl.addEventListener('pointerdown', e => {
    if (!e.target.classList.contains('rg-hit') && !e.target.classList.contains('rg-vertex')) {
      if (_active !== null) { _active = null; updateRadarActive(); haptic('light'); }
    }
  }, {passive:false});
}


/* ── START ── */
loadOverview();
</script>
