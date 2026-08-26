/* Où s'entraîner ? — libellés français et anglais.
 *
 * Une seule source de vérité pour tout le texte de l'interface : le HTML porte
 * des attributs data-i18n, app.js pioche ici pour le reste. La langue est
 * déterminée par <html lang> : la version française est servie à la racine,
 * l'anglaise sous /en/.
 */
(() => {
'use strict';

/* Les chaînes injectées via innerHTML proviennent uniquement de ce fichier :
   les entités et le balisage y sont volontaires. */
const FR = {
  code: 'fr',
  locale: 'fr-FR',
  autre_langue: { code: 'en', nom: 'English', chemin: 'en/' },

  ui: {
    titre_page:  "Où s'entraîner ? — Pistes d'athlétisme en France",
    titre_compte: n => `Où s'entraîner ? — ${n} sites d'athlétisme en France`,
    /* Doit rester identique au gabarit « titre_site » de scripts/build_site.py :
       une fiche ouverte dans l'application est mesurée sous le même titre et la
       même URL que sa page statique, sinon le même stade occupe deux lignes dans
       les rapports. */
    titre_fiche: (nom, ville, piste) => piste
      ? `${nom} — piste d'athlétisme à ${ville}`
      : `${nom} — équipement d'athlétisme à ${ville}`,
    marque:      "Où s'entraîner&nbsp;?",
    a_propos:    'À propos',
    recherche_ph: 'Ville, code postal ou nom du stade',
    recherche_al: 'Rechercher',
    effacer:     'Effacer',
    autour:      'Autour de moi',
    filtres:     'Filtres',
    dep_label:   'Filtrer par département (numéro, nom ou code postal)',
    dep_ph:      'Département',
    dep_tous:    'Tous les départements',
    lp_label:    'Filtrer par développement de la piste',
    lp_tous:     'Tour de piste',
    lp_option:   m => `${m} m`,
    lp_estime:   'développement estimé d’après OpenStreetMap, non mesuré sur place',
    onglet_liste: 'Liste',
    onglet_carte: 'Carte',
    chargement:  'Chargement des 7&nbsp;000 sites…',
    erreur_chargement: 'Impossible de charger les données. Rechargez la page.',
    plus:        'Afficher plus de sites',
    vide:        'Aucun site ne correspond à ces critères.<br>' +
                 '<span class="muted">Une piste manque&nbsp;? <a href="#" data-add-track>Signalez-la</a>.</span>',
    fermer:      'Fermer',
    changer_langue: 'Read this site in English',
    nb_sites:    n => `${n} site${n > 1 ? 's' : ''}`,
    nb_avis:     n => `${n} avis`,
    aucun:       'aucun résultat',
    /* Un « aucun résultat » sec est un cul-de-sac : il ne dit pas que la
       réponse existe juste derrière un filtre resté coché. */
    aucun_mais:  n => `aucun résultat ici — ${n} site${n > 1 ? 's' : ''} sans les filtres actifs`,
    horaires_google: 'Horaires sur Google Maps',
    photos_du_site: 'Photos du site',
    aerienne_alt: n => `Vue aérienne de ${n}`,
    aerienne_legende: "Vue aérienne, à défaut de photo du site.",
    aerienne_legende_datee: a => `Vue aérienne de ${a}, à défaut de photo du site.`,
    aerienne_credit: "Elle montre l'implantation, pas l'état des agrès : une bâche signale bien un sautoir, mais pas s'il est praticable, et un tapis rentré ne laisse rien voir. © IGN — BD ORTHO®, Licence Ouverte 2.0",
    note_sur_5:  n => `${n} sur 5`,
    sans_nom:    'Équipement d’athlétisme',

    // liens de pied de page (index.html)
    nav_annuaire: 'Annuaire par département',
    nav_contributeurs: 'Les contributeurs',
    nav_prive:    'Confidentialité',
    nav_source:   'Source des données',
    nav_code:     'Code source',

    // fiche
    itineraire:  'Itinéraire',
    voir_carte:  'Voir sur la carte',
    masquer_carte: 'Masquer la carte',
    plein_ecran: 'Ouvrir en plein écran',
    sec_piste:   'Piste',
    sec_agres:   'Agrès recensés',
    sec_acces:   'Accès & services',
    sec_avis:    'Avis des athlètes',
    kv_revetement: 'Revêtement',
    kv_developpement: 'Développement',
    kv_couloirs: 'Couloirs',
    kv_config:   'Configuration',
    kv_couverte: 'Couverte / indoor',
    kv_plein_air: 'Plein air',
    kv_service:  'Mise en service',
    kv_renovation: 'Dernière rénovation',
    kv_acces_libre: 'Accès libre',
    kv_eclairage: 'Éclairage',
    kv_vestiaires: 'Vestiaires',
    kv_douches:  'Douches',
    kv_sanitaires: 'Sanitaires',
    kv_tribunes: 'Tribunes',
    kv_type_site: 'Type de site',
    kv_horaires: 'Horaires',
    oui:         'Oui',
    non:         'Non',
    non_reserve: 'Non / réservé',
    ouvert_horaires: 'Ouvert au public (horaires)',
    places:      n => `${n} places`,
    enceinte_scolaire: 'Enceinte scolaire',
    site_officiel: 'Site officiel de l’équipement',
    page_dediee: 'Page dédiée de ce site',
    reference_courte: 'Réf. :',
    signaler:    'Signaler une erreur',
    completer:   'Compléter la fiche',
    donner_avis: '✍️ Donner mon avis',
    anonyme:     'Anonyme',
    pas_davis:   'Personne n’a encore décrit ce site. Vous vous y entraînez&nbsp;? Votre retour aidera les autres.',
    incertain:   `Les mentions en pointillés proviennent d’une fiche ministérielle qui indique
                  la présence d’une aire sans préciser sa discipline.
                  <a href="#" data-contrib="complement">Vous connaissez ce site ? Complétez-le.</a>`,
    reference:   (id, source) => `Réf. ${id} · Source : ${source} —
      <a href="https://equipements.sports.gouv.fr/" target="_blank" rel="noopener">Data ES</a>,
      Licence Ouverte 2.0. Les données déclaratives peuvent être incomplètes&nbsp;: vérifiez
      les conditions d’accès avant de vous déplacer.`,

    // géolocalisation
    geo_absente: 'Géolocalisation indisponible sur cet appareil.',
    geo_refusee: 'Autorisez la géolocalisation pour trier les pistes par distance.',
    geo_echec:   'Position introuvable. Utilisez la recherche par ville.',
  },

  sol: {
    synthetique: ['Synthétique (tartan)', 'sol-synthetique'],
    bitume:      ['Bitume / goudron', ''],
    cendree:     ['Cendrée / stabilisé', ''],
    sable:       ['Sable', ''],
    gazon:       ['Gazon', ''],
    naturel:     ['Surface naturelle', ''],
    interieur:   ['Sol intérieur', ''],
  },

  agres: {
    longueur: 'Sautoir longueur', triple: 'Triple saut', hauteur: 'Sautoir hauteur',
    perche: 'Sautoir à la perche', poids: 'Lancer du poids', disque: 'Lancer du disque',
    marteau: 'Lancer du marteau', javelot: 'Lancer du javelot', steeple: 'Steeple',
    saut_indetermine: 'Aire de saut (type inconnu)',
    lancer_indetermine: 'Aire de lancer (type inconnue)',
  },

  sources: ['Data ES (ministère)', 'Data ES + communauté', 'Contribution communautaire'],

  filtres: {
    g_agres: 'Agrès', g_equip: 'Équipements',
    near: '📍 Près de moi', piste: 'Avec piste', synth: 'Synthétique',
    libre: 'Accès libre', perche: 'Perche', long: 'Longueur', haut: 'Hauteur',
    poids: 'Poids', lancer: 'Lancers longs', sauts: 'Un sautoir', ecl: 'Éclairée',
    couv: 'Couverte', vest: 'Vestiaires', noeco: 'Hors enceinte scolaire',
    photo: '📷 Avec photos', avis: '★ Avec avis', noavis: '☆ Sans avis',
  },

  tags: {
    couloirs: n => `${n} couloirs`,
    acces_libre: 'Accès libre',
    couverte: 'Couverte',
    sautoirs: n => `${n} aire${n > 1 ? 's' : ''} de saut`,
    lancers: n => `${n} aire${n > 1 ? 's' : ''} de lancer`,
    scolaire: 'Site scolaire',
  },

  vitrine: {
    titre:        'Les dernières contributions',
    intro:        'Des photos prises sur place, par des gens qui s’y sont entraînés.',
    photos:       n => `${n} photo${n > 1 ? 's' : ''}`,
    par:          a => `par ${a}`,
    le:           d => `le ${d}`,
    top_titre:    'Les contributeurs',
    top_intro:    'Merci à eux : sans photo ni avis, une fiche reste une ligne de tableau.',
    top_lien:     'Voir toutes les contributions',
    top_sites:    n => `${n} site${n > 1 ? 's' : ''}`,
    top_photos:   n => `${n} photo${n > 1 ? 's' : ''}`,
    top_avis:     n => `${n} avis`,
    cta_titre:    'Vous vous entraînez quelque part ?',
    cta_texte:    'Une photo du sautoir, une note sur l’état de la piste, un horaire : ' +
                  'c’est ce que les données publiques n’auront jamais. Cinq minutes suffisent.',
    cta_bouton:   'Ajouter mes photos et mon avis',
    cta_aide:     'Par e-mail ou via GitHub, au choix — aucun compte obligatoire.',
  },

  contrib: {
    titre:      'Contribuer',
    intro:      'Deux façons d’envoyer votre contribution : avec un compte GitHub, ou par e-mail si vous n’en avez pas.',
    types: {
      photo:      'Envoyer des photos',
      avis:       'Donner mon avis',
      correction: 'Signaler une erreur',
      complement: 'Compléter la fiche',
      ajout:      'Ajouter une piste manquante',
    },
    type_label: 'Type de contribution',
    site:       'Site concerné',
    site_ph:    'Nom du stade, adresse, commune',
    note:       'Votre note',
    note_vide:  'Sans note',
    notes: ['1 — à éviter', '2 — vétuste ou mal équipée', '3 — correcte, quelques défauts',
            '4 — très bonne piste', '5 — excellente piste, rien à redire'],
    message:    'Votre message',
    message_ph: {
      photo:      'Ce qu’on voit, et quand c’était. La ligne droite, le sautoir, le revêtement de près : une photo tranche ce qu’aucune donnée déclarative ne dit.',
      avis:       'État de la piste, agrès disponibles, ambiance, accès… Ce que vous auriez aimé savoir avant de venir.',
      correction: 'Affiché : revêtement cendrée\nRéalité : piste refaite en synthétique en 2023',
      complement: 'Agrès réellement présents, horaires d’ouverture, conditions d’accès…',
      ajout:      'Revêtement, nombre de couloirs, agrès, accès. Et les coordonnées GPS si vous les avez.',
    },
    signature:    'Votre nom ou pseudo (facultatif)',
    signe:        'Signé',
    signature_ph: 'Prénom, pseudo, nom de club…',
    photos:     'Photos : joignez-les à votre e-mail, ou glissez-les dans le formulaire GitHub. Évitez celles où des personnes sont reconnaissables.',
    github:     'Envoyer via GitHub',
    github_aide: 'Demande un compte GitHub',
    mail:       'Envoyer par e-mail',
    mail_aide:  'Ouvre votre logiciel de messagerie',
    manque:     'Décrivez votre contribution avant de l’envoyer.',
    manque_site: 'Indiquez au moins le nom et la commune du site.',
    licence:    'En envoyant, vous acceptez que votre contribution et vos photos soient publiées sur le site sous licence ODbL, avec votre crédit.',
    retour:     '← Retour',
  },

  about: ({ repo }) => `
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
      <p>Les sites qui n’ont encore aucune photo affichent une vue aérienne issue de la
         <a href="https://geoservices.ign.fr/" target="_blank" rel="noopener">BD ORTHO® de l’IGN</a>,
         elle aussi sous Licence Ouverte 2.0. Elle montre l’implantation, pas l’état des agrès :
         une orthophoto a souvent plusieurs années, et une bâche de sautoir, très visible du ciel,
         dit qu’un tapis est là sans rien dire de son état — rentré, il ne laisse rien voir du tout.</p>

      <h3>Les données sont déclaratives</h3>
      <p>Elles sont saisies par les propriétaires des installations. Un site peut mentionner
         une « aire de saut » sans préciser s’il s’agit d’un sautoir en longueur ou d’une perche,
         et les conditions d’accès réelles changent souvent. Vérifiez avant de vous déplacer.</p>

      <h3>Contribuer</h3>
      <p>Avec ou sans compte GitHub : le formulaire propose les deux, l’envoi par
         e-mail comme le formulaire GitHub.</p>
      <ul>
        <li><a href="#" data-contrib="correction">Signaler une erreur</a> sur une fiche</li>
        <li><a href="#" data-contrib="complement">Compléter une fiche</a> existante</li>
        <li><a href="#" data-contrib="ajout">Ajouter une piste manquante</a></li>
        <li><a href="https://github.com/${repo}" target="_blank" rel="noopener">Proposer une pull request</a> sur le dépôt</li>
      </ul>

      <h3>Réutiliser les données</h3>
      <p>Le jeu complet est un simple fichier JSON : <a href="data/tracks.json">data/tracks.json</a>.
         Une page HTML par site est publiée sous <code>/site/</code> pour les moteurs de recherche
         et les agents IA, et <a href="llms.txt">llms.txt</a> décrit l’ensemble.</p>

      <h3>Vie privée</h3>
      <p>Aucun cookie, aucune publicité, aucun profil. La mesure d’audience est anonyme et
         ne mesure pas du tout un navigateur qui envoie « Do Not Track ».
         <a href="confidentialite/">Ce qui est mesuré, et ce qui ne l’est pas</a>.</p>

      <p class="src">Fond de carte © contributeurs
         <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>.
         Code source&nbsp;: <a href="https://github.com/${repo}" target="_blank" rel="noopener">github.com/${repo}</a></p>
    </div>`,
};

const EN = {
  code: 'en',
  locale: 'en-GB',
  autre_langue: { code: 'fr', nom: 'Français', chemin: '' },

  ui: {
    titre_page:  'Where to train? — Athletics tracks in France',
    titre_compte: n => `Where to train? — ${n} athletics venues in France`,
    /* Must match the « titre_site » template in scripts/build_site.py — see the
       French note above. */
    titre_fiche: (nom, ville, piste) => piste
      ? `${nom} — athletics track in ${ville}, France`
      : `${nom} — athletics facility in ${ville}, France`,
    marque:      'Where to train?',
    a_propos:    'About',
    recherche_ph: 'Town, postcode or stadium name',
    recherche_al: 'Search',
    effacer:     'Clear',
    autour:      'Near me',
    filtres:     'Filters',
    dep_label:   'Filter by department (number, name or postcode)',
    dep_ph:      'Department',
    dep_tous:    'All departments',
    lp_label:    'Filter by lap length',
    lp_tous:     'Lap length',
    lp_option:   m => `${m} m`,
    lp_estime:   'lap length estimated from OpenStreetMap, not measured on site',
    onglet_liste: 'List',
    onglet_carte: 'Map',
    chargement:  'Loading 7,000 venues…',
    erreur_chargement: 'Could not load the data. Please reload the page.',
    plus:        'Show more venues',
    vide:        'No venue matches these filters.<br>' +
                 '<span class="muted">Is a track missing? <a href="#" data-add-track>Tell us about it</a>.</span>',
    fermer:      'Close',
    changer_langue: 'Lire ce site en français',
    nb_sites:    n => `${n} venue${n > 1 ? 's' : ''}`,
    nb_avis:     n => `${n} review${n > 1 ? 's' : ''}`,
    aucun:       'no results',
    aucun_mais:  n => `no results here — ${n} venue${n > 1 ? 's' : ''} without the active filters`,
    horaires_google: 'Opening hours on Google Maps',
    photos_du_site: 'Photos of the venue',
    aerienne_alt: n => `Aerial view of ${n}`,
    aerienne_legende: 'Aerial view, in the absence of a photo of the venue.',
    aerienne_legende_datee: a => `${a} aerial view, in the absence of a photo of the venue.`,
    aerienne_credit: 'It shows the layout, not the state of the equipment: a cover marks a landing mat without saying whether it is usable, and a mat put away leaves nothing to see. © IGN — BD ORTHO®, Licence Ouverte 2.0',
    note_sur_5:  n => `${n} out of 5`,
    sans_nom:    'Athletics facility',

    nav_annuaire: 'Browse by department',
    nav_contributeurs: 'Contributors',
    nav_prive:    'Privacy',
    nav_source:   'Data source',
    nav_code:     'Source code',

    itineraire:  'Directions',
    voir_carte:  'Show on map',
    masquer_carte: 'Hide map',
    plein_ecran: 'Open full screen',
    sec_piste:   'Track',
    sec_agres:   'Recorded facilities',
    sec_acces:   'Access & amenities',
    sec_avis:    'Athlete reviews',
    kv_revetement: 'Surface',
    kv_developpement: 'Lap length',
    kv_couloirs: 'Lanes',
    kv_config:   'Setting',
    kv_couverte: 'Covered / indoor',
    kv_plein_air: 'Outdoor',
    kv_service:  'Opened',
    kv_renovation: 'Last refurbished',
    kv_acces_libre: 'Free access',
    kv_eclairage: 'Floodlighting',
    kv_vestiaires: 'Changing rooms',
    kv_douches:  'Showers',
    kv_sanitaires: 'Toilets',
    kv_tribunes: 'Stand',
    kv_type_site: 'Venue type',
    kv_horaires: 'Opening hours',
    oui:         'Yes',
    non:         'No',
    non_reserve: 'No / members only',
    ouvert_horaires: 'Open to the public (set hours)',
    places:      n => `${n} seats`,
    enceinte_scolaire: 'School grounds',
    site_officiel: 'Official website of the venue',
    page_dediee: 'Permanent page for this venue',
    reference_courte: 'Ref.:',
    signaler:    'Report an error',
    completer:   'Complete this record',
    donner_avis: '✍️ Write a review',
    anonyme:     'Anonymous',
    pas_davis:   'Nobody has described this venue yet. Do you train here? Your feedback will help others.',
    incertain:   `Dashed entries come from a ministry record that reports an area without
                  naming its discipline.
                  <a href="#" data-contrib="complement">Know this venue? Fill in the details.</a>`,
    reference:   (id, source) => `Ref. ${id} · Source: ${source} —
      <a href="https://equipements.sports.gouv.fr/" target="_blank" rel="noopener">Data ES</a>,
      Licence Ouverte 2.0 (French open licence). Records are self-declared and may be incomplete:
      check access conditions before travelling.`,

    geo_absente: 'Geolocation is not available on this device.',
    geo_refusee: 'Allow location access to sort venues by distance.',
    geo_echec:   'Position unavailable. Try searching by town instead.',
  },

  sol: {
    synthetique: ['Synthetic (tartan)', 'sol-synthetique'],
    bitume:      ['Asphalt / tarmac', ''],
    cendree:     ['Cinder / gravel', ''],
    sable:       ['Sand', ''],
    gazon:       ['Grass', ''],
    naturel:     ['Natural surface', ''],
    interieur:   ['Indoor flooring', ''],
  },

  agres: {
    longueur: 'Long jump pit', triple: 'Triple jump', hauteur: 'High jump area',
    perche: 'Pole vault', poids: 'Shot put', disque: 'Discus',
    marteau: 'Hammer throw', javelot: 'Javelin', steeple: 'Steeplechase',
    saut_indetermine: 'Jump area (type unknown)',
    lancer_indetermine: 'Throwing area (type unknown)',
  },

  sources: ['Data ES (French sports ministry)', 'Data ES + community', 'Community contribution'],

  filtres: {
    g_agres: 'Field events', g_equip: 'Facilities',
    near: '📍 Near me', piste: 'With a track', synth: 'Synthetic',
    libre: 'Free access', perche: 'Pole vault', long: 'Long jump', haut: 'High jump',
    poids: 'Shot put', lancer: 'Long throws', sauts: 'A jump area', ecl: 'Floodlit',
    couv: 'Indoor', vest: 'Changing rooms', noeco: 'Outside school grounds',
    photo: '📷 With photos', avis: '★ With reviews', noavis: '☆ Without reviews',
  },

  tags: {
    couloirs: n => `${n} lanes`,
    acces_libre: 'Free access',
    couverte: 'Indoor',
    sautoirs: n => `${n} jump area${n > 1 ? 's' : ''}`,
    lancers: n => `${n} throwing area${n > 1 ? 's' : ''}`,
    scolaire: 'School venue',
  },

  vitrine: {
    titre:        'Latest contributions',
    intro:        'Photos taken on site, by people who trained there.',
    photos:       n => `${n} photo${n > 1 ? 's' : ''}`,
    par:          a => `by ${a}`,
    le:           d => `on ${d}`,
    top_titre:    'Contributors',
    top_intro:    'Thanks to them: without a photo or a review, a venue is just a row in a table.',
    top_lien:     'See all contributions',
    top_sites:    n => `${n} venue${n > 1 ? 's' : ''}`,
    top_photos:   n => `${n} photo${n > 1 ? 's' : ''}`,
    top_avis:     n => `${n} review${n > 1 ? 's' : ''}`,
    cta_titre:    'Do you train somewhere?',
    cta_texte:    'A photo of the pole vault pit, a note on the state of the track, an opening time: ' +
                  'that is what open data will never hold. Five minutes is enough.',
    cta_bouton:   'Add my photos and review',
    cta_aide:     'By email or through GitHub — no account required.',
  },

  contrib: {
    titre:      'Contribute',
    intro:      'Two ways to send your contribution: with a GitHub account, or by email if you do not have one.',
    types: {
      photo:      'Send photos',
      avis:       'Write a review',
      correction: 'Report an error',
      complement: 'Complete this record',
      ajout:      'Add a missing track',
    },
    type_label: 'Type of contribution',
    site:       'Venue concerned',
    site_ph:    'Stadium name, address, town',
    note:       'Your rating',
    note_vide:  'No rating',
    notes: ['1 — avoid', '2 — run-down or poorly equipped', '3 — decent, a few flaws',
            '4 — very good track', '5 — excellent track, nothing to fault'],
    message:    'Your message',
    message_ph: {
      photo:      'What the pictures show, and when they were taken. The home straight, the jump pit, a close-up of the surface: a photo settles what no declared field will.',
      avis:       'Condition of the track, available equipment, atmosphere, access… What you would have liked to know before going.',
      correction: 'Shown: cinder surface\nReality: resurfaced with synthetic in 2023',
      complement: 'Equipment actually present, opening hours, access conditions…',
      ajout:      'Surface, number of lanes, equipment, access. And GPS coordinates if you have them.',
    },
    signature:    'Your name or nickname (optional)',
    signe:        'Signed by',
    signature_ph: 'First name, nickname, club name…',
    photos:     'Photos: attach them to your email, or drag them into the GitHub form. Avoid photos where people are recognisable.',
    github:     'Send via GitHub',
    github_aide: 'Requires a GitHub account',
    mail:       'Send by email',
    mail_aide:  'Opens your email application',
    manque:     'Describe your contribution before sending it.',
    manque_site: 'Give at least the name and town of the venue.',
    licence:    'By sending, you agree that your contribution and photos may be published on the site under the ODbL licence, with your credit.',
    retour:     '← Back',
  },

  about: ({ repo }) => `
    <div class="about">
      <h2>About</h2>
      <p>An open directory of French athletics tracks and their facilities: long, high and
         pole vault areas, throwing circles, synthetic, cinder or asphalt surfaces,
         floodlighting, changing rooms…</p>

      <h3>Where does the data come from?</h3>
      <p>From <a href="https://equipements.sports.gouv.fr/" target="_blank" rel="noopener">Data ES</a>,
         the national census of sports facilities run by the French ministry for sport, published
         under the <a href="https://github.com/etalab/licence-ouverte/blob/master/LO.md" target="_blank" rel="noopener">Licence
         Ouverte 2.0</a>, plus contributions from the community.</p>
      <p>Venues that do not yet have a photo show an aerial view from the
         <a href="https://geoservices.ign.fr/" target="_blank" rel="noopener">IGN BD ORTHO®</a>,
         also under Licence Ouverte 2.0. It shows the layout, not the state of the equipment:
         orthophotos are often several years old, and a landing mat’s cover — very visible from
         above — says a mat is there without saying anything about its condition; put away, it
         leaves nothing to see at all.</p>

      <h3>The records are self-declared</h3>
      <p>They are filled in by the owners of each facility. A venue may report a “jump area”
         without saying whether it is a long jump runway or a pole vault box, and real access
         conditions change often. Check before you travel.</p>

      <h3>Contributing</h3>
      <p>With or without a GitHub account: the form offers both, sending by email
         as well as the GitHub form.</p>
      <ul>
        <li><a href="#" data-contrib="correction">Report an error</a> on a record</li>
        <li><a href="#" data-contrib="complement">Complete an existing record</a></li>
        <li><a href="#" data-contrib="ajout">Add a missing track</a></li>
        <li><a href="https://github.com/${repo}" target="_blank" rel="noopener">Open a pull request</a> on the repository</li>
      </ul>

      <h3>Reusing the data</h3>
      <p>The whole dataset is a single JSON file: <a href="../data/tracks.json">data/tracks.json</a>.
         One HTML page per venue is published under <code>/en/track/</code> for search engines
         and AI agents, and <a href="../llms.txt">llms.txt</a> describes the whole site.</p>

      <h3>Privacy</h3>
      <p>No cookie, no advertising, no profile. Audience measurement is anonymous, and a browser
         sending “Do Not Track” is not measured at all.
         <a href="privacy/">What is measured, and what is not</a>.</p>

      <p class="src">Map tiles © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>
         contributors. Source code: <a href="https://github.com/${repo}" target="_blank" rel="noopener">github.com/${repo}</a></p>
    </div>`,
};

const LANGUES = { fr: FR, en: EN };
const code = document.documentElement.lang === 'en' ? 'en' : 'fr';

window.I18N = LANGUES[code];
window.I18N_LANG = code;
/* Depuis /en/ les données et les médias sont un cran plus haut. */
window.I18N_BASE = code === 'en' ? '../' : '';
})();
