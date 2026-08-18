import sys
import os
import time
import tkinter as tk
import ctypes
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
    db.add_produit(
        reference=p[2], nom=p[0], description=p[9],
        categorie_id=cid, fournisseur_id=fourn_ids[0], marque=p[8],
        prix_achat=p[4], prix_vente=p[5],
        stock_reserve=0, stock_vente=p[6], stock_mini=p[7],
        code_barres=p[3]
    )

prods = db.get_produits()
p_map = {p["reference"]: p for p in prods}

db.create_vente(
    "Garage Moderne & Fils",
    [(p_map["SUZ-FRN-001"]["id"], 2, 15000),
     (p_map["SUZ-FLT-001"]["id"], 3, 4500)],
    remise=2500, mode_paiement="Espèces", client_id=client_ids[0]
)

db.create_vente(
    "Auto Service Express",
    [(p_map["TOY-FRN-010"]["id"], 2, 38000),
     (p_map["SUZ-TRM-001"]["id"], 1, 75000)],
    remise=5000, mode_paiement="Virement", client_id=client_ids[1]
)

db.create_vente(
    "Transport & Logistique Diop",
    [(p_map["TOY-DIS-002"]["id"], 1, 68000),
     (p_map["ELC-BOU-001"]["id"], 6, 7000)],
    remise=0, mode_paiement="Crédit", montant_paye=0, client_id=client_ids[2]
)

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
user = {"id": 1, "nom_utilisateur": "admin", "nom_complet": "Mahamoud Diabate", "role": "superviseur"}
app = Application(root, user)
root.geometry("1400x820+40+40")
root.update()

def appliquer_theme_sombre():
    THEME_ACTUEL[0] = "sombre"
    db.set_parametre("theme", "sombre")
    appliquer_palette("sombre")
    appliquer_theme(root)

def appliquer_theme_clair():
    THEME_ACTUEL[0] = "clair"
    db.set_parametre("theme", "clair")
    appliquer_palette("clair")
    appliquer_theme(root)

# 1. Dashboard Sombre
appliquer_theme_sombre()
app.afficher_dashboard()
capture_fenetre(root, "docs/dashboard_sombre.png")
capture_fenetre(root, "docs/capture_sombre.png")

# 2. Dashboard Clair
appliquer_theme_clair()
app.afficher_dashboard()
capture_fenetre(root, "docs/dashboard_clair.png")
capture_fenetre(root, "docs/capture_clair.png")

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
capture_fenetre(root, "docs/caisse_screenshot.png")

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
