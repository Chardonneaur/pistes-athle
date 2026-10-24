/* Cache hors-ligne.
 *
 * Règle : le code de l'application passe TOUJOURS par le réseau en premier,
 * le cache ne sert que de filet hors-ligne. Sans cela, une version installée
 * continue de s'exécuter indéfiniment et les mises à jour restent invisibles.
 * Seuls les contenus immuables (photos, librairies versionnées) sont servis
 * depuis le cache en priorité.
 */
const VERSION = 'v19';
const SHELL = `shell-${VERSION}`;
const DATA = `data-${VERSION}`;
const MEDIA = 'media';                       // photos : jamais modifiées, jamais purgées
// Fonds de carte et orthophotos : servis par d'autres domaines, donc soumis au
// piège des réponses opaques (voir distant()). Cache à part et versionné, pour
// qu'une erreur mise en cache par une version précédente puisse être jetée.
const CARTES = 'cartes-v1';
const ASSETS = [
  './', './index.html', './en/', './en/index.html',
  './assets/style.css?v=14', './assets/i18n.js?v=15', './assets/app.js?v=16',
  './assets/matomo.js?v=3',
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
        keys.filter(k => k !== SHELL && k !== DATA && k !== MEDIA && k !== CARTES)
            .map(k => caches.delete(k))))
      // `media` n'est jamais purgé, et il a hébergé les orthophotos jusqu'à la
      // v18 : les réponses opaques erronées qu'il a pu avaler y sont encore, et
      // resteraient servies à vie. On l'ampute de tout ce qui n'est pas à nous,
      // une fois ; les photos, elles, sont sur notre domaine et ne bougent pas.
      .then(() => caches.open(MEDIA).then(c => c.keys().then(reqs =>
        Promise.all(reqs
          .filter(r => new URL(r.url).origin !== location.origin)
          .map(r => c.delete(r))))))
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

/** Images d'un autre domaine : cache d'abord, mais on vérifie avant de garder.
 *
 * Le piège : une image tierce demandée par <img> part en `no-cors` et revient
 * « opaque ». Une réponse opaque a un statut 0 et un corps illisible — on ne
 * peut pas distinguer l'orthophoto du message d'erreur. Or l'IGN répond 400
 * avec un ServiceExceptionReport en XML quand une requête échoue. Mise en
 * cache telle quelle par une stratégie « cache d'abord », cette erreur était
 * resservie indéfiniment : l'image restait cassée, et recharger n'y changeait
 * rien.
 *
 * data.geopf.fr et les tuiles OSM envoient tous deux `access-control-allow-
 * origin: *`. On redemande donc en `cors`, ce qui rend le statut lisible, et
 * on ne garde que ce qui est une image et qui a repondu 200. Le reste est
 * renvoyé au navigateur sans être mémorisé — au pire l'image manque
 * aujourd'hui et revient au prochain chargement. */
function distant(request, cacheName) {
  return caches.match(request).then(hit => {
    if (hit) return hit;
    return fetch(new Request(request.url, { mode: 'cors', credentials: 'omit' }))
      .then(res => {
        const type = res.headers.get('content-type') || '';
        if (res.ok && type.startsWith('image/')) {
          const copy = res.clone();
          caches.open(cacheName).then(c => c.put(request, copy));
        }
        return res;
      })
      // Le CORS refuse, le réseau tombe : on laisse le navigateur faire sa
      // requête habituelle plutôt que de rejeter et de casser l'image.
      .catch(() => fetch(request));
  });
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
  if (url.host.endsWith('tile.openstreetmap.org') || url.host === 'data.geopf.fr') {
    return e.respondWith(distant(request, CARTES));
  }
  /* Leaflet est chargé à la demande, à la première carte ouverte. Servi depuis
     le cache dès la deuxième : c'est une bibliothèque figée, et la mettre à
     jour se fait en changeant son chemin, pas en attendant le réseau. */
  if (url.pathname.includes('/assets/vendor/')) {
    return e.respondWith(cacheFirst(request, MEDIA));
  }
  if (url.pathname.endsWith('/data/tracks.json')) {
    return e.respondWith(networkFirst(request, DATA));
  }
  if (url.origin === location.origin) {
    return e.respondWith(networkFirst(request, SHELL));
  }
});
