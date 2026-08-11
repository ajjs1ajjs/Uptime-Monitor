// Uptime Monitor — shared UI script.
// Loaded on every page (base.html). Contains theme handling, service worker
// registration, htmx integration and the global event-delegation dispatcher so
// the CSP can drop 'unsafe-inline' (no inline <script> blocks or event
// attributes in templates).
(function () {
  'use strict';

  // --- theme ---------------------------------------------------------------
  function applyTheme() {
    const theme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDark = theme ? theme === 'dark' : prefersDark;
    window.__isDark = isDark;
    if (isDark) {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
    } else {
      document.documentElement.classList.add('light');
      document.documentElement.classList.remove('dark');
    }
    const themeBtn = document.getElementById('themeBtn');
    if (themeBtn) themeBtn.textContent = isDark ? '🌙' : '☀️';
  }

  window.toggleTheme = function () {
    const isDark = !window.__isDark;
    window.__isDark = isDark;
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    applyTheme();
  };

  // --- toast (non-blocking replacement for alert()) ------------------------
  window.showToast = function (msg, isError) {
    let existing = document.getElementById('um-toast');
    if (existing) existing.remove();
    const t = document.createElement('div');
    t.id = 'um-toast';
    t.textContent = msg;
    t.style.cssText =
      'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:9999;' +
      'background:' + (isError ? '#ef4444' : '#10b981') + ';color:#fff;' +
      'padding:12px 20px;border-radius:10px;font-size:14px;' +
      'box-shadow:0 8px 24px rgba(0,0,0,.4);max-width:90vw;text-align:center';
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 3500);
  };

  // --- service worker --------------------------------------------------------
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js')
      .then(function (reg) { reg.update(); })
      .catch(function (err) { console.log('SW registration failed:', err); });
  }

  // --- htmx ----------------------------------------------------------------
  document.addEventListener('htmx:beforeSwap', function (evt) {
    if (evt.detail.xhr.status === 429) {
      showToast('Rate limited. Please wait.', true);
      evt.detail.shouldSwap = false;
    }
  });
  document.addEventListener('htmx:afterSwap', function (evt) {
    if (typeof applyLanguage === 'function') applyLanguage();
  });

  // --- event delegation ----------------------------------------------------
  // Templates use data-action / data-change / data-keyup attributes instead of
  // inline onclick/onchange/onkeyup. Pages register their handlers on
  // window.AppActions / AppChange / AppKeyup.
  document.addEventListener('click', function (e) {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    const handler = (window.AppActions || {})[el.getAttribute('data-action')];
    if (handler) { e.stopPropagation(); handler(el, e); }
  });
  document.addEventListener('change', function (e) {
    const el = e.target.closest('[data-change]');
    if (!el) return;
    const handler = (window.AppChange || {})[el.getAttribute('data-change')];
    if (handler) handler(el, e);
  });
  document.addEventListener('keyup', function (e) {
    const el = e.target.closest('[data-keyup]');
    if (!el) return;
    const handler = (window.AppKeyup || {})[el.getAttribute('data-keyup')];
    if (handler) handler(el, e);
  });

  // Common actions shared by all pages.
  window.AppActions = Object.assign(window.AppActions || {}, {
    toggleTheme: function () { window.toggleTheme(); },
    toggleLang: function () { if (typeof toggleLang === 'function') toggleLang(); },
  });

  document.addEventListener('DOMContentLoaded', function () {
    applyTheme();
    if (typeof applyLanguage === 'function') applyLanguage();
  });
})();
