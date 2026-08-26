/**
 * Tests du Worker : route webhook GitHub, et detection Web Bot Auth.
 *
 *   node --test logs/worker.test.mjs
 *
 * Le depot n'a pas de package.json : Node lit donc les .js en CommonJS, alors
 * que worker.js est un module ES. On en copie une version .mjs dans un dossier
 * temporaire, le temps du test, plutot que d'ajouter au depot un package.json
 * dont wrangler n'a pas besoin.
 */
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { mkdtemp, copyFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const SECRET = "un-secret-de-test";
let worker;
let dossier;

before(async () => {
  dossier = await mkdtemp(join(tmpdir(), "worker-"));
  const copie = join(dossier, "worker.mjs");
  await copyFile(new URL("./worker.js", import.meta.url), copie);
  worker = (await import(pathToFileURL(copie).href)).default;
});

after(async () => { await rm(dossier, { recursive: true, force: true }); });

/** L'en-tete que GitHub calcule sur le corps, avec le secret partage. */
function signer(corps, secret = SECRET) {
  return "sha256=" + createHmac("sha256", secret).update(corps).digest("hex");
}

function requete(corps, { type = "issues", signature, methode = "POST" } = {}) {
  const entetes = { "content-type": "application/json", "x-github-event": type };
  if (signature !== null) entetes["x-hub-signature-256"] = signature ?? signer(corps);
  return new Request("https://pistes-athle.com/_hooks/github", {
    method: methode,
    headers: entetes,
    body: methode === "POST" ? corps : undefined,
  });
}

/** Appelle le Worker en capturant les appels sortants vers Matomo. */
async function appeler(req, env = { GITHUB_WEBHOOK_SECRET: SECRET, MATOMO_URL: "https://matomo.test/", MATOMO_SITE_ID: "149" }) {
  const envois = [];
  const vrai = globalThis.fetch;
  globalThis.fetch = async (url) => { envois.push(String(url)); return new Response(null, { status: 204 }); };
  const attentes = [];
  const ctx = { waitUntil: (p) => attentes.push(p) };
  try {
    const reponse = await worker.fetch(req, env, ctx);
    await Promise.all(attentes);
    return { reponse, envois };
  } finally {
    globalThis.fetch = vrai;
  }
}

const ISSUE_OUVERTE = JSON.stringify({
  action: "opened",
  issue: { html_url: "https://github.com/Chardonneaur/pistes-athle/issues/42", title: "Photo de Pornic", labels: [{ name: "photo" }] },
});

test("refuse un GET sur la route", async () => {
  const { reponse } = await appeler(requete("", { methode: "GET", signature: null }));
  assert.equal(reponse.status, 405);
  assert.equal(reponse.headers.get("allow"), "POST");
});

test("refuse si aucun secret n'est configure — ne jamais enregistrer sans verifier", async () => {
  const { reponse, envois } = await appeler(requete(ISSUE_OUVERTE), { MATOMO_URL: "https://matomo.test/", MATOMO_SITE_ID: "149" });
  assert.equal(reponse.status, 503);
  assert.equal(envois.length, 0);
});

test("refuse une signature absente", async () => {
  const { reponse, envois } = await appeler(requete(ISSUE_OUVERTE, { signature: null }));
  assert.equal(reponse.status, 401);
  assert.equal(envois.length, 0);
});

test("refuse une signature calculee avec un autre secret", async () => {
  const { reponse, envois } = await appeler(requete(ISSUE_OUVERTE, { signature: signer(ISSUE_OUVERTE, "mauvais-secret") }));
  assert.equal(reponse.status, 401);
  assert.equal(envois.length, 0);
});

test("refuse une signature de longueur differente sans planter", async () => {
  const { reponse } = await appeler(requete(ISSUE_OUVERTE, { signature: "sha256=court" }));
  assert.equal(reponse.status, 401);
});

test("refuse un corps modifie apres signature", async () => {
  const signature = signer(ISSUE_OUVERTE);
  const trafique = ISSUE_OUVERTE.replace("Pornic", "Ailleurs");
  const { reponse, envois } = await appeler(requete(trafique, { signature }));
  assert.equal(reponse.status, 401);
  assert.equal(envois.length, 0);
});

test("repond au ping de creation du webhook", async () => {
  const corps = JSON.stringify({ zen: "Non-blocking is better." });
  const { reponse, envois } = await appeler(requete(corps, { type: "ping" }));
  assert.equal(reponse.status, 204);
  assert.equal(envois.length, 0);
});

test("une issue ouverte devient un evenement Matomo", async () => {
  const { reponse, envois } = await appeler(requete(ISSUE_OUVERTE));
  assert.equal(reponse.status, 204);
  assert.equal(envois.length, 1);
  const p = new URL(envois[0]).searchParams;
  assert.equal(new URL(envois[0]).pathname, "/matomo.php");
  assert.equal(p.get("idsite"), "149");
  assert.equal(p.get("rec"), "1");
  assert.equal(p.get("e_c"), "Contribution");
  assert.equal(p.get("e_a"), "Issue ouverte");
  assert.equal(p.get("e_n"), "photo");
  assert.equal(p.get("uid"), "github-webhook");
  assert.equal(p.get("url"), "https://github.com/Chardonneaur/pistes-athle/issues/42");
  // recMode n'ouvrirait pas de visite, donc ne convertirait aucun objectif.
  assert.equal(p.get("recMode"), null);
});

test("une issue sans etiquette retombe sur son titre", async () => {
  const corps = JSON.stringify({ action: "opened", issue: { html_url: "https://x/1", title: "Correction Machecoul", labels: [] } });
  const { envois } = await appeler(requete(corps));
  assert.equal(new URL(envois[0]).searchParams.get("e_n"), "Correction Machecoul");
});

test("une pull request fusionnee est distinguee d'une pull request ouverte", async () => {
  const fusionnee = JSON.stringify({ action: "closed", pull_request: { merged: true, title: "Visite de Pornic", html_url: "https://x/9" } });
  const { envois } = await appeler(requete(fusionnee, { type: "pull_request" }));
  assert.equal(new URL(envois[0]).searchParams.get("e_a"), "Pull request fusionnee");

  const ouverte = JSON.stringify({ action: "opened", pull_request: { merged: false, title: "Visite de Pornic", html_url: "https://x/9" } });
  const b = await appeler(requete(ouverte, { type: "pull_request" }));
  assert.equal(new URL(b.envois[0]).searchParams.get("e_a"), "Pull request ouverte");
});

test("une pull request fermee sans fusion n'est pas une contribution", async () => {
  const corps = JSON.stringify({ action: "closed", pull_request: { merged: false, title: "Abandonnee", html_url: "https://x/9" } });
  const { reponse, envois } = await appeler(requete(corps, { type: "pull_request" }));
  assert.equal(reponse.status, 204);
  assert.equal(envois.length, 0);
});

test("les evenements hors sujet sont ignores sans erreur", async () => {
  const corps = JSON.stringify({ action: "created", comment: { body: "merci" } });
  const { reponse, envois } = await appeler(requete(corps, { type: "issue_comment" }));
  assert.equal(reponse.status, 204, "un 4xx ferait rejouer la livraison par GitHub");
  assert.equal(envois.length, 0);
});

test("refuse une charge annoncee trop grande avant de la lire", async () => {
  const req = new Request("https://pistes-athle.com/_hooks/github", {
    method: "POST",
    headers: { "x-github-event": "issues", "x-hub-signature-256": signer(ISSUE_OUVERTE), "content-length": "50000000" },
    body: ISSUE_OUVERTE,
  });
  const { reponse } = await appeler(req);
  assert.equal(reponse.status, 413);
});

test("refuse un JSON illisible malgre une signature valide", async () => {
  const corps = "{ceci n'est pas du JSON";
  const { reponse, envois } = await appeler(requete(corps));
  assert.equal(reponse.status, 400);
  assert.equal(envois.length, 0);
});

test("une page du site n'est pas interceptee par la route", async () => {
  const vrai = globalThis.fetch;
  globalThis.fetch = async () => new Response("page", { status: 200 });
  try {
    const ctx = { waitUntil: () => {} };
    const reponse = await worker.fetch(
      new Request("https://pistes-athle.com/site/c-piste-casson/"), {}, ctx);
    assert.equal(reponse.status, 200);
    assert.equal(await reponse.text(), "page");
  } finally {
    globalThis.fetch = vrai;
  }
});

/* ------------------------------------------------------------------ *
 * Web Bot Auth : l'agent qui pilote un navigateur                     *
 * ------------------------------------------------------------------ */

const CHROME = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
             + "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36";

/** Appelle le Worker sur une page du site en capturant les ecritures en base. */
async function lirePage(entetes = {}) {
  const inserts = [];
  const env = {
    DB: { prepare: () => ({ bind: (...a) => ({ run: async () => { inserts.push(a); } }) }) },
  };
  const vrai = globalThis.fetch;
  globalThis.fetch = async () => new Response("page", { status: 200 });
  const attentes = [];
  try {
    await worker.fetch(
      new Request("https://pistes-athle.com/site/c-piste-casson/", { headers: entetes }),
      env, { waitUntil: (p) => attentes.push(p) });
    await Promise.all(attentes);
  } finally {
    globalThis.fetch = vrai;
  }
  // colonnes : vu_le, robot, agent, hote, chemin, gabarit, statut, pays
  return inserts.map((a) => ({ robot: a[1], agent: a[2], chemin: a[4] }));
}

test("un agent signe est journalise malgre un user-agent de Chrome", async () => {
  const lignes = await lirePage({
    "user-agent": CHROME,
    "signature-agent": '"https://chatgpt.com"',
    "signature": "sig1=:AAAA:",
    "signature-input": 'sig1=("@authority");created=1',
  });
  assert.equal(lignes.length, 1);
  assert.equal(lignes[0].robot, "ChatGPT");
  assert.equal(lignes[0].agent, CHROME, "le user-agent reel est conserve tel quel");
  assert.equal(lignes[0].chemin, "/site/c-piste-casson/");
});

test("Signature-Agent suffit : c'est lui qui porte l'identite", async () => {
  const lignes = await lirePage({ "user-agent": CHROME, "signature-agent": '"https://claude.com"' });
  assert.equal(lignes[0].robot, "Claude");
});

test("un signataire inconnu est garde, prefixe, pour qu'on le decouvre", async () => {
  const lignes = await lirePage({ "user-agent": CHROME, "signature-agent": '"https://agent.exemple.fr"' });
  assert.equal(lignes[0].robot, "signe:agent.exemple.fr");
});

test("les guillemets et le www sont optionnels", async () => {
  const a = await lirePage({ "user-agent": CHROME, "signature-agent": "https://www.chatgpt.com" });
  assert.equal(a[0].robot, "ChatGPT");
  const b = await lirePage({ "user-agent": CHROME, "signature-agent": '"chatgpt.com"' });
  assert.equal(b[0].robot, "ChatGPT");
});

test("un Signature-Agent illisible ne journalise rien", async () => {
  assert.equal((await lirePage({ "user-agent": CHROME, "signature-agent": '""' })).length, 0);
  assert.equal((await lirePage({ "user-agent": CHROME, "signature-agent": "  " })).length, 0);
});

test("un navigateur sans signature reste invisible — la promesse du site", async () => {
  assert.equal((await lirePage({ "user-agent": CHROME })).length, 0);
});

test("un robot classique est toujours journalise sous son nom", async () => {
  const lignes = await lirePage({ "user-agent": "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)" });
  assert.equal(lignes[0].robot, "GPTBot");
});

test("le user-agent l'emporte sur la signature quand les deux sont la", async () => {
  const lignes = await lirePage({
    "user-agent": "Mozilla/5.0 (compatible; ClaudeBot/1.0)",
    "signature-agent": '"https://chatgpt.com"',
  });
  assert.equal(lignes[0].robot, "ClaudeBot", "un crawler declare reste range sous son nom de crawler");
});
