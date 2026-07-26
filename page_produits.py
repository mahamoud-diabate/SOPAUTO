"""
SODIPAC - Produits
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import database as db
from dialogues import DialogueMouvement, DialogueProduit
from ui_widgets import (COULEURS, POLICE, Bouton, EntreeRecherche,
                        TableauTriable, ajouter_scrollbars, fmt_money, zebre)


class ProduitsMixin:
    """Catalogue produits — recherche, CRUD, import/export CSV.

    Filtre par catégorie, mouvement rapide, double-clic pour modifier.
    """

    def afficher_produits(self, alertes=False):
        self._nouvelle_page("📦 Catalogue produits", 2)

        if self.peut("produits"):
            Bouton(self.zone_actions, "➕ Nouveau (Ctrl+N)", "primary",
                   self.nouveau_produit, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "📤 Exporter CSV", "info",
               self._exporter_produits, petit=True).pack(side=tk.LEFT, padx=3)
        if self.peut("admin"):
            Bouton(self.zone_actions, "📥 Importer CSV", "secondary",
                   self._importer_produits, petit=True).pack(side=tk.LEFT, padx=3)

        barre = tk.Frame(self.zone, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))

        self.rech_produits = EntreeRecherche(barre, "Référence, nom, marque, code-barres…",
                                             38, callback=self._charger_produits)
        self.rech_produits.pack(side=tk.LEFT)

        tk.Label(barre, text="Catégorie :", font=(POLICE, 9),
                 bg=COULEURS["bg"]).pack(side=tk.LEFT, padx=(14, 4))
        self.categories_cache = db.get_categories()
        self.filtre_cat = ttk.Combobox(barre, state="readonly", width=18, font=(POLICE, 9),
                                       values=["Toutes"] + [c["nom"] for c in self.categories_cache])
        self.filtre_cat.current(0)
        self.filtre_cat.pack(side=tk.LEFT)
        self.filtre_cat.bind("<<ComboboxSelected>>", lambda e: self._charger_produits())

        self.var_alertes = tk.BooleanVar(value=alertes)
        tk.Checkbutton(barre, text="⚠ Alertes seulement", variable=self.var_alertes,
                       bg=COULEURS["bg"], font=(POLICE, 9), activebackground=COULEURS["bg"],
                       command=self._charger_produits).pack(side=tk.LEFT, padx=12)

        self.var_inactifs = tk.BooleanVar(value=False)
        tk.Checkbutton(barre, text="Inclure les inactifs", variable=self.var_inactifs,
                       bg=COULEURS["bg"], font=(POLICE, 9), activebackground=COULEURS["bg"],
                       command=self._charger_produits).pack(side=tk.LEFT, padx=12)

        self.var_a_completer = tk.BooleanVar(value=False)
        tk.Checkbutton(barre, text="📝 À compléter", variable=self.var_a_completer,
                       bg=COULEURS["bg"], font=(POLICE, 9), activebackground=COULEURS["bg"],
                       command=self._charger_produits).pack(side=tk.LEFT)

        self.lbl_resume_produits = tk.Label(barre, text="", font=(POLICE, 9, "bold"),
                                            bg=COULEURS["bg"], fg=COULEURS["primary"])
        self.lbl_resume_produits.pack(side=tk.RIGHT, padx=8)

        cadre = tk.Frame(self.zone, bg=COULEURS["card"])
        cadre.pack(fill=tk.BOTH, expand=True)
        self.tab_produits = TableauTriable(cadre, [
            ("ref", "Référence", 100, "w", False),
            ("nom", "Désignation", 230, "w", False),
            ("cat", "Catégorie", 110, "w", False),
            ("marque", "Marque", 85, "w", False),
            ("reserve", "Réserve", 60, "center", True),
            ("vente", "Vente", 55, "center", True),
            ("stock", "Total", 55, "center", True),
            ("mini", "Seuil", 50, "center", True),
            ("pa", "P.A.", 80, "e", True),
            ("pv", "P.V.", 80, "e", True),
            ("marge", "Marge", 80, "e", True),
            ("valeur", "Valeur st.", 90, "e", True),
            ("emp", "Empl.", 80, "w", False),
            ("four", "Fournisseur", 120, "w", False)])
        ajouter_scrollbars(cadre, self.tab_produits)

        self.tab_produits.bind("<Double-1>", lambda e: self.modifier_produit())
        self.tab_produits.bind("<Delete>", lambda e: self.supprimer_produit())

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="✏️  Modifier", command=self.modifier_produit)
        menu.add_command(label="📥  Entrée de stock", command=lambda: self._mouvement_produit("entree"))
        menu.add_command(label="📤  Sortie de stock", command=lambda: self._mouvement_produit("sortie"))
        menu.add_command(label="🔧  Corriger le stock", command=lambda: self._mouvement_produit("correction"))
        menu.add_command(label="🔄  Transfert réserve ↔ vente", command=lambda: self._mouvement_produit("transfert"))
        menu.add_separator()
        menu.add_command(label="📈  Historique des mouvements", command=self._historique_produit)
        menu.add_separator()
        menu.add_command(label="🗑️  Supprimer", command=self.supprimer_produit)

        def clic_droit(e):
            iid = self.tab_produits.identify_row(e.y)
            if iid:
                self.tab_produits.selection_set(iid)
                menu.tk_popup(e.x_root, e.y_root)

        self.tab_produits.bind("<Button-3>", clic_droit)
        self._charger_produits()


    def _charger_produits(self):
        cat_nom = self.filtre_cat.get()
        cat_id = next((c["id"] for c in self.categories_cache if c["nom"] == cat_nom), None)
        produits = db.get_produits(categorie_id=cat_id,
                                   search=self.rech_produits.get(),
                                   seulement_alertes=self.var_alertes.get(),
                                   inclure_inactifs=self.var_inactifs.get())
        # Filtre "à compléter" : produits créés à la volée sans référence propre
        if self.var_a_completer.get():
            produits = [p for p in produits
                        if not p.get("reference") or p["reference"].startswith("PRD-TMP-")
                        or not p.get("marque") or not p.get("prix_achat")]
        t = self.tab_produits
        t.delete(*t.get_children())
        valeur_totale = 0
        for i, p in enumerate(produits):
            etats = []
            if not p.get("actif", 1):
                etats.append("inactif")
            elif p["stock"] <= 0:
                etats.append("rupture")
            elif p["stock"] <= p["stock_mini"]:
                etats.append("alerte")
            valeur_totale += p["valeur_stock"] or 0
            t.insert("", tk.END, iid=p["id"], tags=zebre(i, etats), values=(
                p["reference"], p["nom"] + ("" if p.get("actif", 1) else "  (inactif)"),
                p["categorie_nom"] or "—", p["marque"],
                p.get("stock_reserve", 0), p.get("stock_vente", 0),
                p["stock"], p["stock_mini"],
                fmt_money(p["prix_achat"]), fmt_money(p["prix_vente"]),
                fmt_money(p["marge_unitaire"]), fmt_money(p["valeur_stock"]),
                p["emplacement"], p["fournisseur_nom"] or "—"))
        self.lbl_resume_produits.configure(
            text=f"{len(produits)} produit(s) · valeur {fmt_money(valeur_totale, self.devise)}")


    def _produit_selectionne(self):
        sel = self.tab_produits.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez d'abord un produit.", parent=self.root)
            return None
        return int(sel[0])


    def nouveau_produit(self):
        if not self.peut("produits"):
            return self._refus()
        d = DialogueProduit(self.root)
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            if hasattr(self, "tab_produits") and self.tab_produits.winfo_exists():
                self._charger_produits()


    def modifier_produit(self):
        if not self.peut("produits"):
            return self._refus()
        pid = self._produit_selectionne()
        if pid is None:
            return
        d = DialogueProduit(self.root, db.get_produit(pid))
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            self._charger_produits()


    def supprimer_produit(self):
        if not self.peut("supprimer"):
            return self._refus()
        pid = self._produit_selectionne()
        if pid is None:
            return
        p = db.get_produit(pid)
        if not messagebox.askyesno(
                "Confirmer la suppression",
                f"Supprimer « {p['nom']} » ({p['reference']}) ?\n\n"
                "Si le produit apparaît dans des ventes, il sera désactivé "
                "au lieu d'être supprimé.", parent=self.root, icon="warning"):
            return
        ok, msg = db.delete_produit(pid)
        messagebox.showinfo("Résultat", msg, parent=self.root)
        self._charger_produits()


    def _mouvement_produit(self, type_mvt):
        if not self.peut("stock"):
            return self._refus()
        pid = self._produit_selectionne()
        if pid is None:
            return
        d = DialogueMouvement(self.root, type_mvt, pid)
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            self._charger_produits()
            self._maj_badge_alertes()


    def _historique_produit(self):
        pid = self._produit_selectionne()
        if pid is not None:
            self.afficher_mouvements(produit_id=pid)


    def _exporter_produits(self):
        chemin = db.exporter_produits()
        self._proposer_ouverture(chemin)


    def _importer_produits(self):
        if not self.peut("admin"):
            return self._refus()
        chemin = filedialog.askopenfilename(
            title="Choisir un fichier CSV", parent=self.root,
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")])
        if not chemin:
            return
        if not messagebox.askyesno(
                "Importer",
                "Le fichier doit contenir les colonnes : Référence;Nom;Catégorie;Marque;"
                "Stock;Stock mini;Prix achat;Prix vente;Emplacement\n\n"
                "Les références existantes seront mises à jour. Continuer ?", parent=self.root):
            return
        db.sauvegarder_base()
        ok, msg, _, _ = db.importer_produits_csv(chemin)
        messagebox.showinfo("Import terminé" if ok else "Erreur", msg, parent=self.root)
        self._charger_produits()


    def _proposer_ouverture(self, chemin):
        self.statut(f"Fichier créé : {chemin}", COULEURS["success"])
        if messagebox.askyesno("Export réussi",
                               f"Fichier enregistré :\n{chemin}\n\nL'ouvrir maintenant ?",
                               parent=self.root):
            try:
                os.startfile(chemin)
            except (AttributeError, OSError):
                messagebox.showinfo("Information", chemin, parent=self.root)

    # ═══ STOCK ═════════════════════════════════════════


