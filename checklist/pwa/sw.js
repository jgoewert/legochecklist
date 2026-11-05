// Keeps the checklists you open available offline.
//
// Pages always come from the network when it's reachable, so they stay up to date.
// Each one is also stored, and the stored copy is shown when the network fails.
// Part images come from Rebrickable's server, which doesn't allow pages to store
// them, so they're left to the browser's own cache. Rebrickable lets browsers keep
// them for a year, so images already seen still show offline.

const CACHE = 'legochecklist-pages-v1';
const MAX_PAGES = 30;

const OFFLINE_PAGE = `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Offline - LEGO Checklist</title>
<style>body{background:#2D2A2E;color:#FCFCFA;font-family:sans-serif;text-align:center;padding:2em}
h1{color:#FFD866}</style></head>
<body><h1>You're offline</h1>
<p>This page hasn't been opened on this device before, so it isn't saved for offline use.
Checklists you've opened recently are still available.</p></body></html>`;

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(key => key.startsWith('legochecklist-') && key !== CACHE)
          .map(key => caches.delete(key))))
      .then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET' || request.mode !== 'navigate') {
    return;
  }
  if (new URL(request.url).origin !== self.location.origin) {
    return;
  }
  event.respondWith(fromNetwork(event).catch(() => fromCache(request)));
});

async function fromNetwork(event) {
  const response = await fetch(event.request);
  if (response.ok) {
    event.waitUntil(remember(event.request, response.clone()));
  }
  return response;
}

// Stores a page, moving it to the newest position, and drops the oldest beyond
// MAX_PAGES.
async function remember(request, response) {
  const cache = await caches.open(CACHE);
  await cache.delete(request);
  await cache.put(request, response);
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - MAX_PAGES))
    .map(key => cache.delete(key)));
}

async function fromCache(request) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(request);
  return cached || new Response(OFFLINE_PAGE, {
    status: 503,
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });
}
