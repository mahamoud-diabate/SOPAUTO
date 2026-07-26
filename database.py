"""
SODIPAC - Gestion Pièce Auto
Module Base de Données (SQLite)

Améliorations v2 :
- Migration automatique et non destructive du schéma existant
- Transactions atomiques (plus de stock incohérent en cas d'erreur)
- Mots de passe hashés (PBKDF2-SHA256) + rôles
- Clients, remises, modes de paiement, numéros de facture
- Traçabilité : stock avant/après, utilisateur, annulation de vente
- Rapports (CA, marge, top produits, valeur du stock)
- Sauvegarde de la base et exports CSV
"""

import csv
import hashlib
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from typing import Any

# PyInstaller : quand l'app est compilée en .exe, __file__ pointe vers
# un dossier temporaire. sys.executable pointe vers le .exe réel.
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "gestion_piece_auto.db")
BACKUP_DIR = os.path.join(BASE_DIR, "sauvegardes")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

# Utilisateur courant (renseigné par l'interface après connexion)
UTILISATEUR_COURANT = "système"


def set_utilisateur_courant(nom: str) -> None:
    global UTILISATEUR_COURANT
    UTILISATEUR_COURANT = nom or "système"


def _maintenant() -> str:
    """Horodatage en heure LOCALE.

    SQLite écrit CURRENT_TIMESTAMP en UTC : une vente du soir était comptée
    sur la journée du lendemain. On fournit donc l'heure locale explicitement.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection() -> sqlite3.Connection:
    """Retourne une connexion à la base de données."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# ─── HASHAGE DES MOTS DE PASSE ───────────────────────

def hash_password(mot_de_passe: str, salt: bytes = None) -> str:
    """Retourne 'pbkdf2$<salt_hex>$<hash_hex>'."""
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), salt, 120_000)
    return f"pbkdf2${salt.hex()}${dk.hex()}"


def verify_password(mot_de_passe: str, stocke: str) -> bool:
    """Vérifie un mot de passe. Accepte l'ancien format en clair (legacy)."""
    if not stocke:
        return False
    if stocke.startswith("pbkdf2$"):
        try:
            _, salt_hex, hash_hex = stocke.split("$")
            return hash_password(mot_de_passe, bytes.fromhex(salt_hex)).split("$")[2] == hash_hex
        except (ValueError, IndexError):
            return False
    # Ancien format : mot de passe en clair
    return mot_de_passe == stocke


# ─── MIGRATION / INITIALISATION ──────────────────────

def _colonnes(cursor, table) -> set:
    return {r[1] for r in cursor.execute(f"PRAGMA table_info({table})")}


def _ajouter_colonne(cursor, table, colonne, definition) -> bool:
    if colonne not in _colonnes(cursor, table):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")
        return True
    return False


def init_database() -> None:
    """Cree les tables si besoin puis migre le schema sans perte de donnees."""
    # Charger un dossier de sauvegarde personnalise si defini
    global BACKUP_DIR
    try:
        custom = get_parametres().get("backup_dir", "")
        if custom and os.path.isdir(custom):
            BACKUP_DIR = custom
    except Exception:
        pass
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS fournisseurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            contact TEXT DEFAULT '',
            telephone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            adresse TEXT DEFAULT '',
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            telephone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            adresse TEXT DEFAULT '',
            vehicule TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS produits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL UNIQUE,
            nom TEXT NOT NULL,
            description TEXT DEFAULT '',
            categorie_id INTEGER,
            fournisseur_id INTEGER,
            marque TEXT DEFAULT '',
            prix_achat REAL DEFAULT 0,
            prix_vente REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            stock_mini INTEGER DEFAULT 5,
            emplacement TEXT DEFAULT '',
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_modification TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (categorie_id) REFERENCES categories(id) ON DELETE SET NULL,
            FOREIGN KEY (fournisseur_id) REFERENCES fournisseurs(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS mouvements_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produit_id INTEGER NOT NULL,
            type_mouvement TEXT CHECK(type_mouvement IN ('entree', 'sortie', 'correction', 'transfert')) NOT NULL,
            quantite INTEGER NOT NULL,
            prix_unitaire REAL DEFAULT 0,
            reference_doc TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            date_mouvement TIMESTAMP DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ventes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_nom TEXT DEFAULT 'Client',
            total REAL DEFAULT 0,
            date_vente TIMESTAMP DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS ventes_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vente_id INTEGER NOT NULL,
            produit_id INTEGER,
            quantite INTEGER NOT NULL,
            prix_unitaire REAL NOT NULL,
            total REAL NOT NULL,
            FOREIGN KEY (vente_id) REFERENCES ventes(id) ON DELETE CASCADE,
            FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS utilisateurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_utilisateur TEXT NOT NULL UNIQUE,
            mot_de_passe TEXT NOT NULL,
            role TEXT DEFAULT 'utilisateur',
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS parametres (
            cle TEXT PRIMARY KEY,
            valeur TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utilisateur TEXT DEFAULT '',
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            date_action TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # ── Migrations additives ──
    _ajouter_colonne(cursor, "produits", "code_barres", "TEXT DEFAULT ''")
    _ajouter_colonne(cursor, "produits", "actif", "INTEGER DEFAULT 1")

    # Stock double emplacement (réserve + vente)
    _ajouter_colonne(cursor, "produits", "stock_reserve", "INTEGER DEFAULT 0")
    if _ajouter_colonne(cursor, "produits", "stock_vente", "INTEGER DEFAULT 0"):
        # Première migration : l'ancien stock unique → stock_vente
        cursor.execute("UPDATE produits SET stock_vente=stock WHERE stock>0")
    _ajouter_colonne(cursor, "produits", "emplacement_type", "TEXT DEFAULT 'vente'")

    _ajouter_colonne(cursor, "ventes", "numero", "TEXT DEFAULT ''")
    _ajouter_colonne(cursor, "ventes", "client_id", "INTEGER")
    _ajouter_colonne(cursor, "ventes", "sous_total", "REAL DEFAULT 0")
    _ajouter_colonne(cursor, "ventes", "remise", "REAL DEFAULT 0")
    _ajouter_colonne(cursor, "ventes", "mode_paiement", "TEXT DEFAULT 'Espèces'")
    _ajouter_colonne(cursor, "ventes", "montant_paye", "REAL DEFAULT 0")
    _ajouter_colonne(cursor, "ventes", "utilisateur", "TEXT DEFAULT ''")
    _ajouter_colonne(cursor, "ventes", "statut", "TEXT DEFAULT 'validee'")

    _ajouter_colonne(cursor, "ventes_details", "prix_achat", "REAL DEFAULT 0")

    _ajouter_colonne(cursor, "mouvements_stock", "stock_avant", "INTEGER DEFAULT 0")
    _ajouter_colonne(cursor, "mouvements_stock", "stock_apres", "INTEGER DEFAULT 0")
    _ajouter_colonne(cursor, "mouvements_stock", "utilisateur", "TEXT DEFAULT ''")

    # Migration CHECK constraint pour support 'transfert'.
    # On inspecte le SQL de la table : un probe INSERT échouerait aussi sur la
    # contrainte FK (produit_id inexistant) et recréerait la table à chaque
    # démarrage.
    sql_table = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='mouvements_stock'"
    ).fetchone()[0]
    if "'transfert'" not in sql_table:
        # L'ancien CHECK ne permet pas 'transfert' → recréer la table
        cursor.executescript("""
            CREATE TABLE mouvements_stock_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produit_id INTEGER NOT NULL,
                type_mouvement TEXT CHECK(type_mouvement IN ('entree','sortie','correction','transfert')) NOT NULL,
                quantite INTEGER NOT NULL,
                prix_unitaire REAL DEFAULT 0,
                reference_doc TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                date_mouvement TIMESTAMP DEFAULT (datetime('now','localtime')),
                stock_avant INTEGER DEFAULT 0,
                stock_apres INTEGER DEFAULT 0,
                utilisateur TEXT DEFAULT '',
                FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE CASCADE
            );
            INSERT INTO mouvements_stock_new SELECT * FROM mouvements_stock;
            DROP TABLE mouvements_stock;
            ALTER TABLE mouvements_stock_new RENAME TO mouvements_stock;
        """)

    _ajouter_colonne(cursor, "utilisateurs", "actif", "INTEGER DEFAULT 1")
    _ajouter_colonne(cursor, "utilisateurs", "nom_complet", "TEXT DEFAULT ''")
    _ajouter_colonne(cursor, "utilisateurs", "dernier_acces", "TIMESTAMP")

    # Index de performance
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_produits_ref ON produits(reference);
        CREATE INDEX IF NOT EXISTS idx_produits_cat ON produits(categorie_id);
        CREATE INDEX IF NOT EXISTS idx_produits_cb ON produits(code_barres);
        CREATE INDEX IF NOT EXISTS idx_mvt_produit ON mouvements_stock(produit_id);
        CREATE INDEX IF NOT EXISTS idx_mvt_date ON mouvements_stock(date_mouvement);
        CREATE INDEX IF NOT EXISTS idx_ventes_date ON ventes(date_vente);
        CREATE INDEX IF NOT EXISTS idx_vd_vente ON ventes_details(vente_id);
    """)

    # Admin par défaut
    cursor.execute("SELECT COUNT(*) FROM utilisateurs")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO utilisateurs (nom_utilisateur, mot_de_passe, role, nom_complet) VALUES (?, ?, ?, ?)",
            ("admin", hash_password("admin123"), "superviseur", "Administrateur"),
        )

    # Ré-hashage des anciens mots de passe en clair
    for row in cursor.execute("SELECT id, mot_de_passe FROM utilisateurs").fetchall():
        if not str(row["mot_de_passe"]).startswith("pbkdf2$"):
            cursor.execute("UPDATE utilisateurs SET mot_de_passe=? WHERE id=?",
                           (hash_password(row["mot_de_passe"]), row["id"]))

    # Catégories par défaut
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO categories (nom, description) VALUES (?, ?)",
            [
                ("Freinage", "Système de freinage - plaquettes, disques, tambours"),
                ("Moteur", "Pièces moteur - pistons, soupapes, courroies"),
                ("Suspension", "Suspension et direction - amortisseurs, triangles"),
                ("Éclairage", "Phares, feux, ampoules"),
                ("Filtres", "Filtres à huile, air, carburant, habitacle"),
                ("Échappement", "Silencieux, catalyseurs, tubes"),
                ("Transmission", "Boîte de vitesse, embrayage, cardans"),
                ("Carrosserie", "Portes, pare-chocs, rétroviseurs"),
                ("Électricité", "Batteries, alternateurs, démarreurs"),
                ("Huiles & Fluides", "Huiles moteur, liquide de frein, refroidissement"),
            ],
        )

    # Paramètres par défaut
    defauts = {
        "entreprise_nom": "SODIPAC",
        "entreprise_activite": "Vente de pièces automobiles",
        "entreprise_adresse": "Abidjan, Côte d'Ivoire",
        "entreprise_telephone": "",
        "entreprise_email": "",
        "devise": "F CFA",
        "tva_taux": "0",
        "prefixe_facture": "FAC",
        "pied_facture": "Merci de votre confiance !",
        "theme": "clair",
        "objectif_ca_mois": "0",
    }
    for cle, valeur in defauts.items():
        cursor.execute("INSERT OR IGNORE INTO parametres (cle, valeur) VALUES (?, ?)", (cle, valeur))

    # Renseigner les numéros de facture manquants
    for row in cursor.execute("SELECT id, date_vente FROM ventes WHERE numero IS NULL OR numero=''").fetchall():
        annee = str(row["date_vente"])[:4] or datetime.now().strftime("%Y")
        cursor.execute("UPDATE ventes SET numero=? WHERE id=?",
                       (f"FAC-{annee}-{row['id']:05d}", row["id"]))

    # sous_total cohérent pour les anciennes ventes
    cursor.execute("UPDATE ventes SET sous_total=total WHERE COALESCE(sous_total,0)=0")

    # Correction des horodatages UTC hérités de CURRENT_TIMESTAMP.
    # On applique une seule fois le décalage local pour que les ventes du soir
    # soient comptabilisées sur la bonne journée.
    if cursor.execute("SELECT COUNT(*) FROM parametres WHERE cle='dates_localisees'").fetchone()[0] == 0:
        decalage = round((datetime.now() - datetime.utcnow()).total_seconds() / 3600)
        if decalage:
            modif = f"{decalage:+d} hours"
            for table, colonne in (("ventes", "date_vente"),
                                   ("mouvements_stock", "date_mouvement"),
                                   ("journal", "date_action")):
                cursor.execute(
                    f"UPDATE {table} SET {colonne}=datetime({colonne}, ?) WHERE {colonne} IS NOT NULL",
                    (modif,))
        cursor.execute("INSERT OR REPLACE INTO parametres (cle, valeur) VALUES ('dates_localisees','1')")

    # ── Migration v3 : multi-dépôt, compatibilité véhicule, achats, créances… ──
    try:
        import schema_v3
        actions = schema_v3.migrer(cursor)
        nb_modeles = schema_v3.peupler_modeles(cursor)
        if actions or nb_modeles:
            detail = f"{len(actions)} changements"
            if nb_modeles:
                detail += f", {nb_modeles} modèles véhicules"
            cursor.execute(
                "INSERT INTO journal (utilisateur, action, details, date_action) VALUES (?,?,?,?)",
                ("système", "Migration schéma v3", detail, _maintenant()))
    except Exception as exc:  # migration non bloquante : l'appli doit démarrer
        print(f"[AVERTISSEMENT] Migration v3 incomplète : {exc}")

    conn.commit()
    conn.close()


# ─── JOURNAL ─────────────────────────────────────────

def log_action(action: str, details: str = "") -> None:
    try:
        conn = get_connection()
        with conn:
            conn.execute("INSERT INTO journal (utilisateur, action, details, date_action) "
                         "VALUES (?, ?, ?, ?)",
                         (UTILISATEUR_COURANT, action, details, _maintenant()))
        conn.close()
    except sqlite3.Error:
        pass


def get_journal(limit: int = 300) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM journal ORDER BY date_action DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── PARAMÈTRES ──────────────────────────────────────

def get_parametres() -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT cle, valeur FROM parametres").fetchall()
    conn.close()
    return {r["cle"]: r["valeur"] for r in rows}


def set_parametres_batch(parametres: dict) -> None:
    """Enregistre plusieurs paramètres en une seule transaction."""
    conn = get_connection()
    try:
        with conn:
            conn.executemany(
                "INSERT INTO parametres (cle, valeur) VALUES (?, ?) "
                "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
                [(cle, str(valeur)) for cle, valeur in parametres.items()])
    finally:
        conn.close()


def set_parametre(cle: str, valeur: str | float | int | None) -> None:
    conn = get_connection()
    with conn:
        conn.execute("INSERT INTO parametres (cle, valeur) VALUES (?, ?) "
                     "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", (cle, str(valeur)))
    conn.close()


def get_devise() -> str:
    return get_parametres().get("devise", "F CFA")


# ─── UTILISATEURS / AUTHENTIFICATION ─────────────────

def authenticate(nom_utilisateur: str, mot_de_passe: str) -> tuple[dict | None, str]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM utilisateurs WHERE nom_utilisateur=?",
                       (nom_utilisateur,)).fetchone()
    if not row:
        conn.close()
        return None, "Utilisateur inconnu"
    if not row["actif"]:
        conn.close()
        return None, "Compte désactivé"
    if not verify_password(mot_de_passe, row["mot_de_passe"]):
        conn.close()
        return None, "Mot de passe incorrect"
    with conn:
        conn.execute("UPDATE utilisateurs SET dernier_acces=? WHERE id=?", (_maintenant(), row["id"]))
    user = dict(row)
    conn.close()
    return user, "Connexion réussie"


def get_utilisateurs() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, nom_utilisateur, nom_complet, role, actif, date_creation, dernier_acces "
        "FROM utilisateurs ORDER BY nom_utilisateur").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_utilisateur(nom_utilisateur: str, mot_de_passe: str, role: str = "utilisateur", nom_complet: str = "") -> tuple[bool, str]:
    if len(mot_de_passe) < 4:
        return False, "Le mot de passe doit faire au moins 4 caractères"
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO utilisateurs (nom_utilisateur, mot_de_passe, role, nom_complet) VALUES (?, ?, ?, ?)",
                (nom_utilisateur, hash_password(mot_de_passe), role, nom_complet))
        log_action("Création utilisateur", nom_utilisateur)
        return True, "Utilisateur créé"
    except sqlite3.IntegrityError:
        return False, "Ce nom d'utilisateur existe déjà"
    finally:
        conn.close()


def _dernier_admin_actif(conn, id) -> bool:
    """True si l'utilisateur `id` est le dernier administrateur actif."""
    row = conn.execute("SELECT role, actif FROM utilisateurs WHERE id=?", (id,)).fetchone()
    if not row or row["role"] != "superviseur" or not row["actif"]:
        return False
    nb = conn.execute(
        "SELECT COUNT(*) FROM utilisateurs WHERE role='superviseur' AND actif=1").fetchone()[0]
    return nb <= 1


def update_utilisateur(id: int, role: Any = None, nom_complet: Any = None, actif: Any = None, mot_de_passe: Any = None) -> tuple[bool, str]:
    conn = get_connection()
    # Protection : ne pas rétrograder/désactiver le dernier administrateur actif
    if ((role is not None and role != "superviseur") or actif is False or actif == 0) \
            and _dernier_admin_actif(conn, id):
        conn.close()
        return False, "Impossible : c'est le dernier superviseur actif"
    champs, params = [], []
    if role is not None:
        champs.append("role=?"); params.append(role)
    if nom_complet is not None:
        champs.append("nom_complet=?"); params.append(nom_complet)
    if actif is not None:
        champs.append("actif=?"); params.append(1 if actif else 0)
    if mot_de_passe:
        if len(mot_de_passe) < 4:
            conn.close()
            return False, "Mot de passe trop court (4 caractères minimum)"
        champs.append("mot_de_passe=?"); params.append(hash_password(mot_de_passe))
    if not champs:
        conn.close()
        return False, "Rien à modifier"
    params.append(id)
    with conn:
        conn.execute(f"UPDATE utilisateurs SET {', '.join(champs)} WHERE id=?", params)
    conn.close()
    log_action("Modification utilisateur", f"id={id}")
    return True, "Utilisateur modifié"


def delete_utilisateur(id: int) -> tuple[bool, str]:
    conn = get_connection()
    if _dernier_admin_actif(conn, id):
        conn.close()
        return False, "Impossible : c'est le dernier superviseur actif"
    with conn:
        conn.execute("DELETE FROM utilisateurs WHERE id=?", (id,))
    conn.close()
    log_action("Suppression utilisateur", f"id={id}")
    return True, "Utilisateur supprimé"


# ─── CATÉGORIES ──────────────────────────────────────

def get_categories() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM categories ORDER BY nom").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_categorie(nom: str, description: str = "") -> tuple[bool, str]:
    if not nom.strip():
        return False, "Le nom est requis"
    conn = get_connection()
    try:
        with conn:
            conn.execute("INSERT INTO categories (nom, description) VALUES (?, ?)",
                         (nom.strip(), description))
        log_action("Ajout catégorie", nom)
        return True, "Catégorie ajoutée"
    except sqlite3.IntegrityError:
        return False, "Cette catégorie existe déjà"
    finally:
        conn.close()


def update_categorie(id: int, nom: str, description: str = "") -> tuple[bool, str]:
    conn = get_connection()
    try:
        with conn:
            conn.execute("UPDATE categories SET nom=?, description=? WHERE id=?",
                         (nom.strip(), description, id))
        log_action("Modification catégorie", nom)
        return True, "Catégorie modifiée"
    except sqlite3.IntegrityError:
        return False, "Ce nom existe déjà"
    finally:
        conn.close()


def delete_categorie(id: int) -> tuple[bool, str]:
    conn = get_connection()
    nb = conn.execute("SELECT COUNT(*) FROM produits WHERE categorie_id=?", (id,)).fetchone()[0]
    if nb:
        conn.close()
        return False, f"Impossible : {nb} produit(s) utilisent cette catégorie"
    with conn:
        conn.execute("DELETE FROM categories WHERE id=?", (id,))
    conn.close()
    log_action("Suppression catégorie", f"id={id}")
    return True, "Catégorie supprimée"


# ─── FOURNISSEURS ────────────────────────────────────

def get_fournisseurs(search: str = "") -> list[dict]:
    conn = get_connection()
    if search:
        s = f"%{search}%"
        rows = conn.execute(
            "SELECT * FROM fournisseurs WHERE nom LIKE ? OR contact LIKE ? OR telephone LIKE ? ORDER BY nom",
            (s, s, s)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM fournisseurs ORDER BY nom").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_fournisseur(nom: str, contact: str = "", telephone: str = "", email: str = "", adresse: str = "") -> tuple[bool, str]:
    if not nom.strip():
        return False, "Le nom est requis"
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO fournisseurs (nom, contact, telephone, email, adresse) VALUES (?, ?, ?, ?, ?)",
            (nom.strip(), contact, telephone, email, adresse))
    conn.close()
    log_action("Ajout fournisseur", nom)
    return True, "Fournisseur ajouté"


def update_fournisseur(id: int, nom, contact: str = "", telephone: str = "", email: str = "", adresse: str = "") -> tuple[bool, str]:
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE fournisseurs SET nom=?, contact=?, telephone=?, email=?, adresse=? WHERE id=?",
            (nom.strip(), contact, telephone, email, adresse, id))
    conn.close()
    log_action("Modification fournisseur", nom)
    return True, "Fournisseur modifié"


def delete_fournisseur(id: int) -> tuple[bool, str]:
    conn = get_connection()
    nb = conn.execute("SELECT COUNT(*) FROM produits WHERE fournisseur_id=?", (id,)).fetchone()[0]
    with conn:
        conn.execute("DELETE FROM fournisseurs WHERE id=?", (id,))
    conn.close()
    log_action("Suppression fournisseur", f"id={id}")
    return True, f"Fournisseur supprimé ({nb} produit(s) sans fournisseur)"


# ─── CLIENTS ─────────────────────────────────────────

def get_clients(search: str = "") -> list[dict]:
    conn = get_connection()
    base = """SELECT c.*,
                     (SELECT COUNT(*) FROM ventes v WHERE v.client_id=c.id) AS nb_achats,
                     (SELECT COALESCE(SUM(v.total),0) FROM ventes v
                       WHERE v.client_id=c.id AND v.statut!='annulee') AS total_achats
              FROM clients c"""
    if search:
        s = f"%{search}%"
        rows = conn.execute(base + " WHERE c.nom LIKE ? OR c.telephone LIKE ? OR c.vehicule LIKE ?"
                                   " ORDER BY c.nom", (s, s, s)).fetchall()
    else:
        rows = conn.execute(base + " ORDER BY c.nom").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_client(nom: str, telephone: str = "", email: str = "", adresse: str = "", vehicule: str = "", notes: str = "") -> tuple[bool, str]:
    if not nom.strip():
        return False, "Le nom est requis"
    conn = get_connection()
    with conn:
        conn.execute("""INSERT INTO clients (nom, telephone, email, adresse, vehicule, notes)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     (nom.strip(), telephone, email, adresse, vehicule, notes))
    conn.close()
    log_action("Ajout client", nom)
    return True, "Client ajouté"


def update_client(id: int, nom, telephone: str = "", email: str = "", adresse: str = "", vehicule: str = "", notes: str = "") -> tuple[bool, str]:
    conn = get_connection()
    with conn:
        conn.execute("""UPDATE clients SET nom=?, telephone=?, email=?, adresse=?, vehicule=?, notes=?
                        WHERE id=?""",
                     (nom.strip(), telephone, email, adresse, vehicule, notes, id))
    conn.close()
    log_action("Modification client", nom)
    return True, "Client modifié"


def delete_client(id: int) -> tuple[bool, str]:
    conn = get_connection()
    with conn:
        conn.execute("UPDATE ventes SET client_id=NULL WHERE client_id=?", (id,))
        conn.execute("DELETE FROM clients WHERE id=?", (id,))
    conn.close()
    log_action("Suppression client", f"id={id}")
    return True, "Client supprimé"


# ─── PRODUITS ────────────────────────────────────────

def get_produits(categorie_id=None, search="", seulement_alertes=False,
                 fournisseur_id=None, inclure_inactifs=True):
    conn = get_connection()
    query = """\
        SELECT p.*, c.nom AS categorie_nom, f.nom AS fournisseur_nom,
               (p.prix_vente - p.prix_achat) AS marge_unitaire,
               (p.stock * p.prix_achat) AS valeur_stock,
               (p.stock_vente * p.prix_achat) AS valeur_stock_vente
        FROM produits p
        LEFT JOIN categories c ON p.categorie_id = c.id
        LEFT JOIN fournisseurs f ON p.fournisseur_id = f.id
        WHERE 1=1
    """
    params = []

    if not inclure_inactifs:
        query += " AND COALESCE(p.actif,1)=1"
    if categorie_id:
        query += " AND p.categorie_id = ?"
        params.append(categorie_id)
    if fournisseur_id:
        query += " AND p.fournisseur_id = ?"
        params.append(fournisseur_id)
    if seulement_alertes:
        query += " AND p.stock <= p.stock_mini"
    if search:
        query += (" AND (p.reference LIKE ? OR p.nom LIKE ? OR p.marque LIKE ?"
                  " OR p.code_barres LIKE ? OR p.emplacement LIKE ? OR p.description LIKE ?)")
        s = f"%{search}%"
        params.extend([s] * 6)

    query += " ORDER BY p.nom"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_produit(id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        """SELECT p.*, c.nom AS categorie_nom, f.nom AS fournisseur_nom
           FROM produits p
           LEFT JOIN categories c ON p.categorie_id = c.id
           LEFT JOIN fournisseurs f ON p.fournisseur_id = f.id
           WHERE p.id=?""", (id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def trouver_produit(code: str) -> dict | None:
    """Recherche un produit par référence exacte ou code-barres (scan douchette)."""
    if not code:
        return None
    conn = get_connection()
    row = conn.execute(
        """SELECT p.*, c.nom AS categorie_nom FROM produits p
           LEFT JOIN categories c ON p.categorie_id=c.id
           WHERE p.reference=? OR (p.code_barres<>'' AND p.code_barres=?) LIMIT 1""",
        (code.strip(), code.strip())).fetchone()
    conn.close()
    return dict(row) if row else None


def suggerer_reference(categorie_id: int = None) -> str:
    """Génère une référence unique du type CAT-0001."""
    conn = get_connection()
    prefixe = "PRD"
    if categorie_id:
        row = conn.execute("SELECT nom FROM categories WHERE id=?", (categorie_id,)).fetchone()
        if row:
            prefixe = "".join(ch for ch in row["nom"].upper() if ch.isalnum())[:3] or "PRD"
    n = conn.execute("SELECT COUNT(*) FROM produits").fetchone()[0] + 1
    while conn.execute("SELECT 1 FROM produits WHERE reference=?", (f"{prefixe}-{n:04d}",)).fetchone():
        n += 1
    conn.close()
    return f"{prefixe}-{n:04d}"


def _valider_produit(reference, nom, prix_achat, prix_vente, stock_reserve, stock_vente, stock_mini) -> str | None:
    if not str(reference).strip():
        return "La référence est requise"
    if not str(nom).strip():
        return "Le nom est requis"
    if prix_achat < 0 or prix_vente < 0:
        return "Les prix ne peuvent pas être négatifs"
    if stock_reserve is not None and stock_reserve < 0:
        return "Le stock en réserve ne peut pas être négatif"
    if stock_vente is not None and stock_vente < 0:
        return "Le stock en vente ne peut pas être négatif"
    if stock_mini < 0:
        return "Le stock minimum ne peut pas être négatif"
    return None


def add_produit(reference, nom, description="", categorie_id=None, fournisseur_id=None,
                marque="", prix_achat=0, prix_vente=0, stock_reserve=0, stock_vente=0, stock_mini=5,
                emplacement="", code_barres="", actif=1, emplacement_type="vente"):
    erreur = _valider_produit(reference, nom, prix_achat, prix_vente, stock_reserve, stock_vente, stock_mini)
    if erreur:
        return False, erreur

    conn = get_connection()
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO produits (reference, nom, description, categorie_id, fournisseur_id,
                   marque, prix_achat, prix_vente, stock, stock_reserve, stock_vente, stock_mini,
                   emplacement, code_barres, actif, emplacement_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (reference.strip(), nom.strip(), description, categorie_id, fournisseur_id,
                 marque, prix_achat, prix_vente, stock_reserve + stock_vente,
                 stock_reserve, stock_vente, stock_mini, emplacement,
                 code_barres.strip(), 1 if actif else 0, emplacement_type))
            pid = cur.lastrowid
            total_stock = stock_reserve + stock_vente
            if total_stock:
                conn.execute(
                    """INSERT INTO mouvements_stock (produit_id, type_mouvement, quantite, prix_unitaire,
                       notes, stock_avant, stock_apres, utilisateur, date_mouvement)
                       VALUES (?, 'entree', ?, ?, 'Stock initial', 0, ?, ?, ?)""",
                    (pid, total_stock, prix_achat, total_stock, UTILISATEUR_COURANT, _maintenant()))
            # v3 : initialiser cump + stock_depot pour le nouveau produit
            conn.execute("UPDATE produits SET cump=? WHERE id=?", (prix_achat, pid))
            _sync_depots_depuis_produit(conn, pid, stock_reserve, stock_vente)
        log_action("Ajout produit", f"{reference} - {nom}")
        return True, "Produit ajouté"
    except sqlite3.IntegrityError:
        return False, "Cette référence existe déjà"
    finally:
        conn.close()


def update_produit(id, reference, nom, description="", categorie_id=None, fournisseur_id=None,
                   marque="", prix_achat=0, prix_vente=0, stock_mini=5, emplacement="",
                   code_barres="", actif=1, emplacement_type="vente"):
    erreur = _valider_produit(reference, nom, prix_achat, prix_vente, 0, 0, stock_mini)
    if erreur:
        return False, erreur

    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """UPDATE produits SET reference=?, nom=?, description=?, categorie_id=?,
                   fournisseur_id=?, marque=?, prix_achat=?, prix_vente=?, stock_mini=?,
                   emplacement=?, code_barres=?, actif=?, emplacement_type=?,
                   date_modification=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (reference.strip(), nom.strip(), description, categorie_id, fournisseur_id,
                 marque, prix_achat, prix_vente, stock_mini, emplacement,
                 code_barres.strip(), 1 if actif else 0, emplacement_type, id))
        log_action("Modification produit", f"{reference} - {nom}")
        return True, "Produit modifié"
    except sqlite3.IntegrityError:
        return False, "Cette référence existe déjà"
    finally:
        conn.close()


def delete_produit(id: int) -> tuple[bool, str]:
    """Supprime le produit, ou le désactive s'il est lié à des ventes (pas de perte d'historique)."""
    conn = get_connection()
    nb_ventes = conn.execute("SELECT COUNT(*) FROM ventes_details WHERE produit_id=?", (id,)).fetchone()[0]
    if nb_ventes:
        with conn:
            conn.execute("UPDATE produits SET actif=0, date_modification=CURRENT_TIMESTAMP WHERE id=?", (id,))
        conn.close()
        log_action("Désactivation produit", f"id={id}")
        return True, (f"Produit lié à {nb_ventes} vente(s) : il a été désactivé "
                      "au lieu d'être supprimé pour conserver l'historique.")
    with conn:
        conn.execute("DELETE FROM produits WHERE id=?", (id,))
    conn.close()
    log_action("Suppression produit", f"id={id}")
    return True, "Produit supprimé"


def reactiver_produit(id: int) -> tuple[bool, str]:
    conn = get_connection()
    with conn:
        conn.execute("UPDATE produits SET actif=1 WHERE id=?", (id,))
    conn.close()
    return True, "Produit réactivé"


# ─── MOUVEMENTS DE STOCK ────────────────────────────

def add_mouvement(produit_id, type_mouvement, quantite, prix_unitaire=0,
                  reference_doc="", notes="", cible=None):
    """
    Ajoute un mouvement de stock.

    type_mouvement : 'entree', 'sortie', 'correction', 'transfert'
    cible : 'reserve' ou 'vente' — utilisé pour 'transfert'.
           Pour 'entree' et 'sortie', détermine l'emplacement ciblé.
    """
    if type_mouvement not in ("entree", "sortie", "correction", "transfert"):
        return False, "Type de mouvement invalide"
    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        return False, "Quantité invalide"
    if type_mouvement != "correction" and quantite <= 0:
        return False, "La quantité doit être supérieure à 0"
    if type_mouvement == "correction" and quantite < 0:
        return False, "Le stock corrigé ne peut pas être négatif"

    conn = get_connection()
    try:
        with conn:
            prod = conn.execute(
                "SELECT stock, stock_reserve, stock_vente, nom FROM produits WHERE id=?",
                (produit_id,)).fetchone()
            if not prod:
                return False, "Produit introuvable"
            stock_avant = prod["stock"]

            if type_mouvement == "transfert":
                # Transfert entre réserve et vente
                if cible == "vente":
                    # Reserve → Vente
                    if quantite > prod["stock_reserve"]:
                        return False, (
                            f"Stock réserve insuffisant ! ({prod['stock_reserve']} en reserve)")
                    sr = prod["stock_reserve"] - quantite
                    sv = prod["stock_vente"] + quantite
                    notes = notes or f"Transfert reserve → vente : {quantite}"
                elif cible == "reserve":
                    # Vente → Reserve (retour)
                    if quantite > prod["stock_vente"]:
                        return False, (
                            f"Stock vente insuffisant ! ({prod['stock_vente']} en vente)")
                    sr = prod["stock_reserve"] + quantite
                    sv = prod["stock_vente"] - quantite
                    notes = notes or f"Transfert vente → reserve : {quantite}"
                else:
                    return False, "Cible invalide : choisir 'reserve' ou 'vente'"
                stock_apres = sr + sv
            else:
                # entree / sortie / correction
                cible_emp = cible if cible in ("reserve", "vente") else "vente"
                sr = prod["stock_reserve"]
                sv = prod["stock_vente"]

                if type_mouvement == "entree":
                    if cible_emp == "reserve":
                        sr += quantite
                    else:
                        sv += quantite
                elif type_mouvement == "sortie":
                    dispo = sv if cible_emp == "vente" else sr
                    if quantite > dispo:
                        nom_emp = "vente" if cible_emp == "vente" else "reserve"
                        return False, (
                            f"Stock {nom_emp} insuffisant ! ({dispo} disponible(s))")
                    if cible_emp == "reserve":
                        sr -= quantite
                    else:
                        sv -= quantite
                else:
                    # correction
                    if cible_emp == "reserve":
                        sr = quantite
                    else:
                        sv = quantite
                    notes = notes or f"Correction {cible_emp} : {prod[{'reserve': 'stock_reserve', 'vente': 'stock_vente'}[cible_emp]]} → {quantite}"

                stock_apres = sr + sv

            conn.execute(
                """UPDATE produits SET stock=?, stock_reserve=?, stock_vente=?,
                   date_modification=CURRENT_TIMESTAMP WHERE id=?""",
                (stock_apres, sr, sv, produit_id))

            # v3 : CUMP au lieu d'écraser le prix d'achat, + trace de l'historique
            cout_unitaire = 0.0
            if type_mouvement == "entree" and prix_unitaire > 0:
                actuel = conn.execute("SELECT cump, prix_achat FROM produits WHERE id=?",
                                      (produit_id,)).fetchone()
                ancien_cump = _num_safe(actuel["cump"]) or _num_safe(actuel["prix_achat"])
                # CUMP pondéré sur le stock AVANT l'entrée
                base = max(0, stock_avant)
                if base <= 0 or ancien_cump <= 0:
                    nouveau_cump = float(prix_unitaire)
                else:
                    nouveau_cump = ((base * ancien_cump + quantite * float(prix_unitaire))
                                    / (base + quantite))
                nouveau_cump = round(nouveau_cump, 2)
                cout_unitaire = nouveau_cump
                conn.execute("UPDATE produits SET cump=?, prix_achat=?, date_dernier_achat=? "
                             "WHERE id=?",
                             (nouveau_cump, float(prix_unitaire), _maintenant(), produit_id))
                _tracer_prix(conn, produit_id, "cump", ancien_cump, nouveau_cump,
                             "mouvement", "", reference_doc)
                _tracer_prix(conn, produit_id, "achat", actuel["prix_achat"], prix_unitaire,
                             "mouvement", "", reference_doc)
            else:
                row_cump = conn.execute("SELECT cump FROM produits WHERE id=?",
                                        (produit_id,)).fetchone()
                cout_unitaire = _num_safe(row_cump["cump"]) if row_cump else 0.0

            conn.execute(
                """INSERT INTO mouvements_stock (produit_id, type_mouvement, quantite, prix_unitaire,
                   reference_doc, notes, stock_avant, stock_apres, utilisateur, date_mouvement,
                   depot_id, cout_unitaire)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (produit_id, type_mouvement, quantite, prix_unitaire, reference_doc, notes,
                 stock_avant, stock_apres, UTILISATEUR_COURANT, _maintenant(),
                 _depot_pour_emplacement(conn, cible_emp), cout_unitaire))

            # v3 : synchroniser stock_depot depuis les compteurs produits
            _sync_depots_depuis_produit(conn, produit_id, sr, sv)

        log_action(f"Mouvement {type_mouvement}", f"{prod['nom']} : {stock_avant} → {stock_apres}")
        return True, f"Stock mis à jour : {stock_avant} → {stock_apres}"
    finally:
        conn.close()


def get_mouvements(produit_id=None, limit=500, type_mouvement=None,
                   date_debut=None, date_fin=None):
    conn = get_connection()
    query = """SELECT m.*, p.nom AS produit_nom, p.reference
               FROM mouvements_stock m
               LEFT JOIN produits p ON m.produit_id = p.id
               WHERE 1=1"""
    params = []
    if produit_id:
        query += " AND m.produit_id=?"
        params.append(produit_id)
    if type_mouvement:
        query += " AND m.type_mouvement=?"
        params.append(type_mouvement)
    if date_debut:
        query += " AND date(m.date_mouvement) >= date(?)"
        params.append(date_debut)
    if date_fin:
        query += " AND date(m.date_mouvement) <= date(?)"
        params.append(date_fin)
    query += " ORDER BY m.date_mouvement DESC, m.id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── VENTES ──────────────────────────────────────────

def _num_safe(valeur, defaut=0.0) -> float:
    """Conversion numérique tolérante (chaînes de paramètres, None, vide…)."""
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return defaut


def _tracer_prix(conn, produit_id, type_prix, ancien, nouveau,
                 origine="", tiers="", reference_doc="") -> None:
    """v3 — Historise un changement de prix. Silencieux si la table n'existe pas."""
    try:
        if abs(_num_safe(ancien) - _num_safe(nouveau)) < 0.01:
            return
        conn.execute(
            """INSERT INTO prix_historique (produit_id, type_prix, ancien_prix, nouveau_prix,
               origine, tiers, reference_doc, utilisateur, date_prix)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (produit_id, type_prix, _num_safe(ancien), _num_safe(nouveau), origine,
             tiers, reference_doc, UTILISATEUR_COURANT, _maintenant()))
    except sqlite3.Error:
        pass


def _depot_pour_emplacement(conn, emplacement_type: str):
    """v3 — Traduit 'vente'/'reserve' en depot_id (compatibilité v2)."""
    try:
        code = "RES" if emplacement_type == "reserve" else "BOU"
        row = conn.execute("SELECT id FROM depots WHERE code=? AND actif=1", (code,)).fetchone()
        if row:
            return row["id"]
        col = 0 if emplacement_type == "reserve" else 1
        row = conn.execute("SELECT id FROM depots WHERE autorise_vente=? AND actif=1 "
                           "ORDER BY ordre LIMIT 1", (col,)).fetchone()
        return row["id"] if row else None
    except sqlite3.Error:
        return None


def _sync_depots_depuis_produit(conn, produit_id: int, stock_reserve: int,
                                stock_vente: int) -> None:
    """
    v3 — Reporte les compteurs v2 (stock_reserve / stock_vente) sur stock_depot.

    Utilisé par add_mouvement, qui raisonne encore en réserve/rayon. Le stock est
    posé sur les dépôts BOU et RES ; les dépôts additionnels ne sont pas touchés
    (ils s'alimentent via transferer() et entree_stock()).
    """
    try:
        for code, qte in (("BOU", stock_vente), ("RES", stock_reserve)):
            row = conn.execute("SELECT id FROM depots WHERE code=? AND actif=1",
                               (code,)).fetchone()
            if not row:
                continue
            autres = conn.execute(
                """SELECT COALESCE(SUM(sd.quantite),0) FROM stock_depot sd
                   JOIN depots d ON d.id=sd.depot_id
                   WHERE sd.produit_id=? AND d.actif=1 AND d.code!=?
                     AND d.autorise_vente=?""",
                (produit_id, code, 1 if code == "BOU" else 0)).fetchone()[0]
            cible = max(0, int(qte) - int(autres or 0))
            conn.execute(
                """INSERT INTO stock_depot (produit_id, depot_id, quantite) VALUES (?,?,?)
                   ON CONFLICT(produit_id, depot_id) DO UPDATE
                   SET quantite=excluded.quantite,
                       date_modification=datetime('now','localtime')""",
                (produit_id, row["id"], cible))
    except sqlite3.Error:
        pass


def _controler_credit(conn, client_id, montant) -> tuple[bool, str]:
    """
    v3 — Refuse une vente à crédit qui dépasserait le plafond du client.
    Utilise la connexion en cours (transaction ouverte) : pas de re-connexion.
    """
    params = {r["cle"]: r["valeur"] for r in
              conn.execute("SELECT cle, valeur FROM parametres").fetchall()}
    if params.get("credit_autorise", "1") != "1":
        return False, "Les ventes à crédit sont désactivées dans les paramètres"
    if not client_id:
        return False, ("Une vente à crédit exige un client identifié. "
                       "Sélectionnez ou créez le client.")

    row = conn.execute("SELECT nom, plafond_credit FROM clients WHERE id=?",
                       (client_id,)).fetchone()
    if not row:
        return False, "Client introuvable"

    plafond = _num_safe(row["plafond_credit"]) or _num_safe(
        params.get("credit_plafond_defaut", 0))
    if plafond <= 0:
        return False, (f"« {row['nom']} » n'a pas de plafond de crédit. "
                       f"Renseignez-le dans sa fiche client avant de vendre à crédit.")

    encours = _num_safe(conn.execute(
        "SELECT COALESCE(SUM(reste_du),0) FROM v_creances WHERE client_id=?",
        (client_id,)).fetchone()[0])
    if encours + _num_safe(montant) > plafond:
        return False, (f"Plafond de crédit dépassé pour « {row['nom']} » :\n"
                       f"encours {encours:,.0f} + {_num_safe(montant):,.0f} "
                       f"> plafond {plafond:,.0f} F CFA")
    return True, "OK"


def create_vente(client_nom, items, remise=0, mode_paiement="Espèces",
                 montant_paye=0, client_id=None, depot_id=None,
                 date_echeance=None, controler_credit=True):
    """
    items = [(produit_id, quantite, prix_unitaire), ...]
    Transaction atomique : vérifie le stock de chaque ligne, cumule les doublons.

    v3 : `depot_id` = dépôt servant la vente (défaut = dépôt par défaut).
         Une vente à crédit contrôle le plafond du client (controler_credit=False
         pour forcer, ex. reprise de données).
    Retourne (succès, message, vente_id).
    """
    if not items:
        return False, "Aucun article dans la vente", None

    # Contrôle de stock sur le cumul par produit, mais lignes conservées
    # par (produit, prix) pour ne pas écraser un prix différent (total faux sinon).
    cumul = {}      # pid -> qty totale (contrôle de stock)
    groupes = {}    # (pid, pu) -> qty (lignes de vente)
    for pid, qty, pu in items:
        qty = int(qty)
        if qty <= 0:
            return False, "Quantité invalide", None
        pu = float(pu)
        cumul[pid] = cumul.get(pid, 0) + qty
        groupes[(pid, pu)] = groupes.get((pid, pu), 0) + qty

    conn = get_connection()
    try:
        with conn:
            # Controle du stock vente avant toute ecriture
            for pid, qty in cumul.items():
                prod = conn.execute("SELECT nom, stock_vente FROM produits WHERE id=?", (pid,)).fetchone()
                if not prod:
                    return False, f"Produit #{pid} introuvable", None
                if qty > prod["stock_vente"]:
                    return False, (f"Stock vente insuffisant pour « {prod['nom']} » : "
                                   f"{prod['stock_vente']} en rayon (reserve dispo via transfert)"), None

            sous_total = sum(qty * pu for (pid, pu), qty in groupes.items())
            remise = max(0.0, float(remise or 0))
            if remise > sous_total:
                return False, "La remise dépasse le montant de la vente", None
            total = sous_total - remise

            # v3 : dépôt servant la vente
            if depot_id is None:
                d = (conn.execute("SELECT id FROM depots WHERE par_defaut=1 AND actif=1").fetchone()
                     or conn.execute("SELECT id FROM depots WHERE autorise_vente=1 AND actif=1 "
                                     "ORDER BY ordre LIMIT 1").fetchone())
                depot_id = d["id"] if d else None

            # v3 : contrôle du plafond de crédit
            echeance = date_echeance
            if mode_paiement == "Crédit":
                du = total - _num_safe(montant_paye)
                if du > 0.01 and controler_credit:
                    ok_credit, msg_credit = _controler_credit(conn, client_id, du)
                    if not ok_credit:
                        return False, msg_credit, None
                if not echeance:
                    delai = int(_num_safe(get_parametres().get("credit_delai_jours", 30), 30))
                    echeance = (datetime.now() + timedelta(days=delai)).strftime("%Y-%m-%d")

            # Crédit : montant_paye reste tel quel (0 = dette), sinon défaut = total
            paye = montant_paye if mode_paiement == "Crédit" else (montant_paye or total)
            cur = conn.execute(
                """INSERT INTO ventes (client_nom, client_id, sous_total, remise, total,
                   mode_paiement, montant_paye, utilisateur, statut, date_vente,
                   depot_id, date_echeance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'validee', ?, ?, ?)""",
                (client_nom or "Client", client_id, sous_total, remise, total,
                 mode_paiement, paye, UTILISATEUR_COURANT, _maintenant(),
                 depot_id, echeance))
            vente_id = cur.lastrowid
            numero = f"{get_parametres().get('prefixe_facture', 'FAC')}-{datetime.now().year}-{vente_id:05d}"
            conn.execute("UPDATE ventes SET numero=? WHERE id=?", (numero, vente_id))

            for (pid, pu), qty in groupes.items():
                prod = conn.execute("SELECT stock, stock_vente, prix_achat FROM produits WHERE id=?", (pid,)).fetchone()
                conn.execute(
                    """INSERT INTO ventes_details (vente_id, produit_id, quantite, prix_unitaire,
                       total, prix_achat) VALUES (?, ?, ?, ?, ?, ?)""",
                    (vente_id, pid, qty, pu, qty * pu, prod["prix_achat"]))
                nouveau_stock = prod["stock"] - qty
                nouveau_vente = prod["stock_vente"] - qty
                conn.execute("UPDATE produits SET stock=?, stock_vente=?, date_modification=CURRENT_TIMESTAMP WHERE id=?",
                             (nouveau_stock, nouveau_vente, pid))
                # v3 : décrémenter le stock du/des dépôt(s) de vente
                _decrementer_depots_vente(conn, pid, qty, depot_id)
                conn.execute(
                    """INSERT INTO mouvements_stock (produit_id, type_mouvement, quantite, prix_unitaire,
                       reference_doc, notes, stock_avant, stock_apres, utilisateur, date_mouvement, depot_id)
                       VALUES (?, 'sortie', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (pid, qty, pu, numero, f"Vente {numero}", prod["stock"], nouveau_stock,
                     UTILISATEUR_COURANT, _maintenant(), depot_id))

        log_action("Vente", f"{numero} - {total:,.0f}")
        return True, numero, vente_id
    finally:
        conn.close()


def _decrementer_depots_vente(conn, produit_id: int, quantite: int,
                              depot_id: int | None = None) -> None:
    """
    v3 — Retire `quantite` du stock des dépôts de vente.

    Si `depot_id` est fourni on sert d'abord ce dépôt, puis on complète sur les
    autres dépôts de vente (le contrôle de stock global a déjà été fait en amont).
    Silencieux si la table stock_depot n'existe pas encore (base v2).
    """
    try:
        cibles = []
        if depot_id:
            cibles.append(depot_id)
        for row in conn.execute(
                """SELECT sd.depot_id FROM stock_depot sd JOIN depots d ON d.id=sd.depot_id
                   WHERE sd.produit_id=? AND d.autorise_vente=1 AND d.actif=1
                     AND sd.quantite > 0 ORDER BY d.ordre""", (produit_id,)).fetchall():
            if row["depot_id"] not in cibles:
                cibles.append(row["depot_id"])

        reste = int(quantite)
        for did in cibles:
            if reste <= 0:
                break
            row = conn.execute(
                "SELECT quantite FROM stock_depot WHERE produit_id=? AND depot_id=?",
                (produit_id, did)).fetchone()
            dispo = row["quantite"] if row else 0
            if dispo <= 0:
                continue
            pris = min(dispo, reste)
            conn.execute(
                """UPDATE stock_depot SET quantite=quantite-?,
                   date_modification=datetime('now','localtime')
                   WHERE produit_id=? AND depot_id=?""", (pris, produit_id, did))
            reste -= pris
    except sqlite3.Error:
        pass  # base v2 sans stock_depot : rien à faire


def _incrementer_depot(conn, produit_id: int, quantite: int,
                       depot_id: int | None = None) -> None:
    """v3 — Remet `quantite` en stock dans un dépôt (annulation de vente, retour)."""
    try:
        if not depot_id:
            row = (conn.execute("SELECT id FROM depots WHERE par_defaut=1 AND actif=1").fetchone()
                   or conn.execute("SELECT id FROM depots WHERE autorise_vente=1 AND actif=1 "
                                   "ORDER BY ordre LIMIT 1").fetchone())
            if not row:
                return
            depot_id = row["id"]
        conn.execute(
            """INSERT INTO stock_depot (produit_id, depot_id, quantite) VALUES (?,?,?)
               ON CONFLICT(produit_id, depot_id) DO UPDATE
               SET quantite = quantite + excluded.quantite,
                   date_modification = datetime('now','localtime')""",
            (produit_id, depot_id, int(quantite)))
    except sqlite3.Error:
        pass


def annuler_vente(vente_id: int, motif: str = "") -> tuple[bool, str]:
    """Annule une vente et remet les quantités en stock (transaction atomique)."""
    conn = get_connection()
    try:
        with conn:
            vente = conn.execute("SELECT * FROM ventes WHERE id=?", (vente_id,)).fetchone()
            if not vente:
                return False, "Vente introuvable"
            if vente["statut"] == "annulee":
                return False, "Cette vente est déjà annulée"

            lignes = conn.execute(
                "SELECT produit_id, quantite, prix_unitaire FROM ventes_details WHERE vente_id=?",
                (vente_id,)).fetchall()
            for l in lignes:
                if l["produit_id"] is None:
                    continue
                prod = conn.execute("SELECT stock, stock_vente FROM produits WHERE id=?", (l["produit_id"],)).fetchone()
                if not prod:
                    continue
                nouveau_stock = prod["stock"] + l["quantite"]
                nouveau_vente = prod["stock_vente"] + l["quantite"]
                conn.execute("UPDATE produits SET stock=?, stock_vente=?, date_modification=CURRENT_TIMESTAMP WHERE id=?",
                             (nouveau_stock, nouveau_vente, l["produit_id"]))
                # v3 : remettre en stock dans le dépôt d'origine de la vente
                _incrementer_depot(conn, l["produit_id"], l["quantite"], vente["depot_id"])
                conn.execute(
                    """INSERT INTO mouvements_stock (produit_id, type_mouvement, quantite, prix_unitaire,
                       reference_doc, notes, stock_avant, stock_apres, utilisateur, date_mouvement, depot_id)
                       VALUES (?, 'entree', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (l["produit_id"], l["quantite"], l["prix_unitaire"], vente["numero"],
                     f"Annulation vente {vente['numero']} {motif}".strip(),
                     prod["stock"], nouveau_stock, UTILISATEUR_COURANT, _maintenant(),
                     vente["depot_id"]))

            conn.execute("UPDATE ventes SET statut='annulee' WHERE id=?", (vente_id,))
        log_action("Annulation vente", f"{vente['numero']} {motif}")
        return True, f"Vente {vente['numero']} annulée, stock restauré"
    finally:
        conn.close()


def get_ventes(limit: int = 200, date_debut: Any = None, date_fin: Any = None, search: str = "", inclure_annulees: bool = True) -> list[dict]:
    conn = get_connection()
    query = """SELECT v.*, COALESCE(v.statut,'validee') AS statut_v,
                      (SELECT COUNT(*) FROM ventes_details d WHERE d.vente_id=v.id) AS nb_lignes
               FROM ventes v WHERE 1=1"""
    params = []
    if not inclure_annulees:
        query += " AND COALESCE(v.statut,'validee')<>'annulee'"
    if date_debut:
        query += " AND date(v.date_vente) >= date(?)"
        params.append(date_debut)
    if date_fin:
        query += " AND date(v.date_vente) <= date(?)"
        params.append(date_fin)
    if search:
        query += " AND (v.client_nom LIKE ? OR v.numero LIKE ?)"
        params.extend([f"%{search}%"] * 2)
    query += " ORDER BY v.date_vente DESC, v.id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_vente_details(vente_id: int) -> tuple[dict | None, list[dict]]:
    conn = get_connection()
    items = conn.execute(
        """SELECT vd.*, COALESCE(p.nom, '(produit supprimé)') AS produit_nom,
                  COALESCE(p.reference,'') AS reference
           FROM ventes_details vd
           LEFT JOIN produits p ON vd.produit_id = p.id
           WHERE vd.vente_id=?""", (vente_id,)).fetchall()
    vente = conn.execute("SELECT * FROM ventes WHERE id=?", (vente_id,)).fetchone()
    conn.close()
    return (dict(vente) if vente else None), [dict(i) for i in items]


# ─── STATISTIQUES / RAPPORTS ────────────────────────

def get_dashboard_stats() -> dict:
    conn = get_connection()
    q = lambda sql, p=(): conn.execute(sql, p).fetchone()[0]
    stats = {
        "total_produits": q("SELECT COUNT(*) FROM produits WHERE COALESCE(actif,1)=1"),
        "produits_inactifs": q("SELECT COUNT(*) FROM produits WHERE COALESCE(actif,1)=0"),
        "total_categories": q("SELECT COUNT(*) FROM categories"),
        "total_fournisseurs": q("SELECT COUNT(*) FROM fournisseurs"),
        "total_clients": q("SELECT COUNT(*) FROM clients"),
        "stock_total": q("SELECT COALESCE(SUM(stock),0) FROM produits"),
        "stock_reserve": q("SELECT COALESCE(SUM(stock_reserve),0) FROM produits"),
        "stock_vente": q("SELECT COALESCE(SUM(stock_vente),0) FROM produits"),
        "valeur_stock": q("SELECT COALESCE(SUM(stock*prix_achat),0) FROM produits"),
        "valeur_stock_vente": q("SELECT COALESCE(SUM(stock_vente*prix_vente),0) FROM produits"),
        "nb_alertes": q("SELECT COUNT(*) FROM produits WHERE stock<=stock_mini AND COALESCE(actif,1)=1"),
        "nb_ruptures": q("SELECT COUNT(*) FROM produits WHERE stock<=0 AND COALESCE(actif,1)=1"),
        "ventes_aujourdhui": q("""SELECT COALESCE(SUM(total),0) FROM ventes
                                  WHERE date(date_vente)=date('now','localtime')
                                    AND COALESCE(statut,'validee')<>'annulee'"""),
        "nb_ventes_aujourdhui": q("""SELECT COUNT(*) FROM ventes
                                     WHERE date(date_vente)=date('now','localtime')
                                       AND COALESCE(statut,'validee')<>'annulee'"""),
        "ventes_mois": q("""SELECT COALESCE(SUM(total),0) FROM ventes
                            WHERE strftime('%Y-%m',date_vente)=strftime('%Y-%m','now','localtime')
                              AND COALESCE(statut,'validee')<>'annulee'"""),
        "marge_mois": q("""SELECT COALESCE(SUM((vd.prix_unitaire-vd.prix_achat)*vd.quantite),0)
                           - COALESCE((SELECT SUM(remise) FROM ventes
                                       WHERE strftime('%Y-%m',date_vente)=strftime('%Y-%m','now','localtime')
                                         AND COALESCE(statut,'validee')<>'annulee'),0)
                           FROM ventes_details vd JOIN ventes v ON v.id=vd.vente_id
                           WHERE strftime('%Y-%m',v.date_vente)=strftime('%Y-%m','now','localtime')
                             AND COALESCE(v.statut,'validee')<>'annulee'"""),
    }

    stats["alertes_stock"] = [dict(r) for r in conn.execute(
            """SELECT p.id, p.reference, p.nom, p.stock, p.stock_mini, p.stock_vente,
                      c.nom AS categorie_nom,
                      COALESCE((SELECT SUM(vd.quantite) FROM ventes_details vd
                                JOIN ventes v ON v.id=vd.vente_id
                                WHERE vd.produit_id=p.id
                                  AND date(v.date_vente)>=date('now','localtime','-30 days')
                                  AND COALESCE(v.statut,'validee')<>'annulee'), 0)
                      / 30.0 AS vente_journaliere
               FROM produits p LEFT JOIN categories c ON c.id=p.categorie_id
               WHERE p.stock<=p.stock_mini AND COALESCE(p.actif,1)=1
               ORDER BY (p.stock - p.stock_mini) ASC, p.stock ASC LIMIT 15""").fetchall()]

    # Ajouter rupture_jours à chaque alerte
    for a in stats["alertes_stock"]:
        vj = a["vente_journaliere"]
        a["rupture_jours"] = round(a["stock_vente"] / vj) if vj > 0 else None


    stats["dernieres_ventes"] = [dict(r) for r in conn.execute(
        """SELECT id, numero, client_nom, total, date_vente, COALESCE(statut,'validee') AS statut
           FROM ventes ORDER BY date_vente DESC, id DESC LIMIT 8""").fetchall()]

    stats["top_produits"] = [dict(r) for r in conn.execute(
        """SELECT COALESCE(p.nom,'(supprimé)') AS nom, SUM(vd.quantite) AS qte,
                  SUM(vd.total) AS ca
           FROM ventes_details vd
           JOIN ventes v ON v.id=vd.vente_id
           LEFT JOIN produits p ON p.id=vd.produit_id
           WHERE COALESCE(v.statut,'validee')<>'annulee'
             AND date(v.date_vente)>=date('now','localtime','-30 days')
           GROUP BY vd.produit_id ORDER BY qte DESC LIMIT 8""").fetchall()]

    stats["ventes_7j"] = [dict(r) for r in conn.execute(
        """SELECT date(date_vente) AS jour, COALESCE(SUM(total),0) AS ca, COUNT(*) AS nb
           FROM ventes
           WHERE date(date_vente)>=date('now','localtime','-6 days')
             AND COALESCE(statut,'validee')<>'annulee'
           GROUP BY date(date_vente) ORDER BY jour""").fetchall()]

    # ── Comparaisons de progression ──
    stats["ventes_hier"] = q("""SELECT COALESCE(SUM(total),0) FROM ventes
                                WHERE date(date_vente)=date('now','localtime','-1 day')
                                  AND COALESCE(statut,'validee')<>'annulee'""")
    stats["ventes_semaine"] = q("""SELECT COALESCE(SUM(total),0) FROM ventes
                                   WHERE date(date_vente)>=date('now','localtime','-6 days')
                                     AND COALESCE(statut,'validee')<>'annulee'""")
    stats["ventes_semaine_prec"] = q("""SELECT COALESCE(SUM(total),0) FROM ventes
                                        WHERE date(date_vente) BETWEEN date('now','localtime','-13 days')
                                              AND date('now','localtime','-7 days')
                                          AND COALESCE(statut,'validee')<>'annulee'""")
    stats["ventes_mois_prec"] = q("""SELECT COALESCE(SUM(total),0) FROM ventes
                                     WHERE strftime('%Y-%m',date_vente)=
                                           strftime('%Y-%m',date('now','localtime','start of month','-1 day'))
                                       AND COALESCE(statut,'validee')<>'annulee'""")

    # ── Activité par vendeur (mois en cours) ──
    stats["par_vendeur_mois"] = [dict(r) for r in conn.execute(
        """SELECT COALESCE(NULLIF(utilisateur,''),'(non renseigné)') AS vendeur, COUNT(*) AS nb,
                  COALESCE(SUM(total),0) AS ca,
                  COALESCE(AVG(total),0) AS panier
           FROM ventes
           WHERE strftime('%Y-%m',date_vente)=strftime('%Y-%m','now','localtime')
             AND COALESCE(statut,'validee')<>'annulee'
           GROUP BY utilisateur ORDER BY ca DESC""").fetchall()]

    # ── Paiements du mois ──
    stats["par_paiement_mois"] = [dict(r) for r in conn.execute(
        """SELECT COALESCE(mode_paiement,'Espèces') AS mode, COUNT(*) AS nb,
                  COALESCE(SUM(total),0) AS ca
           FROM ventes
           WHERE strftime('%Y-%m',date_vente)=strftime('%Y-%m','now','localtime')
             AND COALESCE(statut,'validee')<>'annulee'
           GROUP BY mode_paiement ORDER BY ca DESC""").fetchall()]

    # ── CA des 30 derniers jours (courbe) ──
    stats["ventes_30j"] = [dict(r) for r in conn.execute(
        """SELECT date(date_vente) AS jour, COALESCE(SUM(total),0) AS ca
           FROM ventes
           WHERE date(date_vente)>=date('now','localtime','-29 days')
             AND COALESCE(statut,'validee')<>'annulee'
           GROUP BY date(date_vente) ORDER BY jour""").fetchall()]

    conn.close()
    return stats


def rapport_ventes(date_debut, date_fin) -> dict:
    """Synthèse du chiffre d'affaires et de la marge sur une période."""
    conn = get_connection()
    resume = dict(conn.execute(
        """SELECT COUNT(*) AS nb_ventes, COALESCE(SUM(total),0) AS ca,
                  COALESCE(SUM(remise),0) AS remises,
                  COALESCE(AVG(total),0) AS panier_moyen
           FROM ventes WHERE date(date_vente) BETWEEN date(?) AND date(?)
             AND COALESCE(statut,'validee')<>'annulee'""", (date_debut, date_fin)).fetchone())

    resume["marge"] = conn.execute(
        """SELECT COALESCE(SUM((vd.prix_unitaire-vd.prix_achat)*vd.quantite),0)
           FROM ventes_details vd JOIN ventes v ON v.id=vd.vente_id
           WHERE date(v.date_vente) BETWEEN date(?) AND date(?)
             AND COALESCE(v.statut,'validee')<>'annulee'""", (date_debut, date_fin)).fetchone()[0]
    # La remise réduit le CA encaissé : on la déduit aussi de la marge réelle
    resume["marge"] -= resume["remises"] or 0

    resume["articles_vendus"] = conn.execute(
        """SELECT COALESCE(SUM(vd.quantite),0) FROM ventes_details vd
           JOIN ventes v ON v.id=vd.vente_id
           WHERE date(v.date_vente) BETWEEN date(?) AND date(?)
             AND COALESCE(v.statut,'validee')<>'annulee'""", (date_debut, date_fin)).fetchone()[0]

    par_jour = [dict(r) for r in conn.execute(
        """SELECT date(date_vente) AS jour, COUNT(*) AS nb, COALESCE(SUM(total),0) AS ca
           FROM ventes WHERE date(date_vente) BETWEEN date(?) AND date(?)
             AND COALESCE(statut,'validee')<>'annulee'
           GROUP BY date(date_vente) ORDER BY jour DESC""", (date_debut, date_fin)).fetchall()]

    par_produit = [dict(r) for r in conn.execute(
        """SELECT COALESCE(p.reference,'') AS reference,
                  COALESCE(p.nom,'(supprimé)') AS nom,
                  SUM(vd.quantite) AS qte, SUM(vd.total) AS ca,
                  SUM((vd.prix_unitaire-vd.prix_achat)*vd.quantite) AS marge
           FROM ventes_details vd JOIN ventes v ON v.id=vd.vente_id
           LEFT JOIN produits p ON p.id=vd.produit_id
           WHERE date(v.date_vente) BETWEEN date(?) AND date(?)
             AND COALESCE(v.statut,'validee')<>'annulee'
           GROUP BY vd.produit_id ORDER BY ca DESC""", (date_debut, date_fin)).fetchall()]

    par_categorie = [dict(r) for r in conn.execute(
        """SELECT COALESCE(c.nom,'Sans catégorie') AS categorie,
                  SUM(vd.quantite) AS qte, SUM(vd.total) AS ca
           FROM ventes_details vd JOIN ventes v ON v.id=vd.vente_id
           LEFT JOIN produits p ON p.id=vd.produit_id
           LEFT JOIN categories c ON c.id=p.categorie_id
           WHERE date(v.date_vente) BETWEEN date(?) AND date(?)
             AND COALESCE(v.statut,'validee')<>'annulee'
           GROUP BY c.id ORDER BY ca DESC""", (date_debut, date_fin)).fetchall()]

    par_paiement = [dict(r) for r in conn.execute(
        """SELECT COALESCE(mode_paiement,'Espèces') AS mode, COUNT(*) AS nb,
                  COALESCE(SUM(total),0) AS ca
           FROM ventes WHERE date(date_vente) BETWEEN date(?) AND date(?)
             AND COALESCE(statut,'validee')<>'annulee'
           GROUP BY mode_paiement ORDER BY ca DESC""", (date_debut, date_fin)).fetchall()]

    conn.close()
    return {"resume": resume, "par_jour": par_jour, "par_produit": par_produit,
            "par_categorie": par_categorie, "par_paiement": par_paiement}


def rapport_stock() -> dict:
    conn = get_connection()
    par_categorie = [dict(r) for r in conn.execute(
        """SELECT COALESCE(c.nom,'Sans catégorie') AS categorie, COUNT(p.id) AS nb_produits,
                  COALESCE(SUM(p.stock),0) AS qte,
                  COALESCE(SUM(p.stock*p.prix_achat),0) AS valeur_achat,
                  COALESCE(SUM(p.stock*p.prix_vente),0) AS valeur_vente
           FROM produits p LEFT JOIN categories c ON c.id=p.categorie_id
           WHERE COALESCE(p.actif,1)=1
           GROUP BY c.id ORDER BY valeur_achat DESC""").fetchall()]
    dormants = [dict(r) for r in conn.execute(
        """SELECT p.reference, p.nom, p.stock, p.prix_achat,
                  (SELECT MAX(m.date_mouvement) FROM mouvements_stock m
                    WHERE m.produit_id=p.id AND m.type_mouvement='sortie') AS derniere_sortie
           FROM produits p WHERE COALESCE(p.actif,1)=1 AND p.stock>0
           ORDER BY derniere_sortie IS NOT NULL, derniere_sortie ASC LIMIT 20""").fetchall()]
    conn.close()
    return {"par_categorie": par_categorie, "dormants": dormants}


# ─── EXPORT CSV / SAUVEGARDE ────────────────────────

def export_csv(nom_fichier: str, entetes, lignes) -> str:
    os.makedirs(EXPORT_DIR, exist_ok=True)
    chemin = os.path.join(EXPORT_DIR, nom_fichier)
    # Protection anti-injection CSV : préfixer les cellules commençant par
    # = + - @ pour éviter l'exécution de formules dans Excel
    def _securiser(val):
        s = str(val or "")
        if s and s[0] in "=+-@":
            return "'" + s
        return s
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(entetes)
        for ligne in lignes:
            w.writerow([_securiser(c) for c in ligne])
    return chemin


def exporter_produits() -> str:
    produits = get_produits()
    lignes = [[p["reference"], p["nom"], p["categorie_nom"] or "", p["marque"],
               p["code_barres"] or "", p["stock"], p["stock_mini"],
               p["prix_achat"], p["prix_vente"], p["marge_unitaire"],
               p["valeur_stock"], p["emplacement"], p["fournisseur_nom"] or "",
               "Oui" if p.get("actif", 1) else "Non"] for p in produits]
    return export_csv(f"produits_{datetime.now():%Y%m%d_%H%M}.csv",
                      ["Référence", "Nom", "Catégorie", "Marque", "Code-barres", "Stock",
                       "Stock mini", "Prix achat", "Prix vente", "Marge unitaire",
                       "Valeur stock", "Emplacement", "Fournisseur", "Actif"], lignes)


def exporter_ventes(date_debut: Any = None, date_fin: Any = None) -> str:
    ventes = get_ventes(limit=100000, date_debut=date_debut, date_fin=date_fin)
    lignes = [[v["numero"], v["date_vente"], v["client_nom"], v["nb_lignes"],
               v.get("sous_total", 0), v.get("remise", 0), v["total"],
               v.get("mode_paiement", ""), v.get("utilisateur", ""), v["statut_v"]] for v in ventes]
    return export_csv(f"ventes_{datetime.now():%Y%m%d_%H%M}.csv",
                      ["N° facture", "Date", "Client", "Lignes", "Sous-total", "Remise",
                       "Total", "Paiement", "Vendeur", "Statut"], lignes)


def exporter_mouvements(limit: int = 100000) -> str:
    mvts = get_mouvements(limit=limit)
    lignes = [[m["date_mouvement"], m["type_mouvement"], m["reference"] or "", m["produit_nom"] or "",
               m["quantite"], m.get("stock_avant", ""), m.get("stock_apres", ""),
               m["prix_unitaire"], m["reference_doc"], m["notes"], m.get("utilisateur", "")]
              for m in mvts]
    return export_csv(f"mouvements_{datetime.now():%Y%m%d_%H%M}.csv",
                      ["Date", "Type", "Référence", "Produit", "Quantité", "Stock avant",
                       "Stock après", "Prix unitaire", "Document", "Notes", "Utilisateur"], lignes)


def importer_produits_csv(chemin: str) -> tuple[bool, str, int, int]:
    """Importe/actualise des produits depuis un CSV (Référence;Nom;Catégorie;...)."""
    if not os.path.exists(chemin):
        return False, "Fichier introuvable", 0, 0
    cats = {c["nom"].lower(): c["id"] for c in get_categories()}
    ajoutes = maj = 0
    erreurs = []
    with open(chemin, newline="", encoding="utf-8-sig") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        for i, ligne in enumerate(lecteur, start=2):
            ref = (ligne.get("Référence") or ligne.get("reference") or "").strip()
            nom = (ligne.get("Nom") or ligne.get("nom") or "").strip()
            if not ref or not nom:
                erreurs.append(f"ligne {i} : référence ou nom manquant")
                continue

            def num(cle, defaut=0):
                try:
                    return float(str(ligne.get(cle, defaut) or defaut).replace(",", ".").replace(" ", ""))
                except ValueError:
                    return defaut

            cat_nom = (ligne.get("Catégorie") or "").strip().lower()
            cat_id = cats.get(cat_nom)
            existant = trouver_produit(ref)
            if existant:
                update_produit(existant["id"], ref, nom,
                               description=existant.get("description", ""),
                               categorie_id=cat_id or existant["categorie_id"],
                               fournisseur_id=existant.get("fournisseur_id"),
                               marque=(ligne.get("Marque") or existant["marque"]),
                               prix_achat=num("Prix achat", existant["prix_achat"]),
                               prix_vente=num("Prix vente", existant["prix_vente"]),
                               stock_mini=int(num("Stock mini", existant["stock_mini"])),
                               emplacement=(ligne.get("Emplacement") or existant["emplacement"]),
                               code_barres=(ligne.get("Code-barres") or existant.get("code_barres") or ""),
                               actif=existant.get("actif", 1),
                               emplacement_type=existant.get("emplacement_type", "vente"))
                maj += 1
            else:
                ok, _ = add_produit(ref, nom, categorie_id=cat_id,
                                    marque=(ligne.get("Marque") or ""),
                                    prix_achat=num("Prix achat"), prix_vente=num("Prix vente"),
                                    stock_vente=int(num("Stock")), stock_mini=int(num("Stock mini", 5)),
                                    emplacement=(ligne.get("Emplacement") or ""),
                                    code_barres=(ligne.get("Code-barres") or ""))
                if ok:
                    ajoutes += 1
                else:
                    erreurs.append(f"ligne {i} : {ref}")
    msg = f"{ajoutes} produit(s) ajouté(s), {maj} mis à jour"
    if erreurs:
        msg += f" — {len(erreurs)} ignorée(s)"
    log_action("Import CSV produits", msg)
    return True, msg, ajoutes, maj


def sauvegarder_base(max_conserver: int = 30) -> str:
    """Copie sécurisée de la base (checkpoint WAL inclus) + rotation."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    cible = os.path.join(BACKUP_DIR, f"sauvegarde_{datetime.now():%Y%m%d_%H%M%S}.db")
    conn = get_connection()
    try:
        conn.execute("PRAGMA wal_checkpoint(FULL)")
        dest = sqlite3.connect(cible)
        with dest:
            conn.backup(dest)
        dest.close()
    finally:
        conn.close()
    # Rotation : on garde les `max_conserver` sauvegardes automatiques les plus récentes
    autos = sorted(f for f in os.listdir(BACKUP_DIR)
                   if f.startswith("sauvegarde_") and f.endswith(".db"))
    for ancien in autos[:-max_conserver]:
        try:
            os.remove(os.path.join(BACKUP_DIR, ancien))
        except OSError:
            pass
    log_action("Sauvegarde base", os.path.basename(cible))
    return cible


def restaurer_base(chemin: str) -> tuple[bool, str]:
    if not os.path.exists(chemin):
        return False, "Fichier de sauvegarde introuvable"
    try:
        controle = sqlite3.connect(chemin)
        controle.execute("SELECT COUNT(*) FROM produits").fetchone()
        controle.close()
    except sqlite3.Error:
        return False, "Ce fichier n'est pas une base valide"

    os.makedirs(BACKUP_DIR, exist_ok=True)
    secours = os.path.join(BACKUP_DIR, f"avant_restauration_{datetime.now():%Y%m%d_%H%M%S}.db")

    # Fusionne le WAL dans le fichier principal puis libère le verrou,
    # sinon Windows refuse de supprimer test.db-wal (WinError 32).
    conn = get_connection()
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        dest = sqlite3.connect(secours)
        with dest:
            conn.backup(dest)
        dest.close()
    finally:
        conn.close()

    # Restauration via l'API backup de SQLite : on écrit directement DANS la base
    # active au lieu de remplacer les fichiers. Évite les WinError 32 / "database
    # is locked" liés au journal WAL sous Windows.
    derniere_erreur = None
    for tentative in range(5):
        source = cible = None
        try:
            source = sqlite3.connect(chemin)
            cible = get_connection()
            cible.execute("PRAGMA foreign_keys = OFF")
            source.backup(cible)
            cible.commit()
            log_action("Restauration base", os.path.basename(chemin))
            return True, f"Base restaurée. Ancienne version : {os.path.basename(secours)}"
        except sqlite3.Error as e:
            derniere_erreur = e
            time.sleep(0.5)
        finally:
            for c in (source, cible):
                if c is not None:
                    try:
                        c.close()
                    except sqlite3.Error:
                        pass

    return False, (f"Restauration impossible : {derniere_erreur}\n"
                   "Fermez les autres fenêtres du logiciel puis réessayez.")


def lister_sauvegardes() -> list[dict]:
    if not os.path.isdir(BACKUP_DIR):
        return []
    fichiers = []
    for nom in os.listdir(BACKUP_DIR):
        if nom.endswith(".db"):
            chemin = os.path.join(BACKUP_DIR, nom)
            fichiers.append({"nom": nom, "chemin": chemin,
                             "taille": os.path.getsize(chemin),
                             "date": datetime.fromtimestamp(os.path.getmtime(chemin))})
    return sorted(fichiers, key=lambda f: f["date"], reverse=True)


if __name__ == "__main__":
    print("Initialisation / migration de la base…")
    init_database()
    s = get_dashboard_stats()
    print(f"Base : {DB_PATH}")
    print(f"Produits actifs : {s['total_produits']} | Alertes : {s['nb_alertes']} | "
          f"Valeur stock : {s['valeur_stock']:,.0f}")
    print("OK")
