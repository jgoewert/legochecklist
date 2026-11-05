// Runs checklist/pwa/sw.js against fake caches and a fake network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(
  path.join(__dirname, '..', '..', 'checklist', 'pwa', 'sw.js'), 'utf8');
const ORIGIN = 'https://example.test';

function fakeCaches() {
  const store = new Map();
  const open = async name => {
    if (!store.has(name)) {
      store.set(name, new Map());
    }
    const entries = store.get(name);
    return {
      put: async (request, response) => { entries.set(request.url, { request, response }); },
      delete: async request => entries.delete(request.url),
      match: async request => entries.get(request.url)?.response,
      keys: async () => [...entries.values()].map(entry => entry.request),
    };
  };
  return {
    store,
    api: {
      open,
      keys: async () => [...store.keys()],
      delete: async name => store.delete(name),
    },
  };
}

function loadWorker(network) {
  const listeners = {};
  const caches = fakeCaches();
  const self = {
    addEventListener: (type, listener) => { listeners[type] = listener; },
    location: new URL(ORIGIN + '/sw.js'),
    skipWaiting: () => {},
    clients: { claim: async () => {} },
  };
  vm.runInNewContext(source, {
    self, caches: caches.api, fetch: network, Response, URL, Promise, Math,
  });

  async function request(url, { mode = 'navigate', method = 'GET' } = {}) {
    let responded;
    const waits = [];
    listeners.fetch({
      request: { url, mode, method },
      respondWith: promise => { responded = promise; },
      waitUntil: promise => waits.push(promise),
    });
    if (!responded) {
      return undefined;
    }
    const response = await responded;
    await Promise.all(waits);
    return response;
  }

  async function activate() {
    let done;
    listeners.activate({ waitUntil: promise => { done = promise; } });
    await done;
  }

  return { request, activate, caches };
}

const online = async request => new Response('page ' + request.url, { status: 200 });
const offline = async () => { throw new TypeError('Failed to fetch'); };

test('pages come from the network and are stored for later', async () => {
  let network = online;
  const worker = loadWorker(request => network(request));

  const fresh = await worker.request(ORIGIN + '/?set_id=1682');
  assert.equal(await fresh.text(), 'page ' + ORIGIN + '/?set_id=1682');

  network = offline;
  const stored = await worker.request(ORIGIN + '/?set_id=1682');
  assert.equal(stored.status, 200);
  assert.equal(await stored.text(), 'page ' + ORIGIN + '/?set_id=1682');
});

test('an unopened page shows the offline message', async () => {
  const worker = loadWorker(offline);

  const response = await worker.request(ORIGIN + '/?set_id=6080');

  assert.equal(response.status, 503);
  assert.match(await response.text(), /You're offline/);
});

test('error pages are not stored', async () => {
  let network = async () => new Response('not found', { status: 404 });
  const worker = loadWorker(request => network(request));
  await worker.request(ORIGIN + '/?set_id=nope');

  network = offline;
  const response = await worker.request(ORIGIN + '/?set_id=nope');
  assert.equal(response.status, 503);
});

test('images, other requests and other sites are left to the browser', async () => {
  const worker = loadWorker(online);

  assert.equal(await worker.request(ORIGIN + '/icon-192.png', { mode: 'no-cors' }), undefined);
  assert.equal(await worker.request('https://cdn.rebrickable.com/x.jpg', { mode: 'no-cors' }), undefined);
  assert.equal(await worker.request('https://rebrickable.com/sets/1682-1/'), undefined);
  assert.equal(await worker.request(ORIGIN + '/', { method: 'POST' }), undefined);
});

test('only the 30 most recently opened pages are kept', async () => {
  const worker = loadWorker(online);
  for (let i = 1; i <= 32; i++) {
    await worker.request(ORIGIN + '/?set_id=' + i);
  }
  await worker.request(ORIGIN + '/?set_id=3');

  const [entries] = [...worker.caches.store.values()];
  const kept = [...entries.keys()].map(url => new URL(url).searchParams.get('set_id'));
  // Pages 1 and 2 were the oldest, and reopening page 3 made it the newest.
  assert.equal(kept.length, 30);
  assert.ok(!kept.includes('1') && !kept.includes('2'));
  assert.equal(kept.at(-1), '3');

  await worker.request(ORIGIN + '/?set_id=33');
  const after = [...entries.keys()].map(url => new URL(url).searchParams.get('set_id'));
  assert.ok(!after.includes('4') && after.includes('3'));
});

test('activating removes older versions of its cache only', async () => {
  const worker = loadWorker(online);
  await worker.request(ORIGIN + '/');
  await worker.caches.api.open('legochecklist-pages-v0');
  await worker.caches.api.open('something-else');

  await worker.activate();

  assert.deepEqual(
    [...worker.caches.store.keys()].sort(),
    ['legochecklist-pages-v1', 'something-else'],
  );
});
