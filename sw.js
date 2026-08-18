/* Cache hors-ligne : coque de l'application + jeu de données. */
const VERSION = 'v1';
const SHELL = `shell-${VERSION}`;
const DATA = `data-${VERSION}`;
const ASSETS = [
  './', './index.html', './assets/style.css', './assets/app.js',
  './assets/icon.svg', './assets/manifest.webmanifest',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => !k.endsWith(VERSION)).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const { request } = e;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  // Données : réseau d'abord (fraîcheur), cache en secours (hors-ligne).
  if (url.pathname.endsWith('/data/tracks.json')) {
    e.respondWith(
      fetch(request).then(res => {
        const copy = res.clone();
        caches.open(DATA).then(c => c.put(request, copy));
        return res;
      }).catch(() => caches.match(request))
    );
    return;
  }

  // Coque et librairies : cache d'abord.
  e.respondWith(
    caches.match(request).then(hit => hit || fetch(request).then(res => {
      if (res.ok && (url.origin === location.origin || url.host === 'unpkg.com')) {
        const copy = res.clone();
        caches.open(SHELL).then(c => c.put(request, copy));
      }
      return res;
    }))
  );
});
