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
 */

// Le nom canonique du robot, et le fragment d'user-agent qui le designe.
// L'ordre compte : « Google-Extended » doit etre teste avant « Googlebot »,
// sinon le premier tomberait dans le second.
const ROBOTS = [
  ["GPTBot", "gptbot"],
  ["OAI-SearchBot", "oai-searchbot"],
  ["ChatGPT-User", "chatgpt-user"],
  ["ClaudeBot", "claudebot"],
  ["Claude-User", "claude-user"],
  ["Claude-SearchBot", "claude-searchbot"],
  ["anthropic-ai", "anthropic-ai"],
  ["PerplexityBot", "perplexitybot"],
  ["Perplexity-User", "perplexity-user"],
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
  ["cohere-ai", "cohere-ai"],
  ["YouBot", "youbot"],
  ["DuckDuckBot", "duckduckbot"],
  ["Qwantify", "qwantify"],
  ["YandexBot", "yandexbot"],
  ["Diffbot", "diffbot"],
  ["ImagesiftBot", "imagesiftbot"],
];

const AGENT_MAX = 300;

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

export default {
  async fetch(requete, env, ctx) {
    // Sur une route, fetch(requete) va a l'origine definie par le DNS de la
    // zone — GitHub Pages — et ne repasse pas par ce Worker.
    const reponse = await fetch(requete);
    ctx.waitUntil(journaliser(requete, reponse, env));
    return reponse;
  },
};
