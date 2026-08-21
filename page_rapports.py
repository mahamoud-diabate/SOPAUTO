"""
SOPAUTO - Rapports
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

import database as db
import export_pdf
import factures
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, EntreeRecherche,
                        TableauTriable, ajouter_scrollbars, fmt_date, fmt_money, zebre)


class RapportsMixin:
    """Rapports — ventes, stock, historique, exports.

    3 onglets : ventes (CA/période/vendeur/mode), stock (valeur/ruptures),
    historique (recherche, annulation, réimpression, export).
    """

    def afficher_rapports(self):
        if not self.peut("rapports"):
            return self._refus()
        self._nouvelle_page("💹 Rapports et analyses", 8)

        onglets = ttk.Notebook(self.zone)
        onglets.pack(fill=tk.BOTH, expand=True)

        self._onglet_rapport_ventes(onglets)
        self._onglet_rapport_stock(onglets)
        self._onglet_historique_ventes(onglets)


    def _onglet_rapport_ventes(self, parent):
        page = tk.Frame(parent, bg=COULEURS["bg"], padx=12, pady=12)
        parent.add(page, text="  📊 Ventes & marges  ")

        barre = tk.Frame(page, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 10))

        tk.Label(barre, text="Période du", font=(POLICE, 10), bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.e_rap_debut = tk.Entry(barre, font=(POLICE, 10), width=12, bd=1, relief=tk.SOLID)
        self.e_rap_debut.insert(0, datetime.now().replace(day=1).strftime("%Y-%m-%d"))
        self.e_rap_debut.pack(side=tk.LEFT, padx=6)
        tk.Label(barre, text="au", font=(POLICE, 10), bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.e_rap_fin = tk.Entry(barre, font=(POLICE, 10), width=12, bd=1, relief=tk.SOLID)
        self.e_rap_fin.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.e_rap_fin.pack(side=tk.LEFT, padx=6)

        Bouton(barre, "Analyser", "primary", self._calculer_rapport,
               petit=True).pack(side=tk.LEFT, padx=8)

        for libelle, jours in (("Aujourd'hui", 0), ("7 jours", 6), ("30 jours", 29), ("Ce mois", -1)):
            Bouton(barre, libelle, "secondary", lambda j=jours: self._periode_rapide(j),
                   petit=True).pack(side=tk.LEFT, padx=2)

        Bouton(barre, "🖨️ Imprimer / PDF", "info", self._imprimer_rapport,
               petit=True).pack(side=tk.RIGHT, padx=3)
        Bouton(barre, "📄 PDF", "success", self._rapport_en_pdf,
               petit=True).pack(side=tk.RIGHT, padx=3)
        Bouton(barre, "📤 Exporter CSV", "success", self._exporter_ventes,
               petit=True).pack(side=tk.RIGHT, padx=3)

        self.zone_kpi_rapport = tk.Frame(page, bg=COULEURS["bg"])
        self.zone_kpi_rapport.pack(fill=tk.X, pady=(0, 10))

        colonnes = tk.Frame(page, bg=COULEURS["bg"])
        colonnes.pack(fill=tk.BOTH, expand=True)

        c1 = Carte(colonnes, "Détail par produit")
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        f_tree_rp = tk.Frame(c1.corps, bg=COULEURS["card"])
        f_tree_rp.pack(fill=tk.BOTH, expand=True)
        self.tab_rap_produits = TableauTriable(f_tree_rp, [
            ("ref", "Réf.", 90, "w", False),
            ("nom", "Produit", 200, "w", False),
            ("qte", "Qté", 60, "center", True),
            ("ca", "CA", 110, "e", True),
            ("marge", "Marge", 110, "e", True)], height=14)
        ajouter_scrollbars(f_tree_rp, self.tab_rap_produits)

        droite = tk.Frame(colonnes, bg=COULEURS["bg"])
        droite.pack(side=tk.LEFT, fill=tk.BOTH, padx=(6, 0))

        c2 = Carte(droite, "Par catégorie")
        c2.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        f_tree_rc = tk.Frame(c2.corps, bg=COULEURS["card"])
        f_tree_rc.pack(fill=tk.BOTH, expand=True)
        self.tab_rap_cat = TableauTriable(f_tree_rc, [
            ("cat", "Catégorie", 150, "w", False),
            ("qte", "Qté", 55, "center", True),
            ("ca", "CA", 110, "e", True)], height=6)
        ajouter_scrollbars(f_tree_rc, self.tab_rap_cat)

        c3 = Carte(droite, "Par mode de paiement")
        c3.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        f_tree_rpay = tk.Frame(c3.corps, bg=COULEURS["card"])
        f_tree_rpay.pack(fill=tk.BOTH, expand=True)
        self.tab_rap_paiement = TableauTriable(f_tree_rpay, [
            ("mode", "Mode", 150, "w", False),
            ("nb", "Nb", 55, "center", True),
            ("ca", "Montant", 110, "e", True)], height=6)
        ajouter_scrollbars(f_tree_rpay, self.tab_rap_paiement)

        self._calculer_rapport()


    def _onglet_rapport_stock(self, parent):
        page = tk.Frame(parent, bg=COULEURS["bg"], padx=12, pady=12)
        parent.add(page, text="  📦 Valorisation du stock  ")

        barre = tk.Frame(page, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 10))
        Bouton(barre, "📄 Bon de réapprovisionnement", "warning",
               self.generer_reappro, petit=True).pack(side=tk.LEFT)
        Bouton(barre, "📄 Bon en PDF", "success",
               self._reappro_en_pdf, petit=True).pack(side=tk.LEFT, padx=6)
        Bouton(barre, "📤 Exporter le catalogue", "info",
               self._exporter_produits, petit=True).pack(side=tk.LEFT, padx=6)

        rapport = db.rapport_stock()

        c1 = Carte(page, "Valorisation par catégorie")
        c1.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        f_tree_t1 = tk.Frame(c1.corps, bg=COULEURS["card"])
        f_tree_t1.pack(fill=tk.BOTH, expand=True)
        t1 = TableauTriable(f_tree_t1, [
            ("cat", "Catégorie", 200, "w", False),
            ("nb", "Produits", 90, "center", True),
            ("qte", "Quantité", 90, "center", True),
            ("achat", "Valeur d'achat", 140, "e", True),
            ("vente", "Valeur de revente", 150, "e", True),
            ("marge", "Marge potentielle", 150, "e", True)], height=9)
        ajouter_scrollbars(f_tree_t1, t1)
        totaux = [0, 0, 0]
        for i, c in enumerate(rapport["par_categorie"]):
            marge = c["valeur_vente"] - c["valeur_achat"]
            totaux[0] += c["qte"]; totaux[1] += c["valeur_achat"]; totaux[2] += c["valeur_vente"]
            t1.insert("", tk.END, tags=zebre(i), values=(
                c["categorie"], c["nb_produits"], c["qte"], fmt_money(c["valeur_achat"]),
                fmt_money(c["valeur_vente"]), fmt_money(marge)))
        tk.Label(c1.corps, font=(POLICE, 10, "bold"), bg=COULEURS["card"], fg=COULEURS["primary"],
                 text=f"TOTAL : {totaux[0]} unité(s) · achat {fmt_money(totaux[1], self.devise)} · "
                      f"revente {fmt_money(totaux[2], self.devise)} · "
                      f"marge potentielle {fmt_money(totaux[2] - totaux[1], self.devise)}"
                 ).pack(anchor="w", pady=(8, 0))

        c2 = Carte(page, "🐌 Stock dormant (aucune sortie récente)")
        c2.pack(fill=tk.BOTH, expand=True)
        f_tree_t2 = tk.Frame(c2.corps, bg=COULEURS["card"])
        f_tree_t2.pack(fill=tk.BOTH, expand=True)
        t2 = TableauTriable(f_tree_t2, [
            ("ref", "Référence", 110, "w", False),
            ("nom", "Produit", 260, "w", False),
            ("stock", "Stock", 70, "center", True),
            ("valeur", "Capital immobilisé", 150, "e", True),
            ("derniere", "Dernière sortie", 150, "w", False)], height=8)
        ajouter_scrollbars(f_tree_t2, t2)
        for i, d in enumerate(rapport["dormants"]):
            t2.insert("", tk.END, tags=zebre(i), values=(
                d["reference"], d["nom"], d["stock"],
                fmt_money(d["stock"] * d["prix_achat"]),
                fmt_date(d["derniere_sortie"]) if d["derniere_sortie"] else "jamais vendu"))


    def _onglet_historique_ventes(self, parent):
        page = tk.Frame(parent, bg=COULEURS["bg"], padx=12, pady=12)
        parent.add(page, text="  🧾 Historique des ventes  ")

        barre = tk.Frame(page, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        self.rech_ventes = EntreeRecherche(barre, "N° facture ou client…", 30,
                                           callback=self._charger_historique_ventes)
        self.rech_ventes.pack(side=tk.LEFT)
        Bouton(barre, "🖨️ Facture A4", "primary",
               lambda: self._imprimer_selection(self.tab_ventes, False),
               petit=True).pack(side=tk.LEFT, padx=(14, 3))
        Bouton(barre, "📄 PDF", "success",
               lambda: self._pdf_selection(self.tab_ventes, False),
               petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(barre, "🧾 Ticket", "info",
               lambda: self._imprimer_selection(self.tab_ventes, True),
               petit=True).pack(side=tk.LEFT, padx=3)
        if self.peut("admin"):
            Bouton(barre, "✕ Annuler la vente", "danger", self._annuler_vente,
                   petit=True).pack(side=tk.LEFT, padx=3)
        self.lbl_resume_ventes = tk.Label(barre, text="", font=(POLICE, 9, "bold"),
                                          bg=COULEURS["bg"], fg=COULEURS["primary"])
        self.lbl_resume_ventes.pack(side=tk.RIGHT, padx=8)

        conteneur = tk.Frame(page, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        c1 = Carte(conteneur, "Ventes")
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        f_tree_c1 = tk.Frame(c1.corps, bg=COULEURS["card"])
        f_tree_c1.pack(fill=tk.BOTH, expand=True)
        self.tab_ventes = TableauTriable(f_tree_c1, [
            ("num", "N° Facture", 120, "w", False),
            ("date", "Date", 130, "w", False),
            ("client", "Client", 140, "w", False),
            ("montant", "Total", 100, "e", True),
            ("mode", "Mode", 80, "w", False),
            ("vendeur", "Vendeur", 100, "w", False),
            ("statut", "Statut", 85, "center", False)], height=18)
        ajouter_scrollbars(f_tree_c1, self.tab_ventes)
        self.tab_ventes.bind("<<TreeviewSelect>>", lambda e: self._charger_lignes_vente())
        self.tab_ventes.bind("<Double-1>", lambda e: self._imprimer_selection(self.tab_ventes, True))

        c2 = Carte(conteneur, "Détail de la vente")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        f_tree_c2 = tk.Frame(c2.corps, bg=COULEURS["card"])
        f_tree_c2.pack(fill=tk.BOTH, expand=True)
        self.tab_lignes_vente = TableauTriable(f_tree_c2, [
            ("ref", "Réf.", 90, "w", False),
            ("nom", "Article", 160, "w", False),
            ("qte", "Qté", 50, "center", True),
            ("total", "Total", 90, "e", True)], height=18)
        ajouter_scrollbars(f_tree_c2, self.tab_lignes_vente)
        self.lbl_detail_vente = tk.Label(c2.corps, text="Sélectionnez une vente",
                                         font=(POLICE, 9), bg=COULEURS["card"],
                                         fg=COULEURS["text_secondary"], justify="left")
        self.lbl_detail_vente.pack(anchor="w", pady=(8, 0))

        self._charger_historique_ventes()


    def _calculer_rapport(self):
        debut, fin = self._dates_rapport()
        try:
            datetime.strptime(debut, "%Y-%m-%d")
            datetime.strptime(fin, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Dates invalides", "Format attendu : AAAA-MM-JJ", parent=self.root)
            return

        self._rapport_courant = db.rapport_ventes(debut, fin)
        r = self._rapport_courant["resume"]

        for w in self.zone_kpi_rapport.winfo_children():
            w.destroy()
        taux = (r["marge"] / r["ca"] * 100) if r["ca"] else 0
        kpis = [
            ("Chiffre d'affaires", fmt_money(r["ca"], self.devise), COULEURS["primary"]),
            ("Marge brute", fmt_money(r["marge"], self.devise), COULEURS["success"]),
            ("Taux de marge", f"{taux:.1f} %", COULEURS["info"]),
            ("Ventes", f"{r['nb_ventes']}", COULEURS["secondary"]),
            ("Panier moyen", fmt_money(r["panier_moyen"], self.devise), COULEURS["warning"]),
            ("Articles vendus", f"{r['articles_vendus']}", COULEURS["secondary"]),
            ("Remises", fmt_money(r["remises"], self.devise), COULEURS["danger"]),
        ]
        for titre, valeur, couleur in kpis:
            c = tk.Frame(self.zone_kpi_rapport, bg=COULEURS["card"],
                         highlightbackground=COULEURS["border"], highlightthickness=1)
            c.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
            tk.Label(c, text=titre, font=(POLICE, 8), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).pack(pady=(8, 0), padx=8)
            tk.Label(c, text=valeur, font=(POLICE, 14, "bold"), bg=COULEURS["card"],
                     fg=couleur).pack(pady=(2, 8), padx=8)

        t = self.tab_rap_produits
        t.delete(*t.get_children())
        for i, p in enumerate(self._rapport_courant["par_produit"]):
            t.insert("", tk.END, tags=zebre(i), values=(
                p["reference"], p["nom"], p["qte"], fmt_money(p["ca"]), fmt_money(p["marge"])))

        t = self.tab_rap_cat
        t.delete(*t.get_children())
        for i, c in enumerate(self._rapport_courant["par_categorie"]):
            t.insert("", tk.END, tags=zebre(i), values=(c["categorie"], c["qte"], fmt_money(c["ca"])))

        t = self.tab_rap_paiement
        t.delete(*t.get_children())
        for i, p in enumerate(self._rapport_courant["par_paiement"]):
            t.insert("", tk.END, tags=zebre(i), values=(p["mode"], p["nb"], fmt_money(p["ca"])))

        self.statut(f"Rapport calculé du {debut} au {fin}", COULEURS["success"])


    def _dates_rapport(self):
        return self.e_rap_debut.get().strip(), self.e_rap_fin.get().strip()


    def _periode_rapide(self, jours):
        aujourdhui = datetime.now()
        if jours == -1:
            debut = aujourdhui.replace(day=1)
        else:
            debut = aujourdhui - timedelta(days=jours)
        self.e_rap_debut.delete(0, tk.END)
        self.e_rap_debut.insert(0, debut.strftime("%Y-%m-%d"))
        self.e_rap_fin.delete(0, tk.END)
        self.e_rap_fin.insert(0, aujourdhui.strftime("%Y-%m-%d"))
        self._calculer_rapport()


    def _charger_historique_ventes(self):
        ventes = db.get_ventes(limit=500, search=self.rech_ventes.get())
        t = self.tab_ventes
        t.delete(*t.get_children())
        total = 0
        for i, v in enumerate(ventes):
            annulee = v["statut_v"] == "annulee"
            if not annulee:
                total += v["total"]
            t.insert("", tk.END, iid=v["id"], tags=zebre(i, ("annulee",) if annulee else ()),
                     values=(v["numero"] or f"#{v['id']}", fmt_date(v["date_vente"]),
                             v["client_nom"], v["nb_lignes"], fmt_money(v.get("remise", 0)),
                             fmt_money(v["total"]), v.get("mode_paiement", ""),
                             v.get("utilisateur", ""), "❌ Annulée" if annulee else "✅ Validée"))
        self.lbl_resume_ventes.configure(
            text=f"{len(ventes)} vente(s) · total {fmt_money(total, self.devise)}")


    def _charger_lignes_vente(self):
        sel = self.tab_ventes.selection()
        t = self.tab_lignes_vente
        t.delete(*t.get_children())
        if not sel:
            return
        vente, lignes = db.get_vente_details(int(sel[0]))
        for i, l in enumerate(lignes):
            t.insert("", tk.END, tags=zebre(i), values=(
                l["reference"], l["produit_nom"], l["quantite"], fmt_money(l["total"])))
        if vente:
            self.lbl_detail_vente.configure(
                text=f"Sous-total : {fmt_money(vente.get('sous_total', 0), self.devise)}\n"
                     f"Remise : {fmt_money(vente.get('remise', 0), self.devise)}\n"
                     f"TOTAL : {fmt_money(vente['total'], self.devise)}\n"
                     f"Reçu : {fmt_money(vente.get('montant_paye', 0), self.devise)} "
                     f"({vente.get('mode_paiement', '')})")


    def _annuler_vente(self):
        if not self.peut("admin"):
            return self._refus()
        sel = self.tab_ventes.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez une vente.", parent=self.root)
            return
        if not messagebox.askyesno(
                "Annuler la vente",
                "Annuler cette vente et remettre les articles en stock ?\n\n"
                "L'opération est tracée dans l'historique.", parent=self.root, icon="warning"):
            return
        ok, msg = db.annuler_vente(int(sel[0]), f"par {self.utilisateur['nom_utilisateur']}")
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        self._charger_historique_ventes()
        self._maj_badge_alertes()

    # ═══ PARAMÈTRES ════════════════════════════════════


    def _imprimer_rapport(self):
        debut, fin = self._dates_rapport()
        if not hasattr(self, "_rapport_courant"):
            self._calculer_rapport()
        chemin = factures.generer_rapport_html("Rapport de ventes", debut, fin,
                                               self._rapport_courant)
        self.statut(f"Rapport généré : {chemin}", COULEURS["success"])


    def _rapport_en_pdf(self):
        """Rapport de ventes en PDF (paysage : les tableaux sont larges)."""
        debut, fin = self._dates_rapport()
        if not hasattr(self, "_rapport_courant"):
            self._calculer_rapport()
        if not export_pdf.moteur_disponible():
            messagebox.showinfo(
                "PDF indisponible",
                "Aucun navigateur trouvé pour générer le PDF.\n\n"
                "Utilisez « Imprimer » puis Ctrl+P → "
                "« Enregistrer au format PDF ».", parent=self.root)
            return
        self.statut(f"Génération du PDF via {export_pdf.nom_moteur()}…")
        self.root.update_idletasks()
        ok, res = export_pdf.rapport_pdf("Rapport de ventes", debut, fin,
                                         self._rapport_courant, ouvrir=True)
        if ok:
            self.statut(f"PDF créé : {os.path.basename(res)}", COULEURS["success"])
        else:
            messagebox.showwarning("PDF impossible", res, parent=self.root)


    def _reappro_en_pdf(self):
        """Bon de réapprovisionnement en PDF."""
        if not export_pdf.moteur_disponible():
            return self.generer_reappro()
        self.statut("Génération du bon de réapprovisionnement…")
        self.root.update_idletasks()
        ok, res = export_pdf.reappro_pdf(ouvrir=True)
        if ok:
            self.statut(f"Bon PDF créé : {os.path.basename(res)}", COULEURS["success"])
        else:
            messagebox.showwarning("PDF impossible", res, parent=self.root)


    def _exporter_ventes(self):
        debut, fin = self._dates_rapport()
        self._proposer_ouverture(db.exporter_ventes(debut, fin))


