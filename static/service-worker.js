const SHELL_CACHE = 'taskline-shell-v30';
const APP_SHELL = [
  '/',
  '/storage.js?v=1',
  '/auth.js?v=2',
  '/account.html',
  '/account.css?v=1',
  '/account-page.js?v=4',
  '/styles.css?v=23',
  '/theme.js?v=3',
  '/theme.css?v=4',
  '/settings.css?v=1',
  '/debts.css?v=2',
  '/debts.js?v=2',
  '/settings.js?v=5',
  '/task-order.js?v=4',
  '/calendar-utils.js?v=4',
  '/app.js?v=32',
  '/manifest.webmanifest',
  '/icon-192.png',
  '/icon-512.png',
  '/icon-maskable-512.png',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then(cache => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key.startsWith('taskline-') && key !== SHELL_CACHE).map(key => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname.startsWith('/uploads/')) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        // The versioned shell is public. Always validate the session via the network.
        if (url.pathname === '/' || url.pathname === '/index.html') {
          const cache = await caches.open(SHELL_CACHE);
          const shell = await cache.match('/');
          if (shell) return shell;
        }
        try {
          const response = await fetch(request);
          if (response.ok && url.pathname === '/') {
            const cache = await caches.open(SHELL_CACHE);
            await cache.put('/', response.clone());
          }
          return response;
        } catch {
          return caches.match(url.pathname === '/account.html' ? '/account.html' : '/');
        }
      })(),
    );
    return;
  }

  event.respondWith(
    (async () => {
      const cached = await caches.match(request);
      if (cached) return cached;
      const response = await fetch(request);
      if (response.ok) {
        const cache = await caches.open(SHELL_CACHE);
        await cache.put(request, response.clone());
      }
      return response;
    })(),
  );
});
