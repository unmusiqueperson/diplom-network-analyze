/**
 * api.js — универсальный HTTP-клиент
 * Все запросы к FastAPI идут через apiFetch.
 * При 401 — автоматический logout.
 */

async function apiFetch(path, options = {}) {
  const token = sessionStorage.getItem(CONFIG.TOKEN_KEY);

  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${CONFIG.BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    authLogout();
    throw new Error('Unauthorized');
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = body.detail || `HTTP ${response.status}`;
    throw new Error(message);
  }

  // 204 No Content — возвращаем null
  if (response.status === 204) return null;

  return response.json();
}

/**
 * POST /api/v1/token — получить JWT через form-data (OAuth2 spec)
 */
async function apiLogin(username, password) {
  const form = new URLSearchParams();
  form.append('username', username);
  form.append('password', password);

  const response = await fetch(`${CONFIG.BASE_URL}/api/v1/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  });

  if (response.status === 401) {
    throw new Error('Неверный логин или пароль');
  }

  if (!response.ok) {
    throw new Error(`Ошибка сервера: ${response.status}`);
  }

  return response.json(); // { access_token, token_type }
}
