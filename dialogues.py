"""
SODIPAC - Fenêtres de dialogue (connexion, formulaires, mouvements, paiement)
"""

import tkinter as tk
from tkinter import ttk, messagebox

import database as db
from ui_widgets import (COULEURS, POLICE, Bouton, AutocompleteCombobox,
                        centrer_fenetre, fmt_money)
from typing import Any


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

class DialogueProduit(DialogueBase):
    def __init__(self, parent, produit=None) -> None:
        titre = "✏️ Modifier le produit" if produit else "➕ Nouveau produit"
        super().__init__(parent, titre, 680, 720)
        self.produit = produit
        self.categories = db.get_categories()
        self.fournisseurs = db.get_fournisseurs()

        p = produit or {}
        f = self.corps
        r = 0

        self.e_ref = self.champ(f, r, "Référence *", p.get("reference", ""),
                                aide="unique"); r += 1
        if not produit:
            Bouton(f, "Générer", "info", self._generer_ref, petit=True).grid(
                row=r, column=1, sticky="w", pady=(0, 4)); r += 1

        self.e_nom = self.champ(f, r, "Désignation *", p.get("nom", "")); r += 1
        self.e_marque = self.champ(f, r, "Marque", p.get("marque", "")); r += 1
        self.e_cb = self.champ(f, r, "Code-barres", p.get("code_barres", ""),
                               aide="scan"); r += 1

        # Catégorie
        tk.Label(f, text="Catégorie", font=(POLICE, 10), bg=COULEURS["bg"],
                 anchor="w").grid(row=r, column=0, sticky="w", pady=4)
        self.cb_cat = ttk.Combobox(f, state="readonly", font=(POLICE, 10),
                                   values=[""] + [c["nom"] for c in self.categories])
        self.cb_cat.grid(row=r, column=1, sticky="ew", padx=(8, 0), pady=4)
        if p.get("categorie_nom"):
            self.cb_cat.set(p["categorie_nom"])
        r += 1

        # Fournisseur
        tk.Label(f, text="Fournisseur", font=(POLICE, 10), bg=COULEURS["bg"],
                 anchor="w").grid(row=r, column=0, sticky="w", pady=4)
        self.cb_four = ttk.Combobox(f, state="readonly", font=(POLICE, 10),
                                    values=[""] + [x["nom"] for x in self.fournisseurs])
        self.cb_four.grid(row=r, column=1, sticky="ew", padx=(8, 0), pady=4)
        if p.get("fournisseur_nom"):
            self.cb_four.set(p["fournisseur_nom"])
        r += 1

        ttk.Separator(f, orient="horizontal").grid(row=r, column=0, columnspan=3,
                                                   sticky="ew", pady=8); r += 1

        devise = db.get_devise()
        self.e_pa = self.champ(f, r, f"Prix d'achat ({devise})", p.get("prix_achat", 0)); r += 1
        self.e_pv = self.champ(f, r, f"Prix de vente ({devise})", p.get("prix_vente", 0)); r += 1

        self.lbl_marge = tk.Label(f, text="", font=(POLICE, 9, "bold"),
                                  bg=COULEURS["bg"], fg=COULEURS["success"])
        self.lbl_marge.grid(row=r, column=1, sticky="w", pady=(0, 4)); r += 1
        for e in (self.e_pa, self.e_pv):
            e.bind("<KeyRelease>", lambda ev: self._maj_marge())
        self._maj_marge()

        if produit:
            tk.Label(f, text="Stock réserve", font=(POLICE, 10), bg=COULEURS["bg"],
                     anchor="w").grid(row=r, column=0, sticky="w", pady=4)
            tk.Label(f, text=f"{p.get('stock_reserve', 0)} — transferable via Stock",
                     font=(POLICE, 10, "bold"), bg=COULEURS["bg"],
                     fg=COULEURS["info"]).grid(row=r, column=1, sticky="w", padx=(8, 0))
            r += 1
            tk.Label(f, text="Stock vente", font=(POLICE, 10), bg=COULEURS["bg"],
                     anchor="w").grid(row=r, column=0, sticky="w", pady=4)
            tk.Label(f, text=f"{p.get('stock_vente', 0)} — modifiable via Stock",
                     font=(POLICE, 10, "bold"), bg=COULEURS["bg"],
                     fg=COULEURS["info"]).grid(row=r, column=1, sticky="w", padx=(8, 0))
            r += 1
        else:
            self.e_stock_reserve = self.champ(f, r, "Stock réserve (entrepôt)", 0); r += 1
            self.e_stock_vente = self.champ(f, r, "Stock vente (rayon)", 0); r += 1

        self.e_mini = self.champ(f, r, "Seuil d'alerte", p.get("stock_mini", 5),
                                 aide="alerte si stock ≤ seuil"); r += 1
        self.e_emp = self.champ(f, r, "Emplacement", p.get("emplacement", ""),
                                aide="ex : Rayon A3"); r += 1
        self.e_desc = self.champ(f, r, "Description", p.get("description", "")); r += 1

        self.var_actif = tk.BooleanVar(value=bool(p.get("actif", 1)))
        tk.Checkbutton(f, text="Produit actif (visible en caisse)", variable=self.var_actif,
                       bg=COULEURS["bg"], font=(POLICE, 9), anchor="w",
                       activebackground=COULEURS["bg"]).grid(row=r, column=1, sticky="w",
                                                             padx=(8, 0), pady=6)

        self.boutons()
        self.e_ref.focus_set()

    def _generer_ref(self) -> None:
        cat_id = self._id_categorie()
        self.e_ref.delete(0, tk.END)
        self.e_ref.insert(0, db.suggerer_reference(cat_id))

    def _maj_marge(self) -> None:
        try:
            pa = float(self.e_pa.get().replace(",", ".") or 0)
            pv = float(self.e_pv.get().replace(",", ".") or 0)
        except ValueError:
            self.lbl_marge.configure(text="valeurs invalides", fg=COULEURS["danger"])
            return
        marge = pv - pa
        pct = (marge / pa * 100) if pa else 0
        couleur = COULEURS["success"] if marge > 0 else COULEURS["danger"]
        self.lbl_marge.configure(
            text=f"Marge : {fmt_money(marge, db.get_devise())} ({pct:+.1f} %)", fg=couleur)

    def _id_categorie(self) -> int | None:
        nom = self.cb_cat.get()
        return next((c["id"] for c in self.categories if c["nom"] == nom), None)

    def _id_fournisseur(self) -> int | None:
        nom = self.cb_four.get()
        return next((x["id"] for x in self.fournisseurs if x["nom"] == nom), None)

    def valider(self) -> None:
        def nombre(entry, entier=False, defaut=0):
            texte = entry.get().replace(" ", "").replace(",", ".").strip()
            if not texte:
                return defaut
            return int(float(texte)) if entier else float(texte)

        try:
            pa, pv = nombre(self.e_pa), nombre(self.e_pv)
            mini = nombre(self.e_mini, True, 5)
            stock_reserve = nombre(self.e_stock_reserve, True) if not self.produit else None
            stock_vente = nombre(self.e_stock_vente, True) if not self.produit else None
        except ValueError:
            messagebox.showerror("Erreur", "Les prix et quantités doivent être numériques.",
                                 parent=self.dialog)
            return

        if pv < pa and pv > 0:
            if not messagebox.askyesno(
                    "Vente à perte",
                    f"Le prix de vente ({fmt_money(pv)}) est inférieur au prix d'achat "
                    f"({fmt_money(pa)}).\n\nContinuer quand même ?", parent=self.dialog):
                return

        commun = dict(description=self.e_desc.get().strip(),
                      categorie_id=self._id_categorie(),
                      fournisseur_id=self._id_fournisseur(),
                      marque=self.e_marque.get().strip(),
                      prix_achat=pa, prix_vente=pv, stock_mini=mini,
                      emplacement=self.e_emp.get().strip(),
                      code_barres=self.e_cb.get().strip(),
                      actif=1 if self.var_actif.get() else 0)

        ref, nom = self.e_ref.get().strip(), self.e_nom.get().strip()
        if self.produit:
            ok, msg = db.update_produit(self.produit["id"], ref, nom, **commun)
        else:
            ok, msg = db.add_produit(ref, nom, stock_reserve=stock_reserve,
                                     stock_vente=stock_vente, **commun)

        if ok:
            self.result = msg
            self.dialog.destroy()
        else:
            messagebox.showerror("Erreur", msg, parent=self.dialog)


# ─── CATÉGORIE / FOURNISSEUR / CLIENT ────────────────

class DialogueCategorie(DialogueBase):
    def __init__(self, parent, categorie=None) -> None:
        super().__init__(parent, "✏️ Modifier la catégorie" if categorie else "➕ Nouvelle catégorie",
                         460, 280)
        self.categorie = categorie
        c = categorie or {}
        self.e_nom = self.champ(self.corps, 0, "Nom *", c.get("nom", ""))
        self.e_desc = self.champ(self.corps, 1, "Description", c.get("description", ""))
        self.boutons()
        self.e_nom.focus_set()

    def valider(self) -> None:
        nom = self.e_nom.get().strip()
        desc = self.e_desc.get().strip()
        if self.categorie:
            ok, msg = db.update_categorie(self.categorie["id"], nom, desc)
        else:
            ok, msg = db.add_categorie(nom, desc)
        if ok:
            self.result = msg
            self.dialog.destroy()
        else:
            messagebox.showerror("Erreur", msg, parent=self.dialog)


class DialogueFournisseur(DialogueBase):
    def __init__(self, parent, fournisseur=None) -> None:
        super().__init__(parent, "✏️ Modifier le fournisseur" if fournisseur else "➕ Nouveau fournisseur",
                         520, 380)
        self.fournisseur = fournisseur
        f = fournisseur or {}
        self.e_nom = self.champ(self.corps, 0, "Nom / Société *", f.get("nom", ""))
        self.e_contact = self.champ(self.corps, 1, "Personne de contact", f.get("contact", ""))
        self.e_tel = self.champ(self.corps, 2, "Téléphone", f.get("telephone", ""))
        self.e_mail = self.champ(self.corps, 3, "Email", f.get("email", ""))
        self.e_adr = self.champ(self.corps, 4, "Adresse", f.get("adresse", ""))
        self.boutons()
        self.e_nom.focus_set()

    def valider(self) -> None:
        args = (self.e_nom.get().strip(), self.e_contact.get().strip(),
                self.e_tel.get().strip(), self.e_mail.get().strip(), self.e_adr.get().strip())
        if not args[0]:
            messagebox.showerror("Erreur", "Le nom est requis.", parent=self.dialog)
            return
        if self.fournisseur:
            ok, msg = db.update_fournisseur(self.fournisseur["id"], *args)
        else:
            ok, msg = db.add_fournisseur(*args)
        if ok:
            self.result = msg
            self.dialog.destroy()
        else:
            messagebox.showerror("Erreur", msg, parent=self.dialog)


class DialogueClient(DialogueBase):
    def __init__(self, parent, client=None) -> None:
        super().__init__(parent, "✏️ Modifier le client" if client else "➕ Nouveau client",
                         520, 420)
        self.client = client
        c = client or {}
        self.e_nom = self.champ(self.corps, 0, "Nom *", c.get("nom", ""))
        self.e_tel = self.champ(self.corps, 1, "Téléphone", c.get("telephone", ""))
        self.e_mail = self.champ(self.corps, 2, "Email", c.get("email", ""))
        self.e_adr = self.champ(self.corps, 3, "Adresse", c.get("adresse", ""))
        self.e_veh = self.champ(self.corps, 4, "Véhicule", c.get("vehicule", ""),
                                aide="ex : Toyota Corolla 2015")
        self.e_notes = self.champ(self.corps, 5, "Notes", c.get("notes", ""))
        self.boutons()
        self.e_nom.focus_set()

    def valider(self) -> None:
        args = (self.e_nom.get().strip(), self.e_tel.get().strip(), self.e_mail.get().strip(),
                self.e_adr.get().strip(), self.e_veh.get().strip(), self.e_notes.get().strip())
        if not args[0]:
            messagebox.showerror("Erreur", "Le nom est requis.", parent=self.dialog)
            return
        if self.client:
            ok, msg = db.update_client(self.client["id"], *args)
        else:
            ok, msg = db.add_client(*args)
        if ok:
            self.result = msg
            self.dialog.destroy()
        else:
            messagebox.showerror("Erreur", msg, parent=self.dialog)


# ─── MOUVEMENT DE STOCK ──────────────────────────────

class DialogueMouvement(DialogueBase):
    LIBELLES = {"entree": ("📥 Entrée de stock", "success"),
                "sortie": ("📤 Sortie de stock", "danger"),
                "correction": ("🔧 Correction d'inventaire", "warning"),
                "transfert": ("🔄 Transfert réserve ↔ vente", "info")}

    def __init__(self, parent, type_mvt, produit_id=None) -> None:
        titre, couleur = self.LIBELLES[type_mvt]
        super().__init__(parent, titre, 600, 500)
        self.type_mvt = type_mvt
        self.cible = None  # reserve / vente pour transfert ou entree/sortie ciblée
        self.produits = db.get_produits(inclure_inactifs=False)

        f = self.corps
        r = 0

        tk.Label(f, text="Produit *", font=(POLICE, 10), bg=COULEURS["bg"],
                 anchor="w").grid(row=r, column=0, sticky="w", pady=4)
        self.cb_prod = AutocompleteCombobox(f, font=(POLICE, 10), width=42)
        self._etiquettes = {f"{p['reference']} — {p['nom']} (R:{p['stock_reserve']} V:{p['stock_vente']})": p
                            for p in self.produits}
        self.cb_prod.set_completion_list(list(self._etiquettes))
        self.cb_prod.grid(row=r, column=1, sticky="ew", padx=(8, 0), pady=4)
        f.columnconfigure(1, weight=1)
        r += 1

        if produit_id:
            for etiquette, p in self._etiquettes.items():
                if p["id"] == produit_id:
                    self.cb_prod.set(etiquette)
                    break

        self.lbl_info = tk.Label(f, text="", font=(POLICE, 9), bg=COULEURS["bg"],
                                 fg=COULEURS["info"], justify="left")
        self.lbl_info.grid(row=r, column=1, sticky="w", padx=(8, 0))
        r += 1
        self.cb_prod.bind("<<ComboboxSelected>>", lambda e: self._maj_info())

        # Sélecteur d'emplacement (réserve / vente) — inutile pour un transfert
        # qui a son propre sélecteur de direction.
        self.var_emp = tk.StringVar(value="vente")
        if type_mvt != "transfert":
            cadre_emp = tk.Frame(f, bg=COULEURS["bg"])
            cadre_emp.grid(row=r, column=0, columnspan=2, sticky="w", pady=4)
            tk.Label(cadre_emp, text="Emplacement :", font=(POLICE, 10),
                     bg=COULEURS["bg"]).pack(side=tk.LEFT)
            tk.Radiobutton(cadre_emp, text="Vente (rayon)", variable=self.var_emp, value="vente",
                           bg=COULEURS["bg"], font=(POLICE, 9), command=self._maj_info,
                           activebackground=COULEURS["bg"]).pack(side=tk.LEFT, padx=(8, 2))
            tk.Radiobutton(cadre_emp, text="Réserve (entrepôt)", variable=self.var_emp, value="reserve",
                           bg=COULEURS["bg"], font=(POLICE, 9), command=self._maj_info,
                           activebackground=COULEURS["bg"]).pack(side=tk.LEFT, padx=2)
            r += 1

        if type_mvt == "transfert":
            # Pour transfert, on affiche la direction
            self.var_dir = tk.StringVar(value="vente")
            cadre_dir = tk.Frame(f, bg=COULEURS["bg"])
            cadre_dir.grid(row=r, column=0, columnspan=2, sticky="w", pady=4)
            tk.Label(cadre_dir, text="Direction :", font=(POLICE, 10),
                     bg=COULEURS["bg"]).pack(side=tk.LEFT)
            tk.Radiobutton(cadre_dir, text="Réserve → Vente", variable=self.var_dir, value="vente",
                           bg=COULEURS["bg"], font=(POLICE, 9),
                           activebackground=COULEURS["bg"],
                           command=self._maj_info).pack(side=tk.LEFT, padx=(8, 2))
            tk.Radiobutton(cadre_dir, text="Vente → Réserve", variable=self.var_dir, value="reserve",
                           bg=COULEURS["bg"], font=(POLICE, 9),
                           activebackground=COULEURS["bg"],
                           command=self._maj_info).pack(side=tk.LEFT, padx=2)
            r += 1

        libelle_qte = "Nouveau stock réel *" if type_mvt == "correction" else "Quantité *"
        self.e_qte = self.champ(f, r, libelle_qte, 1); r += 1
        self.e_prix = self.champ(f, r, f"Prix unitaire ({db.get_devise()})", 0,
                                 aide="met à jour le prix d'achat" if type_mvt == "entree" else None); r += 1
        self.e_doc = self.champ(f, r, "Réf. document", "", aide="facture, bon de livraison…"); r += 1
        self.e_notes = self.champ(f, r, "Motif / Notes", ""); r += 1

        if type_mvt == "correction":
            tk.Label(f, text="ℹ️ Saisissez le stock physiquement compté pour l'emplacement sélectionné.",
                     font=(POLICE, 9), bg=COULEURS["bg"], fg=COULEURS["text_secondary"],
                     justify="left").grid(row=r, column=0, columnspan=2, sticky="w", pady=4)
        elif type_mvt == "transfert":
            tk.Label(f, text="ℹ️ Quantité à déplacer entre réserve et rayon de vente.",
                     font=(POLICE, 9), bg=COULEURS["bg"], fg=COULEURS["text_secondary"],
                     justify="left").grid(row=r, column=0, columnspan=2, sticky="w", pady=4)

        self.boutons("✅ Valider le mouvement")
        self._maj_info()
        self.cb_prod.focus_set()

    def _produit_selectionne(self) -> dict | None:
        return self._etiquettes.get(self.cb_prod.get())

    def _maj_info(self) -> None:
        p = self._produit_selectionne()
        if not p:
            self.lbl_info.configure(text="")
            return
        if self.type_mvt == "transfert":
            direction = self.var_dir.get()
            source = "réserve" if direction == "vente" else "vente"
            dest = "vente" if direction == "vente" else "réserve"
            dispo = p["stock_reserve"] if direction == "vente" else p["stock_vente"]
            self.lbl_info.configure(
                text=f"Réserve : {p['stock_reserve']}  •  Vente : {p['stock_vente']}  •  "
                     f"Disponible pour {source} → {dest} : {dispo}")
        else:
            emp = self.var_emp.get()
            stock_emp = p["stock_reserve"] if emp == "reserve" else p["stock_vente"]
            nom_emp = "réserve" if emp == "reserve" else "vente"
            self.lbl_info.configure(
                text=f"Stock {nom_emp} : {stock_emp}  •  Stock total : {p['stock']}  •  "
                     f"Seuil : {p['stock_mini']}  •  "
                     f"P.A. : {fmt_money(p['prix_achat'], db.get_devise())}")
        if self.type_mvt == "entree":
            try:
                prix_actuel = float(self.e_prix.get().replace(",", ".") or 0)
            except ValueError:
                prix_actuel = 0
            if not prix_actuel:
                self.e_prix.delete(0, tk.END)
                self.e_prix.insert(0, f"{p['prix_achat']:.0f}")

    def valider(self) -> None:
        p = self._produit_selectionne()
        if not p:
            messagebox.showerror("Erreur", "Sélectionnez un produit dans la liste.",
                                 parent=self.dialog)
            return
        try:
            qte = int(float(self.e_qte.get().replace(",", ".")))
            prix = float(self.e_prix.get().replace(",", ".") or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Quantité ou prix invalide.", parent=self.dialog)
            return

        if self.type_mvt == "transfert":
            cible = self.var_dir.get()
            ok, msg = db.add_mouvement(p["id"], "transfert", qte, 0,
                                       self.e_doc.get().strip(),
                                       self.e_notes.get().strip(),
                                       cible=cible)
        else:
            cible = self.var_emp.get()
            ok, msg = db.add_mouvement(p["id"], self.type_mvt, qte, prix,
                                       self.e_doc.get().strip(),
                                       self.e_notes.get().strip(),
                                       cible=cible)
        if ok:
            self.result = msg
            self.dialog.destroy()
        else:
            messagebox.showerror("Impossible", msg, parent=self.dialog)




# ─── PAIEMENT / ENCAISSEMENT ─────────────────────────

class DialoguePaiement(DialogueBase):
    '''Encaissement : prix reel par ligne, negociation article par article.'''

    MODES = ["Especes", "Orange Money", "Wave", "MTN Money", "Moov Money",
             "Carte bancaire", "Virement", "Cheque", "Credit"]

    def __init__(self, parent, sous_total, items, clients=None) -> None:
        n_lignes = len(items)
        hauteur = 80 + min(n_lignes, 6) * 72 + 380
        super().__init__(parent, " Encaissement", 860, hauteur)
        self.items = items
        self.clients = clients or []
        self.devise = db.get_devise()

        for l in self.items:
            l["prix_reel"] = l.get("prix_reel") or l["pu"]

        f = self.corps

        # Client
        tk.Label(f, text="Client", font=(POLICE, 10), bg=COULEURS["bg"],
                 anchor="w").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))
        self.cb_client = AutocompleteCombobox(f, font=(POLICE, 10), width=28)
        self._etiq_clients = {c["nom"] + (" - " + c["telephone"] if c["telephone"] else ""): c
                              for c in self.clients}
        self.cb_client.set_completion_list(["Client de passage"] + list(self._etiq_clients))
        self.cb_client.set("Client de passage")
        self.cb_client.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 2))
        f.columnconfigure(2, weight=1)
        self.lbl_dette = tk.Label(f, text="", font=(POLICE, 8), bg=COULEURS["bg"],
                                  fg=COULEURS["warning"], anchor="w")
        self.lbl_dette.grid(row=2, column=0, columnspan=3, sticky="w")

        # Lignes avec prix reel
        self._lignes = []
        start_row = 3
        for idx, l in enumerate(self.items):
            bg_ligne = COULEURS.get("row_alt", COULEURS["bg"]) if idx % 2 == 0 else COULEURS["bg"]
            lf = tk.Frame(f, bg=bg_ligne)
            lf.grid(row=start_row + idx, column=0, columnspan=3, sticky="ew", pady=1, ipady=4)

            infos = tk.Frame(lf, bg=bg_ligne)
            infos.pack(side=tk.LEFT, padx=8)
            tk.Label(infos, text=l["nom"], font=(POLICE, 10, "bold"),
                     bg=bg_ligne, fg=COULEURS["text"]).pack(anchor="w")
            qte_pu = "Qte %d x %s" % (l["quantite"], fmt_money(l["pu"], self.devise))
            tk.Label(infos, text=qte_pu, font=(POLICE, 8),
                     bg=bg_ligne, fg=COULEURS["text_secondary"]).pack(anchor="w")

            ctrl = tk.Frame(lf, bg=bg_ligne)
            ctrl.pack(side=tk.RIGHT, padx=8)
            tk.Label(ctrl, text="Prix reel :", font=(POLICE, 9),
                     bg=bg_ligne, fg=COULEURS["warning"]).pack(side=tk.LEFT)
            var = tk.StringVar(value="%d" % l["prix_reel"])
            entry = tk.Entry(ctrl, textvariable=var, font=(POLICE, 12, "bold"), width=10,
                             bd=1, relief=tk.SOLID, justify="right",
                             bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                             insertbackground=COULEURS["input_fg"])
            entry.pack(side=tk.LEFT, padx=(4, 0), ipady=2)
            Bouton(ctrl, "cat.", "secondary",
                   lambda i=idx: self._reset_prix(i), petit=True).pack(side=tk.LEFT, padx=(4, 0))

            cout_ligne = 0.0
            try:
                p = db.get_produit(l.get("id", 0))
                if p:
                    cout_ligne = float(p.get("cump") or p.get("prix_achat") or 0) * l["quantite"]
            except Exception:
                pass

            self._lignes.append({
                "idx": idx, "entry": entry, "var": var, "cout": cout_ligne,
                "qte": l["quantite"], "pu_catalogue": l["pu"]
            })
            entry.bind("<KeyRelease>", lambda e, i=idx: self._recalculer())

        sep_row = start_row + n_lignes
        ttk.Separator(f, orient="horizontal").grid(row=sep_row, column=0, columnspan=3, sticky="ew", pady=8)

        tk.Label(f, text="Mode de paiement", font=(POLICE, 10), bg=COULEURS["bg"],
                 anchor="w").grid(row=sep_row + 1, column=0, sticky="w", pady=4)
        self.cb_mode = ttk.Combobox(f, state="readonly", font=(POLICE, 10),
                                    values=self.MODES, width=18)
        self.cb_mode.current(0)
        self.cb_mode.grid(row=sep_row + 1, column=1, sticky="w", padx=(8, 0), pady=4)

        tk.Label(f, text="Montant recu du client", font=(POLICE, 10, "bold"),
                 bg=COULEURS["bg"], fg=COULEURS["success"]).grid(
            row=sep_row + 2, column=0, sticky="w", pady=(4, 2))
        cadre_paye = tk.Frame(f, bg=COULEURS["bg"])
        cadre_paye.grid(row=sep_row + 2, column=1, columnspan=2, sticky="w", padx=(8, 0))
        self.e_paye = tk.Entry(cadre_paye, font=(POLICE, 15, "bold"), width=12,
                               bd=1, relief=tk.SOLID, justify="right",
                               bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                               insertbackground=COULEURS["input_fg"])
        self.e_paye.pack(side=tk.LEFT, ipady=4)
        self.e_paye.bind("<KeyRelease>", lambda e: self._recalculer())
        self._btns_billets = []
        for montant in (1000, 2000, 5000, 10000):
            b = Bouton(cadre_paye, "+%dk" % (montant // 1000), "secondary",
                       lambda m=montant: self._ajouter(m), petit=True)
            b.pack(side=tk.LEFT, padx=(4, 0))
            self._btns_billets.append(b)
        b = Bouton(cadre_paye, "= total reel", "info",
                   self._montant_exact, petit=True)
        b.pack(side=tk.LEFT, padx=(8, 0))
        self._btns_billets.append(b)

        recap_row = sep_row + 3
        recap = tk.Frame(f, bg=COULEURS["total_bg"], highlightbackground=COULEURS["border"],
                         highlightthickness=1)
        recap.grid(row=recap_row, column=0, columnspan=3, sticky="ew", pady=8)
        self.lbl_recap = tk.Label(recap, text="", font=(POLICE, 12, "bold"),
                                  bg=COULEURS["total_bg"], fg=COULEURS["text"])
        self.lbl_recap.pack(anchor="w", padx=12, pady=(8, 2))
        self.lbl_remise = tk.Label(recap, text="", font=(POLICE, 9),
                                   bg=COULEURS["total_bg"], fg=COULEURS["warning"])
        self.lbl_remise.pack(anchor="w", padx=12, pady=(0, 2))
        self.lbl_cout = tk.Label(recap, text="", font=(POLICE, 9, "bold"),
                                 bg=COULEURS["total_bg"], fg=COULEURS["danger"])
        self.lbl_cout.pack(anchor="w", padx=12)
        self.lbl_rendu = tk.Label(recap, text="", font=(POLICE, 16, "bold"),
                                  bg=COULEURS["total_bg"], fg=COULEURS["success"])
        self.lbl_rendu.pack(anchor="w", padx=12, pady=(2, 8))

        self.var_imprimer = tk.BooleanVar(value=True)
        tk.Checkbutton(f, text="Imprimer le recu apres validation", variable=self.var_imprimer,
                       bg=COULEURS["bg"], font=(POLICE, 9),
                       activebackground=COULEURS["bg"]).grid(row=recap_row + 1, column=0, columnspan=3,
                                                             sticky="w", pady=4)
        self.boutons("Encaisser (F8)")
        self.dialog.bind("<F8>", lambda e: self.valider())
        self._recalculer()

    def _valeur(self, entry, defaut=0.0) -> float:
        try:
            return float(entry.get().replace(" ", "").replace(",", ".") or defaut)
        except ValueError:
            return defaut

    def _client_choisi(self):
        return self._etiq_clients.get(self.cb_client.get().strip())

    def _maj_client(self) -> None:
        client = self._client_choisi()
        t = ""
        if client:
            try:
                import metier_v3
                du = metier_v3.solde_client(client["id"])
                if du > 0:
                    t = "Ce client doit deja " + fmt_money(du, self.devise)
                    plafond = client.get("plafond_credit")
                    if plafond:
                        t += "  (plafond credit: " + fmt_money(plafond, self.devise) + ")"
            except Exception:
                pass
        self.lbl_dette.configure(text=t)
        self._recalculer()

    def _reset_prix(self, idx):
        d = self._lignes[idx]
        d["entry"].delete(0, tk.END)
        d["entry"].insert(0, "%d" % d["pu_catalogue"])
        self._recalculer()

    def _ajouter(self, montant) -> None:
        self.e_paye.delete(0, tk.END)
        self.e_paye.insert(0, "%d" % (self._valeur(self.e_paye) + montant))
        self._recalculer()

    def _montant_exact(self) -> None:
        val = self._prix_reel_total()
        self.e_paye.delete(0, tk.END)
        self.e_paye.insert(0, "%d" % max(0, val))
        self._recalculer()

    def _prix_reel_total(self) -> float:
        return sum(self._valeur(d["entry"]) * d["qte"] for d in self._lignes)

    def _prix_catalogue_total(self) -> float:
        return sum(d["pu_catalogue"] * d["qte"] for d in self._lignes)

    def _recalculer(self) -> None:
        devise = self.devise
        cat_total = self._prix_catalogue_total()
        reel_total = self._prix_reel_total()
        remise = max(0.0, cat_total - reel_total)
        paye = self._valeur(self.e_paye)
        rendu = paye - reel_total
        cout_total = sum(d["cout"] for d in self._lignes)

        t = "Total catalogue: %s  ->  Net reel: %s" % (
            fmt_money(cat_total, devise), fmt_money(reel_total, devise))
        self.lbl_recap.configure(text=t)

        if remise > 0 and cat_total > 0:
            self.lbl_remise.configure(
                text="Remise totale: %s (%.1f %%)" % (
                    fmt_money(remise, devise), remise / cat_total * 100),
                fg=COULEURS["warning"])
        else:
            self.lbl_remise.configure(text="Aucune remise", fg=COULEURS["secondary"])

        if cout_total > 0 and 0 < reel_total < cout_total:
            self.lbl_cout.configure(
                text="SOUS LE COUT DE REVIENT (%s) - perte %s" % (
                    fmt_money(cout_total, devise),
                    fmt_money(cout_total - reel_total, devise)))
        else:
            self.lbl_cout.configure(text="")

        if remise > cat_total:
            self.lbl_rendu.configure(text="Remise superieure au total catalogue",
                                     fg=COULEURS["danger"])
        elif self.cb_mode.get() == "Credit":
            client = self._client_choisi()
            txt = "Vente a credit - paiement differe"
            if not client:
                txt = "Credit: choisissez un client enregistre"
            self.lbl_rendu.configure(text=txt, fg=COULEURS["warning"])
        elif rendu >= 0:
            self.lbl_rendu.configure(text="Monnaie a rendre: " + fmt_money(rendu, devise),
                                     fg=COULEURS["success"])
        else:
            self.lbl_rendu.configure(text="Manque " + fmt_money(-rendu, devise),
                                     fg=COULEURS["danger"])

    def valider(self) -> None:
        items_reels = []
        reel_total = 0.0
        cat_total = self._prix_catalogue_total()
        for d in self._lignes:
            pr = max(0.0, self._valeur(d["entry"]))
            if pr <= 0:
                nom = self.items[d["idx"]]["nom"]
                messagebox.showerror("Erreur",
                                     "Le prix reel de " + nom + " doit etre superieur a 0.",
                                     parent=self.dialog)
                return
            items_reels.append((self.items[d["idx"]]["id"], d["qte"], round(pr, 0)))
            reel_total += pr * d["qte"]

        remise = max(0.0, cat_total - reel_total)
        paye = self._valeur(self.e_paye)
        mode = self.cb_mode.get()

        if remise > cat_total:
            messagebox.showerror("Erreur", "La remise totale depasse le montant catalogue.",
                                 parent=self.dialog)
            return
        if mode == "Credit" and not self._client_choisi():
            messagebox.showerror("Client requis",
                                 "Une vente a credit doit etre liee a un client enregistre.",
                                 parent=self.dialog)
            return
        if mode != "Credit" and paye < reel_total:
            msg = "Le client donne %s pour un total reel de %s." % (
                fmt_money(paye, self.devise), fmt_money(reel_total, self.devise))
            messagebox.showerror("Paiement insuffisant", msg, parent=self.dialog)
            return
        cout_total = sum(d["cout"] for d in self._lignes)
        if cout_total > 0 and reel_total < cout_total:
            msg = ("Le total reel (%s) est INFERIEUR au cout de revient (%s)."
                   " Perte: %s. Confirmer quand meme ?") % (
                       fmt_money(reel_total, self.devise),
                       fmt_money(cout_total, self.devise),
                       fmt_money(cout_total - reel_total, self.devise))
            if not messagebox.askyesno("Vente a perte", msg, parent=self.dialog):
                return

        etiquette = self.cb_client.get().strip()
        client = self._etiq_clients.get(etiquette)
        self.result = {
            "items_reels": items_reels,
            "client_nom": client["nom"] if client else (etiquette or "Client de passage"),
            "client_id": client["id"] if client else None,
            "remise": remise,
            "mode_paiement": mode,
            "montant_paye": paye if mode != "Credit" else 0,
            "imprimer": self.var_imprimer.get(),
        }
        self.dialog.destroy()


# ─── UTILISATEUR ─────────────────────────────────────

class DialogueUtilisateur(DialogueBase):
    ROLES = ["superviseur", "gerant", "vendeur"]

    def __init__(self, parent, utilisateur=None) -> None:
        super().__init__(parent, "✏️ Modifier l'utilisateur" if utilisateur else "➕ Nouvel utilisateur",
                         500, 380)
        self.utilisateur = utilisateur
        u = utilisateur or {}
        f = self.corps

        self.e_login = self.champ(f, 0, "Identifiant *", u.get("nom_utilisateur", ""))
        if utilisateur:
            self.e_login.configure(state="readonly")
        self.e_nom = self.champ(f, 1, "Nom complet", u.get("nom_complet", ""))

        tk.Label(f, text="Rôle", font=(POLICE, 10), bg=COULEURS["bg"],
                 anchor="w").grid(row=2, column=0, sticky="w", pady=4)
        self.cb_role = ttk.Combobox(f, state="readonly", font=(POLICE, 10), values=self.ROLES)
        self.cb_role.set(u.get("role", "vendeur"))
        self.cb_role.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=4)
        f.columnconfigure(1, weight=1)

        libelle = "Nouveau mot de passe" if utilisateur else "Mot de passe *"
        self.e_pass = self.champ(f, 3, libelle, "",
                                 aide="laisser vide = inchangé" if utilisateur else "4 car. min.")
        self.e_pass.configure(show="•")

        self.var_actif = tk.BooleanVar(value=bool(u.get("actif", 1)))
        tk.Checkbutton(f, text="Compte actif", variable=self.var_actif, bg=COULEURS["bg"],
                       font=(POLICE, 9), activebackground=COULEURS["bg"]).grid(
            row=4, column=1, sticky="w", padx=(8, 0), pady=8)

        tk.Label(f, text="Rôles :\n• superviseur — accès total (admin)\n"
                         "• gerant — stock, produits, rapports\n"
                         "• vendeur — caisse seulement",
                 font=(POLICE, 9), bg=COULEURS["bg"], fg=COULEURS["text_secondary"],
                 justify="left").grid(row=5, column=0, columnspan=2, sticky="w", pady=8)

        self.boutons()

    def valider(self) -> None:
        login = self.e_login.get().strip()
        mdp = self.e_pass.get()
        if self.utilisateur:
            ok, msg = db.update_utilisateur(self.utilisateur["id"], role=self.cb_role.get(),
                                            nom_complet=self.e_nom.get().strip(),
                                            actif=self.var_actif.get(),
                                            mot_de_passe=mdp or None)
        else:
            if not login or not mdp:
                messagebox.showerror("Erreur", "Identifiant et mot de passe requis.",
                                     parent=self.dialog)
                return
            ok, msg = db.add_utilisateur(login, mdp, self.cb_role.get(),
                                         self.e_nom.get().strip())
        if ok:
            self.result = msg
            self.dialog.destroy()
        else:
            messagebox.showerror("Erreur", msg, parent=self.dialog)
