"""
SODIPAC — Tests de la couche métier v3
======================================

Teste sur une base JETABLE (test_v3.db) :
  CUMP, multi-dépôt, transferts, créances/règlements, plafond crédit,
  achats/réception, inventaire, retours, compatibilité véhicule,
  références croisées, prévision de rupture, classement ABC.

Lancement :  python test_v3.py
"""

import os
import sys
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DB_TEST = os.path.join(BASE, "test_v3.db")

# Base jetable AVANT tout import
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


# ═══════════════════════════════════════════════
section("DÉPÔTS")

depots = m3.get_depots()
ok(len(depots) == 2, f"2 dépôts par défaut créés ({len(depots)})")
codes = {d["code"] for d in depots}
ok(codes == {"BOU", "RES"}, f"codes BOU + RES ({codes})")

defaut = m3.get_depot_defaut()
ok(defaut and defaut["code"] == "BOU", "dépôt par défaut = BOU")

s, msg = m3.add_depot("MAG", "Magasin Yopougon", "magasin", autorise_vente=True)
ok(s, f"création 3e dépôt : {msg}")
s, msg = m3.add_depot("MAG", "Doublon", "magasin")
ok(not s, f"code dépôt en doublon refusé : {msg}")
s, msg = m3.add_depot("", "Sans code")
ok(not s, "dépôt sans code refusé")

id_bou = next(d["id"] for d in m3.get_depots() if d["code"] == "BOU")
id_res = next(d["id"] for d in m3.get_depots() if d["code"] == "RES")
id_mag = next(d["id"] for d in m3.get_depots() if d["code"] == "MAG")

# On ne doit pas pouvoir supprimer le dernier dépôt de vente
s, msg = m3.update_depot(id_bou, actif=0)
ok(s, "désactivation BOU possible (MAG reste dépôt de vente)")
m3.update_depot(id_bou, actif=1)


# ═══════════════════════════════════════════════
section("CUMP (COÛT MOYEN PONDÉRÉ)")

ok(m3.calculer_cump(0, 0, 10, 1000) == 1000, "stock vide → CUMP = prix d'entrée")
ok(m3.calculer_cump(10, 1000, 10, 2000) == 1500, "10@1000 + 10@2000 → CUMP 1500")
ok(abs(m3.calculer_cump(10, 1000, 5, 1500) - 1166.6666666666667) < 0.01,
   "10@1000 + 5@1500 → CUMP 1166,67")
ok(m3.calculer_cump(10, 1000, 0, 5000) == 1000, "entrée nulle → CUMP inchangé")
ok(m3.calculer_cump(-5, 1000, 10, 2000) == 2000, "stock négatif traité comme 0")

# Produit réel : le bug v2 était d'écraser prix_achat
s, msg = db.add_produit("CUMP-01", "Filtre à huile test", prix_achat=1000,
                        prix_vente=2000, stock_vente=10)
ok(s, f"produit créé : {msg}")
p = db.trouver_produit("CUMP-01")
ok(abs(p["cump"] - 1000) < 0.01, f"CUMP initial = 1000 ({p['cump']})")

# Entrée de 5 à 1500 → CUMP doit devenir 1166,67 et PAS 1500
s, msg = db.add_mouvement(p["id"], "entree", 5, prix_unitaire=1500, cible="vente")
ok(s, f"entrée 5@1500 : {msg}")
p = db.trouver_produit("CUMP-01")
ok(abs(p["cump"] - 1166.67) < 1,
   f"CUMP pondéré = 1166,67 (et non 1500) — obtenu {p['cump']}", f"cump={p['cump']}")
ok(p["stock"] == 15, f"stock total 15 ({p['stock']})")

hist = m3.get_historique_prix(p["id"])
ok(len(hist) >= 1, f"historique de prix alimenté ({len(hist)} lignes)")


# ═══════════════════════════════════════════════
section("MULTI-DÉPÔT & TRANSFERTS")

par_depot = m3.get_stock_par_depot(p["id"])
total_depots = sum(d["quantite"] for d in par_depot)
ok(total_depots == p["stock"],
   f"somme stock_depot ({total_depots}) == produits.stock ({p['stock']})")

s, msg = m3.transferer(p["id"], id_bou, id_mag, 5, "test transfert")
ok(s, f"transfert BOU→MAG 5u : {msg}")
apres = {d["code"]: d["quantite"] for d in m3.get_stock_par_depot(p["id"])}
ok(apres["MAG"] == 5, f"MAG a 5u ({apres.get('MAG')})")
ok(apres["BOU"] == 10, f"BOU a 10u ({apres.get('BOU')})")

s, msg = m3.transferer(p["id"], id_bou, id_mag, 9999)
ok(not s, f"transfert > stock refusé : {msg}")
s, msg = m3.transferer(p["id"], id_bou, id_bou, 1)
ok(not s, "transfert vers le même dépôt refusé")
s, msg = m3.transferer(p["id"], id_bou, id_mag, 0)
ok(not s, "transfert de 0 refusé")
s, msg = m3.transferer(p["id"], id_bou, id_mag, -5)
ok(not s, "transfert négatif refusé")

# La réserve n'autorise pas la vente → stock_vente ne doit compter que BOU+MAG
m3.transferer(p["id"], id_bou, id_res, 3)
p = db.trouver_produit("CUMP-01")
etat = {d["code"]: d["quantite"] for d in m3.get_stock_par_depot(p["id"])}
ok(p["stock_vente"] == etat["BOU"] + etat["MAG"],
   f"stock_vente = BOU+MAG ({p['stock_vente']} vs {etat['BOU']}+{etat['MAG']})")
ok(p["stock_reserve"] == etat["RES"],
   f"stock_reserve = RES ({p['stock_reserve']} vs {etat['RES']})")
ok(p["stock"] == sum(etat.values()), "stock total cohérent")


# ═══════════════════════════════════════════════
section("CRÉANCES & PLAFOND DE CRÉDIT")

db.add_client("Garage Koné", telephone="0700000001")
clients = db.get_clients("Koné")
cid = clients[0]["id"]

# Sans plafond → crédit refusé
s, msg, vid = db.create_vente("Garage Koné", [(p["id"], 1, 5000)],
                              mode_paiement="Crédit", montant_paye=0, client_id=cid)
ok(not s, f"crédit sans plafond refusé : {msg}")

# Crédit sans client → refusé
s, msg, vid = db.create_vente("Passant", [(p["id"], 1, 5000)],
                              mode_paiement="Crédit", montant_paye=0)
ok(not s, f"crédit sans client identifié refusé : {msg}")

# On donne un plafond de 20 000
conn = db.get_connection()
with conn:
    conn.execute("UPDATE clients SET plafond_credit=20000 WHERE id=?", (cid,))
db.close_connection()  # reset _conn_persistante — le backup restore la ferme

s, msg, vid = db.create_vente("Garage Koné", [(p["id"], 2, 5000)],
                              mode_paiement="Crédit", montant_paye=0, client_id=cid)
ok(s, f"crédit 10 000 sous plafond 20 000 accepté : {msg}")

creances = m3.get_creances(client_id=cid)
ok(len(creances) == 1, f"1 créance visible ({len(creances)})")
ok(abs(creances[0]["reste_du"] - 10000) < 0.01,
   f"reste dû = 10 000 ({creances[0]['reste_du']})")
ok(creances[0]["date_echeance"], "échéance calculée automatiquement")

ok(abs(m3.solde_client(cid) - 10000) < 0.01, "solde client = 10 000")

# Dépassement de plafond
s, msg, vid2 = db.create_vente("Garage Koné", [(p["id"], 3, 5000)],
                               mode_paiement="Crédit", montant_paye=0, client_id=cid)
ok(not s, f"crédit qui dépasse le plafond refusé : {msg}")

# Acompte partiel
s, msg = m3.encaisser_creance(creances[0]["vente_id"], 4000, "Orange Money")
ok(s, f"acompte 4 000 : {msg}")
reste = m3.get_creances(client_id=cid)[0]["reste_du"]
ok(abs(reste - 6000) < 0.01, f"reste dû = 6 000 ({reste})")

# Trop-perçu refusé
s, msg = m3.encaisser_creance(creances[0]["vente_id"], 99999)
ok(not s, f"encaissement > reste dû refusé : {msg}")
s, msg = m3.encaisser_creance(creances[0]["vente_id"], 0)
ok(not s, "encaissement de 0 refusé")
s, msg = m3.encaisser_creance(creances[0]["vente_id"], -500)
ok(not s, "encaissement négatif refusé")

# Solde complet → la créance disparaît
s, msg = m3.encaisser_creance(creances[0]["vente_id"], 6000, "Espèces")
ok(s, f"solde final : {msg}")
ok(len(m3.get_creances(client_id=cid)) == 0, "créance soldée → disparaît de la liste")
ok(m3.solde_client(cid) == 0, "solde client remis à 0")

# La vente au comptant ne crée PAS de créance
s, msg, vid3 = db.create_vente("Client comptant", [(p["id"], 1, 3000)],
                               mode_paiement="Espèces")
ok(s, "vente comptant OK")
ok(not any(c["vente_id"] == vid3 for c in m3.get_creances()),
   "vente comptant → aucune créance")

agg = m3.get_creances_par_client()
ok(isinstance(agg, list), "vue agrégée par client fonctionnelle")


# ═══════════════════════════════════════════════
section("ACHATS / COMMANDES FOURNISSEUR")

db.add_fournisseur("Import Auto CI", telephone="0500000001")
fid = db.get_fournisseurs("Import Auto")[0]["id"]

s, msg, cid_cmd = m3.creer_commande(
    fid, [(p["id"], "", 20, 900)], depot_id=id_res, frais=5000, notes="test")
ok(s, f"commande créée : {msg}")

cmds = m3.get_commandes()
ok(len(cmds) == 1, f"1 commande listée ({len(cmds)})")
ok(cmds[0]["statut"] == "brouillon", f"statut brouillon ({cmds[0]['statut']})")
ok(abs(cmds[0]["total"] - (20 * 900 + 5000)) < 0.01,
   f"total = 23 000 avec frais ({cmds[0]['total']})")

s, msg, _ = m3.creer_commande(fid, [])
ok(not s, "commande vide refusée")
s, msg, _ = m3.creer_commande(fid, [(p["id"], "", 0, 900)])
ok(not s, "commande avec quantité 0 refusée")
s, msg, _ = m3.creer_commande(fid, [(p["id"], "", 5, 900)], remise=999999)
ok(not s, "remise > total refusée")

s, msg = m3.envoyer_commande(cid_cmd)
ok(s, f"commande envoyée : {msg}")
s, msg = m3.envoyer_commande(cid_cmd)
ok(not s, "double envoi refusé")

en_route = m3.articles_en_route()
ok(any(a["produit_id"] == p["id"] and a["qte_attendue"] == 20 for a in en_route),
   f"20u en route détectées ({en_route})")

# Réception PARTIELLE : 8 sur 20
lignes = m3.get_commande_details(cid_cmd)
avant = db.trouver_produit("CUMP-01")
cump_avant = avant["cump"]
s, msg = m3.receptionner_commande(cid_cmd, {lignes[0]["id"]: 8})
ok(s, f"réception partielle 8/20 : {msg}")
ok(m3.get_commandes()[0]["statut"] == "partielle", "statut passé à 'partielle'")

apres = db.trouver_produit("CUMP-01")
ok(apres["stock"] == avant["stock"] + 8, f"stock +8 ({avant['stock']}→{apres['stock']})")
ok(apres["cump"] < cump_avant,
   f"CUMP baissé après entrée à 900 ({cump_avant}→{apres['cump']})")
depot_res = {d["code"]: d["quantite"] for d in m3.get_stock_par_depot(p["id"])}["RES"]
ok(depot_res >= 8, f"réception allée dans le dépôt RES ({depot_res}u)")

# Réception du reliquat
s, msg = m3.receptionner_commande(cid_cmd)
ok(s, f"réception du reliquat : {msg}")
ok(m3.get_commandes()[0]["statut"] == "recue", "statut passé à 'recue'")
s, msg = m3.receptionner_commande(cid_cmd)
ok(not s, f"re-réception refusée : {msg}")
ok(not m3.articles_en_route(), "plus rien en route")

# Dette fournisseur
dettes = m3.get_dettes_fournisseur()
ok(len(dettes) == 1, f"1 dette fournisseur ({len(dettes)})")
ok(abs(dettes[0]["reste_a_payer"] - 23000) < 0.01,
   f"reste à payer 23 000 ({dettes[0]['reste_a_payer']})")
s, msg = m3.payer_fournisseur(cid_cmd, 10000, "Wave")
ok(s, f"paiement partiel : {msg}")
ok(abs(m3.get_dettes_fournisseur()[0]["reste_a_payer"] - 13000) < 0.01,
   "reste à payer 13 000")
s, msg = m3.payer_fournisseur(cid_cmd, 999999)
ok(not s, "paiement > dette refusé")

# Annulation d'une commande déjà reçue
s, msg = m3.annuler_commande(cid_cmd)
ok(not s, f"annulation d'une commande reçue refusée : {msg}")


# ═══════════════════════════════════════════════
section("INVENTAIRE PHYSIQUE")

s, msg, inv_id = m3.ouvrir_inventaire(depot_id=id_bou, notes="inventaire test")
ok(s, f"inventaire ouvert : {msg}")
s, msg, _ = m3.ouvrir_inventaire(depot_id=id_bou)
ok(not s, f"2e inventaire sur le même dépôt refusé : {msg}")

lignes_inv = m3.get_inventaire_lignes(inv_id)
ok(len(lignes_inv) >= 1, f"lignes d'inventaire créées ({len(lignes_inv)})")
theorique = next(l["stock_theorique"] for l in lignes_inv if l["produit_id"] == p["id"])

# Comptage avec un écart de -2 (vol)
s, msg = m3.saisir_comptage(inv_id, p["id"], theorique - 2, motif="Vol")
ok(s, f"comptage avec écart -2 : {msg}")
ligne = next(l for l in m3.get_inventaire_lignes(inv_id, True) if l["produit_id"] == p["id"])
ok(ligne["ecart"] == -2, f"écart = -2 ({ligne['ecart']})")
ok(ligne["valeur_ecart"] < 0, f"valeur d'écart négative ({ligne['valeur_ecart']})")

s, msg = m3.saisir_comptage(inv_id, p["id"], -5)
ok(not s, "comptage négatif refusé")
s, msg = m3.saisir_comptage(inv_id, 99999, 10)
ok(not s, "comptage d'un produit hors périmètre refusé")

stock_avant_cloture = db.trouver_produit("CUMP-01")["stock"]
s, msg = m3.cloturer_inventaire(inv_id, appliquer=True)
ok(s, f"clôture avec ajustement : {msg}")
stock_apres = db.trouver_produit("CUMP-01")["stock"]
ok(stock_apres == stock_avant_cloture - 2,
   f"stock ajusté -2 ({stock_avant_cloture}→{stock_apres})")
s, msg = m3.cloturer_inventaire(inv_id)
ok(not s, "re-clôture refusée")

invs = m3.get_inventaires()
ok(invs[0]["nb_ecarts"] == 1, f"1 écart enregistré ({invs[0]['nb_ecarts']})")
ok(invs[0]["statut"] == "cloture", "statut clôturé")

# Inventaire constaté SANS ajustement
s, msg, inv2 = m3.ouvrir_inventaire(depot_id=id_mag)
stock_ref = db.trouver_produit("CUMP-01")["stock"]
m3.saisir_comptage(inv2, p["id"], 0, motif="Casse")
s, msg = m3.cloturer_inventaire(inv2, appliquer=False)
ok(s, f"clôture sans ajustement : {msg}")
ok(db.trouver_produit("CUMP-01")["stock"] == stock_ref,
   "stock INCHANGÉ quand appliquer=False")


# ═══════════════════════════════════════════════
section("RETOURS / AVOIRS")

s, msg, vid_r = db.create_vente("Client retour", [(p["id"], 4, 3000)],
                               mode_paiement="Espèces")
ok(s, "vente de 4 articles pour test retour")
stock_avant_retour = db.trouver_produit("CUMP-01")["stock"]

# Retour partiel : 2 sur 4
s, msg, rid = m3.creer_retour(vid_r, [(p["id"], 2, 3000, True, "neuf")],
                             motif="Ne correspond pas")
ok(s, f"retour partiel 2/4 : {msg}")
ok(db.trouver_produit("CUMP-01")["stock"] == stock_avant_retour + 2,
   "stock +2 après retour remis en stock")

# On ne peut pas retourner plus que vendu
s, msg, _ = m3.creer_retour(vid_r, [(p["id"], 5, 3000)])
ok(not s, f"retour > quantité vendue refusé : {msg}")

# Le solde des 2 restants passe
s, msg, _ = m3.creer_retour(vid_r, [(p["id"], 2, 3000)])
ok(s, f"retour des 2 restants : {msg}")
s, msg, _ = m3.creer_retour(vid_r, [(p["id"], 1, 3000)])
ok(not s, "retour au-delà du total vendu refusé (cumul des retours pris en compte)")

# Retour NON remis en stock (pièce cassée)
s, msg, vid_c = db.create_vente("Client casse", [(p["id"], 1, 3000)])
stock_ref2 = db.trouver_produit("CUMP-01")["stock"]
s, msg, _ = m3.creer_retour(vid_c, [(p["id"], 1, 3000, False, "hs")],
                            motif="Pièce cassée")
ok(s, f"retour non remis en stock : {msg}")
ok(db.trouver_produit("CUMP-01")["stock"] == stock_ref2,
   "stock INCHANGÉ pour une pièce détruite")

s, msg, _ = m3.creer_retour(vid_r, [])
ok(not s, "retour vide refusé")
s, msg, _ = m3.creer_retour(99999, [(p["id"], 1, 3000)])
ok(not s, "retour sur vente inexistante refusé")

retours = m3.get_retours()
ok(len(retours) >= 3, f"retours listés ({len(retours)})")
ok(all(r["numero"] for r in retours), "tous les retours ont un numéro")


# ═══════════════════════════════════════════════
section("COMPATIBILITÉ VÉHICULE")

marques = m3.get_marques()
ok(len(marques) >= 10, f"référentiel marques peuplé ({len(marques)} marques)")
ok("Toyota" in marques and "Suzuki" in marques, "Toyota et Suzuki présents")

modeles_toyota = m3.get_modeles("Toyota")
ok(len(modeles_toyota) >= 5, f"modèles Toyota ({len(modeles_toyota)})")

yaris = [x for x in m3.get_modeles() if x["modele"] == "Yaris"]
ok(len(yaris) == 1, "Yaris trouvée dans le référentiel")
yaris_id = yaris[0]["id"]

s, msg = m3.lier_compatibilite(p["id"], yaris_id, "avant", "confirme")
ok(s, f"compatibilité liée : {msg}")
s, msg = m3.lier_compatibilite(p["id"], yaris_id, "avant", "confirme")
ok(not s, "compatibilité en doublon refusée")
s, msg = m3.lier_compatibilite(p["id"], yaris_id, "arriere", "certitude_invalide")
ok(not s, "certitude invalide refusée")

compats = m3.get_compatibilites_produit(p["id"])
ok(len(compats) == 1, f"1 compatibilité sur le produit ({len(compats)})")

# LA recherche qui fait vendre
trouve = m3.chercher_pieces_pour_vehicule(marque="Toyota", modele="Yaris", annee=2008)
ok(any(x["id"] == p["id"] for x in trouve),
   f"« filtre pour Yaris 2008 » trouve le produit ({len(trouve)} résultat(s))")

hors_periode = m3.chercher_pieces_pour_vehicule(marque="Toyota", modele="Yaris", annee=1990)
ok(not any(x["id"] == p["id"] for x in hors_periode),
   "Yaris 1990 (hors période 2005-2020) ne remonte pas")

autre_marque = m3.chercher_pieces_pour_vehicule(marque="Peugeot")
ok(not any(x["id"] == p["id"] for x in autre_marque), "Peugeot ne remonte pas le produit")

s, msg, mid = m3.add_modele("Toyota", "Probox", "1.5", "essence", 2002, 0)
ok(s, f"nouveau modèle ajouté : {msg}")
s, msg, mid2 = m3.add_modele("Toyota", "Probox", "1.5", "essence", 2002, 0)
ok(not s and mid2 == mid, "modèle en doublon refusé et id existant retourné")
s, msg, _ = m3.add_modele("", "SansMarque")
ok(not s, "modèle sans marque refusé")

m3.delier_compatibilite(compats[0]["id"])
ok(len(m3.get_compatibilites_produit(p["id"])) == 0, "compatibilité déliée")


# ═══════════════════════════════════════════════
section("RÉFÉRENCES CROISÉES")

s, msg = m3.add_reference(p["id"], "90915-YZZD2", "oem", "Toyota")
ok(s, f"référence OEM ajoutée : {msg}")
s, msg = m3.add_reference(p["id"], "W68/3", "equivalent", "Mann")
ok(s, "référence équivalente Mann ajoutée")
s, msg = m3.add_reference(p["id"], "90915-YZZD2", "oem")
ok(not s, "référence en doublon refusée")
s, msg = m3.add_reference(p["id"], "", "oem")
ok(not s, "référence vide refusée")
s, msg = m3.add_reference(p["id"], "XX", "type_bidon")
ok(not s, "type de référence invalide refusé")

refs = m3.get_references_produit(p["id"])
ok(len(refs) == 2, f"2 références croisées ({len(refs)})")

# Recherche universelle : la réf OEM doit retrouver le produit
res = m3.chercher_par_reference("90915-YZZD2")
ok(any(x["id"] == p["id"] for x in res), "recherche par réf OEM trouve le produit")
res = m3.chercher_par_reference("W68/3")
ok(any(x["id"] == p["id"] for x in res), "recherche par équivalent Mann trouve le produit")
res = m3.chercher_par_reference("CUMP-01")
ok(any(x["id"] == p["id"] for x in res), "recherche par réf interne fonctionne")
ok(m3.chercher_par_reference("") == [], "recherche vide → liste vide")
ok(m3.chercher_par_reference("INEXISTANT-ZZZ") == [], "référence inconnue → liste vide")


# ═══════════════════════════════════════════════
section("PRÉVISION DE RUPTURE & ABC")

prev = m3.prevision_rupture(horizon_jours=30)
ok(isinstance(prev, list), f"prévision calculée ({len(prev)} produit(s) à risque)")
if prev:
    champs = {"produit_id", "couverture_jours", "qte_a_commander", "urgence"}
    ok(champs <= set(prev[0]), "champs de prévision complets")
    ok(prev[0]["urgence"] in ("critique", "haute", "moyenne"), "niveau d'urgence valide")
    ok(all(x["qte_a_commander"] >= 0 for x in prev), "quantités à commander >= 0")

s, msg = m3.calculer_classes_abc()
ok(s, f"classement ABC : {msg}")
p_final = db.trouver_produit("CUMP-01")
ok(p_final["classe_abc"] in ("A", "B", "C"), f"classe attribuée ({p_final['classe_abc']})")

dormants = m3.produits_dormants(jours=1)
ok(isinstance(dormants, list), f"produits dormants ({len(dormants)})")


# ═══════════════════════════════════════════════
section("KPI TABLEAU DE BORD v3")

kpi = m3.kpi_v3()
attendus = {"creances_total", "dettes_total", "valeur_stock_cump", "nb_depots",
            "ruptures_prevues", "retours_mois", "commandes_en_cours"}
ok(attendus <= set(kpi), f"KPI complets ({len(kpi)} indicateurs)")
ok(kpi["nb_depots"] == 3, f"3 dépôts actifs ({kpi['nb_depots']})")
ok(kpi["valeur_stock_cump"] > 0, f"valeur stock au CUMP = {kpi['valeur_stock_cump']:,.0f}")
ok(kpi["dettes_total"] > 0, f"dette fournisseur = {kpi['dettes_total']:,.0f}")


# ═══════════════════════════════════════════════
section("COHÉRENCE GLOBALE (invariants)")

conn = db.get_connection()

# Invariant 1 : produits.stock == somme stock_depot
ecarts = conn.execute("""
    SELECT p.id, p.reference, p.stock,
           COALESCE((SELECT SUM(quantite) FROM stock_depot WHERE produit_id=p.id),0) AS somme
    FROM produits p
    WHERE p.stock != COALESCE((SELECT SUM(quantite) FROM stock_depot
                               WHERE produit_id=p.id),0)""").fetchall()
ok(not ecarts, f"produits.stock == SUM(stock_depot) pour tous les produits",
   f"écarts: {[dict(e) for e in ecarts]}")

# Invariant 2 : aucun stock négatif
negs = conn.execute("SELECT * FROM stock_depot WHERE quantite < 0").fetchall()
ok(not negs, "aucune quantité négative en stock_depot",
   f"{[dict(n) for n in negs]}")
negs2 = conn.execute("SELECT reference, stock FROM produits WHERE stock < 0").fetchall()
ok(not negs2, "aucun stock produit négatif", f"{[dict(n) for n in negs2]}")

# Invariant 3 : cohérence stock_vente / stock_reserve
incoh = conn.execute("""
    SELECT reference, stock, stock_vente, stock_reserve FROM produits
    WHERE stock != stock_vente + stock_reserve""").fetchall()
ok(not incoh, "stock == stock_vente + stock_reserve",
   f"{[dict(i) for i in incoh]}")

# Invariant 4 : aucune créance négative
neg_cre = conn.execute("SELECT * FROM v_creances WHERE reste_du < 0").fetchall()
ok(not neg_cre, "aucune créance négative")

# Invariant 5 : tous les CUMP >= 0
neg_cump = conn.execute("SELECT reference, cump FROM produits WHERE cump < 0").fetchall()
ok(not neg_cump, "aucun CUMP négatif")

# Invariant 6 : chaque vente a un dépôt
sans_depot = conn.execute("SELECT COUNT(*) FROM ventes WHERE depot_id IS NULL").fetchone()[0]
ok(sans_depot == 0, f"toutes les ventes ont un dépôt ({sans_depot} sans)")

db.close_connection()  # reset _conn_persistante

# ═══════════════════════════════════════════════
print("\n" + "=" * 50)
if echoues:
    print(f"RESULTAT : {reussis} reussis, {len(echoues)} ECHOUES")
    for e in echoues:
        print(f"   - {e}")
else:
    print(f"RESULTAT : {reussis} reussis, 0 echoues")
print("=" * 50)

# Nettoyage
for suffixe in ("", "-wal", "-shm"):
    try:
        os.remove(DB_TEST + suffixe)
    except OSError:
        pass

if __name__ == "__main__":
    sys.exit(1 if echoues else 0)

