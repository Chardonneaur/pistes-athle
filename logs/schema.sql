-- Passages de robots devant pistes-athle.com.
--
-- Aucune donnee personnelle : ni adresse IP, ni identifiant, ni visite humaine.
-- `pays` vient de l'en-tete CF-IPCountry, qui designe le centre de donnees d'ou
-- le robot interroge le site, pas une personne.

CREATE TABLE IF NOT EXISTS visites_robots (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  vu_le    TEXT    NOT NULL,   -- ISO 8601, UTC
  robot    TEXT    NOT NULL,   -- nom canonique : Googlebot, GPTBot, ClaudeBot...
  agent    TEXT    NOT NULL,   -- user-agent brut, tronque a 300 caracteres
  hote     TEXT    NOT NULL,   -- pistes-athle.com ou www.pistes-athle.com
  chemin   TEXT    NOT NULL,
  gabarit  TEXT    NOT NULL,   -- /site/, /ville/, /en/track/, /sitemap.xml...
  statut   INTEGER NOT NULL,
  pays     TEXT
);

-- « Quand tel robot est-il passe, et dans quel ordre ? » : la question de l'etude.
CREATE INDEX IF NOT EXISTS idx_robot_date  ON visites_robots (robot, vu_le);
-- « Quels types de page ont ete explores, et par qui ? »
CREATE INDEX IF NOT EXISTS idx_gabarit     ON visites_robots (gabarit, robot);
-- « Cette page precise a-t-elle deja ete vue ? »
CREATE INDEX IF NOT EXISTS idx_chemin      ON visites_robots (chemin);
