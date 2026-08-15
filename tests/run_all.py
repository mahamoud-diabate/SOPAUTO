"""
Lance toute la suite de tests et affiche un total.

    python tests/run_all.py

Les tests d'interface (`test_ui*.py`) sont exclus par défaut : ils ouvrent des
fenêtres Tkinter/Qt et exigent `customtkinter` et `PyQt6` (voir
`requirements.txt`). Pour les inclure : `python tests/run_all.py --ui`.
"""
import _bootstrap  # noqa: F401  (chemin d'import + sortie UTF-8)

import os
import re
import subprocess
import sys

DOSSIER = os.path.dirname(os.path.abspath(__file__))

SUITES = ["test_critical.py", "test_app.py", "test_v3.py", "test_analyse_prix.py"]
SUITES_UI = ["test_ui.py", "test_ui_v3.py", "test_ui_analyse.py", "test_ui_qt.py"]

# Les fichiers de test affichent « RESULTAT : N reussis, M echoues ».
MOTIF = re.compile(r"(\d+)\s+reussis,\s+(\d+)\s+echoues")


def lancer(fichier):
    """Exécute un fichier de test et renvoie (réussis, échoués, sortie)."""
    proc = subprocess.run(
        [sys.executable, os.path.join(DOSSIER, fichier)],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    sortie = (proc.stdout or "") + (proc.stderr or "")
    trouve = MOTIF.findall(sortie)
    if not trouve:
        # Pas de ligne de résultat : le fichier a planté avant la fin.
        return 0, 1, sortie
    reussis, echoues = trouve[-1]
    return int(reussis), int(echoues), sortie


def main():
    suites = SUITES + (SUITES_UI if "--ui" in sys.argv else [])
    total_ok = total_ko = 0
    echecs = []

    for fichier in suites:
        ok, ko, sortie = lancer(fichier)
        total_ok += ok
        total_ko += ko
        etat = "OK  " if ko == 0 else "ECHEC"
        print(f"  {etat}  {fichier:<24} {ok:>4} reussis, {ko} echoues")
        if ko:
            echecs.append((fichier, sortie))

    print("=" * 56)
    print(f"TOTAL : {total_ok} reussis, {total_ko} echoues")
    print("=" * 56)

    for fichier, sortie in echecs:
        print(f"\n--- sortie de {fichier} ---\n{sortie[-2000:]}")

    return 1 if total_ko else 0


if __name__ == "__main__":
    sys.exit(main())
