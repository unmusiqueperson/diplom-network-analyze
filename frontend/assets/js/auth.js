/**
 * auth.js — управление аутентификацией
 * Зависит от: config.js, api.js
 */

function authGetToken() {
  return sessionStorage.getItem(CONFIG.TOKEN_KEY);
}

function authIsLoggedIn() {
  return !!authGetToken();
}

function authSaveToken(token) {
  sessionStorage.setItem(CONFIG.TOKEN_KEY, token);
}

function authLogout() {
  sessionStorage.removeItem(CONFIG.TOKEN_KEY);
  window.location.href = '/login.html';
}

/**
 * Вызывается на login.html после сабмита формы
 */
async function authLogin(username, password) {
  const data = await apiLogin(username, password); // бросает Error при 401
  authSaveToken(data.access_token);
  window.location.href = '/index.html';
}

/**
 * Guard для защищённых страниц (index.html).
 * Вызывать в начале скрипта страницы.
 */
function authRequire() {
  if (!authIsLoggedIn()) {
    window.location.href = '/login.html';
  }
}

/**
 * Guard для login.html — если уже залогинен, не показываем форму.
 */
function authRedirectIfLoggedIn() {
  if (authIsLoggedIn()) {
    window.location.href = '/index.html';
  }
}
