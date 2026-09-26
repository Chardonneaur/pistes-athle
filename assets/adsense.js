/**
 * Mise en service des blocs AdSense de la page, et mesure de ce qui leur arrive.
 *
 * POURQUOI CE FICHIER EXISTE. Google fait copier, apres chaque <ins>, un
 * <script> en ligne qui appelle « (adsbygoogle = window.adsbygoogle || [])
 * .push({}) ». Suivre cette consigne obligerait a mettre 'unsafe-inline' dans
 * script-src, c'est-a-dire a autoriser n'importe quel script injecte dans la
 * page. Le meme appel, servi depuis ce domaine, ne coute rien a la politique.
 *
 * Un push PAR bloc : c'est ainsi que l'API compte les emplacements a remplir.
 *
 * CE QUE LA MESURE PEUT, ET CE QU'ELLE NE PEUT PAS
 * ------------------------------------------------
 * Elle ne peut PAS voir un clic sur une annonce, et aucune mesure posee dans
 * cette page ne le pourra jamais : l'annonce est une iframe d'un autre domaine,
 * et la politique de meme origine interdit d'observer ce qui s'y passe. Le
 * contournement qui circule — guetter le blur de la fenetre pendant que la
 * souris survole l'iframe — se declenche sur un alt-tab, une notification ou
 * l'ouverture des devtools, rate les clics qui ne font pas perdre le focus, et
 * bricole autour du comportement de clic d'AdSense. On echangerait une donnee
 * fiable contre une donnee fausse : on ne le fait pas.
 *
 * Les clics et les impressions se lisent chez AdSense, qui les rend par
 * PAGE_URL. Voir scripts/revenu_par_page.py, qui joint les deux moitiees.
 *
 * Elle peut, en revanche, mesurer les trois etats que personne d'autre ne rend,
 * et qui sont EN AMONT de l'impression :
 *
 *   servi    — Google a rempli l'emplacement (data-ad-status="filled") ;
 *   vide     — il n'avait rien a y mettre ("unfilled") : AdSense ne comptera
 *              aucune impression, et son rapport restera muet sur ces pages ;
 *   bloque   — le chargeur n'a pas pu s'executer, bloqueur de publicites ou
 *              refus de consentement.
 *
 * Puis un quatrieme, qui n'a de sens que si l'emplacement a ete servi :
 *
 *   vu       — le cadre est entre dans l'ecran.
 *
 * Le tunnel complet devient donc : emplacement VU -> annonce SERVIE ->
 * impression -> clic, les deux premiers ici, les deux derniers chez AdSense.
 * Sans ces deux-la, une page qui ne rapporte rien ne dit pas si elle convertit
 * mal ou si son encart n'est jamais rempli — deux problemes opposes.
 *
 * SANS COOKIE, COMME LE RESTE. Ces evenements passent par le meme traceur que
 * assets/matomo.js, qui appelle disableCookies() et respecte Do Not Track. Rien
 * n'est ecrit sur le poste du visiteur, et la promesse du site tient.
 */
(function () {
  'use strict';

  var blocs = document.querySelectorAll('ins.adsbygoogle');
  if (!blocs.length) return;

  /* Le chemin de la page sert de nom d'evenement : c'est lui qui permettra de
     joindre ces comptes au rapport AdSense, qui rend ses clics par PAGE_URL. */
  var PAGE = location.pathname;

  /* On ne cree PAS _paq s'il n'existe pas. assets/matomo.js sort avant tout
     quand la page n'est pas servie depuis un hote de production : pousser ici
     ressusciterait la file qu'il a refuse d'ouvrir. Pas de traceur, pas de
     mesure — et surtout aucune erreur. */
  function mesurer(etat) {
    if (!window._paq) return;
    window._paq.push(['trackEvent', 'Publicite', etat, PAGE]);
  }

  Array.prototype.forEach.call(blocs, function (bloc) {
    var cadre = bloc.closest('.pub');
    var servi = null;      // null tant que Google n'a pas repondu
    var visible = false;
    var vuAnnonce = false;

    /* « vu » ne se dit que d'un emplacement REMPLI. Un cadre vide est replie,
       donc invisible : compter sa visibilite melangerait deux choses. Les deux
       signaux arrivant dans un ordre imprevisible, on les attend tous deux. */
    function peutEtreVu() {
      if (vuAnnonce || servi !== true || !visible) return;
      vuAnnonce = true;
      mesurer('emplacement vu');
    }

    /* Une annonce non servie laisserait un cadre vide de 250 px surmonte du mot
       « Publicité » — la pire des sorties : on annonce une publicité et on ne
       montre rien. AdSense pose data-ad-status="unfilled" dans ce cas ; on
       replie alors tout le bloc, etiquette comprise.

       Un observateur plutot qu'un delai : le remplissage peut prendre une
       seconde comme dix, et un delai fixe se trompe dans les deux sens. */
    var observateur = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        if (m.attributeName !== 'data-ad-status') return;
        var etat = m.target.getAttribute('data-ad-status');
        if (etat === 'unfilled') {
          servi = false;
          if (cadre) cadre.hidden = true;
          mesurer('emplacement vide');
          observateur.disconnect();
        } else if (etat === 'filled') {
          servi = true;
          mesurer('emplacement servi');
          peutEtreVu();
          observateur.disconnect();
        }
      });
    });
    observateur.observe(bloc, { attributes: true, attributeFilter: ['data-ad-status'] });

    /* La visibilite se mesure sur le cadre et non sur le <ins> : c'est le cadre
       qui porte la hauteur reservee, et c'est lui qu'on replie. Un seuil de
       50 % plutot que le premier pixel — un encart effleure au rebond d'un
       scroll n'a pas ete vu. */
    if (cadre && window.IntersectionObserver) {
      var oeil = new IntersectionObserver(function (entrees) {
        entrees.forEach(function (e) {
          if (!e.isIntersecting) return;
          visible = true;
          oeil.disconnect();
          peutEtreVu();
        });
      }, { threshold: 0.5 });
      oeil.observe(cadre);
    }

    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch (e) {
      /* Chargeur bloque par un bloqueur de publicites, ou refuse par le
         consentement : ce n'est pas une panne du site. On replie le cadre pour
         ne pas laisser un trou etiquete, et on se taise — vis-a-vis du
         visiteur. Vis-a-vis de la mesure, non : la part de visiteurs qui
         bloquent les annonces est exactement ce qu'AdSense ne dira jamais, et
         c'est elle qui explique l'ecart entre les pages vues de Matomo et
         celles d'AdSense. */
      servi = false;
      if (cadre) cadre.hidden = true;
      mesurer('chargeur bloque');
    }
  });
})();
