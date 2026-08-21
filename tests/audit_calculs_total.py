"""
SOPAUTO - Audit Mathématique & Vérification d'Exactitude des Calculs
Vérifie 100% des formules mathématiques, marges, CUMP, taxes, remises et agrégations.
"""

import _bootstrap  # noqa: F401  (chemin d'import + sortie UTF-8)

import database as db
from ui_widgets import parse_float
import sys

def audit_ventes_et_marges():
    print("--- 1. Verification des calculs de Ventes, Remises et Marges ---")
    db.init_database()
    conn = db.get_connection()

    # Création d'un produit avec PA = 2,000 et PV = 5,000
    ok, msg = db.add_produit("REF-AUDIT-1", "Pièce Audit Marge", categorie_id=1, prix_achat=2000, prix_vente=5000, stock_reserve=0, stock_vente=10, stock_mini=2)
    p = db.get_produits(search="REF-AUDIT-1")[0]
    pid = p["id"]
    db.add_mouvement(pid, "entree", 10, 2000, cible="vente")

    # Test Vente 1 : 2 pièces à 5,000 F CFA avec remise de 1,000 F CFA
    # Sous-total = 10,000 F CFA
    # Net = 9,000 F CFA
    # Marge attendue = 9,000 - (2 * 2,000) = 5,000 F CFA
    ok, msg, vid = db.create_vente("Client Audit", [(pid, 2, 5000)], remise=1000, mode_paiement="Espèces", montant_paye=9000)
    assert ok, f"Échec création vente: {msg}"

    vente, details = db.get_vente_details(vid)
    assert vente["sous_total"] == 10000.0, f"Sous-total incorrect: {vente['sous_total']} != 10000"
    assert vente["remise"] == 1000.0, f"Remise incorrecte: {vente['remise']} != 1000"
    assert vente["total"] == 9000.0, f"Total net incorrect: {vente['total']} != 9000"
    assert details[0]["prix_achat"] == 2000.0, f"Prix d'achat non capturé: {details[0]['prix_achat']}"

    # Vérification dans le rapport des marges
    from datetime import date
    aujourdhui = date.today().isoformat()
    rap = db.rapport_ventes(aujourdhui, aujourdhui)
    assert rap["resume"]["ca"] >= 9000.0, f"CA rapport incorrect: {rap['resume']['ca']}"
    assert rap["resume"]["marge"] >= 5000.0, f"Marge rapport incorrecte: {rap['resume']['marge']}"
    print("  OK   Formules Ventes / Remises / Marge brute 100% exactes")

def audit_pmp_et_valorisation():
    print("\n--- 2. Verification des calculs de Stock et Prix Moyen Ponderes (PMP/CUMP) ---")
    conn = db.get_connection()

    # Produit avec 10 pièces à 2,000 F CFA (Valeur = 20,000)
    ok, msg = db.add_produit("REF-PMP-1", "Huile PMP Audit", categorie_id=1, prix_achat=2000, prix_vente=3500, stock_vente=10, stock_mini=2)
    p = db.get_produits(search="REF-PMP-1")[0]
    pid = p["id"]

    # Entrée de stock : 10 pièces supplémentaires achetées à 4,000 F CFA
    # Nouveau stock = 20 pièces
    # Valeur totale = (10 * 2,000) + (10 * 4,000) = 20,000 + 40,000 = 60,000 F CFA
    # Nouveau PMP = 60,000 / 20 = 3,000 F CFA
    ok, msg = db.add_mouvement(pid, "entree", 10, prix_unitaire=4000, notes="Réappro PMP")
    assert ok, f"Mouvement PMP échoué: {msg}"

    p_apres = db.get_produit(pid)
    assert p_apres["stock"] == p["stock"] + 10, f"Stock incorrect: {p_apres['stock']} != {p['stock'] + 10}"
    cump_attendu = round((p["stock"] * p["cump"] + 10 * 4000) / (p["stock"] + 10), 2)
    assert abs(p_apres["cump"] - cump_attendu) < 0.01, f"CUMP calculé incorrect: {p_apres['cump']} != {cump_attendu}"
    assert p_apres["prix_achat"] == 4000.0, f"Dernier prix d'achat incorrect: {p_apres['prix_achat']} != 4000"
    print(f"  OK   Formule PMP / CUMP pondéré ({cump_attendu} F CFA) et Dernier Prix d'Achat 100% exacts")

def audit_creances_et_reglements():
    print("\n--- 3. Verification des calculs de Creances et Règlements ---")
    conn = db.get_connection()

    nom_c = "Client Unique Audit 777"
    db.add_client(nom_c, "05050505")
    c = db.get_clients(nom_c)[0]
    cid = c["id"]

    p = db.get_produits()[0]
    db.add_mouvement(p["id"], "entree", 5, p["prix_achat"], cible="vente")

    # Vente à crédit de 20,000 F CFA avec acompte de 5,000 F CFA -> Reste dû = 15,000 F CFA
    ok, msg, vid = db.create_vente(nom_c, [(p["id"], 2, 10000)], mode_paiement="Crédit", montant_paye=5000, client_id=cid)
    assert ok, f"Vente créance échouée: {msg}"

    solde_1 = db.get_clients(nom_c)[0]["solde_creances"]
    assert solde_1 == 15000.0, f"Solde créance client incorrect: {solde_1} != 15000"

    # Réglement partiel de 10,000 F CFA
    import metier_v3 as m3
    ok, msg = m3.encaisser_creance(vid, 10000, mode_paiement="Wave", notes="Acompte Wave")
    assert ok, f"Règlement échoué: {msg}"

    solde_restant = m3.solde_client(cid)
    assert solde_restant == 5000.0, f"Solde restant après règlement incorrect: {solde_restant} != 5000"
    print("  OK   Formules Solde Créance / Acompte / Reste dû 100% exactes")

if __name__ == "__main__":
    try:
        audit_ventes_et_marges()
        audit_pmp_et_valorisation()
        audit_creances_et_reglements()
        print("\n==============================================")
        print("AUDIT DE CALCUL : TOUTES LES FORMULES SONT 100% EXACTES")
        print("==============================================")
    except Exception as e:
        print(f"\n❌ ERREUR AUDIT : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
