/* Mesure d'audience — Matomo Cloud, site 149.
 *
 * POURQUOI CE FICHIER EXISTE
 * --------------------------
 * Le projet pose une question : les agents IA explorent-ils cet annuaire, et
 * envoient-ils des gens dessus ? Sans mesure, la réponse reste une intuition.
 * Ce fichier répond à la moitié « humaine » de la question — les visiteurs
 * arrivés depuis ChatGPT, Perplexity, Claude ou Gemini, que Matomo classe
 * tout seul dans ses rapports « Assistants IA » d'après le référent.
 *
 * L'autre moitié — les robots qui viennent lire les pages sans jamais ouvrir
 * un navigateur — n'est PAS mesurable ici : un crawler n'exécute pas ce
 * script. Elle se mesure au bord du réseau, dans logs/worker.js.
 *
 * SANS COOKIE, DONC SANS BANDEAU
 * ------------------------------
 * disableCookies() est appelé avant toute mesure : aucun cookie n'est déposé,
 * aucun identifiant ne survit à la visite. C'est ce qui permet de mesurer
 * l'audience sans demander de consentement, et de rester fidèle à ce que le
 * site annonce depuis le début. Ne pas retirer cette ligne sans ajouter, le
 * même jour, une demande de consentement.
 *
 * Le fichier est chargé par index.html et par toutes les pages statiques
 * (scripts/build_site.py, scripts/build_api.py) : c'est le seul endroit où
 * cette configuration existe.
 */
(function () {
  /* Le tracker ne doit connaître que le site publié. Sans ce garde, une page
     ouverte depuis localhost pendant une vérification part dans les rapports,
     où elle se range sous son chemin comme si elle avait été lue en ligne —
     VU LE 25/08/2026 : quatre vues de localhost:8777/confidentialite/, qui
     ressemblent à s'y méprendre à du trafic sur la page en ligne. */
  var HOTES = ['pistes-athle.com', 'www.pistes-athle.com', 'chardonneaur.github.io'];
  if (HOTES.indexOf(location.hostname) === -1) return;

  var HOTE = 'https://ronanchardonneau.matomo.cloud/';
  var SITE = '149';

  var _paq = (window._paq = window._paq || []);

  /* Avant tout le reste : rien ne doit être écrit sur le poste du visiteur. */
  _paq.push(['disableCookies']);

  /* Un navigateur qui envoie l'en-tête « Do Not Track » n'est pas mesuré du
     tout. On y perd quelques visites ; on y gagne de pouvoir écrire, sans
     réserve, que le site respecte le refus quand il est exprimé. */
  _paq.push(['setDoNotTrack', true]);

  _paq.push(['setTrackerUrl', HOTE + 'matomo.php']);
  _paq.push(['setSiteId', SITE]);

  /* Une visite qui dure est un signal : elle distingue l'agent qui rebondit du
     lecteur qui lit la fiche. Sans ce battement, toute page vue en dernier
     compte pour zéro seconde. */
  _paq.push(['enableHeartBeatTimer', 15]);

  /* Le titre est figé ici, avant que l'application ne le réécrive avec le
     nombre de sites une fois le JSON chargé (assets/app.js). Sans ça, la même
     page d'accueil arrive dans les rapports sous deux titres, selon lequel du
     tracker ou du chargement des données a fini le premier — VU LE 25/08/2026 :
     « — Pistes d'athlétisme en France » et « — 7002 sites d'athlétisme en
     France » comptés comme deux pages. */
  _paq.push(['setDocumentTitle', document.title]);

  _paq.push(['trackPageView']);

  /* Les liens sortants disent où l'annuaire renvoie : OpenStreetMap, le site
     de la mairie, l'itinéraire. C'est la mesure de son utilité réelle. */
  _paq.push(['enableLinkTracking']);

  var d = document;
  var g = d.createElement('script');
  var s = d.getElementsByTagName('script')[0];
  g.async = true;
  g.src = 'https://cdn.matomo.cloud/ronanchardonneau.matomo.cloud/matomo.js';
  s.parentNode.insertBefore(g, s);
})();
