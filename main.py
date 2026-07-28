"""
SODIPAC — Gestion Pièce Auto
Point d'entrée de l'application.
"""
import os

# DPI awareness pour Windows - texte net (DOIT être avant tkinter import)
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)  # 1 = Per-Monitor DPI Aware
except Exception:
    try:
        windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import tkinter as tk
import customtkinter as ctk
import database as db
from core import Application
from dialogues import DialogueConnexion
from ui_widgets import centrer_fenetre

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


def lancer():
    """Connexion puis application."""
    print("Demarrage de SODIPAC...")
    db.init_database()
    root = tk.Tk()

    # Écran de connexion
    connexion = DialogueConnexion(root)
    root.deiconify()
    root.focus_force()
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
