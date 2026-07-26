"""
SODIPAC - Catégories
"""
import tkinter as tk
from tkinter import messagebox

import database as db
from dialogues import DialogueCategorie
from ui_widgets import (COULEURS, Bouton, TableauTriable, ajouter_scrollbars,
                        fmt_money, zebre)


class CategoriesMixin:
    """Gestion des catégories de produits (Freinage, Moteur, Suspension…).

    Une catégorie liée à des produits ne peut pas être supprimée.
    """

    def afficher_categories(self):
        if not self.peut("produits"):
            return self._refus()
        self._nouvelle_page("📁 Catégories", 5)
        Bouton(self.zone_actions, "➕ Nouvelle catégorie", "primary",
               self._nouvelle_categorie, petit=True).pack(side=tk.LEFT, padx=3)

        cadre = tk.Frame(self.zone, bg=COULEURS["card"])
        cadre.pack(fill=tk.BOTH, expand=True)
        self.tab_categories = TableauTriable(cadre, [
            ("nom", "Nom", 200, "w", False),
            ("description", "Description", 420, "w", False),
            ("nb", "Produits", 90, "center", True),
            ("valeur", "Valeur du stock", 150, "e", True)])
        ajouter_scrollbars(cadre, self.tab_categories)
        self.tab_categories.bind("<Double-1>", lambda e: self._modifier_categorie())

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="✏️  Modifier", command=self._modifier_categorie)
        menu.add_command(label="🗑️  Supprimer", command=self._supprimer_categorie)

        def clic_droit(e):
            iid = self.tab_categories.identify_row(e.y)
            if iid:
                self.tab_categories.selection_set(iid)
                menu.tk_popup(e.x_root, e.y_root)

        self.tab_categories.bind("<Button-3>", clic_droit)
        self._charger_categories()


    def _charger_categories(self):
        rapport = {r["categorie"]: r for r in db.rapport_stock()["par_categorie"]}
        t = self.tab_categories
        t.delete(*t.get_children())
        for i, c in enumerate(db.get_categories()):
            info = rapport.get(c["nom"], {})
            t.insert("", tk.END, iid=c["id"], tags=zebre(i), values=(
                c["nom"], c["description"], info.get("nb_produits", 0),
                fmt_money(info.get("valeur_achat", 0))))


    def _nouvelle_categorie(self):
        d = DialogueCategorie(self.root)
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            self._charger_categories()


    def _modifier_categorie(self):
        sel = self.tab_categories.selection()
        if not sel:
            return
        cat = next((c for c in db.get_categories() if c["id"] == int(sel[0])), None)
        if cat:
            d = DialogueCategorie(self.root, cat)
            if d.attendre():
                self.statut(d.result, COULEURS["success"])
                self._charger_categories()


    def _supprimer_categorie(self):
        if not self.peut("supprimer"):
            return self._refus()
        sel = self.tab_categories.selection()
        if sel and messagebox.askyesno("Confirmer", "Supprimer cette catégorie ?", parent=self.root):
            ok, msg = db.delete_categorie(int(sel[0]))
            if not ok:
                messagebox.showwarning("Impossible", msg, parent=self.root)
            self._charger_categories()

    # ═══ FOURNISSEURS ══════════════════════════════════


