/**
 * Journalise le passage des robots devant pistes-athle.com.
 *
 * Le site est servi par GitHub Pages, qui ne donne aucun log d'acces. Or les
 * robots d'exploration — Googlebot comme GPTBot ou ClaudeBot — n'executent pas
 * de JavaScript : aucune mesure cote navigateur ne les voit jamais. Ce Worker
 * est le seul endroit d'ou l'on puisse les observer.
 *
 * Il ne journalise que les robots. Les visites humaines traversent sans laisser
 * la moindre trace : le site promet de n'avoir aucun traceur, et cette promesse
 * vaut plus que la donnee qu'on y gagnerait.
 *
 * La reponse part avant l'ecriture en base (`waitUntil`), et une panne de la
 * base ne peut pas empecher une page de s'afficher.
 *
 * DEUX SORTIES, UN SEUL PASSAGE
 * -----------------------------
 * Depuis l'installation de Matomo, ce Worker alimente deux journaux a partir
 * de la meme observation :
 *
 *   - la base D1, qui repond a la question de l'etude : qui a decouvert le
 *     site en premier, et a quelle cadence ? Elle garde TOUS les robots,
 *     Googlebot compris, parce que la comparaison IA / moteur est le sujet.
 *   - Matomo, qui ne recoit que les robots d'IA, en `recMode=1`. Ce mode
 *     n'ouvre ni visite ni session : les statistiques humaines restent
 *     intactes, les deux mesures ne se melangent jamais.
 *
 * Les deux sorties sont independantes : une panne de Matomo n'empeche pas
 * l'ecriture en base, et reciproquement.
 */

// Le nom canonique du robot, et le fragment d'user-agent qui le designe.
// L'ordre compte : « Google-Extended » doit etre teste avant « Googlebot »,
// sinon le premier tomberait dans le second.
const ROBOTS = [
  ["GPTBot", "gptbot"],
  ["OAI-SearchBot", "oai-searchbot"],
  ["ChatGPT-User", "chatgpt-user"],
  ["GoogleAgent", "googleagent"],
  ["NovaAct", "novaact"],
  ["ClaudeBot", "claudebot"],
  ["Claude-User", "claude-user"],
  ["Claude-SearchBot", "claude-searchbot"],
  ["anthropic-ai", "anthropic-ai"],
  ["PerplexityBot", "perplexitybot"],
  ["Perplexity-User", "perplexity-user"],
  ["Gemini-Deep-Research", "gemini-deep-research"],
  ["Google-NotebookLM", "google-notebooklm"],
  ["Google-GeminiNotebook", "google-gemininotebook"],
  ["Google-Extended", "google-extended"],
  ["GoogleOther", "googleother"],
  ["Googlebot", "googlebot"],
  ["Google-InspectionTool", "google-inspectiontool"],
  ["Bingbot", "bingbot"],
  ["Applebot-Extended", "applebot-extended"],
  ["Applebot", "applebot"],
  ["meta-externalagent", "meta-externalagent"],
  ["Amazonbot", "amazonbot"],
  ["Bytespider", "bytespider"],
  ["CCBot", "ccbot"],
  ["MistralAI-User", "mistralai-user"],
  ["MistralAI-Crawler", "mistralai-crawler"],
  ["DuckAssistBot", "duckassistbot"],
  ["AI2Bot", "ai2bot"],
  ["Firecrawl", "firecrawl"],
  ["cohere-ai", "cohere-ai"],
  ["YouBot", "youbot"],
  ["DuckDuckBot", "duckduckbot"],
  ["Qwantify", "qwantify"],
  ["YandexBot", "yandexbot"],
  ["Diffbot", "diffbot"],
  ["ImagesiftBot", "imagesiftbot"],
];

const AGENT_MAX = 300;

/* Parmi les robots ci-dessus, ceux que Matomo doit recevoir. Googlebot,
   Bingbot ou YandexBot n'y sont pas : ce sont des moteurs, pas des IA, et les
   envoyer polluerait un rapport intitule « Chatbots IA ». Ils restent
   evidemment en base D1, ou la comparaison avec les IA est tout le sujet.

   Deux familles, parce qu'elles ne disent pas la meme chose :
   - AGENTS : ils cherchent une page POUR REPONDRE A QUELQU'UN, maintenant.
     Ce sont ceux que Matomo nomme nativement dans ses rapports.
   - CORPUS : ils constituent un fonds. Ils decident si l'annuaire sera
     citable demain. VERIFIE LE 25/08/2026 : Matomo les JETTE — un hit dont
     l'user-agent n'est pas dans sa liste de chatbots disparait sans erreur.
     D'ou MATOMO_CORPUS="0" par defaut : ces robots-la sont mesures par D1,
     qui est de toute facon le seul des deux a savoir repondre « qui a
     decouvert le site en premier ». L'ensemble reste ici pour documenter
     ce qui a ete essaye, et pour le jour ou Matomo elargira sa liste. */
const MATOMO_AGENTS = new Set([
  "ChatGPT-User", "Claude-User", "Perplexity-User", "MistralAI-User",
  "Gemini-Deep-Research", "Google-NotebookLM", "Google-GeminiNotebook",
  "GoogleAgent", "NovaAct",
]);
const MATOMO_CORPUS = new Set([
  "GPTBot", "OAI-SearchBot", "ClaudeBot", "Claude-SearchBot", "anthropic-ai",
  "PerplexityBot", "Google-Extended", "Applebot-Extended", "meta-externalagent",
  "Amazonbot", "Bytespider", "CCBot", "cohere-ai", "YouBot", "Diffbot",
  "MistralAI-Crawler", "DuckAssistBot", "AI2Bot", "Firecrawl",
]);

/* L'habillage n'apprend rien sur ce qu'un robot a lu. Volontairement plus
   permissif que le reglage par defaut de Matomo, qui ecarte aussi .json et
   .txt : ici /api/index.json et /llms.txt sont justement les adresses qu'un
   agent bien eleve demande en premier. Les exclure reviendrait a ne pas voir
   ce qu'on cherche a mesurer. (La base D1, elle, garde tout.) */
const HABILLAGE = /^[^?]+\.(?:css|js|mjs|map|webmanifest|manifest|png|jpe?g|gif|webp|avif|svg|ico|bmp|tiff?|woff2?|ttf|otf|eot|wasm)(?:\?|$)/i;
const DOCUMENTS = /^[^?]+\.(?:pdf|docx?|xlsx?|pptx?|csv|epub|zip|gz|tgz|tar)(?:\?|$)/i;
const MATOMO_DELAI_MS = 5000;

/* Les seuls hotes dont une lecture est une lecture DU SITE. Sans ce garde, une
   requete de test sur l'URL workers.dev du Worker part dans Matomo avec cet
   hote-la, et le rapport « Chatbots IA » compte une page cassee du site qui
   n'est pas une page du site. VU LE 25/08/2026 : deux hits
   pistes-athle-ai-tracker.athle.workers.dev/site/TEST-WORKERS-DEV/ y sont
   restes, en tete des « pages cassees ». La base D1, elle, garde tout : elle
   a une colonne `hote` justement pour pouvoir faire le tri apres coup. */
const HOTES_MESURES = new Set(["pistes-athle.com", "www.pistes-athle.com"]);

/* Une adresse qu'aucun humain n'a tapee : c'est un agent qui l'a deduite.
   VU LE 25/08/2026 : ChatGPT-User demande /criteres/piste-400m/, et prend un
   404. Le segment n'a jamais existe (les pages par critere sont sous /pistes/)
   et le slug non plus (c'est `400m`). Deux erreurs plausibles, la meme cause :
   l'agent devine une adresse au lieu de suivre un lien. Une 301 le corrige et
   lui sert la page ; un 404 lui apprend que le site n'a pas la reponse.
   Le prefixe `piste-` / `track-` est retire pour la meme raison. */
const CRITERE_DEVINE = /^\/(?:(en)\/)?(?:criteres?|criteria|criterion)\/([^/]+)\/?$/i;

/* La coquille anglaise a servi des liens en segments francais : depuis /en/,
   `contributeurs/` menait a /en/contributeurs/, qui n'existe pas. Corrige a la
   generation, mais un crawler garde l'adresse qu'il a lue — VU LE 25/08/2026 :
   GPTBot et ClaudeBot ont pris ce 404 tous les deux. Un correctif de gabarit ne
   rattrape que les futurs lecteurs ; cette table rattrape les autres. */
const SEGMENTS_EN = new Map([
  ["contributeurs", "contributors"],
  ["departements", "departments"],
  ["departement", "department"],
  ["pistes", "tracks"],
  ["ville", "city"],
  ["site", "track"],
]);

function redirection(url, methode) {
  if (methode !== "GET" && methode !== "HEAD") return null;

  const parts = url.pathname.split("/").filter(Boolean);
  if (parts[0] === "en" && SEGMENTS_EN.has(parts[1])) {
    const anglais = [...parts];
    anglais[1] = SEGMENTS_EN.get(parts[1]);
    const cible = new URL(`/${anglais.join("/")}/`, url);
    cible.search = url.search;
    return Response.redirect(cible.toString(), 301);
  }

  /* Les neuf departements a un chiffre. Le portail du ministere servait un
     code non comble — « 1 » pour l'Ain — et le site publiait /departement/1/.
     Le champ zero-comble adopte le 25/08/2026 rend « 01 », la forme INSEE :
     409 sites changent d'adresse de departement, et les anciennes sont
     indexees. Elles menent ici a la nouvelle plutot qu'a un 404. */
  if ((parts[0] === "departement" || (parts[0] === "en" && parts[1] === "department"))
      && /^[1-9]$/.test(parts[parts[0] === "en" ? 2 : 1] || "")) {
    const suite = [...parts];
    const rang = parts[0] === "en" ? 2 : 1;
    suite[rang] = "0" + suite[rang];
    const cible = new URL(`/${suite.join("/")}/`, url);
    cible.search = url.search;
    return Response.redirect(cible.toString(), 301);
  }

  const trouve = url.pathname.match(CRITERE_DEVINE);
  if (!trouve) return null;
  const anglais = Boolean(trouve[1]);
  const slug = trouve[2].toLowerCase().replace(/^(?:pistes?|tracks?)-/, "");
  const cible = new URL(anglais ? `/en/tracks/${slug}/` : `/pistes/${slug}/`, url);
  cible.search = url.search;
  return Response.redirect(cible.toString(), 301);
}

/** Le nom du robot, ou null pour tout le reste — humains compris. */
function robot(agent) {
  const bas = (agent || "").toLowerCase();
  if (!bas) return null;
  for (const [nom, fragment] of ROBOTS) {
    if (bas.includes(fragment)) return nom;
  }
  return null;
}

/**
 * Le gabarit de page, pour agreger sans lire 23 762 chemins un par un.
 * Le prefixe de langue est traite a part : il dit la version du site, pas le
 * type de page. Meme regle que `_gabarit` cote build.
 */
function gabarit(chemin) {
  const parts = chemin.split("/").filter(Boolean);
  if (!parts.length) return "/";
  let prefixe = "";
  if (parts[0] === "en") {
    prefixe = "/en";
    parts.shift();
  }
  if (!parts.length) return `${prefixe}/`;
  // Un fichier garde son nom : sitemap.xml et robots.txt sont les pages les
  // plus revelatrices du lot, les noyer dans « / » perdrait l'essentiel.
  if (parts.length === 1 && parts[0].includes(".")) return `${prefixe}/${parts[0]}`;
  return `${prefixe}/${parts[0]}/`;
}

async function journaliser(requete, reponse, env) {
  const agent = requete.headers.get("user-agent") || "";
  const nom = robot(agent);
  if (!nom) return;

  const url = new URL(requete.url);
  try {
    await env.DB.prepare(
      `INSERT INTO visites_robots (vu_le, robot, agent, hote, chemin, gabarit, statut, pays)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    )
      .bind(
        new Date().toISOString(),
        nom,
        agent.slice(0, AGENT_MAX),
        url.hostname,
        url.pathname,
        gabarit(url.pathname),
        reponse.status,
        requete.headers.get("cf-ipcountry") || null
      )
      .run();
  } catch (erreur) {
    // Une panne de la base ne doit rien casser : la page est deja partie.
    console.log(JSON.stringify({
      niveau: "erreur", ou: "journaliser", robot: nom,
      chemin: url.pathname, message: String(erreur),
    }));
  }
}

/** Horodatage attendu par Matomo : « AAAA-MM-JJ HH:MM:SS », en UTC. */
function horodatage(date) {
  const p = (n) => String(n).padStart(2, "0");
  return `${date.getUTCFullYear()}-${p(date.getUTCMonth() + 1)}-${p(date.getUTCDate())} `
       + `${p(date.getUTCHours())}:${p(date.getUTCMinutes())}:${p(date.getUTCSeconds())}`;
}

/**
 * Envoie une requete robot a Matomo, en mode « sans visite ».
 *
 * Le contrat de parametres est celui du worker officiel de Matomo
 * (matomo-org/tracker-cloudflare) : idsite, rec, recMode, url, source, cdt,
 * ua, http_status, bw_bytes, pf_srv, download.
 */
async function mesurer(requete, reponse, dureeMs, env) {
  if (!env.MATOMO_URL || !env.MATOMO_SITE_ID) return;
  if (requete.method.toUpperCase() !== "GET") return;

  if (!HOTES_MESURES.has(new URL(requete.url).hostname)) return;

  const agent = requete.headers.get("user-agent") || "";
  const nom = robot(agent);
  if (!nom) return;
  const corpus = (env.MATOMO_CORPUS ?? "1") !== "0";
  if (!MATOMO_AGENTS.has(nom) && !(corpus && MATOMO_CORPUS.has(nom))) return;

  // Une redirection n'est pas un contenu lu. www.pistes-athle.com renvoie un
  // 301 vers l'apex : la compter ferait deux lignes pour une seule lecture.
  if (reponse.status >= 300 && reponse.status < 400) return;

  const url = requete.url;
  if (HABILLAGE.test(url)) return;

  const p = {
    idsite: env.MATOMO_SITE_ID,
    rec: 1,
    recMode: 1,
    url,
    source: "Cloudflare",
    cdt: horodatage(new Date(Date.now() - dureeMs)),   // l'instant de la demande
    ua: agent,
    http_status: reponse.status,
  };
  const octets = Number.parseInt(reponse.headers.get("content-length") || "", 10);
  if (!Number.isNaN(octets)) p.bw_bytes = octets;
  if (dureeMs >= 0) p.pf_srv = Math.round(dureeMs);
  if (DOCUMENTS.test(url)) p.download = url;

  const cible = new URL(env.MATOMO_URL);
  const chemin = (cible.pathname || "/").replace(/\/matomo\.php$/i, "/");
  cible.pathname = (chemin.endsWith("/") ? chemin : chemin + "/") + "matomo.php";
  cible.search = new URLSearchParams(
    Object.entries(p).map(([k, v]) => [k, String(v)])).toString();
  cible.hash = "";

  const arret = new AbortController();
  const minuteur = setTimeout(() => arret.abort(), MATOMO_DELAI_MS);
  try {
    await fetch(cible.toString(), { method: "GET", signal: arret.signal });
  } catch (erreur) {
    // Une mesure ratee est un trou dans un graphique. La page est deja partie.
    console.log(JSON.stringify({
      niveau: "erreur", ou: "mesurer", robot: nom, message: String(erreur),
    }));
  } finally {
    clearTimeout(minuteur);
  }
}

export default {
  async fetch(requete, env, ctx) {
    // Sur une route, fetch(requete) va a l'origine definie par le DNS de la
    // zone — GitHub Pages — et ne repasse pas par ce Worker.
    const debut = Date.now();
    // Une adresse devinee par un agent est corrigee ici, sans aller a
    // l'origine : GitHub Pages ne sait pas rediriger.
    const devinee = redirection(new URL(requete.url), requete.method.toUpperCase());
    const reponse = devinee || await fetch(requete);
    const duree = Date.now() - debut;

    // Deux sorties independantes : chacune avale ses propres pannes, et
    // aucune des deux ne retarde la reponse deja en route.
    ctx.waitUntil(journaliser(requete, reponse, env));
    ctx.waitUntil(mesurer(requete, reponse, duree, env));

    return reponse;
  },
};
