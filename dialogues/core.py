"""Dialogues: core"""
from typing import Any
import tkinter as tk
from tkinter import ttk, messagebox

import database as db
from ui_widgets import COULEURS, POLICE, Bouton, centrer_fenetre

class DialogueBase:
    """Socle commun : modal, centré, Échap = annuler, Entrée = valider."""

    def __init__(self, parent, titre, largeur=520, hauteur=420) -> None:
        self.result = None
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(titre)
        self.dialog.configure(bg=COULEURS["bg"])
        self.dialog.transient(parent)
        self.dialog.resizable(False, False)

        entete = tk.Frame(self.dialog, bg=COULEURS["primary"], height=46)
        entete.pack(fill=tk.X)
        entete.pack_propagate(False)
        tk.Label(entete, text=titre, font=(POLICE, 13, "bold"),
                 bg=COULEURS["primary"], fg="white").pack(side=tk.LEFT, padx=18)

        # Le pied est packé AVANT le corps : en cas de manque de place,
        # c'est le corps qui est rogné, jamais les boutons Enregistrer/Annuler.
        self.pied = tk.Frame(self.dialog, bg=COULEURS["bg"], pady=12)
        self.pied.pack(fill=tk.X, side=tk.BOTTOM)

        self.corps = tk.Frame(self.dialog, bg=COULEURS["bg"], padx=20, pady=16)
        self.corps.pack(fill=tk.BOTH, expand=True)

        centrer_fenetre(self.dialog, largeur, hauteur)
        self.dialog.bind("<Escape>", lambda e: self.annuler())
        self.dialog.protocol("WM_DELETE_WINDOW", self.annuler)

    def boutons(self, texte_valider="💾 Enregistrer"):
        cadre = tk.Frame(self.pied, bg=COULEURS["bg"])
        cadre.pack()
        Bouton(cadre, texte_valider, "primary", self.valider).pack(side=tk.LEFT, padx=5)
        Bouton(cadre, "Annuler", "secondary", self.annuler).pack(side=tk.LEFT, padx=5)
        self.dialog.bind("<Return>", lambda e: self.valider())

    def attendre(self) -> Any:
        self.dialog.grab_set()
        self.dialog.wait_window()
        return self.result

    def valider(self) -> None:
        raise NotImplementedError

    def annuler(self) -> None:
        self.result = None
        self.dialog.destroy()

    # Helpers de formulaire
    def champ(self, parent, ligne, libelle, valeur="", largeur=32, aide=None):
        tk.Label(parent, text=libelle, font=(POLICE, 10), bg=COULEURS["bg"],
                 fg=COULEURS["text"], anchor="w").grid(row=ligne, column=0, sticky="w", pady=4)
        e = tk.Entry(parent, font=(POLICE, 10), width=largeur, bd=1, relief=tk.SOLID,
                     bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                     insertbackground=COULEURS["input_fg"], highlightthickness=0)
        e.insert(0, "" if valeur is None else str(valeur))
        e.grid(row=ligne, column=1, sticky="ew", padx=(8, 0), pady=4, ipady=3)
        if aide:
            tk.Label(parent, text=aide, font=(POLICE, 8), bg=COULEURS["bg"],
                     fg=COULEURS["text_secondary"]).grid(row=ligne, column=2, sticky="w", padx=6)
        parent.columnconfigure(1, weight=1)
        return e


# ─── CONNEXION ───────────────────────────────────────

class DialogueConnexion:
    """Écran de connexion (fenêtre racine)."""

    def __init__(self, root) -> None:
        self.utilisateur = None
        self.root = root
        root.title("SODIPAC — Connexion")
        root.configure(bg=COULEURS["sidebar"])
        root.resizable(False, False)
        centrer_fenetre(root, 400, 480)

        cadre = tk.Frame(root, bg=COULEURS["sidebar"], padx=40, pady=30)
        cadre.pack(fill=tk.BOTH, expand=True)

        tk.Label(cadre, text="🚗", font=(POLICE, 46),
                 bg=COULEURS["sidebar"], fg="white").pack(pady=(10, 0))
        nom_soc = db.get_parametres().get("entreprise_nom", "SODIPAC")
        tk.Label(cadre, text=nom_soc, font=(POLICE, 22, "bold"),
                 bg=COULEURS["sidebar"], fg="white").pack()
        tk.Label(cadre, text="Gestion de pièces automobiles", font=(POLICE, 9),
                 bg=COULEURS["sidebar"], fg=COULEURS["sidebar_text"]).pack(pady=(0, 24))

        tk.Label(cadre, text="Identifiant", font=(POLICE, 9), bg=COULEURS["sidebar"],
                 fg=COULEURS["sidebar_text"], anchor="w").pack(fill=tk.X)
        self.e_user = tk.Entry(cadre, font=(POLICE, 12), bd=0, bg="white",
                               justify="center", highlightthickness=0)
        self.e_user.pack(fill=tk.X, ipady=7, pady=(3, 12))
        self.e_user.insert(0, "admin")

        tk.Label(cadre, text="Mot de passe", font=(POLICE, 9), bg=COULEURS["sidebar"],
                 fg=COULEURS["sidebar_text"], anchor="w").pack(fill=tk.X)
        self.e_pass = tk.Entry(cadre, font=(POLICE, 12), bd=0, bg="white", show="•",
                               justify="center", highlightthickness=0)
        self.e_pass.pack(fill=tk.X, ipady=7, pady=(3, 6))

        self.lbl_erreur = tk.Label(cadre, text="", font=(POLICE, 9),
                                   bg=COULEURS["sidebar"], fg="#ff8a80")
        self.lbl_erreur.pack(pady=(2, 8))

        Bouton(cadre, "Se connecter", "primary", self._connecter,
               pady=9).pack(fill=tk.X)
        Bouton(cadre, "Quitter", "secondary", root.destroy,
               petit=True, pady=5).pack(fill=tk.X, pady=(8, 0))

        tk.Label(cadre, text="Par défaut : admin / admin123", font=(POLICE, 8),
                 bg=COULEURS["sidebar"], fg=COULEURS["text_secondary"]).pack(side=tk.BOTTOM)

        root.bind("<Return>", lambda e: self._connecter())
        self.e_pass.focus_set()

    def _connecter(self) -> None:
        user, msg = db.authenticate(self.e_user.get().strip(), self.e_pass.get())
        if not user:
            self.lbl_erreur.configure(text=f"⚠ {msg}")
            self.e_pass.delete(0, tk.END)
            return
        self.utilisateur = user
        for enfant in self.root.winfo_children():
            enfant.destroy()
        self.root.unbind("<Return>")
        self.root.resizable(True, True)
        self.root.quit()  # Sortir de mainloop pour passer à l'application


# ─── PRODUIT ─────────────────────────────────────────

