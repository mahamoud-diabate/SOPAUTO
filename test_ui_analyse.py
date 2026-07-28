"""
SODIPAC — Test headless de l'écran « Analyse commerciale »
=========================================================

Crée un scénario de négociation réaliste, ouvre l'écran d'analyse et
exerce chaque onglet, filtre et dialogue.

Lancement :  python test_ui_analyse.py
"""

import os
import sys
import traceback
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DB_TEST = os.path.join(BASE, "test_ui_analyse.db")

for suffixe in ("", "-wal", "-shm"):
    try:
        os.remove(DB_TEST + suffixe)
    except OSError:
        pass

import database as db
db.DB_PATH = DB_TEST
db.BACKUP_DIR = os.path.join(BASE, "sauvegardes_test")
db.init_database()
db.set_utilisateur_courant("admin")

import analyse_prix as ap

# ─── Scénario : 3 comportements de prix + 2 tendances ───
cats = db.get_categories()
produits_def = [
    ("BRADE-01", "Plaquettes bradées", 5000, 10000),
    ("MAJOR-01", "Amortisseur rare", 5000, 10000),
    ("JUSTE-01", "Filtre standard", 5000, 10000),
    ("PERTE-01", "Batterie soldée", 8000, 10000),
    ("DECLIN-01", "Pièce qui décroche", 2000, 5000),
    ("BOOM-01", "Pièce qui décolle", 2000, 5000),
]
for ref, nom, achat, vente in produits_def:
    db.add_produit(ref, nom, categorie_id=cats[0]["id"], prix_achat=achat,
                   prix_vente=vente, stock_vente=400, stock_mini=5)
p = {ref: db.trouver_produit(ref) for ref, *_ in produits_def}


def vendre(pid, qte, prix, jours_avant=0, client="Client", vendeur="admin"):
    db.set_utilisateur_courant(vendeur)
    ok, num, vid = db.create_vente(client, [(pid, qte, prix)])
    if ok and jours_avant:
        date = (datetime.now() - timedelta(days=jours_avant)).strftime("%Y-%m-%d %H:%M:%S")
        conn = db.get_connection()
        with conn:
            conn.execute("UPDATE ventes SET date_vente=? WHERE id=?", (date, vid))
        db.close_connection()  # reset _conn_persistante
    return vid


for jour in (2, 5, 9, 14, 20):
    vendre(p["BRADE-01"]["id"], 2, 8000, jour)     # -20 %
    vendre(p["MAJOR-01"]["id"], 2, 12000, jour)    # +20 %
    vendre(p["JUSTE-01"]["id"], 2, 10000, jour)    # au prix
vendre(p["PERTE-01"]["id"], 1, 7000, 3)            # vente à perte
vendre(p["PERTE-01"]["id"], 1, 10000, 10)

for jour in (35, 40, 45, 50):
    vendre(p["DECLIN-01"]["id"], 10, 5000, jour)
vendre(p["DECLIN-01"]["id"], 5, 5000, 10)
vendre(p["BOOM-01"]["id"], 4, 5000, 45)
for jour in (3, 8, 15, 22):
    vendre(p["BOOM-01"]["id"], 11, 5000, jour)

# Deux vendeurs opposés + un client négociateur
vendre(p["JUSTE-01"]["id"], 5, 7000, 1, vendeur="brade_tout")
vendre(p["JUSTE-01"]["id"], 5, 11000, 1, vendeur="tient_les_prix")
db.add_client("Garage Négociateur", telephone="0700000123")
cid = db.get_clients("Négociateur")[0]["id"]
db.set_utilisateur_courant("admin")
for _ in range(3):
    db.create_vente("Garage Négociateur", [(p["JUSTE-01"]["id"], 3, 7500)],
                    client_id=cid)

# ─── Interface ───
import tkinter as tk
from ui_widgets import appliquer_palette, appliquer_theme
import main

erreurs, reussis = [], []


def essai(libelle, fonction):
    try:
        fonction()
        root.update()
        reussis.append(libelle)
        print(f"  OK   {libelle}")
    except Exception as e:
        erreurs.append((libelle, e))
        print(f"  FAIL {libelle} : {e}")
        traceback.print_exc()


appliquer_palette("clair")
root = tk.Tk()
root.geometry("1500x880")
appliquer_theme(root)

app = main.Application(root, {"id": 1, "nom_utilisateur": "admin",
                              "nom_complet": "Admin", "role": "superviseur"})
root.update()
print("OK   Application instanciée avec PageAnalyse")

print("\n=== OUVERTURE DE L'ÉCRAN ===")
essai("page Analyse commerciale", app.afficher_analyse)

print("\n=== ONGLET PRIX PRATIQUÉS ===")
app.afficher_analyse()
root.update()
for periode in ("7 jours", "30 jours", "90 jours", "6 mois", "1 an"):
    essai(f"période {periode}",
          lambda pe=periode: (app.cb_periode_prix.set(pe), app._charger_prix()))
for filtre in ("Tout", "Bradés (sous le prix)", "Majorés (sur le prix)",
               "Vendus au prix", "⚠ Ventes à perte"):
    essai(f"filtre « {filtre} »",
          lambda f=filtre: (app.cb_filtre_prix.set(f), app._charger_prix()))

# Vérification du contenu affiché
app.cb_periode_prix.set("30 jours")
app.cb_filtre_prix.set("Tout")
app._charger_prix()
root.update()
nb = len(app.tab_prix.get_children())
print(f"       → {nb} produit(s) dans le tableau des prix")
assert nb >= 6, f"au moins 6 produits attendus, {nb} affichés"
verdict = app.lbl_verdict.cget("text")
print(f"       → verdict : {verdict[:100]}")
assert len(verdict) > 20, "le verdict doit être renseigné"

app.cb_filtre_prix.set("Bradés (sous le prix)")
app._charger_prix()
root.update()
nb_brades = len(app.tab_prix.get_children())
print(f"       → {nb_brades} produit(s) bradé(s) filtré(s)")
assert nb_brades >= 1, "BRADE-01 devrait apparaître"

app.cb_filtre_prix.set("⚠ Ventes à perte")
app._charger_prix()
root.update()
nb_perte = len(app.tab_prix.get_children())
print(f"       → {nb_perte} produit(s) vendu(s) à perte")
assert nb_perte == 1, f"1 produit à perte attendu, {nb_perte} trouvé(s)"

essai("tri des colonnes prix",
      lambda: [app.tab_prix.trier(c) for c in
               ("catalogue", "moyen", "ecart", "impact", "nb")])

print("\n=== ONGLET TENDANCES ===")
app.afficher_analyse()
root.update()
for fenetre in ("7 jours", "14 jours", "30 jours", "60 jours", "90 jours"):
    essai(f"fenêtre {fenetre}",
          lambda f=fenetre: (app.cb_fenetre_tend.set(f), app._charger_tendances()))
for filtre in ("Tout", "📉 En baisse seulement", "📈 En hausse seulement",
               "⛔ Ne se vendent plus", "🆕 Nouveaux"):
    essai(f"filtre « {filtre} »",
          lambda f=filtre: (app.cb_filtre_tend.set(f), app._charger_tendances()))

app.cb_fenetre_tend.set("30 jours")
app.cb_filtre_tend.set("📉 En baisse seulement")
app._charger_tendances()
root.update()
nb_baisse = len(app.tab_tendances.get_children())
print(f"       → {nb_baisse} produit(s) en baisse")
assert nb_baisse >= 1, "DECLIN-01 devrait apparaître en baisse"

app.cb_filtre_tend.set("📈 En hausse seulement")
app._charger_tendances()
root.update()
nb_hausse = len(app.tab_tendances.get_children())
print(f"       → {nb_hausse} produit(s) en hausse")
assert nb_hausse >= 1, "BOOM-01 devrait apparaître en hausse"

essai("tri des colonnes tendances",
      lambda: [app.tab_tendances.trier(c) for c in
               ("avant", "apres", "varpct", "capital")])

print("\n=== ONGLET ALERTES ===")
app.afficher_analyse()
root.update()
essai("chargement des alertes", app._charger_alertes)
nb_alertes = len(app.tab_alertes.get_children())
print(f"       → {nb_alertes} alerte(s) affichée(s)")
assert nb_alertes >= 2, f"au moins 2 alertes attendues, {nb_alertes} trouvée(s)"
essai("tri des alertes", lambda: [app.tab_alertes.trier(c) for c in ("niveau", "cat")])

print("\n=== ONGLET QUI NÉGOCIE ===")
app.afficher_analyse()
root.update()
for periode in ("30 jours", "90 jours", "1 an"):
    essai(f"période {periode}",
          lambda pe=periode: (app.cb_periode_nego.set(pe), app._charger_negociation()))
nb_v = len(app.tab_nego_vendeur.get_children())
nb_c = len(app.tab_nego_client.get_children())
print(f"       → {nb_v} vendeur(s), {nb_c} client(s)")
assert nb_v >= 2, f"au moins 2 vendeurs attendus, {nb_v} trouvé(s)"
essai("tri vendeurs", lambda: [app.tab_nego_vendeur.trier(c) for c in ("ca", "ecart", "impact")])
essai("tri clients", lambda: [app.tab_nego_client.trier(c) for c in ("ca", "impact")])

print("\n=== DIALOGUES ===")
app.afficher_analyse()
app.cb_filtre_prix.set("Tout")
app._charger_prix()
root.update()


def ouvrir_historique():
    from pages_analyse import DialogueHistoriquePrix
    d = DialogueHistoriquePrix(root, p["BRADE-01"]["id"], "F CFA")
    root.update()
    d.destroy()


essai("dialogue Historique des prix (avec courbe)", ouvrir_historique)


def ouvrir_conseil():
    from pages_analyse import DialoguePrixConseille
    conseil = ap.prix_conseille(p["BRADE-01"]["id"], 90)
    assert conseil["possible"], "le conseil devrait être calculable"
    d = DialoguePrixConseille(root, p["BRADE-01"]["id"], conseil, "F CFA", app)
    root.update()
    d.destroy()


essai("dialogue Prix conseillé", ouvrir_conseil)


def historique_produit_sans_vente():
    from pages_analyse import DialogueHistoriquePrix
    db.add_produit("VIDE-01", "Jamais vendu", prix_achat=100, prix_vente=200,
                   stock_vente=1)
    pv = db.trouver_produit("VIDE-01")
    d = DialogueHistoriquePrix(root, pv["id"], "F CFA")
    root.update()
    try:
        d.destroy()
    except tk.TclError:
        pass


essai("historique d'un produit jamais vendu (pas de plantage)",
      historique_produit_sans_vente)

print("\n=== EXPORTS ===")
essai("export CSV analyse prix",
      lambda: os.path.isfile(ap.exporter_analyse_prix(30)) or
              (_ for _ in ()).throw(AssertionError("fichier non créé")))
essai("export CSV tendances",
      lambda: os.path.isfile(ap.exporter_tendances(30)) or
              (_ for _ in ()).throw(AssertionError("fichier non créé")))

print("\n=== EXPORT PDF ===")
import export_pdf
print(f"       → moteur détecté : {export_pdf.nom_moteur()}")
if export_pdf.moteur_disponible():
    ventes = db.get_ventes(limit=1, inclure_annulees=False)

    def pdf_facture():
        ok, res = export_pdf.facture_pdf(ventes[0]["id"], ouvrir=False)
        assert ok, f"PDF non généré : {res}"
        taille = os.path.getsize(res)
        assert taille > 1000, f"PDF trop petit ({taille} octets)"
        print(f"       → PDF facture : {taille:,} octets")

    essai("génération PDF d'une facture", pdf_facture)

    def pdf_reappro():
        ok, res = export_pdf.reappro_pdf(ouvrir=False)
        assert ok, f"PDF non généré : {res}"
        print(f"       → PDF réappro : {os.path.getsize(res):,} octets")

    essai("génération PDF du bon de réappro", pdf_reappro)
else:
    print("       → aucun moteur PDF : tests PDF ignorés (comportement normal)")

print("\n=== NON-RÉGRESSION DES AUTRES PAGES ===")
for nom, fonction in [
        ("dashboard", app.afficher_dashboard), ("caisse", app.afficher_caisse),
        ("produits", app.afficher_produits), ("stock", app.afficher_stock),
        ("clients", app.afficher_clients), ("créances", app.afficher_creances),
        ("achats", app.afficher_achats), ("dépôts", app.afficher_depots),
        ("inventaire", app.afficher_inventaire), ("retours", app.afficher_retours),
        ("prévisions", app.afficher_previsions),
        ("rapports", app.afficher_rapports), ("paramètres", app.afficher_parametres),
        ("aide", app.afficher_aide)]:
    essai(f"page {nom}", fonction)

print("\n=== MENU ===")
nb_boutons = len(app.boutons_menu)
print(f"       → {nb_boutons} entrée(s) de menu")
assert nb_boutons >= 18, f"18 entrées attendues, {nb_boutons} trouvées"
assert app._idx_menu("Analyse") >= 0, "l'entrée Analyse doit être dans le menu"
print("       → l'entrée « Analyse » est bien présente")

print("\n=== BASCULE DE THÈME ===")
essai("thème sombre", app.basculer_theme)
essai("analyse en thème sombre", app.afficher_analyse)
essai("retour thème clair", app.basculer_theme)

print("\n" + "=" * 56)
if erreurs:
    print(f"RESULTAT : {len(reussis)} OK, {len(erreurs)} ECHECS")
    for libelle, e in erreurs:
        print(f"   - {libelle} : {e}")
else:
    print(f"RESULTAT : {len(reussis)} OK, 0 echec — ECRAN ANALYSE VALIDE")
print("=" * 56)

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
