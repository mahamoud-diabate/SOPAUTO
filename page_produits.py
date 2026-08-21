"""
SOPAUTO - Catalogue Produits (Version Modernisée)

Fonctionnalités :
- Synthèse KPI du catalogue (Total fiches, Marques référencées, Fiches à compléter, Marge catalogue moyenne).
- Filtres avancés 3 dimensions (Recherche globale, Marque de véhicule, Catégorie, Pilules d'état : Tous/Actifs/Inactifs/À compléter).
- Volet d'aperçu détaillé dynamique au bas du catalogue (Identité OEM, Marques & Modèles compatibles, Marge brute & CUMP, Emplacement).
- Raccourcis et édition directe (`Ctrl+N` pour nouveau, double-clic pour modifier, clic droit contextuel).
- Import et Export CSV optimisés.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import database as db
from dialogues import DialogueMouvement, DialogueProduit
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, EntreeRecherche,
                        TableauTriable, ajouter_scrollbars, fmt_money, zebre,
                        KPI, AutocompleteCombobox)


class ProduitsMixin:
    """Catalogue produits — recherche avancée, CRUD, aperçu fiche & import/export."""

    def afficher_produits(self, alertes=False):
        self._nouvelle_page("Catalogue produits & Référentiel", 2)

        self._filtre_statut_prod = "tous"  # tous | actifs | inactifs | a_completer

        # ── Actions dans l'en-tête de page ──
        if self.peut("produits"):
            Bouton(self.zone_actions, "Nouveau (Ctrl+N)", "primary",
                   self.nouveau_produit, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "Exporter CSV", "info",
               self._exporter_produits, petit=True).pack(side=tk.LEFT, padx=3)
        if self.peut("admin"):
            Bouton(self.zone_actions, "Importer CSV", "secondary",
                   self._importer_produits, petit=True, outline=True).pack(side=tk.LEFT, padx=3)

        # ── Conteneur principal ──
        grille = tk.Frame(self.zone, bg=COULEURS["bg"])
        grille.pack(fill=tk.BOTH, expand=True)

        # --- Section 1 : Bandeau KPI Synthèse Catalogue ---
        self.cadre_kpi_prod = tk.Frame(grille, bg=COULEURS["bg"])
        self.cadre_kpi_prod.pack(fill=tk.X, pady=(0, 10))

        # --- Section 2 : Barre de Filtres Multi-critères ---
        carte_filtres = Carte(grille)
        carte_filtres.pack(fill=tk.X, pady=(0, 10))
        cf = carte_filtres.corps

        # Recherche texte
        self.rech_produits = EntreeRecherche(cf, "Référence, nom, marque ou code-barres…", 28,
                                             callback=self._charger_produits)
        self.rech_produits.pack(side=tk.LEFT, padx=(0, 10))

        # Filtre Catégorie
        tk.Label(cf, text="Catégorie:", font=(POLICE, 9),
                 bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(side=tk.LEFT, padx=(4, 2))

        self.categories_cache = db.get_categories()
        self._dict_cats_prod = {c["nom"]: c["id"] for c in self.categories_cache}
        noms_cats = ["Toutes les catégories"] + list(self._dict_cats_prod.keys())

        self.cb_filtre_cat_prod = AutocompleteCombobox(cf, font=(POLICE, 9), width=18)
        self.cb_filtre_cat_prod.set_completion_list(noms_cats)
        self.cb_filtre_cat_prod.set("Toutes les catégories")
        self.cb_filtre_cat_prod.pack(side=tk.LEFT, padx=(0, 10))
        self.cb_filtre_cat_prod.bind("<<ComboboxSelected>>", lambda e: self._charger_produits())
        self.cb_filtre_cat_prod.bind("<Return>", lambda e: self._charger_produits())

        # Filtre Marque Véhicule
        tk.Label(cf, text="Marque:", font=(POLICE, 9),
                 bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(side=tk.LEFT, padx=(4, 2))

        # Extraire les marques uniques de la base
        all_prods = db.get_produits(inclure_inactifs=True)
        marques_uniques = sorted(list({p.get("marque", "").strip() for p in all_prods if p.get("marque") and p.get("marque").strip()}))
        self.cb_filtre_marque = AutocompleteCombobox(cf, font=(POLICE, 9), width=14)
        self.cb_filtre_marque.set_completion_list(["Toutes les marques"] + marques_uniques)
        self.cb_filtre_marque.set("Toutes les marques")
        self.cb_filtre_marque.pack(side=tk.LEFT, padx=(0, 10))
        self.cb_filtre_marque.bind("<<ComboboxSelected>>", lambda e: self._charger_produits())

        # Pilules d'état rapides
        f_pilules = tk.Frame(cf, bg=COULEURS["card"])
        f_pilules.pack(side=tk.LEFT, padx=4)

        self.btn_stat_tous = Bouton(f_pilules, "Tous", "primary", lambda: self._changer_statut_filtre("tous"), petit=True)
        self.btn_stat_tous.pack(side=tk.LEFT, padx=2)

        self.btn_stat_actifs = Bouton(f_pilules, "Actifs", "secondary", lambda: self._changer_statut_filtre("actifs"), petit=True, outline=True)
        self.btn_stat_actifs.pack(side=tk.LEFT, padx=2)

        self.btn_stat_inactifs = Bouton(f_pilules, "Inactifs", "secondary", lambda: self._changer_statut_filtre("inactifs"), petit=True, outline=True)
        self.btn_stat_inactifs.pack(side=tk.LEFT, padx=2)

        self.btn_stat_completer = Bouton(f_pilules, "À compléter", "warning", lambda: self._changer_statut_filtre("a_completer"), petit=True, outline=True)
        self.btn_stat_completer.pack(side=tk.LEFT, padx=2)

        self.lbl_resume_produits = tk.Label(cf, text="", font=(POLICE, 9),
                                            bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_resume_produits.pack(side=tk.RIGHT, padx=6)

        # --- Section 3 : Table du Catalogue ---
        carte_table = Carte(grille)
        carte_table.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        ct = carte_table.corps

        self.tab_produits = TableauTriable(ct, [
            ("ref", "Référence", 100, "w", False),
            ("nom", "Désignation Produit", 220, "w", False),
            ("cat", "Catégorie", 110, "w", False),
            ("marque", "Marque", 85, "w", False),
            ("stock", "Stock", 55, "center", True),
            ("mini", "Seuil", 50, "center", True),
            ("pa", "Prix Achat", 85, "e", True),
            ("pv", "Prix Vente", 85, "e", True),
            ("marge", "Marge Unit.", 85, "e", True),
            ("valeur", "Valeur Stk", 95, "e", True),
            ("emp", "Emplac.", 75, "w", False),
            ("four", "Fournisseur", 110, "w", False)
        ])
        ajouter_scrollbars(ct, self.tab_produits)

        # Evénements Table
        self.tab_produits.bind("<<TreeviewSelect>>", self._sur_selection_produit)
        self.tab_produits.bind("<Double-1>", lambda e: self.modifier_produit())
        self.tab_produits.bind("<Delete>", lambda e: self.supprimer_produit())

        # Menu contextuel clic droit
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Modifier la fiche (Double-clic)", command=self.modifier_produit)
        menu.add_command(label="Entrée de stock...", command=lambda: self._mouvement_produit("entree"))
        menu.add_command(label="Sortie de stock...", command=lambda: self._mouvement_produit("sortie"))
        menu.add_command(label="Transfert réserve ↔ rayon...", command=lambda: self._mouvement_produit("transfert"))
        menu.add_separator()
        menu.add_command(label="Supprimer / Désactiver", command=self.supprimer_produit)

        def clic_droit(e):
            iid = self.tab_produits.identify_row(e.y)
            if iid:
                self.tab_produits.selection_set(iid)
                menu.tk_popup(e.x_root, e.y_root)

        self.tab_produits.bind("<Button-3>", clic_droit)

        # --- Section 4 : Volet d'Aperçu Fiche Produit (Panneau bas) ---
        self.carte_apercu = Carte(grille, "ℹ Aperçu & Fiche Technique Article")
        self.carte_apercu.pack(fill=tk.X)
        ca = self.carte_apercu.corps

        self.lbl_apercu_titre = tk.Label(ca, text="Sélectionnez un produit dans le tableau pour afficher sa fiche.",
                                         font=(POLICE, 10, "italic"), bg=COULEURS["card"], fg=COULEURS["text_secondary"])
        self.lbl_apercu_titre.pack(anchor="w", pady=4)

        self._charger_produits()

    def _changer_statut_filtre(self, statut: str):
        self._filtre_statut_prod = statut
        self.btn_stat_tous.configure(bg=COULEURS["primary"] if statut == "tous" else COULEURS["card"], fg="white" if statut == "tous" else COULEURS["primary"])
        self.btn_stat_actifs.configure(bg=COULEURS["primary"] if statut == "actifs" else COULEURS["card"], fg="white" if statut == "actifs" else COULEURS["primary"])
        self.btn_stat_inactifs.configure(bg=COULEURS["secondary"] if statut == "inactifs" else COULEURS["card"], fg="white" if statut == "inactifs" else COULEURS["secondary"])
        self.btn_stat_completer.configure(bg=COULEURS["warning"] if statut == "a_completer" else COULEURS["card"], fg="white" if statut == "a_completer" else COULEURS["warning"])
        self._charger_produits()

    def _kpis_produits(self, prods: list):
        for w in self.cadre_kpi_prod.winfo_children():
            w.destroy()

        self.cadre_kpi_prod.columnconfigure(0, weight=1)
        self.cadre_kpi_prod.columnconfigure(1, weight=1)
        self.cadre_kpi_prod.columnconfigure(2, weight=1)
        self.cadre_kpi_prod.columnconfigure(3, weight=1)

        total_fiches = len(prods)
        actifs = sum(1 for p in prods if p.get("actif", 1))
        inactifs = total_fiches - actifs
        marques = len({p.get("marque", "").strip() for p in prods if p.get("marque") and p.get("marque").strip()})

        # Marge moyenne catalogue
        marges = [((p["prix_vente"] - p["prix_achat"]) / p["prix_vente"] * 100) for p in prods if p.get("prix_vente", 0) > 0 and p.get("prix_achat", 0) > 0]
        marge_moy = (sum(marges) / len(marges)) if marges else 0.0

        # Articles à compléter
        a_completer = sum(1 for p in prods if not p.get("reference") or p["reference"].startswith("PRD-TMP-") or not p.get("marque") or not p.get("prix_achat"))

        kpis_data = [
            ("", f"{total_fiches} fiches", f"{actifs} actives · {inactifs} inactives", COULEURS["primary"]),
            ("", f"{marques} marque(s)", "Equipementiers & Constructeurs", COULEURS["info"]),
            ("", f"{marge_moy:.1f} %", "Marge catalogue moyenne", COULEURS["success"]),
            ("", f"{a_completer} à compléter", "Référence ou prix manquant", COULEURS["warning"] if a_completer > 0 else COULEURS["success"]),
        ]

        for i, (icone, val, label, coul) in enumerate(kpis_data):
            k = KPI(self.cadre_kpi_prod, icone, val, label, couleur=coul)
            k.grid(row=0, column=i, sticky="ew", padx=4)

    def _charger_produits(self):
        cat_nom = self.cb_filtre_cat_prod.get() if hasattr(self, 'cb_filtre_cat_prod') else "Toutes les catégories"
        cat_id = self._dict_cats_prod.get(cat_nom) if hasattr(self, '_dict_cats_prod') else None

        marque_choisie = self.cb_filtre_marque.get() if hasattr(self, 'cb_filtre_marque') else "Toutes les marques"
        texte_recherche = self.rech_produits.get() if hasattr(self, 'rech_produits') else ""

        tous_prods = db.get_produits(inclure_inactifs=True)
        self._kpis_produits(tous_prods)

        # Récupération selon statut et filtres
        inclure_inact = (self._filtre_statut_prod in ("tous", "inactifs"))
        produits = db.get_produits(categorie_id=cat_id,
                                   search=texte_recherche,
                                   inclure_inactifs=inclure_inact)

        # Filtre par marque
        if marque_choisie and marque_choisie != "Toutes les marques":
            produits = [p for p in produits if p.get("marque", "").strip().lower() == marque_choisie.strip().lower()]

        # Filtre par pilule d'état
        if self._filtre_statut_prod == "actifs":
            produits = [p for p in produits if p.get("actif", 1)]
        elif self._filtre_statut_prod == "inactifs":
            produits = [p for p in produits if not p.get("actif", 1)]
        elif self._filtre_statut_prod == "a_completer":
            produits = [p for p in produits if not p.get("reference") or p["reference"].startswith("PRD-TMP-") or not p.get("marque") or not p.get("prix_achat")]

        t = self.tab_produits
        t.delete(*t.get_children())
        valeur_totale = 0.0

        for i, p in enumerate(produits):
            etats = []
            if not p.get("actif", 1):
                etats.append("inactif")
            elif p["stock"] <= 0:
                etats.append("rupture")
            elif p["stock"] <= p["stock_mini"]:
                etats.append("alerte")

            valeur_prod = (p.get("stock", 0) * float(p.get("cump") or p.get("prix_achat") or 0))
            valeur_totale += valeur_prod

            nom_aff = p["nom"] + ("  (inactif)" if not p.get("actif", 1) else "")

            t.insert("", tk.END, iid=p["id"], tags=zebre(i, etats), values=(
                p["reference"], nom_aff,
                p.get("categorie_nom") or "—", p.get("marque") or "—",
                p.get("stock", 0), p.get("stock_mini", 5),
                fmt_money(p.get("prix_achat", 0)), fmt_money(p.get("prix_vente", 0)),
                fmt_money(p.get("marge_unitaire", 0)), fmt_money(valeur_prod),
                p.get("emplacement") or "—", p.get("fournisseur_nom") or "—"))

        self.lbl_resume_produits.configure(
            text=f"{len(produits)} produit(s) affiché(s)  ·  valeur {fmt_money(valeur_totale, self.devise)}")

    def _sur_selection_produit(self, event=None):
        pid = self._produit_selectionne()
        if not pid:
            return

        produit = db.get_produit(pid)
        if not produit:
            return

        # Vider l'ancien contenu de la carte d'aperçu
        for w in self.carte_apercu.corps.winfo_children():
            w.destroy()

        ca = self.carte_apercu.corps
        ca.columnconfigure(0, weight=1)
        ca.columnconfigure(1, weight=1)
        ca.columnconfigure(2, weight=1)

        # Colonne 1 : Identité & Emplacement
        col1 = tk.Frame(ca, bg=COULEURS["card"])
        col1.grid(row=0, column=0, sticky="nsew", padx=8)

        tk.Label(col1, text=f"{produit['nom']}", font=(POLICE, 12, "bold"),
                 bg=COULEURS["card"], fg=COULEURS["text"]).pack(anchor="w")
        tk.Label(col1, text=f"Réf: {produit['reference']}  ·  Marque: {produit.get('marque') or 'N/A'}",
                 font=(POLICE, 9), bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(2, 4))
        tk.Label(col1, text=f"Code OEM / Barres: {produit.get('code_barres') or 'Non renseigné'}",
                 font=(POLICE, 9), bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(anchor="w")
        tk.Label(col1, text=f"Emplacement: {produit.get('emplacement') or 'Rayon A1'}",
                 font=(POLICE, 9), bg=COULEURS["card"], fg=COULEURS["primary"]).pack(anchor="w", pady=(2, 0))

        # Colonne 2 : Analyse financière (CUMP vs Prix Vente)
        col2 = tk.Frame(ca, bg=COULEURS["card"])
        col2.grid(row=0, column=1, sticky="nsew", padx=8)

        pa = float(produit.get("prix_achat") or 0)
        pv = float(produit.get("prix_vente") or 0)
        cump = float(produit.get("cump") or pa)
        marge = pv - cump
        marge_pct = (marge / pv * 100) if pv > 0 else 0

        tk.Label(col2, text="Tarification & Rentabilité", font=(POLICE, 10, "bold"),
                 bg=COULEURS["card"], fg=COULEURS["text"]).pack(anchor="w")
        tk.Label(col2, text=f"Prix Achat / CUMP : {fmt_money(cump, self.devise)}",
                 font=(POLICE, 9), bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(anchor="w")
        tk.Label(col2, text=f"Prix Vente Catalogue : {fmt_money(pv, self.devise)}",
                 font=(POLICE, 10, "bold"), bg=COULEURS["card"], fg=COULEURS["primary"]).pack(anchor="w")
        
        lbl_m = f"Marge brute : {fmt_money(marge, self.devise)} ({marge_pct:.1f}%)"
        coul_m = COULEURS["success"] if marge > 0 else COULEURS["danger"]
        tk.Label(col2, text=lbl_m, font=(POLICE, 9),
                 bg=COULEURS["card"], fg=coul_m).pack(anchor="w", pady=(2, 0))

        # Colonne 3 : Stock & Actions rapides
        col3 = tk.Frame(ca, bg=COULEURS["card"])
        col3.grid(row=0, column=2, sticky="nsew", padx=8)

        tk.Label(col3, text="État du Stock", font=(POLICE, 10, "bold"),
                 bg=COULEURS["card"], fg=COULEURS["text"]).pack(anchor="w")
        stk_txt = f"Stock Vente: {produit.get('stock_vente', 0)}  ·  Réserve: {produit.get('stock_reserve', 0)} (Total: {produit.get('stock', 0)})"
        tk.Label(col3, text=stk_txt, font=(POLICE, 9),
                 bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(2, 6))

        btn_box = tk.Frame(col3, bg=COULEURS["card"])
        btn_box.pack(anchor="w")
        Bouton(btn_box, "Modifier", "primary", self.modifier_produit, petit=True).pack(side=tk.LEFT, padx=(0, 4))
        Bouton(btn_box, "Entrée", "success", lambda: self._mouvement_produit("entree"), petit=True).pack(side=tk.LEFT, padx=2)

    def _produit_selectionne(self):
        sel = self.tab_produits.selection()
        if not sel:
            return None
        return int(sel[0])

    def nouveau_produit(self):
        d = DialogueProduit(self.root)
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            self._charger_produits()

    def modifier_produit(self):
        pid = self._produit_selectionne()
        if not pid:
            messagebox.showinfo("Information", "Sélectionnez d'abord un produit à modifier.", parent=self.root)
            return
        p = db.get_produit(pid)
        if p:
            d = DialogueProduit(self.root, p)
            if d.attendre():
                self.statut(d.result, COULEURS["success"])
                self._charger_produits()

    def supprimer_produit(self):
        pid = self._produit_selectionne()
        if not pid:
            messagebox.showinfo("Information", "Sélectionnez d'abord un produit.", parent=self.root)
            return
        p = db.get_produit(pid)
        if not p:
            return
        if messagebox.askyesno("Suppression / Désactivation",
                               f"Voulez-vous supprimer ou désactiver « {p['nom']} » ?", parent=self.root):
            ok, msg = db.delete_produit(pid)
            if ok:
                self.statut(f"{msg}", COULEURS["success"])
                self._charger_produits()
            else:
                messagebox.showerror("Erreur", msg, parent=self.root)

    def _mouvement_produit(self, type_mvt):
        pid = self._produit_selectionne()
        if not pid:
            messagebox.showinfo("Information", "Sélectionnez d'abord un produit.", parent=self.root)
            return
        d = DialogueMouvement(self.root, type_mvt, pid)
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            self._charger_produits()

    def _exporter_produits(self):
        self._exporter_stock_csv() if hasattr(self, '_exporter_stock_csv') else None

    def _importer_produits(self):
        fichier = filedialog.askopenfilename(
            title="Importer des produits CSV",
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")],
            parent=self.root)
        if not fichier:
            return
        ok, msg = db.import_produits_csv(fichier)
        if ok:
            self.statut(f"{msg}", COULEURS["success"])
            self._charger_produits()
        else:
            messagebox.showerror("Erreur import", msg, parent=self.root)
