/* ===================================
   TRADE PLANNER WEBAPP
   Main JavaScript
   =================================== */

'use strict';

// ===== TELEGRAM WEBAPP INIT =====
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor('#0a0a0f');
  tg.setBackgroundColor('#0a0a0f');
}

// ===== STATE =====
const State = {
  period: 'strategy',
  summaryData: null,
  journalsData: null,
  progressionData: null,
  loading: false,
};

// ===== API =====
const API_BASE = window.location.origin;

async function apiFetch(path) {
  const headers = {};
  if (tg?.initData) {
    headers['X-Telegram-Init-Data'] = tg.initData;
  }
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API xato');
  }
  return res.json();
}

// ===== UTILS =====
function fmt(val, decimals = 2) {
  if (val === null || val === undefined) return '—';
  return Number(val).toFixed(decimals);
}

function fmtSign(val) {
  if (val === null || val === undefined) return '—';
  const n = Number(val);
  return (n >= 0 ? '+' : '') + n.toFixed(2);
}

function pnlClass(val) {
  const n = Number(val);
  if (n > 0) return 'pos';
  if (n < 0) return 'neg';
  return 'zero';
}

function pnlEmoji(val) {
  const n = Number(val);
  return n >= 0 ? '🟢' : '🔴';
}

// ===== TABS =====
function initTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const pageId = tab.dataset.page;
      document.getElementById(pageId).classList.add('active');
      onPageActivated(pageId);
    });
  });

  document.querySelectorAll('.period-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.period-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      State.period = btn.dataset.period;
      loadStats();
    });
  });
}

function onPageActivated(pageId) {
  if (pageId === 'page-overview' && !State.summaryData) loadOverview();
  if (pageId === 'page-stats') loadStats();
  if (pageId === 'page-chart') loadChart();
}

// ===== OVERVIEW PAGE =====
async function loadOverview() {
  showLoading('overview-content');
  try {
    const data = await apiFetch('/api/summary');
    State.summaryData = data;
    renderOverview(data);
  } catch (e) {
    showError('overview-content', e.message);
  }
}

function renderOverview(data) {
  const { summary, real_balance, settings } = data;
  const perf = Math.min(100, Math.max(0, summary.performance_pct));
  const totalPnl = summary.total_actual_profit;
  const pnlC = totalPnl >= 0 ? 'green' : 'red';

  document.getElementById('overview-content').innerHTML = `
    <div class="summary-grid">
      <div class="stat-box blue">
        <div class="stat-label">Haqiqiy balans</div>
        <div class="stat-value blue">$${fmt(real_balance)}</div>
        <div class="stat-sub">Rejalangan: $${fmt(settings.starting_balance)}</div>
      </div>
      <div class="stat-box ${pnlC}">
        <div class="stat-label">Jami PnL</div>
        <div class="stat-value ${pnlC}">${fmtSign(totalPnl)}$</div>
        <div class="stat-sub">Maqsad: $${fmt(summary.total_expected_profit)}</div>
      </div>
      <div class="stat-box green">
        <div class="stat-label">Bajarilgan</div>
        <div class="stat-value green">${summary.completed_days}</div>
        <div class="stat-sub">/ ${summary.total_days} kun</div>
      </div>
      <div class="stat-box amber">
        <div class="stat-label">Samaradorlik</div>
        <div class="stat-value amber">${fmt(summary.performance_pct, 1)}%</div>
        <div class="stat-sub">Yechilgan: $${fmt(summary.total_withdrawn)}</div>
      </div>
    </div>

    <div class="card">
      <div class="progress-wrap">
        <div class="progress-label">
          <span>Strategiya davri</span>
          <span>${summary.completed_days} / ${summary.total_days}</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" style="width:${(summary.completed_days/summary.total_days*100).toFixed(1)}%"></div>
        </div>
      </div>
      <div class="divider"></div>
      <div class="progress-wrap">
        <div class="progress-label">
          <span>Maqsad bajarish</span>
          <span>${fmt(summary.performance_pct, 1)}%</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" style="width:${perf}%"></div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Sozlamalar</div>
      <div class="info-row">
        <span class="info-label">Boshlang'ich balans</span>
        <span class="info-value">$${fmt(settings.starting_balance)}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Kunlik foiz</span>
        <span class="info-value">${(settings.daily_profit_rate * 100).toFixed(0)}%</span>
      </div>
      <div class="info-row">
        <span class="info-label">Boshlanish sanasi</span>
        <span class="info-value">${settings.start_date || '—'}</span>
      </div>
      ${settings.broker_name ? `
      <div class="info-row">
        <span class="info-label">Broker</span>
        <span class="info-value">${settings.broker_name}</span>
      </div>` : ''}
    </div>
  `;
}

// ===== STATS PAGE =====
async function loadStats() {
  showLoading('stats-content');
  try {
    const data = await apiFetch(`/api/journals?period=${State.period}`);
    State.journalsData = data.journals;
    renderStats(data.journals);
  } catch (e) {
    showError('stats-content', e.message);
  }
}

function renderStats(journals) {
  if (!journals.length) {
    document.getElementById('stats-content').innerHTML = `
      <div class="empty">
        <div class="empty-icon">📊</div>
        Hali savdo ma'lumotlari yo'q
      </div>`;
    return;
  }

  const totalPnl = journals.reduce((s, j) => s + j.actual_pnl, 0);
  const completed = journals.filter(j => j.is_completed);
  const winning = completed.filter(j => j.actual_pnl > 0).length;
  const losing = completed.filter(j => j.actual_pnl < 0).length;
  const totalTarget = journals.reduce((s, j) => s + j.target_profit + j.extra_target + j.carry_over_amount, 0);
  const perf = totalTarget > 0 ? (totalPnl / totalTarget * 100) : 0;

  const rows = journals.map(j => {
    const isRolled = j.is_rolled_over;
    const status = j.is_completed
      ? (isRolled ? 'status-rolled' : 'status-done')
      : 'status-pending';
    const target = j.target_profit + j.extra_target + j.carry_over_amount;
    const pnlStr = j.is_completed ? fmtSign(j.actual_pnl) + '$' : '—';
    return `
      <div class="journal-row${isRolled ? ' rolled' : ''}">
        <span class="journal-day">${j.day_number}</span>
        <span class="journal-date">${j.date}</span>
        <span class="journal-target">+${fmt(target)}$</span>
        <span class="journal-pnl ${j.is_completed ? pnlClass(j.actual_pnl) : 'zero'}">${pnlStr}</span>
        <span class="journal-status ${status}"></span>
      </div>`;
  }).join('');

  document.getElementById('stats-content').innerHTML = `
    <div class="summary-grid" style="margin-bottom:12px">
      <div class="stat-box ${totalPnl >= 0 ? 'green' : 'red'}">
        <div class="stat-label">Jami PnL</div>
        <div class="stat-value ${totalPnl >= 0 ? 'green' : 'red'}">${fmtSign(totalPnl)}$</div>
      </div>
      <div class="stat-box amber">
        <div class="stat-label">Samaradorlik</div>
        <div class="stat-value amber">${fmt(perf, 1)}%</div>
      </div>
      <div class="stat-box green">
        <div class="stat-label">Foydali kunlar</div>
        <div class="stat-value green">${winning}</div>
      </div>
      <div class="stat-box red">
        <div class="stat-label">Zararli kunlar</div>
        <div class="stat-value red">${losing}</div>
      </div>
    </div>
    <div class="card-title" style="margin-bottom:8px">Kunlik jurnal</div>
    <div class="journal-list">${rows}</div>`;
}

// ===== CHART PAGE =====
async function loadChart() {
  if (!window.Chart) {
    showError('chart-content', 'Chart.js yuklanmadi');
    return;
  }
  showLoading('chart-content');
  try {
    const data = await apiFetch('/api/progression');
    State.progressionData = data.progression;
    renderCharts(data.progression);
  } catch (e) {
    showError('chart-content', e.message);
  }
}

function renderCharts(progression) {
  const completed = progression.filter(d => d.is_completed);
  if (!completed.length) {
    document.getElementById('chart-content').innerHTML = `
      <div class="empty">
        <div class="empty-icon">📈</div>
        Grafik uchun ma'lumot yetarli emas.<br>Avval savdo kiriting va kunni yakunlang.
      </div>`;
    return;
  }

  document.getElementById('chart-content').innerHTML = `
    <div class="card">
      <div class="card-title">PnL — Kunlik</div>
      <div class="chart-wrap"><canvas id="pnlChart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title">Balans o'sishi</div>
      <div class="chart-wrap"><canvas id="balanceChart"></canvas></div>
    </div>`;

  const labels = completed.map(d => d.date.slice(5));
  const pnls = completed.map(d => d.actual_pnl || 0);
  const targets = completed.map(d => d.target_profit + d.extra_target + d.carry_over);

  // PnL Chart
  const pnlColors = completed.map(d => {
    if (d.is_rolled_over) return 'rgba(255,184,48,0.85)';
    return (d.actual_pnl || 0) >= 0 ? 'rgba(0,229,160,0.85)' : 'rgba(255,77,109,0.85)';
  });

  new Chart(document.getElementById('pnlChart'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'PnL',
          data: pnls,
          backgroundColor: pnlColors,
          borderRadius: 4,
          order: 2,
        },
        {
          label: 'Maqsad',
          data: targets,
          type: 'line',
          borderColor: '#4d9fff',
          borderWidth: 2,
          borderDash: [4, 3],
          pointRadius: 3,
          pointBackgroundColor: '#4d9fff',
          fill: false,
          order: 1,
        }
      ]
    },
    options: _chartOptions('USD'),
  });

  // Balance Chart
  const expectedBalances = progression.map(d => d.final_balance);
  const actualBalances = [];
  let runningBalance = progression[0]?.start_balance || 0;
  progression.forEach(d => {
    if (d.is_completed && d.actual_pnl !== null) {
      runningBalance = d.start_balance + d.actual_pnl;
      actualBalances.push({ x: d.date.slice(5), y: runningBalance });
    }
  });

  new Chart(document.getElementById('balanceChart'), {
    type: 'line',
    data: {
      labels: progression.map(d => d.date.slice(5)),
      datasets: [
        {
          label: 'Rejalangan',
          data: expectedBalances,
          borderColor: '#4d9fff',
          borderWidth: 2,
          borderDash: [4, 3],
          pointRadius: 2,
          fill: false,
        },
        {
          label: 'Haqiqiy',
          data: actualBalances.map(d => d.y),
          borderColor: '#00e5a0',
          borderWidth: 2.5,
          pointRadius: 3,
          pointBackgroundColor: '#00e5a0',
          fill: {
            target: 'origin',
            above: 'rgba(0,229,160,0.06)',
          },
        }
      ]
    },
    options: _chartOptions('USD'),
  });
}

function _chartOptions(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        labels: { color: '#9890b0', font: { family: 'Space Mono', size: 10 }, boxWidth: 12 }
      },
      tooltip: {
        backgroundColor: '#1a1a24',
        borderColor: '#2a2a38',
        borderWidth: 1,
        titleColor: '#9890b0',
        bodyColor: '#e8e6f0',
        titleFont: { family: 'Space Mono', size: 10 },
        bodyFont: { family: 'Space Mono', size: 11 },
        callbacks: {
          label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y >= 0 ? '+' : ''}${ctx.parsed.y.toFixed(2)}$`
        }
      }
    },
    scales: {
      x: {
        ticks: { color: '#554e6e', font: { family: 'Space Mono', size: 9 }, maxRotation: 45 },
        grid: { color: 'rgba(42,42,56,0.6)' }
      },
      y: {
        ticks: { color: '#554e6e', font: { family: 'Space Mono', size: 9 } },
        grid: { color: 'rgba(42,42,56,0.6)' },
        title: { display: true, text: yLabel, color: '#554e6e', font: { size: 9 } }
      }
    }
  };
}

// ===== HELPERS =====
function showLoading(containerId) {
  document.getElementById(containerId).innerHTML = `
    <div class="loading">
      <div class="spinner"></div>
      Yuklanmoqda...
    </div>`;
}

function showError(containerId, msg) {
  document.getElementById(containerId).innerHTML = `
    <div class="empty">
      <div class="empty-icon">⚠️</div>
      ${msg || 'Xato yuz berdi'}
    </div>`;
}

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  loadOverview();
});
