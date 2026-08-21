"""
SOPAUTO - Mouvements
"""
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

import database as db
from ui_widgets import (COULEURS, POLICE, Bouton, TableauTriable,
                        ajouter_scrollbars, fmt_date, fmt_money, zebre)


class MouvementsMixin:
    """Historique des mouvements de stock — journal complet.

    Entrées, sorties, corrections, transferts. Filtre par type/produit/date.
    """

    def afficher_mouvements(self, produit_id=None):
        self._nouvelle_page("Historique des mouvements", 7)
        Bouton(self.zone_actions, "Exporter CSV", "info",
               lambda: self._proposer_ouverture(db.exporter_mouvements()),
               petit=True).pack(side=tk.LEFT, padx=3)

        self._filtre_produit_mvt = produit_id
        barre = tk.Frame(self.zone, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))

        tk.Label(barre, text="Type :", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.filtre_type = ttk.Combobox(barre, state="readonly", width=14, font=(POLICE, 9),
                                        values=["Tous", "Entrées", "Sorties", "Corrections", "Transferts"])
        self.filtre_type.current(0)
        self.filtre_type.pack(side=tk.LEFT, padx=(4, 14))
        self.filtre_type.bind("<<ComboboxSelected>>", lambda e: self._charger_mouvements())

        tk.Label(barre, text="Du :", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.e_mvt_debut = tk.Entry(barre, font=(POLICE, 9), width=11, bd=1, relief=tk.SOLID)
        self.e_mvt_debut.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
        self.e_mvt_debut.pack(side=tk.LEFT, padx=4)
        tk.Label(barre, text="au :", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.e_mvt_fin = tk.Entry(barre, font=(POLICE, 9), width=11, bd=1, relief=tk.SOLID)
        self.e_mvt_fin.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.e_mvt_fin.pack(side=tk.LEFT, padx=4)
        Bouton(barre, "Filtrer", "primary", self._charger_mouvements,
               petit=True).pack(side=tk.LEFT, padx=8)

        if produit_id:
            p = db.get_produit(produit_id)
            tk.Label(barre, text=f"Produit : {p['nom'] if p else produit_id}",
                     font=(POLICE, 9), bg=COULEURS["bg"],
                     fg=COULEURS["primary"]).pack(side=tk.LEFT, padx=12)
            Bouton(barre, "Tous les produits", "secondary",
                   lambda: self.afficher_mouvements(), petit=True).pack(side=tk.LEFT)

        self.lbl_resume_mvt = tk.Label(barre, text="", font=(POLICE, 9),
                                       bg=COULEURS["bg"], fg=COULEURS["primary"])
        self.lbl_resume_mvt.pack(side=tk.RIGHT, padx=8)

        cadre = tk.Frame(self.zone, bg=COULEURS["card"])
        cadre.pack(fill=tk.BOTH, expand=True)
        self.tab_mouvements = TableauTriable(cadre, [
            ("date", "Date", 135, "w", False),
            ("type", "Type", 110, "w", False),
            ("ref", "Référence", 100, "w", False),
            ("produit", "Produit", 220, "w", False),
            ("qte", "Qté", 60, "center", True),
            ("avant", "Avant", 60, "center", True),
            ("apres", "Après", 60, "center", True),
            ("pu", "P.U.", 85, "e", True),
            ("doc", "Document", 120, "w", False),
            ("notes", "Notes", 200, "w", False),
            ("user", "Utilisateur", 100, "w", False)])
        ajouter_scrollbars(cadre, self.tab_mouvements)
        self._charger_mouvements()


    def _charger_mouvements(self):
        types = {"Tous": None, "Entrées": "entree", "Sorties": "sortie",
                 "Corrections": "correction", "Transferts": "transfert"}
        mvts = db.get_mouvements(produit_id=self._filtre_produit_mvt,
                                 type_mouvement=types.get(self.filtre_type.get()),
                                 date_debut=self.e_mvt_debut.get().strip() or None,
                                 date_fin=self.e_mvt_fin.get().strip() or None,
                                 limit=2000)
        libelles = {"entree": "Entrée", "sortie": "Sortie",
                    "correction": "Correction", "transfert": "Transfert"}
        t = self.tab_mouvements
        t.delete(*t.get_children())
        entrees = sorties = 0
        for i, m in enumerate(mvts):
            tags = (m["type_mouvement"],) if m["type_mouvement"] in ("entree", "sortie") else ()
            if m["type_mouvement"] == "entree":
                entrees += m["quantite"]
            elif m["type_mouvement"] == "sortie":
                sorties += m["quantite"]
            t.insert("", tk.END, tags=zebre(i, tags), values=(
                fmt_date(m["date_mouvement"]), libelles.get(m["type_mouvement"], m["type_mouvement"]),
                m["reference"] or "", m["produit_nom"] or "(supprimé)", m["quantite"],
                m.get("stock_avant", ""), m.get("stock_apres", ""),
                fmt_money(m["prix_unitaire"]), m["reference_doc"], m["notes"],
                m.get("utilisateur", "")))
        self.lbl_resume_mvt.configure(
            text=f"{len(mvts)} mouvement(s) · +{entrees} entrée(s) / −{sorties} sortie(s)")

    # ═══ RAPPORTS ══════════════════════════════════════


