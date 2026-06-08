const CACHE_NAME = 'uptime-monitor-v2';
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
            // Create offline response
            return caches.open(CACHE_NAME).then((cache) => {
                const offlineHtml = '<!DOCTYPE html><html lang="uk"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Офлайн</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-gray-900 text-white flex items-center justify-center h-screen"><div class="text-center"><div class="text-6xl mb-4">📡</div><h1 class="text-2xl font-bold">Немає з\'єднання</h1><p class="text-gray-400 mt-2">You are offline</p><button onclick="location.reload()" class="mt-6 px-6 py-3 bg-cyan-500 rounded-lg hover:bg-cyan-600 transition">Спробувати знову</button></div></body></html>';
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
            const cacheable = response.status === 200 && !url.pathname.startsWith('/login');
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
