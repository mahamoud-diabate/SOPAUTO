"""
SOPAUTO - Fournisseurs
"""
import tkinter as tk
from tkinter import messagebox

import database as db
from dialogues import DialogueFournisseur
from ui_widgets import (COULEURS, Bouton, EntreeRecherche, TableauTriable,
                        ajouter_scrollbars, zebre)


class FournisseursMixin:
    """Gestion des fournisseurs — contacts, délais, dettes.

    Solde calculé automatiquement depuis les commandes non réglées.
    """

    def afficher_fournisseurs(self):
        if not self.peut("produits"):
            return self._refus()
        self._nouvelle_page("Fournisseurs", 6)
        Bouton(self.zone_actions, "Nouveau fournisseur", "primary",
               self._nouveau_fournisseur, petit=True).pack(side=tk.LEFT, padx=3)

        barre = tk.Frame(self.zone, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        self.rech_fournisseurs = EntreeRecherche(barre, "Nom, contact, téléphone…", 34,
                                                 callback=self._charger_fournisseurs)
        self.rech_fournisseurs.pack(side=tk.LEFT)

        cadre = tk.Frame(self.zone, bg=COULEURS["card"])
        cadre.pack(fill=tk.BOTH, expand=True)
        self.tab_fournisseurs = TableauTriable(cadre, [
            ("nom", "Nom / Société", 210, "w", False),
            ("contact", "Contact", 160, "w", False),
            ("tel", "Téléphone", 130, "w", False),
            ("email", "Email", 200, "w", False),
            ("adresse", "Adresse", 230, "w", False),
            ("nb", "Produits", 80, "center", True)])
        ajouter_scrollbars(cadre, self.tab_fournisseurs)
        self.tab_fournisseurs.bind("<Double-1>", lambda e: self._modifier_fournisseur())

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Modifier", command=self._modifier_fournisseur)
        menu.add_command(label="Supprimer", command=self._supprimer_fournisseur)

        def clic_droit(e):
            iid = self.tab_fournisseurs.identify_row(e.y)
            if iid:
                self.tab_fournisseurs.selection_set(iid)
                menu.tk_popup(e.x_root, e.y_root)

        self.tab_fournisseurs.bind("<Button-3>", clic_droit)
        self._charger_fournisseurs()


    def _charger_fournisseurs(self):
        produits = db.get_produits()
        compte = {}
        for p in produits:
            if p["fournisseur_id"]:
                compte[p["fournisseur_id"]] = compte.get(p["fournisseur_id"], 0) + 1
        t = self.tab_fournisseurs
        t.delete(*t.get_children())
        for i, f in enumerate(db.get_fournisseurs(self.rech_fournisseurs.get())):
            t.insert("", tk.END, iid=f["id"], tags=zebre(i), values=(
                f["nom"], f["contact"], f["telephone"], f["email"], f["adresse"],
                compte.get(f["id"], 0)))


    def _nouveau_fournisseur(self):
        d = DialogueFournisseur(self.root)
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            self._charger_fournisseurs()


    def _modifier_fournisseur(self):
        sel = self.tab_fournisseurs.selection()
        if not sel:
            return
        f = next((x for x in db.get_fournisseurs() if x["id"] == int(sel[0])), None)
        if f:
            d = DialogueFournisseur(self.root, f)
            if d.attendre():
                self.statut(d.result, COULEURS["success"])
                self._charger_fournisseurs()


    def _supprimer_fournisseur(self):
        if not self.peut("supprimer"):
            return self._refus()
        sel = self.tab_fournisseurs.selection()
        if sel and messagebox.askyesno("Confirmer", "Supprimer ce fournisseur ?", parent=self.root):
            ok, msg = db.delete_fournisseur(int(sel[0]))
            messagebox.showinfo("Résultat", msg, parent=self.root)
            self._charger_fournisseurs()

    # ═══ MOUVEMENTS ════════════════════════════════════


