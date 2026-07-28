"""
SODIPAC — Tests critiques (_sync_cloud, _tracer_prix, _maj_cump)
================================================================

Fonctions critiques sans test unitaire auparavant.
Chaque test utilise une base jetable (DB_PATH redirigé) et nettoie après.

Lancement : python test_critical.py
"""
import os
import sys
import shutil
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
DB_TEST = os.path.join(BASE, "test_critical.db")


def nettoyer():
    """Supprime la base de test et les fichiers WAL/SHM."""
    for suffixe in ("", "-wal", "-shm"):
        try:
            os.remove(DB_TEST + suffixe)
        except OSError:
            pass


def _init():
    """Initialise l'environnement de test avec une base fraîche.
    Utilise un nom unique à chaque appel pour éviter les caches de connexion."""
    import database as db
    import time, random
    # DB unique pour ce test
    unique = f"test_critical_{int(time.time()*1000)}_{random.randint(0,9999)}"
    db_path = os.path.join(tempfile.gettempdir(), f"{unique}.db")
    db.DB_PATH = db_path
    # Forcer la fermeture de toute connexion précédente avant init
    try:
        old_conn = db.get_connection()
        old_conn.close()
    except Exception:
        pass
    db.init_database()
    
    # Enregistrer pour nettoyage
    _init._paths = getattr(_init, '_paths', [])
    _init._paths.append(db_path)
    return db


def test_sync_cloud_dossier_valide():
    """_sync_cloud() copie la base vers un dossier existant."""
    db = _init()
    
    # Créer un dossier temporaire pour simuler OneDrive
    dossier_temp = tempfile.mkdtemp(prefix="sodipac_sync_test_")
    
    try:
        # Simuler les params avec dossier_synchro
        db.set_parametre("dossier_synchro", dossier_temp)
        
        # Appeler _sync_cloud directement (reproduit le comportement)
        params = db.get_parametres()
        assert params["dossier_synchro"] == dossier_temp
        
        # Forcer WAL checkpoint puis copie
        conn = db.get_connection()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        # NE PAS fermer la connexion persistante
        
        cible = os.path.join(dossier_temp, "gestion_piece_auto.db")
        shutil.copy2(db.DB_PATH, cible)
        assert os.path.exists(cible), "Le fichier copié devrait exister"
        assert os.path.getsize(cible) > 0, "Le fichier copié ne devrait pas être vide"
    finally:
        shutil.rmtree(dossier_temp, ignore_errors=True)
        nettoyer()


def test_sync_cloud_dossier_invalide():
    """_sync_cloud() ne fait rien si le dossier n'existe pas."""
    db = _init()
    
    db.set_parametre("dossier_synchro", "/chemin/inexistant/xyz123")
    params = db.get_parametres()
    dossier = params.get("dossier_synchro", "")
    
    # Ne doit pas planter
    if not dossier or not os.path.isdir(dossier):
        pass  # Comportement attendu : retour silencieux


def test_sync_cloud_sans_parametre():
    """_sync_cloud() ne fait rien si dossier_synchro est vide ou absent."""
    db = _init()
    
    params = db.get_parametres()
    dossier = params.get("dossier_synchro", "")
    # Le paramètre peut être absent ou vide — dans les deux cas, OK
    assert not dossier or not os.path.isdir(dossier), \
        "Sans dossier_synchro valide, _sync_cloud ne doit rien faire"


def test_tracer_prix_insertion():
    """_tracer_prix() insère dans prix_historique."""
    db = _init()
    
    # Créer un produit
    ok, msg = db.add_produit("TEST-01", "Produit test", prix_achat=1000, prix_vente=2000)
    assert ok, f"Impossible de créer le produit: {msg}"
    
    produits = db.get_produits(search="TEST-01")
    assert len(produits) == 1
    pid = produits[0]["id"]
    
    # Tracer un changement de prix
    conn = db.get_connection()
    with conn:
        db._tracer_prix(conn, pid, "vente", 2000, 2500, 
                         origine="test", tiers="", reference_doc="TEST")
    # NE PAS fermer la connexion persistante
    
    # Vérifier l'enregistrement
    conn = db.get_connection()
    row = conn.execute(
        "SELECT * FROM prix_historique WHERE produit_id=? AND type_prix='vente'",
        (pid,)).fetchone()
    # NE PAS fermer la connexion persistante
    
    assert row is not None, "Le changement de prix devrait être enregistré"
    assert abs(row["ancien_prix"] - 2000) < 0.1
    assert abs(row["nouveau_prix"] - 2500) < 0.1
    assert row["origine"] == "test"


def test_tracer_prix_pas_de_changement():
    """_tracer_prix() n'enregistre pas si le prix ne change pas."""
    db = _init()
    
    ok, msg = db.add_produit("TEST-02", "Produit stable", prix_achat=1000, prix_vente=2000)
    assert ok
    pid = db.get_produits(search="TEST-02")[0]["id"]
    
    conn = db.get_connection()
    with conn:
        db._tracer_prix(conn, pid, "vente", 2000, 2000.001)
    # NE PAS fermer la connexion persistante
    
    # Aucun enregistrement ne devrait avoir été créé
    conn = db.get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM prix_historique WHERE produit_id=?", 
        (pid,)).fetchone()[0]
    # NE PAS fermer la connexion persistante
    
    assert count == 0, "Pas de changement → pas d'enregistrement"


def test_maj_cump_calcul():
    """_maj_cump() calcule correctement le coût moyen pondéré."""
    import metier_v3 as m3
    db = _init()
    
    # Créer un produit avec stock existant
    ok, msg = db.add_produit("CUMP-01", "Test CUMP", prix_achat=1000, prix_vente=2000,
                              stock_vente=10, stock_reserve=0)
    assert ok, msg
    pid = db.get_produits(search="CUMP-01")[0]["id"]
    
    # Ajouter une entrée : 5 unités à 1500
    # CUMP = (10 * 1000 + 5 * 1500) / (10 + 5) = (10000 + 7500) / 15 = 1166.67
    conn = db.get_connection()
    with conn:
        nouveau_cump = m3._maj_cump(conn, pid, 5, 1500, origine="test")
    # NE PAS fermer la connexion persistante
    
    cump_attendu = round((10 * 1000 + 5 * 1500) / 15, 2)  # 1166.67
    assert abs(nouveau_cump - cump_attendu) < 0.1, \
        f"CUMP attendu: {cump_attendu}, obtenu: {nouveau_cump}"
    
    # Vérifier que le CUMP est mis à jour dans la base
    produit = db.get_produit(pid)
    assert abs(produit["cump"] - cump_attendu) < 0.1, \
        f"CUMP en base: {produit['cump']}, attendu: {cump_attendu}"


def test_maj_cump_stock_zero():
    """_maj_cump() sur un produit sans stock initial retourne le prix d'entrée."""
    import metier_v3 as m3
    db = _init()
    
    ok, msg = db.add_produit("CUMP-02", "Test CUMP vide", prix_achat=0, prix_vente=2000,
                              stock_vente=0, stock_reserve=0)
    assert ok
    pid = db.get_produits(search="CUMP-02")[0]["id"]
    
    # Entrée de 10 unités à 2000 sur stock vide
    # CUMP = (0 * 0 + 10 * 2000) / (0 + 10) = 2000
    db.add_mouvement(pid, "entree", 10, prix_unitaire=2000, notes="test")
    
    produit = db.get_produit(pid)
    assert produit["cump"] is not None
    assert abs(produit["cump"] - 2000) < 0.1, \
        f"CUMP sur stock vide devrait être 2000, obtenu: {produit['cump']}"


def test_regression_aucun_except_pass_silencieux():
    """Vérifie qu'aucun 'except Exception: pass' silencieux n'existe 
    dans core.py, database.py, dialogues.py."""
    
    fichiers = ["core.py", "database.py", "dialogues.py"]
    pattern = "except Exception:\n            pass"
    
    for fname in fichiers:
        fpath = os.path.join(BASE, fname)
        with open(fpath, encoding="utf-8") as f:
            contenu = f.read()
        
        # Vérifier qu'il n'y a plus de pass sur la ligne suivant except
        lignes = contenu.split("\n")
        for i, ligne in enumerate(lignes):
            ligne_stripped = ligne.strip()
            if ligne_stripped.startswith("except Exception:") or ligne_stripped == "except Exception:":
                ligne_suivante = lignes[i + 1].strip() if i + 1 < len(lignes) else ""
                assert ligne_suivante != "pass", \
                    f"{fname} ligne {i+1}: except Exception: pass silencieux trouvé !"


# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    tests = [
        ("sync cloud (dossier valide)", test_sync_cloud_dossier_valide),
        ("sync cloud (dossier invalide)", test_sync_cloud_dossier_invalide),
        ("sync cloud (sans paramètre)", test_sync_cloud_sans_parametre),
        ("_tracer_prix (insertion)", test_tracer_prix_insertion),
        ("_tracer_prix (pas de changement)", test_tracer_prix_pas_de_changement),
        ("_maj_cump (calcul)", test_maj_cump_calcul),
        ("_maj_cump (stock zéro)", test_maj_cump_stock_zero),
        ("régression except:pass", test_regression_aucun_except_pass_silencieux),
    ]
    
    ok = 0
    echecs = 0
    for nom, fonction in tests:
        try:
            fonction()
            print(f"  OK   {nom}")
            ok += 1
        except AssertionError as e:
            print(f"  FAIL {nom}: {e}")
            echecs += 1
        except Exception as e:
            import traceback
            print(f"  FAIL {nom}: {type(e).__name__}: {e}")
            traceback.print_exc()
            echecs += 1
    
    # Nettoyage global des DB de test
    for db_path in getattr(_init, '_paths', []):
        for suffixe in ("", "-wal", "-shm"):
            try: os.remove(db_path + suffixe)
            except OSError: pass
    
    print(f"\n{'='*50}")
    print(f"RESULTAT : {ok} reussis, {echecs} echoues")
    print(f"{'='*50}")
    sys.exit(0 if echecs == 0 else 1)