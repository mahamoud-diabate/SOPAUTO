"""
SODIPAC - Test de validation des 18 modules PyQt6
"""

import _bootstrap  # noqa: F401  (chemin d'import + sortie UTF-8)

import sys
import database as db
from PyQt6.QtWidgets import QApplication
from core_qt import ApplicationQt


def tester_interface_qt_complete():
    print("=== Démarrage des tests UI PyQt6 (18 modules) ===")
    if hasattr(db, '_init_db'):
        db._init_db()

    app = QApplication(sys.argv)
    user = {"id": 1, "nom_utilisateur": "admin", "nom_complet": "Admin Test", "role": "superviseur"}

    try:
        win = ApplicationQt(user)
        print("OK - Fenêtre principale ApplicationQt instanciée")

        for idx in range(18):
            win.naviguer(idx)
            app.processEvents()
            print(f"OK - Navigation module index {idx}: {win.lbl_titre_page.text()}")

        print("\n==============================================")
        print("INTERFACE PyQt6 COMPLETE (18/18) OK — 0 erreur !")
        print("==============================================")
    except Exception as e:
        print(f"\n[ERREUR FATALE UI QT] : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    tester_interface_qt_complete()
