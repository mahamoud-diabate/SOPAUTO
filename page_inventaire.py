
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import database as db
import metier_v3 as m3
from ui_widgets import (COULEURS, POLICE, Bouton, Carte,
                        TableauTriable, fmt_date, fmt_money, zebre,
                        ajouter_scrollbars)
from dialogues import (DialogueOuvrirInventaire, DialogueComptage)

class InventaireMixin:
    """Mixin : Inventaire physique."""

# ═══════════════════════════════════════════════════
    #  📋 INVENTAIRE
    # ═══════════════════════════════════════════════════

    def afficher_inventaire(self):
        if not self.peut("stock"):
            return self._refus()
        self._nouvelle_page("📋 Inventaire physique", self._idx_menu("Inventaire"))

        Bouton(self.zone_actions, "➕ Ouvrir un inventaire", "primary",
               self._ouvrir_inventaire, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "🔢 Saisir le comptage", "info",
               self._saisir_comptage, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "✅ Clôturer", "success",
               self._cloturer_inventaire, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "📤 Exporter", "secondary",
               self._exporter_inventaire, petit=True).pack(side=tk.LEFT, padx=3)

        conteneur = tk.Frame(self.zone, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        c1 = Carte(conteneur, "Inventaires")
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        f_tree_c1 = tk.Frame(c1.corps, bg=COULEURS["card"])
        f_tree_c1.pack(fill=tk.BOTH, expand=True)
        self.tab_inventaires = TableauTriable(f_tree_c1, [
            ("num", "N°", 120, "w", False),
            ("depot", "Dépôt", 105, "w", False),
            ("debut", "Ouvert le", 100, "w", False),
            ("avance", "Comptés", 75, "center", False),
            ("ecarts", "Écarts", 55, "center", True),
            ("valeur", "Impact", 100, "e", True),
            ("statut", "Statut", 85, "center", False)], height=16)
        ajouter_scrollbars(f_tree_c1, self.tab_inventaires)
        self.tab_inventaires.bind("<<TreeviewSelect>>", lambda e: self._charger_inv_lignes())

        c2 = Carte(conteneur, "Lignes de comptage")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        barre2 = tk.Frame(c2.corps, bg=COULEURS["card"])
        barre2.pack(fill=tk.X, pady=(0, 6))
        self.var_inv_ecarts = tk.BooleanVar(value=False)
        tk.Checkbutton(barre2, text="Écarts seulement", variable=self.var_inv_ecarts,
                       font=(POLICE, 9), bg=COULEURS["card"], fg=COULEURS["text"],
                       selectcolor=COULEURS["card"], activebackground=COULEURS["card"],
                       command=self._charger_inv_lignes).pack(side=tk.LEFT)
        self.lbl_inv_resume = tk.Label(barre2, text="", font=(POLICE, 9, "bold"),
                                       bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_inv_resume.pack(side=tk.RIGHT)

        f_tree_c2 = tk.Frame(c2.corps, bg=COULEURS["card"])
        f_tree_c2.pack(fill=tk.BOTH, expand=True)
        self.tab_inv_lignes = TableauTriable(f_tree_c2, [
            ("ref", "Réf.", 95, "w", False),
            ("nom", "Produit", 190, "w", False),
            ("theo", "Théorique", 75, "center", True),
            ("compte", "Compté", 70, "center", True),
            ("ecart", "Écart", 60, "center", True),
            ("valeur", "Valeur écart", 105, "e", True),
            ("motif", "Motif", 105, "w", False)], height=15)
        ajouter_scrollbars(f_tree_c2, self.tab_inv_lignes)
        self.tab_inv_lignes.bind("<Double-1>", lambda e: self._saisir_comptage())

        tk.Label(c2.corps, text="Double-cliquez sur une ligne pour saisir la quantité comptée.",
                 font=(POLICE, 9), bg=COULEURS["card"],
                 fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(6, 0))

        self._charger_inventaires()

    def _charger_inventaires(self):
        libelles = {"en_cours": "🔄 En cours", "cloture": "✅ Clôturé",
                    "annule": "❌ Annulé"}
        t = self.tab_inventaires
        t.delete(*t.get_children())
        for i, inv in enumerate(m3.get_inventaires()):
            tags = ("alerte",) if inv["statut"] == "en_cours" else ()
            t.insert("", tk.END, iid=inv["id"], tags=zebre(i, tags), values=(
                inv["numero"] or f"#{inv['id']}", inv["depot_nom"] or "Tous",
                fmt_date(inv["date_debut"], False),
                f"{inv['nb_comptes']}/{inv['nb_lignes']}",
                inv["nb_ecarts"], fmt_money(inv["valeur_ecart"]),
                libelles.get(inv["statut"], inv["statut"])))
        enfants = t.get_children()
        if enfants:
            t.selection_set(enfants[0])
        self._charger_inv_lignes()

    def _charger_inv_lignes(self):
        sel = self.tab_inventaires.selection()
        t = self.tab_inv_lignes
        t.delete(*t.get_children())
        if not sel:
            self.lbl_inv_resume.configure(text="")
            return
        lignes = m3.get_inventaire_lignes(int(sel[0]), self.var_inv_ecarts.get())
        nb_comptes = impact = 0
        for i, l in enumerate(lignes):
            compte = l["stock_compte"]
            if compte is not None:
                nb_comptes += 1
                impact += l["valeur_ecart"] or 0
            tags = ()
            if compte is not None and l["ecart"]:
                tags = ("rupture",) if l["ecart"] < 0 else ("alerte",)
            t.insert("", tk.END, iid=l["produit_id"], tags=zebre(i, tags), values=(
                l["reference"], l["produit_nom"], l["stock_theorique"],
                "—" if compte is None else compte,
                "" if compte is None else f"{l['ecart']:+d}",
                "" if compte is None else fmt_money(l["valeur_ecart"]),
                l["motif"] or ""))
        self.lbl_inv_resume.configure(
            text=f"{nb_comptes}/{len(lignes)} compté(s) · impact {fmt_money(impact, self.devise)}")

    def _ouvrir_inventaire(self):
        depots = m3.get_depots()
        d = DialogueOuvrirInventaire(self.root, depots, db.get_categories())
        if not d.resultat:
            return
        depot_id, categorie_id, notes = d.resultat
        ok, msg, _ = m3.ouvrir_inventaire(depot_id, categorie_id, notes)
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self.statut(msg, COULEURS["success"])
            self._charger_inventaires()

    def _saisir_comptage(self):
        sel_inv = self.tab_inventaires.selection()
        if not sel_inv:
            messagebox.showinfo("Information", "Sélectionnez un inventaire.",
                                parent=self.root)
            return
        inv_id = int(sel_inv[0])
        inv = next((x for x in m3.get_inventaires() if x["id"] == inv_id), None)
        if not inv or inv["statut"] != "en_cours":
            messagebox.showinfo("Information",
                                "Cet inventaire est clôturé : le comptage n'est plus modifiable.",
                                parent=self.root)
            return
        sel = self.tab_inv_lignes.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez un produit à compter.",
                                parent=self.root)
            return
        produit_id = int(sel[0])
        ligne = next((l for l in m3.get_inventaire_lignes(inv_id)
                      if l["produit_id"] == produit_id), None)
        if not ligne:
            return
        motifs = (db.get_parametres().get("motifs_ecart") or "Vol,Casse,Autre").split(",")
        d = DialogueComptage(self.root, ligne, motifs)
        if not d.resultat:
            return
        compte, motif, notes = d.resultat
        ok, msg = m3.saisir_comptage(inv_id, produit_id, compte, motif, notes)
        if not ok:
            messagebox.showwarning("Impossible", msg, parent=self.root)
        else:
            self.statut(msg, COULEURS["success"] if "conforme" in msg else COULEURS["warning"])
        self._charger_inv_lignes()
        self._charger_inventaires_selection(inv_id)

    def _charger_inventaires_selection(self, inv_id):
        """Recharge la liste en conservant la sélection courante."""
        self._charger_inventaires()
        try:
            if str(inv_id) in self.tab_inventaires.get_children():
                self.tab_inventaires.selection_set(str(inv_id))
        except tk.TclError:
            pass

    def _cloturer_inventaire(self):
        sel = self.tab_inventaires.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez un inventaire.",
                                parent=self.root)
            return
        inv_id = int(sel[0])
        inv = next((x for x in m3.get_inventaires() if x["id"] == inv_id), None)
        if not inv or inv["statut"] != "en_cours":
            messagebox.showinfo("Information", "Cet inventaire est déjà clôturé.",
                                parent=self.root)
            return
        ecarts = m3.get_inventaire_lignes(inv_id, True)
        impact = sum(l["valeur_ecart"] or 0 for l in ecarts)
        non_comptes = inv["nb_lignes"] - inv["nb_comptes"]

        message = (f"Inventaire {inv['numero']}\n\n"
                   f"{inv['nb_comptes']}/{inv['nb_lignes']} produit(s) compté(s)\n"
                   f"{len(ecarts)} écart(s) — impact {fmt_money(impact, self.devise)}\n")
        if non_comptes:
            message += (f"\n⚠ {non_comptes} produit(s) NON compté(s) : "
                        f"leur stock restera inchangé.\n")
        message += ("\nAppliquer les écarts au stock réel ?\n\n"
                    "• Oui = le stock est ajusté sur le comptage\n"
                    "• Non = les écarts sont constatés sans toucher au stock")
        reponse = messagebox.askyesnocancel("Clôturer l'inventaire", message,
                                            parent=self.root)
        if reponse is None:
            return
        ok, msg = m3.cloturer_inventaire(inv_id, appliquer=bool(reponse))
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self.statut(msg, COULEURS["success"])
            self._charger_inventaires()
            self._maj_badge_alertes()

    def _exporter_inventaire(self):
        sel = self.tab_inventaires.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez un inventaire.",
                                parent=self.root)
            return
        inv_id = int(sel[0])
        lignes = m3.get_inventaire_lignes(inv_id)
        donnees = [[l["reference"], l["produit_nom"], l["stock_theorique"],
                    "" if l["stock_compte"] is None else l["stock_compte"],
                    "" if l["stock_compte"] is None else l["ecart"],
                    f"{l['cump_unitaire']:.0f}",
                    "" if l["stock_compte"] is None else f"{l['valeur_ecart']:.0f}",
                    l["motif"] or ""] for l in lignes]
        chemin = db.export_csv(
            f"inventaire_{inv_id}_{datetime.now():%Y%m%d_%H%M}.csv",
            ["Référence", "Produit", "Théorique", "Compté", "Écart",
             "CUMP", "Valeur écart", "Motif"], donnees)
        self._proposer_ouverture(chemin)
