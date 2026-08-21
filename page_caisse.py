"""
SOPAUTO - Point de Vente / Caisse (Négociation de prix & UI modernisée)

Permet :
- La sélection immédiate du client (avec solde des créances et historique d'achat).
- L'affichage automatique du dernier prix négocié pour ce client.
- L'édition rapide du prix négocié par ligne (raccourci F2, double-clic, ou modal dédié).
- L'évaluation visuelle en temps réel des marges (Vert: >20%, Orange: 5-20%, Rouge: perte/sous coût).
- La disposition ergonomique 2 colonnes haut de gamme.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

import database as db
from dialogues import DialoguePaiementSimple, DialoguePaiement
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, AutocompleteCombobox,
                        fmt_money, zebre, config_lignes_alternees, ajouter_scrollbars,
                        Badge, parse_float)


class DialogueNegociationPrix(tk.Toplevel):
    """Fenêtre modale élégante pour négocier le prix unitaire d'un produit."""

    def __init__(self, parent, ligne: dict, client_nom: str = "", client_id: int = None, devise: str = "F CFA"):
        super().__init__(parent)
        self.title(f"Négocier le prix — {ligne['nom']}")
        self.geometry("520x480")
        self.minsize(500, 460)
        self.configure(bg=COULEURS["card"])
        self.transient(parent)
        self.grab_set()

        self.ligne = ligne
        self.devise = devise
        self.resultat = None

        # Récupération des informations de coût et de catalogue
        self.prix_cat = float(ligne.get("prix_catalogue", ligne["pu"]))
        self.cout = float(ligne.get("cout", 0))

        # Récupération du dernier prix négocié pour ce client
        self.dernier_prix_info = db.get_dernier_prix_client(ligne["id"], client_id=client_id, client_nom=client_nom)

        self._construire_interface(client_nom)
        self._centrer(parent)

    def _centrer(self, parent):
        self.update_idletasks()
        req_w = max(520, self.winfo_reqwidth())
        req_h = max(480, self.winfo_reqheight())
        x = parent.winfo_rootx() + (parent.winfo_width() - req_w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - req_h) // 2
        self.geometry(f"{req_w}x{req_h}+{max(0, x)}+{max(0, y)}")

    def _construire_interface(self, client_nom: str):
        pad_frame = tk.Frame(self, bg=COULEURS["card"], padx=24, pady=20)
        pad_frame.pack(fill=tk.BOTH, expand=True)

        # En-tête
        tk.Label(pad_frame, text=self.ligne['nom'], font=(POLICE, 12, "bold"),
                 bg=COULEURS["card"], fg=COULEURS["text"], wraplength=460, justify="left").pack(anchor="w")

        ref_txt = f"Réf: {self.ligne.get('ref', 'N/A')}"
        if client_nom:
            ref_txt += f"  ·  Client: {client_nom}"
        tk.Label(pad_frame, text=ref_txt, font=(POLICE, 9),
                 bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(2, 10))

        # Panneau récapitulatif des repères de prix
        reperes = tk.Frame(pad_frame, bg=COULEURS["row_alt"],
                           highlightbackground=COULEURS["border"], highlightthickness=1, padx=14, pady=10)
        reperes.pack(fill=tk.X, pady=(0, 12))

        # Ligne Catalogue
        r1 = tk.Frame(reperes, bg=COULEURS["row_alt"])
        r1.pack(fill=tk.X, pady=2)
        tk.Label(r1, text="Prix Catalogue :", font=(POLICE, 9),
                 bg=COULEURS["row_alt"], fg=COULEURS["text_secondary"]).pack(side=tk.LEFT)
        tk.Label(r1, text=fmt_money(self.prix_cat, self.devise), font=(POLICE, 10, "bold"),
                 bg=COULEURS["row_alt"], fg=COULEURS["primary"]).pack(side=tk.RIGHT)

        # Ligne Coût / CUMP
        if self.cout > 0:
            r2 = tk.Frame(reperes, bg=COULEURS["row_alt"])
            r2.pack(fill=tk.X, pady=2)
            tk.Label(r2, text="Coût de revient (CUMP) :", font=(POLICE, 9),
                     bg=COULEURS["row_alt"], fg=COULEURS["text_secondary"]).pack(side=tk.LEFT)
            tk.Label(r2, text=fmt_money(self.cout, self.devise), font=(POLICE, 9),
                     bg=COULEURS["row_alt"], fg=COULEURS["text"]).pack(side=tk.RIGHT)

        # Ligne Historique Client
        if self.dernier_prix_info:
            r3 = tk.Frame(reperes, bg=COULEURS["row_alt"])
            r3.pack(fill=tk.X, pady=2)
            hist_txt = f"Dernier prix ce client ({self.dernier_prix_info.get('date', '')[:10]}) :"
            tk.Label(r3, text=hist_txt, font=(POLICE, 9),
                     bg=COULEURS["row_alt"], fg=COULEURS["success"]).pack(side=tk.LEFT)
            tk.Label(r3, text=fmt_money(self.dernier_prix_info['prix'], self.devise), font=(POLICE, 10, "bold"),
                     bg=COULEURS["row_alt"], fg=COULEURS["success"]).pack(side=tk.RIGHT)

        # Saisie du nouveau prix négocié
        tk.Label(pad_frame, text="Nouveau Prix Négocié unitaire (F CFA) :",
                 font=(POLICE, 10, "bold"), bg=COULEURS["card"], fg=COULEURS["text"]).pack(anchor="w", pady=(6, 4))

        cadre_saisie = tk.Frame(pad_frame, bg=COULEURS["card"])
        cadre_saisie.pack(fill=tk.X, pady=(0, 6))

        self.var_nouveau_prix = tk.StringVar(value=f"{int(self.ligne['pu']):d}" if self.ligne['pu'] == int(self.ligne['pu']) else f"{self.ligne['pu']:.2f}")
        self.entry_prix = tk.Entry(cadre_saisie, textvariable=self.var_nouveau_prix,
                                   font=(POLICE, 16, "bold"), bd=1, relief=tk.SOLID,
                                   bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                                   insertbackground=COULEURS["input_fg"], justify="right")
        self.entry_prix.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        self.entry_prix.focus_set()
        self.entry_prix.select_range(0, tk.END)

        # Boutons de remises rapides
        cadre_remises = tk.Frame(pad_frame, bg=COULEURS["card"])
        cadre_remises.pack(fill=tk.X, pady=(4, 6))

        tk.Label(cadre_remises, text="Remises rapides :", font=(POLICE, 9),
                 bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(side=tk.LEFT, padx=(0, 4))

        for pct in (5, 10, 15):
            p_remise = self.prix_cat * (1.0 - pct / 100.0)
            Bouton(cadre_remises, f"-{pct}%", "secondary",
                   lambda p=p_remise: self._fixer_prix(p), petit=True).pack(side=tk.LEFT, padx=2)

        Bouton(cadre_remises, "Prix Cat.", "info",
               lambda: self._fixer_prix(self.prix_cat), petit=True).pack(side=tk.LEFT, padx=4)

        if self.dernier_prix_info:
            Bouton(cadre_remises, "Hist. Client", "success",
                   self._appliquer_historique, petit=True).pack(side=tk.LEFT, padx=2)

        # Zone d'évaluation de la marge en temps réel
        self.lbl_marge_preview = tk.Label(pad_frame, text="", font=(POLICE, 10, "bold"),
                                          bg=COULEURS["card"], anchor="w", pady=4)
        self.lbl_marge_preview.pack(fill=tk.X)

        self.var_nouveau_prix.trace_add("write", lambda *_: self._evaluer_marge())
        self._evaluer_marge()

        # Boutons de validation (en bas de fenêtre avec espace réservé)
        btn_frame = tk.Frame(pad_frame, bg=COULEURS["card"])
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(16, 0))

        Bouton(btn_frame, "  Annuler  ", "secondary", self.destroy).pack(side=tk.LEFT)
        Bouton(btn_frame, "Valider le prix", "success", self._valider).pack(side=tk.RIGHT)

        self.bind("<Return>", lambda e: self._valider())
        self.bind("<Escape>", lambda e: self.destroy())

    def _fixer_prix(self, val: float):
        v = int(val) if val == int(val) else round(val, 2)
        self.var_nouveau_prix.set(str(v))
        self.entry_prix.select_range(0, tk.END)

    def _appliquer_historique(self):
        if self.dernier_prix_info:
            prix_hist = self.dernier_prix_info['prix']
            self.var_nouveau_prix.set(f"{int(prix_hist):d}" if prix_hist == int(prix_hist) else f"{prix_hist:.2f}")
            self.entry_prix.select_range(0, tk.END)

    def _evaluer_marge(self):
        val = parse_float(self.var_nouveau_prix.get(), -1)
        if val <= 0:
            self.lbl_marge_preview.configure(text="Saisissez un prix supérieur à 0", fg=COULEURS["warning"])
            return

        marge_val = val - self.cout
        marge_pct = (marge_val / val * 100) if val > 0 else 0
        diff_cat = val - self.prix_cat
        diff_pct = (diff_cat / self.prix_cat * 100) if self.prix_cat > 0 else 0

        txt = f"Marge: {fmt_money(marge_val, self.devise)} ({marge_pct:.1f}%)"
        if diff_cat != 0:
            txt += f"  ·  Écart Cat.: {diff_pct:+.1f}%"

        if self.cout > 0 and val < self.cout:
            self.lbl_marge_preview.configure(text=f"⚠ Vente à perte ! {txt}", fg=COULEURS["danger"])
        elif marge_pct >= 20:
            self.lbl_marge_preview.configure(text=f"{txt}", fg=COULEURS["success"])
        else:
            self.lbl_marge_preview.configure(text=f"● {txt}", fg=COULEURS["warning"])

    def _valider(self):
        val = parse_float(self.var_nouveau_prix.get(), 0)
        if val <= 0:
            messagebox.showwarning("Prix invalide", "Veuillez entrer un prix valide supérieur à 0.", parent=self)
            return

        if self.cout > 0 and val < self.cout:
            perte = self.cout - val
            if not messagebox.askyesno(
                    "Vente à perte",
                    f"Le prix saisi ({fmt_money(val, self.devise)}) est inférieur au coût de revient ({fmt_money(self.cout, self.devise)}).\n"
                    f"Perte estimée : {fmt_money(perte, self.devise)} / article.\n\n"
                    "Confirmer ce prix négocié ?", parent=self):
                return

        self.resultat = val
        self.destroy()


class CaisseMixin:
    """Point de vente modernisé — Négociation dynamique de prix & UI ergonomique."""

    def afficher_caisse(self):
        if not self.peut("caisse"):
            return self._refus()
        self._nouvelle_page("Enregistrer une vente", 1)

        self.enregistrement = []       # [{"id","ref","nom","quantite","pu","cout","prix_catalogue"}, ...]
        self._produits_visibles = []   # Cache des suggestions de recherche
        self._clients_cache = db.get_clients()
        self.client_selectionne = None

        # ── Conteneur principal 2 colonnes ──
        grille = tk.Frame(self.zone, bg=COULEURS["bg"])
        grille.pack(fill=tk.BOTH, expand=True)
        grille.columnconfigure(0, weight=4)  # Colonne Gauche (Client + Recherche)
        grille.columnconfigure(1, weight=6)  # Colonne Droite (Panier Négocié)
        grille.rowconfigure(0, weight=1)

        # =========================================================================
        # COLONNE GAUCHE : CLIENT & RECHERCHE PRODUITS
        # =========================================================================
        col_gauche = tk.Frame(grille, bg=COULEURS["bg"])
        col_gauche.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        col_gauche.rowconfigure(1, weight=1)
        col_gauche.columnconfigure(0, weight=1)

        # --- Card 1 : Client & Contexte ---
        carte_client = Carte(col_gauche, "Client & Tarification")
        carte_client.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        cc = carte_client.corps

        tk.Label(cc, text="Sélectionner un client pour voir ses prix négociés :",
                 font=(POLICE, 9), bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(anchor="w")

        self._etiq_clients = {
            f"{c['nom']}" + (f" ({c['telephone']})" if c.get('telephone') else ""): c
            for c in self._clients_cache
        }
        liste_noms_clients = ["Client de passage (Comptant)"] + list(self._etiq_clients.keys())

        f_client_select = tk.Frame(cc, bg=COULEURS["card"])
        f_client_select.pack(fill=tk.X, pady=(6, 4))

        self.cb_client_pos = AutocompleteCombobox(f_client_select, font=(POLICE, 10))
        self.cb_client_pos.set_completion_list(liste_noms_clients)
        self.cb_client_pos.set("Client de passage (Comptant)")
        self.cb_client_pos.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cb_client_pos.bind("<<ComboboxSelected>>", self._sur_changement_client)
        self.cb_client_pos.bind("<Return>", self._sur_changement_client)

        Bouton(f_client_select, "Client", "secondary", self._nouveau_client_rapide, petit=True).pack(side=tk.RIGHT, padx=(6, 0))

        # Badge d'état client (créances / infos)
        self.lbl_info_client = tk.Label(cc, text="Client comptant standard (Prix catalogue par défaut)",
                                        font=(POLICE, 9, "italic"), bg=COULEURS["card"], fg=COULEURS["text_secondary"])
        self.lbl_info_client.pack(anchor="w", pady=(2, 0))

        # --- Card 2 : Saisie & Catalogue Produits ---
        carte_recherche = Carte(col_gauche, "Catalogue & Ajout Article")
        carte_recherche.grid(row=1, column=0, sticky="nsew")
        cr = carte_recherche.corps
        cr.columnconfigure(0, weight=1)
        cr.rowconfigure(2, weight=1)

        # Ligne de recherche + Qté
        f_recherche = tk.Frame(cr, bg=COULEURS["card"])
        f_recherche.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        f_recherche.columnconfigure(0, weight=1)

        tk.Label(f_recherche, text="Rechercher par référence, nom ou scan code-barres :",
                 font=(POLICE, 9), bg=COULEURS["card"], fg=COULEURS["text_secondary"]).grid(row=0, column=0, columnspan=2, sticky="w")

        self.e_recherche = tk.Entry(f_recherche, font=(POLICE, 12),
                                    bd=1, relief=tk.SOLID,
                                    bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                                    insertbackground=COULEURS["input_fg"])
        self.e_recherche.grid(row=1, column=0, sticky="ew", pady=(4, 0), ipady=6)
        self._var_recherche = tk.StringVar()
        self.e_recherche.configure(textvariable=self._var_recherche)
        self._var_recherche.trace_add("write", lambda *_: self._recherche_typing())
        self.e_recherche.bind("<Return>", self._ajouter_premier)
        self.e_recherche.bind("<Down>", self._focus_listbox)
        self.e_recherche.bind("<Escape>", lambda e: self._var_recherche.set(""))
        self.e_recherche.focus_set()

        # Champ Quantité
        qte_box = tk.Frame(f_recherche, bg=COULEURS["card"])
        qte_box.grid(row=1, column=1, sticky="e", padx=(8, 0), pady=(4, 0))
        tk.Label(qte_box, text="Qté:", font=(POLICE, 9),
                 bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(side=tk.LEFT)
        self.var_qte = tk.StringVar(value="1")
        sp_qte = tk.Spinbox(qte_box, from_=1, to=9999, textvariable=self.var_qte,
                            font=(POLICE, 12, "bold"), width=4, justify="center")
        sp_qte.pack(side=tk.LEFT, padx=4)

        # Panneau des suggestions (Listbox enrichie)
        self._frame_liste = tk.Frame(cr, bg=COULEURS["card"])
        self._frame_liste.grid(row=2, column=0, sticky="nsew", pady=(4, 0))

        self._lb_suggestions = tk.Listbox(self._frame_liste,
                                          font=(POLICE, 10),
                                          bg=COULEURS["card"], fg=COULEURS["text"],
                                          selectbackground=COULEURS["selection"],
                                          selectforeground=COULEURS["selection_fg"],
                                          activestyle="none", bd=1, relief=tk.SOLID,
                                          highlightthickness=0, exportselection=False)
        self._lb_suggestions.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._lb_suggestions.bind("<ButtonRelease-1>", self._clic_listbox)
        self._lb_suggestions.bind("<Return>", self._clic_listbox)
        self._lb_suggestions.bind("<Escape>", lambda e: self.e_recherche.focus_set())

        ajouter_scrollbars(self._frame_liste, self._lb_suggestions)

        # =========================================================================
        # COLONNE DROITE : PANIER INTERACTIF & RÉCAPITULATIF NÉGOCIÉ
        # =========================================================================
        col_droite = tk.Frame(grille, bg=COULEURS["bg"])
        col_droite.grid(row=0, column=1, sticky="nsew")
        col_droite.rowconfigure(0, weight=1)
        col_droite.columnconfigure(0, weight=1)

        carte_panier = Carte(col_droite, "Enregistrement & Négociation Panier")
        carte_panier.grid(row=0, column=0, sticky="nsew")
        cp = carte_panier.corps
        cp.columnconfigure(0, weight=1)
        cp.rowconfigure(1, weight=1)

        # Barre d'actions rapides du panier
        actions_panier = tk.Frame(cp, bg=COULEURS["card"])
        actions_panier.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        Bouton(actions_panier, "Négocier le prix (F2)", "primary", self._negocier_selection, petit=True).pack(side=tk.LEFT, padx=(0, 4))
        Bouton(actions_panier, "Qté +1", "secondary", lambda: self._ajuster_qte_selection(1), petit=True).pack(side=tk.LEFT, padx=2)
        Bouton(actions_panier, "Qté -1", "secondary", lambda: self._ajuster_qte_selection(-1), petit=True).pack(side=tk.LEFT, padx=2)
        Bouton(actions_panier, "Supprimer", "danger", self._retirer_ligne_selection, petit=True, outline=True).pack(side=tk.LEFT, padx=6)
        Bouton(actions_panier, "Vider tout", "secondary", self._vider_panier, petit=True, outline=True).pack(side=tk.RIGHT)

        # Table du Panier (Treeview modernisé avec colonnes de négociation)
        cadre_tree = tk.Frame(cp, bg=COULEURS["card"])
        cadre_tree.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        self.tree_panier = ttk.Treeview(
            cadre_tree,
            columns=("nom", "qte", "prix_cat", "pu", "marge", "total", "action"),
            show="headings", height=10, selectmode="browse")

        self.tree_panier.heading("nom", text="Article / Réf.", anchor="w")
        self.tree_panier.heading("qte", text="Qté", anchor="center")
        self.tree_panier.heading("prix_cat", text="Prix Cat.", anchor="e")
        self.tree_panier.heading("pu", text="Prix Négo", anchor="e")
        self.tree_panier.heading("marge", text="Marge", anchor="center")
        self.tree_panier.heading("total", text="Total Net", anchor="e")
        self.tree_panier.heading("action", text="Action", anchor="center")

        self.tree_panier.column("#0", width=0, stretch=False)
        self.tree_panier.column("nom", width=180, minwidth=80, anchor="w", stretch=True)
        self.tree_panier.column("qte", width=45, minwidth=30, anchor="center", stretch=True)
        self.tree_panier.column("prix_cat", width=95, minwidth=60, anchor="e", stretch=True)
        self.tree_panier.column("pu", width=105, minwidth=60, anchor="e", stretch=True)
        self.tree_panier.column("marge", width=70, minwidth=40, anchor="center", stretch=True)
        self.tree_panier.column("total", width=105, minwidth=60, anchor="e", stretch=True)
        self.tree_panier.column("action", width=85, minwidth=50, anchor="center", stretch=True)

        config_lignes_alternees(self.tree_panier)
        self.tree_panier.tag_configure("perte", foreground=COULEURS["danger"], background=COULEURS.get("danger_light", "#fee2e2"))
        self.tree_panier.tag_configure("negocie_bas", foreground=COULEURS["success"])
        self.tree_panier.tag_configure("negocie_haut", foreground=COULEURS["warning"])

        # Scrollbar verticale uniquement (évite le décalage horizontal intempestif)
        vsb_panier = ttk.Scrollbar(cadre_tree, orient="vertical", command=self.tree_panier.yview)
        self.tree_panier.configure(yscrollcommand=vsb_panier.set)
        self.tree_panier.grid(row=0, column=0, sticky="nsew")
        vsb_panier.grid(row=0, column=1, sticky="ns")
        cadre_tree.rowconfigure(0, weight=1)
        cadre_tree.columnconfigure(0, weight=1)

        # Evénements Treeview
        self.tree_panier.bind("<ButtonRelease-1>", self._sur_clic_panier)
        self.tree_panier.bind("<Double-1>", self._sur_double_clic_panier)
        self.tree_panier.bind("<Delete>", lambda e: self._retirer_ligne_selection())
        self.tree_panier.bind("<KP_Delete>", lambda e: self._retirer_ligne_selection())
        self.tree_panier.bind("<plus>", lambda e: self._ajuster_qte_selection(1))
        self.tree_panier.bind("<KP_Add>", lambda e: self._ajuster_qte_selection(1))
        self.tree_panier.bind("<minus>", lambda e: self._ajuster_qte_selection(-1))
        self.tree_panier.bind("<KP_Subtract>", lambda e: self._ajuster_qte_selection(-1))

        # Raccourcis globaux de négociation et validation
        self.root.bind("<F2>", lambda e: self._negocier_selection())
        self.root.bind("<F4>", lambda e: self._retirer_ligne_selection())
        self.root.bind("<F8>", lambda e: self._enregistrer())

        # Panneau de Synthèse Financière & Bouton d'Enregistrement Grand Format
        panneau_total = tk.Frame(cp, bg=COULEURS["total_bg"],
                                 highlightbackground=COULEURS["border"], highlightthickness=1, padx=16, pady=12)
        panneau_total.grid(row=2, column=0, sticky="ew")

        # Ligne résumé des chiffres
        resume_frame = tk.Frame(panneau_total, bg=COULEURS["total_bg"])
        resume_frame.pack(fill=tk.X, pady=(0, 8))

        self.lbl_details_panier = tk.Label(resume_frame, text="0 article(s)",
                                           font=(POLICE, 10), bg=COULEURS["total_bg"], fg=COULEURS["text_secondary"])
        self.lbl_details_panier.pack(side=tk.LEFT)

        self.lbl_ecart_negociation = tk.Label(resume_frame, text="Négociation: 0 F CFA",
                                              font=(POLICE, 9), bg=COULEURS["total_bg"], fg=COULEURS["success"])
        self.lbl_ecart_negociation.pack(side=tk.RIGHT)

        # Montant Total Principal
        self.lbl_total = tk.Label(panneau_total, text="Total : 0 " + self.devise,
                                  font=(POLICE, 20, "bold"),
                                  bg=COULEURS["total_bg"], fg=COULEURS["primary"])
        self.lbl_total.pack(anchor="w", pady=(0, 6))

        # Mode de Paiement Direct
        f_mode_direct = tk.Frame(panneau_total, bg=COULEURS["total_bg"])
        f_mode_direct.pack(fill=tk.X, pady=(0, 6))

        tk.Label(f_mode_direct, text="Mode de paiement :", font=(POLICE, 10, "bold"),
                 bg=COULEURS["total_bg"], fg=COULEURS["text"]).pack(side=tk.LEFT)

        self.cb_mode_caisse = ttk.Combobox(f_mode_direct, state="readonly", font=(POLICE, 10),
                                            values=["Espèces", "Wave", "Orange Money", "MTN Money", "Moov Money", "Crédit"],
                                            width=18)
        self.cb_mode_caisse.current(0)
        self.cb_mode_caisse.pack(side=tk.RIGHT)

        # Client attribué (synchronisé avec le panneau supérieur)
        f_client_direct = tk.Frame(panneau_total, bg=COULEURS["total_bg"])
        f_client_direct.pack(fill=tk.X, pady=(0, 10))

        tk.Label(f_client_direct, text="Client attribué :", font=(POLICE, 10, "bold"),
                 bg=COULEURS["total_bg"], fg=COULEURS["text"]).pack(side=tk.LEFT)

        self.lbl_client_attribue = tk.Label(f_client_direct, text="Client de passage (Comptant)",
                                            font=(POLICE, 10, "bold"), bg=COULEURS["total_bg"],
                                            fg=COULEURS["primary"])
        self.lbl_client_attribue.pack(side=tk.LEFT, padx=(6, 0))

        # Bouton d'encaissement
        btn_enreg = Bouton(panneau_total, "VALIDER ET ENREGISTRER (F8)", "success",
                           self._enregistrer, pady=12)
        btn_enreg.pack(fill=tk.X)

        self._rafraichir_enregistrement()
        self._recherche_typing()

    # ── Gestion des clients ──

    def _sur_changement_client(self, event=None):
        val = self.cb_client_pos.get().strip()

        client = self._etiq_clients.get(val)
        self.client_selectionne = client

        if hasattr(self, 'lbl_client_attribue'):
            self.lbl_client_attribue.configure(text=client['nom'] if client else "Client de passage (Comptant)")

        if client:
            solde = float(client.get("solde_creances", 0) or client.get("dette", 0) or 0)
            txt = f"Client : {client['nom']}"
            if solde > 0:
                txt += f"· CRÉANCE EN COURS : {fmt_money(solde, self.devise)}"
                self.lbl_info_client.configure(text=txt, fg=COULEURS["danger"])
                messagebox.showwarning(
                    "Client en Dette",
                    f"ATTENTION : Le client « {client['nom']} » a déjà une créance impayée de {fmt_money(solde, self.devise)} !\n\n"
                    "Gardez cela à l'esprit avant d'accorder de nouveaux crédits.", parent=self.root)
            else:
                txt += f"  ·  Solde à jour  ·  Tarification préférentielle"
                self.lbl_info_client.configure(text=txt, fg=COULEURS["success"])
        else:
            self.lbl_info_client.configure(text="Client comptant standard (Prix catalogue par défaut)", fg=COULEURS["text_secondary"])

        # Re-déclencher la recherche pour afficher les prix négociés spécifiques
        self._recherche_typing()

    def _nouveau_client_rapide(self):
        nom = simpledialog.askstring("Nouveau client", "Nom complet du client :", parent=self.root)
        if not nom or not nom.strip():
            return
        tel = simpledialog.askstring("Nouveau client", f"Téléphone pour « {nom.strip()} » (optionnel) :", parent=self.root) or ""

        ok, msg = db.add_client(nom.strip(), tel.strip())
        if ok:
            self._clients_cache = db.get_clients()
            self._etiq_clients = {
                f"{c['nom']}" + (f" ({c['telephone']})" if c.get('telephone') else ""): c
                for c in self._clients_cache
            }
            liste_noms = ["Client de passage (Comptant)"] + list(self._etiq_clients.keys())
            if hasattr(self, 'cb_client_pos'):
                self.cb_client_pos.set_completion_list(liste_noms)

            # Sélectionner le nouveau client
            cle = next((k for k, v in self._etiq_clients.items() if v["nom"].lower() == nom.strip().lower()), None)
            if cle:
                if hasattr(self, 'cb_client_pos'):
                    self.cb_client_pos.set(cle)
                self._sur_changement_client()
            self.statut(f"Client {nom.strip()} créé", COULEURS["success"])
        else:
            messagebox.showerror("Erreur", msg, parent=self.root)

    # ── Recherche Produits ──

    def _recherche_typing(self, event=None):
        texte = self._var_recherche.get().strip()
        lb = self._lb_suggestions
        lb.delete(0, tk.END)

        if not texte:
            resultats = db.get_produits(inclure_inactifs=False)[:15]
        else:
            resultats = db.get_produits(search=texte, inclure_inactifs=False)[:25]

        self._produits_visibles = resultats

        if not resultats:
            lb.insert(tk.END, "  Aucun résultat dans le catalogue")
            lb.configure(fg=COULEURS["text_secondary"])
        else:
            lb.configure(fg=COULEURS["text"])
            client_id = self.client_selectionne["id"] if self.client_selectionne else None
            client_nom = self.client_selectionne["nom"] if self.client_selectionne else ""

            for p in resultats:
                sv = p.get("stock_vente", p["stock"])
                sr = p.get("stock_reserve", 0)
                if sv > 0:
                    stock_txt = f"Rayon: {sv}"
                else:
                    stock_txt = "RAYON RUPTURE"
                if sr > 0:
                    stock_txt += f" (Réserve: {sr})"

                prix_cat = float(p["prix_vente"])
                txt_ligne = f"{p['nom'][:30]:<30} │ Cat: {fmt_money(prix_cat, self.devise)} │ {stock_txt}"
                lb.insert(tk.END, txt_ligne)

    def _focus_listbox(self, event=None):
        if self._lb_suggestions.size() > 0:
            self._lb_suggestions.focus_set()
            self._lb_suggestions.selection_set(0)
            return "break"

    def _clic_listbox(self, event=None):
        sel = self._lb_suggestions.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._produits_visibles):
            pid = self._produits_visibles[idx]["id"]
            self._ajouter_produit(pid)
            self._var_recherche.set("")
            self.e_recherche.focus_set()

    def _ajouter_premier(self, event=None):
        texte = self._var_recherche.get().strip()
        if not texte:
            return

        produit = db.trouver_produit(texte)
        if not produit:
            resultats = db.get_produits(search=texte, inclure_inactifs=False)
            if resultats:
                produit = resultats[0]
            else:
                if messagebox.askyesno("Produit introuvable",
                                       f"« {texte} » n'est pas dans le catalogue.\n\n"
                                       "L'ajouter en création rapide ?", parent=self.root):
                    self._ajout_rapide(texte)
                return

        if produit:
            self._ajouter_produit(produit["id"])
            self._var_recherche.set("")
            self.e_recherche.focus_set()

    def _ajouter_produit(self, produit_id):
        produit = db.get_produit(produit_id)
        if not produit:
            messagebox.showerror("Erreur", "Produit introuvable.", parent=self.root)
            return

        try:
            qte = int(self.var_qte.get() or 1)
        except ValueError:
            qte = 1
        if qte <= 0:
            qte = 1

        stock_dispo = produit.get("stock_vente", produit["stock"])
        stock_reserve = produit.get("stock_reserve", 0)

        # Prix par défaut : vérifier si un prix négocié habituel existe pour ce client
        prix_defaut = float(produit["prix_vente"])
        client_id = self.client_selectionne["id"] if self.client_selectionne else None
        client_nom = self.client_selectionne["nom"] if self.client_selectionne else ""
        hist = db.get_dernier_prix_client(produit_id, client_id=client_id, client_nom=client_nom)

        if hist and hist.get("prix"):
            prix_defaut = float(hist["prix"])

        # Recherche si l'article est déjà dans le panier
        for ligne in self.enregistrement:
            if ligne["id"] == produit_id:
                nouvelle_qte = ligne["quantite"] + qte
                if nouvelle_qte > stock_dispo:
                    if stock_reserve > 0 and (nouvelle_qte - stock_dispo) <= stock_reserve:
                        manquant = nouvelle_qte - stock_dispo
                        if messagebox.askyesno(
                                "Stock en Réserve Disponible",
                                f"La quantité en rayon ({stock_dispo}) est insuffisante pour « {produit['nom']} ».\n\n"
                                f"Vous avez {stock_reserve} pièce(s) disponible(s) en RÉSERVE (ENTREPÔT) !\n\n"
                                f"Voulez-vous transférer automatiquement {manquant} pièce(s) de la Réserve vers le Rayon pour valider la vente ?",
                                parent=self.root):
                            ok_tr, msg_tr = db.transferer_stock_depot(produit_id, manquant, source='reserve', destination='vente')
                            if ok_tr:
                                ligne["quantite"] = nouvelle_qte
                                self.var_qte.set("1")
                                self._rafraichir_enregistrement()
                                self.statut(f"Transfert de {manquant} pièce(s) de la réserve vers le rayon effectué", COULEURS["success"])
                                return
                            else:
                                messagebox.showerror("Erreur Transfert", msg_tr, parent=self.root)
                                return
                    messagebox.showwarning(
                        "Stock insuffisant",
                        f"Seulement {stock_dispo} disponible(s) en rayon (et {stock_reserve} en réserve) pour « {produit['nom']} ».",
                        parent=self.root)
                    return
                ligne["quantite"] = nouvelle_qte
                self.var_qte.set("1")
                self._rafraichir_enregistrement()
                return

        if qte > stock_dispo:
            if stock_reserve > 0 and (qte - stock_dispo) <= stock_reserve:
                manquant = qte - stock_dispo
                if messagebox.askyesno(
                        "Stock en Réserve Disponible",
                        f"La quantité demandée ({qte}) dépasse le stock en rayon ({stock_dispo}) pour « {produit['nom']} ».\n\n"
                        f"Cependant, vous avez {stock_reserve} pièce(s) en RÉSERVE (ENTREPÔT) !\n\n"
                        f"Voulez-vous transférer automatiquement {manquant} pièce(s) de la Réserve vers le Rayon pour ajouter cet article au panier ?",
                        parent=self.root):
                    ok_tr, msg_tr = db.transferer_stock_depot(produit_id, manquant, source='reserve', destination='vente')
                    if ok_tr:
                        # Mettre à jour le stock dispo après transfert
                        stock_dispo += manquant
                        self.statut(f"Transfert de {manquant} pièce(s) de la réserve vers le rayon effectué", COULEURS["success"])
                    else:
                        messagebox.showerror("Erreur Transfert", msg_tr, parent=self.root)
                        return
                else:
                    return
            else:
                messagebox.showwarning(
                    "Stock insuffisant",
                    f"Seulement {stock_dispo} disponible(s) en rayon (et {stock_reserve} en réserve) pour « {produit['nom']} ».",
                    parent=self.root)
                return

        cout = float(produit.get("cump") or produit.get("prix_achat") or 0)

        self.enregistrement.append({
            "id": produit_id,
            "ref": produit.get("reference", ""),
            "nom": produit["nom"],
            "quantite": qte,
            "pu": prix_defaut,
            "prix_catalogue": float(produit["prix_vente"]),
            "cout": cout,
        })
        self.var_qte.set("1")
        self._rafraichir_enregistrement()

    def _ajout_rapide(self, nom_suggere=""):
        nom = simpledialog.askstring("Ajout rapide", "Nom de la pièce auto :",
                                     initialvalue=nom_suggere or "", parent=self.root)
        if not nom or not nom.strip():
            return
        prix_str = simpledialog.askstring("Ajout rapide",
                                          f"Prix catalogue pour « {nom.strip()} » (F CFA) :",
                                          initialvalue="", parent=self.root)
        if not prix_str:
            return
        prix = parse_float(prix_str, 0)
        if prix <= 0:
            messagebox.showerror("Erreur", "Le prix doit être supérieur à 0.", parent=self.root)
            return

        ref = f"PRD-TMP-{int(datetime.now().timestamp())}"
        cats = db.get_categories()
        cat_id = cats[0]["id"] if cats else 1

        ok, msg = db.add_produit(
            ref, nom.strip(), prix_vente=prix, prix_achat=0,
            stock_vente=1, stock_reserve=0, categorie_id=cat_id,
            description="Ajouté rapidement depuis la caisse")
        if not ok:
            messagebox.showerror("Erreur", msg, parent=self.root)
            return

        produit = db.trouver_produit(ref)
        if produit:
            self._ajouter_produit(produit["id"])
            self.statut(f"{nom.strip()} ajouté au catalogue", COULEURS["success"])

    # ── Gestion du Panier & Négociation ──

    def _rafraichir_enregistrement(self):
        tree = self.tree_panier
        sel_iid = tree.selection()[0] if tree.selection() else None

        for iid in tree.get_children():
            tree.delete(iid)

        total_cat = 0.0
        total_neg = 0.0

        for i, ligne in enumerate(self.enregistrement):
            qte = ligne["quantite"]
            pu_neg = ligne["pu"]
            prix_cat = ligne.get("prix_catalogue", pu_neg)
            cout = ligne.get("cout", 0)

            subtotal_cat = qte * prix_cat
            subtotal_neg = qte * pu_neg

            total_cat += subtotal_cat
            total_neg += subtotal_neg

            # Calcul des marges et écarts
            marge_unit = pu_neg - cout
            marge_pct = (marge_unit / pu_neg * 100) if pu_neg > 0 else 0

            if cout > 0 and pu_neg < cout:
                marge_txt = f"⚠ {marge_pct:.0f}%"
                tags = zebre(i, ["perte"])
            elif marge_pct >= 20:
                marge_txt = f"▲ {marge_pct:.0f}%"
                tags = zebre(i, ["negocie_bas"])
            else:
                marge_txt = f"● {marge_pct:.0f}%"
                tags = zebre(i, ["negocie_haut"])

            tree.insert("", "end", iid=str(i), values=(
                f"{ligne['nom']}",
                qte,
                fmt_money(prix_cat, self.devise),
                fmt_money(pu_neg, self.devise),
                marge_txt,
                fmt_money(subtotal_neg, self.devise),
                "Modifier"),
                tags=tags)

        if sel_iid and sel_iid in tree.get_children():
            tree.selection_set(sel_iid)

        # Mise à jour des totaux
        nb_articles = sum(l["quantite"] for l in self.enregistrement)
        ecart_total = total_neg - total_cat
        ecart_pct = (ecart_total / total_cat * 100) if total_cat > 0 else 0

        self.lbl_total.configure(text=f"Total : {fmt_money(total_neg, self.devise)}")
        self.lbl_details_panier.configure(text=f"{nb_articles} article(s) au panier")

        if ecart_total < 0:
            self.lbl_ecart_negociation.configure(
                text=f"Remise négociée: {fmt_money(abs(ecart_total), self.devise)} ({ecart_pct:.1f}%)",
                fg=COULEURS["success"])
        elif ecart_total > 0:
            self.lbl_ecart_negociation.configure(
                text=f"Majoration: +{fmt_money(ecart_total, self.devise)} (+{ecart_pct:.1f}%)",
                fg=COULEURS["warning"])
        else:
            self.lbl_ecart_negociation.configure(text="Prix conforme au catalogue", fg=COULEURS["text_secondary"])

    def _ligne_selectionnee_idx(self):
        sel = self.tree_panier.selection()
        if not sel:
            return None
        try:
            idx = int(sel[0])
            if 0 <= idx < len(self.enregistrement):
                return idx
        except ValueError:
            pass
        return None

    def _sur_clic_panier(self, event):
        iid = self.tree_panier.identify_row(event.y)
        if not iid:
            return
        col = self.tree_panier.identify_column(event.x)
        try:
            idx = int(iid)
            if col in ("#4", "#7"):
                self.tree_panier.selection_set(iid)
                self._negocier_prix_idx(idx)
        except ValueError:
            pass

    def _sur_double_clic_panier(self, event):
        iid = self.tree_panier.identify_row(event.y)
        if not iid:
            return
        col = self.tree_panier.identify_column(event.x)
        self.tree_panier.selection_set(iid)
        idx = int(iid)

        if col in ("#4", "#5", "#7"):
            self._negocier_prix_idx(idx)
        else:
            self._modifier_qte_idx(idx)

    def _negocier_selection(self):
        idx = self._ligne_selectionnee_idx()
        if idx is None and len(self.enregistrement) > 0:
            idx = len(self.enregistrement) - 1
            self.tree_panier.selection_set(str(idx))

        if idx is not None:
            self._negocier_prix_idx(idx)
        elif not self.enregistrement:
            messagebox.showinfo("Panier vide", "Veuillez ajouter au moins un article au panier avant de négocier.", parent=self.root)

    def _negocier_prix_idx(self, idx: int):
        if idx < 0 or idx >= len(self.enregistrement):
            return
        ligne = self.enregistrement[idx]
        client_nom = self.client_selectionne["nom"] if self.client_selectionne else ""
        client_id = self.client_selectionne["id"] if self.client_selectionne else None

        dlg = DialogueNegociationPrix(self.root, ligne, client_nom=client_nom, client_id=client_id, devise=self.devise)
        self.root.wait_window(dlg)

        if dlg.resultat is not None:
            ligne["pu"] = dlg.resultat
            self._rafraichir_enregistrement()

    def _modifier_qte_idx(self, idx: int):
        if idx < 0 or idx >= len(self.enregistrement):
            return
        ligne = self.enregistrement[idx]
        produit = db.get_produit(ligne["id"])
        stock_dispo = produit.get("stock_vente", produit["stock"]) if produit else 9999

        nouveau = simpledialog.askinteger(
            "Quantité", f"Ajuster la quantité pour « {ligne['nom']} » (Dispo : {stock_dispo}) :",
            initialvalue=ligne["quantite"], minvalue=0, maxvalue=9999, parent=self.root)

        if nouveau is None:
            return
        if nouveau == 0:
            del self.enregistrement[idx]
        else:
            if nouveau > stock_dispo:
                messagebox.showwarning("Stock insuffisant", f"Seulement {stock_dispo} en rayon.", parent=self.root)
                return
            ligne["quantite"] = nouveau
        self._rafraichir_enregistrement()

    def _ajuster_qte_selection(self, delta: int):
        idx = self._ligne_selectionnee_idx()
        if idx is None:
            return
        ligne = self.enregistrement[idx]
        nouvelle = ligne["quantite"] + delta

        if nouvelle <= 0:
            del self.enregistrement[idx]
        else:
            produit = db.get_produit(ligne["id"])
            stock_dispo = produit.get("stock_vente", produit["stock"]) if produit else 9999
            if nouvelle > stock_dispo:
                messagebox.showwarning("Stock insuffisant", f"Seulement {stock_dispo} en rayon.", parent=self.root)
                return
            ligne["quantite"] = nouvelle

        self._rafraichir_enregistrement()

    def _retirer_ligne_selection(self):
        idx = self._ligne_selectionnee_idx()
        if idx is not None:
            del self.enregistrement[idx]
            self._rafraichir_enregistrement()

    def _vider_panier(self):
        if not self.enregistrement:
            return
        if messagebox.askyesno("Vider l'enregistrement", "Voulez-vous retirer tous les articles du panier ?", parent=self.root):
            self.enregistrement.clear()
            self._rafraichir_enregistrement()

    # ── Validation & Encaissement ──

    # ── Validation & Encaissement ──

    def _enregistrer(self, forcer_modal=False):
        if not self.enregistrement:
            messagebox.showinfo("Panier vide", "Veuillez ajouter au moins une pièce au panier.", parent=self.root)
            return

        mode_paiement = self.cb_mode_caisse.get() if hasattr(self, 'cb_mode_caisse') else "Espèces"
        client = self.client_selectionne

        if mode_paiement == db.MODE_CREDIT and not client:
            messagebox.showwarning("Client requis", "Veuillez sélectionner un client pour une vente à crédit.", parent=self.root)
            return

        if client:
            solde = float(client.get("solde_creances", 0) or client.get("dette", 0) or 0)
            if solde > 0 and mode_paiement == db.MODE_CREDIT:
                if not messagebox.askyesno(
                        "⚠ Créance existante",
                        f"Le client « {client['nom']} » a déjà un immatriculé de créances impayées de {fmt_money(solde, self.devise)}.\n\n"
                        "Voulez-vous quand même lui accorder cette nouvelle vente à crédit ?", parent=self.root):
                    return

        if forcer_modal:
            sous_total = sum(l["quantite"] * l["pu"] for l in self.enregistrement)
            items = [dict(l) for l in self.enregistrement]
            d = DialoguePaiementSimple(self.root, sous_total, items, self._clients_cache)
            if hasattr(self, 'cb_mode_caisse') and hasattr(d, 'cb_mode'):
                d.cb_mode.set(mode_paiement)
            if client:
                cle_client = next((k for k, v in self._etiq_clients.items() if v["id"] == client["id"]), None)
                if cle_client and hasattr(d, 'cb_client'):
                    d.cb_client.set(cle_client)
            infos = d.attendre()
            if not infos:
                return
            client_nom = infos["client_nom"]
            items_reels = infos["items_reels"]
            remise = infos["remise"]
            mode_paiement = infos["mode_paiement"]
            montant_paye = infos["montant_paye"]
            client_id = infos["client_id"]
        else:
            client_nom = client["nom"] if client else "Client de passage"
            client_id = client["id"] if client else None
            items_reels = [(l["id"], l["quantite"], l["pu"]) for l in self.enregistrement]
            remise = 0
            montant_paye = sum(l[1] * l[2] for l in items_reels) if mode_paiement != "Crédit" else 0

        ok, message, vente_id = db.create_vente(
            client_nom, items_reels,
            remise=remise,
            mode_paiement=mode_paiement,
            montant_paye=montant_paye,
            client_id=client_id)

        if not ok:
            messagebox.showerror("Vente refusée", message, parent=self.root)
            return

        for l in items_reels:
            try:
                pid, qte, pu = l[0], l[1], l[2]
                db.log_action("Vente Directe", f"Produit #{pid} ({qte}x) vendu à {pu} F CFA pour {client_nom} [{mode_paiement}]")
            except Exception:
                pass

        self.enregistrement.clear()
        self._rafraichir_enregistrement()
        self._maj_badge_alertes()
        self.statut(f"Vente {message} enregistrée avec succès ({mode_paiement}) !", COULEURS["success"])
        self._afficher_flash_enregistrement(message, mode_paiement)
        self.e_recherche.focus_set()
        self._sync_cloud()

    def _afficher_flash_enregistrement(self, num_vente, mode):
        try:
            bandeau = tk.Frame(self.zone, bg=COULEURS["success"], padx=24, pady=12,
                               highlightbackground="white", highlightthickness=2)
            bandeau.place(relx=0.5, rely=0.06, anchor="n")
            lbl = tk.Label(bandeau, text=f"VENTE {num_vente} ENREGISTRÉE AVEC SUCCÈS ! ({mode})",
                           font=(POLICE, 12, "bold"), bg=COULEURS["success"], fg="white")
            lbl.pack()
            self.root.after(2400, lambda: bandeau.destroy() if bandeau.winfo_exists() else None)
        except Exception:
            pass
