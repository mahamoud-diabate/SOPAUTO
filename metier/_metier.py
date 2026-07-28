"""
SODIPAC - Couche métier v3
==========================

Fonctions métier des nouveautés v3. Importable depuis database.py ou main.py.

  • CUMP (coût moyen pondéré) + historique des prix
  • Multi-dépôt : stock par dépôt, transferts inter-dépôts
  • Créances clients & règlements / dettes fournisseurs
  • Achats : commandes fournisseur + réception (qui alimente le CUMP)
  • Inventaire physique : ouverture, comptage, clôture avec écarts
  • Retours / avoirs
  • Compatibilité véhicule & références croisées
  • Prévision de rupture (couverture en jours)

Toutes les écritures sont atomiques (`with conn:`) et journalisées.
Chaque fonction retourne (succes: bool, message: str[, id]).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from database import (
    get_connection, get_parametres, log_action, _maintenant,
    UTILISATEUR_COURANT,
)
import database as _db


def _user() -> str:
    """Utilisateur courant (relu dynamiquement : la valeur change après login)."""
    return _db.UTILISATEUR_COURANT


from ui_widgets import parse_float


def _numero(prefixe_cle: str, defaut: str, table: str, rowid: int) -> str:
    prefixe = get_parametres().get(prefixe_cle, defaut)
    return f"{prefixe}-{datetime.now().year}-{rowid:05d}"


# ═══════════════════════════════════════════════════════
#  DÉPÔTS
# ═══════════════════════════════════════════════════════

def get_depots(actifs_seulement: bool = True) -> list[dict]:
    conn = get_connection()
    sql = "SELECT * FROM depots"
    if actifs_seulement:
        sql += " WHERE actif=1"
    sql += " ORDER BY ordre, nom"
    rows = conn.execute(sql).fetchall()
    
    return [dict(r) for r in rows]


def get_depot_defaut() -> dict | None:
    conn = get_connection()
    row = (conn.execute("SELECT * FROM depots WHERE par_defaut=1 AND actif=1").fetchone()
           or conn.execute("SELECT * FROM depots WHERE autorise_vente=1 AND actif=1 "
                           "ORDER BY ordre LIMIT 1").fetchone())
    
    return dict(row) if row else None


def add_depot(code: str, nom: str, type_depot: str = "boutique", adresse: str = "",
              responsable: str = "", telephone: str = "",
              autorise_vente: bool = True) -> tuple[bool, str]:
    code = (code or "").strip().upper()
    nom = (nom or "").strip()
    if not code or not nom:
        return False, "Le code et le nom sont requis"
    if type_depot not in ("boutique", "reserve", "magasin", "vehicule", "autre"):
        return False, "Type de dépôt invalide"
    conn = get_connection()
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO depots (code, nom, type, adresse, responsable, telephone,
                   autorise_vente, ordre)
                   VALUES (?,?,?,?,?,?,?, (SELECT COALESCE(MAX(ordre),0)+1 FROM depots))""",
                (code, nom, type_depot, adresse, responsable, telephone,
                 1 if autorise_vente else 0))
            depot_id = cur.lastrowid
            # Créer les lignes de stock à 0 pour tous les produits existants
            conn.execute(
                "INSERT OR IGNORE INTO stock_depot (produit_id, depot_id, quantite) "
                "SELECT id, ?, 0 FROM produits", (depot_id,))
        log_action("Ajout dépôt", f"{code} - {nom}")
        return True, "Dépôt créé"
    except sqlite3.IntegrityError:
        return False, "Ce code de dépôt existe déjà"
    finally:
        pass


def update_depot(depot_id: int, **champs) -> tuple[bool, str]:
    autorises = {"code", "nom", "type", "adresse", "responsable", "telephone",
                 "autorise_vente", "actif", "ordre"}
    maj = {k: v for k, v in champs.items() if k in autorises and v is not None}
    if not maj:
        return False, "Rien à modifier"
    conn = get_connection()
    try:
        # Ne pas désactiver le dernier dépôt de vente
        if maj.get("actif") in (0, False) or maj.get("autorise_vente") in (0, False):
            nb = conn.execute("SELECT COUNT(*) FROM depots WHERE actif=1 AND autorise_vente=1 "
                              "AND id!=?", (depot_id,)).fetchone()[0]
            if nb == 0:
                return False, "Impossible : c'est le dernier dépôt de vente actif"
        sets = ", ".join(f"{k}=?" for k in maj)
        with conn:
            conn.execute(f"UPDATE depots SET {sets} WHERE id=?",
                         [*maj.values(), depot_id])
        log_action("Modification dépôt", f"id={depot_id}")
        return True, "Dépôt modifié"
    except sqlite3.IntegrityError:
        return False, "Ce code de dépôt existe déjà"
    finally:
        pass


def delete_depot(depot_id: int) -> tuple[bool, str]:
    conn = get_connection()
    try:
        reste = conn.execute("SELECT COALESCE(SUM(quantite),0) FROM stock_depot WHERE depot_id=?",
                             (depot_id,)).fetchone()[0]
        if reste:
            return False, f"Impossible : {reste} article(s) encore en stock dans ce dépôt"
        nb = conn.execute("SELECT COUNT(*) FROM depots WHERE actif=1 AND id!=?",
                          (depot_id,)).fetchone()[0]
        if nb == 0:
            return False, "Impossible : c'est le dernier dépôt"
        with conn:
            conn.execute("DELETE FROM depots WHERE id=?", (depot_id,))
        log_action("Suppression dépôt", f"id={depot_id}")
        return True, "Dépôt supprimé"
    finally:
        pass


def get_stock_par_depot(produit_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT d.id AS depot_id, d.code, d.nom, d.autorise_vente,
                  COALESCE(sd.quantite,0) AS quantite,
                  COALESCE(sd.stock_mini,0) AS stock_mini,
                  COALESCE(sd.stock_maxi,0) AS stock_maxi,
                  COALESCE(sd.emplacement,'') AS emplacement
           FROM depots d
           LEFT JOIN stock_depot sd ON sd.depot_id=d.id AND sd.produit_id=?
           WHERE d.actif=1 ORDER BY d.ordre, d.nom""", (produit_id,)).fetchall()
    
    return [dict(r) for r in rows]


def _stock_dispo(conn, produit_id: int, depot_id: int) -> int:
    row = conn.execute("SELECT quantite FROM stock_depot WHERE produit_id=? AND depot_id=?",
                       (produit_id, depot_id)).fetchone()
    return row["quantite"] if row else 0


def _appliquer_stock(conn, produit_id: int, depot_id: int, delta: int) -> None:
    """Ajoute `delta` (peut être négatif) au stock du dépôt et resynchronise produits."""
    conn.execute(
        """INSERT INTO stock_depot (produit_id, depot_id, quantite)
           VALUES (?,?,?)
           ON CONFLICT(produit_id, depot_id) DO UPDATE
           SET quantite = quantite + excluded.quantite,
               date_modification = datetime('now','localtime')""",
        (produit_id, depot_id, delta))
    _resync_produit(conn, produit_id)


def _resync_produit(conn, produit_id: int) -> None:
    """
    Recalcule produits.stock / stock_vente / stock_reserve depuis stock_depot.
    Garantit la compatibilité avec tout le code v2 existant.
    """
    conn.execute("""
        UPDATE produits SET
          stock = COALESCE((SELECT SUM(quantite) FROM stock_depot
                            WHERE produit_id=?), 0),
          stock_vente = COALESCE((SELECT SUM(sd.quantite) FROM stock_depot sd
                                  JOIN depots d ON d.id=sd.depot_id
                                  WHERE sd.produit_id=? AND d.autorise_vente=1
                                    AND d.actif=1), 0),
          stock_reserve = COALESCE((SELECT SUM(sd.quantite) FROM stock_depot sd
                                    JOIN depots d ON d.id=sd.depot_id
                                    WHERE sd.produit_id=? AND d.autorise_vente=0
                                      AND d.actif=1), 0),
          date_modification = datetime('now','localtime')
        WHERE id=?""", (produit_id, produit_id, produit_id, produit_id))


def transferer(produit_id: int, depot_source_id: int, depot_dest_id: int,
               quantite: int, notes: str = "") -> tuple[bool, str]:
    """Transfert de stock entre deux dépôts. Atomique."""
    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        return False, "Quantité invalide"
    if quantite <= 0:
        return False, "La quantité doit être supérieure à 0"
    if depot_source_id == depot_dest_id:
        return False, "Les dépôts source et destination sont identiques"

    conn = get_connection()
    try:
        with conn:
            prod = conn.execute("SELECT nom, cump FROM produits WHERE id=?",
                                (produit_id,)).fetchone()
            if not prod:
                return False, "Produit introuvable"
            dispo = _stock_dispo(conn, produit_id, depot_source_id)
            if quantite > dispo:
                return False, f"Stock insuffisant dans le dépôt source : {dispo} disponible(s)"

            _appliquer_stock(conn, produit_id, depot_source_id, -quantite)
            _appliquer_stock(conn, produit_id, depot_dest_id, quantite)

            total = conn.execute("SELECT stock FROM produits WHERE id=?",
                                 (produit_id,)).fetchone()["stock"]
            conn.execute(
                """INSERT INTO mouvements_stock
                   (produit_id, type_mouvement, quantite, prix_unitaire, notes,
                    stock_avant, stock_apres, utilisateur, date_mouvement,
                    depot_id, depot_source_id, cout_unitaire)
                   VALUES (?,'transfert',?,?,?,?,?,?,?,?,?,?)""",
                (produit_id, quantite, prod["cump"], notes, total, total,
                 _user(), _maintenant(), depot_dest_id, depot_source_id, prod["cump"]))
        log_action("Transfert stock", f"produit={produit_id} {quantite}u "
                                      f"dépôt {depot_source_id}→{depot_dest_id}")
        return True, f"{quantite} article(s) transféré(s)"
    finally:
        pass


# ═══════════════════════════════════════════════════════
#  CUMP (COÛT MOYEN PONDÉRÉ) + HISTORIQUE DES PRIX
# ═══════════════════════════════════════════════════════

def enregistrer_prix(conn, produit_id: int, type_prix: str, ancien: float,
                     nouveau: float, origine: str = "", tiers: str = "",
                     reference_doc: str = "") -> None:
    """Trace un changement de prix. Ne fait rien si le prix est inchangé."""
    if abs(parse_float(ancien) - parse_float(nouveau)) < 0.01:
        return
    conn.execute(
        """INSERT INTO prix_historique
           (produit_id, type_prix, ancien_prix, nouveau_prix, origine, tiers,
            reference_doc, utilisateur, date_prix)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (produit_id, type_prix, parse_float(ancien), parse_float(nouveau), origine, tiers,
         reference_doc, _user(), _maintenant()))


def calculer_cump(stock_actuel: int, cump_actuel: float,
                  qte_entree: int, prix_entree: float) -> float:
    """
    Coût moyen pondéré après une entrée.

        CUMP = (stock × cump + qté × prix) / (stock + qté)

    Le stock négatif ou nul est traité comme 0 : le nouveau prix devient le CUMP.
    """
    stock_actuel = max(0, int(stock_actuel or 0))
    qte_entree = int(qte_entree or 0)
    cump_actuel = parse_float(cump_actuel)
    prix_entree = parse_float(prix_entree)
    if qte_entree <= 0:
        return cump_actuel
    if stock_actuel <= 0 or cump_actuel <= 0:
        return prix_entree
    total_qte = stock_actuel + qte_entree
    return (stock_actuel * cump_actuel + qte_entree * prix_entree) / total_qte


def _maj_cump(conn, produit_id: int, qte_entree: int, prix_entree: float,
              origine: str = "", tiers: str = "", reference_doc: str = "") -> float:
    """Recalcule et enregistre le CUMP après une entrée. Retourne le nouveau CUMP."""
    prod = conn.execute("SELECT stock, cump, prix_achat FROM produits WHERE id=?",
                        (produit_id,)).fetchone()
    if not prod:
        return 0.0
    ancien = parse_float(prod["cump"]) or parse_float(prod["prix_achat"])
    nouveau = calculer_cump(prod["stock"], ancien, qte_entree, prix_entree)
    conn.execute("UPDATE produits SET cump=?, prix_achat=?, date_dernier_achat=? WHERE id=?",
                 (round(nouveau, 2), parse_float(prix_entree), _maintenant(), produit_id))
    enregistrer_prix(conn, produit_id, "cump", ancien, nouveau, origine, tiers, reference_doc)
    enregistrer_prix(conn, produit_id, "achat", prod["prix_achat"], prix_entree,
                     origine, tiers, reference_doc)
    return round(nouveau, 2)


def entree_stock(produit_id: int, depot_id: int, quantite: int, prix_unitaire: float,
                 origine: str = "manuel", tiers: str = "", reference_doc: str = "",
                 notes: str = "") -> tuple[bool, str]:
    """Entrée de stock dans un dépôt, avec mise à jour du CUMP."""
    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        return False, "Quantité invalide"
    if quantite <= 0:
        return False, "La quantité doit être supérieure à 0"

    conn = get_connection()
    try:
        with conn:
            prod = conn.execute("SELECT nom, stock FROM produits WHERE id=?",
                                (produit_id,)).fetchone()
            if not prod:
                return False, "Produit introuvable"
            avant = prod["stock"]
            cump = _maj_cump(conn, produit_id, quantite, prix_unitaire,
                             origine, tiers, reference_doc)
            _appliquer_stock(conn, produit_id, depot_id, quantite)
            apres = conn.execute("SELECT stock FROM produits WHERE id=?",
                                 (produit_id,)).fetchone()["stock"]
            conn.execute(
                """INSERT INTO mouvements_stock
                   (produit_id, type_mouvement, quantite, prix_unitaire, reference_doc,
                    notes, stock_avant, stock_apres, utilisateur, date_mouvement,
                    depot_id, cout_unitaire)
                   VALUES (?,'entree',?,?,?,?,?,?,?,?,?,?)""",
                (produit_id, quantite, parse_float(prix_unitaire), reference_doc, notes,
                 avant, apres, _user(), _maintenant(), depot_id, cump))
        log_action("Entrée stock", f"produit={produit_id} +{quantite} (CUMP {cump})")
        return True, f"{quantite} article(s) entré(s) — CUMP recalculé : {cump:,.0f}"
    finally:
        pass


def get_historique_prix(produit_id: int, type_prix: str = "", limit: int = 100) -> list[dict]:
    conn = get_connection()
    sql = "SELECT * FROM prix_historique WHERE produit_id=?"
    params: list = [produit_id]
    if type_prix:
        sql += " AND type_prix=?"
        params.append(type_prix)
    sql += " ORDER BY date_prix DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    
    return [dict(r) for r in rows]


def dernier_prix_vente_client(produit_id: int, client_id: int) -> dict | None:
    """« On lui a vendu ça à combien la dernière fois ? »"""
    conn = get_connection()
    row = conn.execute(
        """SELECT vd.prix_unitaire, vd.quantite, v.date_vente, v.numero
           FROM ventes_details vd JOIN ventes v ON v.id=vd.vente_id
           WHERE vd.produit_id=? AND v.client_id=? AND v.statut='validee'
           ORDER BY v.date_vente DESC LIMIT 1""", (produit_id, client_id)).fetchone()
    
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════
#  CRÉANCES CLIENTS & RÈGLEMENTS
# ═══════════════════════════════════════════════════════

def get_creances(client_id: int | None = None, seuil_jours: int = 0) -> list[dict]:
    """Ventes à crédit non soldées, les plus anciennes d'abord."""
    conn = get_connection()
    sql = "SELECT * FROM v_creances WHERE 1=1"
    params: list = []
    if client_id:
        sql += " AND client_id=?"
        params.append(client_id)
    if seuil_jours:
        sql += " AND anciennete_jours >= ?"
        params.append(seuil_jours)
    sql += " ORDER BY anciennete_jours DESC"
    rows = conn.execute(sql, params).fetchall()
    
    return [dict(r) for r in rows]


def get_creances_par_client() -> list[dict]:
    """Vue agrégée : combien chaque client doit, et depuis quand."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT COALESCE(c.id, 0)            AS client_id,
                  COALESCE(c.nom, vc.client_nom) AS client_nom,
                  COALESCE(c.telephone,'')     AS telephone,
                  COALESCE(c.plafond_credit,0) AS plafond_credit,
                  COUNT(*)                     AS nb_factures,
                  SUM(vc.reste_du)             AS total_du,
                  MAX(vc.anciennete_jours)     AS plus_ancienne_jours
           FROM v_creances vc
           LEFT JOIN clients c ON c.id = vc.client_id
           GROUP BY COALESCE(c.id, vc.client_nom)
           ORDER BY total_du DESC""").fetchall()
    
    return [dict(r) for r in rows]


def solde_client(client_id: int) -> float:
    conn = get_connection()
    row = conn.execute("SELECT COALESCE(SUM(reste_du),0) FROM v_creances WHERE client_id=?",
                       (client_id,)).fetchone()
    
    return round(parse_float(row[0]), 2)


def verifier_plafond_credit(client_id: int | None, montant: float) -> tuple[bool, str]:
    """
    Vérifie l'éligibilité d'une vente à crédit. Exige un client valide identifié.
    """
    params = get_parametres()
    if params.get("credit_autorise", "1") != "1":
        return False, "Les ventes à crédit sont désactivées dans les paramètres"
    if not client_id:
        return False, "Une vente à crédit exige un client identifié"

    conn = get_connection()
    row = conn.execute("SELECT nom, plafond_credit FROM clients WHERE id=?", (client_id,)).fetchone()
    if not row:
        return False, "Client introuvable"

    plafond = parse_float(row["plafond_credit"]) or parse_float(params.get("credit_plafond_defaut", 0))
    encours = solde_client(client_id)

    # Si aucun plafond n'est spécifié (<= 0), le crédit est autorisé sans limite arbitraire
    if plafond > 0 and (encours + parse_float(montant) > plafond):
        return False, (f"Plafond de crédit dépassé pour « {row['nom']} » : encours {encours:,.0f} "
                       f"+ vente {parse_float(montant):,.0f} > plafond autorisé {plafond:,.0f}")

    return True, f"Crédit autorisé (encours {encours:,.0f})"


def encaisser_creance(vente_id: int, montant: float, mode_paiement: str = "Espèces",
                      reference_doc: str = "", notes: str = "") -> tuple[bool, str]:
    """Encaisse un acompte ou le solde d'une vente à crédit."""
    montant = parse_float(montant)
    if montant <= 0:
        return False, "Le montant doit être supérieur à 0"

    conn = get_connection()
    try:
        with conn:
            row = conn.execute("SELECT reste_du, client_id, client_nom, numero "
                               "FROM v_creances WHERE vente_id=?", (vente_id,)).fetchone()
            if not row:
                return False, "Cette vente est déjà soldée ou introuvable"
            reste = parse_float(row["reste_du"])
            if montant > reste + 0.01:
                return False, f"Montant trop élevé : reste dû {reste:,.0f} seulement"
            conn.execute(
                """INSERT INTO reglements (sens, vente_id, client_id, montant,
                   mode_paiement, reference_doc, notes, utilisateur, date_reglement)
                   VALUES ('encaissement',?,?,?,?,?,?,?,?)""",
                (vente_id, row["client_id"], montant, mode_paiement, reference_doc,
                 notes, _user(), _maintenant()))
            nouveau_reste = reste - montant
        log_action("Encaissement créance",
                   f"{row['numero']} {montant:,.0f} — reste {nouveau_reste:,.0f}")
        if nouveau_reste < 0.01:
            return True, f"Facture {row['numero']} soldée. Merci !"
        return True, f"Acompte enregistré. Reste dû : {nouveau_reste:,.0f}"
    finally:
        pass


def get_reglements(vente_id: int | None = None, commande_id: int | None = None,
                   limit: int = 200) -> list[dict]:
    conn = get_connection()
    sql = "SELECT * FROM reglements WHERE 1=1"
    params: list = []
    if vente_id:
        sql += " AND vente_id=?"
        params.append(vente_id)
    if commande_id:
        sql += " AND commande_id=?"
        params.append(commande_id)
    sql += " ORDER BY date_reglement DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    
    return [dict(r) for r in rows]


def annuler_reglement(reglement_id: int) -> tuple[bool, str]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT montant, vente_id FROM reglements WHERE id=?",
                           (reglement_id,)).fetchone()
        if not row:
            return False, "Règlement introuvable"
        with conn:
            conn.execute("DELETE FROM reglements WHERE id=?", (reglement_id,))
        log_action("Annulation règlement", f"id={reglement_id} {row['montant']:,.0f}")
        return True, "Règlement annulé"
    finally:
        pass


# ═══════════════════════════════════════════════════════
#  DETTES FOURNISSEUR
# ═══════════════════════════════════════════════════════

def get_dettes_fournisseur(fournisseur_id: int | None = None) -> list[dict]:
    conn = get_connection()
    sql = "SELECT * FROM v_dettes_fournisseur WHERE 1=1"
    params: list = []
    if fournisseur_id:
        sql += " AND fournisseur_id=?"
        params.append(fournisseur_id)
    sql += " ORDER BY date_commande"
    rows = conn.execute(sql, params).fetchall()
    
    return [dict(r) for r in rows]


def payer_fournisseur(commande_id: int, montant: float, mode_paiement: str = "Espèces",
                      reference_doc: str = "", notes: str = "") -> tuple[bool, str]:
    montant = parse_float(montant)
    if montant <= 0:
        return False, "Le montant doit être supérieur à 0"
    conn = get_connection()
    try:
        with conn:
            row = conn.execute("SELECT reste_a_payer, fournisseur_id, numero "
                               "FROM v_dettes_fournisseur WHERE commande_id=?",
                               (commande_id,)).fetchone()
            if not row:
                return False, "Cette commande est déjà payée ou introuvable"
            reste = parse_float(row["reste_a_payer"])
            if montant > reste + 0.01:
                return False, f"Montant trop élevé : reste à payer {reste:,.0f}"
            conn.execute(
                """INSERT INTO reglements (sens, commande_id, fournisseur_id, montant,
                   mode_paiement, reference_doc, notes, utilisateur, date_reglement)
                   VALUES ('decaissement',?,?,?,?,?,?,?,?)""",
                (commande_id, row["fournisseur_id"], montant, mode_paiement,
                 reference_doc, notes, _user(), _maintenant()))
        log_action("Paiement fournisseur", f"{row['numero']} {montant:,.0f}")
        return True, f"Paiement enregistré. Reste : {reste - montant:,.0f}"
    finally:
        pass


# ═══════════════════════════════════════════════════════
#  ACHATS / COMMANDES FOURNISSEUR
# ═══════════════════════════════════════════════════════

def creer_commande(fournisseur_id: int, items: list, depot_id: int | None = None,
                   frais: float = 0, remise: float = 0, date_prevue: str = "",
                   notes: str = "") -> tuple[bool, str, int | None]:
    """
    items = [(produit_id|None, designation, quantite, prix_unitaire), ...]
    Crée une commande en statut 'brouillon'. Aucun impact stock.
    """
    if not items:
        return False, "Aucune ligne dans la commande", None
    lignes = []
    for pid, designation, qte, pu in items:
        try:
            qte = int(qte)
        except (TypeError, ValueError):
            return False, "Quantité invalide", None
        if qte <= 0:
            return False, "Les quantités doivent être supérieures à 0", None
        if not pid and not (designation or "").strip():
            return False, "Chaque ligne doit avoir un produit ou une désignation", None
        lignes.append((pid, (designation or "").strip(), qte, parse_float(pu)))

    if depot_id is None:
        d = get_depot_defaut()
        depot_id = d["id"] if d else None

    sous_total = sum(q * p for _, _, q, p in lignes)
    remise = max(0.0, parse_float(remise))
    if remise > sous_total:
        return False, "La remise dépasse le montant de la commande", None
    total = sous_total - remise + max(0.0, parse_float(frais))

    conn = get_connection()
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO commandes (fournisseur_id, depot_id, statut, sous_total,
                   remise, frais, total, date_commande, date_prevue, notes, utilisateur)
                   VALUES (?,?,'brouillon',?,?,?,?,?,?,?,?)""",
                (fournisseur_id, depot_id, sous_total, remise, parse_float(frais), total,
                 _maintenant(), date_prevue or None, notes, _user()))
            cid = cur.lastrowid
            numero = _numero("prefixe_commande", "CMD", "commandes", cid)
            conn.execute("UPDATE commandes SET numero=? WHERE id=?", (numero, cid))
            conn.executemany(
                """INSERT INTO commandes_details
                   (commande_id, produit_id, designation, quantite, prix_unitaire, total)
                   VALUES (?,?,?,?,?,?)""",
                [(cid, pid, des, q, p, q * p) for pid, des, q, p in lignes])
        log_action("Création commande", f"{numero} — {total:,.0f}")
        return True, f"Commande {numero} créée ({total:,.0f})", cid
    finally:
        pass


def envoyer_commande(commande_id: int) -> tuple[bool, str]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT statut, numero FROM commandes WHERE id=?",
                           (commande_id,)).fetchone()
        if not row:
            return False, "Commande introuvable"
        if row["statut"] != "brouillon":
            return False, f"Commande déjà « {row['statut']} »"
        with conn:
            conn.execute("UPDATE commandes SET statut='envoyee' WHERE id=?", (commande_id,))
        log_action("Envoi commande", row["numero"])
        return True, f"Commande {row['numero']} marquée envoyée"
    finally:
        pass


def receptionner_commande(commande_id: int, receptions: dict | None = None,
                          depot_id: int | None = None) -> tuple[bool, str]:
    """
    Réceptionne une commande : entrée en stock + mise à jour du CUMP.

    receptions = {ligne_id: quantite_recue_maintenant}
                 None = tout réceptionner (reliquat complet).
    Gère les réceptions partielles (statut 'partielle').
    """
    conn = get_connection()
    try:
        with conn:
            cmd = conn.execute("SELECT * FROM commandes WHERE id=?", (commande_id,)).fetchone()
            if not cmd:
                return False, "Commande introuvable"
            if cmd["statut"] in ("recue", "annulee"):
                return False, f"Commande déjà « {cmd['statut']} »"

            cible_depot = depot_id or cmd["depot_id"]
            if not cible_depot:
                d = get_depot_defaut()
                cible_depot = d["id"] if d else None
            if not cible_depot:
                return False, "Aucun dépôt de réception défini"

            lignes = conn.execute(
                "SELECT * FROM commandes_details WHERE commande_id=?",
                (commande_id,)).fetchall()
            fournisseur = conn.execute("SELECT nom FROM fournisseurs WHERE id=?",
                                       (cmd["fournisseur_id"],)).fetchone()
            nom_fourn = fournisseur["nom"] if fournisseur else ""

            nb_recu = 0
            for ligne in lignes:
                reliquat = ligne["quantite"] - ligne["quantite_recue"]
                if reliquat <= 0:
                    continue
                if receptions is None:
                    qte = reliquat
                else:
                    qte = int(receptions.get(ligne["id"], 0) or 0)
                    if qte <= 0:
                        continue
                    qte = min(qte, reliquat)

                if not ligne["produit_id"]:
                    return False, (f"La ligne « {ligne['designation']} » n'est pas liée "
                                   f"à un produit : créez-le d'abord")

                pid = ligne["produit_id"]
                avant = conn.execute("SELECT stock FROM produits WHERE id=?",
                                     (pid,)).fetchone()["stock"]
                cump = _maj_cump(conn, pid, qte, ligne["prix_unitaire"],
                                 "reception", nom_fourn, cmd["numero"])
                _appliquer_stock(conn, pid, cible_depot, qte)
                apres = conn.execute("SELECT stock FROM produits WHERE id=?",
                                     (pid,)).fetchone()["stock"]
                conn.execute(
                    """INSERT INTO mouvements_stock
                       (produit_id, type_mouvement, quantite, prix_unitaire, reference_doc,
                        notes, stock_avant, stock_apres, utilisateur, date_mouvement,
                        depot_id, cout_unitaire)
                       VALUES (?,'entree',?,?,?,?,?,?,?,?,?,?)""",
                    (pid, qte, ligne["prix_unitaire"], cmd["numero"],
                     f"Réception {nom_fourn}", avant, apres, _user(),
                     _maintenant(), cible_depot, cump))
                conn.execute("UPDATE commandes_details SET quantite_recue=quantite_recue+? "
                             "WHERE id=?", (qte, ligne["id"]))
                nb_recu += qte

            if nb_recu == 0:
                return False, "Aucune quantité à réceptionner"

            reste = conn.execute(
                "SELECT COALESCE(SUM(quantite - quantite_recue),0) FROM commandes_details "
                "WHERE commande_id=?", (commande_id,)).fetchone()[0]
            statut = "recue" if reste <= 0 else "partielle"
            conn.execute("UPDATE commandes SET statut=?, date_reception=? WHERE id=?",
                         (statut, _maintenant(), commande_id))

        log_action("Réception commande", f"{cmd['numero']} — {nb_recu}u ({statut})")
        msg = f"{nb_recu} article(s) réceptionné(s) — CUMP mis à jour"
        if statut == "partielle":
            msg += f" (reste {reste} en attente)"
        return True, msg
    finally:
        pass


def annuler_commande(commande_id: int) -> tuple[bool, str]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT statut, numero FROM commandes WHERE id=?",
                           (commande_id,)).fetchone()
        if not row:
            return False, "Commande introuvable"
        if row["statut"] in ("recue", "partielle"):
            return False, "Impossible : la commande a déjà été réceptionnée"
        with conn:
            conn.execute("UPDATE commandes SET statut='annulee' WHERE id=?", (commande_id,))
        log_action("Annulation commande", row["numero"])
        return True, f"Commande {row['numero']} annulée"
    finally:
        pass


def get_commandes(statut: str = "", fournisseur_id: int | None = None,
                  limit: int = 200) -> list[dict]:
    conn = get_connection()
    sql = """SELECT c.*, f.nom AS fournisseur_nom, d.nom AS depot_nom,
                    (SELECT COUNT(*) FROM commandes_details cd WHERE cd.commande_id=c.id)
                        AS nb_lignes,
                    (SELECT COALESCE(SUM(cd.quantite - cd.quantite_recue),0)
                       FROM commandes_details cd WHERE cd.commande_id=c.id) AS reste_a_recevoir
             FROM commandes c
             LEFT JOIN fournisseurs f ON f.id=c.fournisseur_id
             LEFT JOIN depots d ON d.id=c.depot_id
             WHERE 1=1"""
    params: list = []
    if statut:
        sql += " AND c.statut=?"
        params.append(statut)
    if fournisseur_id:
        sql += " AND c.fournisseur_id=?"
        params.append(fournisseur_id)
    sql += " ORDER BY c.date_commande DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    
    return [dict(r) for r in rows]


def get_commande_details(commande_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT cd.*, p.reference, p.nom AS produit_nom
           FROM commandes_details cd
           LEFT JOIN produits p ON p.id=cd.produit_id
           WHERE cd.commande_id=? ORDER BY cd.id""", (commande_id,)).fetchall()
    
    return [dict(r) for r in rows]


def articles_en_route() -> list[dict]:
    """Ce qui est commandé mais pas encore reçu — évite de recommander en double."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.id AS produit_id, p.reference, p.nom,
                  SUM(cd.quantite - cd.quantite_recue) AS qte_attendue,
                  MIN(c.date_prevue) AS date_prevue,
                  GROUP_CONCAT(DISTINCT c.numero) AS commandes
           FROM commandes_details cd
           JOIN commandes c ON c.id=cd.commande_id
           JOIN produits p  ON p.id=cd.produit_id
           WHERE c.statut IN ('envoyee','partielle')
             AND cd.quantite > cd.quantite_recue
           GROUP BY p.id ORDER BY p.nom""").fetchall()
    
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
#  INVENTAIRE PHYSIQUE
# ═══════════════════════════════════════════════════════

def ouvrir_inventaire(depot_id: int | None = None, categorie_id: int | None = None,
                      notes: str = "") -> tuple[bool, str, int | None]:
    """Ouvre un inventaire et fige le stock théorique de chaque produit du périmètre."""
    conn = get_connection()
    try:
        with conn:
            en_cours = conn.execute(
                "SELECT numero FROM inventaires WHERE statut='en_cours' "
                "AND COALESCE(depot_id,0)=COALESCE(?,0)", (depot_id,)).fetchone()
            if en_cours:
                return False, f"Un inventaire est déjà en cours ({en_cours['numero']})", None

            perimetre = "categorie" if categorie_id else "total"
            cur = conn.execute(
                """INSERT INTO inventaires (depot_id, perimetre, categorie_id, statut,
                   date_debut, notes, utilisateur)
                   VALUES (?,?,?,'en_cours',?,?,?)""",
                (depot_id, perimetre, categorie_id, _maintenant(), notes, _user()))
            inv_id = cur.lastrowid
            numero = _numero("prefixe_inventaire", "INV", "inventaires", inv_id)
            conn.execute("UPDATE inventaires SET numero=? WHERE id=?", (numero, inv_id))

            # Stock théorique : par dépôt si précisé, sinon total consolidé
            if depot_id:
                sql = """INSERT INTO inventaire_lignes
                         (inventaire_id, produit_id, stock_theorique, cump_unitaire)
                         SELECT ?, p.id, COALESCE(sd.quantite,0), COALESCE(p.cump,p.prix_achat)
                         FROM produits p
                         LEFT JOIN stock_depot sd ON sd.produit_id=p.id AND sd.depot_id=?
                         WHERE p.actif=1"""
                params: list = [inv_id, depot_id]
            else:
                sql = """INSERT INTO inventaire_lignes
                         (inventaire_id, produit_id, stock_theorique, cump_unitaire)
                         SELECT ?, p.id, COALESCE(p.stock,0), COALESCE(p.cump,p.prix_achat)
                         FROM produits p WHERE p.actif=1"""
                params = [inv_id]
            if categorie_id:
                sql += " AND p.categorie_id=?"
                params.append(categorie_id)
            conn.execute(sql, params)

            nb = conn.execute("SELECT COUNT(*) FROM inventaire_lignes WHERE inventaire_id=?",
                              (inv_id,)).fetchone()[0]
            conn.execute("UPDATE inventaires SET nb_lignes=? WHERE id=?", (nb, inv_id))
        log_action("Ouverture inventaire", f"{numero} — {nb} produits")
        return True, f"Inventaire {numero} ouvert ({nb} produits à compter)", inv_id
    finally:
        pass


def saisir_comptage(inventaire_id: int, produit_id: int, stock_compte: int,
                    motif: str = "", notes: str = "") -> tuple[bool, str]:
    try:
        stock_compte = int(stock_compte)
    except (TypeError, ValueError):
        return False, "Quantité comptée invalide"
    if stock_compte < 0:
        return False, "La quantité comptée ne peut pas être négative"

    conn = get_connection()
    try:
        with conn:
            inv = conn.execute("SELECT statut FROM inventaires WHERE id=?",
                               (inventaire_id,)).fetchone()
            if not inv:
                return False, "Inventaire introuvable"
            if inv["statut"] != "en_cours":
                return False, "Cet inventaire est clôturé"
            ligne = conn.execute(
                "SELECT stock_theorique, cump_unitaire FROM inventaire_lignes "
                "WHERE inventaire_id=? AND produit_id=?",
                (inventaire_id, produit_id)).fetchone()
            if not ligne:
                return False, "Ce produit n'est pas dans le périmètre de l'inventaire"
            ecart = stock_compte - ligne["stock_theorique"]
            conn.execute(
                """UPDATE inventaire_lignes
                   SET stock_compte=?, ecart=?, valeur_ecart=?, motif=?, notes=?,
                       date_comptage=?
                   WHERE inventaire_id=? AND produit_id=?""",
                (stock_compte, ecart, ecart * parse_float(ligne["cump_unitaire"]), motif, notes,
                 _maintenant(), inventaire_id, produit_id))
        if ecart == 0:
            return True, "Comptage conforme"
        signe = "+" if ecart > 0 else ""
        return True, f"Écart enregistré : {signe}{ecart}"
    finally:
        pass


def cloturer_inventaire(inventaire_id: int, appliquer: bool = True) -> tuple[bool, str]:
    """
    Clôture l'inventaire. Si appliquer=True, ajuste le stock réel sur le comptage
    et journalise un mouvement 'correction' par écart.
    Les produits non comptés sont ignorés (stock inchangé).
    """
    conn = get_connection()
    try:
        with conn:
            inv = conn.execute("SELECT * FROM inventaires WHERE id=?",
                               (inventaire_id,)).fetchone()
            if not inv:
                return False, "Inventaire introuvable"
            if inv["statut"] != "en_cours":
                return False, "Cet inventaire est déjà clôturé"

            depot_id = inv["depot_id"]
            if not depot_id:
                d = get_depot_defaut()
                depot_id = d["id"] if d else None

            lignes = conn.execute(
                "SELECT * FROM inventaire_lignes WHERE inventaire_id=? "
                "AND stock_compte IS NOT NULL AND ecart != 0",
                (inventaire_id,)).fetchall()

            nb_ecarts, valeur_ecart = 0, 0.0
            for ligne in lignes:
                nb_ecarts += 1
                valeur_ecart += parse_float(ligne["valeur_ecart"])
                if not appliquer:
                    continue
                pid, ecart = ligne["produit_id"], ligne["ecart"]
                avant = conn.execute("SELECT stock FROM produits WHERE id=?",
                                     (pid,)).fetchone()["stock"]
                _appliquer_stock(conn, pid, depot_id, ecart)
                apres = conn.execute("SELECT stock FROM produits WHERE id=?",
                                     (pid,)).fetchone()["stock"]
                conn.execute(
                    """INSERT INTO mouvements_stock
                       (produit_id, type_mouvement, quantite, prix_unitaire, reference_doc,
                        notes, stock_avant, stock_apres, utilisateur, date_mouvement,
                        depot_id, cout_unitaire)
                       VALUES (?,'correction',?,?,?,?,?,?,?,?,?,?)""",
                    (pid, apres, parse_float(ligne["cump_unitaire"]), inv["numero"],
                     f"Inventaire — écart {ecart:+d} ({ligne['motif'] or 'non précisé'})",
                     avant, apres, _user(), _maintenant(), depot_id,
                     parse_float(ligne["cump_unitaire"])))

            conn.execute(
                """UPDATE inventaires SET statut='cloture', date_cloture=?,
                   nb_ecarts=?, valeur_ecart=? WHERE id=?""",
                (_maintenant(), nb_ecarts, round(valeur_ecart, 2), inventaire_id))

        log_action("Clôture inventaire",
                   f"{inv['numero']} — {nb_ecarts} écarts, {valeur_ecart:,.0f}")
        action = "appliqués au stock" if appliquer else "constatés sans ajustement"
        return True, (f"Inventaire {inv['numero']} clôturé : {nb_ecarts} écart(s) {action}, "
                      f"impact {valeur_ecart:,.0f}")
    finally:
        pass


def get_inventaires(limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT i.*, d.nom AS depot_nom, c.nom AS categorie_nom,
                  (SELECT COUNT(*) FROM inventaire_lignes il
                    WHERE il.inventaire_id=i.id AND il.stock_compte IS NOT NULL)
                      AS nb_comptes
           FROM inventaires i
           LEFT JOIN depots d ON d.id=i.depot_id
           LEFT JOIN categories c ON c.id=i.categorie_id
           ORDER BY i.date_debut DESC LIMIT ?""", (limit,)).fetchall()
    
    return [dict(r) for r in rows]


def get_inventaire_lignes(inventaire_id: int, ecarts_seulement: bool = False) -> list[dict]:
    conn = get_connection()
    sql = """SELECT il.*, p.reference, p.nom AS produit_nom, p.emplacement
             FROM inventaire_lignes il JOIN produits p ON p.id=il.produit_id
             WHERE il.inventaire_id=?"""
    if ecarts_seulement:
        sql += " AND il.stock_compte IS NOT NULL AND il.ecart != 0"
    sql += " ORDER BY p.nom"
    rows = conn.execute(sql, (inventaire_id,)).fetchall()
    
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
#  RETOURS / AVOIRS
# ═══════════════════════════════════════════════════════

def creer_retour(vente_id: int | None, items: list, motif: str = "",
                 mode_remboursement: str = "Espèces", depot_id: int | None = None,
                 client_id: int | None = None, client_nom: str = "",
                 notes: str = "") -> tuple[bool, str, int | None]:
    """
    Retour partiel ou total.
    items = [(produit_id, quantite, prix_unitaire, remis_en_stock, etat), ...]

    Contrôle : on ne peut pas reprendre plus que ce qui a été vendu
    (net des retours déjà effectués).
    """
    if not items:
        return False, "Aucun article dans le retour", None

    if depot_id is None:
        d = get_depot_defaut()
        depot_id = d["id"] if d else None

    conn = get_connection()
    try:
        with conn:
            if vente_id:
                vente = conn.execute("SELECT * FROM ventes WHERE id=?", (vente_id,)).fetchone()
                if not vente:
                    return False, "Vente introuvable", None
                if vente["statut"] == "annulee":
                    return False, "Cette vente est déjà annulée", None
                client_id = client_id or vente["client_id"]
                client_nom = client_nom or vente["client_nom"]

            lignes = []
            for item in items:
                pid, qte, pu, *reste = item
                remis = reste[0] if reste else 1
                etat = reste[1] if len(reste) > 1 else "neuf"
                try:
                    qte = int(qte)
                except (TypeError, ValueError):
                    return False, "Quantité invalide", None
                if qte <= 0:
                    return False, "Les quantités doivent être supérieures à 0", None

                if vente_id:
                    vendu = conn.execute(
                        "SELECT COALESCE(SUM(quantite),0) FROM ventes_details "
                        "WHERE vente_id=? AND produit_id=?", (vente_id, pid)).fetchone()[0]
                    deja = conn.execute(
                        """SELECT COALESCE(SUM(rd.quantite),0)
                           FROM retours_details rd JOIN retours r ON r.id=rd.retour_id
                           WHERE r.vente_id=? AND rd.produit_id=? AND r.statut='valide'""",
                        (vente_id, pid)).fetchone()[0]
                    if qte > vendu - deja:
                        nom = conn.execute("SELECT nom FROM produits WHERE id=?",
                                           (pid,)).fetchone()
                        return False, (f"Retour impossible pour « {nom['nom'] if nom else pid} » : "
                                       f"{vendu} vendu(s), {deja} déjà retourné(s)"), None
                lignes.append((pid, qte, parse_float(pu), 1 if remis else 0, etat))

            total = sum(q * p for _, q, p, _, _ in lignes)
            cur = conn.execute(
                """INSERT INTO retours (vente_id, client_id, client_nom, depot_id, motif,
                   total, mode_remboursement, statut, notes, utilisateur, date_retour)
                   VALUES (?,?,?,?,?,?,?,'valide',?,?,?)""",
                (vente_id, client_id, client_nom or "Client", depot_id, motif, total,
                 mode_remboursement, notes, _user(), _maintenant()))
            rid = cur.lastrowid
            numero = _numero("prefixe_retour", "RET", "retours", rid)
            conn.execute("UPDATE retours SET numero=? WHERE id=?", (numero, rid))

            for pid, qte, pu, remis, etat in lignes:
                conn.execute(
                    """INSERT INTO retours_details (retour_id, produit_id, quantite,
                       prix_unitaire, total, remis_en_stock, etat)
                       VALUES (?,?,?,?,?,?,?)""",
                    (rid, pid, qte, pu, qte * pu, remis, etat))
                if remis:
                    avant = conn.execute("SELECT stock FROM produits WHERE id=?",
                                         (pid,)).fetchone()["stock"]
                    _appliquer_stock(conn, pid, depot_id, qte)
                    apres = conn.execute("SELECT stock FROM produits WHERE id=?",
                                         (pid,)).fetchone()["stock"]
                    cump = conn.execute("SELECT cump FROM produits WHERE id=?",
                                        (pid,)).fetchone()["cump"]
                    conn.execute(
                        """INSERT INTO mouvements_stock
                           (produit_id, type_mouvement, quantite, prix_unitaire,
                            reference_doc, notes, stock_avant, stock_apres, utilisateur,
                            date_mouvement, depot_id, cout_unitaire)
                           VALUES (?,'entree',?,?,?,?,?,?,?,?,?,?)""",
                        (pid, qte, pu, numero, f"Retour client ({etat})", avant, apres,
                         _user(), _maintenant(), depot_id, cump))

            # Remboursement par avoir → crée une créance négative encaissable
            if mode_remboursement == "Avoir" and vente_id:
                conn.execute(
                    """INSERT INTO reglements (sens, vente_id, client_id, montant,
                       mode_paiement, reference_doc, notes, utilisateur, date_reglement)
                       VALUES ('encaissement',?,?,?,'Avoir',?,?,?,?)""",
                    (vente_id, client_id, total, numero,
                     "Avoir sur retour", _user(), _maintenant()))

        log_action("Retour client", f"{numero} — {total:,.0f}")
        return True, f"Retour {numero} enregistré ({total:,.0f})", rid
    finally:
        pass


def get_retours(limit: int = 200) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT r.*, v.numero AS vente_numero,
                  (SELECT COUNT(*) FROM retours_details rd WHERE rd.retour_id=r.id)
                      AS nb_lignes
           FROM retours r LEFT JOIN ventes v ON v.id=r.vente_id
           ORDER BY r.date_retour DESC LIMIT ?""", (limit,)).fetchall()
    
    return [dict(r) for r in rows]


def get_retour_details(retour_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT rd.*, p.reference, p.nom AS produit_nom
           FROM retours_details rd LEFT JOIN produits p ON p.id=rd.produit_id
           WHERE rd.retour_id=? ORDER BY rd.id""", (retour_id,)).fetchall()
    
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
#  COMPATIBILITÉ VÉHICULE
# ═══════════════════════════════════════════════════════

def get_marques() -> list[str]:
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT marque FROM vehicules_modeles ORDER BY marque").fetchall()
    
    return [r[0] for r in rows]


def get_modeles(marque: str = "", recherche: str = "") -> list[dict]:
    conn = get_connection()
    sql = "SELECT * FROM vehicules_modeles WHERE 1=1"
    params: list = []
    if marque:
        sql += " AND marque=?"
        params.append(marque)
    if recherche:
        s = f"%{recherche}%"
        sql += " AND (marque LIKE ? OR modele LIKE ? OR motorisation LIKE ?)"
        params += [s, s, s]
    sql += " ORDER BY marque, modele, annee_debut"
    rows = conn.execute(sql, params).fetchall()
    
    return [dict(r) for r in rows]


def add_modele(marque: str, modele: str, motorisation: str = "", carburant: str = "",
               annee_debut: int = 0, annee_fin: int = 0,
               notes: str = "") -> tuple[bool, str, int | None]:
    marque, modele = (marque or "").strip(), (modele or "").strip()
    if not marque or not modele:
        return False, "Marque et modèle sont requis", None
    conn = get_connection()
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO vehicules_modeles (marque, modele, motorisation, carburant,
                   annee_debut, annee_fin, notes) VALUES (?,?,?,?,?,?,?)""",
                (marque, modele, (motorisation or "").strip(), carburant,
                 int(annee_debut or 0), int(annee_fin or 0), notes))
        log_action("Ajout modèle véhicule", f"{marque} {modele} {motorisation}")
        return True, "Modèle ajouté", cur.lastrowid
    except sqlite3.IntegrityError:
        row = conn.execute(
            """SELECT id FROM vehicules_modeles WHERE marque=? AND modele=?
               AND motorisation=? AND annee_debut=?""",
            (marque, modele, (motorisation or "").strip(), int(annee_debut or 0))).fetchone()
        return False, "Ce modèle existe déjà", row["id"] if row else None
    finally:
        pass


def lier_compatibilite(produit_id: int, modele_id: int, position: str = "",
                       certitude: str = "confirme", notes: str = "") -> tuple[bool, str]:
    if certitude not in ("confirme", "probable", "a_verifier"):
        return False, "Niveau de certitude invalide"
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """INSERT INTO produit_compatibilite
                   (produit_id, modele_id, position, certitude, notes)
                   VALUES (?,?,?,?,?)""",
                (produit_id, modele_id, position, certitude, notes))
        return True, "Compatibilité enregistrée"
    except sqlite3.IntegrityError:
        return False, "Cette compatibilité existe déjà"
    finally:
        pass


def delier_compatibilite(compatibilite_id: int) -> tuple[bool, str]:
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM produit_compatibilite WHERE id=?", (compatibilite_id,))
    
    return True, "Compatibilité supprimée"


def get_compatibilites_produit(produit_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT pc.id, pc.position, pc.certitude, pc.notes, vm.*
           FROM produit_compatibilite pc
           JOIN vehicules_modeles vm ON vm.id=pc.modele_id
           WHERE pc.produit_id=? ORDER BY vm.marque, vm.modele""", (produit_id,)).fetchall()
    
    return [dict(r) for r in rows]


def chercher_pieces_pour_vehicule(marque: str = "", modele: str = "", annee: int = 0,
                                  categorie_id: int | None = None,
                                  recherche: str = "") -> list[dict]:
    """
    LA fonction qui fait vendre : « une plaquette pour Yaris 2008 ».
    Retourne les produits compatibles avec stock et prix.
    """
    conn = get_connection()
    sql = """SELECT DISTINCT p.id, p.reference, p.nom, p.marque, p.prix_vente, p.cump,
                    p.stock, p.stock_vente, p.emplacement,
                    c.nom AS categorie_nom,
                    pc.position, pc.certitude,
                    vm.marque || ' ' || vm.modele ||
                      CASE WHEN vm.motorisation != '' THEN ' ' || vm.motorisation ELSE '' END
                      AS vehicule
             FROM produits p
             JOIN produit_compatibilite pc ON pc.produit_id=p.id
             JOIN vehicules_modeles vm ON vm.id=pc.modele_id
             LEFT JOIN categories c ON c.id=p.categorie_id
             WHERE p.actif=1"""
    params: list = []
    if marque:
        sql += " AND vm.marque=?"
        params.append(marque)
    if modele:
        sql += " AND vm.modele LIKE ?"
        params.append(f"%{modele}%")
    if annee:
        sql += " AND vm.annee_debut <= ? AND (vm.annee_fin=0 OR vm.annee_fin >= ?)"
        params += [int(annee), int(annee)]
    if categorie_id:
        sql += " AND p.categorie_id=?"
        params.append(categorie_id)
    if recherche:
        s = f"%{recherche}%"
        sql += " AND (p.nom LIKE ? OR p.reference LIKE ?)"
        params += [s, s]
    sql += """ ORDER BY CASE pc.certitude WHEN 'confirme' THEN 0
                        WHEN 'probable' THEN 1 ELSE 2 END,
                        p.stock_vente DESC, p.nom"""
    rows = conn.execute(sql, params).fetchall()
    
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
#  RÉFÉRENCES CROISÉES
# ═══════════════════════════════════════════════════════

def add_reference(produit_id: int, reference: str, type_ref: str = "equivalent",
                  marque: str = "", notes: str = "") -> tuple[bool, str]:
    reference = (reference or "").strip()
    if not reference:
        return False, "La référence est requise"
    if type_ref not in ("oem", "equivalent", "fournisseur", "ancienne", "code_barres"):
        return False, "Type de référence invalide"
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """INSERT INTO produit_references (produit_id, reference, type, marque, notes)
                   VALUES (?,?,?,?,?)""", (produit_id, reference, type_ref, marque, notes))
        return True, "Référence ajoutée"
    except sqlite3.IntegrityError:
        return False, "Cette référence existe déjà pour ce produit"
    finally:
        pass


def delete_reference(reference_id: int) -> tuple[bool, str]:
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM produit_references WHERE id=?", (reference_id,))
    
    return True, "Référence supprimée"


def get_references_produit(produit_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM produit_references WHERE produit_id=? ORDER BY type, reference",
        (produit_id,)).fetchall()
    
    return [dict(r) for r in rows]


def chercher_par_reference(reference: str) -> list[dict]:
    """
    Recherche universelle : référence interne, code-barres, OEM, équivalent…
    C'est ce qu'il faut brancher sur la douchette et la barre de recherche caisse.
    """
    reference = (reference or "").strip()
    if not reference:
        return []
    s = f"%{reference}%"
    conn = get_connection()
    rows = conn.execute(
        """SELECT DISTINCT p.*, 'interne' AS origine_match
           FROM produits p
           WHERE p.actif=1 AND (p.reference LIKE ? OR p.code_barres LIKE ?)
           UNION
           SELECT DISTINCT p.*, pr.type AS origine_match
           FROM produits p JOIN produit_references pr ON pr.produit_id=p.id
           WHERE p.actif=1 AND pr.reference LIKE ?
           LIMIT 50""", (s, s, s)).fetchall()
    
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
#  PRÉVISION DE RUPTURE & CLASSEMENT ABC
# ═══════════════════════════════════════════════════════

def prevision_rupture(horizon_jours: int = 30, fenetre_analyse: int = 90) -> list[dict]:
    """
    Estime la date de rupture de chaque produit à partir de la vitesse de vente
    observée sur `fenetre_analyse` jours.

    couverture_jours = stock_vendable / vitesse_journaliere
    Ne remonte que les produits qui casseront dans l'horizon donné.
    """
    depuis = (datetime.now() - timedelta(days=fenetre_analyse)).strftime("%Y-%m-%d")
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.id, p.reference, p.nom, p.stock, p.stock_vente, p.stock_mini,
                  p.cump, p.prix_vente, p.delai_reappro_jours,
                  f.nom AS fournisseur_nom,
                  COALESCE(SUM(vd.quantite), 0) AS vendu_periode
           FROM produits p
           LEFT JOIN fournisseurs f ON f.id=p.fournisseur_id
           LEFT JOIN ventes_details vd ON vd.produit_id=p.id
           LEFT JOIN ventes v ON v.id=vd.vente_id
                AND v.statut='validee' AND date(v.date_vente) >= date(?)
           WHERE p.actif=1
           GROUP BY p.id""", (depuis,)).fetchall()

    # Quantités déjà commandées : on ne réalerte pas sur ce qui arrive
    en_route = {r["produit_id"]: r["qte_attendue"] for r in articles_en_route()}
    

    resultat = []
    for r in rows:
        vendu = parse_float(r["vendu_periode"])
        vitesse = vendu / fenetre_analyse if vendu else 0.0
        stock = r["stock_vente"] or 0
        attendu = en_route.get(r["id"], 0)

        if vitesse <= 0:
            couverture = 9999 if stock > 0 else 0
            date_rupture = None
        else:
            couverture = stock / vitesse
            date_rupture = (datetime.now() + timedelta(days=couverture)).strftime("%Y-%m-%d")

        delai = r["delai_reappro_jours"] or 7
        # Quantité à commander : couvrir l'horizon + le délai de réappro
        besoin = max(0, round(vitesse * (horizon_jours + delai)) - stock - attendu)

        if couverture <= horizon_jours or (stock <= (r["stock_mini"] or 0) and vitesse > 0):
            resultat.append({
                "produit_id": r["id"],
                "reference": r["reference"],
                "nom": r["nom"],
                "fournisseur_nom": r["fournisseur_nom"] or "",
                "stock": stock,
                "stock_mini": r["stock_mini"] or 0,
                "vendu_periode": int(vendu),
                "vitesse_jour": round(vitesse, 3),
                "couverture_jours": round(couverture, 1) if couverture < 9999 else None,
                "date_rupture": date_rupture,
                "delai_reappro_jours": delai,
                "qte_en_route": attendu,
                "qte_a_commander": besoin,
                "valeur_commande": round(besoin * parse_float(r["cump"]), 2),
                "urgence": ("critique" if couverture <= delai
                            else "haute" if couverture <= delai * 2
                            else "moyenne"),
            })

    ordre = {"critique": 0, "haute": 1, "moyenne": 2}
    resultat.sort(key=lambda x: (ordre[x["urgence"]], x["couverture_jours"] or 9999))
    return resultat


def calculer_classes_abc(fenetre_jours: int = 180) -> tuple[bool, str]:
    """
    Classement ABC par chiffre d'affaires cumulé :
      A = 80 % du CA, B = 80→95 %, C = le reste.
    Écrit produits.classe_abc.
    """
    depuis = (datetime.now() - timedelta(days=fenetre_jours)).strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT p.id, COALESCE(SUM(vd.total), 0) AS ca
               FROM produits p
               LEFT JOIN ventes_details vd ON vd.produit_id=p.id
               LEFT JOIN ventes v ON v.id=vd.vente_id
                    AND v.statut='validee' AND date(v.date_vente) >= date(?)
               WHERE p.actif=1
               GROUP BY p.id ORDER BY ca DESC""", (depuis,)).fetchall()
        total = sum(parse_float(r["ca"]) for r in rows)
        if total <= 0:
            return False, "Pas assez de ventes pour calculer le classement ABC"
        cumul, maj = 0.0, []
        for r in rows:
            ca = parse_float(r["ca"])
            if ca <= 0:
                maj.append(("C", r["id"]))
                continue
            cumul += ca
            part = cumul / total
            maj.append(("A" if part <= 0.80 else "B" if part <= 0.95 else "C", r["id"]))
        with conn:
            conn.executemany("UPDATE produits SET classe_abc=? WHERE id=?", maj)
        nb_a = sum(1 for c, _ in maj if c == "A")
        log_action("Classement ABC", f"{len(maj)} produits, {nb_a} en classe A")
        return True, f"Classement ABC calculé : {nb_a} produits font 80 % du CA"
    finally:
        pass


def produits_dormants(jours: int = 90) -> list[dict]:
    """Argent immobilisé : en stock mais rien vendu depuis `jours`."""
    depuis = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.id, p.reference, p.nom, p.stock, p.cump, p.prix_vente,
                  p.stock * COALESCE(p.cump, p.prix_achat) AS capital_immobilise,
                  (SELECT MAX(v.date_vente) FROM ventes_details vd
                     JOIN ventes v ON v.id=vd.vente_id
                    WHERE vd.produit_id=p.id AND v.statut='validee') AS derniere_vente
           FROM produits p
           WHERE p.actif=1 AND p.stock > 0
             AND (SELECT MAX(v.date_vente) FROM ventes_details vd
                    JOIN ventes v ON v.id=vd.vente_id
                   WHERE vd.produit_id=p.id AND v.statut='validee') IS NULL
              OR (SELECT MAX(v.date_vente) FROM ventes_details vd
                    JOIN ventes v ON v.id=vd.vente_id
                   WHERE vd.produit_id=p.id AND v.statut='validee') < date(?)
           ORDER BY capital_immobilise DESC""", (depuis,)).fetchall()
    
    return [dict(r) for r in rows if r["stock"] and r["stock"] > 0]


# ═══════════════════════════════════════════════════════
#  TABLEAU DE BORD v3
# ═══════════════════════════════════════════════════════

def kpi_v3() -> dict:
    """Indicateurs des nouveautés v3, pour le dashboard."""
    conn = get_connection()

    def q(sql, params=()):
        row = conn.execute(sql, params).fetchone()
        return parse_float(row[0]) if row and row[0] is not None else 0.0

    params_app = get_parametres()
    seuil = int(parse_float(params_app.get("alerte_creance_jours", 15)) or 15)

    kpi = {
        "creances_total":      q("SELECT COALESCE(SUM(reste_du),0) FROM v_creances"),
        "creances_nb":         q("SELECT COUNT(*) FROM v_creances"),
        "creances_retard":     q("SELECT COALESCE(SUM(reste_du),0) FROM v_creances "
                                 "WHERE anciennete_jours >= ?", (seuil,)),
        "creances_nb_retard":  q("SELECT COUNT(*) FROM v_creances WHERE anciennete_jours >= ?",
                                 (seuil,)),
        "dettes_total":        q("SELECT COALESCE(SUM(reste_a_payer),0) "
                                 "FROM v_dettes_fournisseur"),
        "commandes_en_cours":  q("SELECT COUNT(*) FROM commandes "
                                 "WHERE statut IN ('envoyee','partielle')"),
        "valeur_stock_cump":   q("SELECT COALESCE(SUM(stock * COALESCE(cump, prix_achat)),0) "
                                 "FROM produits WHERE actif=1"),
        "nb_depots":           q("SELECT COUNT(*) FROM depots WHERE actif=1"),
        "inventaire_en_cours": q("SELECT COUNT(*) FROM inventaires WHERE statut='en_cours'"),
        "retours_mois":        q("SELECT COALESCE(SUM(total),0) FROM retours "
                                 "WHERE statut='valide' "
                                 "AND strftime('%Y-%m', date_retour)=strftime('%Y-%m','now','localtime')"),
        "nb_compatibilites":   q("SELECT COUNT(*) FROM produit_compatibilite"),
    }
    
    kpi["ruptures_prevues"] = len(prevision_rupture(horizon_jours=14))
    return kpi
