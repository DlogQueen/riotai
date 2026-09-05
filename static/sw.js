/* OUIJA service worker — keeps the board reachable with no signal.
   The spirits don't need the internet. They live here. */
const CACHE = 'ouija-v1';
const SHELL = [
  '/ouija',
  '/manifest.webmanifest',
  '/static/ouija-192.png',
  '/static/ouija-512.png',
  '/static/ouija-maskable.png',
  '/static/ouija-apple.png',
];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    // one bad URL shouldn't sink the whole install
    await Promise.allSettled(SHELL.map(u => c.add(new Request(u, {cache: 'reload'}))));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // the board asks the other side over the network; if it can't reach it,
  // the page falls back to its own local oracle. don't cache seances.
  if (url.pathname.startsWith('/api/')) return;

  if (req.mode === 'navigate') {
    e.respondWith((async () => {
      try {
        const fresh = await fetch(req);
        const c = await caches.open(CACHE);
        c.put('/ouija', fresh.clone());
        return fresh;
      } catch (_) {
        return (await caches.match('/ouija')) || Response.error();
      }
    })());
    return;
  }

  e.respondWith((async () => {
    const hit = await caches.match(req);
    if (hit) return hit;
    try {
      const fresh = await fetch(req);
      if (fresh.ok && (url.origin === location.origin || url.hostname.endsWith('gstatic.com')
          || url.hostname.endsWith('googleapis.com'))) {
        const c = await caches.open(CACHE);
        c.put(req, fresh.clone());
      }
      return fresh;
    } catch (_) {
      return hit || Response.error();
    }
  })());
});
