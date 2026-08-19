/* Où s'entraîner ? — annuaire des pistes d'athlétisme françaises
   Données : Recensement des équipements sportifs (Data ES) — Licence Ouverte 2.0
   + contributions communautaires (data/overrides/). */
(() => {
'use strict';

/* ------------------------------------------------------------------ config */
// Version de l'application. À incrémenter à chaque déploiement du code :
// scripts/build_data.py la recopie dans tracks.json, ce qui permet à un
// navigateur exécutant une version périmée de s'en rendre compte tout seul.
const APP_VERSION = '5';

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
  { id: 'p400',   test: t => t.longueur_piste === 400 },
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
                q: '', dep: '', me: null, openId: null, map: null, mini: null,
                cluster: null, mapReady: false };

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
  if (state.mapReady) renderMap();
}

/* ----------------------------------------------------------------- liste */
function tagsOf(t) {
  const tags = [];
  if (t.surface) {
    const [lab, cls] = SOL[t.surface] || [t.surface, ''];
    tags.push(`<span class="tag sol ${cls}">${esc(lab)}</span>`);
  }
  if (t.longueur_piste) tags.push(`<span class="tag">${t.longueur_piste} m${t.couloirs ? ` · ${DICO.tags.couloirs(t.couloirs)}` : ''}</span>`);
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
  const libelle = `${t.nom} (${t.ville})`;

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
    <a class="btn" style="margin-top:10px" target="_blank" rel="noopener"
       href="${ISSUE('avis.yml', { title: U.avis_titre(libelle), id: t.id })}">
       ${esc(U.donner_avis)}</a>`;

  $('#sheet-body').innerHTML = `
    <h2>${esc(t.nom || U.sans_nom)}</h2>
    <p class="loc">${esc([t.adresse, [t.cp, t.ville].filter(Boolean).join(' ')].filter(Boolean).join(', '))}${t.dep_nom ? ` · ${esc(t.dep_nom)}` : ''}</p>
    ${t.note_moyenne ? `<p class="rating big">${stars(t.note_moyenne)}
       <span>${esc(U.note_sur_5(fmtNote(t.note_moyenne)))} · ${esc(U.nb_avis(t.nb_avis))}</span></p>` : ''}

    ${galerie}

    <div class="actions">
      <a class="btn primary" href="${gmaps}" target="_blank" rel="noopener">${esc(U.itineraire)}</a>
      <button class="btn" type="button" id="btn-minimap">${esc(U.voir_carte)}</button>
    </div>
    <div id="minimap" class="minimap" hidden></div>

    <div class="sec">${esc(U.sec_piste)}</div>
    <div class="grid">
      ${kv(U.kv_revetement, sol)}
      ${kv(U.kv_developpement, t.longueur_piste ? t.longueur_piste + ' m' : null)}
      ${kv(U.kv_couloirs, t.couloirs)}
      ${kv(U.kv_config, t.couvert ? U.kv_couverte : (t.piste ? U.kv_plein_air : null))}
      ${kv(U.kv_service, t.annee)}
      ${kv(U.kv_renovation, t.renovation)}
    </div>

    ${agres ? `<div class="sec">${esc(U.sec_agres)}</div><div class="eq">${agres}</div>` : ''}
    ${t.agres_probables.length ? `<p class="src">${U.incertain(
        ISSUE('correction.yml', { title: U.correction_titre(libelle), id: t.id }))}</p>` : ''}

    <div class="sec">${esc(U.sec_acces)}</div>
    <div class="grid">
      ${kv(U.kv_acces_libre, t.acces_libre ? U.oui : (t.ouvert_public ? U.ouvert_horaires : U.non_reserve))}
      ${kv(U.kv_eclairage, t.eclairage ? U.oui : U.non)}
      ${kv(U.kv_vestiaires, t.vestiaires ? U.oui : U.non)}
      ${kv(U.kv_douches, t.douches ? U.oui : U.non)}
      ${kv(U.kv_sanitaires, t.sanitaires ? U.oui : U.non)}
      ${kv(U.kv_tribunes, t.tribunes ? U.places(t.tribunes) : null)}
      ${t.scolaire ? kv(U.kv_type_site, U.enceinte_scolaire) : ''}
      ${kv(U.kv_horaires, t.horaires)}
    </div>
    ${t.acces_note ? `<p class="note">${esc(t.acces_note)}</p>` : ''}
    ${avis}
    ${t.note ? `<p class="note">${esc(t.note)}</p>` : ''}
    ${t.url ? `<p><a href="${esc(t.url)}" target="_blank" rel="noopener">${esc(U.site_officiel)}</a></p>` : ''}

    <div class="actions" style="margin-top:18px">
      <a class="btn" target="_blank" rel="noopener"
         href="${ISSUE('correction.yml', { title: U.correction_titre(libelle), id: t.id })}">${esc(U.signaler)}</a>
      <a class="btn" target="_blank" rel="noopener"
         href="${ISSUE('complement.yml', { title: U.complement_titre(libelle), id: t.id })}">${esc(U.completer)}</a>
    </div>

    <p class="src"><a href="${FICHES}${esc(t.id)}/">${esc(U.page_dediee)}</a><br>
      ${U.reference(esc(t.id), esc(SOURCES[t.source] || SOURCES[0]))}</p>`;
  $('#sheet').hidden = false;
  document.body.style.overflow = 'hidden';
  setHash();
}

function closeSheet() {
  destroyMiniMap();
  state.openId = null;
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
  if (state.q.trim()) parts.push('q=' + encodeURIComponent(state.q.trim()));
  if (id) parts.push('site=' + id);
  history.replaceState(null, '', parts.length ? '#' + parts.join('&') : location.pathname);
}

function readHash() {
  const h = new URLSearchParams(location.hash.replace(/^#/, '').replace(/&/g, '&'));
  if (location.hash.includes('carte')) switchView('map');
  let filtre = false;
  const dep = h.get('dep');
  if (dep) {
    state.dep = dep;
    const sel = $('#dep');
    if (sel) { sel.value = dep; sel.classList.toggle('is-on', !!sel.value); }
    filtre = true;
  }
  const q = h.get('q');
  if (q) { state.q = q; $('#q').value = q; $('#q-clear').hidden = false; filtre = true; }
  if (filtre) { apply(); cadrerSurResultats(); }
  const id = h.get('site');
  if (id) openSheet(id);
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
    btn.textContent = 'Voir sur la carte';
    return;
  }

  box.hidden = false;
  btn.textContent = 'Masquer la carte';
  box.innerHTML = '<div class="minimap-canvas"></div>' +
    '<button type="button" class="minimap-full" data-full-map>Ouvrir en plein écran</button>';

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

/* ----------------------------------------------------------- à propos */
function openAbout() {
  state.openId = null;
  $('#sheet-body').innerHTML = DICO.about({ repo: REPO, issue: ISSUE });
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
    `<select id="dep" class="chip-select" aria-label="${esc(U.dep_label)}">
       <option value="">${esc(U.dep_toutes)}</option>
     </select>` +
    FILTERS.map(f =>
      `<button class="chip${state.active.has(f.id) ? ' is-on' : ''}" data-f="${f.id}">${f.label}</button>`
    ).join('');
}

/* 108 départements : un menu déroulant, groupé par région et compté, plutôt
   qu'une puce par département qu'il faudrait faire défiler indéfiniment. */
function remplirDepartements() {
  const sel = $('#dep');
  if (!sel) return;
  const nb = {};
  for (const t of state.all) if (t.dep) nb[t.dep] = (nb[t.dep] || 0) + 1;

  const regions = {};
  for (const code in nb) {
    const [nom, region] = state.deps[code] || [code, ''];
    (regions[region] || (regions[region] = [])).push([code, nom || code, nb[code]]);
  }
  const cmp = (a, b) => a.localeCompare(b, DICO.locale);
  const html = [`<option value="">${esc(U.dep_toutes)}</option>`];
  for (const region of Object.keys(regions).sort(cmp)) {
    html.push(`<optgroup label="${esc(region || 'France')}">` +
      regions[region].sort((a, b) => cmp(a[1], b[1])).map(([code, nom, n]) =>
        `<option value="${esc(code)}">${esc(code)} · ${esc(nom)} (${n})</option>`).join('') +
      '</optgroup>');
  }
  sel.innerHTML = html.join('');
  sel.value = state.dep;
  sel.classList.toggle('is-on', !!state.dep);
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

  $('#chips').addEventListener('change', e => {
    if (e.target.id !== 'dep') return;
    state.dep = e.target.value;
    e.target.classList.toggle('is-on', !!state.dep);
    apply();
    cadrerSurResultats();
    setHash();
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
  $('#q-clear').addEventListener('click', () => {
    $('#q').value = ''; state.q = ''; $('#q-clear').hidden = true; apply(); setHash();
  });

  $('#btn-geo').addEventListener('click', geolocate);
  $('#btn-about').addEventListener('click', openAbout);
  $('#more').addEventListener('click', () => { state.limit += 60; renderList(); });
  $('#results').addEventListener('click', e => {
    const c = e.target.closest('.card'); if (c) openSheet(c.dataset.id);
  });
  $('#sheet').addEventListener('click', e => {
    const img = e.target.closest('img[data-full]');
    if (img) return openPhoto(img.dataset.full, img.alt);
    if (e.target.closest('#btn-minimap')) return toggleMiniMap();
    if (e.target.closest('[data-full-map]')) return showOnFullMap();
    if (e.target.closest('[data-close]')) closeSheet();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });
  document.addEventListener('click', e => {
    const a = e.target.closest('[data-add-track]');
    if (a) { e.preventDefault(); window.open(ISSUE('ajout.yml', {}), '_blank', 'noopener'); }
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
