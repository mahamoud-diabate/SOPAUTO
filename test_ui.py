"""Smoke test de l'interface : navigation, interactions, dialogues."""
import sys, traceback, tkinter as tk

erreurs = []
try:
    root = tk.Tk()
except tk.TclError as e:
    print(f"SKIP: pas d'affichage disponible ({e})")
    sys.exit(0)

root.withdraw()
import database as db
db.init_database()
import main
from ui_widgets import appliquer_theme
appliquer_theme(root)

user = {"id": 1, "nom_utilisateur": "admin", "role": "superviseur",
        "nom_complet": "Administrateur"}
try:
    app = main.Application(root, user)
    print("OK   Application instanciee")
except Exception:
    traceback.print_exc(); sys.exit(1)

pages = [
    ("dashboard", app.afficher_dashboard),
    ("caisse", app.afficher_caisse),
    ("produits", app.afficher_produits),
    ("produits (alertes)", lambda: app.afficher_produits(alertes=True)),
    ("stock", app.afficher_stock),
    ("clients", app.afficher_clients),
    ("categories", app.afficher_categories),
    ("fournisseurs", app.afficher_fournisseurs),
    ("mouvements", app.afficher_mouvements),
    ("rapports", app.afficher_rapports),
    ("parametres", app.afficher_parametres),
    ("aide", app.afficher_aide),
]
for nom, fn in pages:
    try:
        fn(); root.update()
        print(f"OK   page {nom}")
    except Exception as e:
        erreurs.append((nom, e)); print(f"FAIL page {nom}: {e}"); traceback.print_exc()

# ─── Interactions caisse complètes ───
try:
    app.afficher_caisse(); root.update()
    prods = db.get_produits(inclure_inactifs=False)
    dispo = [p for p in prods if p["stock_vente"] >= 2 and p["prix_vente"] > 0]
    if dispo:
        app._ajouter_produit_panier(dispo[0]["id"], 1)
        assert len(app.panier) == 1, "panier vide"
        app._ajouter_produit_panier(dispo[0]["id"], 1)
        assert app.panier[0]["quantite"] == 2, "cumul ligne KO"
        app.tab_panier.selection_set("0"); app._retirer_panier()
        assert not app.panier, "retrait KO"
        app.recherche_caisse.var.set(dispo[0]["reference"])
        app.recherche_caisse._placeholder_actif = False
        app._ajouter_panier()
        assert len(app.panier) == 1, "scan KO"
        app._vider_panier()
        assert not app.panier, "vider KO"
        print("OK   caisse: ajout/cumul/retrait/scan/vider")
    app.recherche_caisse.var.set("x"); app.recherche_caisse._placeholder_actif = False
    app._charger_catalogue_caisse(); root.update()
    print("OK   filtre catalogue caisse")
except Exception as e:
    erreurs.append(("caisse interactions", e)); traceback.print_exc()

# ─── Tri des colonnes ───
try:
    app.afficher_produits(); root.update()
    for col in ("nom", "stock", "pv", "valeur", "reserve", "vente"):
        app.tab_produits.trier(col); app.tab_produits.trier(col)
    root.update()
    print("OK   tri des colonnes")
except Exception as e:
    erreurs.append(("tri", e)); traceback.print_exc()

# ─── Recherche live + filtres produits ───
try:
    app.rech_produits.var.set("a"); app.rech_produits._placeholder_actif = False
    app._charger_produits()
    app.var_alertes.set(True); app._charger_produits()
    app.var_inactifs.set(True); app._charger_produits()
    app.filtre_cat.current(1); app._charger_produits()
    root.update()
    print("OK   recherche et filtres produits")
except Exception as e:
    erreurs.append(("filtres", e)); traceback.print_exc()

# ─── Rapports: periodes rapides ───
try:
    app.afficher_rapports(); root.update()
    for j in (0, 6, 29, -1):
        app._periode_rapide(j)
    root.update()
    print("OK   rapports: periodes rapides")
except Exception as e:
    erreurs.append(("rapports periodes", e)); traceback.print_exc()

# ─── Historique ventes + detail ───
try:
    app.afficher_rapports(); root.update()
    enfants = app.tab_ventes.get_children()
    if enfants:
        app.tab_ventes.selection_set(enfants[0])
        app._charger_lignes_vente(); root.update()
        assert app.tab_lignes_vente.get_children(), "detail vide"
        print("OK   detail de vente")
    else:
        print("OK   detail de vente (aucune vente)")
except Exception as e:
    erreurs.append(("detail vente", e)); traceback.print_exc()

# ─── Export CSV ───
try:
    chemin = db.exporter_produits()
    assert chemin.endswith(".csv"), "export CSV KO"
    import os
    assert os.path.exists(chemin), "fichier CSV non cree"
    os.remove(chemin)
    print("OK   export CSV produits")
except Exception as e:
    erreurs.append(("export", e)); traceback.print_exc()

# ─── Mouvement stock ───
try:
    prods = db.get_produits(inclure_inactifs=False)
    if prods:
        ok, msg = db.add_mouvement(prods[0]["id"], "entree", 10,
                                    cible="reserve", notes="Test UI")
        assert ok, f"mouvement KO: {msg}"
        print("OK   mouvement stock (entree reserve)")
except Exception as e:
    erreurs.append(("mouvement", e)); traceback.print_exc()

# ─── Roles restreints (sans instancier deux fois la racine) ───
try:
    for role, droits in (("vendeur", {"caisse"}), ("gerant", {"caisse", "produits", "stock", "rapports"})):
        with_modal = tk.Toplevel(root)
        with_modal.withdraw()
        from ui_widgets import appliquer_theme
        # Créer une app sur la Toplevel (évite conflit de root)
        app2 = main.Application(with_modal, {"id": 2, "nom_utilisateur": "t",
                                              "role": role, "nom_complet": "T"})
        for d in droits:
            assert app2.peut(d), f"{role} devrait pouvoir {d}"
        assert not app2.peut("admin"), f"{role} ne devrait pas etre admin"
        app2._sur_destruction(); with_modal.destroy()
        print(f"OK   role {role}")
except Exception as e:
    erreurs.append(("roles", e)); traceback.print_exc()

# ─── Dialogues ───
try:
    from dialogues import (DialogueProduit, DialogueClient, DialogueMouvement,
                           DialoguePaiement, DialogueUtilisateur, DialogueCategorie,
                           DialogueFournisseur)
    for cls, args in ((DialogueProduit, ()), (DialogueClient, ()),
                      (DialogueCategorie, ()), (DialogueFournisseur, ()),
                      (DialogueUtilisateur, ()),
                      (DialogueMouvement, ("entree",)),
                      (DialogueMouvement, ("sortie",)),
                      (DialogueMouvement, ("correction",)),
                      (DialogueMouvement, ("transfert",)),
                      (DialoguePaiement, (15000, [{"id": 1, "nom": "Article test", "quantite": 1, "pu": 15000}], db.get_clients()))):
        d = cls(root, *args); root.update(); d.dialog.destroy()
        print(f"OK   dialogue {cls.__name__}")
    p = db.get_produits()
    if p:
        d = DialogueProduit(root, p[0]); root.update(); d.dialog.destroy()
        print("OK   dialogue DialogueProduit (edition)")
except Exception as e:
    erreurs.append(("dialogues", e)); traceback.print_exc()

# ─── Batch paramètres ───
try:
    db.set_parametres_batch({"test_cle": "test_valeur", "devise": "F CFA"})
    v = db.get_parametres().get("test_cle")
    assert v == "test_valeur", f"batch params KO: {v}"
    print("OK   set_parametres_batch")
except Exception as e:
    erreurs.append(("batch params", e)); traceback.print_exc()

app._sur_destruction()
root.update()
root.destroy()
print(f"\n{'='*46}\n{'ECHECS: ' + str(len(erreurs)) if erreurs else 'INTERFACE OK - aucune erreur'}\n{'='*46}")
sys.exit(1 if erreurs else 0)