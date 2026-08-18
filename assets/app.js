/* Où s'entraîner ? — annuaire des pistes d'athlétisme françaises
   Données : Recensement des équipements sportifs (Data ES) — Licence Ouverte 2.0
   + contributions communautaires (data/overrides/). */
(() => {
'use strict';

/* ------------------------------------------------------------------ config */
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
const SOL = {
  synthetique: ['Synthétique (tartan)', 'sol-synthetique'],
  bitume:      ['Bitume / goudron', ''],
  cendree:     ['Cendrée / stabilisé', ''],
  sable:       ['Sable', ''],
  gazon:       ['Gazon', ''],
  naturel:     ['Surface naturelle', ''],
  interieur:   ['Sol intérieur', ''],
};
const AGRES = {
  longueur: 'Sautoir longueur', triple: 'Triple saut', hauteur: 'Sautoir hauteur',
  perche: 'Sautoir à la perche', poids: 'Lancer du poids', disque: 'Lancer du disque',
  marteau: 'Lancer du marteau', javelot: 'Lancer du javelot', steeple: 'Steeple',
  saut_indetermine: 'Aire de saut (type inconnu)',
  lancer_indetermine: 'Aire de lancer (type inconnue)',
};
const SOURCES = ['Data ES (ministère)', 'Data ES + communauté', 'Contribution communautaire'];
const ORDRE_AGRES = ['steeple', 'longueur', 'triple', 'hauteur', 'perche',
                     'poids', 'disque', 'marteau', 'javelot'];
const trier = list => [...list].sort((a, b) => ORDRE_AGRES.indexOf(a) - ORDRE_AGRES.indexOf(b));

const FILTERS = [
  { id: 'near',   label: '📍 Près de moi', test: null },
  { id: 'piste',  label: 'Avec piste',     test: t => t.piste },
  { id: 'synth',  label: 'Synthétique',    test: t => t.surface === 'synthetique' },
  { id: 'p400',   label: '400 m',          test: t => t.longueur_piste === 400 },
  { id: 'libre',  label: 'Accès libre',    test: t => t.acces_libre },
  { id: 'perche', label: 'Perche',         test: t => has(t, 'perche') },
  { id: 'long',   label: 'Longueur',       test: t => has(t, 'longueur') || has(t, 'triple') },
  { id: 'haut',   label: 'Hauteur',        test: t => has(t, 'hauteur') },
  { id: 'poids',  label: 'Poids',          test: t => has(t, 'poids') },
  { id: 'lancer', label: 'Lancers longs',  test: t => ['disque','marteau','javelot'].some(a => has(t, a)) },
  { id: 'sauts',  label: 'Un sautoir',     test: t => t.nb_sautoirs > 0 },
  { id: 'ecl',    label: 'Éclairée',       test: t => t.eclairage },
  { id: 'couv',   label: 'Couverte',       test: t => t.couvert },
  { id: 'vest',   label: 'Vestiaires',     test: t => t.vestiaires },
  { id: 'noeco',  label: 'Hors enceinte scolaire', test: t => !t.scolaire },
  { id: 'photo',  label: '📷 Avec photos',  test: t => t.photos.length > 0 },
  { id: 'avis',   label: '★ Avec avis',     test: t => t.avis.length > 0 },
];

const has = (t, a) => t.agres.includes(a);

/* ------------------------------------------------------------------ état */
const state = { all: [], deps: {}, shown: [], limit: 40, active: new Set(['piste']),
                q: '', me: null, openId: null, map: null, cluster: null, mapReady: false };

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
  return isNaN(d) ? iso : d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
};
const fmtDist = km => km < 1 ? `${Math.round(km * 1000)} m`
                    : km < 10 ? `${km.toFixed(1)} km` : `${Math.round(km)} km`;

/* --------------------------------------------------------------- données */
async function load() {
  const res = await fetch('data/tracks.json', { cache: 'no-cache' });
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const raw = await res.json();
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
  document.title = `Où s'entraîner ? — ${state.all.length} sites d'athlétisme en France`;
  apply();
  readHash();
}

/* -------------------------------------------------------------- filtrage */
function apply() {
  const q = norm(state.q).trim();
  const words = q ? q.split(/\s+/) : [];
  const tests = FILTERS.filter(f => f.test && state.active.has(f.id)).map(f => f.test);

  let out = state.all.filter(t => {
    for (const fn of tests) if (!fn(t)) return false;
    for (const w of words) if (!t._s.includes(w)) return false;
    return true;
  });

  if (state.me) {
    for (const t of out) t._d = distance(state.me.lat, state.me.lon, t.lat, t.lon);
    out.sort((a, b) => a._d - b._d);
    if (state.active.has('near')) out = out.filter(t => t._d <= 30);
  } else {
    out.sort((a, b) => (a.ville || '').localeCompare(b.ville || '', 'fr'));
  }

  state.shown = out;
  state.limit = 40;
  $('#count').textContent = out.length ? `${out.length} site${out.length > 1 ? 's' : ''}` : '';
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
  if (t.longueur_piste) tags.push(`<span class="tag">${t.longueur_piste} m${t.couloirs ? ` · ${t.couloirs} couloirs` : ''}</span>`);
  else if (t.couloirs) tags.push(`<span class="tag">${t.couloirs} couloirs</span>`);
  if (t.acces_libre) tags.push('<span class="tag free">Accès libre</span>');
  if (t.couvert) tags.push('<span class="tag">Couverte</span>');
  for (const a of trier(t.agres)) tags.push(`<span class="tag">${esc(AGRES[a] || a)}</span>`);
  if (!t.agres.length) {
    if (t.nb_sautoirs) tags.push(`<span class="tag maybe">${t.nb_sautoirs} aire${t.nb_sautoirs>1?'s':''} de saut</span>`);
    if (t.nb_aires_lancer) tags.push(`<span class="tag maybe">${t.nb_aires_lancer} aire${t.nb_aires_lancer>1?'s':''} de lancer</span>`);
  }
  if (t.scolaire) tags.push('<span class="tag">Site scolaire</span>');
  return tags.join('');
}

function stars(n) {
  const full = Math.round(n);
  return `<span class="stars" aria-label="${n} sur 5">${'★'.repeat(full)}${'☆'.repeat(5 - full)}</span>`;
}

function renderList() {
  const list = state.shown.slice(0, state.limit);
  $('#results').innerHTML = list.map(t => {
    const vignette = t.photos[0];
    return `
    <li class="card${vignette ? ' has-photo' : ''}" data-id="${esc(t.id)}">
      <div class="card-main">
        <div class="card-top">
          <h2>${esc(t.nom || 'Équipement d’athlétisme')}</h2>
          ${t._d != null ? `<span class="dist">${fmtDist(t._d)}</span>` : ''}
        </div>
        <p class="loc">${esc([t.ville, t.dep && `(${t.dep})`].filter(Boolean).join(' '))}</p>
        ${t.note_moyenne ? `<p class="rating">${stars(t.note_moyenne)}
           <span>${t.note_moyenne.toFixed(1).replace('.', ',')} · ${t.nb_avis} avis</span></p>` : ''}
        <div class="tags">${tagsOf(t)}</div>
      </div>
      ${vignette ? `<img class="thumb" loading="lazy" src="${esc(vignette.t || vignette.f)}"
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

function initMap() {
  state.map = L.map('map', { zoomControl: false, tap: false })
              .setView(state.me ? [state.me.lat, state.me.lon] : [46.7, 2.4],
                       state.me ? 11 : 5);
  L.control.zoom({ position: 'bottomright' }).addTo(state.map);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(state.map);
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
  const osm = `https://www.openstreetmap.org/?mlat=${t.lat}&mlon=${t.lon}#map=17/${t.lat}/${t.lon}`;

  const agres = [
    ...trier(t.agres).map(a => `<span>${esc(AGRES[a] || a)}</span>`),
    ...t.agres_probables.map(a => `<span class="maybe">${esc(AGRES[a] || a)}</span>`),
  ].join('');

  const galerie = t.photos.length ? `
    <div class="gallery" role="group" aria-label="Photos du site">
      ${t.photos.map((p, i) => `
        <figure><img loading="${i ? 'lazy' : 'eager'}" src="${esc(p.f)}"
             alt="${esc(p.l || t.nom)}" data-full="${esc(p.f)}">
          ${p.l ? `<figcaption>${esc(p.l)}${p.c ? ` <span>© ${esc(p.c)}</span>` : ''}</figcaption>` : ''}
        </figure>`).join('')}
    </div>` : '';

  const avis = `
    <div class="sec">Avis des athlètes${t.nb_avis ? ` (${t.nb_avis})` : ''}</div>
    ${t.avis.length ? t.avis.map(a => `
      <article class="avis">
        <header>
          ${a.n ? stars(a.n) : ''}
          <strong>${esc(a.a || 'Anonyme')}</strong>
          ${a.d ? `<time datetime="${esc(a.d)}">${fmtDate(a.d)}</time>` : ''}
        </header>
        <p>${esc(a.t)}</p>
      </article>`).join('')
    : `<p class="vide">Personne n’a encore décrit ce site.
         Vous vous y entraînez&nbsp;? Votre retour aidera les autres.</p>`}
    <a class="btn" style="margin-top:10px" target="_blank" rel="noopener"
       href="${ISSUE('avis.yml', { title: `[Avis] ${t.nom} (${t.ville})`, id: t.id })}">
       ✍️ Donner mon avis</a>`;

  $('#sheet-body').innerHTML = `
    <h2>${esc(t.nom || 'Équipement d’athlétisme')}</h2>
    <p class="loc">${esc([t.adresse, [t.cp, t.ville].filter(Boolean).join(' ')].filter(Boolean).join(', '))}${t.dep_nom ? ` · ${esc(t.dep_nom)}` : ''}</p>
    ${t.note_moyenne ? `<p class="rating big">${stars(t.note_moyenne)}
       <span>${t.note_moyenne.toFixed(1).replace('.', ',')} sur 5 · ${t.nb_avis} avis</span></p>` : ''}

    ${galerie}

    <div class="actions">
      <a class="btn primary" href="${gmaps}" target="_blank" rel="noopener">Itinéraire</a>
      <a class="btn" href="${osm}" target="_blank" rel="noopener">Voir sur OSM</a>
    </div>

    <div class="sec">Piste</div>
    <div class="grid">
      ${kv('Revêtement', sol)}
      ${kv('Développement', t.longueur_piste ? t.longueur_piste + ' m' : null)}
      ${kv('Couloirs', t.couloirs)}
      ${kv('Configuration', t.couvert ? 'Couverte / indoor' : (t.piste ? 'Plein air' : null))}
      ${kv('Mise en service', t.annee)}
      ${kv('Dernière rénovation', t.renovation)}
    </div>

    ${agres ? `<div class="sec">Agrès recensés</div><div class="eq">${agres}</div>` : ''}
    ${t.agres_probables.length ? `<p class="src">Les mentions en pointillés proviennent d’une fiche
       ministérielle qui indique la présence d’une aire sans préciser sa discipline.
       <a href="${ISSUE('correction.yml', { title: `[Correction] ${t.nom} (${t.ville})`, id: t.id })}"
          target="_blank" rel="noopener">Vous connaissez ce site ? Complétez-le.</a></p>` : ''}

    <div class="sec">Accès &amp; services</div>
    <div class="grid">
      ${kv('Accès libre', t.acces_libre ? 'Oui' : (t.ouvert_public ? 'Ouvert au public (horaires)' : 'Non / réservé'))}
      ${kv('Éclairage', t.eclairage ? 'Oui' : 'Non')}
      ${kv('Vestiaires', t.vestiaires ? 'Oui' : 'Non')}
      ${kv('Douches', t.douches ? 'Oui' : 'Non')}
      ${kv('Sanitaires', t.sanitaires ? 'Oui' : 'Non')}
      ${kv('Tribunes', t.tribunes ? t.tribunes + ' places' : null)}
      ${t.scolaire ? kv('Type de site', 'Enceinte scolaire') : ''}
      ${kv('Horaires', t.horaires)}
    </div>
    ${t.acces_note ? `<p class="note">${esc(t.acces_note)}</p>` : ''}
    ${avis}
    ${t.note ? `<p class="note">${esc(t.note)}</p>` : ''}
    ${t.url ? `<p><a href="${esc(t.url)}" target="_blank" rel="noopener">Site officiel de l’équipement</a></p>` : ''}

    <div class="actions" style="margin-top:18px">
      <a class="btn" target="_blank" rel="noopener"
         href="${ISSUE('correction.yml', { title: `[Correction] ${t.nom} (${t.ville})`, id: t.id })}">Signaler une erreur</a>
      <a class="btn" target="_blank" rel="noopener"
         href="${ISSUE('complement.yml', { title: `[Complément] ${t.nom} (${t.ville})`, id: t.id })}">Compléter la fiche</a>
    </div>

    <p class="src">Réf. ${esc(t.id)} · Source : ${esc(SOURCES[t.source] || SOURCES[0])} —
      <a href="https://equipements.sports.gouv.fr/" target="_blank" rel="noopener">Data ES</a>,
      Licence Ouverte 2.0. Les données déclaratives peuvent être incomplètes&nbsp;: vérifiez
      les conditions d’accès avant de vous déplacer.</p>`;
  $('#sheet').hidden = false;
  document.body.style.overflow = 'hidden';
  setHash();
}

function closeSheet() {
  state.openId = null;
  $('#sheet').hidden = true;
  document.body.style.overflow = '';
  if (location.hash.includes('site=')) history.replaceState(null, '', location.pathname + location.search);
}

/* Liens partageables : #carte, #site=I352380090 */
function setHash() {
  const id = state.openId;
  const parts = [];
  if ($('#view-map').classList.contains('is-active')) parts.push('carte');
  if (state.q.trim()) parts.push('q=' + encodeURIComponent(state.q.trim()));
  if (id) parts.push('site=' + id);
  history.replaceState(null, '', parts.length ? '#' + parts.join('&') : location.pathname);
}

function readHash() {
  const h = new URLSearchParams(location.hash.replace(/^#/, '').replace(/&/g, '&'));
  if (location.hash.includes('carte')) switchView('map');
  const q = h.get('q');
  if (q) { state.q = q; $('#q').value = q; $('#q-clear').hidden = false; apply(); }
  const id = h.get('site');
  if (id) openSheet(id);
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
  $('#sheet-body').innerHTML = `
    <div class="about">
      <h2>À propos</h2>
      <p>Un annuaire libre des pistes d’athlétisme françaises et de leurs agrès :
         sautoirs longueur / hauteur / perche, aires de lancer, revêtement synthétique,
         cendrée ou bitume, éclairage, vestiaires…</p>

      <h3>D’où viennent les données ?</h3>
      <p>Du <a href="https://equipements.sports.gouv.fr/" target="_blank" rel="noopener">Recensement
         des équipements sportifs (Data ES)</a> du ministère chargé des Sports, publié sous
         <a href="https://github.com/etalab/licence-ouverte/blob/master/LO.md" target="_blank" rel="noopener">Licence
         Ouverte 2.0</a>, complété par les contributions de la communauté.</p>

      <h3>Les données sont déclaratives</h3>
      <p>Elles sont saisies par les propriétaires des installations. Un site peut mentionner
         une « aire de saut » sans préciser s’il s’agit d’un sautoir en longueur ou d’une perche,
         et les conditions d’accès réelles changent souvent. Vérifiez avant de vous déplacer.</p>

      <h3>Contribuer</h3>
      <ul>
        <li><a href="${ISSUE('correction.yml', {})}" target="_blank" rel="noopener">Signaler une erreur</a> sur une fiche</li>
        <li><a href="${ISSUE('ajout.yml', {})}" target="_blank" rel="noopener">Ajouter une piste manquante</a></li>
        <li><a href="https://github.com/${REPO}" target="_blank" rel="noopener">Proposer une pull request</a> sur le dépôt</li>
      </ul>
      <p class="src">Fond de carte © contributeurs
         <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>.
         Code source&nbsp;: <a href="https://github.com/${REPO}" target="_blank" rel="noopener">github.com/${esc(REPO)}</a></p>
    </div>`;
  $('#sheet').hidden = false;
  document.body.style.overflow = 'hidden';
}

/* -------------------------------------------------------- géolocalisation */
function geolocate() {
  if (!navigator.geolocation) return alert('Géolocalisation indisponible sur cet appareil.');
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
    alert(err.code === 1
      ? 'Autorisez la géolocalisation pour trier les pistes par distance.'
      : 'Position introuvable. Utilisez la recherche par ville.');
  }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
}

/* -------------------------------------------------------------- interface */
function buildChips() {
  $('#chips').innerHTML = FILTERS.map(f =>
    `<button class="chip${state.active.has(f.id) ? ' is-on' : ''}" data-f="${f.id}">${f.label}</button>`
  ).join('');
}

function init() {
  buildChips();

  $('#chips').addEventListener('click', e => {
    const b = e.target.closest('.chip'); if (!b) return;
    const id = b.dataset.f;
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
    $('#loader').innerHTML = 'Impossible de charger les données. Rechargez la page.';
    console.error(err);
  });

  if ('serviceWorker' in navigator && location.protocol === 'https:')
    navigator.serviceWorker.register('sw.js').catch(() => {});
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
