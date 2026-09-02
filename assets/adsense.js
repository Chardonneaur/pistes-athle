/**
 * Mise en service des blocs AdSense de la page.
 *
 * POURQUOI CE FICHIER EXISTE. Google fait copier, apres chaque <ins>, un
 * <script> en ligne qui appelle « (adsbygoogle = window.adsbygoogle || [])
 * .push({}) ». Suivre cette consigne obligerait a mettre 'unsafe-inline' dans
 * script-src, c'est-a-dire a autoriser n'importe quel script injecte dans la
 * page. Le meme appel, servi depuis ce domaine, ne coute rien a la politique.
 *
 * Un push PAR bloc : c'est ainsi que l'API compte les emplacements a remplir.
 */
(function () {
  'use strict';

  var blocs = document.querySelectorAll('ins.adsbygoogle');
  if (!blocs.length) return;

  /* Une annonce non servie laisserait un cadre vide de 250 px surmonte du mot
     « Publicité » — la pire des sorties : on annonce une publicité et on ne
     montre rien. AdSense pose data-ad-status="unfilled" dans ce cas ; on replie
     alors tout le bloc, etiquette comprise.

     Un observateur plutot qu'un delai : le remplissage peut prendre une
     seconde comme dix, et un delai fixe se trompe dans les deux sens. */
  var observateur = new MutationObserver(function (mutations) {
    mutations.forEach(function (m) {
      if (m.attributeName !== 'data-ad-status') return;
      var ins = m.target;
      if (ins.getAttribute('data-ad-status') === 'unfilled') {
        var cadre = ins.closest('.pub');
        if (cadre) cadre.hidden = true;
      }
    });
  });

  Array.prototype.forEach.call(blocs, function (bloc) {
    observateur.observe(bloc, { attributes: true, attributeFilter: ['data-ad-status'] });
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch (e) {
      /* Chargeur bloque par un bloqueur de publicites, ou refuse par le
         consentement : ce n'est pas une panne du site. On replie le cadre pour
         ne pas laisser un trou etiquete, et on se taise. */
      var cadre = bloc.closest('.pub');
      if (cadre) cadre.hidden = true;
    }
  });
})();
