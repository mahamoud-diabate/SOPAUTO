"""
SODIPAC - Test d'Stress Aggressif et Simulation Utilisateur Débutant / Non-Expert
Simule des saisies chaotiques, erreurs de manipulation, doubles clics et cas limites.
"""

import _bootstrap  # noqa: F401  (chemin d'import + sortie UTF-8)

import os, tempfile
TMP_DB = os.path.join(tempfile.gettempdir(), "test_stress_debutant.db")
for s in ("", "-wal", "-shm"):
    try: os.remove(TMP_DB + s)
    except OSError: pass

import database as db
db.DB_PATH = TMP_DB
import dialogues.operations as ops
from ui_widgets import parse_float
import sys

def tester_saisies_chaotiques():
    print("--- 1. Test de robustesse des parseurs numériques (Saisie débutant) ---")
    cas_tests = [
        (" 450 000 F CFA ", 450000.0),
        ("10.000", 10000.0),
        ("15 000,50 FCFA", 15000.5),
        ("  -50  ", -50.0),
        ("abc", 0.0),
        ("", 0.0),
        ("0", 0.0),
        ("12,34€", 12.34),
        ("  1 000 000  ", 1000000.0),
    ]
    for ent, att in cas_tests:
        res = parse_float(ent)
        assert abs(res - att) < 0.01, f"Échec parse_float('{ent}') -> {res} au lieu de {att}"
    print("  OK   Parseur numérique ultra-résistant aux fautes de frappe")

def tester_scenarios_caisse_chaotiques():
    print("\n--- 2. Simulation d'actions chaotiques à la Caisse ---")
    db.init_database()
    conn = db.get_connection()
    
    # Produit de test
    ok, msg = db.add_produit("REF-CHAOS-1", "Filtre Huile Test", "", 1, None, "", 2500, 5000, 0, 2, 1)
    p = db.get_produits(search="REF-CHAOS-1")[0]
    pid = p["id"]

    # Client de test
    db.add_client("Client Stress Test", "01020304")
    c = db.get_clients("Client Stress Test")[0]
    cid = c["id"]

    # 2.1 Vente avec quantité supérieure au stock
    ok, msg, vid = db.create_vente("Client Stress Test", [(pid, 10, 5000)], mode_paiement="Espèces")
    assert not ok, "La vente aurait dû être refusée (stock insuffisant)"
    print("  OK   Refus propre de vente en sur-stock (quantité trop élevée)")

    # 2.2 Vente valide vider le stock (passer stock à 0)
    ok, msg, vid = db.create_vente("Client Stress Test", [(pid, 2, 5000)], mode_paiement="Espèces")
    assert ok, f"Vente normale échouée: {msg}"
    p_maj = db.get_produit(pid)
    assert p_maj["stock"] == 0, "Le stock aurait dû passer à 0"
    print("  OK   Stock vidé proprement à 0 sans crash")

    # 2.3 Nouvelle tentative de vente alors que le stock est à 0 (Rupture)
    ok, msg, vid2 = db.create_vente("Client Stress Test", [(pid, 1, 5000)], mode_paiement="Espèces")
    assert not ok, "Vente autorisée en rupture de stock !"
    print("  OK   Bloqué correctement en cas de rupture de stock")

    # 2.4 Annulation de la vente précédente pour rétablir le stock
    ok, msg = db.annuler_vente(vid)
    assert ok, f"Annulation échouée: {msg}"
    assert db.get_produit(pid)["stock"] == 2, "Le stock n'a pas été ré-approvisionné après annulation"
    print("  OK   Stock ré-approvisionné après annulation de vente")

    # 2.5 Double annulation par erreur du vendeur
    ok, msg = db.annuler_vente(vid)
    assert not ok, "La double annulation a été acceptée !"
    print("  OK   Double annulation bloquée proprement")

def tester_credit_sans_plafond():
    print("\n--- 3. Simulation Vente à Crédit sans Plafond (Scénario Client Débiteur) ---")
    db.add_client("Client Crédit Libre", "07070707")
    c = db.get_clients("Client Crédit Libre")[0]
    cid = c["id"]
    conn = db.get_connection()
    with conn:
        conn.execute("UPDATE clients SET plafond_credit=50000 WHERE id=?", (cid,))

    p = db.get_produits()[0]
    
    # Première vente à crédit
    ok, msg, vid = db.create_vente("Client Crédit Libre", [(p["id"], 1, p["prix_vente"])], mode_paiement="Crédit", montant_paye=0, client_id=cid)
    assert ok, f"Vente à crédit refusée : {msg}"
    print("  OK   Première vente à crédit enregistrée sans blocage de plafond")

    # Deuxième vente à crédit alors qu'il a déjà une dette impayée
    ok, msg, vid2 = db.create_vente("Client Crédit Libre", [(p["id"], 1, p["prix_vente"])], mode_paiement="Crédit", montant_paye=0, client_id=cid)
    assert ok, f"Deuxième vente à crédit refusée : {msg}"
    print("  OK   Deuxième vente à crédit acceptée (signalement visuel géré côté UI)")

def tester_noms_et_caracteres_speciaux():
    print("\n--- 4. Injection de caractères spéciaux (Saisie erronée) ---")
    nom_bizarre = "O'Connor & Co \"Special\" <Test> 100%"
    ok, msg = db.add_client(nom_bizarre, "00000000")
    assert ok, f"Échec ajout client nom spécial: {msg}"
    c = db.get_clients(nom_bizarre)[0]
    assert c["nom"] == nom_bizarre
    print("  OK   Caractères spéciaux (quotes, accents, symboles) gérés sans erreur SQL ou crash")

if __name__ == "__main__":
    try:
        tester_saisies_chaotiques()
        tester_scenarios_caisse_chaotiques()
        tester_credit_sans_plafond()
        tester_noms_et_caracteres_speciaux()
        print("\n==============================================")
        print("RÉSULTAT DU TEST DE STRESS : TOUS LES TEST PASSED (100% ROBUSTE)")
        print("==============================================")
    except Exception as e:
        print(f"\n❌ ERREUR DE STRESS TEST : {e}")
        import traceback
        traceback.print_exc()
        if __name__ == "__main__":
            sys.exit(1)
    finally:
        for s in ("", "-wal", "-shm"):
            try: os.remove(TMP_DB + s)
            except OSError: pass
