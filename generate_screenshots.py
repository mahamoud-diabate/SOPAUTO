import sys
import os
import random
import time
import tkinter as tk
import ctypes
from datetime import datetime, timedelta
from ctypes import windll, byref, sizeof, Structure, c_int
from PIL import Image

DEMO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_screenshots.db")
for f in [DEMO_DB, DEMO_DB + "-wal", DEMO_DB + "-shm"]:
    if os.path.exists(f):
        try: os.remove(f)
        except Exception: pass

import database as db
db.DB_PATH = DEMO_DB
db.init_database()
db.set_utilisateur_courant("admin")

# 1. Catégories
cats = ["Freinage", "Filtres", "Suspension & Direction", "Moteur & Distribution", "Électricité & Allumage", "Carrosserie & Éclairage"]
cat_ids = {}
for c in cats:
    db.add_categorie(c, f"Pièces de {c.lower()}")
for c in db.get_categories():
    cat_ids[c["nom"]] = c["id"]

# 2. Fournisseurs
fournisseurs = [
    ("BOSCH Automotive", "M. Traore", "+225 07 01 02 03", "contact@bosch-ci.com", "Abidjan Zone 4"),
    ("VALEO Distribution", "Mme Kone", "+225 05 44 55 66", "valeo@distrib.ci", "Treichville"),
    ("TOYOTA / SUZUKI Genuine", "M. Diabate", "+225 01 88 99 00", "pieces@toyota-ci.com", "Vridi"),
]
fourn_ids = []
for f in fournisseurs:
    db.add_fournisseur(*f)
for f in db.get_fournisseurs():
    fourn_ids.append(f["id"])

# 3. Clients
clients = [
    ("Garage Moderne & Fils", "+225 07 12 34 56", "bamba@garagemoderne.ci", "Treichville", "Hilux, Prado", "Client fidèle flotte pro", 5000000),
    ("Auto Service Express", "+225 05 98 76 54", "contact@autoservice.ci", "Marcory", "Suzuki Swift / Vitara", "Paiement à 30 jours", 2000000),
    ("Transport & Logistique Diop", "+225 01 22 33 44", "diop.trans@gmail.com", "Yopougon", "Peugeot Boxer, Carry", "Flotte utilitaire", 10000000),
    ("Garage de la Paix", "+225 07 88 11 22", "yapi@paixauto.ci", "Cocody", "Corolla, RAV4", "", 1500000),
]
for cl in clients:
    db.add_client(*cl)
cl_list = db.get_clients()
client_ids = [c["id"] for c in cl_list]

# 4. Produits
produits_data = [
    ("Plaquettes de frein Avant Suzuki Swift / Alto", "Freinage", "SUZ-FRN-001", "33061-M79F00", 8500, 15000, 24, 6, "Suzuki", "Plaquettes céramique"),
    ("Disque de frein ventilé Avant Toyota Hilux", "Freinage", "TOY-FRN-010", "43512-0K060", 22000, 38000, 14, 4, "BOSCH", "Disque acier ventilé"),
    ("Filtre à huile Suzuki Swift / Jimny", "Filtres", "SUZ-FLT-001", "16510-61A31", 2200, 4500, 45, 10, "Suzuki", "Filtre longue durée"),
    ("Filtre à air moteur Toyota Land Cruiser Prado", "Filtres", "TOY-FLT-004", "17801-51020", 4500, 9000, 32, 8, "TOYOTA", "Cartouche filtrante"),
    ("Kit d'embrayage complet Suzuki Swift III", "Moteur & Distribution", "SUZ-TRM-001", "22100-63J00", 42000, 75000, 8, 2, "VALEO", "Mécanisme + disque"),
    ("Kit distribution + Pompe à eau Toyota Corolla", "Moteur & Distribution", "TOY-DIS-002", "13568-19106", 38000, 68000, 3, 5, "BOSCH", "Courroie + galets"),
    ("Amortisseur Avant Droit Suzuki Jimny", "Suspension & Direction", "SUZ-SUS-001", "41601-81A00", 24000, 42000, 12, 4, "KYB", "Amortisseur gaz"),
    ("Rotule de suspension Inférieure Toyota RAV4", "Suspension & Direction", "TOY-SUS-005", "43330-49095", 7500, 14000, 2, 6, "555 Japan", "Rotule forgée"),
    ("Bougie d'allumage Iridium Power Denso", "Électricité & Allumage", "ELC-BOU-001", "IK20-5304", 3500, 7000, 60, 12, "DENSO", "Électrode iridium"),
    ("Alternateur 12V 90A Peugeot 206 1.4 HDi", "Électricité & Allumage", "PGT-ALT-001", "9642880480", 55000, 95000, 4, 2, "VALEO", "Alternateur neuf"),
]

for p in produits_data:
    cid = cat_ids.get(p[1], 1)
    # Rayon multiplie pour encaisser 10 jours de ventes de demonstration.
    # Les references deja sous leur seuil restent intactes : ce sont elles qui
    # alimentent les alertes de stock du tableau de bord.
    stock_vente = p[6] * 5 if p[6] > 5 else p[6]
    db.add_produit(
        reference=p[2], nom=p[0], description=p[9],
        categorie_id=cid, fournisseur_id=fourn_ids[0], marque=p[8],
        prix_achat=p[4], prix_vente=p[5],
        stock_reserve=stock_vente * 2, stock_vente=stock_vente, stock_mini=p[7],
        code_barres=p[3]
    )

prods = db.get_produits()
p_map = {p["reference"]: p for p in prods}

# ── Historique de ventes sur 10 jours ──────────────────────────────────────
# Toutes les ventes datees du meme jour donnaient un histogramme a une seule
# barre et « pas de comparaison » sur chaque indicateur. On etale l'historique
# et on fait varier les prix : sans dispersion, l'ecran d'analyse des prix
# affiche +0.0 % sur chaque ligne et ne montre rien de ce qu'il sait faire.
random.seed(11)
MODES = ["Espèces", "Espèces", "Espèces", "Mobile Money", "Virement"]
refs = list(p_map)


def prix_pratique(catalogue):
    """Prix reellement facture : le magasin negocie ligne par ligne."""
    tirage = random.random()
    if tirage < 0.04:
        facteur = random.choice([0.68, 0.72])                   # vente a perte
    elif tirage < 0.34:
        facteur = random.choice([0.88, 0.90, 0.93, 0.96])       # remise
    elif tirage < 0.46:
        facteur = random.choice([1.03, 1.05, 1.08])             # majoration
    else:
        return catalogue                                        # prix affiche
    return max(50, round(catalogue * facteur / 50) * 50)


conn_seed = db.get_connection()
for recul in range(9, -1, -1):
    jour = datetime.now() - timedelta(days=recul)
    for _ in range(random.randint(2, 5)):
        panier = random.sample(refs, random.randint(1, 3))
        items = [(p_map[r]["id"], random.randint(1, 3),
                  prix_pratique(p_map[r]["prix_vente"])) for r in panier]
        total = sum(q * pu for _, q, pu in items)

        a_credit = random.random() < 0.25
        idx = random.randrange(len(client_ids))
        # "Crédit" porte un accent dans create_vente() : sans lui la vente est
        # enregistree comme soldee et aucune creance n'est ouverte.
        acompte = round(total * random.choice([0, 0, 0.3, 0.5]) / 100) * 100

        ok, msg, vente_id = db.create_vente(
            cl_list[idx]["nom"] if a_credit or random.random() < 0.5 else "Client comptant",
            items,
            remise=random.choice([0, 0, 0, 2500, 5000]),
            mode_paiement=db.MODE_CREDIT if a_credit else random.choice(MODES),
            montant_paye=acompte if a_credit else total,
            client_id=client_ids[idx] if a_credit else None,
            # Echeance calee sur la date de vente et non sur aujourd'hui,
            # sinon aucune creance n'apparait jamais en retard.
            date_echeance=((jour + timedelta(days=random.choice([7, 15, 30])))
                           .strftime("%Y-%m-%d") if a_credit else None),
            controler_credit=False,
        )
        if ok and vente_id:
            horodatage = jour.replace(hour=random.randint(8, 18),
                                      minute=random.randint(0, 59))
            with conn_seed:
                conn_seed.execute("UPDATE ventes SET date_vente=? WHERE id=?",
                                  (horodatage.strftime("%Y-%m-%d %H:%M:%S"), vente_id))

# ── Fonctions de capture Win32 ctypes ──
class BITMAPINFOHEADER(Structure):
    _fields_ = [
        ('biSize', c_int),
        ('biWidth', c_int),
        ('biHeight', c_int),
        ('biPlanes', ctypes.c_short),
        ('biBitCount', ctypes.c_short),
        ('biCompression', c_int),
        ('biSizeImage', c_int),
        ('biXPelsPerMeter', c_int),
        ('biYPelsPerMeter', c_int),
        ('biClrUsed', c_int),
        ('biClrImportant', c_int),
    ]

class BITMAPINFO(Structure):
    _fields_ = [
        ('bmiHeader', BITMAPINFOHEADER),
        ('bmiColors', c_int * 3),
    ]

def capture_fenetre(root_widget, out_path):
    # Certains ecrans remaximisent la fenetre : on la ramene a la taille de
    # capture avant chaque prise pour garder un jeu d'images homogene.
    if root_widget.state() != "normal" or root_widget.winfo_width() != 2300:
        root_widget.state("normal")
        root_widget.geometry("2300x1120+30+30")
        root_widget.update()
        time.sleep(0.4)

    root_widget.update()
    time.sleep(0.2)
    hwnd = windll.user32.GetParent(root_widget.winfo_id()) or root_widget.winfo_id()
    
    rect = (ctypes.c_long * 4)()
    windll.user32.GetWindowRect(hwnd, byref(rect))
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]
    
    if w <= 0 or h <= 0:
        w = root_widget.winfo_width()
        h = root_widget.winfo_height()

    hdc_screen = windll.user32.GetDC(hwnd)
    hdc_mem = windll.gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = windll.gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    windll.gdi32.SelectObject(hdc_mem, hbmp)
    windll.user32.PrintWindow(hwnd, hdc_mem, 2)  # PW_RENDERFULLCONTENT
    
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0
    
    buf = ctypes.create_string_buffer(w * h * 4)
    windll.gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, byref(bi), 0)
    
    img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
    img.convert('RGB').save(out_path)
    
    windll.gdi32.DeleteObject(hbmp)
    windll.gdi32.DeleteDC(hdc_mem)
    windll.user32.ReleaseDC(hwnd, hdc_screen)
    print(f"OK {out_path} ({w}x{h})")

# ── Lancement CustomTkinter Application (core.py) ──
from core import Application
from ui_widgets import appliquer_palette, appliquer_theme, THEME_ACTUEL

root = tk.Tk()
# Les largeurs de l'interface sont en pixels fixes (menu lateral = 248 px) alors
# que Tk agrandit les polices selon le DPI : sur un ecran 4K le libelle deborde
# de la barre et se retrouve coupe (« Tableau de bo »). On force les metriques
# de police en 96 dpi pour retrouver les proportions prevues par le design.
root.tk.call("tk", "scaling", 1.0)
user = {"id": 1, "nom_utilisateur": "admin", "nom_complet": "Mahamoud Diabate", "role": "superviseur"}
app = Application(root, user)
# Application() maximise la fenetre : en 4K le contenu prevu pour ~1400 px se
# retrouve noye dans le vide. On revient a une taille de capture homogene.
root.state("normal")
root.geometry("2300x1120+30+30")
root.update()

# On passe par la bascule reelle de l'application. L'ancienne version changeait
# la palette a la main puis redessinait seulement la page : l'en-tete, construit
# avec la palette claire au demarrage, n'etait jamais reconstruit et restait
# blanc sur toutes les captures « sombres ». basculer_theme() reconstruit toute
# l'interface, donc la capture montre ce que l'utilisateur voit vraiment.
def _basculer_vers(cible):
    if THEME_ACTUEL[0] != cible:
        app.basculer_theme()
        root.update()
        time.sleep(0.3)
    assert THEME_ACTUEL[0] == cible, f"theme attendu {cible}, obtenu {THEME_ACTUEL[0]}"

def appliquer_theme_sombre():
    _basculer_vers("sombre")

def appliquer_theme_clair():
    _basculer_vers("clair")

# 1. Dashboard Sombre
appliquer_theme_sombre()
app.afficher_dashboard()
capture_fenetre(root, "docs/dashboard_sombre.png")

# 2. Dashboard Clair
appliquer_theme_clair()
app.afficher_dashboard()
capture_fenetre(root, "docs/dashboard_clair.png")

# 3. Caisse Sombre
appliquer_theme_sombre()
app.afficher_caisse()
app.enregistrement = [
    {"id": p_map["SUZ-FRN-001"]["id"], "ref": "SUZ-FRN-001", "nom": "Plaquettes de frein Avant Suzuki Swift", "quantite": 2, "pu": 15000, "cout": 8500, "prix_catalogue": 15000},
    {"id": p_map["SUZ-FLT-001"]["id"], "ref": "SUZ-FLT-001", "nom": "Filtre à huile Suzuki Swift / Jimny", "quantite": 3, "pu": 4500, "cout": 2200, "prix_catalogue": 4500},
    {"id": p_map["ELC-BOU-001"]["id"], "ref": "ELC-BOU-001", "nom": "Bougie d'allumage Iridium Denso Power", "quantite": 4, "pu": 7000, "cout": 3500, "prix_catalogue": 7000},
]
app._rafraichir_enregistrement()
capture_fenetre(root, "docs/caisse_sombre.png")

# 4. Caisse Clair
appliquer_theme_clair()
app.afficher_caisse()
app.enregistrement = [
    {"id": p_map["SUZ-FRN-001"]["id"], "ref": "SUZ-FRN-001", "nom": "Plaquettes de frein Avant Suzuki Swift", "quantite": 2, "pu": 15000, "cout": 8500, "prix_catalogue": 15000},
    {"id": p_map["SUZ-FLT-001"]["id"], "ref": "SUZ-FLT-001", "nom": "Filtre à huile Suzuki Swift / Jimny", "quantite": 3, "pu": 4500, "cout": 2200, "prix_catalogue": 4500},
    {"id": p_map["ELC-BOU-001"]["id"], "ref": "ELC-BOU-001", "nom": "Bougie d'allumage Iridium Denso Power", "quantite": 4, "pu": 7000, "cout": 3500, "prix_catalogue": 7000},
]
app._rafraichir_enregistrement()
capture_fenetre(root, "docs/caisse_clair.png")

# 5. Stock Sombre
appliquer_theme_sombre()
app.afficher_stock()
capture_fenetre(root, "docs/stock_sombre.png")

# 6. Produits Sombre
appliquer_theme_sombre()
app.afficher_produits()
capture_fenetre(root, "docs/produits_sombre.png")

# 7. Créances Sombre
appliquer_theme_sombre()
app.afficher_creances()
capture_fenetre(root, "docs/creances_sombre.png")

# 8. Analyse Sombre
appliquer_theme_sombre()
app.afficher_analyse()
capture_fenetre(root, "docs/rapports_sombre.png")

root.destroy()
print("Captures de l'application principale terminées avec succès !")
