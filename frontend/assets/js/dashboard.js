/**
 * dashboard.js
 * Зависит от: config.js, api.js, auth.js, Chart.js (глобальный)
 *
 * Один setInterval на все запросы.
 * Chart инициализируется один раз, далее только .update('none').
 * apiFetch() подставляет JWT автоматически.
 * Ошибки API не роняют страницу.
 */

const POLL_INTERVAL = 10_000; // мс

// ── DOM-ссылки ────────────────────────────────────────────────
const dom = {
  statusDot:    document.getElementById('status-dot'),
  statusText:   document.getElementById('status-text'),
  lastUpdate:   document.getElementById('last-update'),
  errorBanner:  document.getElementById('error-banner'),
  topbarUser:   document.getElementById('topbar-user'),
  logoutBtn:    document.getElementById('logout-btn'),

  kpiTotal:     document.getElementById('kpi-total'),
  kpiAnomalies: document.getElementById('kpi-anomalies'),
  kpiRate:      document.getElementById('kpi-rate'),
  kpiDdos:      document.getElementById('kpi-ddos'),
  kpiPortscan:  document.getElementById('kpi-portscan'),

  alertsCount:  document.getElementById('alerts-count'),
  alertsTbody:  document.getElementById('alerts-tbody'),
  alertsFilter: document.getElementById('alerts-filter'),

  chartCanvas:  document.getElementById('timeseries-chart'),
  chartEmpty:   document.getElementById('chart-empty'),
  chartMeta:    document.getElementById('chart-meta'),
};

// ── Helpers ───────────────────────────────────────────────────
function formatBytes(n) {
  if (n === undefined || n === null) return '—';
  if (n >= 1_048_576) return (n / 1_048_576).toFixed(1) + ' MB';
  if (n >= 1_024)     return (n / 1_024).toFixed(1) + ' KB';
  return n + ' B';
}

function formatTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('ru-RU', { hour12: false });
}

function pillClass(type) {
  const map = {
    ddos:         'pill-ddos',
    portscan:     'pill-portscan',
    data_leak:    'pill-data_leak',
    bgp_anomaly:  'pill-bgp_anomaly',
  };
  return map[type] || 'pill-unknown';
}

// ── Chart ─────────────────────────────────────────────────────
// Инициализируется один раз в init(), далее только .update()
let timeseriesChart = null;

function initChart() {
  timeseriesChart = new Chart(dom.chartCanvas, {
    type: 'bar',
    data: {
      labels:   [],
      datasets: [
        {
          label:           'Events',
          data:            [],
          backgroundColor: '#1e3a5f',
          borderRadius:    2,
          order:           2,
        },
        {
          label:           'Anomalies',
          data:            [],
          backgroundColor: '#e05c6a',
          borderRadius:    2,
          order:           1,
        },
      ],
    },
    options: {
      responsive:          true,
      maintainAspectRatio: false,
      animation:           false,  // отключаем анимацию при обновлении данных
      plugins: {
        legend: {
          labels: {
            color:    '#555c6e',
            font:     { family: "'JetBrains Mono', monospace", size: 11 },
            boxWidth: 10,
          },
        },
        tooltip: {
          backgroundColor: '#141720',
          borderColor:     '#252933',
          borderWidth:     1,
          titleColor:      '#d4d8e2',
          bodyColor:       '#555c6e',
          titleFont:       { family: "'JetBrains Mono', monospace", size: 11 },
          bodyFont:        { family: "'JetBrains Mono', monospace", size: 11 },
        },
      },
      scales: {
        x: {
          ticks: {
            color:    '#555c6e',
            font:     { family: "'JetBrains Mono', monospace", size: 10 },
            maxRotation: 0,
            // показываем каждую N-ю метку чтобы не перекрывались
            maxTicksLimit: 12,
          },
          grid:  { color: '#1a1d24' },
        },
        y: {
          beginAtZero: true,
          ticks: {
            color:     '#555c6e',
            font:      { family: "'JetBrains Mono', monospace", size: 10 },
            precision: 0,
          },
          grid: { color: '#1a1d24' },
        },
      },
    },
  });
}

const CHART_MAX_POINTS  = 60;
const ALERTS_MAX_ROWS   = 50;

function safeTimeLabel(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function safeInt(value) {
  const n = parseInt(value, 10);
  return isNaN(n) || n < 0 ? 0 : n;
}

function renderTimeseries(rows) {
  // Защита от некорректного ответа
  const valid = Array.isArray(rows)
    ? rows.filter(r => r && typeof r === 'object')
    : [];

  // Ограничиваем количество точек — берём последние N
  const slice = valid.slice(-CHART_MAX_POINTS);

  const empty = slice.length === 0;
  dom.chartEmpty.classList.toggle('visible', empty);
  dom.chartMeta.textContent = empty ? '—' : `${slice.length} points`;

  if (empty) {
    timeseriesChart.data.labels            = [];
    timeseriesChart.data.datasets[0].data  = [];
    timeseriesChart.data.datasets[1].data  = [];
    timeseriesChart.update('none');
    return;
  }

  timeseriesChart.data.labels            = slice.map(r => safeTimeLabel(r.time));
  timeseriesChart.data.datasets[0].data  = slice.map(r => safeInt(r.events));
  timeseriesChart.data.datasets[1].data  = slice.map(r => safeInt(r.anomalies));
  timeseriesChart.update('none');
}

// ── Статус соединения ─────────────────────────────────────────
function setStatus(ok, msg) {
  dom.statusDot.className    = 'status-dot' + (ok ? ' live' : '');
  dom.statusText.textContent = msg;
}

// ── Ошибки ────────────────────────────────────────────────────
function showError(msg) {
  dom.errorBanner.textContent = msg;
  dom.errorBanner.classList.add('visible');
}

function clearError() {
  dom.errorBanner.classList.remove('visible');
}

// ── Render: KPI ───────────────────────────────────────────────
function renderStats(data) {
  dom.kpiTotal.textContent     = (data.total_events ?? '—').toLocaleString();
  dom.kpiAnomalies.textContent = (data.total_anomalies ?? '—').toLocaleString();
  dom.kpiRate.textContent      = data.anomaly_rate != null
    ? `${data.anomaly_rate}% of traffic`
    : '—';

  const by = data.by_type || {};
  dom.kpiDdos.textContent     = (by.ddos     ?? '—').toLocaleString();
  dom.kpiPortscan.textContent = (by.portscan ?? '—').toLocaleString();
}

// ── Alerts store ──────────────────────────────────────────────
//
// Единственный источник истины для таблицы.
// Polling вызывает alertsStore.replace(rows).
// WebSocket (в будущем) будет вызывать alertsStore.add(row).
//
const alertsStore = (() => {
  let items   = [];          // текущие записи, новые — в начале
  let seenKeys = new Set();  // для дедупликации

  // Уникальный ключ записи: id если есть, иначе timestamp|src_ip
  function dedupeKey(r) {
    return r.id != null
      ? String(r.id)
      : `${r.timestamp || ''}|${r.src_ip || ''}|${r.anomaly_type || ''}`;
  }

  // Полная замена из polling.
  // WS-записи, которых ещё нет в ответе API, сохраняются.
  function replace(rows) {
    const valid = Array.isArray(rows)
      ? rows.filter(r => r && typeof r === 'object')
      : [];

    // Ключи из нового polling-ответа
    const incomingKeys = new Set(valid.map(dedupeKey));

    // WS-записи, которые polling ещё не вернул (гонка или лимит API)
    const wsOnly = items.filter(r => !incomingKeys.has(dedupeKey(r)));

    // Объединяем: свежие WS-записи сверху, потом ответ polling
    const merged = [...wsOnly, ...valid];

    // Сортируем по timestamp DESC, если поле есть
    merged.sort((a, b) => {
      const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0;
      const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0;
      return tb - ta;
    });

    items    = merged.slice(0, ALERTS_MAX_ROWS);
    seenKeys = new Set(items.map(dedupeKey));
    applyAlertsFilter();
  }

  // Добавление одной записи (вызов из WebSocket в будущем).
  // Возвращает true если запись была новой и добавлена.
  function add(row) {
    if (!row || typeof row !== 'object') return false;

    const key = dedupeKey(row);
    if (seenKeys.has(key)) return false;  // дубликат — игнорируем

    seenKeys.add(key);
    items.unshift(row);                   // новые сверху

    // Удаляем лишнее из конца
    if (items.length > ALERTS_MAX_ROWS) {
      const removed = items.splice(ALERTS_MAX_ROWS);
      removed.forEach(r => seenKeys.delete(dedupeKey(r)));
    }

    return true;
  }

  function getItems() { return items; }

  return { replace, add, getItems };
})();

// ── Render: одна строка (DOM insert без перерисовки) ──────────
// WebSocket будет вызывать: if (alertsStore.add(row)) prependAlertRow(row)
function buildAlertRow(r) {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td>${formatTime(r.timestamp)}</td>
    <td>${r.src_ip || '—'}</td>
    <td><span class="pill ${pillClass(r.anomaly_type)}">${r.anomaly_type || 'unknown'}</span></td>
    <td>${r.ensemble != null ? r.ensemble : '—'}</td>
  `;
  return tr;
}

function prependAlertRow(r) {
  // Убираем заглушку "No anomalies" если она есть
  const empty = dom.alertsTbody.querySelector('.empty-row');
  if (empty) empty.remove();

  dom.alertsTbody.insertBefore(buildAlertRow(r), dom.alertsTbody.firstChild);

  // Удаляем строки сверх лимита снизу таблицы
  const rows = dom.alertsTbody.querySelectorAll('tr');
  if (rows.length > ALERTS_MAX_ROWS) {
    rows[rows.length - 1].remove();
  }

  updateAlertsCount();
}

function updateAlertsCount() {
  const n = dom.alertsTbody.querySelectorAll('tr:not(.empty-row)').length;
  dom.alertsCount.textContent = n ? `${n} records` : '0 records';
}

// ── Render: полная перерисовка из store (polling + смена фильтра)
function applyAlertsFilter() {
  const type = dom.alertsFilter.value;
  const all  = alertsStore.getItems();

  const filtered = type
    ? all.filter(r => r.anomaly_type === type)
    : all;

  const slice = filtered.slice(0, ALERTS_MAX_ROWS);

  dom.alertsCount.textContent = slice.length
    ? `${slice.length}${filtered.length > ALERTS_MAX_ROWS ? ` / ${filtered.length}` : ''} records`
    : '0 records';

  if (!slice.length) {
    dom.alertsTbody.innerHTML =
      '<tr class="empty-row"><td colspan="4">No anomalies found</td></tr>';
    return;
  }

  // Полный перерендер при смене данных от polling
  const fragment = document.createDocumentFragment();
  slice.forEach(r => fragment.appendChild(buildAlertRow(r)));
  dom.alertsTbody.replaceChildren(fragment);
}

// Polling вызывает только эту функцию
function renderAlerts(rows) {
  alertsStore.replace(rows);
}

// ── Один цикл опроса ─────────────────────────────────────────
async function poll() {
  let hasError = false;

  // /stats
  try {
    const stats = await apiFetch('/api/v1/stats');
    renderStats(stats);
  } catch (err) {
    hasError = true;
    // 401 обрабатывается в apiFetch → logout автоматически
    if (err.message !== 'Unauthorized') {
      showError(`Stats error: ${err.message}`);
    }
  }

  // /alerts
  try {
    const alerts = await apiFetch('/api/v1/alerts?limit=20');
    renderAlerts(alerts);
  } catch (err) {
    hasError = true;
    if (err.message !== 'Unauthorized') {
      showError(`Alerts error: ${err.message}`);
    }
  }

  // /stats/timeseries
  try {
    const series = await apiFetch('/api/v1/stats/timeseries');
    renderTimeseries(series);
  } catch (err) {
    hasError = true;
    if (err.message !== 'Unauthorized') {
      showError(`Timeseries error: ${err.message}`);
    }
  }

  if (!hasError) {
    clearError();
    // Если WS подключён — alerts приходят через него, polling только для stats/timeseries
    const source = (typeof wsModule !== 'undefined' && wsModule.isConnected())
      ? 'live · ws'
      : 'live · polling';
    setStatus(true, source);
    dom.lastUpdate.textContent = new Date().toLocaleTimeString('ru-RU');
  } else {
    setStatus(false, 'error');
  }
}

// ── Init ──────────────────────────────────────────────────────
function init() {
  // Redirect если нет токена
  authRequire();

  // Показываем username из токена (JWT payload, base64)
  try {
    const token   = sessionStorage.getItem(CONFIG.TOKEN_KEY);
    const payload = JSON.parse(atob(token.split('.')[1]));
    dom.topbarUser.textContent = payload.sub ?? '';
  } catch {
    // не критично
  }

  dom.logoutBtn.addEventListener('click', authLogout);

  // Смена фильтра — перерендер из кэша без нового запроса
  dom.alertsFilter.addEventListener('change', applyAlertsFilter);

  // График инициализируется один раз здесь
  initChart();

  // WebSocket — запускаем, polling остаётся как fallback
  if (typeof wsModule !== 'undefined') wsModule.connect();

  // Первый запрос сразу, потом по интервалу
  poll();
  setInterval(poll, POLL_INTERVAL);
}

init();
