/**
 * Trade Planner WebApp
 */

const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }
const telegramId = tg?.initDataUnsafe?.user?.id || null;

// ─── Yordamchilar ───────────────────────────

async function apiFetch(endpoint, extraParams = '') {
  if (!telegramId) return null;
  try {
    const res = await fetch(`${endpoint}?telegram_id=${telegramId}${extraParams}`);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) { return null; }
}

function fmtMoney(val, showSign = true) {
  if (val == null) return '—';
  const n = Number(val);
  const sign = showSign ? (n >= 0 ? '+' : '') : '';
  return `${sign}${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}$`;
}

function fmtPrice(val) {
  if (val == null) return '—';
  return Number(val).toLocaleString('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 5 });
}

function setEl(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text ?? '—';
}

function setProgress(fillId, textId, percent, label, colorClass = '') {
  const fill = document.getElementById(fillId);
  const text = document.getElementById(textId);
  const clamped = Math.min(Math.max(Number(percent) || 0, 0), 100);
  if (fill) {
    fill.style.width = `${clamped}%`;
    if (colorClass) fill.className = `progress-fill ${colorClass}`;
  }
  if (text) text.textContent = label;
}

// ─── Tabs ────────────────────────────────────

const tabLoaded = { overview: false, journal: false, chart: false };

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    const name = btn.dataset.tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${name}`)?.classList.add('active');
    if (name === 'journal' && !tabLoaded.journal) { loadJournal(); tabLoaded.journal = true; }
    if (name === 'chart'   && !tabLoaded.chart)   { loadCharts();  tabLoaded.chart   = true; }
  });
});

// ─── Overview ────────────────────────────────

async function loadOverview() {
  const data = await apiFetch('/api/overview');
  if (!data) return;

  const { settings, current_balance, planned_balance, summary } = data;

  document.getElementById('actual-balance').textContent  = fmtMoney(current_balance, false);
  document.getElementById('planned-balance').textContent = fmtMoney(planned_balance, false);

  const diff = (current_balance || 0) - (planned_balance || 0);
  const diffEl = document.getElementById('balance-diff-val');
  if (diffEl) {
    diffEl.textContent = fmtMoney(diff);
    diffEl.className = `diff-value ${diff >= 0 ? 'pos' : 'neg'}`;
  }

  const totalDays = settings?.total_days || 0;
  const doneDays  = summary?.total_days  || 0;
  const daysPct   = totalDays > 0 ? (doneDays / totalDays) * 100 : 0;
  setProgress('progress-days', 'progress-days-text', daysPct, `${doneDays}/${totalDays}`, 'blue');

  const start  = settings?.starting_balance || 0;
  const target = planned_balance || start;
  const balPct = target > start ? ((current_balance - start) / (target - start)) * 100 : 0;
  setProgress('progress-balance', 'progress-balance-text', balPct, `${Math.max(0, Math.round(balPct))}%`, 'green');

  const totalPnl = summary?.total_pnl || 0;
  const winDays  = summary?.win_days  || 0;
  const lossDays = summary?.loss_days || 0;
  const winRate  = doneDays > 0 ? Math.round((winDays / doneDays) * 100) : 0;

  const pnlEl = document.getElementById('total-pnl');
  if (pnlEl) {
    pnlEl.textContent = fmtMoney(totalPnl);
    pnlEl.className   = `stat-value ${totalPnl >= 0 ? 'green' : 'red'}`;
  }
  setEl('win-rate',  `${winRate}%`);
  setEl('win-days',  String(winDays));
  setEl('loss-days', String(lossDays));
  setEl('s-starting', settings?.starting_balance ? `${Number(settings.starting_balance).toLocaleString()}$` : '—');
  setEl('s-rate',     settings?.daily_profit_rate ? `${(settings.daily_profit_rate * 100).toFixed(0)}%` : '—');
  setEl('s-days',     settings?.total_days ? `${settings.total_days} kun` : '—');
  setEl('s-start',    settings?.start_date || '—');
  setEl('s-broker',   settings?.broker_name || '—');
}

// ─── Journal ─────────────────────────────────

async function loadJournal() {
  const container = document.getElementById('journal-tbody');
  if (!container) return;
  container.innerHTML = '<tr><td colspan="5"><div class="loading-state"><div class="spinner"></div></div></td></tr>';

  const data = await apiFetch('/api/journal');
  if (!data?.journal?.length) {
    container.innerHTML = '<tr><td colspan="5"><div class="empty-state">Ma\'lumot topilmadi</div></td></tr>';
    return;
  }

  const rows = [...data.journal].reverse();
  container.innerHTML = rows.map(j => {
    const pnlClass = j.net_pnl >= 0 ? 'pnl-pos' : 'pnl-neg';
    const rowClass = !j.is_completed ? '' : j.is_rolled_over ? 'loss' : 'win';
    const badge = !j.is_completed
      ? '<span class="badge pending">Davom</span>'
      : j.is_rolled_over
        ? '<span class="badge loss">Rollover</span>'
        : '<span class="badge win">✓ Bajarildi</span>';

    return `<tr class="${rowClass}" onclick="openDayDetail(${j.day_number})" style="cursor:pointer">
      <td>${j.day_number}</td>
      <td class="mono" style="font-size:11px">${j.date}</td>
      <td class="mono" style="font-size:11px">${fmtMoney(j.target, false)}</td>
      <td class="${pnlClass}">${fmtMoney(j.net_pnl)}</td>
      <td>${badge}</td>
    </tr>`;
  }).join('');
}

// ─── Day Detail ──────────────────────────────

async function openDayDetail(dayNumber) {
  // Header almashtirish
  document.getElementById('main-header').style.display  = 'none';
  document.getElementById('detail-header').style.display = '';
  document.getElementById('main-view').style.display    = 'none';
  document.getElementById('detail-view').style.display  = '';
  document.getElementById('detail-badge').textContent   = `${dayNumber}-KUN`;

  // Loading
  document.getElementById('day-summary-card').innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
  document.getElementById('trades-list').innerHTML      = '<div class="loading-state"><div class="spinner"></div></div>';

  const data = await apiFetch(`/api/day_detail`, `&day_number=${dayNumber}`);
  if (!data) {
    document.getElementById('day-summary-card').innerHTML = '<div class="empty-state">Ma\'lumot topilmadi</div>';
    document.getElementById('trades-list').innerHTML = '';
    return;
  }

  const { journal: j, trades } = data;

  // ── Kun xulosasi ──
  const pnlPos  = j.net_pnl >= 0;
  const isWin   = j.is_completed && !j.is_rolled_over;
  const isLoss  = j.is_completed && j.is_rolled_over;
  const resultClass = isWin ? 'win' : isLoss ? 'loss' : '';
  const resultText  = isWin ? '✅ Maqsad bajarildi' : isLoss ? '❌ Rollover' : '⏳ Davom etmoqda';

  let carryLine = '';
  if (j.carry_over > 0) {
    carryLine = `<div class="modal-row"><span class="m-label">Rollover (+)</span><span class="m-value pnl-neg">${fmtMoney(j.carry_over)}</span></div>`;
  }

  document.getElementById('day-summary-card').innerHTML = `
    <div class="card-title">📅 ${j.day_number}-kun — ${j.date}</div>
    <div class="day-summary-grid">
      <div class="stat-item">
        <span class="stat-label">Boshlang'ich</span>
        <span class="stat-value" style="font-size:15px">${fmtMoney(j.start_balance, false)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Yakuniy</span>
        <span class="stat-value ${pnlPos ? 'green' : 'red'}" style="font-size:15px">${fmtMoney(j.end_balance, false)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Maqsad</span>
        <span class="stat-value blue" style="font-size:15px">${fmtMoney(j.total_target, false)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Net PnL</span>
        <span class="stat-value ${pnlPos ? 'green' : 'red'}" style="font-size:15px">${fmtMoney(j.net_pnl)}</span>
      </div>
    </div>
    ${carryLine}
    <div class="day-result-row ${resultClass}">
      <span>${resultText}</span>
      <span class="mono" style="font-size:12px">${trades.length} ta savdo</span>
    </div>
  `;

  // ── Savdolar ro'yxati ──
  if (!trades.length) {
    document.getElementById('trades-list').innerHTML = '<div class="empty-state">Savdolar yo\'q</div>';
    return;
  }

  document.getElementById('trades-list').innerHTML = trades.map((t, idx) => `
    <div class="trade-item" onclick="openTradeModal(${idx})">
      <div class="trade-side-bar ${t.result}"></div>
      <div class="trade-main">
        <div class="trade-top">
          <span class="trade-symbol">${t.symbol}</span>
          <span class="trade-dir ${t.direction.toLowerCase()}">${t.direction}</span>
        </div>
        <div class="trade-prices">
          ${fmtPrice(t.entry_price)} → ${fmtPrice(t.exit_price)}
          ${t.close_time ? `<span style="margin-left:6px;color:var(--text-muted)">${t.close_time.slice(0,5)}</span>` : ''}
        </div>
      </div>
      <div>
        <div class="trade-pnl ${t.pnl >= 0 ? 'pnl-pos' : 'pnl-neg'}">${fmtMoney(t.pnl)}</div>
        <div class="trade-lot">${t.quantity} lot</div>
      </div>
    </div>
  `).join('');

  // Savdolarni global ga saqlash (modal uchun)
  window._currentTrades = trades;
}

// ─── Trade Modal ─────────────────────────────

function openTradeModal(idx) {
  const t = window._currentTrades?.[idx];
  if (!t) return;

  const resultLabel = t.result === 'tp' ? '🟢 TP' : t.result === 'sl' ? '🔴 SL' : '⚪ BE';
  const dirClass    = t.direction.toLowerCase() === 'buy' ? 'green' : 'red';

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-handle"></div>
    <div class="modal-title">
      <span>${t.symbol}</span>
      <span class="trade-dir ${t.direction.toLowerCase()}">${t.direction}</span>
      <span style="margin-left:auto;font-size:13px">${resultLabel}</span>
    </div>

    <div class="modal-row">
      <span class="m-label">Kirish narxi</span>
      <span class="m-value">${fmtPrice(t.entry_price)}</span>
    </div>
    <div class="modal-row">
      <span class="m-label">Chiqish narxi</span>
      <span class="m-value">${fmtPrice(t.exit_price)}</span>
    </div>
    <div class="modal-row">
      <span class="m-label">Hajm (lot)</span>
      <span class="m-value">${t.quantity}</span>
    </div>

    <div class="modal-divider"></div>

    <div class="modal-row">
      <span class="m-label">PnL</span>
      <span class="m-value ${t.pnl >= 0 ? 'pnl-pos' : 'pnl-neg'}">${fmtMoney(t.pnl)}</span>
    </div>
    ${t.swap !== 0 ? `
    <div class="modal-row">
      <span class="m-label">Swap</span>
      <span class="m-value ${t.swap >= 0 ? 'pnl-pos' : 'pnl-neg'}">${fmtMoney(t.swap)}</span>
    </div>` : ''}
    ${t.commission !== 0 ? `
    <div class="modal-row">
      <span class="m-label">Komissiya</span>
      <span class="m-value pnl-neg">${fmtMoney(t.commission)}</span>
    </div>` : ''}
    <div class="modal-row">
      <span class="m-label">Net PnL</span>
      <span class="m-value ${t.net_pnl >= 0 ? 'pnl-pos' : 'pnl-neg'}" style="font-size:15px">${fmtMoney(t.net_pnl)}</span>
    </div>

    ${t.open_time || t.close_time ? `<div class="modal-divider"></div>` : ''}
    ${t.sl_price ? `
    <div class="modal-row">
      <span class="m-label">Stop Loss</span>
      <span class="m-value pnl-neg">${fmtPrice(t.sl_price)}</span>
    </div>` : ''}
    ${t.tp_price ? `
    <div class="modal-row">
      <span class="m-label">Take Profit</span>
      <span class="m-value pnl-pos">${fmtPrice(t.tp_price)}</span>
    </div>` : ''}
    ${t.open_time ? `
    <div class="modal-row">
      <span class="m-label">Ochilish vaqti</span>
      <span class="m-value">${t.open_time}</span>
    </div>` : ''}
    ${t.close_time ? `
    <div class="modal-row">
      <span class="m-label">Yopilish vaqti</span>
      <span class="m-value">${t.close_time}</span>
    </div>` : ''}
    ${t.order_id ? `
    <div class="modal-row">
      <span class="m-label">Order ID</span>
      <span class="m-value" style="font-size:11px">#${t.order_id}</span>
    </div>` : ''}
    ${t.broker ? `
    <div class="modal-row">
      <span class="m-label">Broker</span>
      <span class="m-value">${t.broker}</span>
    </div>` : ''}
  `;

  document.getElementById('trade-modal').style.display = '';
}

function closeModal() {
  document.getElementById('trade-modal').style.display = 'none';
}

document.getElementById('modal-backdrop')?.addEventListener('click', closeModal);

// ─── Back button ─────────────────────────────

document.getElementById('back-btn')?.addEventListener('click', () => {
  document.getElementById('main-header').style.display  = '';
  document.getElementById('detail-header').style.display = 'none';
  document.getElementById('main-view').style.display    = '';
  document.getElementById('detail-view').style.display  = 'none';
  window._currentTrades = [];
});

// ─── Charts ──────────────────────────────────

let balChart = null, pnlChart = null;

async function loadCharts() {
  const data = await apiFetch('/api/chart_data');
  if (!data?.planned_dates?.length) {
    document.getElementById('chart-balance-wrap').innerHTML = '<div class="empty-state">Ma\'lumot yetarli emas</div>';
    document.getElementById('chart-pnl-wrap').innerHTML = '';
    return;
  }

  const { actual_dates = [], actual = [], planned_dates, planned, pnl = [] } = data;

  // Ikkala dataset uchun alohida labellar
  const grid = 'rgba(255,255,255,0.06)', hint = '#5a6478';

  const yScale = {
    ticks: { color: hint, font: { size: 10, family: "'JetBrains Mono'" }, callback: v => `$${Number(v).toLocaleString()}` },
    grid: { color: grid, drawBorder: false },
  };
  const xScale = (labels) => ({
    ticks: { color: hint, font: { size: 10, family: "'JetBrains Mono'" }, maxRotation: 45, maxTicksLimit: 8 },
    grid: { color: grid, drawBorder: false },
  });

  document.getElementById('chart-balance-wrap').innerHTML = '<canvas id="balance-chart" height="220"></canvas>';
  const balCtx = document.getElementById('balance-chart')?.getContext('2d');
  if (balCtx) {
    if (balChart) balChart.destroy();
    balChart = new Chart(balCtx, {
      type: 'line',
      data: {
        datasets: [
          {
            label: 'Haqiqiy',
            data: actual_dates.map((d, i) => ({ x: d, y: actual[i] })),
            borderColor: '#00e096',
            backgroundColor: 'rgba(0,224,150,0.08)',
            borderWidth: 2,
            pointRadius: 3,
            pointBackgroundColor: '#00e096',
            fill: true,
            tension: 0.35,
          },
          {
            label: 'Rejalangan',
            data: planned_dates.map((d, i) => ({ x: d, y: planned[i] })),
            borderColor: '#4d9fff',
            borderWidth: 1.5,
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
            tension: 0.35,
          },
        ],
      },
      options: {
        responsive: true,
        parsing: false,
        plugins: {
          legend: { labels: { color: '#8892a4', font: { size: 11 }, boxWidth: 12, padding: 16 } },
          tooltip: {
            backgroundColor: '#1a1e2a', borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1,
            titleColor: '#e8eaf0', bodyColor: '#8892a4',
            callbacks: { label: ctx => ` ${ctx.dataset.label}: $${Number(ctx.parsed.y).toLocaleString('en-US', { minimumFractionDigits: 2 })}` },
          },
        },
        scales: {
          x: { type: 'category', ticks: { color: hint, font: { size: 10, family: "'JetBrains Mono'" }, maxRotation: 45, maxTicksLimit: 8 }, grid: { color: grid, drawBorder: false } },
          y: yScale,
        },
        interaction: { mode: 'index', intersect: false },
      },
    });
  }

  document.getElementById('chart-pnl-wrap').innerHTML = '<canvas id="pnl-chart" height="180"></canvas>';
  const pnlCtx = document.getElementById('pnl-chart')?.getContext('2d');
  if (pnlCtx) {
    if (pnlChart) pnlChart.destroy();
    pnlChart = new Chart(pnlCtx, {
      type: 'bar',
      data: {
        labels: actual_dates,
        datasets: [{
          label: 'Kunlik PnL', data: pnl,
          backgroundColor: pnl.map(v => v >= 0 ? 'rgba(0,224,150,0.65)' : 'rgba(255,77,106,0.65)'),
          borderColor: pnl.map(v => v >= 0 ? '#00e096' : '#ff4d6a'),
          borderWidth: 1, borderRadius: 4,
        }],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1a1e2a', borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1,
            titleColor: '#e8eaf0', bodyColor: '#8892a4',
            callbacks: { label: ctx => ` PnL: ${ctx.raw >= 0 ? '+' : ''}$${Number(ctx.raw).toLocaleString('en-US', { minimumFractionDigits: 2 })}` },
          },
        },
        scales: {
          x: { ticks: { color: hint, font: { size: 10, family: "'JetBrains Mono'" }, maxRotation: 45 }, grid: { color: grid, drawBorder: false } },
          y: yScale,
        },
      },
    });
  }
}

// ─── Start ───────────────────────────────────
loadOverview();
