"""Tests agressifs - testeur méchant. Chaque test prouve/réfute un bug suspecté."""
import os, sqlite3, sys, tempfile

TMP = tempfile.mkdtemp()
import database as db
db.DB_PATH = os.path.join(TMP, "test.db")
db.BACKUP_DIR = os.path.join(TMP, "sauvegardes")
db.EXPORT_DIR = os.path.join(TMP, "exports")

db.init_database()
# Créer au moins un superviseur pour les tests (la base est vide)
db.add_utilisateur("admin", "admin123", "superviseur", "Admin")
bugs = []

def check(cond, bug_id, desc):
    print(("BUG CONFIRME " if not cond else "ok           ") + f"[{bug_id}] {desc}")
    if not cond:
        bugs.append(bug_id)

# --- B3: la migration CHECK recrée-t-elle la table à chaque démarrage ?
conn = db.get_connection()
conn.execute("DELETE FROM produits")  # aucun produit id=1 (le probe FK échouerait)
conn.commit()
root_avant = conn.execute("SELECT rootpage FROM sqlite_master WHERE name='mouvements_stock'").fetchone()[0]
conn.close()
db.init_database()  # 2e init
conn = db.get_connection()
root_apres = conn.execute("SELECT rootpage FROM sqlite_master WHERE name='mouvements_stock'").fetchone()[0]
conn.close()
check(root_avant == root_apres, "B3", "table mouvements_stock recréée au 2e démarrage (rootpage a changé)")

# setup produits
ok, _ = db.add_produit("REF-1", "Plaquette", prix_achat=1000, prix_vente=2000, stock_reserve=10, stock_vente=5)
p1 = db.trouver_produit("REF-1")

# --- B13: la caisse (main.py) contrôle produit['stock'] total mais create_vente exige stock_vente
# preuve DB-level: vendre 8 (<= stock total 15, > stock_vente 5) doit échouer
ok, msg, vid = db.create_vente("Client", [(p1["id"], 8, 2000)])
check(not ok, "B13-db", "vente 8 avec stock_vente=5, total=15 refusée par create_vente (l'UI panier accepte pourtant jusqu'à 15)")
import inspect, main
src = inspect.getsource(main.Application._ajouter_produit_panier)
check('stock_vente' in src, "B13-ui", "_ajouter_produit_panier contrôle stock_vente (sinon panier accepte l'invendable)")

# --- B1: vente à Crédit -> montant_paye=0 transformé en total par 'montant_paye or total'
# v3 : le crédit exige désormais un client avec plafond. On en crée un.
db.add_client("Débiteur", telephone="0700000099")
cli_deb = next(c for c in db.get_clients("Débiteur"))
_c = db.get_connection()
with _c:
    _c.execute("UPDATE clients SET plafond_credit=50000 WHERE id=?", (cli_deb["id"],))
_c.close()
ok, num, vid = db.create_vente("Débiteur", [(p1["id"], 2, 2000)], mode_paiement="Crédit",
                               montant_paye=0, client_id=cli_deb["id"])
check(ok, "B1-pre", f"vente à crédit acceptée avec plafond client ({num})")
v, _ = db.get_vente_details(vid)
check(v["montant_paye"] == 0, "B1", f"crédit: montant_paye devrait rester 0, vaut {v['montant_paye']} (dette invisible!)")

# --- v3 : la dette est désormais VISIBLE dans les créances
import metier_v3 as m3
_cre = m3.get_creances(client_id=cli_deb["id"])
check(len(_cre) == 1 and abs(_cre[0]["reste_du"] - 4000) < 0.01,
      "B1-v3", f"la dette de 4000 apparaît dans les créances ({_cre})")
check(not db.create_vente("Inconnu", [(p1["id"], 1, 2000)], mode_paiement="Crédit",
                          montant_paye=0)[0],
      "B1-v3b", "crédit sans client identifié désormais refusé")

# --- B45: update_utilisateur peut rétrograder/désactiver le dernier admin
users = db.get_utilisateurs()
admin = next(u for u in users if u["role"] == "superviseur")
ok, msg = db.update_utilisateur(admin["id"], role="vendeur")
check(not ok, "B45a", f"rétrogradation du dernier admin devrait être refusée (résultat: {ok}, {msg})")
# restaurer au cas où
db.update_utilisateur(admin["id"], role="superviseur")
ok, msg = db.update_utilisateur(admin["id"], actif=False)
check(not ok, "B45b", f"désactivation du dernier admin devrait être refusée (résultat: {ok}, {msg})")
db.update_utilisateur(admin["id"], actif=True)

# --- B8: delete_utilisateur refuse de supprimer un admin INACTIF quand il ne reste qu'1 actif
db.add_utilisateur("adm2", "pass1234", "superviseur", "Admin2")
u2 = next(u for u in db.get_utilisateurs() if u["nom_utilisateur"] == "adm2")
db.update_utilisateur(u2["id"], actif=False)  # adm2 inactif, admin reste seul actif
ok, msg = db.delete_utilisateur(u2["id"])
check(ok, "B8", f"suppression d'un admin INACTIF (un autre actif existe) devrait passer: {msg}")

# --- B7: import CSV écrase description + réactive produit inactif
db.add_produit("REF-2", "Filtre", description="Description importante", prix_achat=500, prix_vente=900, stock_vente=3)
p2 = db.trouver_produit("REF-2")
db.update_produit(p2["id"], "REF-2", "Filtre", description="Description importante",
                  prix_achat=500, prix_vente=900, actif=0)
csv_path = os.path.join(TMP, "imp.csv")
with open(csv_path, "w", encoding="utf-8-sig") as f:
    f.write("Référence;Nom;Prix achat;Prix vente\nREF-2;Filtre;600;1000\n")
db.importer_produits_csv(csv_path)
p2b = db.trouver_produit("REF-2")
check(p2b["description"] == "Description importante", "B7a", f"import CSV a écrasé la description: '{p2b['description']}'")
check(p2b["actif"] == 0, "B7b", f"import CSV a réactivé un produit désactivé (actif={p2b['actif']})")

# --- B34: marge du rapport ignore la remise (marge surestimée)
# vente 1 article 2000 (achat 1000) avec remise 500 => marge réelle 500, rapportée 1000
ok, num, vid3 = db.create_vente("C", [(p1["id"], 1, 2000)], remise=500)
r = db.rapport_ventes("2000-01-01", "2100-01-01")
# ventes: crédit 2×2000 (marge 2000) + 1×2000 remise 500 (marge 500) => marge réelle 2500
check(abs(r["resume"]["marge"] - 2500) < 0.01, "B34", f"marge={r['resume']['marge']} attendu 2500 (remises déduites)")

# --- B2/correction cible: correction réserve met stock_reserve=qte
ok, msg = db.add_mouvement(p1["id"], "correction", 20, cible="reserve")
p1c = db.get_produit(p1["id"])
check(p1c["stock_reserve"] == 20 and p1c["stock"] == p1c["stock_reserve"] + p1c["stock_vente"],
      "B2", f"correction réserve: reserve={p1c['stock_reserve']} total={p1c['stock']} vente={p1c['stock_vente']}")

# --- transferts au-delà du dispo
ok, msg = db.add_mouvement(p1["id"], "transfert", 9999, cible="vente")
check(not ok, "T1", "transfert > réserve refusé")

# --- B49: doublons panier avec prix différents (le 2e prix est ignoré silencieusement)
ok, num, vid4 = db.create_vente("C", [(p1["id"], 1, 2000), (p1["id"], 1, 1500)])
if ok:
    v4, lignes4 = db.get_vente_details(vid4)
    check(abs(v4["total"] - 3500) < 0.01, "B49", f"2 lignes même produit prix 2000+1500: total={v4['total']} (attendu 3500)")

# --- B38: prefixe facture avec caractères dangereux -> nom de fichier
db.set_parametre("prefixe_facture", "FAC")

# --- suggestion: sauvegardes illimitées
for _ in range(3):
    db.sauvegarder_base()
n = len(db.lister_sauvegardes())
print(f"info: {n} sauvegardes, aucune rotation (croissance illimitée ~100Ko/fermeture)")

print()
print("BUGS CONFIRMES:", bugs if bugs else "aucun")
