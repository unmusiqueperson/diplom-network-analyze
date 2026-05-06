/**
 * websocket.js — real-time слой поверх polling
 * Зависит от: config.js, auth.js, dashboard.js (alertsStore, prependAlertRow, setStatus)
 *
 * Подключается при загрузке страницы.
 * При разрыве — переподключается с экспоненциальной задержкой (3s → 6s → ... → 30s).
 * Один активный сокет в любой момент времени.
 * Polling в dashboard.js продолжает работать как fallback всегда.
 */

const wsModule = (() => {
  const DELAY_INITIAL = 3_000;   // мс до первого переподключения
  const DELAY_MAX     = 30_000;  // максимальная задержка
  const PING_INTERVAL = 20_000;  // keep-alive ping (мс)

  let socket         = null;
  let reconnectTimer = null;  // null = нет запланированного реконнекта
  let pingTimer      = null;
  let currentDelay   = DELAY_INITIAL;
  let destroyed      = false;

  // ── URL с токеном (WS не поддерживает custom headers) ──────────
  function buildUrl() {
    const token = sessionStorage.getItem(CONFIG.TOKEN_KEY) || '';
    return `${CONFIG.WS_URL}?token=${encodeURIComponent(token)}`;
  }

  // ── Ping чтобы не дропал прокси/nginx ──────────────────────────
  function startPing() {
    stopPing();
    pingTimer = setInterval(() => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send('ping');
      }
    }, PING_INTERVAL);
  }

  function stopPing() {
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
  }

  // ── Статус в topbar ────────────────────────────────────────────
  function markConnected() {
    setStatus(true, 'live · ws');
  }

  function markDisconnected() {
    // Не трогаем статус — polling сам выставит 'live · polling' при успехе
  }

  // ── Создание сокета ────────────────────────────────────────────
  function connect() {
    if (destroyed) return;

    // Не создаём новый сокет если уже есть активный
    if (socket && (
      socket.readyState === WebSocket.CONNECTING ||
      socket.readyState === WebSocket.OPEN
    )) return;

    socket = new WebSocket(buildUrl());

    socket.onopen = () => {
      currentDelay = DELAY_INITIAL;   // сбрасываем задержку
      reconnectTimer = null;
      startPing();
      markConnected();
    };

    socket.onmessage = ({ data }) => {
      try {
        const row = JSON.parse(data);
        if (alertsStore.add(row)) prependAlertRow(row);
      } catch {
        // игнорируем невалидный JSON (например pong от сервера)
      }
    };

    socket.onerror = () => {
      // onerror всегда предшествует onclose — реконнект делаем в onclose
    };

    socket.onclose = ({ code }) => {
      stopPing();
      markDisconnected();

      // 4001 = невалидный токен → не переподключаемся
      if (code === 4001) {
        authLogout();
        return;
      }

      scheduleReconnect();
    };
  }

  // ── Переподключение с задержкой ────────────────────────────────
  function scheduleReconnect() {
    if (destroyed || reconnectTimer) return;  // уже запланировано

    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, currentDelay);

    // Экспоненциальный backoff
    currentDelay = Math.min(currentDelay * 2, DELAY_MAX);
  }

  // ── Публичный API ──────────────────────────────────────────────
  function isConnected() {
    return socket !== null && socket.readyState === WebSocket.OPEN;
  }

  function destroy() {
    destroyed = true;
    stopPing();
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    if (socket) { socket.close(); socket = null; }
  }

  return { connect, isConnected, destroy };
})();
