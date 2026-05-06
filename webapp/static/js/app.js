/**
 * Trade Planner WebApp — asosiy JavaScript
 * Telegram WebApp API orqali ishlaydi.
 */

const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }

const telegramId = tg?.initDataUnsafe?.user?.id || null;

// ─── Yordamchilar ───────────────────────────

async function apiFetch(endpoint) {
  if (!telegramId) return null;
  try {
    const res = await fetch(`${endpoint}?telegram_id=${telegramId}`);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    console.error(`apiFetch [${endpoint}]:`, e);
    return null;
  }
}

function fmtMoney(val, showSign = true) {
  if (val == null || val === '') return '—';
  const n = Number(val);
  const sign = showSign ? (n >= 0 ? '+' : '') : '';
  return `${sign}${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}$`;
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

function showLoading(id) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<div class="loading-state"><div class="spinner"></div><span>Yuklanmoqda...</span></div>`;
}

function showError(id, msg = 'Ma\'lumot topilmadi') {
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<div class="empty-state">${msg}</div>`;
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
  if (!data) {
    document.getElementById('actual-balance').textContent = 'Xato';
    return;
  }

  const { settings, current_balance, planned_balance, summary } = data;

  // Balans
  const actualEl = document.getElementById('actual-balance');
  if (actualEl) actualEl.textContent = fmtMoney(current_balance, false);

  const plannedEl = document.getElementById('planned-balance');
  if (plannedEl) plannedEl.textContent = fmtMoney(planned_balance, false);

  // Farq
  const diff = (current_balance || 0) - (planned_balance || 0);
  const diffEl = document.getElementById('balance-diff-val');
  if (diffEl) {
    diffEl.textContent = fmtMoney(diff);
    diffEl.className = `diff-value ${diff >= 0 ? 'pos' : 'neg'}`;
  }

  // Progress — kunlar
  const totalDays = settings?.total_days || 0;
  const doneDays  = summary?.total_days  || 0;
  const daysPct   = totalDays > 0 ? (doneDays / totalDays) * 100 : 0;
  setProgress('progress-days', 'progress-days-text', daysPct, `${doneDays}/${totalDays}`, 'blue');

  // Progress — balans
  const start  = settings?.starting_balance || 0;
  const target = planned_balance || start;
  const balPct = target > start
    ? ((current_balance - start) / (target - start)) * 100
    : 0;
  setProgress('progress-balance', 'progress-balance-text', balPct, `${Math.max(0, Math.round(balPct))}%`, 'green');

  // Natijalar
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

  // Sozlamalar
  setEl('s-starting', settings?.starting_balance  ? `${Number(settings.starting_balance).toLocaleString()}$` : '—');
  setEl('s-rate',     settings?.daily_profit_rate  ? `${(settings.daily_profit_rate * 100).toFixed(0)}%`     : '—');
  setEl('s-days',     settings?.total_days         ? `${settings.total_days} kun`                            : '—');
  setEl('s-start',    settings?.start_date         || '—');
  setEl('s-broker',   settings?.broker_name        || '—');
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

    return `<tr class="${rowClass}">
      <td>${j.day_number}</td>
      <td class="mono" style="font-size:11px">${j.date}</td>
      <td class="mono pnl-pos" style="font-size:11px">${fmtMoney(j.target, false)}</td>
      <td class="${pnlClass}">${fmtMoney(j.net_pnl)}</td>
      <td>${badge}</td>
    </tr>`;
  }).join('');
}

// ─── Charts ──────────────────────────────────

let balChart = null;
let pnlChart = null;

async function loadCharts() {
  showLoading('chart-balance-wrap');
  showLoading('chart-pnl-wrap');

  const data = await apiFetch('/api/chart_data');

  if (!data?.dates?.length) {
    showError('chart-balance-wrap', 'Grafik uchun ma\'lumot yetarli emas');
    showError('chart-pnl-wrap', '');
    return;
  }

  const { dates, actual, planned, pnl } = data;
  const grid = 'rgba(255,255,255,0.06)';
  const hint = '#5a6478';

  const commonScales = {
    x: {
      ticks: { color: hint, font: { size: 10, family: "'JetBrains Mono'" }, maxRotation: 45 },
      grid:  { color: grid, drawBorder: false },
    },
    y: {
      ticks: {
        color: hint,
        font: { size: 10, family: "'JetBrains Mono'" },
        callback: v => `$${Number(v).toLocaleString()}`,
      },
      grid: { color: grid, drawBorder: false },
    },
  };

  // Balance chart
  document.getElementById('chart-balance-wrap').innerHTML = '<canvas id="balance-chart" height="220"></canvas>';
  const balCtx = document.getElementById('balance-chart')?.getContext('2d');
  if (balCtx) {
    if (balChart) balChart.destroy();
    balChart = new Chart(balCtx, {
      type: 'line',
      data: {
        labels: dates,
        datasets: [
          {
            label: 'Haqiqiy',
            data: actual,
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
            data: planned,
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
        plugins: {
          legend: {
            labels: {
              color: '#8892a4',
              font: { size: 11 },
              boxWidth: 12,
              padding: 16,
            },
          },
          tooltip: {
            backgroundColor: '#1a1e2a',
            borderColor: 'rgba(255,255,255,0.1)',
            borderWidth: 1,
            titleColor: '#e8eaf0',
            bodyColor: '#8892a4',
            callbacks: {
              label: ctx => ` ${ctx.dataset.label}: $${Number(ctx.raw).toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
            },
          },
        },
        scales: commonScales,
        interaction: { mode: 'index', intersect: false },
      },
    });
  }

  // PnL chart
  document.getElementById('chart-pnl-wrap').innerHTML = '<canvas id="pnl-chart" height="180"></canvas>';
  const pnlCtx = document.getElementById('pnl-chart')?.getContext('2d');
  if (pnlCtx) {
    if (pnlChart) pnlChart.destroy();
    pnlChart = new Chart(pnlCtx, {
      type: 'bar',
      data: {
        labels: dates,
        datasets: [{
          label: 'Kunlik PnL',
          data: pnl,
          backgroundColor: pnl.map(v => v >= 0 ? 'rgba(0,224,150,0.65)' : 'rgba(255,77,106,0.65)'),
          borderColor:      pnl.map(v => v >= 0 ? '#00e096' : '#ff4d6a'),
          borderWidth: 1,
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1a1e2a',
            borderColor: 'rgba(255,255,255,0.1)',
            borderWidth: 1,
            titleColor: '#e8eaf0',
            bodyColor: '#8892a4',
            callbacks: {
              label: ctx => ` PnL: ${ctx.raw >= 0 ? '+' : ''}$${Number(ctx.raw).toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
            },
          },
        },
        scales: commonScales,
      },
    });
  }
}

// ─── Ishga tushirish ─────────────────────────

loadOverview();
