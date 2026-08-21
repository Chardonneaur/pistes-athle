/* Où s'entraîner ? — annuaire des pistes d'athlétisme françaises
   Données : Recensement des équipements sportifs (Data ES) — Licence Ouverte 2.0
   + contributions communautaires (data/overrides/). */
(() => {
'use strict';

/* ------------------------------------------------------------------ config */
// Version de l'application. À incrémenter à chaque déploiement du code :
// scripts/build_data.py la recopie dans tracks.json, ce qui permet à un
// navigateur exécutant une version périmée de s'en rendre compte tout seul.
const APP_VERSION = '9';

// Laisser vide pour une détection automatique depuis l'URL *.github.io.
const REPO_OVERRIDE = '';

const REPO = (() => {
  if (REPO_OVERRIDE) return REPO_OVERRIDE;
  const m = location.hostname.match(/^([\w-]+)\.github\.io$/);
  if (!m) return 'Chardonneaur/pistes-athle';
  const seg = location.pathname.split('/').filter(Boolean)[0];
  return seg ? `${m[1]}/${seg}` : `${m[1]}/${m[1]}.github.io`;
})();
const ISSUE = (tpl, params) =>
  `https://github.com/${REPO}/issues/new?` +
  new URLSearchParams({ template: tpl, ...params }).toString();

/* Tout le monde n'a pas de compte GitHub : une contribution peut aussi partir
   par e-mail. L'adresse est assemblée à l'exécution et n'apparaît donc nulle
   part en clair dans le HTML, où les robots collecteurs viendraient la lire. */
const CONTACT = ['ronanchardonneau', 'gmail.com'];
const SUJET = '[Piste]';                    // préfixe : un filtre suffit à trier

/* Le jour où le volume justifie un vrai service de formulaire, il suffira de
   renseigner cette URL : envoyerContribution() postera au lieu d'ouvrir le
   client mail, sans rien changer au formulaire ni aux appels. */
const ENVOI_ENDPOINT = '';

/* ------------------------------------------------------------- libellés */
/* Tout le texte visible vient de assets/i18n.js, choisi d'après <html lang>. */
const DICO = window.I18N;
const LANG = window.I18N_LANG;
const U = DICO.ui;
/* Depuis /en/ les données et les photos sont un cran plus haut dans l'arborescence. */
const BASE = window.I18N_BASE;

// Une page HTML par site est publiée au déploiement : /site/<id>/ en français,
// /en/track/<id>/ en anglais. C'est elle que voient les moteurs et les agents IA.
const FICHES = BASE + (LANG === 'en' ? 'en/track/' : 'site/');
// Page statique qui liste tous les contributeurs et toutes leurs contributions.
const PAGE_CONTRIB = LANG === 'en' ? 'en/contributors/' : 'contributeurs/';

const V = DICO.vitrine;
const SOL = DICO.sol;
const AGRES = DICO.agres;
const SOURCES = DICO.sources;
const ORDRE_AGRES = ['steeple', 'longueur', 'triple', 'hauteur', 'perche',
                     'poids', 'disque', 'marteau', 'javelot'];
const trier = list => [...list].sort((a, b) => ORDRE_AGRES.indexOf(a) - ORDRE_AGRES.indexOf(b));

const FILTERS = [
  { id: 'near',   test: null },
  { id: 'piste',  test: t => t.piste },
  { id: 'synth',  test: t => t.surface === 'synthetique' },
  { id: 'libre',  test: t => t.acces_libre },
  { id: 'perche', test: t => has(t, 'perche') },
  { id: 'long',   test: t => has(t, 'longueur') || has(t, 'triple') },
  { id: 'haut',   test: t => has(t, 'hauteur') },
  { id: 'poids',  test: t => has(t, 'poids') },
  { id: 'lancer', test: t => ['disque','marteau','javelot'].some(a => has(t, a)) },
  { id: 'sauts',  test: t => t.nb_sautoirs > 0 },
  { id: 'ecl',    test: t => t.eclairage },
  { id: 'couv',   test: t => t.couvert },
  { id: 'vest',   test: t => t.vestiaires },
  { id: 'noeco',  test: t => !t.scolaire },
  { id: 'photo',  test: t => t.photos.length > 0 },
  { id: 'avis',   test: t => t.avis.length > 0 },
].map(f => ({ ...f, label: DICO.filtres[f.id] }));

const has = (t, a) => t.agres.includes(a);

/* ------------------------------------------------------------------ état */
const state = { all: [], deps: {}, shown: [], limit: 40, active: new Set(['piste']),
                q: '', dep: '', me: null, openId: null, contrib: null, map: null,
                mini: null, cluster: null, mapReady: false, communaute: null, lp: '' };

/* Developpement de l'anneau : le tour de piste. Une puce « 400 m » ne servait
   que les grands stades ; on cherche aussi un 250 m pres de chez soi, et la
   plupart des sites n'ont aucun developpement declare — d'ou `lpp`, estime
   d'apres OpenStreetMap. Le filtre accepte l'un ou l'autre. */
const DEVELOPPEMENTS = [400, 333, 300, 250, 200];

/* Code de `source` d'un site créé par la communauté (build_data.SOURCE_CODES) :
   le ministère ne le connaît pas du tout. */
const SOURCE_COMMUNAUTE = 2;
const tourDePiste = t => t.longueur_piste || t.longueur_probable || null;

const $ = s => document.querySelector(s);
const norm = s => (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));

function distance(a, b, c, d) {                     // haversine, km
  const R = 6371, r = Math.PI / 180;
  const dLat = (c - a) * r, dLon = (d - b) * r;
  const h = Math.sin(dLat/2)**2 + Math.cos(a*r) * Math.cos(c*r) * Math.sin(dLon/2)**2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
const fmtDate = iso => {
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString(DICO.locale, { day: 'numeric', month: 'long', year: 'numeric' });
};
const fmtNote = n => n.toFixed(1).replace('.', LANG === 'fr' ? ',' : '.');
const fmtDist = km => km < 1 ? `${Math.round(km * 1000)} m`
                    : km < 10 ? `${km.toFixed(1)} km` : `${Math.round(km)} km`;

/* ------------------------------------------------- réparation d'un cache périmé
   tracks.json passe toujours par le réseau : c'est notre canal de vérité.
   S'il annonce une version d'application différente de celle qui s'exécute,
   c'est qu'un ancien cache sert du vieux code. On purge et on recharge. */
async function reparerCachePerime(version) {
  if (!version || version === APP_VERSION) return false;
  try {
    if (sessionStorage.getItem('reparation') === version) return false;  // déjà tenté
    sessionStorage.setItem('reparation', version);
  } catch (e) { /* stockage indisponible : on tente quand même une fois */ }
  console.warn(`Version ${APP_VERSION} périmée (serveur : ${version}) — purge du cache.`);
  try {
    if (self.caches) await Promise.all((await caches.keys()).map(k => caches.delete(k)));
    if (navigator.serviceWorker) {
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map(r => r.unregister()));
    }
  } catch (e) { console.error(e); }
  location.reload();
  return true;
}

/* --------------------------------------------------------------- données */
async function load() {
  const res = await fetch(BASE + 'data/tracks.json', { cache: 'no-cache' });
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const raw = await res.json();
  if (await reparerCachePerime(raw.app_version)) return;
  const map = raw.keymap;
  state.deps = raw.deps || {};
  state.communaute = raw.communaute || null;
  state.all = raw.tracks.map(rec => {
    const t = {};
    for (const k in rec) t[map[k] || k] = rec[k];
    for (const b of ['piste','couvert','eclairage','acces_libre','ouvert_public',
                     'vestiaires','douches','sanitaires','scolaire'])
      t[b] = !!t[b];
    t.agres = t.agres || [];
    t.agres_probables = t.agres_probables || [];
    t.photos = t.photos || [];
    t.avis = t.avis || [];
    t.nb_sautoirs = t.nb_sautoirs || 0;
    t.nb_aires_lancer = t.nb_aires_lancer || 0;
    const d = state.deps[t.dep] || [];
    t.dep_nom = d[0] || ''; t.region = d[1] || '';
    t._s = norm([t.nom, t.ville, t.cp, t.dep_nom, t.dep].join(' '));
    return t;
  });
  $('#loader').hidden = true;
  remplirDepartements();
  renderVitrine();
  document.title = U.titre_compte(state.all.length);
  apply();
  readHash();
}

/* Plus le score est bas, plus le site est pertinent pour la recherche saisie. */
function pertinence(t, q, words) {
  const ville = norm(t.ville);
  const nom = norm(t.nom);
  if (ville === q) return 0;                              // « pornic »
  if (t.cp === q) return 1;                               // « 44210 »
  if (ville.startsWith(q)) return 2;                      // « porni »
  if (nom.includes(q)) return 3;                          // « val saint martin »
  if (ville.includes(q)) return 4;
  if (words.every(w => nom.includes(w))) return 5;
  return 6;
}

/* -------------------------------------------------------------- filtrage */
function apply() {
  const q = norm(state.q).trim();
  const words = q ? q.split(/\s+/) : [];
  const tests = FILTERS.filter(f => f.test && state.active.has(f.id)).map(f => f.test);

  let out = state.all.filter(t => {
    if (state.dep && t.dep !== state.dep) return false;
    if (state.lp && tourDePiste(t) !== Number(state.lp)) return false;
    for (const fn of tests) if (!fn(t)) return false;
    for (const w of words) if (!t._s.includes(w)) return false;
    return true;
  });

  if (state.me) {
    for (const t of out) t._d = distance(state.me.lat, state.me.lon, t.lat, t.lon);
    out.sort((a, b) => a._d - b._d);
    if (state.active.has('near')) out = out.filter(t => t._d <= 30);
  } else if (q) {
    // Une recherche par commune doit faire remonter la commune, pas l'ordre
    // alphabétique : « val saint martin » doit donner Pornic avant Cergy.
    for (const t of out) t._r = pertinence(t, q, words);
    out.sort((a, b) => a._r - b._r ||
      (a.ville || '').localeCompare(b.ville || '', DICO.locale) ||
      (a.nom || '').localeCompare(b.nom || '', DICO.locale));
  } else {
    out.sort((a, b) => (a.ville || '').localeCompare(b.ville || '', DICO.locale));
  }

  state.shown = out;
  state.limit = 40;
  $('#count').textContent = out.length ? U.nb_sites(out.length) : U.aucun;
  renderList();
  renderVitrine();
  if (state.mapReady) renderMap();
}

/* ----------------------------------------------------------------- liste */
function tagsOf(t) {
  const tags = [];
  if (t.surface) {
    const [lab, cls] = SOL[t.surface] || [t.surface, ''];
    tags.push(`<span class="tag sol ${cls}">${esc(lab)}</span>`);
  }
  const tour = tourDePiste(t);
  if (tour) {
    const sur = !t.longueur_piste;            // valeur estimee, pas declaree
    tags.push(`<span class="tag${sur ? ' maybe' : ''}"${sur ? ` title="${esc(U.lp_estime)}"` : ''}>` +
              `${tour} m${sur ? ' ?' : ''}${t.couloirs ? ` · ${DICO.tags.couloirs(t.couloirs)}` : ''}</span>`);
  }
  else if (t.couloirs) tags.push(`<span class="tag">${DICO.tags.couloirs(t.couloirs)}</span>`);
  if (t.acces_libre) tags.push(`<span class="tag free">${DICO.tags.acces_libre}</span>`);
  if (t.couvert) tags.push(`<span class="tag">${DICO.tags.couverte}</span>`);
  for (const a of trier(t.agres)) tags.push(`<span class="tag">${esc(AGRES[a] || a)}</span>`);
  if (!t.agres.length) {
    if (t.nb_sautoirs) tags.push(`<span class="tag maybe">${DICO.tags.sautoirs(t.nb_sautoirs)}</span>`);
    if (t.nb_aires_lancer) tags.push(`<span class="tag maybe">${DICO.tags.lancers(t.nb_aires_lancer)}</span>`);
  }
  if (t.scolaire) tags.push(`<span class="tag">${DICO.tags.scolaire}</span>`);
  return tags.join('');
}

function stars(n) {
  const full = Math.round(n);
  return `<span class="stars" aria-label="${esc(U.note_sur_5(n))}">${'★'.repeat(full)}${'☆'.repeat(5 - full)}</span>`;
}

/* Vue aérienne (orthophoto IGN, Licence Ouverte 2.0).
 *
 * L'image est servie en direct par la Géoplateforme : rien n'est stocké ici.
 * Stocker une vignette pour chacune des 6 500 pistes pèserait des centaines de
 * mégaoctets, ce qu'un dépôt GitHub Pages ne peut pas porter — et l'application
 * cesserait d'être installable.
 *
 * Ce n'est PAS une photo du site : une orthophoto a souvent plusieurs années et
 * ne dit rien de l'état des agrès (les tapis de perche et de hauteur sont bâchés
 * ou rentrés, un bac de sable envahi ne se distingue plus du sol). Elle montre
 * l'implantation — anneau, couloirs, revêtement — et rien de plus.
 */
const IGN_WMS = 'https://data.geopf.fr/wms-r/wms';

function vueAerienne(t, largeur = 960) {
  if (typeof t.lat !== 'number' || typeof t.lon !== 'number') return null;
  const hauteur = Math.round(largeur * 9 / 16);
  /* Cadrage : un anneau de 400 m tient dans 360 m de champ ; une petite piste
     se contente de moins, sans quoi elle se perd au milieu de l'image. */
  const tour = tourDePiste(t);
  const champ = tour >= 400 ? 360 : (tour ? 260 : 300);
  const dlat = (champ * hauteur / largeur) / 2 / 111132;
  const dlon = champ / 2 / (111320 * Math.cos(t.lat * Math.PI / 180));
  const bbox = [t.lat - dlat, t.lon - dlon, t.lat + dlat, t.lon + dlon].join(',');
  return `${IGN_WMS}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap` +
         '&LAYERS=HR.ORTHOIMAGERY.ORTHOPHOTOS&STYLES=&CRS=EPSG:4326' +
         `&BBOX=${bbox}&WIDTH=${largeur}&HEIGHT=${hauteur}&FORMAT=image/jpeg`;
}

/* --------------------------------------------------- vitrine d'accueil
   Les dernières contributions, le classement des contributeurs et l'appel à
   contribuer. Les deux premiers blocs sont calculés à la construction du jeu
   de données (scripts/build_data.py) : le navigateur n'a qu'à les afficher.

   L'encart ne s'affiche qu'en vue neutre. Dès qu'une recherche, un filtre ou
   un département est actif, l'utilisateur a posé une question : la réponse
   doit arriver en haut de l'écran, pas sous une vitrine. */
const VITRINE_MAX = 3;

function vitrineVisible() {
  const filtresParDefaut = state.active.size === 1 && state.active.has('piste');
  return !state.q.trim() && !state.dep && !state.lp && filtresParDefaut;
}

function carteContribution(c) {
  const t = state.all.find(x => x.id === c.i);
  if (!t || !t.photos.length) return '';
  const p = t.photos[0];
  const auteur = p.c || (t.avis[0] && t.avis[0].a) || '';
  const lieu = [t.ville, t.dep && `(${t.dep})`].filter(Boolean).join(' ');
  return `
    <a class="vit-card" href="${esc(FICHES + t.id + '/')}" data-site="${esc(t.id)}">
      <img loading="lazy" src="${esc(BASE + (p.t || p.f))}"
           alt="${esc(p.l || t.nom)}" width="480" height="270">
      <span class="vit-body">
        <strong>${esc(t.nom || U.sans_nom)}</strong>
        <span class="loc">${esc(lieu)}</span>
        <span class="meta">${esc(V.photos(t.photos.length))}${
          auteur ? ' · ' + esc(V.par(auteur)) : ''}</span>
      </span>
    </a>`;
}

function carteContributeur(c, rang) {
  const detail = [V.top_sites(c.s), c.p && V.top_photos(c.p), c.a && V.top_avis(c.a)]
                 .filter(Boolean).join(' · ');
  return `
    <li class="vit-top">
      <span class="rang" aria-hidden="true">${rang}</span>
      <span class="qui"><strong>${esc(c.n)}</strong><span class="meta">${esc(detail)}</span></span>
    </li>`;
}

function renderVitrine() {
  const el = $('#vitrine');
  if (!el) return;
  const c = state.communaute;
  if (!c || !vitrineVisible()) { el.hidden = true; return; }

  const cartes = (c.recentes || []).map(carteContribution).filter(Boolean).slice(0, VITRINE_MAX);
  const top = (c.top || []).slice(0, VITRINE_MAX);

  el.innerHTML = `
    ${cartes.length ? `
      <h2 id="vitrine-titre">${esc(V.titre)}</h2>
      <p class="vit-intro">${esc(V.intro)}</p>
      <div class="vit-grid">${cartes.join('')}</div>`
    : `<h2 id="vitrine-titre" class="sr-only">${esc(V.cta_titre)}</h2>`}

    ${top.length ? `
      <h2>${esc(V.top_titre)}</h2>
      <p class="vit-intro">${esc(V.top_intro)}</p>
      <ol class="vit-tops">${top.map((x, i) => carteContributeur(x, i + 1)).join('')}</ol>
      <p class="vit-plus"><a href="${esc(BASE + PAGE_CONTRIB)}">${esc(V.top_lien)} →</a></p>` : ''}

    <div class="vit-cta">
      <strong>${esc(V.cta_titre)}</strong>
      <p>${esc(V.cta_texte)}</p>
      <button class="btn primary" type="button" data-contrib="avis">${esc(V.cta_bouton)}</button>
      <span class="src">${esc(V.cta_aide)}</span>
    </div>`;
  el.hidden = false;
}

function renderList() {
  const list = state.shown.slice(0, state.limit);
  $('#results').innerHTML = list.map(t => {
    const vignette = t.photos[0];
    return `
    <li class="card${vignette ? ' has-photo' : ''}" data-id="${esc(t.id)}">
      <div class="card-main">
        <div class="card-top">
          <h2>${esc(t.nom || U.sans_nom)}</h2>
          ${t._d != null ? `<span class="dist">${fmtDist(t._d)}</span>` : ''}
        </div>
        <p class="loc">${esc([t.ville, t.dep && `(${t.dep})`].filter(Boolean).join(' '))}</p>
        ${t.note_moyenne ? `<p class="rating">${stars(t.note_moyenne)}
           <span>${fmtNote(t.note_moyenne)} · ${U.nb_avis(t.nb_avis)}</span></p>` : ''}
        <div class="tags">${tagsOf(t)}</div>
      </div>
      ${vignette ? `<img class="thumb" loading="lazy" src="${esc(BASE + (vignette.t || vignette.f))}"
         alt="${esc(vignette.l || t.nom)}">` : ''}
    </li>`;
  }).join('');
  $('#more').hidden = state.shown.length <= state.limit;
  $('#empty').hidden = state.shown.length > 0;
}

/* ----------------------------------------------------------------- carte */
function pinColor(t) {
  if (t.surface === 'synthetique') return '#0d7d5a';
  if (t.surface === 'cendree') return '#b45309';
  if (t.surface === 'bitume') return '#475569';
  return '#c2410c';
}

const fondOSM = () => L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
});

function initMap() {
  state.map = L.map('map', { zoomControl: false, tap: false })
              .setView(state.me ? [state.me.lat, state.me.lon] : [46.7, 2.4],
                       state.me ? 11 : 5);
  L.control.zoom({ position: 'bottomright' }).addTo(state.map);
  fondOSM().addTo(state.map);
  state.cluster = L.markerClusterGroup({
    maxClusterRadius: 55,
    chunkedLoading: true,
    showCoverageOnHover: false,
    iconCreateFunction(c) {
      const n = c.getChildCount();
      const size = n < 10 ? 32 : n < 100 ? 38 : n < 1000 ? 44 : 50;
      return L.divIcon({
        html: `<div class="cluster"><span>${n}</span></div>`,
        className: '', iconSize: [size, size],
      });
    },
  });
  state.map.addLayer(state.cluster);
  state.mapReady = true;
  renderMap();
}

function renderMap() {
  state.cluster.clearLayers();
  const markers = state.shown.map(t =>
    L.marker([t.lat, t.lon], {
      icon: L.divIcon({
        className: '',
        html: `<div class="pin" style="width:14px;height:14px;background:${pinColor(t)}"></div>`,
        iconSize: [14, 14], iconAnchor: [7, 7],
      }),
      title: t.nom,
    }).on('click', () => openSheet(t.id)));
  state.cluster.addLayers(markers);
  if (state.me) {
    L.circleMarker([state.me.lat, state.me.lon], {
      radius: 7, color: '#fff', weight: 2, fillColor: '#2563eb', fillOpacity: 1,
    }).addTo(state.cluster);
  }
}

/* ------------------------------------------------------------ fiche site */
function kv(label, value) {
  return value == null || value === '' ? ''
    : `<div class="kv"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`;
}

function openSheet(id) {
  const t = state.all.find(x => x.id === id);
  if (!t) return;
  state.openId = id;
  const sol = t.surface ? (SOL[t.surface] || [t.surface])[0] : null;
  const gmaps = `https://www.google.com/maps/dir/?api=1&destination=${t.lat},${t.lon}`;
  /* Les horaires ne sont dans aucune donnee ouverte : ni le recensement du
     ministere, qui n'a pas le champ, ni OpenStreetMap, ou aucune piste n'est
     renseignee. Ils existent en revanche sur les fiches Google des equipements.
     On y renvoie plutot que de les recopier : les conditions de Google
     interdisent de stocker et de redistribuer ce contenu, et le lien a
     l'avantage d'etre toujours a jour. */
  const gplace = 'https://www.google.com/maps/search/?api=1&query=' +
    encodeURIComponent([t.nom, t.ville, t.cp].filter(Boolean).join(' '));

  const agres = [
    ...trier(t.agres).map(a => `<span>${esc(AGRES[a] || a)}</span>`),
    ...t.agres_probables.map(a => `<span class="maybe">${esc(AGRES[a] || a)}</span>`),
  ].join('');

  const galerie = t.photos.length ? `
    <div class="gallery" role="group" aria-label="${esc(U.photos_du_site)}">
      ${t.photos.map((p, i) => `
        <figure><img loading="${i ? 'lazy' : 'eager'}" src="${esc(BASE + p.f)}"
             alt="${esc(p.l || t.nom)}" data-full="${esc(BASE + p.f)}">
          ${p.l ? `<figcaption>${esc(p.l)}${p.c ? ` <span>© ${esc(p.c)}</span>` : ''}</figcaption>` : ''}
        </figure>`).join('')}
    </div>` : '';

  /* À défaut de photo de terrain, on montre au moins l'implantation vue du ciel.
     Le bloc reste distinct de la galerie : une orthophoto n'est pas le témoignage
     de quelqu'un qui est allé courir là. */
  /* Un site que le ministère ne connaît pas n'a pas de cases à cocher : ses
     booléens valent faux faute de saisie, pas par déclaration. Écrire « Non »
     ferait passer un blanc pour un constat — on se tait, et la ligne revient
     dès qu'un contributeur remplit le champ. */
  const declare = t.source !== SOURCE_COMMUNAUTE;
  const ouiNon = actif => actif ? U.oui : (declare ? U.non : null);

  const acces = [
    kv(U.kv_acces_libre, t.acces_libre ? U.oui
        : (t.ouvert_public ? U.ouvert_horaires : (declare ? U.non_reserve : null))),
    kv(U.kv_eclairage, ouiNon(t.eclairage)),
    kv(U.kv_vestiaires, ouiNon(t.vestiaires)),
    kv(U.kv_douches, ouiNon(t.douches)),
    kv(U.kv_sanitaires, ouiNon(t.sanitaires)),
    kv(U.kv_tribunes, t.tribunes ? U.places(t.tribunes) : null),
    t.scolaire ? kv(U.kv_type_site, U.enceinte_scolaire) : '',
    kv(U.kv_horaires, t.horaires),
  ].join('');

  const aerienneUrl = t.photos.length ? null : vueAerienne(t);
  const anneeOrtho = (state.deps[t.dep] || [])[2];
  const aerienne = aerienneUrl ? `
    <figure class="aerial">
      <img loading="lazy" src="${esc(aerienneUrl)}" alt="${esc(U.aerienne_alt(t.nom || U.sans_nom))}">
      <figcaption>${esc(anneeOrtho ? U.aerienne_legende_datee(anneeOrtho) : U.aerienne_legende)}
        <span>${esc(U.aerienne_credit)}</span></figcaption>
    </figure>` : '';

  const avis = `
    <div class="sec">${esc(U.sec_avis)}${t.nb_avis ? ` (${t.nb_avis})` : ''}</div>
    ${t.avis.length ? t.avis.map(a => `
      <article class="avis">
        <header>
          ${a.n ? stars(a.n) : ''}
          <strong>${esc(a.a || U.anonyme)}</strong>
          ${a.d ? `<time datetime="${esc(a.d)}">${fmtDate(a.d)}</time>` : ''}
        </header>
        <p>${esc(a.t)}</p>
      </article>`).join('')
    : `<p class="vide">${U.pas_davis}</p>`}
    <button class="btn" type="button" style="margin-top:10px" data-contrib="avis">
       ${esc(U.donner_avis)}</button>`;

  $('#sheet-body').innerHTML = `
    <h2>${esc(t.nom || U.sans_nom)}</h2>
    <p class="loc">${esc([t.adresse, [t.cp, t.ville].filter(Boolean).join(' ')].filter(Boolean).join(', '))}${t.dep_nom ? ` · ${esc(t.dep_nom)}` : ''}</p>
    ${t.note_moyenne ? `<p class="rating big">${stars(t.note_moyenne)}
       <span>${esc(U.note_sur_5(fmtNote(t.note_moyenne)))} · ${esc(U.nb_avis(t.nb_avis))}</span></p>` : ''}

    ${galerie}
    ${aerienne}

    <div class="actions">
      <a class="btn primary" href="${gmaps}" target="_blank" rel="noopener">${esc(U.itineraire)}</a>
      <button class="btn" type="button" id="btn-minimap">${esc(U.voir_carte)}</button>
      <a class="btn" href="${gplace}" target="_blank" rel="nofollow noopener">${esc(U.horaires_google)}</a>
    </div>
    <div id="minimap" class="minimap" hidden></div>

    <div class="sec">${esc(U.sec_piste)}</div>
    <div class="grid">
      ${kv(U.kv_revetement, sol)}
      ${kv(U.kv_developpement, t.longueur_piste ? t.longueur_piste + ' m'
            : (t.longueur_probable ? `${t.longueur_probable} m — ${U.lp_estime}` : null))}
      ${kv(U.kv_couloirs, t.couloirs)}
      ${kv(U.kv_config, t.couvert ? U.kv_couverte : (t.piste ? U.kv_plein_air : null))}
      ${kv(U.kv_service, t.annee)}
      ${kv(U.kv_renovation, t.renovation)}
    </div>

    ${agres ? `<div class="sec">${esc(U.sec_agres)}</div><div class="eq">${agres}</div>` : ''}
    ${t.agres_probables.length ? `<p class="src">${U.incertain}</p>` : ''}

    ${acces ? `<div class="sec">${esc(U.sec_acces)}</div><div class="grid">${acces}</div>` : ''}
    ${t.acces_note ? `<p class="note">${esc(t.acces_note)}</p>` : ''}
    ${avis}
    ${t.note ? `<p class="note">${esc(t.note)}</p>` : ''}
    ${t.url ? `<p><a href="${esc(t.url)}" target="_blank" rel="noopener">${esc(U.site_officiel)}</a></p>` : ''}

    <div class="actions" style="margin-top:18px">
      <button class="btn" type="button" data-contrib="correction">${esc(U.signaler)}</button>
      <button class="btn" type="button" data-contrib="complement">${esc(U.completer)}</button>
    </div>

    <p class="src"><a href="${FICHES}${esc(t.id)}/">${esc(U.page_dediee)}</a><br>
      ${U.reference(esc(t.id), esc(SOURCES[t.source] || SOURCES[0]))}</p>`;

  /* Hors couverture IGN, ou service indisponible : on retire le bloc plutôt que
     de laisser une image cassée sous le nom du stade. */
  const imgAerienne = $('#sheet-body .aerial img');
  if (imgAerienne) imgAerienne.addEventListener('error', () => {
    const fig = imgAerienne.closest('.aerial');
    if (fig) fig.remove();
  });

  $('#sheet').hidden = false;
  document.body.style.overflow = 'hidden';
  setHash();
}

function closeSheet() {
  destroyMiniMap();
  state.openId = null;
  state.contrib = null;
  $('#sheet').hidden = true;
  document.body.style.overflow = '';
  if (location.hash.includes('site=')) history.replaceState(null, '', location.pathname + location.search);
}

/* Liens partageables : #carte, #dep=44, #q=pornic, #site=I352380090 */
function setHash() {
  const id = state.openId;
  const parts = [];
  if ($('#view-map').classList.contains('is-active')) parts.push('carte');
  if (state.dep) parts.push('dep=' + encodeURIComponent(state.dep));
  if (state.lp) parts.push('lp=' + encodeURIComponent(state.lp));
  if (state.q.trim()) parts.push('q=' + encodeURIComponent(state.q.trim()));
  if (id) parts.push('site=' + id);
  history.replaceState(null, '', parts.length ? '#' + parts.join('&') : location.pathname);
}

function readHash() {
  const h = new URLSearchParams(location.hash.replace(/^#/, '').replace(/&/g, '&'));
  if (location.hash.includes('carte')) switchView('map');
  let filtre = false;
  const dep = h.get('dep');
  if (dep) { state.dep = dep; afficherDep(); filtre = true; }
  const lp = h.get('lp');
  if (lp && DEVELOPPEMENTS.includes(Number(lp))) {
    state.lp = String(Number(lp));
    const sel = $('#lp'); if (sel) sel.value = state.lp;
    filtre = true;
  }
  const q = h.get('q');
  if (q) { state.q = q; $('#q').value = q; $('#q-clear').hidden = false; filtre = true; }
  if (filtre) { apply(); cadrerSurResultats(); }
  const id = h.get('site');
  if (id) return openSheet(id);
  /* #contribuer ouvre le formulaire sans passer par une fiche : c'est le lien
     donné aux contributeurs sans compte GitHub, depuis le dépôt notamment. */
  if (h.has('contribuer')) ouvrirContribution(h.get('contribuer') || 'correction', null);
}

function destroyMiniMap() {
  if (state.mini) { state.mini.remove(); state.mini = null; }
}

function toggleMiniMap() {
  const box = $('#minimap');
  const btn = $('#btn-minimap');
  const t = state.all.find(x => x.id === state.openId);
  if (!box || !btn || !t) return;

  if (!box.hidden) {                                  // deja ouverte : on replie
    destroyMiniMap();
    box.hidden = true;
    box.innerHTML = '';
    btn.textContent = U.voir_carte;
    return;
  }

  box.hidden = false;
  btn.textContent = U.masquer_carte;
  box.innerHTML = '<div class="minimap-canvas"></div>' +
    `<button type="button" class="minimap-full" data-full-map>${esc(U.plein_ecran)}</button>`;

  destroyMiniMap();
  state.mini = L.map(box.querySelector('.minimap-canvas'), {
    zoomControl: true, scrollWheelZoom: false, dragging: true,
  }).setView([t.lat, t.lon], 17);
  fondOSM().addTo(state.mini);
  L.marker([t.lat, t.lon], {
    icon: L.divIcon({
      className: '',
      html: `<div class="pin pin-big" style="background:${pinColor(t)}"></div>`,
      iconSize: [20, 20], iconAnchor: [10, 10],
    }),
    keyboard: false,
  }).addTo(state.mini);

  setTimeout(() => {
    state.mini.invalidateSize();
    box.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 60);
}

function showOnFullMap() {
  const t = state.all.find(x => x.id === state.openId);
  closeSheet();
  switchView('map');
  if (t) state.map.setView([t.lat, t.lon], 17);
}

function openPhoto(src, alt) {
  const v = document.createElement('div');
  v.className = 'viewer';
  v.innerHTML = `<img src="${esc(src)}" alt="${esc(alt)}"><button aria-label="Fermer">×</button>`;
  v.addEventListener('click', () => v.remove());
  document.body.appendChild(v);
}

/* ------------------------------------------------------- contribution */
const TYPES_CONTRIB = ['avis', 'correction', 'complement', 'ajout'];
const ETIQUETTE = { avis: 'Avis', correction: 'Correction',
                    complement: 'Complément', ajout: 'Ajout' };

function ouvrirContribution(type, t) {
  const C = DICO.contrib;
  if (!TYPES_CONTRIB.includes(type)) type = 'correction';
  state.contrib = { retour: t ? t.id : null, id: t ? t.id : '' };
  state.openId = null;
  const site = t ? [t.nom || U.sans_nom, t.ville].filter(Boolean).join(', ')
                   + (t.dep ? ` (${t.dep})` : '')
                 : '';

  $('#sheet-body').innerHTML = `
    <div class="contrib">
      ${t ? `<button class="retour" type="button" data-retour>${esc(C.retour)}</button>` : ''}
      <h2>${esc(C.titre)}</h2>
      <p class="intro">${esc(C.intro)}</p>

      <label class="champ"><span>${esc(C.type_label)}</span>
        <select id="c-type">${TYPES_CONTRIB.map(k =>
          `<option value="${k}"${k === type ? ' selected' : ''}>${esc(C.types[k])}</option>`).join('')}
        </select></label>

      <label class="champ"><span>${esc(C.site)}</span>
        <input id="c-site" type="text" value="${esc(site)}" placeholder="${esc(C.site_ph)}"></label>

      <label class="champ" id="c-note-champ"${type === 'avis' ? '' : ' hidden'}>
        <span>${esc(C.note)}</span>
        <select id="c-note"><option value="">${esc(C.note_vide)}</option>
          ${C.notes.map((l, i) => `<option value="${i + 1}">${esc(l)}</option>`).join('')}
        </select></label>

      <label class="champ"><span>${esc(C.message)}</span>
        <textarea id="c-message" rows="6" placeholder="${esc(C.message_ph[type])}"></textarea></label>

      <label class="champ"><span>${esc(C.signature)}</span>
        <input id="c-signature" type="text" placeholder="${esc(C.signature_ph)}"></label>

      <p class="src">${esc(C.photos)}</p>
      <p class="erreur" id="c-erreur" hidden></p>

      <div class="actions">
        <button class="btn primary" type="button" data-envoi="mail">${esc(C.mail)}</button>
        <button class="btn" type="button" data-envoi="github">${esc(C.github)}</button>
      </div>
      <p class="src aides"><span>${esc(C.mail_aide)}</span><span>${esc(C.github_aide)}</span></p>
      <p class="src">${esc(C.licence)}</p>
    </div>`;

  $('#sheet').hidden = false;
  document.body.style.overflow = 'hidden';
}

/* Le type choisi change l'exemple proposé et l'utilité de la note. */
function majTypeContribution() {
  const type = $('#c-type').value;
  $('#c-message').placeholder = DICO.contrib.message_ph[type] || '';
  $('#c-note-champ').hidden = type !== 'avis';
}

function lireContribution() {
  const C = DICO.contrib;
  const err = $('#c-erreur');
  const d = {
    type: $('#c-type').value,
    site: $('#c-site').value.trim(),
    note: $('#c-note-champ').hidden ? '' : $('#c-note').value,
    message: $('#c-message').value.trim(),
    signature: $('#c-signature').value.trim(),
    id: state.contrib ? state.contrib.id : '',
  };
  const souci = !d.site ? C.manque_site : !d.message ? C.manque : '';
  err.textContent = souci;
  err.hidden = !souci;
  if (souci) { (souci === C.manque_site ? $('#c-site') : $('#c-message')).focus(); return null; }
  return d;
}

/* Renvoie l'adresse publique de la fiche, pour que le message reçu mène au site. */
function lienFiche(id) {
  return id ? new URL(FICHES + id + '/', location.href).href : '';
}

function envoyerContribution(voie) {
  const d = lireContribution();
  if (!d) return;
  const C = DICO.contrib;
  const titre = `[${ETIQUETTE[d.type]}] ${d.site}`;

  if (voie === 'github') {
    const params = { title: titre, nom: d.site };
    if (d.id) params.id = d.id;
    if (d.type === 'avis') {
      params.avis = d.message;
      if (d.signature) params.pseudo = d.signature;
      if (d.note) params.note = d.note;
    } else if (d.type === 'correction') {
      params.erreur = d.message;
    } else {
      params.note = d.message;                 // « complement » et « ajout »
    }
    return window.open(ISSUE(`${d.type}.yml`, params), '_blank', 'noopener');
  }

  const corps = [
    `${C.type_label} : ${C.types[d.type]}`,
    `${C.site} : ${d.site}`,
    d.id ? `${U.reference_courte} ${d.id}` : '',
    d.note ? `${C.note} : ${d.note}/5` : '',
    d.signature ? `${C.signe} : ${d.signature}` : '',
    '',
    d.message,
    '',
    lienFiche(d.id),
  ].filter(Boolean).join('\n');

  /* Un lien cliqué plutôt qu'une navigation : la page reste en place si aucun
     client mail n'est configuré, et le brouillon s'ouvre à côté. */
  const lien = document.createElement('a');
  lien.href = `mailto:${CONTACT.join('@')}` +
    `?subject=${encodeURIComponent(`${SUJET}${titre}`)}` +
    `&body=${encodeURIComponent(corps)}`;
  lien.rel = 'noopener';
  lien.style.display = 'none';
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
}

/* ----------------------------------------------------------- à propos */
function openAbout() {
  state.openId = null;
  $('#sheet-body').innerHTML = DICO.about({ repo: REPO });
  $('#sheet').hidden = false;
  document.body.style.overflow = 'hidden';
}

/* -------------------------------------------------------- géolocalisation */
function geolocate() {
  if (!navigator.geolocation) return alert(U.geo_absente);
  const btn = $('#btn-geo');
  btn.disabled = true;
  navigator.geolocation.getCurrentPosition(pos => {
    btn.disabled = false;
    btn.classList.add('is-on');
    state.me = { lat: pos.coords.latitude, lon: pos.coords.longitude };
    if (state.mapReady) state.map.setView([state.me.lat, state.me.lon], 11);
    apply();
  }, err => {
    btn.disabled = false;
    alert(err.code === 1 ? U.geo_refusee : U.geo_echec);
  }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
}

/* -------------------------------------------------------------- interface */
function buildChips() {
  $('#chips').innerHTML =
    `<input id="dep" class="chip-select" list="dep-liste" type="text" autocomplete="off"
            size="12" placeholder="${esc(U.dep_ph)}" aria-label="${esc(U.dep_label)}">
     <datalist id="dep-liste"></datalist>
     <select id="lp" class="chip-select" aria-label="${esc(U.lp_label)}">
       <option value="">${esc(U.lp_tous)}</option>
       ${DEVELOPPEMENTS.map(m => `<option value="${m}">${esc(U.lp_option(m))}</option>`).join('')}
     </select>` +
    FILTERS.map(f =>
      `<button class="chip${state.active.has(f.id) ? ' is-on' : ''}" data-f="${f.id}">${f.label}</button>`
    ).join('');
}

/* 108 départements : un champ où l'on tape, avec suggestions. On y saisit le
   numéro (« 44 », « 01 », « 2A »), le nom, ou un code postal — plutôt qu'une
   puce par département qu'il faudrait faire défiler indéfiniment. */
const DEPS = [];

/* Les codes de Data ES ne sont pas zéropadés : l'Ain est « 1 ». On affiche
   « 01 » comme tout le monde, mais on compare sur la forme canonique. */
const codeCanon = v => {
  const s = String(v || '').trim().toUpperCase();
  return /^\d+$/.test(s) ? String(Number(s)) : s;
};
const codeAffiche = code => (/^\d$/.test(code) ? '0' + code : code);

function remplirDepartements() {
  const champ = $('#dep');
  if (!champ) return;
  const nb = {};
  for (const t of state.all) if (t.dep) nb[t.dep] = (nb[t.dep] || 0) + 1;

  DEPS.length = 0;
  for (const code in nb) {
    const [nom, region] = state.deps[code] || [code, ''];
    DEPS.push({ code, nom: nom || code, region: region || '', n: nb[code],
                libelle: `${codeAffiche(code)} · ${nom || code}` });
  }
  const cmp = (a, b) => a.localeCompare(b, DICO.locale);
  DEPS.sort((a, b) => cmp(a.region, b.region) || cmp(a.nom, b.nom));

  $('#dep-liste').innerHTML = DEPS.map(d =>
    `<option value="${esc(d.libelle)}">${esc(d.region)} · ${esc(U.nb_sites(d.n))}</option>`
  ).join('');
  afficherDep();
}

/* Remet dans le champ le libellé complet du département retenu. */
function afficherDep() {
  const champ = $('#dep');
  if (!champ) return;
  const d = DEPS.find(x => x.code === state.dep);
  champ.value = d ? d.libelle : '';
  champ.size = Math.max(12, champ.value.length + 1);   // la pastille suit le texte
  champ.classList.toggle('is-on', !!d);
}

/* Rend le code du département désigné par une saisie libre.
   '' = rien de saisi, null = saisie non reconnue (on ne touche à rien). */
function resoudreDep(saisie, avecCodePostal) {
  const brut = String(saisie || '').trim();
  if (!brut) return '';

  // « 44 · Loire-Atlantique (171) » : on ne garde que le numéro de tête
  const tete = codeCanon(brut.split('·')[0]);
  const parCode = DEPS.find(d => codeCanon(d.code) === tete);
  if (parCode) return parCode.code;

  if (avecCodePostal) {
    const chiffres = brut.replace(/\s/g, '');
    if (/^\d{5}$/.test(chiffres)) {                  // 44210 -> 44, 97400 -> 974
      const prefixe = chiffres.startsWith('97') ? chiffres.slice(0, 3) : chiffres.slice(0, 2);
      const trouve = DEPS.find(d => codeCanon(d.code) === codeCanon(prefixe));
      if (trouve) return trouve.code;
    }
  }

  const cle = norm(brut);
  const exact = DEPS.find(d => norm(d.nom) === cle || norm(d.libelle) === cle);
  if (exact) return exact.code;
  const debuts = DEPS.filter(d => norm(d.nom).startsWith(cle));
  return debuts.length === 1 ? debuts[0].code : null;
}

/* Applique un département et recadre la carte. */
function choisirDep(code) {
  if (code === state.dep) return false;
  state.dep = code;
  afficherDep();
  apply();
  cadrerSurResultats();
  setHash();
  return true;
}

/* Après un changement de département, on recadre la carte sur les résultats :
   sans cela le filtre semble sans effet tant qu'on n'a pas navigué à la main. */
function cadrerSurResultats() {
  if (!state.mapReady || !state.shown.length) return;
  const pts = state.shown.slice(0, 2000).map(t => [t.lat, t.lon]);
  state.map.fitBounds(L.latLngBounds(pts).pad(0.15));
}

/* Applique le dictionnaire aux éléments statiques du HTML. Le HTML est écrit en
   français ; sous /en/ c'est cette passe qui pose l'anglais. Les chaînes viennent
   toutes de assets/i18n.js, jamais d'une saisie utilisateur. */
function traduire() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const v = U[el.dataset.i18n];
    if (v != null) el.innerHTML = v;
  });
  for (const [suffixe, attribut] of [['ph', 'placeholder'], ['al', 'aria-label'], ['ti', 'title']]) {
    document.querySelectorAll(`[data-i18n-${suffixe}]`).forEach(el => {
      const v = U[el.dataset[`i18n${suffixe[0].toUpperCase()}${suffixe[1]}`]];
      if (v != null) el.setAttribute(attribut, v);
    });
  }
  /* Les liens de bascule pointent vers l'autre langue, où que l'on soit. */
  const bascule = BASE + DICO.autre_langue.chemin;
  document.querySelectorAll('[data-lang-switch]').forEach(a => {
    a.setAttribute('href', bascule || './');
    a.setAttribute('hreflang', DICO.autre_langue.code);
    a.setAttribute('lang', DICO.autre_langue.code);
    if (a.classList.contains('lang-btn')) a.textContent = DICO.autre_langue.code.toUpperCase();
  });
  document.title = U.titre_page;
}

function init() {
  traduire();
  buildChips();

  /* Pendant la frappe on n'agit que sur une saisie reconnue — ou vidée. Les
     états intermédiaires (« lo », « loi »…) laissent la liste tranquille. */
  let debDep;
  $('#chips').addEventListener('input', e => {
    if (e.target.id !== 'dep') return;
    clearTimeout(debDep);
    const saisie = e.target.value;
    debDep = setTimeout(() => {
      const code = resoudreDep(saisie, true);
      if (code !== null) choisirDep(code);
    }, 200);
  });

  /* À la sortie du champ (ou après un choix dans la liste), on affiche le
     libellé complet, et on efface une saisie restée sans correspondance. */
  $('#chips').addEventListener('change', e => {
    if (e.target.id === 'lp') {
      state.lp = e.target.value;
      e.target.classList.toggle('is-on', !!state.lp);
      apply();
      setHash();
      return;
    }
    if (e.target.id !== 'dep') return;
    clearTimeout(debDep);
    const code = resoudreDep(e.target.value, true);
    if (code === null || !choisirDep(code)) afficherDep();
  });

  $('#chips').addEventListener('click', e => {
    const b = e.target.closest('.chip'); if (!b) return;
    const id = b.dataset.f;
    if (!id) return;
    if (id === 'near' && !state.me) { geolocate(); }
    state.active.has(id) ? state.active.delete(id) : state.active.add(id);
    b.classList.toggle('is-on');
    apply();
  });

  let deb;
  $('#q').addEventListener('input', e => {
    state.q = e.target.value;
    $('#q-clear').hidden = !state.q;
    clearTimeout(deb);
    deb = setTimeout(() => { apply(); setHash(); }, 160);
  });
  /* « 44 » ou « loire-atlantique » tapé dans la recherche désigne un
     département : à la validation, on le bascule dans son filtre plutôt que
     de chercher la chaîne « 44 » dans toutes les fiches du pays. */
  const rechercheVersDep = () => {
    const code = resoudreDep(state.q, false);
    if (!code) return;
    state.q = '';
    $('#q').value = '';
    $('#q-clear').hidden = true;
    if (!choisirDep(code)) { apply(); setHash(); }   // déjà sur ce département
  };
  $('#q').addEventListener('change', rechercheVersDep);
  $('#q').addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); rechercheVersDep(); $('#q').blur(); }
  });

  $('#q-clear').addEventListener('click', () => {
    $('#q').value = ''; state.q = ''; $('#q-clear').hidden = true; apply(); setHash();
  });

  $('#btn-geo').addEventListener('click', geolocate);
  $('#btn-about').addEventListener('click', openAbout);
  $('#more').addEventListener('click', () => { state.limit += 60; renderList(); });
  $('#results').addEventListener('click', e => {
    const c = e.target.closest('.card'); if (c) openSheet(c.dataset.id);
  });
  $('#sheet').addEventListener('change', e => {
    if (e.target.id === 'c-type') majTypeContribution();
  });

  $('#sheet').addEventListener('click', e => {
    const contrib = e.target.closest('[data-contrib]');
    if (contrib) {
      e.preventDefault();
      return ouvrirContribution(contrib.dataset.contrib,
                                state.all.find(x => x.id === state.openId) || null);
    }
    const envoi = e.target.closest('[data-envoi]');
    if (envoi) return envoyerContribution(envoi.dataset.envoi);
    if (e.target.closest('[data-retour]')) return openSheet(state.contrib.retour);
    const img = e.target.closest('img[data-full]');
    if (img) return openPhoto(img.dataset.full, img.alt);
    if (e.target.closest('#btn-minimap')) return toggleMiniMap();
    if (e.target.closest('[data-full-map]')) return showOnFullMap();
    if (e.target.closest('[data-close]')) closeSheet();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });
  document.addEventListener('click', e => {
    const a = e.target.closest('[data-add-track]');
    if (a) { e.preventDefault(); ouvrirContribution('ajout', null); }
  });

  $('#vitrine').addEventListener('click', e => {
    const contrib = e.target.closest('[data-contrib]');
    if (contrib) {
      e.preventDefault();
      return ouvrirContribution(contrib.dataset.contrib, null);
    }
    const carte = e.target.closest('[data-site]');
    if (carte && !e.metaKey && !e.ctrlKey && e.button === 0) {
      e.preventDefault();
      openSheet(carte.dataset.site);
    }
  });

  $('#tab-list').addEventListener('click', () => switchView('list'));
  $('#tab-map').addEventListener('click', () => switchView('map'));

  load().catch(err => {
    $('#loader').innerHTML = U.erreur_chargement;
    console.error(err);
  });

  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register(BASE + 'sw.js').catch(() => {});
    // Quand une nouvelle version prend la main, on recharge une seule fois :
    // sans cela un ancien service worker continuerait de servir l'ancienne appli.
    let rechargement = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (rechargement) return;
      rechargement = true;
      location.reload();
    });
  }
}

function switchView(v) {
  const isMap = v === 'map';
  $('#tab-list').classList.toggle('is-active', !isMap);
  $('#tab-map').classList.toggle('is-active', isMap);
  $('#tab-list').setAttribute('aria-selected', String(!isMap));
  $('#tab-map').setAttribute('aria-selected', String(isMap));
  $('#view-list').classList.toggle('is-active', !isMap);
  $('#view-map').classList.toggle('is-active', isMap);
  if (isMap) { state.mapReady ? state.map.invalidateSize() : initMap(); }
  setHash();
}

document.addEventListener('DOMContentLoaded', init);
})();
