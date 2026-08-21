"""
SOPAUTO — Export PDF
====================

Convertit les documents HTML déjà produits par factures.py en PDF **sans
aucune dépendance à installer** : on pilote le navigateur déjà présent sur
la machine (Edge ou Chrome) en mode headless.

Ordre de recherche :
  1. Microsoft Edge   (présent sur tout Windows 10/11)
  2. Google Chrome
  3. wkhtmltopdf      (si jamais installé)

Si aucun n'est trouvé, on retombe proprement sur le HTML et on le dit à
l'utilisateur — pas de plantage.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE_DIR, "factures")


# ─── Détection du moteur de rendu ─────────────────────

CHEMINS_NAVIGATEURS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
]

# Cache : la détection n'est faite qu'une fois par session
_moteur_cache: list = []


def trouver_moteur() -> tuple[str | None, str | None]:
    """
    Retourne (chemin, type) où type ∈ {'navigateur', 'wkhtmltopdf'}.
    (None, None) si aucun moteur disponible.
    """
    if _moteur_cache:
        return _moteur_cache[0]

    resultat = (None, None)

    # 1/2 — Edge ou Chrome
    for chemin in CHEMINS_NAVIGATEURS:
        if chemin and os.path.isfile(chemin):
            resultat = (chemin, "navigateur")
            break

    # 3 — wkhtmltopdf dans le PATH
    if resultat[0] is None:
        import shutil
        for nom in ("wkhtmltopdf", "wkhtmltopdf.exe"):
            chemin = shutil.which(nom)
            if chemin:
                resultat = (chemin, "wkhtmltopdf")
                break

    # Sous Linux/Mac (tests, CI)
    if resultat[0] is None and sys.platform != "win32":
        import shutil
        for nom in ("google-chrome", "chromium", "chromium-browser",
                    "microsoft-edge"):
            chemin = shutil.which(nom)
            if chemin:
                resultat = (chemin, "navigateur")
                break

    _moteur_cache.append(resultat)
    return resultat


def moteur_disponible() -> bool:
    return trouver_moteur()[0] is not None


def nom_moteur() -> str:
    """Libellé lisible du moteur, pour l'affichage."""
    chemin, type_moteur = trouver_moteur()
    if not chemin:
        return "aucun"
    base = os.path.basename(chemin).lower()
    if "msedge" in base:
        return "Microsoft Edge"
    if "chrome" in base or "chromium" in base:
        return "Google Chrome"
    if "wkhtmltopdf" in base:
        return "wkhtmltopdf"
    return base


# ─── Conversion ───────────────────────────────────────

def html_vers_pdf(chemin_html: str, chemin_pdf: str | None = None,
                  paysage: bool = False, timeout: int = 60) -> tuple[bool, str]:
    """
    Convertit un fichier HTML local en PDF.
    Retourne (succès, chemin_pdf_ou_message).
    """
    if not os.path.isfile(chemin_html):
        return False, f"Fichier HTML introuvable : {chemin_html}"

    if chemin_pdf is None:
        chemin_pdf = os.path.splitext(chemin_html)[0] + ".pdf"
    os.makedirs(os.path.dirname(os.path.abspath(chemin_pdf)), exist_ok=True)

    moteur, type_moteur = trouver_moteur()
    if not moteur:
        return False, ("Aucun moteur PDF trouvé.\n\n"
                       "Le document HTML reste disponible et s'imprime "
                       "directement depuis le navigateur (Ctrl+P → "
                       "« Enregistrer au format PDF »).")

    # Le navigateur refuse d'écraser un PDF existant : on nettoie avant
    if os.path.exists(chemin_pdf):
        try:
            os.remove(chemin_pdf)
        except OSError:
            horodatage = time.strftime("%H%M%S")
            racine, ext = os.path.splitext(chemin_pdf)
            chemin_pdf = f"{racine}_{horodatage}{ext}"

    url = "file:///" + os.path.abspath(chemin_html).replace("\\", "/")

    if type_moteur == "navigateur":
        commande = [
            moteur,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",       # pas d'URL/date parasites
            "--print-to-pdf-no-header",     # ancienne syntaxe, ignorée si inconnue
            f"--print-to-pdf={os.path.abspath(chemin_pdf)}",
            url,
        ]
        if paysage:
            commande.insert(-1, "--landscape")
    else:
        commande = [moteur, "--quiet",
                    "--orientation", "Landscape" if paysage else "Portrait",
                    os.path.abspath(chemin_html), os.path.abspath(chemin_pdf)]

    try:
        proc = subprocess.run(commande, capture_output=True, timeout=timeout,
                              creationflags=(subprocess.CREATE_NO_WINDOW
                                             if sys.platform == "win32" else 0))
    except subprocess.TimeoutExpired:
        return False, f"La conversion PDF a dépassé {timeout} s."
    except OSError as e:
        return False, f"Impossible de lancer {nom_moteur()} : {e}"

    # Le navigateur écrit le fichier de façon asynchrone : on patiente un peu
    for _ in range(20):
        if os.path.isfile(chemin_pdf) and os.path.getsize(chemin_pdf) > 800:
            return True, chemin_pdf
        time.sleep(0.25)

    detail = (proc.stderr or b"").decode("utf-8", "ignore").strip()[:300]
    return False, (f"{nom_moteur()} n'a pas produit de PDF exploitable."
                   + (f"\n{detail}" if detail else ""))


def ouvrir_fichier(chemin: str) -> None:
    """Ouvre le fichier avec l'application par défaut."""
    try:
        if sys.platform == "win32":
            os.startfile(chemin)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", chemin])
        else:
            subprocess.Popen(["xdg-open", chemin])
    except (AttributeError, OSError):
        pass


# ─── Raccourcis métier ────────────────────────────────

def facture_pdf(vente_id: int, format_ticket: bool = False,
                ouvrir: bool = True) -> tuple[bool, str]:
    """Génère la facture (ou le ticket) en PDF."""
    import factures
    # imprimer_facture() écrit le fichier HTML sur disque et retourne son chemin
    ok, chemin_html = factures.imprimer_facture(vente_id, format_ticket, ouvrir=False)
    if not ok:
        return False, chemin_html
    ok, resultat = html_vers_pdf(chemin_html)
    if ok and ouvrir:
        ouvrir_fichier(resultat)
    return ok, resultat


def rapport_pdf(titre: str, date_debut: str, date_fin: str, donnees,
                ouvrir: bool = True, paysage: bool = True) -> tuple[bool, str]:
    """Génère un rapport en PDF (paysage par défaut : les tableaux sont larges)."""
    import factures
    chemin_html = factures.generer_rapport_html(titre, date_debut, date_fin,
                                                donnees, ouvrir=False)
    ok, resultat = html_vers_pdf(chemin_html, paysage=paysage)
    if ok and ouvrir:
        ouvrir_fichier(resultat)
    return ok, resultat


def reappro_pdf(ouvrir: bool = True) -> tuple[bool, str]:
    """Génère le bon de réapprovisionnement en PDF."""
    import factures
    chemin_html = factures.generer_liste_reappro(ouvrir=False)
    ok, resultat = html_vers_pdf(chemin_html)
    if ok and ouvrir:
        ouvrir_fichier(resultat)
    return ok, resultat


if __name__ == "__main__":
    print(f"Moteur PDF détecté : {nom_moteur()}")
    if moteur_disponible():
        chemin, type_m = trouver_moteur()
        print(f"  chemin : {chemin}")
        print(f"  type   : {type_m}")
    else:
        print("  → Aucun. Les documents resteront en HTML.")
