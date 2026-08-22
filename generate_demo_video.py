"""
SOPAUTO — Génération de la vidéo de démonstration (MP4 + WebM, 1080p).

Pilote l'interface réelle (Tkinter) de la caisse et capture une frame Win32
(PrintWindow) à chaque étape, puis encode les frames en MP4 (H.264) et WebM
(VP9) via ffmpeg. Réutilise le seed jetable de generate_demo_gif.py.
"""
import os
import sys
import time
import subprocess
import shutil
import tkinter as tk
from ctypes import windll, byref, sizeof, Structure, c_int, c_long, c_short, create_string_buffer
from PIL import Image

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

DEMO_DB = os.path.join(REPO, "demo_video.db")
for f in [DEMO_DB, DEMO_DB + "-wal", DEMO_DB + "-shm"]:
    if os.path.exists(f):
        try:
            os.remove(f)
        except Exception:
            pass

import database as db
db.DB_PATH = DEMO_DB
db.init_database()
db.set_utilisateur_courant("admin")

# ── Seed (identique à generate_demo_gif.py) ─────────────────────────────────
cats = ["Freinage", "Filtres", "Suspension & Direction", "Moteur & Distribution",
        "Électricité & Allumage", "Carrosserie & Éclairage"]
cat_ids = {}
for c in cats:
    db.add_categorie(c, f"Pièces de {c.lower()}")
for c in db.get_categories():
    cat_ids[c["nom"]] = c["id"]

for f in [("BOSCH Automotive", "M. Traore", "+225 07 01 02 03", "contact@bosch-ci.com", "Abidjan Zone 4"),
          ("VALEO Distribution", "Mme Kone", "+225 05 44 55 66", "valeo@distrib.ci", "Treichville"),
          ("TOYOTA / SUZUKI Genuine", "M. Diabate", "+225 01 88 99 00", "pieces@toyota-ci.com", "Vridi")]:
    db.add_fournisseur(*f)
fourn_ids = [x["id"] for x in db.get_fournisseurs()]

for cl in [("Garage Moderne & Fils", "+225 07 12 34 56", "bamba@garagemoderne.ci", "Treichville", "Hilux, Prado", "Client fidèle flotte pro", 5000000),
           ("Auto Service Express", "+225 05 98 76 54", "contact@autoservice.ci", "Marcory", "Suzuki Swift / Vitara", "Paiement à 30 jours", 2000000),
           ("Transport & Logistique Diop", "+225 01 22 33 44", "diop.trans@gmail.com", "Yopougon", "Peugeot Boxer, Carry", "Flotte utilitaire", 10000000),
           ("Garage de la Paix", "+225 07 88 11 22", "yapi@paixauto.ci", "Cocody", "Corolla, RAV4", "", 1500000)]:
    db.add_client(*cl)
cl_list = db.get_clients()
client_ids = [c["id"] for c in cl_list]

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
    stock_vente = p[6] * 5 if p[6] > 5 else p[6]
    db.add_produit(reference=p[2], nom=p[0], description=p[9], categorie_id=cid,
                   fournisseur_id=fourn_ids[0], marque=p[8], prix_achat=p[4],
                   prix_vente=p[5], stock_reserve=stock_vente * 2, stock_vente=stock_vente,
                   stock_mini=p[7], code_barres=p[3])
prods = db.get_produits()
p_map = {p["reference"]: p for p in prods}

# ── Capture Win32 ───────────────────────────────────────────────────────────
class BITMAPINFOHEADER(Structure):
    _fields_ = [('biSize', c_int), ('biWidth', c_int), ('biHeight', c_int),
                ('biPlanes', c_short), ('biBitCount', c_short), ('biCompression', c_int),
                ('biSizeImage', c_int), ('biXPelsPerMeter', c_int), ('biYPelsPerMeter', c_int),
                ('biClrUsed', c_int), ('biClrImportant', c_int)]

class BITMAPINFO(Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', c_int * 3)]

def _cap(root, out):
    hwnd = windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
    rect = (c_long * 4)()
    windll.user32.GetWindowRect(hwnd, byref(rect))
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]
    if w <= 0 or h <= 0:
        w, h = root.winfo_width(), root.winfo_height()
    hdc_screen = windll.user32.GetDC(hwnd)
    hdc_mem = windll.gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = windll.gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    windll.gdi32.SelectObject(hdc_mem, hbmp)
    windll.user32.PrintWindow(hwnd, hdc_mem, 2)
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0
    buf = create_string_buffer(w * h * 4)
    windll.gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, byref(bi), 0)
    Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1).convert('RGB').save(out)
    windll.gdi32.DeleteObject(hbmp)
    windll.gdi32.DeleteDC(hdc_mem)
    windll.user32.ReleaseDC(hwnd, hdc_screen)

# ── Pilote d'animation ──────────────────────────────────────────────────────
from core import Application
from ui_widgets import THEME_ACTUEL

root = tk.Tk()
root.tk.call("tk", "scaling", 1.0)
user = {"id": 1, "nom_utilisateur": "admin", "nom_complet": "Mahamoud Diabate", "role": "superviseur"}
app = Application(root, user)
root.state("normal")
root.geometry("1920x1080+0+0")  # 16:9 — évite la distorsion à l'encodage
root.update()
time.sleep(0.5)

if THEME_ACTUEL[0] != "sombre":
    app.basculer_theme()
    root.update()
    time.sleep(0.3)

frames_dir = os.path.join(REPO, ".video_frames")
if os.path.exists(frames_dir):
    shutil.rmtree(frames_dir)
os.makedirs(frames_dir)

seq = []
def snap(duree=0.12):
    i = len(seq)
    p = os.path.join(frames_dir, f"f{i:05d}.jpg")
    root.update()
    _cap(root, p)
    seq.append((duree, p))

def hold(n=8, duree=0.12):
    for _ in range(n):
        snap(duree)

# ── Scénario caisse ─────────────────────────────────────────────────────────
app.afficher_caisse()
root.update(); time.sleep(0.6)
hold(14, 0.12)

# saisie progressive de la recherche
for c in "plaquettes":
    app._var_recherche.set(app._var_recherche.get() + c)
    root.update()
    snap(0.14)
hold(8, 0.14)

# ajout
app._ajouter_premier()
root.update(); time.sleep(0.4)
hold(12, 0.12)

# seconde recherche
app._var_recherche.set("")
app._recherche_typing()
for c in "filtre":
    app._var_recherche.set(app._var_recherche.get() + c)
    root.update()
    snap(0.13)
app._ajouter_premier()
root.update(); time.sleep(0.4)
hold(10, 0.12)

# qté +1
app.tree_panier.selection_set("0")
app._ajuster_qte_selection(1)
root.update(); time.sleep(0.2)
hold(8, 0.12)

# négociation de prix
app.enregistrement[0]["pu"] = 12500
app._rafraichir_enregistrement()
root.update(); time.sleep(0.2)
hold(14, 0.12)

# fin
hold(16, 0.15)

# ── Assemblage vidéo ────────────────────────────────────────────────────────
manifest = os.path.join(frames_dir, "list.txt")
with open(manifest, "w", encoding="utf-8") as fh:
    for i, (d, p) in enumerate(seq):
        fh.write(f"file 'f{i:05d}.jpg'\n")
        fh.write(f"duration {max(0.04, d):.3f}\n")
    fh.write(f"file 'f{len(seq)-1:05d}.jpg'\n")

base_filter = "fps=30,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"
for ext, vcodec, extra in [
    ("mp4", "libx264", ["-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium"]),
    ("webm", "libvpx-vp9", ["-pix_fmt", "yuv420p", "-crf", "34", "-b:v", "0"]),
]:
    out = os.path.join(REPO, "docs", f"demo-caisse.{ext}")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", manifest,
           "-vf", base_filter, "-c:v", vcodec] + extra + ["-an", out]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"OK: {out} ({os.path.getsize(out)//1024} Ko)")

shutil.rmtree(frames_dir, ignore_errors=True)
root.destroy()
print(f"Terminé — {len(seq)} frames")
