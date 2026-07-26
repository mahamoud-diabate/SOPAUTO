"""
SODIPAC — Gestion Pièce Auto
Point d'entrée de l'application.
"""
import tkinter as tk
import database as db
from core import Application
from dialogues import DialogueConnexion
from ui_widgets import centrer_fenetre


def lancer():
    """Connexion puis application."""
    db.init_database()
    root = tk.Tk()
    root.withdraw()

    # Écran de connexion
    connexion = DialogueConnexion(root)
    root.deiconify()
    root.mainloop()  # Sort quand l'utilisateur se connecte (root.quit())
    
    utilisateur = connexion.utilisateur
    if not utilisateur:
        try:
            root.destroy()
        except tk.TclError:
            pass
        return

    # Lancer l'application principale sur le même root (enfants déjà nettoyés)
    root.withdraw()
    app = Application(root, utilisateur)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    lancer()
