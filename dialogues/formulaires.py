"""Dialogues: formulaires"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import database as db
from ui_widgets import (COULEURS, POLICE, Bouton, AutocompleteCombobox,
                        centrer_fenetre, fmt_money)
from .core import DialogueBase

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


# ═══════════════════════════════════════════════════
# Dialogues v3 (importés depuis pages_v3.py)
# ═══════════════════════════════════════════════════

