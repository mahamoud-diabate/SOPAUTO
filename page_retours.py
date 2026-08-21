
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import database as db
import metier_v3 as m3
from ui_widgets import (COULEURS, POLICE, Bouton, Carte,
                        TableauTriable, fmt_date, fmt_money, zebre,
                        ajouter_scrollbars)
from dialogues import DialogueRetour

class RetoursMixin:
    """Mixin : Retours et avoirs."""

# ═══════════════════════════════════════════════════
    #  ↩️ RETOURS
    # ═══════════════════════════════════════════════════

    def afficher_retours(self):
        if not self.peut("caisse"):
            return self._refus()
        self._nouvelle_page("Retours et avoirs", self._idx_menu("Retours"))

        Bouton(self.zone_actions, "Enregistrer un retour", "primary",
               self._nouveau_retour, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "Actualiser", "secondary",
               self.afficher_retours, petit=True).pack(side=tk.LEFT, padx=3)

        conteneur = tk.Frame(self.zone, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        c1 = Carte(conteneur, "Retours enregistrés")
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        f_tree_c1 = tk.Frame(c1.corps, bg=COULEURS["card"])
        f_tree_c1.pack(fill=tk.BOTH, expand=True)
        self.tab_retours = TableauTriable(f_tree_c1, [
            ("num", "N° retour", 125, "w", False),
            ("date", "Date", 130, "w", False),
            ("vente", "Vente d'origine", 130, "w", False),
            ("client", "Client", 150, "w", False),
            ("motif", "Motif", 175, "w", False),
            ("nb", "Lignes", 55, "center", True),
            ("total", "Montant", 105, "e", True),
            ("mode", "Remboursement", 120, "w", False)], height=16)
        ajouter_scrollbars(f_tree_c1, self.tab_retours)
        self.tab_retours.bind("<<TreeviewSelect>>", lambda e: self._charger_retour_lignes())

        c2 = Carte(conteneur, "Détail du retour")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        f_tree_c2 = tk.Frame(c2.corps, bg=COULEURS["card"])
        f_tree_c2.pack(fill=tk.BOTH, expand=True)
        self.tab_retour_lignes = TableauTriable(f_tree_c2, [
            ("ref", "Réf.", 90, "w", False),
            ("nom", "Article", 145, "w", False),
            ("qte", "Qté", 45, "center", True),
            ("total", "Total", 85, "e", True),
            ("stock", "En stock", 70, "center", False)], height=16)
        ajouter_scrollbars(f_tree_c2, self.tab_retour_lignes)
        self.lbl_retour_info = tk.Label(c2.corps, text="Sélectionnez un retour",
                                        font=(POLICE, 9), bg=COULEURS["card"],
                                        fg=COULEURS["text_secondary"], justify="left")
        self.lbl_retour_info.pack(anchor="w", pady=(8, 0))

        self._charger_retours()

    def _charger_retours(self):
        t = self.tab_retours
        t.delete(*t.get_children())
        total = 0.0
        for i, r in enumerate(m3.get_retours()):
            total += r["total"]
            t.insert("", tk.END, iid=r["id"], tags=zebre(i), values=(
                r["numero"] or f"#{r['id']}", fmt_date(r["date_retour"]),
                r["vente_numero"] or "—", r["client_nom"] or "—",
                r["motif"] or "—", r["nb_lignes"], fmt_money(r["total"]),
                r["mode_remboursement"]))
        self.statut(f"{len(t.get_children())} retour(s) · "
                    f"total {fmt_money(total, self.devise)}")
        self._charger_retour_lignes()

    def _charger_retour_lignes(self):
        sel = self.tab_retours.selection()
        t = self.tab_retour_lignes
        t.delete(*t.get_children())
        if not sel:
            self.lbl_retour_info.configure(text="Sélectionnez un retour")
            return
        lignes = m3.get_retour_details(int(sel[0]))
        for i, l in enumerate(lignes):
            t.insert("", tk.END, tags=zebre(i, () if l["remis_en_stock"] else ("rupture",)),
                     values=(l["reference"] or "—", l["produit_nom"] or "—",
                             l["quantite"], fmt_money(l["total"]),
                             "Oui" if l["remis_en_stock"] else f"{l['etat']}"))
        retour = next((r for r in m3.get_retours() if r["id"] == int(sel[0])), None)
        if retour:
            remis = sum(1 for l in lignes if l["remis_en_stock"])
            self.lbl_retour_info.configure(
                text=f"Total remboursé : {fmt_money(retour['total'], self.devise)}\n"
                     f"Mode : {retour['mode_remboursement']}\n"
                     f"{remis}/{len(lignes)} ligne(s) remise(s) en stock\n"
                     f"Par : {retour['utilisateur']}")

    def _nouveau_retour(self):
        ventes = db.get_ventes(limit=300, inclure_annulees=False)
        if not ventes:
            messagebox.showinfo("Aucune vente", "Aucune vente à retourner.",
                                parent=self.root)
            return
        d = DialogueRetour(self.root, ventes, self.devise)
        if d.resultat:
            self.statut(d.resultat, COULEURS["success"])
            self._charger_retours()
            self._maj_badge_alertes()
