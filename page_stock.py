"""
SOPAUTO - Gestion des Stocks & Mouvements Multi-Dépôts (Version Améliorée)

Fonctionnalités :
- Tableau de bord synthétique du stock (Valeur CUMP, Revente potentielle, Marge brute théorique, Nb d'alertes).
- Filtres intelligents (Par statut: Tout / OK / Alerte / Rupture, Par catégorie, Recherche texte / Référence / Code-barres).
- Vue détaillée par produit (Emplacement, Stock Vente, Stock Réserve, Total, Seuil mini, Prix d'achat CUMP, Prix Vente, Marge & Valeur).
- Actions rapides (Entrée, Sortie, Transfert multi-dépôt, Ajustement inventaire, Export CSV, Impression du bon de réapprovisionnement).
- Menu contextuel au clic droit et double-clic ergonomique.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os

import database as db
import export_pdf
import factures
from dialogues import DialogueMouvement, DialogueTransfert
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, EntreeRecherche,
                        TableauTriable, ajouter_scrollbars, fmt_money,
                        infobulle, zebre, KPI, AutocompleteCombobox)


class StockMixin:
    """Gestion du stock modernisée — Écran principal de suivi et mouvements."""

    def afficher_stock(self):
        if not self.peut("stock"):
            return self._refus()
        self._nouvelle_page("Gestion des stocks & Mouvements", 3)

        self._filtre_statut = "tous"  # tous | alerte | rupture | ok

        # ── Actions dans l'en-tête de page ──
        Bouton(self.zone_actions, "Entrée", "success",
               lambda: self._mouvement("entree"), petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "Sortie", "danger",
               lambda: self._mouvement("sortie"), petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "Transfert", "info",
               self._ouvrir_transfert, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "Inventaire", "warning",
               lambda: self._mouvement("correction"), petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "Bon de réappro", "secondary",
               self.generer_reappro, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "Exporter CSV", "secondary",
               self._exporter_stock_csv, petit=True, outline=True).pack(side=tk.LEFT, padx=3)

        # ── Conteneur principal ──
        grille = tk.Frame(self.zone, bg=COULEURS["bg"])
        grille.pack(fill=tk.BOTH, expand=True)

        # --- Section 1 : KPI Synthèse du Stock ---
        self.cadre_kpi_stock = tk.Frame(grille, bg=COULEURS["bg"])
        self.cadre_kpi_stock.pack(fill=tk.X, pady=(0, 10))

        # --- Section 2 : Barre de filtres avancés ---
        carte_filtres = Carte(grille)
        carte_filtres.pack(fill=tk.X, pady=(0, 10))
        cf = carte_filtres.corps

        # Filtre Recherche
        self.rech_stock = EntreeRecherche(cf, "Chercher réf, nom, marque ou code-barres…", 30,
                                          callback=self._charger_stock)
        self.rech_stock.pack(side=tk.LEFT, padx=(0, 10))

        # Filtre Catégorie
        tk.Label(cf, text="Catégorie:", font=(POLICE, 9),
                 bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(side=tk.LEFT, padx=(6, 4))

        cats = db.get_categories()
        self._dict_cats = {c["nom"]: c["id"] for c in cats}
        noms_cats = ["Toutes les catégories"] + list(self._dict_cats.keys())

        self.cb_filtre_cat = AutocompleteCombobox(cf, font=(POLICE, 9), width=20)
        self.cb_filtre_cat.set_completion_list(noms_cats)
        self.cb_filtre_cat.set("Toutes les catégories")
        self.cb_filtre_cat.pack(side=tk.LEFT, padx=(0, 12))
        self.cb_filtre_cat.bind("<<ComboboxSelected>>", lambda e: self._charger_stock())
        self.cb_filtre_cat.bind("<Return>", lambda e: self._charger_stock())

        # Boutons de filtres d'état rapides (Pilules)
        f_pilules = tk.Frame(cf, bg=COULEURS["card"])
        f_pilules.pack(side=tk.LEFT, padx=6)

        self.btn_f_tous = Bouton(f_pilules, "Tous", "primary", lambda: self._changer_filtre_statut("tous"), petit=True)
        self.btn_f_tous.pack(side=tk.LEFT, padx=2)

        self.btn_f_alerte = Bouton(f_pilules, "Alerte", "warning", lambda: self._changer_filtre_statut("alerte"), petit=True, outline=True)
        self.btn_f_alerte.pack(side=tk.LEFT, padx=2)

        self.btn_f_rupture = Bouton(f_pilules, "Rupture", "danger", lambda: self._changer_filtre_statut("rupture"), petit=True, outline=True)
        self.btn_f_rupture.pack(side=tk.LEFT, padx=2)

        # Label Récapitulatif à droite
        self.lbl_resume_stock = tk.Label(cf, text="", font=(POLICE, 9),
                                         bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_resume_stock.pack(side=tk.RIGHT, padx=6)

        # --- Section 3 : Table du Stock (Treeview avec colonnes de valorisation) ---
        carte_table = Carte(grille)
        carte_table.pack(fill=tk.BOTH, expand=True)
        ct = carte_table.corps

        self.tab_stock = TableauTriable(ct, [
            ("ref", "Référence", 100, "w", False),
            ("nom", "Nom de la pièce", 220, "w", False),
            ("cat", "Catégorie", 110, "w", False),
            ("emp", "Emplac.", 80, "w", False),
            ("reserve", "Réserve", 65, "center", True),
            ("vente", "Rayon", 60, "center", True),
            ("total", "Stock Total", 75, "center", True),
            ("mini", "Seuil", 55, "center", True),
            ("etat", "Statut", 90, "center", False),
            ("cump", "Coût CUMP", 90, "e", True),
            ("pv", "Prix Vente", 90, "e", True),
            ("valeur", "Valeur Stock", 105, "e", True)
        ])
        ajouter_scrollbars(ct, self.tab_stock)

        # Evénements d'interaction
        self.tab_stock.bind("<Double-1>", lambda e: self._mouvement_depuis_stock())
        self.tab_stock.bind("<Button-3>", self._menu_contextuel_stock)
        infobulle(self.tab_stock, "Double-clic : Entrée de stock rapide  ·  Clic droit : Actions contextuelles")

        self._charger_stock()

    def _changer_filtre_statut(self, statut: str):
        self._filtre_statut = statut
        # Mettre à jour l'apparence des pilules
        self.btn_f_tous.configure(bg=COULEURS["primary"] if statut == "tous" else COULEURS["card"],
                                   fg="white" if statut == "tous" else COULEURS["primary"])
        self.btn_f_alerte.configure(bg=COULEURS["warning"] if statut == "alerte" else COULEURS["card"],
                                    fg="white" if statut == "alerte" else COULEURS["warning"])
        self.btn_f_rupture.configure(bg=COULEURS["danger"] if statut == "rupture" else COULEURS["card"],
                                     fg="white" if statut == "rupture" else COULEURS["danger"])
        self._charger_stock()

    def _kpis_stock(self, prods: list):
        # Nettoyage de l'ancien conteneur KPI
        for w in self.cadre_kpi_stock.winfo_children():
            w.destroy()

        self.cadre_kpi_stock.columnconfigure(0, weight=1)
        self.cadre_kpi_stock.columnconfigure(1, weight=1)
        self.cadre_kpi_stock.columnconfigure(2, weight=1)
        self.cadre_kpi_stock.columnconfigure(3, weight=1)

        valeur_cump = sum((p.get("stock", 0) * (p.get("cump") or p.get("prix_achat") or 0)) for p in prods)
        valeur_vente = sum((p.get("stock", 0) * (p.get("prix_vente") or 0)) for p in prods)
        marge_potentielle = valeur_vente - valeur_cump
        nb_alertes = sum(1 for p in prods if p.get("stock", 0) <= p.get("stock_mini", 0))
        nb_ruptures = sum(1 for p in prods if p.get("stock", 0) <= 0)

        kpis_data = [
            ("", fmt_money(valeur_cump, self.devise), "Valeur au Coût (CUMP)", COULEURS["primary"]),
            ("", fmt_money(valeur_vente, self.devise), "Valeur Revente estimée", COULEURS["success"]),
            ("", fmt_money(marge_potentielle, self.devise), "Marge théorique stock", COULEURS["info"]),
            ("⚠", f"{nb_alertes} alerte(s)", f"dont {nb_ruptures} rupture(s)", COULEURS["danger"] if nb_alertes > 0 else COULEURS["success"]),
        ]

        for i, (icone, val, label, coul) in enumerate(kpis_data):
            k = KPI(self.cadre_kpi_stock, icone, val, label, couleur=coul)
            k.grid(row=0, column=i, sticky="ew", padx=4)

    def _charger_stock(self):
        texte_recherche = self.rech_stock.get() if hasattr(self, 'rech_stock') else ""
        cat_choisie = self.cb_filtre_cat.get() if hasattr(self, 'cb_filtre_cat') else "Toutes les catégories"
        cat_id = self._dict_cats.get(cat_choisie) if hasattr(self, '_dict_cats') else None

        # Récupération globale pour KPI
        tous_produits = db.get_produits(inclure_inactifs=False)
        self._kpis_stock(tous_produits)

        # Filtrage pour la table
        produits = db.get_produits(search=texte_recherche,
                                   categorie_id=cat_id,
                                   seulement_alertes=(self._filtre_statut == "alerte"),
                                   inclure_inactifs=False)

        t = self.tab_stock
        t.delete(*t.get_children())
        valeur_filtree = 0.0
        count_affiche = 0

        for i, p in enumerate(produits):
            stk = p.get("stock", 0)
            stk_mini = p.get("stock_mini", 5)

            # Filtre par pilule d'état
            if self._filtre_statut == "rupture" and stk > 0:
                continue
            if self._filtre_statut == "alerte" and (stk > stk_mini or stk <= 0):
                continue
            if self._filtre_statut == "ok" and stk <= stk_mini:
                continue

            count_affiche += 1
            cump = float(p.get("cump") or p.get("prix_achat") or 0)
            pv = float(p.get("prix_vente") or 0)
            valeur_prod = stk * cump
            valeur_filtree += valeur_prod

            if stk <= 0:
                etat, tags = "🔴 Rupture", ("rupture",)
            elif stk <= stk_mini:
                etat, tags = "🟠 Alerte", ("alerte",)
            else:
                etat, tags = "🟢 En stock", ()

            t.insert("", tk.END, iid=p["id"], tags=zebre(i, tags), values=(
                p.get("reference", ""),
                p["nom"],
                p.get("categorie_nom") or "—",
                p.get("emplacement") or "—",
                p.get("stock_reserve", 0),
                p.get("stock_vente", 0),
                stk,
                stk_mini,
                etat,
                fmt_money(cump, self.devise),
                fmt_money(pv, self.devise),
                fmt_money(valeur_prod, self.devise)
            ))

        self.lbl_resume_stock.configure(
            text=f"{count_affiche} produit(s) affiché(s)  ·  Valeur: {fmt_money(valeur_filtree, self.devise)}")

    def _mouvement(self, type_mvt, produit_id=None):
        d = DialogueMouvement(self.root, type_mvt, produit_id)
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            if hasattr(self, "tab_stock") and self.tab_stock.winfo_exists():
                self._charger_stock()
            self._maj_badge_alertes()

    def _ouvrir_transfert(self):
        sel = self.tab_stock.selection()
        pid = int(sel[0]) if sel else None
        self._mouvement("transfert", pid)

    def _mouvement_depuis_stock(self):
        sel = self.tab_stock.selection()
        if sel:
            self._mouvement("entree", int(sel[0]))

    def _menu_contextuel_stock(self, event):
        iid = self.tab_stock.identify_row(event.y)
        if not iid:
            return
        self.tab_stock.selection_set(iid)
        pid = int(iid)

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Entrée de stock rapide...", command=lambda: self._mouvement("entree", pid))
        menu.add_command(label="Sortie de stock...", command=lambda: self._mouvement("sortie", pid))
        menu.add_command(label="Transfert dépôt...", command=lambda: self._mouvement("transfert", pid))
        menu.add_command(label="Ajustement d'inventaire...", command=lambda: self._mouvement("correction", pid))
        menu.post(event.x_root, event.y_root)

    def generer_reappro(self):
        chemin = factures.generer_liste_reappro()
        self.statut(f"Bon de réapprovisionnement généré : {chemin}", COULEURS["success"])

    def _exporter_stock_csv(self):
        produits = db.get_produits(search=self.rech_stock.get(), inclure_inactifs=False)
        if not produits:
            messagebox.showinfo("Export CSV", "Aucun produit à exporter.", parent=self.root)
            return

        export_dir = os.path.join(db.BASE_DIR, "exports")
        os.makedirs(export_dir, exist_ok=True)
        fichier = os.path.join(export_dir, "etat_du_stock.csv")

        try:
            with open(fichier, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Référence", "Nom", "Catégorie", "Emplacement", "Stock Réserve", "Stock Vente", "Stock Total", "Seuil Mini", "Coût CUMP", "Prix Vente", "Valeur Stock"])
                for p in produits:
                    cump = float(p.get("cump") or p.get("prix_achat") or 0)
                    writer.writerow([
                        p.get("reference", ""), p["nom"], p.get("categorie_nom", ""),
                        p.get("emplacement", ""), p.get("stock_reserve", 0), p.get("stock_vente", 0),
                        p.get("stock", 0), p.get("stock_mini", 0), cump, p.get("prix_vente", 0),
                        p.get("stock", 0) * cump
                    ])
            self.statut(f"Export stock réussi : {fichier}", COULEURS["success"])
            messagebox.showinfo("Export réussi", f"Le fichier d'état du stock a été créé :\n\n{fichier}", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Erreur Export", f"Impossible d'exporter : {exc}", parent=self.root)

    # ═══ CLIENTS (Retrocompatibilité mixin) ═══════════════════════════════════════

    def _entree_rapide(self, tree):
        sel = tree.selection()
        if not sel:
            return
        d = DialogueMouvement(self.root, "entree", int(sel[0]))
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            self.afficher_dashboard()

    def _imprimer_selection(self, tree, ticket=False):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez une vente.", parent=self.root)
            return
        ok, res = factures.imprimer_facture(int(sel[0]), format_ticket=ticket)
        self.statut("Facture ouverte pour impression" if ok else res,
                    COULEURS["success"] if ok else COULEURS["danger"])

    def _pdf_selection(self, tree, ticket=False):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez une vente.", parent=self.root)
            return
        if not export_pdf.moteur_disponible():
            messagebox.showinfo(
                "PDF indisponible",
                "Aucun navigateur trouvé pour générer le PDF.\n\n"
                "Utilisez « Facture A4 » puis Ctrl+P →"
                "« Enregistrer au format PDF ».", parent=self.root)
            return
