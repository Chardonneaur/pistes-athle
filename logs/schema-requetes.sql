-- Etat de la boucle Search Console -> fiches de pistes-athle.com.
--
-- Base « pistes-athle-seo », volontairement distincte de « pistes-athle-logs » :
-- celle-ci pilote l'editorial, l'autre observe les robots pour l'etude. Les
-- melanger obligerait a expliquer la table intruse le jour ou l'etude est
-- publiee, et a defendre une promesse — « aucune visite humaine » — dans une
-- base qui ne parle plus que de robots.
--
-- Aucune donnee personnelle : Search Console ne livre que des requetes agregees,
-- et masque justement celles qui sont trop rares pour l'etre.
--
-- Application du schema :
--   npx wrangler d1 execute pistes-athle-seo --remote --file logs/schema-requetes.sql

-- Une ligne par QUESTION POSEE, jamais par formulation.
--
-- « piste tartan lorient », « revetement stade lorient » et « lorient piste
-- synthetique ? » sont trois manieres de poser la meme question au meme endroit.
-- Sans cette normalisation, la boucle rouvrirait chaque matin un dossier deja
-- traite : la longue traine reformule sans fin, elle ne demande pas autre chose.
-- D'ou la cle « cible|intention », et non la requete brute — c'est elle qui rend
-- tenable le declenchement des la premiere impression.
CREATE TABLE IF NOT EXISTS requetes_gsc (
  cle           TEXT PRIMARY KEY,  -- « <cible>|<intention> »
  cible         TEXT NOT NULL,     -- id de fiche, « ville:<slug> », « dep:<code> »,
                                   -- « critere:<chemin> », ou « inconnu »
  intention     TEXT NOT NULL,     -- revetement, couvert, acces, horaires,
                                   -- tarif, agres, distance, contact, photos,
                                   -- fiche, existence
                                   -- « fiche » = le nom du stade tape tel quel,
                                   -- de loin le cas le plus frequent ;
                                   -- « existence » = un lieu qu'aucune fiche
                                   -- ne couvre, le signal le plus precieux.
  requete       TEXT NOT NULL,     -- une formulation, gardee en exemple
  variantes     INTEGER NOT NULL DEFAULT 1,   -- formulations distinctes vues
  page          TEXT,              -- page d'atterrissage rendue par GSC
  impressions   INTEGER NOT NULL DEFAULT 0,   -- cumul sur la fenetre relevee
  position      REAL,              -- position moyenne, sert a ordonner la file
  vu_le         TEXT NOT NULL,     -- premiere impression connue, ISO 8601
  revu_le       TEXT NOT NULL,     -- dernier releve quotidien
  statut        TEXT NOT NULL DEFAULT 'file'
                CHECK (statut IN ('file','traite','sans-source','candidat','hors-sujet')),
  -- « file » est le seul statut non terminal : tout le reste ferme le dossier.
  -- Seul « sans-source » se rouvre, et a deux conditions, l'une ou l'autre,
  -- toutes deux exigeant d'abord que les impressions aient triple :
  --
  --   a. elles atteignent 10 depuis le gel. La question n'est plus rare, et le
  --      « rien a ecrire » avait ete juge quand elle valait deux impressions ;
  --   b. ou 90 jours ont passe, au cas ou une source soit parue entre-temps.
  --
  -- Le (a) manquait, et il coutait cher. « complexe sportif pierre minssieux »
  -- est passe de 2 a 36 impressions en quatre jours, position 8,4, zero clic,
  -- premiere requete du site en clics manques : la seule regle du temps le
  -- gardait ferme jusqu'a fin novembre. Un triplement seul ne suffit pas non
  -- plus : de 1 a 3 impressions, c'est du bruit. D'ou le plancher.
  detail        TEXT,              -- URL de la PR, source citee, ou raison
  rouvert_le    TEXT,              -- derniere reouverture automatique, ISO 8601
                                   -- (colonne ajoutee le 2026-09-04 ; sur une
                                   -- base existante : ALTER TABLE requetes_gsc
                                   -- ADD COLUMN rouvert_le TEXT;)

  -- L'etat de la question AU MOMENT ou on l'a fermee. Sans ce gel, il est
  -- impossible de savoir si le traitement a servi a quelque chose : le releve
  -- quotidien ecrase impressions et position, et revu_le avec elles. On saurait
  -- « la position est de 3,1 » sans pouvoir dire d'ou elle vient.
  impressions_avant INTEGER,
  position_avant    REAL,
  traite_le         TEXT             -- date du gel, ISO 8601
);

-- Le gel est refait a chaque reouverture, et c'est voulu : sans cela, un
-- dossier rouvert a 36 impressions garderait un gel a 2, se verrait triple
-- des le lendemain, et rouvrirait chaque matin sans fin. Le gel dit donc
-- « l'etat de la question la derniere fois qu'on l'a prise en main ». La
-- raison de la fermeture precedente, elle, reste dans `detail` jusqu'a ce
-- qu'un nouveau verdict la remplace.

-- La file du jour se lit par statut puis par position : l'index porte les deux.
CREATE INDEX IF NOT EXISTS idx_requetes_file   ON requetes_gsc (statut, position);
-- « Que sait-on deja qu'on demande sur cette installation ? »
CREATE INDEX IF NOT EXISTS idx_requetes_cible  ON requetes_gsc (cible);
-- La reouverture des dossiers sans source balaie par statut et par date.
CREATE INDEX IF NOT EXISTS idx_requetes_revu   ON requetes_gsc (statut, revu_le);

-- Un passage quotidien du releve.
--
-- Une boucle qui n'ecrit que les jours ou elle a quelque chose a dire est
-- silencieuse pour deux raisons opposees : rien a faire, ou plus rien qui
-- tourne. Cette table est le seul endroit d'ou l'on distingue les deux.
CREATE TABLE IF NOT EXISTS passages (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  lance_le       TEXT    NOT NULL, -- ISO 8601, UTC
  fenetre        TEXT    NOT NULL, -- « 2026-08-22 -> 2026-08-29 »
  appels_gsc     INTEGER NOT NULL, -- appels d'API reellement emis
  couples_vus    INTEGER NOT NULL, -- couples (requete, page) rendus par GSC
  cles_neuves    INTEGER NOT NULL, -- clefs jamais vues avant ce passage
  cles_majes     INTEGER NOT NULL, -- clefs deja connues, reactualisees
  file_restante  INTEGER NOT NULL, -- ce qui attend un traitement
  note           TEXT              -- panne, plafond atteint, « rien a faire »...
);

CREATE INDEX IF NOT EXISTS idx_passages_date ON passages (lance_le);

-- Le gel doit etre automatique, pas une discipline.
--
-- Un agent qui ferme un dossier a dix choses en tete ; relever les valeurs
-- d'avant est celle qu'on oublie, et elle ne se rattrape jamais — le releve du
-- lendemain a deja ecrase la ligne. Le declencheur l'ecrit a sa place, une
-- seule fois, au passage de « file » a un statut terminal.
CREATE TRIGGER IF NOT EXISTS gel_au_traitement
AFTER UPDATE OF statut ON requetes_gsc
WHEN OLD.statut = 'file' AND NEW.statut <> 'file' AND NEW.traite_le IS NULL
BEGIN
  UPDATE requetes_gsc
     SET impressions_avant = NEW.impressions,
         position_avant    = NEW.position,
         traite_le         = date('now')
   WHERE cle = NEW.cle;
END;
