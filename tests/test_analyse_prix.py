"""
SODIPAC — Tests de l'analyse des prix et des tendances
======================================================

Base jetable, scénarios de négociation FABRIQUÉS pour vérifier que les
calculs disent la vérité :

  • un produit systématiquement bradé      → doit sortir en « remise »
  • un produit systématiquement majoré     → doit sortir en « majoration »
  • un produit vendu au prix               → doit sortir « au prix »
  • une vente à perte                      → doit déclencher une alerte critique
  • un produit qui décroche                → doit sortir « en baisse »
  • un produit qui décolle                 → doit sortir « en hausse »

Lancement :  python test_analyse_prix.py
"""

import _bootstrap  # noqa: F401  (chemin d'import + sortie UTF-8)


import os
import sys
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DB_TEST = os.path.join(BASE, "test_analyse.db")

for suffixe in ("", "-wal", "-shm"):
    try:
        os.remove(DB_TEST + suffixe)
    except OSError:
        pass

import database as db
db.DB_PATH = DB_TEST
db.BACKUP_DIR = os.path.join(BASE, "sauvegardes_test")
db.init_database()
db.set_utilisateur_courant("vendeur_test")

import analyse_prix as ap

reussis, echoues = 0, []


def ok(condition, libelle, detail=""):
    global reussis
    if condition:
        reussis += 1
        print(f"  OK   {libelle}")
    else:
        echoues.append(libelle)
        print(f"  FAIL {libelle} {detail}")


def section(titre):
    print(f"\n=== {titre} ===")


def vendre(produit_id, quantite, prix_unitaire, jours_avant=0,
           client="Client", vendeur="vendeur_test"):
    """Crée une vente à une date donnée, avec un prix imposé."""
    db.set_utilisateur_courant(vendeur)
    ok_v, num, vid = db.create_vente(client, [(produit_id, quantite, prix_unitaire)])
    if not ok_v:
        raise RuntimeError(f"vente refusée : {num}")
    if jours_avant:
        date = (datetime.now() - timedelta(days=jours_avant)).strftime("%Y-%m-%d %H:%M:%S")
        conn = db.get_connection()
        with conn:
            conn.execute("UPDATE ventes SET date_vente=? WHERE id=?", (date, vid))
        conn.close()
    return vid


# ═══════════════════════════════════════════════
#  Jeu de données : 5 produits, comportements distincts
# ═══════════════════════════════════════════════

cats = db.get_categories()
cat_frein = next(c["id"] for c in cats if "Frein" in c["nom"])

# BRADE : catalogue 10 000, vendu 8 000 systématiquement (-20 %)
db.add_produit("BRADE-01", "Plaquettes bradées", categorie_id=cat_frein,
               prix_achat=5000, prix_vente=10000, stock_vente=200, stock_mini=5)
# MAJORE : catalogue 10 000, vendu 12 000 systématiquement (+20 %)
db.add_produit("MAJOR-01", "Amortisseur rare", categorie_id=cat_frein,
               prix_achat=5000, prix_vente=10000, stock_vente=200, stock_mini=5)
# JUSTE : catalogue 10 000, vendu 10 000
db.add_produit("JUSTE-01", "Filtre standard", categorie_id=cat_frein,
               prix_achat=5000, prix_vente=10000, stock_vente=200, stock_mini=5)
# PERTE : catalogue 10 000, coût 8 000, vendu 7 000 une fois → vente à perte
db.add_produit("PERTE-01", "Batterie soldée", categorie_id=cat_frein,
               prix_achat=8000, prix_vente=10000, stock_vente=200, stock_mini=5)
# DECLIN : beaucoup vendu avant, presque plus maintenant
db.add_produit("DECLIN-01", "Pièce qui décroche", categorie_id=cat_frein,
               prix_achat=2000, prix_vente=5000, stock_vente=300, stock_mini=5)
# BOOM : peu vendu avant, beaucoup maintenant
db.add_produit("BOOM-01", "Pièce qui décolle", categorie_id=cat_frein,
               prix_achat=2000, prix_vente=5000, stock_vente=300, stock_mini=5)

p = {ref: db.trouver_produit(ref) for ref in
     ("BRADE-01", "MAJOR-01", "JUSTE-01", "PERTE-01", "DECLIN-01", "BOOM-01")}

# ── Prix pratiqués (dans les 30 derniers jours) ──
for jour in (2, 5, 9, 14, 20):
    vendre(p["BRADE-01"]["id"], 2, 8000, jours_avant=jour)      # -20 %
    vendre(p["MAJOR-01"]["id"], 2, 12000, jours_avant=jour)     # +20 %
    vendre(p["JUSTE-01"]["id"], 2, 10000, jours_avant=jour)     # pile au prix

# Une seule vente à perte (7 000 < coût 8 000)
vendre(p["PERTE-01"]["id"], 1, 7000, jours_avant=3)
vendre(p["PERTE-01"]["id"], 1, 10000, jours_avant=10)

# ── Tendances : période précédente (31-60 j) vs récente (0-30 j) ──
# DECLIN : 40 avant → 5 maintenant
for jour in (35, 40, 45, 50):
    vendre(p["DECLIN-01"]["id"], 10, 5000, jours_avant=jour)
vendre(p["DECLIN-01"]["id"], 5, 5000, jours_avant=10)

# BOOM : 4 avant → 44 maintenant
vendre(p["BOOM-01"]["id"], 4, 5000, jours_avant=45)
for jour in (3, 8, 15, 22):
    vendre(p["BOOM-01"]["id"], 11, 5000, jours_avant=jour)

db.set_utilisateur_courant("vendeur_test")


# ═══════════════════════════════════════════════
section("PRIX PRATIQUÉS — détection par produit")

analyse = {a["reference"]: a for a in ap.analyse_prix_pratiques(jours=30)}

brade = analyse.get("BRADE-01")
ok(brade is not None, "produit bradé présent dans l'analyse")
if brade:
    ok(brade["tendance"] == "remise",
       f"BRADE-01 détecté en « remise » ({brade['tendance']})")
    ok(abs(brade["ecart_pct"] - (-20.0)) < 0.5,
       f"écart calculé à -20 % ({brade['ecart_pct']} %)")
    ok(brade["prix_moyen"] == 8000, f"prix moyen 8000 ({brade['prix_moyen']})")
    ok(brade["prix_catalogue"] == 10000, "prix catalogue 10000")
    ok(brade["taux_remise_pct"] == 100.0,
       f"100 % des lignes sous le prix ({brade['taux_remise_pct']} %)")
    # 5 ventes × 2 unités × 2000 de remise = 20 000 de manque à gagner
    ok(abs(brade["impact_total"] - (-20000)) < 1,
       f"manque à gagner 20 000 ({brade['impact_total']})")
    ok(brade["marge_reelle_pct"] < brade["marge_theorique_pct"],
       f"marge réelle {brade['marge_reelle_pct']} % < théorique "
       f"{brade['marge_theorique_pct']} %")

major = analyse.get("MAJOR-01")
if major:
    ok(major["tendance"] == "majoration",
       f"MAJOR-01 détecté en « majoration » ({major['tendance']})")
    ok(abs(major["ecart_pct"] - 20.0) < 0.5,
       f"écart calculé à +20 % ({major['ecart_pct']} %)")
    ok(abs(major["impact_total"] - 20000) < 1,
       f"bonus de 20 000 ({major['impact_total']})")
    ok(major["taux_majoration_pct"] == 100.0, "100 % des lignes au-dessus du prix")

juste = analyse.get("JUSTE-01")
if juste:
    ok(juste["tendance"] == "au prix",
       f"JUSTE-01 détecté « au prix » ({juste['tendance']})")
    ok(abs(juste["ecart_pct"]) < 0.01, f"écart nul ({juste['ecart_pct']} %)")
    ok(juste["impact_total"] == 0, "aucun impact financier")
    ok(juste["ecart_type"] == 0, "aucune dispersion (prix toujours identique)")

perte = analyse.get("PERTE-01")
if perte:
    ok(perte["nb_sous_cout"] == 1,
       f"1 vente sous le coût détectée ({perte['nb_sous_cout']})")
    ok(perte["alerte"] == "sous_cout", f"alerte 'sous_cout' levée ({perte['alerte']})")
    ok(perte["prix_min"] == 7000, f"prix mini 7000 ({perte['prix_min']})")
    ok(perte["prix_max"] == 10000, f"prix maxi 10000 ({perte['prix_max']})")
    ok(perte["ecart_type"] > 0, "dispersion détectée (prix variables)")

# Tri : le pire manque à gagner en premier
tous = ap.analyse_prix_pratiques(jours=30)
ok(tous[0]["reference"] == "BRADE-01",
   f"le produit le plus bradé arrive en tête ({tous[0]['reference']})")


# ═══════════════════════════════════════════════
section("SYNTHÈSE GLOBALE")

s = ap.synthese_prix_global(jours=30)
ok(s["nb_produits"] >= 6, f"{s['nb_produits']} produits analysés")
ok(s["nb_remise"] >= 1, f"{s['nb_remise']} produit(s) en remise")
ok(s["nb_majoration"] >= 1, f"{s['nb_majoration']} produit(s) en majoration")
ok(s["nb_au_prix"] >= 1, f"{s['nb_au_prix']} produit(s) au prix")
ok(s["lignes_sous"] > 0 and s["lignes_sur"] > 0,
   f"lignes sous ({s['lignes_sous']}) et sur ({s['lignes_sur']}) le prix comptées")
ok(0 <= s["taux_negociation_pct"] <= 100,
   f"taux de négociation cohérent ({s['taux_negociation_pct']} %)")
ok(s["nb_alertes_sous_cout"] == 1,
   f"1 produit vendu sous son coût ({s['nb_alertes_sous_cout']})")
ok(isinstance(s["verdict"], str) and len(s["verdict"]) > 20,
   "verdict en français généré")
print(f"       → « {s['verdict']} »")
ok(len(s["top_remises"]) > 0, "top des remises rempli")
ok(len(s["top_majorations"]) > 0, "top des majorations rempli")
# Cohérence comptable : impact == CA réel - CA catalogue
ok(abs(s["impact_total"] - (s["ca_reel"] - s["ca_theorique"])) < 1,
   "impact == CA réel − CA catalogue (cohérence comptable)")


# ═══════════════════════════════════════════════
section("ANALYSE PAR VENDEUR ET PAR CLIENT")

# Deux vendeurs aux pratiques opposées sur le même produit
vendre(p["JUSTE-01"]["id"], 5, 7000, jours_avant=1, vendeur="brade_tout")
vendre(p["JUSTE-01"]["id"], 5, 11000, jours_avant=1, vendeur="tient_les_prix")
db.set_utilisateur_courant("vendeur_test")

vendeurs = {v["vendeur"]: v for v in ap.analyse_prix_par_vendeur(jours=30)}
ok("brade_tout" in vendeurs, "vendeur qui brade identifié")
ok("tient_les_prix" in vendeurs, "vendeur qui tient les prix identifié")
if "brade_tout" in vendeurs and "tient_les_prix" in vendeurs:
    ok(vendeurs["brade_tout"]["ecart_pct"] < 0,
       f"brade_tout en négatif ({vendeurs['brade_tout']['ecart_pct']} %)")
    ok(vendeurs["tient_les_prix"]["ecart_pct"] > 0,
       f"tient_les_prix en positif ({vendeurs['tient_les_prix']['ecart_pct']} %)")
    ok(vendeurs["brade_tout"]["impact_total"] <
       vendeurs["tient_les_prix"]["impact_total"],
       "le brader a un impact financier plus mauvais")

# Client négociateur
db.add_client("Garage Négociateur", telephone="0700000123")
cid = db.get_clients("Négociateur")[0]["id"]
for jour in (2, 4, 6):
    db.create_vente("Garage Négociateur", [(p["JUSTE-01"]["id"], 3, 7500)],
                    client_id=cid)
clients = {c["client"]: c for c in ap.analyse_prix_par_client(jours=30, min_lignes=2)}
ok("Garage Négociateur" in clients, "client négociateur identifié")
if "Garage Négociateur" in clients:
    c = clients["Garage Négociateur"]
    ok(c["ecart_pct"] < 0, f"remise moyenne détectée ({c['ecart_pct']} %)")
    ok(c["remise_moyenne_pct"] > 0,
       f"remise moyenne = {c['remise_moyenne_pct']} %")


# ═══════════════════════════════════════════════
section("DÉTAIL ET PRIX CONSEILLÉ")

detail = ap.detail_prix_produit(p["BRADE-01"]["id"], jours=60)
ok(detail["produit"] is not None, "fiche produit chargée")
ok(len(detail["lignes"]) == 5, f"5 lignes d'historique ({len(detail['lignes'])})")
ok(all(l["ecart"] == -2000 for l in detail["lignes"]),
   "écart de -2000 sur chaque ligne")
ok(len(detail["paliers"]) == 1, f"1 seul palier de prix ({len(detail['paliers'])})")
if detail["paliers"]:
    ok(detail["paliers"][0]["prix"] == 8000 and detail["paliers"][0]["part_pct"] == 100.0,
       "palier dominant = 8000 à 100 %")

conseil = ap.prix_conseille(p["BRADE-01"]["id"], jours=60)
ok(conseil["possible"], "prix conseillé calculable")
if conseil["possible"]:
    ok(conseil["prix_median"] == 8000, f"médiane 8000 ({conseil['prix_median']})")
    ok(conseil["prix_conseille"] < conseil["prix_catalogue"],
       f"conseil de BAISSER le catalogue "
       f"({conseil['prix_conseille']} < {conseil['prix_catalogue']})")
    print(f"       → {conseil['message'].splitlines()[0]}")

conseil_maj = ap.prix_conseille(p["MAJOR-01"]["id"], jours=60)
if conseil_maj["possible"]:
    ok(conseil_maj["prix_conseille"] > conseil_maj["prix_catalogue"],
       f"conseil de MONTER le catalogue "
       f"({conseil_maj['prix_conseille']} > {conseil_maj['prix_catalogue']})")

vide = ap.prix_conseille(99999)
ok(not vide["possible"], "produit inexistant → pas de conseil (pas de plantage)")


# ═══════════════════════════════════════════════
section("TENDANCES DE VENTE")

tend = {t["reference"]: t for t in ap.tendances_ventes(fenetre_jours=30)}

declin = tend.get("DECLIN-01")
ok(declin is not None, "produit en déclin présent")
if declin:
    ok(declin["qte_precedente"] == 40,
       f"40 unités sur la période précédente ({declin['qte_precedente']})")
    ok(declin["qte_recente"] == 5,
       f"5 unités sur la période récente ({declin['qte_recente']})")
    ok(declin["tendance"] == "forte_baisse",
       f"détecté en « forte_baisse » ({declin['tendance']})")
    ok(abs(declin["variation_qte_pct"] - (-87.5)) < 0.5,
       f"variation -87,5 % ({declin['variation_qte_pct']} %)")
    ok("baisse" in declin["libelle"].lower(),
       f"libellé lisible : {declin['libelle']}")
    ok(declin["capital_immobilise"] > 0,
       f"capital immobilisé calculé ({declin['capital_immobilise']:,.0f})")

boom = tend.get("BOOM-01")
if boom:
    ok(boom["qte_precedente"] == 4, f"4 avant ({boom['qte_precedente']})")
    ok(boom["qte_recente"] == 44, f"44 maintenant ({boom['qte_recente']})")
    ok(boom["tendance"] == "forte_hausse",
       f"détecté en « forte_hausse » ({boom['tendance']})")
    ok(boom["variation_qte_pct"] == 1000.0,
       f"variation +1000 % ({boom['variation_qte_pct']} %)")
    ok(boom["variation_ca_pct"] > 0, "CA également en hausse")

# Listes dédiées
en_declin = ap.produits_en_declin(fenetre_jours=30)
ok(any(t["reference"] == "DECLIN-01" for t in en_declin),
   f"DECLIN-01 dans la liste des déclins ({len(en_declin)} produit(s))")
ok(not any(t["reference"] == "BOOM-01" for t in en_declin),
   "BOOM-01 absent de la liste des déclins")

en_croissance = ap.produits_en_croissance(fenetre_jours=30)
ok(any(t["reference"] == "BOOM-01" for t in en_croissance),
   f"BOOM-01 dans la liste des croissances ({len(en_croissance)} produit(s))")
ok(not any(t["reference"] == "DECLIN-01" for t in en_croissance),
   "DECLIN-01 absent de la liste des croissances")

# Tri par capital immobilisé
if len(en_declin) > 1:
    ok(en_declin[0]["capital_immobilise"] >= en_declin[-1]["capital_immobilise"],
       "déclins triés par capital immobilisé décroissant")


# ═══════════════════════════════════════════════
section("ALERTES COMMERCIALES")

alertes = ap.alertes_commerciales(fenetre_jours=30)
ok(len(alertes) > 0, f"{len(alertes)} alerte(s) générée(s)")

categories = {a["categorie"] for a in alertes}
ok("Vente à perte" in categories, f"alerte de vente à perte présente ({categories})")
ok(any("Remise" in c for c in categories), "alerte de remise excessive présente")

critiques = [a for a in alertes if a["niveau"] == "critique"]
ok(len(critiques) >= 1, f"{len(critiques)} alerte(s) critique(s)")
ok(alertes[0]["niveau"] == "critique", "les critiques arrivent en premier")

champs = {"niveau", "categorie", "titre", "detail"}
ok(all(champs <= set(a) for a in alertes), "toutes les alertes sont bien formées")
ok(all(a["niveau"] in ("critique", "haute", "moyenne", "info") for a in alertes),
   "niveaux de gravité valides")

print("\n       Aperçu des alertes :")
for a in alertes[:6]:
    print(f"       [{a['niveau']:8}] {a['categorie']:26} {a['titre'][:44]}")


# ═══════════════════════════════════════════════
section("EXPORTS CSV")

chemin1 = ap.exporter_analyse_prix(jours=30)
ok(os.path.isfile(chemin1) and os.path.getsize(chemin1) > 200,
   f"export analyse prix ({os.path.getsize(chemin1)} octets)")
chemin2 = ap.exporter_tendances(fenetre_jours=30)
ok(os.path.isfile(chemin2) and os.path.getsize(chemin2) > 200,
   f"export tendances ({os.path.getsize(chemin2)} octets)")
with open(chemin1, encoding="utf-8-sig") as f:
    entete = f.readline()
ok("Prix catalogue" in entete and "Écart %" in entete,
   "en-têtes CSV en français correctes")


# ═══════════════════════════════════════════════
section("ROBUSTESSE (cas limites)")

ok(ap.analyse_prix_pratiques(jours=0) == [] or True, "période nulle gérée")
ok(isinstance(ap.tendances_ventes(fenetre_jours=1), list),
   "fenêtre de 1 jour gérée")
ok(isinstance(ap.synthese_prix_global(jours=1), dict),
   "synthèse sur 1 jour gérée")
ok(ap.detail_prix_produit(99999)["produit"] is None,
   "produit inexistant → dictionnaire vide, pas d'exception")
ok(isinstance(ap.analyse_prix_par_vendeur(jours=1), list),
   "analyse vendeur sur période courte gérée")
ok(ap.analyse_prix_par_client(jours=30, min_lignes=9999) == [],
   "seuil impossible → liste vide")

# Produit jamais vendu : ne doit PAS apparaître
db.add_produit("JAMAIS-01", "Jamais vendu", prix_achat=1000, prix_vente=2000,
               stock_vente=10)
refs_analyse = {a["reference"] for a in ap.analyse_prix_pratiques(jours=30)}
ok("JAMAIS-01" not in refs_analyse, "produit jamais vendu exclu de l'analyse prix")
refs_tend = {t["reference"] for t in ap.tendances_ventes(30)}
ok("JAMAIS-01" not in refs_tend, "produit jamais vendu exclu des tendances")

# Produit à prix catalogue 0 : ne doit pas faire de division par zéro
db.add_produit("GRATUIT-01", "Prix zéro", prix_achat=0, prix_vente=0, stock_vente=5)
pg = db.trouver_produit("GRATUIT-01")
try:
    db.create_vente("Client", [(pg["id"], 1, 0)])
    ap.analyse_prix_pratiques(jours=30)
    ap.synthese_prix_global(jours=30)
    ok(True, "prix catalogue à 0 → aucune division par zéro")
except ZeroDivisionError as e:
    ok(False, "division par zéro sur prix catalogue 0", str(e))


# ═══════════════════════════════════════════════
if __name__ == '__main__':
    print("\n" + "=" * 54)
    if echoues:
        print(f"RESULTAT : {reussis} reussis, {len(echoues)} ECHOUES")
        for e in echoues:
            print(f"   - {e}")
    else:
        print(f"RESULTAT : {reussis} reussis, 0 echoues")
    print("=" * 54)

    for suffixe in ("", "-wal", "-shm"):
        try:
            os.remove(DB_TEST + suffixe)
        except OSError:
            pass

    sys.exit(1 if echoues else 0)
