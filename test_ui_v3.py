"""
SODIPAC — Test headless des écrans v3
====================================

Instancie l'application et ouvre CHAQUE page v3 sur une base jetable,
puis exerce les chargements/filtres. Détecte les erreurs Tkinter sans
intervention humaine.

Lancement :  python test_ui_v3.py
"""

import os
import sys
import traceback

BASE = os.path.dirname(os.path.abspath(__file__))
DB_TEST = os.path.join(BASE, "test_ui_v3.db")

for suffixe in ("", "-wal", "-shm"):
    try:
        os.remove(DB_TEST + suffixe)
    except OSError:
        pass

import database as db
db.DB_PATH = DB_TEST
db.BACKUP_DIR = os.path.join(BASE, "sauvegardes_test")
db.init_database()
db.set_utilisateur_courant("testeur")

import metier_v3 as m3

# ─── Jeu de données minimal mais représentatif ───
db.add_fournisseur("Import Auto CI", telephone="0500000001")
fid = db.get_fournisseurs()[0]["id"]
db.add_client("Garage Koné", telephone="0700000001")
cid = db.get_clients()[0]["id"]
conn = db.get_connection()
with conn:
    conn.execute("UPDATE clients SET plafond_credit=50000 WHERE id=?", (cid,))
db.close_connection()  # reset _conn_persistante

cats = db.get_categories()
for i, (ref, nom) in enumerate([
        ("FIL-001", "Filtre à huile Yaris"),
        ("PLQ-001", "Plaquettes avant Corolla"),
        ("AMO-001", "Amortisseur avant Hilux"),
        ("BAT-001", "Batterie 60Ah")]):
    db.add_produit(ref, nom, categorie_id=cats[i % len(cats)]["id"], fournisseur_id=fid,
                   marque="Bosch", prix_achat=1000 * (i + 1), prix_vente=2000 * (i + 1),
                   stock_reserve=10, stock_vente=8, stock_mini=4)

produits = db.get_produits()
p1 = produits[0]

# Ventes : comptant + crédit (créance) + vente pour retour
db.create_vente("Client comptant", [(p1["id"], 2, 3000)], mode_paiement="Espèces")
db.create_vente("Garage Koné", [(p1["id"], 2, 5000)], mode_paiement="Crédit",
                montant_paye=0, client_id=cid)
ok, num, vid_retour = db.create_vente("Client retour", [(p1["id"], 2, 3000)])

# Commande fournisseur envoyée (pour tester réception) + une reçue (pour dette)
ok, msg, cmd1 = m3.creer_commande(fid, [(p1["id"], "", 10, 900)], frais=2000)
m3.envoyer_commande(cmd1)
ok, msg, cmd2 = m3.creer_commande(fid, [(produits[1]["id"], "", 5, 1800)])
m3.envoyer_commande(cmd2)
m3.receptionner_commande(cmd2)

# Dépôt supplémentaire + transfert
m3.add_depot("MAG", "Magasin Yopougon", "magasin")
depots = m3.get_depots()
m3.transferer(p1["id"], depots[0]["id"], depots[-1]["id"], 2)

# Inventaire en cours avec un écart
ok, msg, inv = m3.ouvrir_inventaire(depot_id=depots[0]["id"])
m3.saisir_comptage(inv, p1["id"], 1, motif="Vol")

# Retour partiel
m3.creer_retour(vid_retour, [(p1["id"], 1, 3000, True, "neuf")], motif="Test")

# Compatibilité véhicule + référence croisée
yaris = [x for x in m3.get_modeles("Toyota") if x["modele"] == "Yaris"]
if yaris:
    m3.lier_compatibilite(p1["id"], yaris[0]["id"], "avant", "confirme")
m3.add_reference(p1["id"], "90915-YZZD2", "oem", "Toyota")

# ─── Lancement de l'interface ───
import tkinter as tk
from ui_widgets import appliquer_palette, appliquer_theme
import main

erreurs = []
reussis = []


def essai(libelle, fonction):
    try:
        fonction()
        root.update()
        reussis.append(libelle)
        print(f"OK   {libelle}")
    except Exception as e:
        erreurs.append((libelle, e))
        print(f"FAIL {libelle} : {e}")
        traceback.print_exc()


appliquer_palette("clair")
root = tk.Tk()
root.geometry("1400x820")
appliquer_theme(root)

utilisateur = {"id": 1, "nom_utilisateur": "admin", "nom_complet": "Admin Test",
               "role": "superviseur"}

try:
    app = main.Application(root, utilisateur)
    root.update()
    print("OK   Application instanciée avec le mixin PagesV3")
    reussis.append("instanciation")
except Exception as e:
    print(f"FAIL instanciation : {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== PAGES v3 ===")
essai("page Créances", app.afficher_creances)
essai("page Achats", app.afficher_achats)
essai("page Inventaire", app.afficher_inventaire)
essai("page Recherche véhicule", app.afficher_recherche_vehicule)
essai("page Dépôts", app.afficher_depots)
essai("page Retours", app.afficher_retours)
essai("page Prévisions", app.afficher_previsions)

print("\n=== PAGES v2 (non-régression) ===")
essai("dashboard (courbe linéaire)", app.afficher_dashboard)
essai("caisse", app.afficher_caisse)
essai("produits", app.afficher_produits)
essai("stock", app.afficher_stock)
essai("clients", app.afficher_clients)
essai("catégories", app.afficher_categories)
essai("fournisseurs", app.afficher_fournisseurs)
essai("mouvements", app.afficher_mouvements)
essai("rapports", app.afficher_rapports)
essai("paramètres", app.afficher_parametres)
essai("aide", app.afficher_aide)

print("\n=== INTERACTIONS CRÉANCES ===")
app.afficher_creances()
root.update()
essai("sélection client → détail",
      lambda: (app.tab_creances_client.selection_set(
          app.tab_creances_client.get_children()[0]),
          app._charger_creances_detail()) if app.tab_creances_client.get_children() else None)
essai("rechargement créances", app._charger_creances)
nb_creances = len(app.tab_creances.get_children())
print(f"     → {nb_creances} facture(s) impayée(s) affichée(s)")
assert nb_creances >= 1, "la créance de test devrait être visible"

print("\n=== INTERACTIONS ACHATS ===")
app.afficher_achats()
root.update()
essai("sélection commande → lignes",
      lambda: (app.tab_commandes.selection_set(app.tab_commandes.get_children()[0]),
               app._charger_cmd_lignes()) if app.tab_commandes.get_children() else None)
for statut in ("Brouillon", "Envoyée", "Reçue", "Toutes"):
    essai(f"filtre statut « {statut} »",
          lambda s=statut: (app.filtre_cmd.set(s), app._charger_commandes()))

print("\n=== INTERACTIONS INVENTAIRE ===")
app.afficher_inventaire()
root.update()
essai("chargement lignes d'inventaire", app._charger_inv_lignes)
essai("filtre écarts seulement",
      lambda: (app.var_inv_ecarts.set(True), app._charger_inv_lignes()))
essai("retour à toutes les lignes",
      lambda: (app.var_inv_ecarts.set(False), app._charger_inv_lignes()))

print("\n=== INTERACTIONS RECHERCHE VÉHICULE ===")
app.afficher_recherche_vehicule()
root.update()
essai("maj des modèles", app._maj_modeles)
essai("recherche Toyota Yaris 2008",
      lambda: (app.cb_marque.set("Toyota"), app._maj_modeles(),
               app.cb_modele.set("Yaris"), app.e_annee.delete(0, tk.END),
               app.e_annee.insert(0, "2008"), app._chercher_vehicule()))
trouve = len(app.tab_vehic.get_children())
print(f"     → {trouve} pièce(s) compatible(s) trouvée(s)")
essai("recherche par référence OEM",
      lambda: (app.e_ref_univ.delete(0, tk.END),
               app.e_ref_univ.insert(0, "90915-YZZD2"), app._chercher_reference()))
par_ref = len(app.tab_vehic.get_children())
print(f"     → {par_ref} pièce(s) trouvée(s) par référence OEM")
essai("réinitialisation des filtres", app._reset_vehicule)

print("\n=== INTERACTIONS DÉPÔTS ===")
app.afficher_depots()
root.update()
essai("contenu du dépôt", app._charger_depot_contenu)
essai("sélection 2e dépôt",
      lambda: (app.tab_depots.selection_set(app.tab_depots.get_children()[1]),
               app._charger_depot_contenu()) if len(app.tab_depots.get_children()) > 1 else None)
nb_depots = len(app.tab_depots.get_children())
print(f"     → {nb_depots} dépôt(s) listé(s)")
assert nb_depots == 3, f"3 dépôts attendus, {nb_depots} trouvés"

print("\n=== INTERACTIONS RETOURS ===")
app.afficher_retours()
root.update()
essai("détail du retour",
      lambda: (app.tab_retours.selection_set(app.tab_retours.get_children()[0]),
               app._charger_retour_lignes()) if app.tab_retours.get_children() else None)
nb_retours = len(app.tab_retours.get_children())
print(f"     → {nb_retours} retour(s) affiché(s)")
assert nb_retours >= 1, "le retour de test devrait être visible"

print("\n=== INTERACTIONS PRÉVISIONS ===")
app.afficher_previsions()
root.update()
for horizon in ("7 jours", "14 jours", "30 jours", "60 jours"):
    essai(f"horizon {horizon}",
          lambda h=horizon: (app.cb_horizon.set(h), app._charger_previsions()))
essai("recalcul ABC", app._recalculer_abc)

print("\n=== TRI DES COLONNES (toutes les nouvelles tables) ===")
tables = [
    ("créances", app.afficher_creances, "tab_creances", ("total", "reste", "age")),
    ("commandes", app.afficher_achats, "tab_commandes", ("total", "lignes")),
    ("inventaire", app.afficher_inventaire, "tab_inventaires", ("ecarts", "valeur")),
    ("dépôts", app.afficher_depots, "tab_depots", ("articles", "valeur")),
    ("retours", app.afficher_retours, "tab_retours", ("total", "nb")),
    ("prévisions", app.afficher_previsions, "tab_previsions", ("stock", "cmd", "valeur")),
]
for nom, ouvrir, attr, colonnes in tables:
    def trier(o=ouvrir, a=attr, c=colonnes):
        o()
        root.update()
        t = getattr(app, a)
        for col in c:
            t.trier(col)
            t.trier(col)
    essai(f"tri {nom}", trier)

print("\n=== BASCULE DE THÈME (reconstruit tout le menu) ===")
essai("passage en thème sombre", app.basculer_theme)
essai("page Créances en sombre", app.afficher_creances)
essai("page Prévisions en sombre", app.afficher_previsions)
essai("retour au thème clair", app.basculer_theme)

print("\n=== GRAPHIQUE LINÉAIRE ===")
essai("dashboard avec courbe 7j", app.afficher_dashboard)
essai("prévisions avec courbe 30j", app.afficher_previsions)

print("\n=== MENU DÉFILANT ===")
nb_boutons = len(app.boutons_menu)
print(f"     → {nb_boutons} entrée(s) de menu construite(s)")
assert nb_boutons >= 16, f"Au moins 16 entrées attendues, {nb_boutons} trouvées"
manquants = [libelle for libelle in
             ("Créances", "Achats", "Dépôts", "Inventaire", "Retours",
              "Prévisions")
             if app._idx_menu(libelle) < 0]
assert not manquants, f"entrées de menu introuvables : {manquants}"
print("     → toutes les rubriques v3 sont dans le menu")

# ─── Bilan ───
print("\n" + "=" * 50)
if erreurs:
    print(f"RESULTAT : {len(reussis)} OK, {len(erreurs)} ECHECS")
    for libelle, e in erreurs:
        print(f"   - {libelle} : {e}")
else:
    print(f"RESULTAT : {len(reussis)} OK, 0 echec — INTERFACE v3 VALIDEE")
print("=" * 50)

try:
    root.destroy()
except tk.TclError:
    pass

for suffixe in ("", "-wal", "-shm"):
    try:
        os.remove(DB_TEST + suffixe)
    except OSError:
        pass

sys.exit(1 if erreurs else 0)
