/**
 * Serveur de recherche pour /api/tracks — a deployer sur Cloudflare Workers,
 * Netlify Functions, Vercel ou tout autre execution en peripherie.
 *
 * POURQUOI CE FICHIER EXISTE
 * --------------------------
 * Le site est publie sur GitHub Pages, qui sert des fichiers statiques et
 * ignore la chaine de requete : /api/tracks?city=Nantes et /api/tracks?city=Lyon
 * designent le meme octet. Les facettes pre-calculees de scripts/build_api.py
 * couvrent les criteres simples, mais aucune combinaison arbitraire, et aucune
 * recherche par rayon autour de coordonnees quelconques.
 *
 * Ce worker comble exactement ce trou. Il ne contient aucune donnee : il lit
 * l'index publie par le build (api/index.json), donc il ne peut pas diverger
 * du site. Un rebuild mensuel du site suffit a le mettre a jour.
 *
 * DEPLOIEMENT
 * -----------
 *   npx wrangler deploy api/worker.js --name pistes-athle-api
 * puis, pour que le site l'annonce dans openapi.json et dans son document de
 * capacites, rebuild avec API_URL pointant sur le worker :
 *   API_URL=https://pistes-athle-api.<compte>.workers.dev python3 scripts/build_site.py
 *
 * Tant qu'API_URL n'est pas renseigne, le site declare honnetement qu'aucun
 * serveur de recherche n'est disponible : mieux vaut un agent qui sait qu'il
 * doit filtrer lui-meme qu'un agent qui croit avoir filtre.
 *
 * (c) Data ES, ministere charge des Sports, Licence Ouverte 2.0.
 */

const SOURCE = "https://chardonneaur.github.io/pistes-athle";
const LICENCE = "https://github.com/etalab/licence-ouverte/blob/master/LO.md";
const MAX_LIMIT = 500, DEFAUT_LIMIT = 50, MAX_RADIUS = 100, DEFAUT_RADIUS = 10;

// Nom de parametre -> valeur du champ `agres`. Doit rester identique a
// DISCIPLINES dans scripts/build_api.py : c'est le meme contrat.
const DISCIPLINES = {
  long_jump: "longueur", triple_jump: "triple", high_jump: "hauteur",
  pole_vault: "perche", shot_put: "poids", discus: "disque",
  hammer: "marteau", javelin: "javelot", steeplechase: "steeple",
};
const SURFACES = {
  synthetic: "synthetique", asphalt: "bitume", cinder: "cendree",
  sand: "sable", grass: "gazon", natural: "naturel", indoor: "interieur",
};

let INDEX = null, CHARGE_A = 0;
const TTL_MS = 6 * 60 * 60 * 1000;   // le jeu de donnees bouge une fois par mois

async function index() {
  if (INDEX && Date.now() - CHARGE_A < TTL_MS) return INDEX;
  const r = await fetch(`${SOURCE}/api/index.json`, { cf: { cacheTtl: 3600 } });
  if (!r.ok) throw new Error(`index indisponible : ${r.status}`);
  const d = await r.json();
  INDEX = d;
  CHARGE_A = Date.now();
  return d;
}

function slug(s) {
  return (s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function distanceKm(aLat, aLon, bLat, bLon) {
  const p = Math.PI / 180;
  const x = 0.5 - Math.cos((bLat - aLat) * p) / 2
    + Math.cos(aLat * p) * Math.cos(bLat * p) * (1 - Math.cos((bLon - aLon) * p)) / 2;
  return 2 * 6371 * Math.asin(Math.sqrt(Math.max(0, x)));
}

function erreur(message, parametre, indice, statut = 400) {
  return reponse({ error: message, parameter: parametre, hint: indice }, statut);
}

function reponse(corps, statut = 200) {
  return new Response(JSON.stringify(corps, null, 1) + "\n", {
    status: statut,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
      "cache-control": "public, max-age=3600",
    },
  });
}

/** Un site, en noms de champs complets — la forme que decrit openapi.json. */
function plein(t, distance) {
  return {
    id: t.i, nom: t.n, ville: t.v, departement: t.d, code_postal: t.cp,
    latitude: t.y, longitude: t.x,
    distance_km: distance === undefined ? null : Math.round(distance * 10) / 10,
    piste: !!t.p,
    longueur_piste_m: t.lp ?? null,
    longueur_probable_m: t.lpp ?? null,
    couloirs: t.cl ?? null,
    revetement: t.s ?? null,
    // Jamais false : 5 551 installations n'ont aucune information d'acces, et
    // un blanc n'est pas un refus.
    acces_libre: t.al ? true : null,
    agres_declares: t.g || [],
    agres_probables: t.gp || [],
    url: `${SOURCE}/site/${t.i}/`,
  };
}

export default {
  async fetch(requete) {
    const url = new URL(requete.url);
    if (requete.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET, OPTIONS",
        },
      });
    }
    if (requete.method !== "GET") return erreur("Methode non supportee", null, "GET", 405);

    // Une fiche : /api/tracks/I505020004 ou .../I505020004.json
    const fiche = url.pathname.match(/^\/api\/tracks\/([A-Za-z0-9_-]+)(?:\.json)?$/);
    if (fiche) {
      const d = await index();
      const t = d.tracks.find((x) => x.i === fiche[1]);
      if (!t) return erreur("Identifiant inconnu", "id", `Voir ${SOURCE}/api/index.json`, 404);
      return reponse(enveloppe({ id: t.i }, [plein(t)], d.generated, 1));
    }
    if (!/^\/api\/tracks\/?$/.test(url.pathname)) {
      return erreur("Chemin inconnu", null, `Voir ${SOURCE}/openapi.json`, 404);
    }

    const q = url.searchParams;
    const compris = {};

    // --- acces libre : tri-etat, et le refus est deliberé
    const acces = (q.get("free_access") || "").toLowerCase();
    if (acces === "false" || acces === "0" || acces === "no") {
      return erreur(
        "free_access=false n'est pas servi : l'absence d'information d'acces n'est pas un refus.",
        "free_access",
        "5 551 des 7 135 installations n'ont aucune information d'acces. Utilisez "
        + "free_access=unknown pour les demander explicitement, ou free_access=true "
        + "pour celles qui declarent un acces libre.");
    }
    if (acces && !["true", "1", "yes", "unknown"].includes(acces)) {
      return erreur("Valeur invalide", "free_access", "true | unknown");
    }
    if (acces) compris.free_access = acces === "unknown" ? "unknown" : true;

    // --- coordonnees et rayon
    let lat = null, lon = null, rayon = DEFAUT_RADIUS;
    if (q.has("lat") !== q.has("lon")) {
      return erreur("lat et lon vont ensemble", q.has("lat") ? "lon" : "lat",
        "Fournissez les deux, ou aucun.");
    }
    if (q.has("lat")) {
      lat = Number(q.get("lat")); lon = Number(q.get("lon"));
      if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
        return erreur("Coordonnees invalides", "lat/lon", "WGS84, ex. lat=47.21&lon=-1.55");
      }
      if (q.has("radius")) {
        rayon = Number(q.get("radius"));
        if (!Number.isFinite(rayon) || rayon <= 0) return erreur("Rayon invalide", "radius", "Entier en km");
        if (rayon > MAX_RADIUS) {
          return erreur(`Rayon plafonne a ${MAX_RADIUS} km`, "radius",
            "Au-dela, telechargez api/index.json et filtrez localement.", 413);
        }
      }
      compris.lat = lat; compris.lon = lon; compris.radius = rayon;
    }

    // --- developpement : valeur exacte ou intervalle
    let lgMin = null, lgMax = null;
    const lg = q.get("track_length") || q.get("length");
    if (lg) {
      const m = lg.match(/^(\d+)(?:-(\d+))?$/);
      if (!m) return erreur("Format invalide", "track_length", "400 ou 300-400");
      lgMin = Number(m[1]);
      lgMax = m[2] ? Number(m[2]) : lgMin;
      compris.track_length = lg;
    }

    let couloirs = null;
    if (q.has("lanes_min")) {
      couloirs = Number(q.get("lanes_min"));
      if (!Number.isInteger(couloirs) || couloirs < 1) {
        return erreur("Valeur invalide", "lanes_min", "Entier positif");
      }
      compris.lanes_min = couloirs;
    }

    let revetement = null;
    if (q.has("surface")) {
      const s = q.get("surface").toLowerCase();
      revetement = SURFACES[s] || (Object.values(SURFACES).includes(s) ? s : null);
      if (!revetement) {
        return erreur("Revetement inconnu", "surface", Object.keys(SURFACES).join(" | "));
      }
      compris.surface = revetement;
    }

    const certitude = (q.get("certainty") || "declared").toLowerCase();
    if (!["declared", "probable", "any"].includes(certitude)) {
      return erreur("Valeur invalide", "certainty", "declared | probable | any");
    }
    const voulues = [];
    for (const [param, valeur] of Object.entries(DISCIPLINES)) {
      const v = (q.get(param) || "").toLowerCase();
      if (!v) continue;
      if (!["true", "1", "yes"].includes(v)) {
        return erreur("Une discipline se demande avec true", param,
          `${param}=true. Il n'y a pas de « sans cet agres » : une fiche muette `
          + "n'affirme pas l'absence.");
      }
      voulues.push(valeur);
      compris[param] = true;
    }
    if (certitude !== "declared") compris.certainty = certitude;

    const ville = q.get("city") ? slug(q.get("city")) : null;
    if (ville) compris.city = q.get("city");
    const departement = q.get("department") || null;
    if (departement) compris.department = departement;

    let limite = q.has("limit") ? Number(q.get("limit")) : DEFAUT_LIMIT;
    if (!Number.isInteger(limite) || limite < 1) return erreur("Valeur invalide", "limit", "1 a " + MAX_LIMIT);
    limite = Math.min(limite, MAX_LIMIT);
    const page = q.has("page") ? Number(q.get("page")) : 1;
    if (!Number.isInteger(page) || page < 1) return erreur("Valeur invalide", "page", "Entier a partir de 1");

    // --- filtrage
    const d = await index();
    const avec = [];
    for (const t of d.tracks) {
      if (departement && t.d !== departement) continue;
      if (ville) {
        const sv = slug(t.v);
        // « Lyon » doit attraper « Lyon 3e Arrondissement ».
        if (sv !== ville && !sv.startsWith(`${ville}-`)) continue;
      }
      if (compris.free_access === true && !t.al) continue;
      if (compris.free_access === "unknown" && t.al) continue;
      if (lgMin !== null && !(t.lp >= lgMin && t.lp <= lgMax)) continue;
      if (couloirs !== null && !(t.cl >= couloirs)) continue;
      if (revetement && t.s !== revetement) continue;
      if (voulues.length) {
        const declares = t.g || [], probables = t.gp || [];
        const pool = certitude === "declared" ? declares
          : certitude === "probable" ? probables
            : declares.concat(probables);
        if (!voulues.every((a) => pool.includes(a))) continue;
      }
      let dist;
      if (lat !== null) {
        dist = distanceKm(lat, lon, t.y, t.x);
        if (dist > rayon) continue;
      }
      avec.push([t, dist]);
    }

    avec.sort((a, b) => (lat !== null
      ? a[1] - b[1]
      : (a[0].v || "").localeCompare(b[0].v || "", "fr")
        || (a[0].n || "").localeCompare(b[0].n || "", "fr")));

    const debut = (page - 1) * limite;
    const tranche = avec.slice(debut, debut + limite);
    const corps = enveloppe(compris, tranche.map(([t, dist]) => plein(t, dist)),
      d.generated, avec.length);
    corps.page = page;
    if (debut + limite < avec.length) {
      const suivante = new URL(url);
      suivante.searchParams.set("page", String(page + 1));
      corps.next = suivante.toString();
    }
    return reponse(corps);
  },
};

function enveloppe(query, results, build, total) {
  return {
    query,
    count: results.length,
    total,
    source: `Data ES, ministere charge des Sports, Licence Ouverte 2.0 — build ${build}`,
    license: LICENCE,
    results,
  };
}
