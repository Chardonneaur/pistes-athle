/* Cache hors-ligne.
 *
 * Règle : le code de l'application passe TOUJOURS par le réseau en premier,
 * le cache ne sert que de filet hors-ligne. Sans cela, une version installée
 * continue de s'exécuter indéfiniment et les mises à jour restent invisibles.
 * Seuls les contenus immuables (photos, librairies versionnées) sont servis
 * depuis le cache en priorité.
 */
const VERSION = 'v6';
const SHELL = `shell-${VERSION}`;
const DATA = `data-${VERSION}`;
const MEDIA = 'media';                       // photos : jamais modifiées, jamais purgées
const ASSETS = [
  './', './index.html', './en/', './en/index.html',
  './assets/style.css?v=6', './assets/i18n.js?v=6', './assets/app.js?v=6',
  './assets/icon.svg', './assets/manifest.webmanifest', './assets/manifest.en.webmanifest',
];

self.addEventListener('install', e => {
  e.waitUntil(
    // Un fichier absent (site servi sans la version anglaise, par exemple) ne doit
    // pas faire echouer toute l'installation : on met en cache ce qui repond.
    caches.open(SHELL)
      .then(c => Promise.all(ASSETS.map(u =>
        c.add(new Request(u, { cache: 'reload' })).catch(() => {}))))
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
  /* Fonds de carte et orthophotos IGN : immuables, et c'est ce qui rend une
     fiche déjà consultée lisible hors-ligne. */
  if (url.host === 'unpkg.com' || url.host.endsWith('tile.openstreetmap.org')
      || url.host === 'data.geopf.fr') {
    return e.respondWith(cacheFirst(request, MEDIA));
  }
  if (url.pathname.endsWith('/data/tracks.json')) {
    return e.respondWith(networkFirst(request, DATA));
  }
  if (url.origin === location.origin) {
    return e.respondWith(networkFirst(request, SHELL));
  }
});
