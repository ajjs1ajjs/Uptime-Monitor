const CACHE_NAME = 'uptime-monitor-v3';
const STATIC_URLS = [
    '/static/icon-192.svg',
    '/static/icon-512.svg',
    '/static/manifest.json'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_URLS);
        }).then(() => {
            // Create offline response (self-contained, no external CDN or
            // Tailwind build dependency)
            return caches.open(CACHE_NAME).then((cache) => {
                const offlineHtml = '<!DOCTYPE html><html lang="uk"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Офлайн</title><style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f172a;color:#fff;font-family:ui-sans-serif,system-ui,sans-serif}.box{text-align:center}.icon{font-size:60px;margin-bottom:16px}h1{font-size:24px;margin:0 0 8px}p{color:#94a3b8;margin:0 0 24px}button{padding:12px 24px;background:#06b6d4;color:#fff;border:0;border-radius:8px;font-size:16px;cursor:pointer}button:hover{background:#0891b2}</style></head><body><div class="box"><div class="icon">📡</div><h1>Немає з\'єднання</h1><p>You are offline</p><button onclick="location.reload()">Спробувати знову</button></div></body></html>';
                return cache.put('/offline', new Response(offlineHtml, { headers: {'Content-Type': 'text/html; charset=utf-8'} }));
            });
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    if (url.origin !== self.location.origin) return;

    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request).catch(() =>
                new Response(JSON.stringify({ error: 'offline' }), {
                    headers: { 'Content-Type': 'application/json' }
                })
            )
        );
        return;
    }

    event.respondWith(
        fetch(event.request).then((response) => {
            // Never cache authenticated pages or API responses: the dashboard
            // HTML embeds per-session data (and admin notify settings), which
            // must not be served from the cache to a different browser user.
            const cacheable = response.status === 200 &&
                !url.pathname.startsWith('/login') &&
                !url.pathname.startsWith('/change-password') &&
                !url.pathname.startsWith('/forgot-password') &&
                !url.pathname.startsWith('/users') &&
                url.pathname !== '/' &&
                url.pathname !== '';
            if (cacheable) {
                const clone = response.clone();
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
            }
            return response;
        }).catch(() => {
            return caches.match(event.request).then((cached) => {
                return cached || caches.match('/offline');
            });
        })
    );
});
