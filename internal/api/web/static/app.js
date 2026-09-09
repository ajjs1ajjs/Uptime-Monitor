// Uptime Monitor — shared UI script.
// Loaded on every page (base.html). Contains theme handling, service worker
// registration, htmx integration and the global event-delegation dispatcher so
// the CSP can drop 'unsafe-inline' (no inline <script> blocks or event
// attributes in templates).
(function () {
  'use strict';

  // --- CSRF double-submit (SEC-002) ----------------------------------------
  // The server sets a readable `csrf_token` cookie on login; every same-origin
  // fetch() with a state-changing method echoes it back as X-CSRF-Token. This
  // is defense-in-depth on top of the server's Origin/Referer check and needs
  // no per-call-site changes (dashboard.js / users.js call fetch directly).
  function getCookie(name) {
    const prefix = name + '=';
    const parts = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < parts.length; i++) {
      const c = parts[i].trim();
      if (c.indexOf(prefix) === 0) return decodeURIComponent(c.slice(prefix.length));
    }
    return '';
  }
  if (window.fetch) {
    const origFetch = window.fetch.bind(window);
    window.fetch = function (input, init) {
      try {
        const token = getCookie('csrf_token');
        if (token) {
          let url = '';
          let method = 'GET';
          if (typeof input === 'string') {
            url = input;
          } else if (input && input.url) {
            url = input.url;
            if (input.method) method = input.method;
          }
          if (init && init.method) method = init.method;
          const m = String(method).toUpperCase();
          if (m !== 'GET' && m !== 'HEAD' && m !== 'OPTIONS') {
            let sameOrigin = false;
            try {
              sameOrigin = new URL(url, window.location.href).origin === window.location.origin;
            } catch (e) { sameOrigin = false; }
            if (sameOrigin) {
              if (input && typeof input !== 'string' && input.headers) {
                // Request object: only attach when the caller did not set it.
                try {
                  if (!input.headers.get('X-CSRF-Token')) {
                    input = new Request(input, { headers: Object.assign({}, Object.fromEntries(input.headers.entries()), { 'X-CSRF-Token': token }) });
                  }
                } catch (e) { /* leave request untouched on exotic inputs */ }
              } else {
                init = init || {};
                init.headers = init.headers || {};
                if (init.headers instanceof Headers) {
                  if (!init.headers.get('X-CSRF-Token')) init.headers.set('X-CSRF-Token', token);
                } else if (Array.isArray(init.headers)) {
                  if (!init.headers.some(function (h) { return String(h[0]).toLowerCase() === 'x-csrf-token'; })) {
                    init.headers.push(['X-CSRF-Token', token]);
                  }
                } else if (!init.headers['X-CSRF-Token']) {
                  init.headers['X-CSRF-Token'] = token;
                }
              }
            }
          }
        }
      } catch (e) { /* never break fetch on CSRF helper errors */ }
      return origFetch(input, init);
    };
  }

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
