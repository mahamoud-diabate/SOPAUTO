"""
SODIPAC - Point d'entrée principal PyQt6
"""
import sys
import os
import database as db
from PyQt6.QtWidgets import QApplication
from core_qt import ApplicationQt


def main():
    # Initialisation base de données
    if hasattr(db, '_init_db'):
        db._init_db()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Session utilisateur superviseur/admin par défaut
    utilisateur = {
        "id": 1,
        "nom_utilisateur": "admin",
        "nom_complet": "Administrateur SODIPAC",
        "role": "superviseur"
    }

    fenetre = ApplicationQt(utilisateur)
    fenetre.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
