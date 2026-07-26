"""
SODIPAC - Migration de schéma v3
================================

Ajoute, de façon **additive et non destructive**, tout ce qui manquait au
schéma v2 :

  1. Multi-dépôt              → depots, stock_depot
  2. Compatibilité véhicule   → vehicules_modeles, produit_compatibilite
  3. Références croisées      → produit_references
  4. CUMP + historique prix   → produits.cump, prix_historique
  5. Achats fournisseurs      → commandes, commandes_details
  6. Créances / règlements    → reglements, ventes.date_echeance
  7. Inventaire physique      → inventaires, inventaire_lignes
  8. Retours / avoirs         → retours, retours_details
  9. Données de pilotage      → colonnes produits/clients/fournisseurs
 10. Index de performance manquants

Appelé par database.init_database(). Idempotent : peut tourner à chaque
démarrage sans effet de bord.
"""

from __future__ import annotations

SCHEMA_VERSION = 3


# ─── Helpers (dupliqués volontairement pour éviter un import circulaire) ───

def _colonnes(cursor, table) -> set:
    return {r[1] for r in cursor.execute(f"PRAGMA table_info({table})")}


def _ajouter_colonne(cursor, table, colonne, definition) -> bool:
    if colonne not in _colonnes(cursor, table):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")
        return True
    return False


# ─── 1. NOUVELLES TABLES ──────────────────────────────

TABLES = """
/* ═══ MULTI-DÉPÔT ═══ */

CREATE TABLE IF NOT EXISTS depots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,
    nom             TEXT NOT NULL,
    type            TEXT DEFAULT 'boutique'
                    CHECK(type IN ('boutique','reserve','magasin','vehicule','autre')),
    adresse         TEXT DEFAULT '',
    responsable     TEXT DEFAULT '',
    telephone       TEXT DEFAULT '',
    autorise_vente  INTEGER DEFAULT 1,   -- 0 = stockage seul (pas de vente directe)
    par_defaut      INTEGER DEFAULT 0,
    actif           INTEGER DEFAULT 1,
    ordre           INTEGER DEFAULT 0,
    date_creation   TIMESTAMP DEFAULT (datetime('now','localtime'))
);

/* Stock réel par produit ET par dépôt. Source de vérité du stock. */
CREATE TABLE IF NOT EXISTS stock_depot (
    produit_id      INTEGER NOT NULL,
    depot_id        INTEGER NOT NULL,
    quantite        INTEGER NOT NULL DEFAULT 0,
    stock_mini      INTEGER DEFAULT 0,
    stock_maxi      INTEGER DEFAULT 0,
    emplacement     TEXT DEFAULT '',      -- ex: "Allée B - Étagère 3"
    date_modification TIMESTAMP DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (produit_id, depot_id),
    FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE CASCADE,
    FOREIGN KEY (depot_id)   REFERENCES depots(id)   ON DELETE CASCADE
);

/* ═══ COMPATIBILITÉ VÉHICULE ═══ */

CREATE TABLE IF NOT EXISTS vehicules_modeles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    marque          TEXT NOT NULL,
    modele          TEXT NOT NULL,
    motorisation    TEXT DEFAULT '',      -- ex: "1.4 D-4D", "2.0 essence"
    carburant       TEXT DEFAULT '',      -- essence / diesel / hybride
    annee_debut     INTEGER DEFAULT 0,
    annee_fin       INTEGER DEFAULT 0,    -- 0 = encore produit
    notes           TEXT DEFAULT '',
    UNIQUE (marque, modele, motorisation, annee_debut)
);

CREATE TABLE IF NOT EXISTS produit_compatibilite (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    produit_id      INTEGER NOT NULL,
    modele_id       INTEGER NOT NULL,
    position        TEXT DEFAULT '',      -- avant / arrière / gauche / droite
    certitude       TEXT DEFAULT 'confirme'
                    CHECK(certitude IN ('confirme','probable','a_verifier')),
    notes           TEXT DEFAULT '',
    UNIQUE (produit_id, modele_id, position),
    FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE CASCADE,
    FOREIGN KEY (modele_id)  REFERENCES vehicules_modeles(id) ON DELETE CASCADE
);

/* ═══ RÉFÉRENCES CROISÉES / ÉQUIVALENCES ═══ */

CREATE TABLE IF NOT EXISTS produit_references (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    produit_id      INTEGER NOT NULL,
    reference       TEXT NOT NULL,
    type            TEXT DEFAULT 'equivalent'
                    CHECK(type IN ('oem','equivalent','fournisseur','ancienne','code_barres')),
    marque          TEXT DEFAULT '',      -- marque de l'équivalent (SKF, Bosch…)
    notes           TEXT DEFAULT '',
    UNIQUE (produit_id, reference, type),
    FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE CASCADE
);

/* ═══ HISTORIQUE DES PRIX ═══ */

CREATE TABLE IF NOT EXISTS prix_historique (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    produit_id      INTEGER NOT NULL,
    type_prix       TEXT NOT NULL CHECK(type_prix IN ('achat','vente','cump')),
    ancien_prix     REAL DEFAULT 0,
    nouveau_prix    REAL DEFAULT 0,
    origine         TEXT DEFAULT '',      -- 'manuel', 'reception', 'import'
    tiers           TEXT DEFAULT '',      -- fournisseur ou client concerné
    reference_doc   TEXT DEFAULT '',
    utilisateur     TEXT DEFAULT '',
    date_prix       TIMESTAMP DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE CASCADE
);

/* ═══ ACHATS / COMMANDES FOURNISSEUR ═══ */

CREATE TABLE IF NOT EXISTS commandes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    numero              TEXT DEFAULT '',
    fournisseur_id      INTEGER,
    depot_id            INTEGER,          -- dépôt de réception
    statut              TEXT DEFAULT 'brouillon'
                        CHECK(statut IN ('brouillon','envoyee','partielle','recue','annulee')),
    sous_total          REAL DEFAULT 0,
    remise              REAL DEFAULT 0,
    frais               REAL DEFAULT 0,   -- transport, douane
    total               REAL DEFAULT 0,
    montant_paye        REAL DEFAULT 0,
    date_commande       TIMESTAMP DEFAULT (datetime('now','localtime')),
    date_prevue         DATE,
    date_reception      TIMESTAMP,
    notes               TEXT DEFAULT '',
    utilisateur         TEXT DEFAULT '',
    FOREIGN KEY (fournisseur_id) REFERENCES fournisseurs(id) ON DELETE SET NULL,
    FOREIGN KEY (depot_id)       REFERENCES depots(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS commandes_details (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    commande_id     INTEGER NOT NULL,
    produit_id      INTEGER,
    designation     TEXT DEFAULT '',      -- si produit pas encore créé
    quantite        INTEGER NOT NULL,
    quantite_recue  INTEGER DEFAULT 0,
    prix_unitaire   REAL DEFAULT 0,
    total           REAL DEFAULT 0,
    FOREIGN KEY (commande_id) REFERENCES commandes(id) ON DELETE CASCADE,
    FOREIGN KEY (produit_id)  REFERENCES produits(id) ON DELETE SET NULL
);

/* ═══ RÈGLEMENTS (crédits clients + paiements fournisseurs) ═══ */

CREATE TABLE IF NOT EXISTS reglements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sens            TEXT NOT NULL CHECK(sens IN ('encaissement','decaissement')),
    vente_id        INTEGER,              -- si encaissement client
    commande_id     INTEGER,              -- si décaissement fournisseur
    client_id       INTEGER,
    fournisseur_id  INTEGER,
    montant         REAL NOT NULL,
    mode_paiement   TEXT DEFAULT 'Espèces',
    reference_doc   TEXT DEFAULT '',      -- n° transaction Mobile Money…
    notes           TEXT DEFAULT '',
    utilisateur     TEXT DEFAULT '',
    date_reglement  TIMESTAMP DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (vente_id)       REFERENCES ventes(id) ON DELETE CASCADE,
    FOREIGN KEY (commande_id)    REFERENCES commandes(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id)      REFERENCES clients(id) ON DELETE SET NULL,
    FOREIGN KEY (fournisseur_id) REFERENCES fournisseurs(id) ON DELETE SET NULL
);

/* ═══ INVENTAIRE PHYSIQUE ═══ */

CREATE TABLE IF NOT EXISTS inventaires (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    numero          TEXT DEFAULT '',
    depot_id        INTEGER,
    perimetre       TEXT DEFAULT 'total',  -- total / categorie / partiel
    categorie_id    INTEGER,
    statut          TEXT DEFAULT 'en_cours'
                    CHECK(statut IN ('en_cours','cloture','annule')),
    nb_lignes       INTEGER DEFAULT 0,
    nb_ecarts       INTEGER DEFAULT 0,
    valeur_ecart    REAL DEFAULT 0,
    date_debut      TIMESTAMP DEFAULT (datetime('now','localtime')),
    date_cloture    TIMESTAMP,
    notes           TEXT DEFAULT '',
    utilisateur     TEXT DEFAULT '',
    FOREIGN KEY (depot_id)     REFERENCES depots(id) ON DELETE SET NULL,
    FOREIGN KEY (categorie_id) REFERENCES categories(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS inventaire_lignes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    inventaire_id       INTEGER NOT NULL,
    produit_id          INTEGER NOT NULL,
    stock_theorique     INTEGER DEFAULT 0,
    stock_compte        INTEGER,           -- NULL = pas encore compté
    ecart               INTEGER DEFAULT 0,
    cump_unitaire       REAL DEFAULT 0,
    valeur_ecart        REAL DEFAULT 0,
    motif               TEXT DEFAULT '',   -- vol / casse / erreur saisie / perime
    notes               TEXT DEFAULT '',
    date_comptage       TIMESTAMP,
    UNIQUE (inventaire_id, produit_id),
    FOREIGN KEY (inventaire_id) REFERENCES inventaires(id) ON DELETE CASCADE,
    FOREIGN KEY (produit_id)    REFERENCES produits(id) ON DELETE CASCADE
);

/* ═══ RETOURS / AVOIRS ═══ */

CREATE TABLE IF NOT EXISTS retours (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    numero          TEXT DEFAULT '',
    vente_id        INTEGER,
    client_id       INTEGER,
    client_nom      TEXT DEFAULT '',
    depot_id        INTEGER,
    motif           TEXT DEFAULT '',
    total           REAL DEFAULT 0,
    mode_remboursement TEXT DEFAULT 'Espèces',  -- Espèces / Avoir / Échange
    statut          TEXT DEFAULT 'valide'
                    CHECK(statut IN ('valide','annule')),
    notes           TEXT DEFAULT '',
    utilisateur     TEXT DEFAULT '',
    date_retour     TIMESTAMP DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (vente_id)  REFERENCES ventes(id) ON DELETE SET NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL,
    FOREIGN KEY (depot_id)  REFERENCES depots(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS retours_details (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    retour_id       INTEGER NOT NULL,
    produit_id      INTEGER,
    quantite        INTEGER NOT NULL,
    prix_unitaire   REAL DEFAULT 0,
    total           REAL DEFAULT 0,
    remis_en_stock  INTEGER DEFAULT 1,     -- 0 = pièce cassée, détruite
    etat            TEXT DEFAULT 'neuf',   -- neuf / abime / hs
    FOREIGN KEY (retour_id)  REFERENCES retours(id) ON DELETE CASCADE,
    FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE SET NULL
);
"""


# ─── 2. INDEX ─────────────────────────────────────────

INDEX = """
/* Index manquants sur le schéma v2 */
CREATE INDEX IF NOT EXISTS idx_produits_fourn    ON produits(fournisseur_id);
CREATE INDEX IF NOT EXISTS idx_produits_actif    ON produits(actif);
CREATE INDEX IF NOT EXISTS idx_produits_nom      ON produits(nom);
CREATE INDEX IF NOT EXISTS idx_ventes_client     ON ventes(client_id);
CREATE INDEX IF NOT EXISTS idx_ventes_statut     ON ventes(statut);
CREATE INDEX IF NOT EXISTS idx_ventes_paiement   ON ventes(mode_paiement);
CREATE INDEX IF NOT EXISTS idx_vd_produit        ON ventes_details(produit_id);
CREATE INDEX IF NOT EXISTS idx_journal_date      ON journal(date_action);

/* Index v3 */
CREATE INDEX IF NOT EXISTS idx_sd_depot          ON stock_depot(depot_id);
CREATE INDEX IF NOT EXISTS idx_sd_produit        ON stock_depot(produit_id);
CREATE INDEX IF NOT EXISTS idx_compat_produit    ON produit_compatibilite(produit_id);
CREATE INDEX IF NOT EXISTS idx_compat_modele     ON produit_compatibilite(modele_id);
CREATE INDEX IF NOT EXISTS idx_modeles_marque    ON vehicules_modeles(marque, modele);
CREATE INDEX IF NOT EXISTS idx_refs_reference    ON produit_references(reference);
CREATE INDEX IF NOT EXISTS idx_refs_produit      ON produit_references(produit_id);
CREATE INDEX IF NOT EXISTS idx_prixh_produit     ON prix_historique(produit_id, date_prix);
CREATE INDEX IF NOT EXISTS idx_cmd_fourn         ON commandes(fournisseur_id);
CREATE INDEX IF NOT EXISTS idx_cmd_statut        ON commandes(statut);
CREATE INDEX IF NOT EXISTS idx_cmdd_commande     ON commandes_details(commande_id);
CREATE INDEX IF NOT EXISTS idx_regl_vente        ON reglements(vente_id);
CREATE INDEX IF NOT EXISTS idx_regl_commande     ON reglements(commande_id);
CREATE INDEX IF NOT EXISTS idx_regl_date         ON reglements(date_reglement);
CREATE INDEX IF NOT EXISTS idx_invl_inventaire   ON inventaire_lignes(inventaire_id);
CREATE INDEX IF NOT EXISTS idx_retours_vente     ON retours(vente_id);
CREATE INDEX IF NOT EXISTS idx_retd_retour       ON retours_details(retour_id);
CREATE INDEX IF NOT EXISTS idx_mvt_depot         ON mouvements_stock(depot_id);
"""


# ─── 3. VUES DE PILOTAGE ──────────────────────────────

VUES = """
/* Créances clients : ce qui reste dû sur chaque vente à crédit */
DROP VIEW IF EXISTS v_creances;
CREATE VIEW v_creances AS
SELECT  v.id                AS vente_id,
        v.numero,
        v.client_id,
        v.client_nom,
        v.date_vente,
        v.date_echeance,
        v.total,
        v.montant_paye + COALESCE((
            SELECT SUM(r.montant) FROM reglements r
            WHERE r.vente_id = v.id AND r.sens = 'encaissement'
        ), 0)               AS total_paye,
        v.total - (v.montant_paye + COALESCE((
            SELECT SUM(r.montant) FROM reglements r
            WHERE r.vente_id = v.id AND r.sens = 'encaissement'
        ), 0))              AS reste_du,
        CAST(julianday('now','localtime') - julianday(v.date_vente) AS INTEGER)
                            AS anciennete_jours
FROM ventes v
WHERE v.statut = 'validee'
  AND v.total - (v.montant_paye + COALESCE((
        SELECT SUM(r.montant) FROM reglements r
        WHERE r.vente_id = v.id AND r.sens = 'encaissement'
      ), 0)) > 0.01;

/* Stock consolidé tous dépôts (compatible avec l'ancien produits.stock) */
DROP VIEW IF EXISTS v_stock_produit;
CREATE VIEW v_stock_produit AS
SELECT  p.id                AS produit_id,
        p.reference,
        p.nom,
        p.cump,
        p.prix_vente,
        COALESCE(SUM(sd.quantite), 0)          AS stock_total,
        COALESCE(SUM(CASE WHEN d.autorise_vente = 1
                          THEN sd.quantite ELSE 0 END), 0) AS stock_vendable,
        COALESCE(SUM(sd.quantite), 0) * p.cump AS valeur_stock
FROM produits p
LEFT JOIN stock_depot sd ON sd.produit_id = p.id
LEFT JOIN depots d       ON d.id = sd.depot_id AND d.actif = 1
GROUP BY p.id;

/* Dette fournisseur : reste à payer par commande reçue */
DROP VIEW IF EXISTS v_dettes_fournisseur;
CREATE VIEW v_dettes_fournisseur AS
SELECT  c.id                AS commande_id,
        c.numero,
        c.fournisseur_id,
        f.nom               AS fournisseur_nom,
        c.date_commande,
        c.total,
        c.montant_paye + COALESCE((
            SELECT SUM(r.montant) FROM reglements r
            WHERE r.commande_id = c.id AND r.sens = 'decaissement'
        ), 0)               AS total_paye,
        c.total - (c.montant_paye + COALESCE((
            SELECT SUM(r.montant) FROM reglements r
            WHERE r.commande_id = c.id AND r.sens = 'decaissement'
        ), 0))              AS reste_a_payer
FROM commandes c
LEFT JOIN fournisseurs f ON f.id = c.fournisseur_id
WHERE c.statut IN ('partielle','recue')
  AND c.total - (c.montant_paye + COALESCE((
        SELECT SUM(r.montant) FROM reglements r
        WHERE r.commande_id = c.id AND r.sens = 'decaissement'
      ), 0)) > 0.01;
"""


# ─── 4. MIGRATION PRINCIPALE ──────────────────────────

def migrer(cursor) -> list[str]:
    """
    Applique la migration v3. Retourne la liste des actions effectuées.
    Idempotent : sans effet si déjà appliquée.
    """
    actions: list[str] = []

    # ── 4.1 Colonnes additives sur les tables existantes ──

    # PRODUITS : pilotage, CUMP, conditionnement
    colonnes_produits = [
        ("cump",                 "REAL DEFAULT 0"),      # coût moyen pondéré
        ("stock_maxi",           "INTEGER DEFAULT 0"),
        ("delai_reappro_jours",  "INTEGER DEFAULT 7"),
        ("emballage_qte",        "INTEGER DEFAULT 1"),   # vendu par jeu de 4…
        ("unite",                "TEXT DEFAULT 'pièce'"),
        ("garantie_mois",        "INTEGER DEFAULT 0"),
        ("classe_abc",           "TEXT DEFAULT ''"),     # A/B/C recalculé
        ("date_dernier_achat",   "TIMESTAMP"),
        ("date_derniere_vente",  "TIMESTAMP"),
        ("origine",              "TEXT DEFAULT ''"),     # neuf / occasion / adaptable
    ]
    for col, definition in colonnes_produits:
        if _ajouter_colonne(cursor, "produits", col, definition):
            actions.append(f"produits.{col}")

    # Initialiser le CUMP au prix d'achat actuel (meilleure approximation)
    cursor.execute("UPDATE produits SET cump = prix_achat WHERE cump = 0 AND prix_achat > 0")

    # CLIENTS : crédit, segmentation
    colonnes_clients = [
        ("type_client",        "TEXT DEFAULT 'particulier'"),  # particulier/garage/revendeur
        ("plafond_credit",     "REAL DEFAULT 0"),              # 0 = pas de crédit autorisé
        ("remise_defaut",      "REAL DEFAULT 0"),              # en %
        ("date_dernier_achat", "TIMESTAMP"),
        ("actif",              "INTEGER DEFAULT 1"),
    ]
    for col, definition in colonnes_clients:
        if _ajouter_colonne(cursor, "clients", col, definition):
            actions.append(f"clients.{col}")

    # FOURNISSEURS : fiabilité, conditions
    colonnes_fournisseurs = [
        ("delai_livraison_jours", "INTEGER DEFAULT 7"),
        ("conditions_paiement",   "TEXT DEFAULT ''"),   # comptant / 30j…
        ("actif",                 "INTEGER DEFAULT 1"),
        ("notes",                 "TEXT DEFAULT ''"),
    ]
    for col, definition in colonnes_fournisseurs:
        if _ajouter_colonne(cursor, "fournisseurs", col, definition):
            actions.append(f"fournisseurs.{col}")

    # VENTES : dépôt d'origine, échéance de crédit
    colonnes_ventes = [
        ("depot_id",      "INTEGER"),
        ("date_echeance", "DATE"),
    ]
    for col, definition in colonnes_ventes:
        if _ajouter_colonne(cursor, "ventes", col, definition):
            actions.append(f"ventes.{col}")

    # MOUVEMENTS : traçabilité par dépôt + coût
    colonnes_mvt = [
        ("depot_id",        "INTEGER"),   # dépôt concerné (destination si transfert)
        ("depot_source_id", "INTEGER"),   # dépôt source si transfert
        ("cout_unitaire",   "REAL DEFAULT 0"),   # CUMP au moment du mouvement
    ]
    for col, definition in colonnes_mvt:
        if _ajouter_colonne(cursor, "mouvements_stock", col, definition):
            actions.append(f"mouvements_stock.{col}")

    # ── 4.2 Nouvelles tables ──
    cursor.executescript(TABLES)

    # ── 4.3 Dépôts par défaut + bascule du stock existant ──
    cursor.execute("SELECT COUNT(*) FROM depots")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """INSERT INTO depots (code, nom, type, autorise_vente, par_defaut, ordre)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                ("BOU", "Boutique (rayon)", "boutique", 1, 1, 1),
                ("RES", "Réserve",          "reserve",  0, 0, 2),
            ],
        )
        actions.append("depots: BOU + RES créés")

    # Migration du stock v2 (produits.stock_vente / stock_reserve) → stock_depot
    cursor.execute("SELECT COUNT(*) FROM stock_depot")
    if cursor.fetchone()[0] == 0:
        id_bou = cursor.execute("SELECT id FROM depots WHERE code='BOU'").fetchone()
        id_res = cursor.execute("SELECT id FROM depots WHERE code='RES'").fetchone()
        if id_bou and id_res:
            cursor.execute(
                """INSERT INTO stock_depot (produit_id, depot_id, quantite, stock_mini, emplacement)
                   SELECT id, ?, COALESCE(stock_vente, 0), COALESCE(stock_mini, 5),
                          COALESCE(emplacement, '')
                   FROM produits""",
                (id_bou[0],),
            )
            cursor.execute(
                """INSERT INTO stock_depot (produit_id, depot_id, quantite, stock_mini)
                   SELECT id, ?, COALESCE(stock_reserve, 0), 0 FROM produits""",
                (id_res[0],),
            )
            n = cursor.execute("SELECT COUNT(*) FROM stock_depot").fetchone()[0]
            actions.append(f"stock_depot: {n} lignes migrées depuis produits")

    # Rattacher les ventes existantes au dépôt boutique
    id_bou = cursor.execute("SELECT id FROM depots WHERE code='BOU'").fetchone()
    if id_bou:
        cursor.execute("UPDATE ventes SET depot_id=? WHERE depot_id IS NULL", (id_bou[0],))
        cursor.execute("UPDATE mouvements_stock SET depot_id=? WHERE depot_id IS NULL",
                       (id_bou[0],))

    # ── 4.4 Index + vues ──
    cursor.executescript(INDEX)
    cursor.executescript(VUES)

    # ── 4.5 Nouveaux paramètres ──
    nouveaux_params = {
        "schema_version":        str(SCHEMA_VERSION),
        "prefixe_commande":      "CMD",
        "prefixe_retour":        "RET",
        "prefixe_inventaire":    "INV",
        "depot_defaut":          "BOU",
        "credit_autorise":       "1",
        "credit_plafond_defaut": "0",
        "credit_delai_jours":    "30",
        "alerte_creance_jours":  "15",
        "seuil_couverture_jours": "14",   # prévision de rupture
        "valorisation":          "cump",  # cump | dernier_prix
    }
    for cle, valeur in nouveaux_params.items():
        cursor.execute("INSERT OR IGNORE INTO parametres (cle, valeur) VALUES (?, ?)",
                       (cle, valeur))

    # ── 4.6 Motifs d'écart d'inventaire (référentiel léger en paramètres) ──
    cursor.execute("INSERT OR IGNORE INTO parametres (cle, valeur) VALUES (?, ?)",
                   ("motifs_ecart", "Vol,Casse,Erreur de saisie,Perte,Périmé,Autre"))

    return actions


def marques_courantes_ci() -> list[tuple]:
    """
    Référentiel de démarrage : modèles les plus courants en Côte d'Ivoire.
    (marque, modele, motorisation, carburant, annee_debut, annee_fin)
    """
    return [
        ("Toyota", "Corolla",    "1.4 VVT-i",  "essence", 2002, 2013),
        ("Toyota", "Corolla",    "1.8 VVT-i",  "essence", 2013, 0),
        ("Toyota", "Yaris",      "1.0 / 1.3",  "essence", 2005, 2020),
        ("Toyota", "RAV4",       "2.0 / 2.2",  "essence", 2006, 0),
        ("Toyota", "Hilux",      "2.5 D-4D",   "diesel",  2005, 2015),
        ("Toyota", "Hiace",      "2.5 D-4D",   "diesel",  2004, 0),
        ("Toyota", "Land Cruiser", "4.2 / 4.5", "diesel", 1998, 0),
        ("Toyota", "Avensis",    "2.0 D-4D",   "diesel",  2003, 2018),
        ("Suzuki", "Alto",       "1.0",        "essence", 2009, 0),
        ("Suzuki", "Dzire",      "1.2",        "essence", 2017, 0),
        ("Suzuki", "Swift",      "1.2",        "essence", 2010, 0),
        ("Hyundai", "Accent",    "1.4 / 1.6",  "essence", 2006, 0),
        ("Hyundai", "i10",       "1.1",        "essence", 2008, 0),
        ("Hyundai", "Tucson",    "2.0 CRDi",   "diesel",  2004, 0),
        ("Kia",     "Rio",       "1.4",        "essence", 2005, 0),
        ("Kia",     "Picanto",   "1.0 / 1.2",  "essence", 2004, 0),
        ("Nissan",  "Almera",    "1.5",        "essence", 2000, 2012),
        ("Nissan",  "Patrol",    "3.0 Di",     "diesel",  1997, 2013),
        ("Renault", "Logan",     "1.4 / 1.6",  "essence", 2004, 0),
        ("Renault", "Duster",    "1.5 dCi",    "diesel",  2010, 0),
        ("Dacia",   "Sandero",   "1.4 / 1.6",  "essence", 2008, 0),
        ("Peugeot", "206",       "1.4",        "essence", 1998, 2012),
        ("Peugeot", "301",       "1.6 HDi",    "diesel",  2012, 0),
        ("Peugeot", "Partner",   "1.6 HDi",    "diesel",  2008, 0),
        ("Mercedes", "Sprinter", "2.2 CDI",    "diesel",  2006, 0),
        ("Mitsubishi", "Pajero", "3.2 DiD",    "diesel",  2000, 0),
        ("Isuzu",   "D-Max",     "2.5 TD",     "diesel",  2002, 0),
        ("Ford",    "Ranger",    "2.2 TDCi",   "diesel",  2011, 0),
        ("Honda",   "Civic",     "1.6",        "essence", 2001, 2011),
        ("Volkswagen", "Golf",   "1.6 / 1.9 TDI", "diesel", 1997, 2013),
    ]


def peupler_modeles(cursor) -> int:
    """Insère le référentiel véhicules s'il est vide. Retourne le nb inséré."""
    cursor.execute("SELECT COUNT(*) FROM vehicules_modeles")
    if cursor.fetchone()[0] > 0:
        return 0
    cursor.executemany(
        """INSERT OR IGNORE INTO vehicules_modeles
           (marque, modele, motorisation, carburant, annee_debut, annee_fin)
           VALUES (?, ?, ?, ?, ?, ?)""",
        marques_courantes_ci(),
    )
    return cursor.execute("SELECT COUNT(*) FROM vehicules_modeles").fetchone()[0]
