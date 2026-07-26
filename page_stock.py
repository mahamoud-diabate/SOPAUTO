"""
SODIPAC - Stock
Généré automatiquement depuis main.py
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime, timedelta
from typing import Any

import database as db
import analyse_prix
import factures
import export_pdf
from dialogues import (DialogueCategorie, DialogueClient, DialogueMouvement, DialoguePaiement,
                       DialogueProduit, DialogueUtilisateur, DialogueFournisseur)
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, EntreeRecherche,
                        TableauTriable, ajouter_scrollbars, centrer_fenetre,
                        fmt_date, fmt_money, infobulle, zebre)


class StockMixin:
    """Gestion du stock — état, mouvements, réapprovisionnement.

    Affiche stock total/vente/réserve avec valeur CUMP, filtres alerte/rupture.
    """

    def afficher_stock(self):
        if not self.peut("stock"):
            return self._refus()
        self._nouvelle_page("📋 Gestion des stocks", 3)

        Bouton(self.zone_actions, "📥 Entrée", "success",
               lambda: self._mouvement("entree"), petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "📤 Sortie", "danger",
               lambda: self._mouvement("sortie"), petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "🔧 Inventaire", "warning",
               lambda: self._mouvement("correction"), petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "🔄 Transfert", "info",
               lambda: self._mouvement("transfert"), petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "📄 Bon de réappro", "info",
               self.generer_reappro, petit=True).pack(side=tk.LEFT, padx=3)

        barre = tk.Frame(self.zone, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        self.rech_stock = EntreeRecherche(barre, "Rechercher un produit…", 36,
                                          callback=self._charger_stock)
        self.rech_stock.pack(side=tk.LEFT)
        self.var_alertes_stock = tk.BooleanVar(value=False)
        tk.Checkbutton(barre, text="⚠ Sous le seuil uniquement", variable=self.var_alertes_stock,
                       bg=COULEURS["bg"], font=(POLICE, 9), activebackground=COULEURS["bg"],
                       command=self._charger_stock).pack(side=tk.LEFT, padx=14)
        self.lbl_resume_stock = tk.Label(barre, text="", font=(POLICE, 9, "bold"),
                                         bg=COULEURS["bg"], fg=COULEURS["primary"])
        self.lbl_resume_stock.pack(side=tk.RIGHT, padx=8)

        cadre = tk.Frame(self.zone, bg=COULEURS["card"])
        cadre.pack(fill=tk.BOTH, expand=True)
        self.tab_stock = TableauTriable(cadre, [
            ("ref", "Référence", 105, "w", False),
            ("nom", "Produit", 230, "w", False),
            ("cat", "Catégorie", 120, "w", False),
            ("reserve", "Réserve", 65, "center", True),
            ("vente", "Vente", 60, "center", True),
            ("total", "Total", 60, "center", True),
            ("mini", "Seuil", 55, "center", True),
            ("etat", "État", 100, "center", False),
            ("pa", "P.A.", 80, "e", True),
            ("valeur", "Valeur", 100, "e", True),
            ("emp", "Empl.", 90, "w", False)])
        ajouter_scrollbars(cadre, self.tab_stock)
        self.tab_stock.bind("<Double-1>", lambda e: self._mouvement_depuis_stock())
        infobulle(self.tab_stock, "Double-clic : entrée de stock rapide")
        self._charger_stock()


    def _charger_stock(self):
        produits = db.get_produits(search=self.rech_stock.get(),
                                   seulement_alertes=self.var_alertes_stock.get(),
                                   inclure_inactifs=False)
        t = self.tab_stock
        t.delete(*t.get_children())
        valeur = 0
        for i, p in enumerate(produits):
            if p["stock"] <= 0:
                etat, tags = "🔴 Rupture", ("rupture",)
            elif p["stock"] <= p["stock_mini"]:
                etat, tags = "🟠 Alerte", ("alerte",)
            else:
                etat, tags = "🟢 OK", ()
            valeur += p["valeur_stock"] or 0
            t.insert("", tk.END, iid=p["id"], tags=zebre(i, tags), values=(
                p["reference"], p["nom"], p["categorie_nom"] or "—",
                p.get("stock_reserve", 0), p.get("stock_vente", 0),
                p["stock"], p["stock_mini"], etat,
                fmt_money(p["prix_achat"]),
                fmt_money(p["valeur_stock"]), p["emplacement"]))
        self.lbl_resume_stock.configure(
            text=f"{len(produits)} produit(s) · valeur totale {fmt_money(valeur, self.devise)}")


    def _mouvement(self, type_mvt, produit_id=None):
        d = DialogueMouvement(self.root, type_mvt, produit_id)
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            if hasattr(self, "tab_stock") and self.tab_stock.winfo_exists():
                self._charger_stock()
            self._maj_badge_alertes()


    def _mouvement_depuis_stock(self):
        sel = self.tab_stock.selection()
        if sel:
            self._mouvement("entree", int(sel[0]))


    def generer_reappro(self):
        chemin = factures.generer_liste_reappro()
        self.statut(f"Bon de réapprovisionnement généré : {chemin}", COULEURS["success"])

    # ═══ CLIENTS ═══════════════════════════════════════


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
        """Génère un PDF de la vente sélectionnée (via Edge/Chrome headless)."""
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez une vente.", parent=self.root)
            return
        if not export_pdf.moteur_disponible():
            messagebox.showinfo(
                "PDF indisponible",
                "Aucun navigateur trouvé pour générer le PDF.\n\n"
                "Utilisez « Facture A4 » puis Ctrl+P → "
                "« Enregistrer au format PDF ».", parent=self.root)
            return
        self.statut(f"Génération du PDF via {export_pdf.nom_moteur()}…")
        self.root.update_idletasks()
        ok, res = export_pdf.facture_pdf(int(sel[0]), format_ticket=ticket, ouvrir=True)
        if ok:
            self.statut(f"PDF créé : {os.path.basename(res)}", COULEURS["success"])
        else:
            messagebox.showwarning("PDF impossible", res, parent=self.root)
            self.statut("Échec de la génération PDF", COULEURS["danger"])

    # ═══ CAISSE ════════════════════════════════════════


