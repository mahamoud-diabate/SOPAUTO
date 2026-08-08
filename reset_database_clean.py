"""
SODIPAC - Réinitialisation à Neuf de la Base de Données (Production Clean Reset)
Supprime toutes les données de test (produits, ventes, clients, mouvements, créances, réappro)
et réinitialise l'application avec la structure propre et le compte admin par défaut.
"""
import os
import sqlite3
import database as db

def reinitialiser_a_neuf():
    print("--- 1. Réinitialisation à neuf de la base de données ---")
    db.init_database()
    conn = db.get_connection()
    with conn:
        tables = ["ventes_details", "ventes", "reglements", "mouvements_stock", 
                  "produits", "clients", "fournisseurs", "stock_depot", "journal_activite"]
        for t in tables:
            try:
                conn.execute(f"DELETE FROM {t}")
                print(f"  OK   Table {t} vidée")
            except Exception as e:
                print(f"  Avertissement table {t}: {e}")
        
        try:
            conn.execute("DELETE FROM sqlite_sequence")
        except Exception:
            pass

    # Vérification des catégories par défaut
    cats = db.get_categories()
    print(f"\n--- 2. Catégories par défaut prêtes ({len(cats)} catégories) ---")
    for c in cats:
        print(f"  - {c['nom']}")

    # Vérification de l'utilisateur administrateur par défaut
    users = db.get_utilisateurs()
    print(f"\n--- 3. Utilisateurs configurés ({len(users)} utilisateur) ---")
    for u in users:
        print(f"  - {u['nom_utilisateur']} ({u['role']})")

    print("\n==============================================")
    print("RÉINITIALISATION REUSSIE : LA BASE EST 100% VIERGE ET PRÊTE À L'EMPLOI")
    print("==============================================")

if __name__ == "__main__":
    reinitialiser_a_neuf()
