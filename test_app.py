"""Tests fonctionnels du module database (exécution réelle sur une base temporaire)."""
import os, sys, shutil, tempfile, traceback

TMP = tempfile.mkdtemp(prefix="sodipac_test_")
import database as db
db.DB_PATH = os.path.join(TMP, "test.db")
db.BACKUP_DIR = os.path.join(TMP, "sauvegardes")
db.EXPORT_DIR = os.path.join(TMP, "exports")

ok = fail = 0
def check(nom, condition, info=""):
    global ok, fail
    if condition:
        ok += 1; print(f"  OK   {nom}")
    else:
        fail += 1; print(f"  FAIL {nom} {info}")

print("=== INITIALISATION ===")
db.init_database()
check("base creee", os.path.exists(db.DB_PATH))
check("categories par defaut", len(db.get_categories()) == 10)

print("\n=== AUTHENTIFICATION ===")
u, m = db.authenticate("admin", "admin123")
check("login admin ok", u is not None, m)
check("mdp hashe", db.get_connection().execute(
    "select mot_de_passe from utilisateurs where nom_utilisateur='admin'").fetchone()[0].startswith("pbkdf2$"))
check("mauvais mdp refuse", db.authenticate("admin", "xxx")[0] is None)
check("user inconnu refuse", db.authenticate("bob", "x")[0] is None)
db.set_utilisateur_courant("admin")

ok2, m2 = db.add_utilisateur("vendeur1", "1234", "vendeur", "Vendeur Test")
check("creation utilisateur", ok2, m2)
check("mdp trop court refuse", not db.add_utilisateur("x", "1")[0])
check("doublon refuse", not db.add_utilisateur("vendeur1", "1234")[0])
check("dernier admin protege", not db.delete_utilisateur(1)[0])

print("\n=== PRODUITS ===")
cat = db.get_categories()[0]["id"]
ok3, m3 = db.add_fournisseur("Auto Pieces CI", "Kone", "0102030405")
four = db.get_fournisseurs()[0]["id"]
ok4, m4 = db.add_produit("FRE-001", "Plaquettes avant", categorie_id=cat, fournisseur_id=four,
                         prix_achat=8000, prix_vente=12000, stock_vente=10, stock_mini=3)
check("ajout produit", ok4, m4)
check("reference dupliquee refusee", not db.add_produit("FRE-001", "Autre")[0])
check("prix negatif refuse", not db.add_produit("X-1", "X", prix_achat=-5)[0])
check("nom vide refuse", not db.add_produit("X-2", "  ")[0])
check("mouvement stock initial cree", len(db.get_mouvements()) == 1)

db.add_produit("MOT-001", "Courroie distribution", categorie_id=cat, prix_achat=15000,
               prix_vente=22000, stock_vente=4, stock_mini=5, code_barres="3401234567890")
p1 = db.trouver_produit("FRE-001"); p2 = db.trouver_produit("3401234567890")
check("recherche par reference", p1 and p1["nom"] == "Plaquettes avant")
check("recherche par code-barres", p2 and p2["nom"] == "Courroie distribution")
ref_sug = db.suggerer_reference(cat)
prefixe_attendu = "".join(ch for ch in db.get_categories()[0]["nom"].upper() if ch.isalnum())[:3]
check("suggestion reference", ref_sug.startswith(prefixe_attendu + "-"), ref_sug)
check("suggestion reference unique", db.trouver_produit(ref_sug) is None)
check("filtre alertes", len(db.get_produits(seulement_alertes=True)) == 1)
check("recherche texte", len(db.get_produits(search="courroie")) == 1)

print("\n=== MOUVEMENTS ===")
r, m = db.add_mouvement(p1["id"], "entree", 5, 8500)
check("entree stock", r and db.get_produit(p1["id"])["stock"] == 15, m)
check("PMP mis a jour", db.get_produit(p1["id"])["prix_achat"] == 8500)
r, m = db.add_mouvement(p1["id"], "sortie", 3)
check("sortie stock", r and db.get_produit(p1["id"])["stock"] == 12, m)
r, m = db.add_mouvement(p1["id"], "sortie", 999)
check("sortie > stock refusee", not r, m)
check("stock inchange apres refus", db.get_produit(p1["id"])["stock"] == 12)
r, m = db.add_mouvement(p1["id"], "correction", 20)
check("correction inventaire", r and db.get_produit(p1["id"])["stock"] == 20, m)
mv = db.get_mouvements(produit_id=p1["id"])[0]
check("stock avant/apres traces", mv["stock_avant"] == 12 and mv["stock_apres"] == 20)
check("quantite 0 refusee", not db.add_mouvement(p1["id"], "entree", 0)[0])
check("type invalide refuse", not db.add_mouvement(p1["id"], "bidon", 1)[0])

print("\n=== VENTES ===")
db.add_client("Yao Kouassi", "0708091011", vehicule="Toyota Corolla")
cl = db.get_clients()[0]["id"]
ok5, num, vid = db.create_vente("Yao Kouassi", [(p1["id"], 2, 12000), (p2["id"], 1, 22000)],
                                remise=1000, mode_paiement="Wave", montant_paye=50000, client_id=cl)
check("vente creee", ok5, num)
check("numero facture genere", num and num.startswith("FAC-"), num)
v, lignes = db.get_vente_details(vid)
check("total = sous_total - remise", abs(v["total"] - (46000 - 1000)) < 0.01, v["total"])
check("prix_achat capture (marge)", all(l["prix_achat"] > 0 for l in lignes))
check("stock decremente", db.get_produit(p1["id"])["stock"] == 18)

# doublons cumules
avant = db.get_produit(p1["id"])["stock"]
ok6, num6, vid6 = db.create_vente("Test", [(p1["id"], 5, 12000), (p1["id"], 5, 12000)])
check("lignes dupliquees cumulees", ok6 and db.get_produit(p1["id"])["stock"] == avant - 10, num6)

# stock insuffisant -> aucune ecriture partielle
avant = db.get_produit(p1["id"])["stock"]
nb_ventes_avant = len(db.get_ventes(limit=9999))
ok7, m7, _ = db.create_vente("Test", [(p2["id"], 1, 22000), (p1["id"], 99999, 12000)])
check("vente refusee si stock insuffisant", not ok7, m7)
check("ATOMICITE: stock intact", db.get_produit(p1["id"])["stock"] == avant)
check("ATOMICITE: aucune vente creee", len(db.get_ventes(limit=9999)) == nb_ventes_avant)
check("remise > total refusee", not db.create_vente("T", [(p1["id"], 1, 100)], remise=9999)[0])
check("panier vide refuse", not db.create_vente("T", [])[0])

print("\n=== ANNULATION ===")
avant = db.get_produit(p1["id"])["stock"]
r, m = db.annuler_vente(vid)
check("annulation ok", r, m)
check("stock restaure", db.get_produit(p1["id"])["stock"] == avant + 2)
check("double annulation refusee", not db.annuler_vente(vid)[0])
check("vente annulee exclue du CA",
      all(v["statut_v"] != "annulee" for v in db.get_ventes(inclure_annulees=False)))

print("\n=== SUPPRESSIONS PROTEGEES ===")
r, m = db.delete_produit(p1["id"])
check("produit vendu = desactive", r and "désactivé" in m, m)
check("produit inactif masque par defaut",
      p1["id"] not in [x["id"] for x in db.get_produits(inclure_inactifs=False)])
check("historique vente preserve", db.get_vente_details(vid6)[1][0]["produit_nom"] != "")
check("categorie utilisee non supprimable", not db.delete_categorie(cat)[0])
db.reactiver_produit(p1["id"])
check("reactivation", db.get_produit(p1["id"])["actif"] == 1)

print("\n=== STATS & RAPPORTS ===")
s = db.get_dashboard_stats()
for cle in ("total_produits","valeur_stock","ventes_mois","marge_mois","nb_alertes",
            "alertes_stock","top_produits","ventes_7j","dernieres_ventes"):
    check(f"stat '{cle}' presente", cle in s)
from datetime import datetime
today = datetime.now().strftime("%Y-%m-%d")
rap = db.rapport_ventes("2000-01-01", today)
check("rapport CA > 0", rap["resume"]["ca"] > 0, rap["resume"]["ca"])
check("rapport marge calculee", rap["resume"]["marge"] != 0)
check("rapport par produit", len(rap["par_produit"]) > 0)
check("rapport par paiement", len(rap["par_paiement"]) > 0)
rs = db.rapport_stock()
check("valorisation par categorie", len(rs["par_categorie"]) > 0)
check("stock dormant", isinstance(rs["dormants"], list))

print("\n=== EXPORTS / IMPORT / SAUVEGARDE ===")
f1 = db.exporter_produits(); f2 = db.exporter_ventes(); f3 = db.exporter_mouvements()
check("export produits", os.path.getsize(f1) > 100)
check("export ventes", os.path.getsize(f2) > 50)
check("export mouvements", os.path.getsize(f3) > 50)
ok8, m8, aj, mj = db.importer_produits_csv(f1)
check("reimport = mise a jour (pas de doublon)", ok8 and aj == 0 and mj > 0, m8)
csv_new = os.path.join(TMP, "new.csv")
open(csv_new, "w", encoding="utf-8-sig").write(
    "Référence;Nom;Catégorie;Marque;Stock;Stock mini;Prix achat;Prix vente;Emplacement\n"
    "NEW-001;Filtre a huile;Filtres;Bosch;25;5;2500;4000;Rayon B2\n")
ok9, m9, aj9, _ = db.importer_produits_csv(csv_new)
check("import nouveau produit", ok9 and aj9 == 1, m9)
np = db.trouver_produit("NEW-001")
check("donnees importees correctes", np and np["stock"] == 25 and np["prix_vente"] == 4000)

bak = db.sauvegarder_base()
check("sauvegarde creee", os.path.exists(bak) and os.path.getsize(bak) > 1000)
check("liste sauvegardes", len(db.lister_sauvegardes()) >= 1)
nb_avant = len(db.get_produits())
db.add_produit("TMP-999", "A supprimer par restauration")
r, m = db.restaurer_base(bak)
check("restauration", r, m)
check("etat restaure", len(db.get_produits()) == nb_avant, len(db.get_produits()))

print("\n=== PARAMETRES & JOURNAL ===")
db.set_parametre("devise", "EUR")
check("parametre modifie", db.get_devise() == "EUR")
db.set_parametre("devise", "F CFA")
check("journal alimente", len(db.get_journal()) > 5)

print("\n=== FACTURES HTML ===")
import factures
html, err = factures.generer_facture_html(vid6)
check("facture A4 generee", html and "FACTURE" in html and "NET À PAYER" in html, err)
html2, _ = factures.generer_facture_html(vid)
check("filigrane vente annulee", "VENTE ANNULÉE" in html2)
check("injection HTML echappee", "<script>" not in factures._echapper("<script>"))
ht, _ = factures.generer_facture_html(vid6, format_ticket=True)
check("ticket 80mm", "80mm" in ht)
check("facture inexistante geree", factures.generer_facture_html(999999)[1] is not None)
p_rap = factures.generer_rapport_html("Test", "2000-01-01", today, rap, ouvrir=False)
check("rapport HTML", os.path.getsize(p_rap) > 1000)
p_rea = factures.generer_liste_reappro(ouvrir=False)
check("bon reappro HTML", os.path.getsize(p_rea) > 500)

print(f"\n{'='*46}\nRESULTAT : {ok} reussis, {fail} echoues\n{'='*46}")
shutil.rmtree(TMP, ignore_errors=True)
if __name__ == "__main__":
    sys.exit(1 if fail else 0)

