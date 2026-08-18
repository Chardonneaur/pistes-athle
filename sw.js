/* Cache hors-ligne.
 *
 * Règle : le code de l'application passe TOUJOURS par le réseau en premier,
 * le cache ne sert que de filet hors-ligne. Sans cela, une version installée
 * continue de s'exécuter indéfiniment et les mises à jour restent invisibles.
 * Seuls les contenus immuables (photos, librairies versionnées) sont servis
 * depuis le cache en priorité.
 */
const VERSION = 'v4';
const SHELL = `shell-${VERSION}`;
const DATA = `data-${VERSION}`;
const MEDIA = 'media';                       // photos : jamais modifiées, jamais purgées
const ASSETS = [
  './', './index.html', './assets/style.css?v=4', './assets/app.js?v=4',
  './assets/icon.svg', './assets/manifest.webmanifest',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(SHELL)
      .then(c => c.addAll(ASSETS.map(u => new Request(u, { cache: 'reload' }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== SHELL && k !== DATA && k !== MEDIA)
            .map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

/** Réseau d'abord ; on met à jour le cache au passage, et on y retombe hors-ligne. */
function networkFirst(request, cacheName) {
  return fetch(request)
    .then(res => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(cacheName).then(c => c.put(request, copy));
      }
      return res;
    })
    .catch(() => caches.match(request).then(hit => hit || caches.match('./index.html')));
}

/** Cache d'abord, pour ce qui ne change jamais. */
function cacheFirst(request, cacheName) {
  return caches.match(request).then(hit => hit || fetch(request).then(res => {
    if (res.ok || res.type === 'opaque') {
      const copy = res.clone();
      caches.open(cacheName).then(c => c.put(request, copy));
    }
    return res;
  }));
}

self.addEventListener('fetch', e => {
  const { request } = e;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  if (url.pathname.includes('/data/photos/')) {
    return e.respondWith(cacheFirst(request, MEDIA));
  }
  if (url.host === 'unpkg.com' || url.host.endsWith('tile.openstreetmap.org')) {
    return e.respondWith(cacheFirst(request, MEDIA));
  }
  if (url.pathname.endsWith('/data/tracks.json')) {
    return e.respondWith(networkFirst(request, DATA));
  }
  if (url.origin === location.origin) {
    return e.respondWith(networkFirst(request, SHELL));
  }
});
