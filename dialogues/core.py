"""Dialogues: core"""
from typing import Any
import tkinter as tk
from tkinter import ttk, messagebox

import database as db
from ui_widgets import COULEURS, POLICE, Bouton, centrer_fenetre

class DialogueBase:
    """Socle commun : modal, centré, Échap = annuler, Entrée = valider."""

    def __init__(self, parent, titre, largeur=580, hauteur=600) -> None:
        self.result = None
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(titre)
        self.dialog.configure(bg=COULEURS["bg"])
        self.dialog.transient(parent)
        self.dialog.resizable(True, True)

        entete = tk.Frame(self.dialog, bg=COULEURS["primary"], height=42)
        entete.pack(fill=tk.X)
        entete.pack_propagate(False)
        tk.Label(entete, text=titre, font=(POLICE, 12, "bold"),
                 bg=COULEURS["primary"], fg="white").pack(side=tk.LEFT, padx=16)

        # Le pied avec les boutons est fixé en bas
        self.pied = tk.Frame(self.dialog, bg=COULEURS["bg"], pady=10)
        self.pied.pack(fill=tk.X, side=tk.BOTTOM)

        # Zone du corps avec défilement intelligent uniquement si nécessaire
        cadre_scroll = tk.Frame(self.dialog, bg=COULEURS["bg"])
        cadre_scroll.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(cadre_scroll, bg=COULEURS["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(cadre_scroll, orient="vertical", command=canvas.yview)
        self.corps = tk.Frame(canvas, bg=COULEURS["bg"], padx=20, pady=12)

        def _sur_ajustement_corps(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            bbox = canvas.bbox("all")
            if bbox and (bbox[3] - bbox[1]) <= canvas.winfo_height() + 5:
                vsb.pack_forget()
            else:
                vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.corps.bind("<Configure>", _sur_ajustement_corps)
        win_id = canvas.create_window((0, 0), window=self.corps, anchor="nw")
        canvas.bind("<Configure>", lambda e: (canvas.itemconfig(win_id, width=e.width), _sur_ajustement_corps(e)))
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        centrer_fenetre(self.dialog, max(largeur, 680), min(hauteur, 720))
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
        parent.columnconfigure(1, weight=1, minsize=200)
        return e


# ─── CONNEXION ───────────────────────────────────────

class DialogueConnexion:
    """Écran de connexion modernisé — Design Slate Dark & Ergonomie haut de gamme."""

    def __init__(self, root) -> None:
        self.utilisateur = None
        self.root = root
        root.title("SODIPAC — Connexion au système")
        root.configure(bg="#0f172a")
        root.resizable(False, False)
        root.geometry("540x650")
        centrer_fenetre(root, 540, 650)

        # Conteneur principal avec défilement si nécessaire mais hauteur calibrée
        cadre_principal = tk.Frame(root, bg="#0f172a", padx=36, pady=20)
        cadre_principal.pack(fill=tk.BOTH, expand=True)

        # ── En-tête Marque & Logo ──
        f_badge = tk.Frame(cadre_principal, bg="#1e293b", padx=14, pady=8, highlightbackground="#334155", highlightthickness=1)
        f_badge.pack(pady=(0, 10))

        tk.Label(f_badge, text="🚗", font=(POLICE, 32), bg="#1e293b", fg="#818cf8").pack()

        nom_soc = db.get_parametres().get("entreprise_nom", "SODIPAC")
        tk.Label(cadre_principal, text=nom_soc, font=(POLICE, 22, "bold"),
                 bg="#0f172a", fg="white").pack()
        tk.Label(cadre_principal, text="Gestion & Distribution de Pièces Automobiles",
                 font=(POLICE, 9), bg="#0f172a", fg="#94a3b8").pack(pady=(2, 12))

        # ── Formulaire de Saisie ──
        f_form = tk.Frame(cadre_principal, bg="#0f172a")
        f_form.pack(fill=tk.X, pady=(0, 6))

        # Identifiant
        tk.Label(f_form, text="👤  Identifiant utilisateur", font=(POLICE, 10, "bold"),
                 bg="#0f172a", fg="#cbd5e1", anchor="w").pack(fill=tk.X, pady=(0, 3))

        self.e_user = tk.Entry(f_form, font=(POLICE, 11), bd=1, relief=tk.SOLID,
                               bg="#1e293b", fg="white", insertbackground="white",
                               justify="center", highlightthickness=1, highlightbackground="#334155")
        self.e_user.pack(fill=tk.X, ipady=6, pady=(0, 10))
        self.e_user.insert(0, "admin")

        # Mot de passe avec toggle Oeil
        tk.Label(f_form, text="🔒  Mot de passe", font=(POLICE, 10, "bold"),
                 bg="#0f172a", fg="#cbd5e1", anchor="w").pack(fill=tk.X, pady=(0, 3))

        f_pass_wrapper = tk.Frame(f_form, bg="#1e293b", highlightbackground="#334155", highlightthickness=1)
        f_pass_wrapper.pack(fill=tk.X, pady=(0, 4))

        self.e_pass = tk.Entry(f_pass_wrapper, font=(POLICE, 11), bd=0, bg="#1e293b",
                               fg="white", insertbackground="white", show="•", justify="center")
        self.e_pass.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, ipady=6, padx=(10, 0))

        self._afficher_mdp = False

        def _basculer_mdp():
            self._afficher_mdp = not self._afficher_mdp
            self.e_pass.configure(show="" if self._afficher_mdp else "•")
            btn_eye.configure(text="👁️" if self._afficher_mdp else "🔒")

        btn_eye = tk.Button(f_pass_wrapper, text="🔒", font=(POLICE, 10), bg="#1e293b", fg="#94a3b8",
                            bd=0, activebackground="#1e293b", activeforeground="white",
                            cursor="hand2", command=_basculer_mdp)
        btn_eye.pack(side=tk.RIGHT, padx=8)

        # Message d'erreur
        self.lbl_erreur = tk.Label(cadre_principal, text="", font=(POLICE, 9, "bold"),
                                   bg="#0f172a", fg="#f87171")
        self.lbl_erreur.pack(pady=(0, 6))

        # ── Boutons d'Action ──
        Bouton(cadre_principal, "🚀  SE CONNECTER  (Entrée)", "primary", self._connecter,
               pady=9).pack(fill=tk.X)

        Bouton(cadre_principal, "❌ Quitter", "secondary", root.destroy,
               petit=True, pady=5, outline=True).pack(fill=tk.X, pady=(8, 0))

        tk.Label(cadre_principal, text="💡 Compte administrateur par défaut : admin / admin123",
                 font=(POLICE, 8), bg="#0f172a", fg="#64748b").pack(side=tk.BOTTOM, pady=(10, 0))

        root.bind("<Return>", lambda e: self._connecter())
        self.e_pass.focus_set()

    def _connecter(self) -> None:
        user, msg = db.authenticate(self.e_user.get().strip(), self.e_pass.get())
        if not user:
            self.lbl_erreur.configure(text=f"⚠️ {msg}")
            self.e_pass.delete(0, tk.END)
            return
        self.utilisateur = user
        for enfant in self.root.winfo_children():
            enfant.destroy()
        self.root.unbind("<Return>")
        self.root.resizable(True, True)
        self.root.quit()  # Sortir de mainloop pour passer à l'application


# ─── PRODUIT ─────────────────────────────────────────

