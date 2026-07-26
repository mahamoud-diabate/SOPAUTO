
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import database as db
import metier_v3 as m3
from ui_widgets import (COULEURS, POLICE, Bouton, Carte,
                        TableauTriable, fmt_date, fmt_money, zebre,
                        parse_float)
from dialogues import DemanderMontant

class CreancesMixin:
    """Mixin : Créances clients."""

# ═══════════════════════════════════════════════════
    #  💳 CRÉANCES
    # ═══════════════════════════════════════════════════

    def afficher_creances(self):
        if not self.peut("rapports"):
            return self._refus()
        self._nouvelle_page("💳 Créances clients — qui doit quoi", self._idx_menu("Créances"))

        Bouton(self.zone_actions, "💰 Encaisser", "success",
               self._encaisser_creance, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "🖨️ Relances", "info",
               self._imprimer_creances, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "🔄 Actualiser", "secondary",
               self.afficher_creances, petit=True).pack(side=tk.LEFT, padx=3)

        # ── Bandeau KPI ──
        kpi = m3.kpi_v3()
        bandeau = tk.Frame(self.zone, bg=COULEURS["bg"])
        bandeau.pack(fill=tk.X, pady=(0, 10))
        seuil = int(parse_float(self.params.get("alerte_creance_jours", 15), 15))
        cartes = [
            ("Total dû", fmt_money(kpi["creances_total"], self.devise),
             COULEURS["warning"], f"{int(kpi['creances_nb'])} facture(s) non soldée(s)"),
            (f"En retard (> {seuil} j)", fmt_money(kpi["creances_retard"], self.devise),
             COULEURS["danger"], f"{int(kpi['creances_nb_retard'])} facture(s) à relancer"),
            ("Dettes fournisseurs", fmt_money(kpi["dettes_total"], self.devise),
             COULEURS["info"], "ce que vous devez"),
        ]
        for titre, valeur, couleur, sous in cartes:
            c = tk.Frame(bandeau, bg=COULEURS["card"], padx=16, pady=12,
                         highlightbackground=COULEURS["border"], highlightthickness=1)
            c.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
            tk.Label(c, text=titre, font=(POLICE, 9), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).pack(anchor="w")
            tk.Label(c, text=valeur, font=(POLICE, 17, "bold"), bg=COULEURS["card"],
                     fg=couleur).pack(anchor="w")
            tk.Label(c, text=sous, font=(POLICE, 8), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).pack(anchor="w")

        conteneur = tk.Frame(self.zone, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        # ── Par client (gauche) ──
        c1 = Carte(conteneur, "Encours par client")
        c1.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 6))
        c1.configure(width=430)
        c1.pack_propagate(False)
        self.tab_creances_client = TableauTriable(c1.corps, [
            ("client", "Client", 160, "w", False),
            ("tel", "Téléphone", 105, "w", False),
            ("nb", "Fact.", 45, "center", True),
            ("du", "Total dû", 105, "e", True),
            ("age", "Ancienn.", 70, "center", True)], height=16)
        self.tab_creances_client.pack(fill=tk.BOTH, expand=True)
        self.tab_creances_client.bind("<<TreeviewSelect>>",
                                      lambda e: self._charger_creances_detail())

        # ── Factures (droite) ──
        c2 = Carte(conteneur, "Factures non soldées")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self.tab_creances = TableauTriable(c2.corps, [
            ("num", "N° facture", 125, "w", False),
            ("client", "Client", 150, "w", False),
            ("date", "Date", 100, "w", False),
            ("ech", "Échéance", 95, "w", False),
            ("total", "Total", 100, "e", True),
            ("paye", "Déjà payé", 100, "e", True),
            ("reste", "Reste dû", 105, "e", True),
            ("age", "Jours", 60, "center", True)], height=16)
        self.tab_creances.pack(fill=tk.BOTH, expand=True)
        self.tab_creances.bind("<Double-1>", lambda e: self._encaisser_creance())

        self.lbl_creances_info = tk.Label(
            c2.corps, text="Double-cliquez sur une facture pour encaisser un acompte.",
            font=(POLICE, 9), bg=COULEURS["card"], fg=COULEURS["text_secondary"])
        self.lbl_creances_info.pack(anchor="w", pady=(6, 0))

        self._filtre_creance_client = None
        self._charger_creances()

    def _charger_creances(self):
        # Par client
        t1 = self.tab_creances_client
        t1.delete(*t1.get_children())
        seuil = int(parse_float(self.params.get("alerte_creance_jours", 15), 15))
        for i, c in enumerate(m3.get_creances_par_client()):
            retard = (c["plus_ancienne_jours"] or 0) >= seuil
            t1.insert("", tk.END, iid=str(c["client_id"]),
                      tags=zebre(i, ("alerte",) if retard else ()),
                      values=(c["client_nom"], c["telephone"], c["nb_factures"],
                              fmt_money(c["total_du"]),
                              f"{int(c['plus_ancienne_jours'] or 0)} j"))
        self._charger_creances_detail()

    def _charger_creances_detail(self):
        sel = self.tab_creances_client.selection()
        client_id = int(sel[0]) if sel and sel[0].isdigit() and int(sel[0]) > 0 else None
        creances = m3.get_creances(client_id=client_id)
        seuil = int(parse_float(self.params.get("alerte_creance_jours", 15), 15))
        t = self.tab_creances
        t.delete(*t.get_children())
        total = 0.0
        for i, c in enumerate(creances):
            total += c["reste_du"]
            retard = (c["anciennete_jours"] or 0) >= seuil
            t.insert("", tk.END, iid=c["vente_id"],
                     tags=zebre(i, ("alerte",) if retard else ()),
                     values=(c["numero"] or f"#{c['vente_id']}", c["client_nom"],
                             fmt_date(c["date_vente"], False),
                             c["date_echeance"] or "—",
                             fmt_money(c["total"]), fmt_money(c["total_paye"]),
                             fmt_money(c["reste_du"]), int(c["anciennete_jours"] or 0)))
        self.lbl_creances_info.configure(
            text=f"{len(creances)} facture(s) · reste dû {fmt_money(total, self.devise)}"
                 + ("  —  double-clic pour encaisser" if creances else ""))

    def _encaisser_creance(self):
        sel = self.tab_creances.selection()
        if not sel:
            messagebox.showinfo("Information",
                                "Sélectionnez une facture à encaisser.", parent=self.root)
            return
        vente_id = int(sel[0])
        creance = next((c for c in m3.get_creances() if c["vente_id"] == vente_id), None)
        if not creance:
            messagebox.showinfo("Information", "Cette facture est déjà soldée.",
                                parent=self.root)
            self._charger_creances()
            return

        d = DemanderMontant(
            self.root, "Encaisser une créance",
            f"Facture {creance['numero']} — {creance['client_nom']}\n"
            f"Total {fmt_money(creance['total'], self.devise)} · "
            f"déjà payé {fmt_money(creance['total_paye'], self.devise)}\n"
            f"Reste dû : {fmt_money(creance['reste_du'], self.devise)}",
            montant_max=creance["reste_du"])
        if not d.resultat:
            return
        montant, mode, ref = d.resultat
        ok, msg = m3.encaisser_creance(vente_id, montant, mode, ref)
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self.statut(msg, COULEURS["success"])
            self.afficher_creances()

    def _imprimer_creances(self):
        seuil = int(parse_float(self.params.get("alerte_creance_jours", 15), 15))
        retards = m3.get_creances(seuil_jours=seuil)
        if not retards:
            messagebox.showinfo("Aucune relance",
                                f"Aucune facture en retard de plus de {seuil} jours.",
                                parent=self.root)
            return
        lignes = [[c["numero"], c["client_nom"], fmt_date(c["date_vente"], False),
                   c["date_echeance"] or "", f"{c['total']:.0f}",
                   f"{c['total_paye']:.0f}", f"{c['reste_du']:.0f}",
                   int(c["anciennete_jours"] or 0)] for c in retards]
        chemin = db.export_csv(
            f"relances_{datetime.now():%Y%m%d_%H%M}.csv",
            ["N° facture", "Client", "Date", "Échéance", "Total", "Payé",
             "Reste dû", "Jours"], lignes)
        total = sum(c["reste_du"] for c in retards)
        messagebox.showinfo(
            "Liste de relances",
            f"{len(retards)} facture(s) en retard · {fmt_money(total, self.devise)}\n\n"
            f"Fichier : {chemin}", parent=self.root)
        self._proposer_ouverture(chemin)
