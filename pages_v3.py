"""
SODIPAC — Écrans v3
===================

Pages Tkinter des nouveautés v3, servies sous forme de **mixin** pour ne pas
alourdir davantage main.py :

  • 💳 Créances       — qui doit quoi, encaissement d'acomptes
  • 🛒 Achats         — commandes fournisseur, réception, dettes
  • 📋 Inventaire     — comptage physique, écarts valorisés
  • 🚗 Recherche véhicule — « une plaquette pour Yaris 2008 »
  • 🏬 Dépôts         — multi-dépôt, transferts
  • ↩️ Retours        — retours partiels et avoirs
  • 📉 Prévisions     — ruptures à venir, quantités à commander

Convention respectée : chaque page appelle self._nouvelle_page(titre, index),
utilise Carte / TableauTriable / Bouton / zebre / fmt_money comme le reste.
Les graphiques sont des COURBES (préférence utilisateur).
"""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, simpledialog, ttk

import database as db
import metier_v3 as m3
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, EntreeRecherche,
                        TableauTriable, ajouter_scrollbars, fmt_date, fmt_money,
                        zebre)


def _num(valeur, defaut=0.0):
    try:
        return float(str(valeur).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return defaut


class DemanderMontant(simpledialog.Dialog):
    """Petite boîte de dialogue : montant + mode de paiement + référence."""

    def __init__(self, parent, titre, message, montant_max=None,
                 modes=("Espèces", "Wave", "Orange Money", "MTN Money", "Virement", "Chèque")):
        self.message = message
        self.montant_max = montant_max
        self.modes = modes
        self.resultat = None
        super().__init__(parent, titre)

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        tk.Label(master, text=self.message, font=(POLICE, 10), bg=COULEURS["card"],
                 fg=COULEURS["text"], justify="left", wraplength=380).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        tk.Label(master, text="Montant", font=(POLICE, 10), bg=COULEURS["card"]).grid(
            row=1, column=0, sticky="w", pady=4)
        self.e_montant = tk.Entry(master, font=(POLICE, 12, "bold"), width=16,
                                  bd=1, relief=tk.SOLID, justify="right")
        self.e_montant.grid(row=1, column=1, sticky="w", padx=8, pady=4, ipady=3)
        if self.montant_max:
            self.e_montant.insert(0, f"{self.montant_max:.0f}")
            self.e_montant.select_range(0, tk.END)

        tk.Label(master, text="Mode", font=(POLICE, 10), bg=COULEURS["card"]).grid(
            row=2, column=0, sticky="w", pady=4)
        self.cb_mode = ttk.Combobox(master, state="readonly", width=18,
                                    font=(POLICE, 10), values=list(self.modes))
        self.cb_mode.current(0)
        self.cb_mode.grid(row=2, column=1, sticky="w", padx=8, pady=4)

        tk.Label(master, text="Référence", font=(POLICE, 10), bg=COULEURS["card"]).grid(
            row=3, column=0, sticky="w", pady=4)
        self.e_ref = tk.Entry(master, font=(POLICE, 10), width=22, bd=1, relief=tk.SOLID)
        self.e_ref.grid(row=3, column=1, sticky="w", padx=8, pady=4, ipady=2)
        if self.montant_max:
            tk.Label(master, text=f"Maximum : {fmt_money(self.montant_max)}",
                     font=(POLICE, 8), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).grid(
                row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
        return self.e_montant

    def validate(self):
        montant = _num(self.e_montant.get())
        if montant <= 0:
            messagebox.showwarning("Montant invalide",
                                   "Saisissez un montant supérieur à 0.", parent=self)
            return False
        if self.montant_max and montant > self.montant_max + 0.01:
            messagebox.showwarning(
                "Montant trop élevé",
                f"Le maximum est {fmt_money(self.montant_max)}.", parent=self)
            return False
        return True

    def apply(self):
        self.resultat = (_num(self.e_montant.get()), self.cb_mode.get(),
                         self.e_ref.get().strip())


class PagesV3:
    """Mixin ajouté à Application. Fournit les pages des nouveautés v3."""

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
        seuil = int(_num(self.params.get("alerte_creance_jours", 15), 15))
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
        seuil = int(_num(self.params.get("alerte_creance_jours", 15), 15))
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
        seuil = int(_num(self.params.get("alerte_creance_jours", 15), 15))
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
        seuil = int(_num(self.params.get("alerte_creance_jours", 15), 15))
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

    # ═══════════════════════════════════════════════════
    #  🛒 ACHATS / COMMANDES FOURNISSEUR
    # ═══════════════════════════════════════════════════

    def afficher_achats(self):
        if not self.peut("stock"):
            return self._refus()
        self._nouvelle_page("🛒 Achats — commandes fournisseur", self._idx_menu("Achats"))

        Bouton(self.zone_actions, "➕ Nouvelle commande", "primary",
               self._nouvelle_commande, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "📨 Marquer envoyée", "info",
               self._envoyer_commande, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "📥 Réceptionner", "success",
               self._receptionner_commande, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "💸 Payer", "warning",
               self._payer_fournisseur, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "✕ Annuler", "danger",
               self._annuler_commande, petit=True).pack(side=tk.LEFT, padx=3)

        barre = tk.Frame(self.zone, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        tk.Label(barre, text="Statut :", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.filtre_cmd = ttk.Combobox(
            barre, state="readonly", width=14, font=(POLICE, 9),
            values=["Toutes", "Brouillon", "Envoyée", "Partielle", "Reçue", "Annulée"])
        self.filtre_cmd.current(0)
        self.filtre_cmd.pack(side=tk.LEFT, padx=(4, 14))
        self.filtre_cmd.bind("<<ComboboxSelected>>", lambda e: self._charger_commandes())
        self.lbl_resume_cmd = tk.Label(barre, text="", font=(POLICE, 9, "bold"),
                                       bg=COULEURS["bg"], fg=COULEURS["primary"])
        self.lbl_resume_cmd.pack(side=tk.RIGHT, padx=8)

        conteneur = tk.Frame(self.zone, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        c1 = Carte(conteneur, "Commandes")
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self.tab_commandes = TableauTriable(c1.corps, [
            ("num", "N° commande", 130, "w", False),
            ("fourn", "Fournisseur", 170, "w", False),
            ("date", "Date", 100, "w", False),
            ("prevue", "Prévue le", 95, "w", False),
            ("depot", "Dépôt", 110, "w", False),
            ("lignes", "Lignes", 55, "center", True),
            ("total", "Total", 105, "e", True),
            ("reste", "À recevoir", 85, "center", True),
            ("statut", "Statut", 95, "center", False)], height=15)
        self.tab_commandes.pack(fill=tk.BOTH, expand=True)
        self.tab_commandes.bind("<<TreeviewSelect>>", lambda e: self._charger_cmd_lignes())

        c2 = Carte(conteneur, "Détail de la commande")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, padx=(6, 0))
        c2.configure(width=420)
        c2.pack_propagate(False)
        self.tab_cmd_lignes = TableauTriable(c2.corps, [
            ("ref", "Réf.", 90, "w", False),
            ("nom", "Article", 150, "w", False),
            ("cmd", "Cmdé", 50, "center", True),
            ("recu", "Reçu", 50, "center", True),
            ("pu", "P.U.", 80, "e", True)], height=15)
        self.tab_cmd_lignes.pack(fill=tk.BOTH, expand=True)
        self.lbl_cmd_detail = tk.Label(c2.corps, text="Sélectionnez une commande",
                                       font=(POLICE, 9), bg=COULEURS["card"],
                                       fg=COULEURS["text_secondary"], justify="left")
        self.lbl_cmd_detail.pack(anchor="w", pady=(8, 0))

        self._charger_commandes()

    def _charger_commandes(self):
        statuts = {"Toutes": "", "Brouillon": "brouillon", "Envoyée": "envoyee",
                   "Partielle": "partielle", "Reçue": "recue", "Annulée": "annulee"}
        cmds = m3.get_commandes(statut=statuts.get(self.filtre_cmd.get(), ""))
        libelles = {"brouillon": "📝 Brouillon", "envoyee": "📨 Envoyée",
                    "partielle": "📦 Partielle", "recue": "✅ Reçue",
                    "annulee": "❌ Annulée"}
        t = self.tab_commandes
        t.delete(*t.get_children())
        total = 0.0
        for i, c in enumerate(cmds):
            if c["statut"] != "annulee":
                total += c["total"]
            tags = ("alerte",) if c["statut"] == "partielle" else ()
            t.insert("", tk.END, iid=c["id"], tags=zebre(i, tags), values=(
                c["numero"] or f"#{c['id']}", c["fournisseur_nom"] or "—",
                fmt_date(c["date_commande"], False), c["date_prevue"] or "—",
                c["depot_nom"] or "—", c["nb_lignes"], fmt_money(c["total"]),
                c["reste_a_recevoir"] or 0,
                libelles.get(c["statut"], c["statut"])))
        self.lbl_resume_cmd.configure(
            text=f"{len(cmds)} commande(s) · {fmt_money(total, self.devise)}")
        self._charger_cmd_lignes()

    def _charger_cmd_lignes(self):
        sel = self.tab_commandes.selection()
        t = self.tab_cmd_lignes
        t.delete(*t.get_children())
        if not sel:
            self.lbl_cmd_detail.configure(text="Sélectionnez une commande")
            return
        cid = int(sel[0])
        for i, l in enumerate(m3.get_commande_details(cid)):
            manque = l["quantite"] > l["quantite_recue"]
            t.insert("", tk.END, iid=l["id"], tags=zebre(i, ("alerte",) if manque else ()),
                     values=(l["reference"] or "—",
                             l["produit_nom"] or l["designation"] or "—",
                             l["quantite"], l["quantite_recue"],
                             fmt_money(l["prix_unitaire"])))
        cmd = next((c for c in m3.get_commandes() if c["id"] == cid), None)
        if cmd:
            dette = next((d for d in m3.get_dettes_fournisseur()
                          if d["commande_id"] == cid), None)
            texte = (f"Sous-total : {fmt_money(cmd['sous_total'], self.devise)}\n"
                     f"Remise : {fmt_money(cmd['remise'], self.devise)}  ·  "
                     f"Frais : {fmt_money(cmd['frais'], self.devise)}\n"
                     f"TOTAL : {fmt_money(cmd['total'], self.devise)}")
            if dette:
                texte += (f"\nPayé : {fmt_money(dette['total_paye'], self.devise)}\n"
                          f"RESTE À PAYER : {fmt_money(dette['reste_a_payer'], self.devise)}")
            elif cmd["statut"] in ("recue", "partielle"):
                texte += "\n✅ Intégralement payée"
            if cmd["notes"]:
                texte += f"\nNotes : {cmd['notes']}"
            self.lbl_cmd_detail.configure(text=texte)

    def _nouvelle_commande(self):
        fournisseurs = db.get_fournisseurs()
        if not fournisseurs:
            messagebox.showwarning("Aucun fournisseur",
                                   "Créez d'abord un fournisseur (menu Fournisseurs).",
                                   parent=self.root)
            return
        d = DialogueCommande(self.root, self.devise)
        if d.resultat:
            fid, items, depot_id, frais, prevue, notes = d.resultat
            ok, msg, _ = m3.creer_commande(fid, items, depot_id=depot_id, frais=frais,
                                           date_prevue=prevue, notes=notes)
            messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
            if ok:
                self.statut(msg, COULEURS["success"])
                self._charger_commandes()

    def _cmd_selectionnee(self):
        sel = self.tab_commandes.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez une commande.",
                                parent=self.root)
            return None
        return int(sel[0])

    def _envoyer_commande(self):
        cid = self._cmd_selectionnee()
        if cid is None:
            return
        ok, msg = m3.envoyer_commande(cid)
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self._charger_commandes()

    def _receptionner_commande(self):
        cid = self._cmd_selectionnee()
        if cid is None:
            return
        lignes = [l for l in m3.get_commande_details(cid)
                  if l["quantite"] > l["quantite_recue"]]
        if not lignes:
            messagebox.showinfo("Information",
                                "Cette commande est entièrement réceptionnée.",
                                parent=self.root)
            return
        d = DialogueReception(self.root, cid, lignes, self.devise)
        if d.resultat is None:
            return
        ok, msg = m3.receptionner_commande(cid, d.resultat or None, d.depot_id)
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self.statut(msg, COULEURS["success"])
            self._charger_commandes()
            self._maj_badge_alertes()

    def _payer_fournisseur(self):
        cid = self._cmd_selectionnee()
        if cid is None:
            return
        dette = next((d for d in m3.get_dettes_fournisseur() if d["commande_id"] == cid), None)
        if not dette:
            messagebox.showinfo("Information",
                                "Rien à payer sur cette commande "
                                "(non réceptionnée ou déjà soldée).", parent=self.root)
            return
        d = DemanderMontant(
            self.root, "Payer le fournisseur",
            f"Commande {dette['numero']} — {dette['fournisseur_nom']}\n"
            f"Total {fmt_money(dette['total'], self.devise)} · "
            f"payé {fmt_money(dette['total_paye'], self.devise)}\n"
            f"Reste à payer : {fmt_money(dette['reste_a_payer'], self.devise)}",
            montant_max=dette["reste_a_payer"])
        if not d.resultat:
            return
        montant, mode, ref = d.resultat
        ok, msg = m3.payer_fournisseur(cid, montant, mode, ref)
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self._charger_commandes()

    def _annuler_commande(self):
        cid = self._cmd_selectionnee()
        if cid is None:
            return
        if not messagebox.askyesno("Confirmer", "Annuler cette commande ?",
                                   parent=self.root, icon="warning"):
            return
        ok, msg = m3.annuler_commande(cid)
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self._charger_commandes()

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
        c1.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 6))
        c1.configure(width=470)
        c1.pack_propagate(False)
        self.tab_inventaires = TableauTriable(c1.corps, [
            ("num", "N°", 120, "w", False),
            ("depot", "Dépôt", 105, "w", False),
            ("debut", "Ouvert le", 100, "w", False),
            ("avance", "Comptés", 75, "center", False),
            ("ecarts", "Écarts", 55, "center", True),
            ("valeur", "Impact", 100, "e", True),
            ("statut", "Statut", 85, "center", False)], height=16)
        self.tab_inventaires.pack(fill=tk.BOTH, expand=True)
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

        self.tab_inv_lignes = TableauTriable(c2.corps, [
            ("ref", "Réf.", 95, "w", False),
            ("nom", "Produit", 190, "w", False),
            ("theo", "Théorique", 75, "center", True),
            ("compte", "Compté", 70, "center", True),
            ("ecart", "Écart", 60, "center", True),
            ("valeur", "Valeur écart", 105, "e", True),
            ("motif", "Motif", 105, "w", False)], height=15)
        self.tab_inv_lignes.pack(fill=tk.BOTH, expand=True)
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

    # ═══════════════════════════════════════════════════
    #  🚗 RECHERCHE PAR VÉHICULE
    # ═══════════════════════════════════════════════════

    def afficher_recherche_vehicule(self):
        self._nouvelle_page("🚗 Quelle pièce pour quel véhicule ?",
                            self._idx_menu("Véhicules"))

        Bouton(self.zone_actions, "🔗 Lier une pièce", "primary",
               self._lier_compatibilite, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "🚙 Nouveau modèle", "info",
               self._nouveau_modele, petit=True).pack(side=tk.LEFT, padx=3)

        # ── Filtres ──
        filtre = Carte(self.zone, "Rechercher")
        filtre.pack(fill=tk.X, pady=(0, 8))
        ligne = tk.Frame(filtre.corps, bg=COULEURS["card"])
        ligne.pack(fill=tk.X)

        tk.Label(ligne, text="Marque", font=(POLICE, 9), bg=COULEURS["card"]).pack(side=tk.LEFT)
        self.cb_marque = ttk.Combobox(ligne, state="readonly", width=15, font=(POLICE, 10),
                                      values=["(toutes)"] + m3.get_marques())
        self.cb_marque.current(0)
        self.cb_marque.pack(side=tk.LEFT, padx=(4, 12))
        self.cb_marque.bind("<<ComboboxSelected>>", lambda e: self._maj_modeles())

        tk.Label(ligne, text="Modèle", font=(POLICE, 9), bg=COULEURS["card"]).pack(side=tk.LEFT)
        self.cb_modele = ttk.Combobox(ligne, state="readonly", width=17, font=(POLICE, 10))
        self.cb_modele.pack(side=tk.LEFT, padx=(4, 12))

        tk.Label(ligne, text="Année", font=(POLICE, 9), bg=COULEURS["card"]).pack(side=tk.LEFT)
        self.e_annee = tk.Entry(ligne, font=(POLICE, 10), width=7, bd=1, relief=tk.SOLID,
                                justify="center")
        self.e_annee.pack(side=tk.LEFT, padx=(4, 12), ipady=2)

        tk.Label(ligne, text="Catégorie", font=(POLICE, 9), bg=COULEURS["card"]).pack(side=tk.LEFT)
        self.cats_vehic = db.get_categories()
        self.cb_cat_vehic = ttk.Combobox(
            ligne, state="readonly", width=16, font=(POLICE, 10),
            values=["(toutes)"] + [c["nom"] for c in self.cats_vehic])
        self.cb_cat_vehic.current(0)
        self.cb_cat_vehic.pack(side=tk.LEFT, padx=(4, 12))

        Bouton(ligne, "🔍 Chercher", "primary", self._chercher_vehicule,
               petit=True).pack(side=tk.LEFT, padx=4)
        Bouton(ligne, "✕ Réinitialiser", "secondary", self._reset_vehicule,
               petit=True).pack(side=tk.LEFT, padx=4)

        ligne2 = tk.Frame(filtre.corps, bg=COULEURS["card"])
        ligne2.pack(fill=tk.X, pady=(8, 0))
        tk.Label(ligne2, text="Ou par référence / code-barres / équivalent :",
                 font=(POLICE, 9), bg=COULEURS["card"]).pack(side=tk.LEFT)
        self.e_ref_univ = tk.Entry(ligne2, font=(POLICE, 10), width=26, bd=1, relief=tk.SOLID)
        self.e_ref_univ.pack(side=tk.LEFT, padx=6, ipady=2)
        self.e_ref_univ.bind("<Return>", lambda e: self._chercher_reference())
        Bouton(ligne2, "🔎 Chercher la référence", "info", self._chercher_reference,
               petit=True).pack(side=tk.LEFT, padx=4)

        self.lbl_vehic_resume = tk.Label(ligne2, text="", font=(POLICE, 9, "bold"),
                                         bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_vehic_resume.pack(side=tk.RIGHT)

        # ── Résultats ──
        cadre = Carte(self.zone, "Pièces compatibles")
        cadre.pack(fill=tk.BOTH, expand=True)
        # ajouter_scrollbars() utilise grid() : on isole le tableau dans son
        # propre conteneur pour pouvoir pack() la légende en dessous.
        zone_tab = tk.Frame(cadre.corps, bg=COULEURS["card"])
        zone_tab.pack(fill=tk.BOTH, expand=True)
        self.tab_vehic = TableauTriable(zone_tab, [
            ("ref", "Référence", 115, "w", False),
            ("nom", "Pièce", 230, "w", False),
            ("cat", "Catégorie", 130, "w", False),
            ("marque", "Marque", 110, "w", False),
            ("vehicule", "Véhicule", 195, "w", False),
            ("pos", "Position", 85, "w", False),
            ("cert", "Fiabilité", 85, "center", False),
            ("stock", "Rayon", 65, "center", True),
            ("prix", "Prix vente", 105, "e", True),
            ("empl", "Emplacement", 130, "w", False)])
        ajouter_scrollbars(zone_tab, self.tab_vehic)
        self.tab_vehic.bind("<Double-1>", lambda e: self._vendre_depuis_vehicule())

        tk.Label(cadre.corps, text="Double-cliquez sur une pièce pour l'envoyer directement "
                                   "dans le panier de la caisse.",
                 font=(POLICE, 9), bg=COULEURS["card"],
                 fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(6, 0))

        self._maj_modeles()

    def _maj_modeles(self):
        marque = self.cb_marque.get()
        marque = "" if marque == "(toutes)" else marque
        modeles = sorted({m["modele"] for m in m3.get_modeles(marque)})
        self.cb_modele.configure(values=["(tous)"] + modeles)
        self.cb_modele.current(0)

    def _reset_vehicule(self):
        self.cb_marque.current(0)
        self._maj_modeles()
        self.e_annee.delete(0, tk.END)
        self.cb_cat_vehic.current(0)
        self.e_ref_univ.delete(0, tk.END)
        self.tab_vehic.delete(*self.tab_vehic.get_children())
        self.lbl_vehic_resume.configure(text="")

    def _chercher_vehicule(self):
        marque = self.cb_marque.get()
        modele = self.cb_modele.get()
        cat = self.cb_cat_vehic.get()
        cat_id = None
        if cat != "(toutes)":
            cat_id = next((c["id"] for c in self.cats_vehic if c["nom"] == cat), None)
        resultats = m3.chercher_pieces_pour_vehicule(
            marque="" if marque == "(toutes)" else marque,
            modele="" if modele == "(tous)" else modele,
            annee=int(_num(self.e_annee.get(), 0)),
            categorie_id=cat_id)
        self._afficher_resultats_vehicule(resultats)

    def _chercher_reference(self):
        ref = self.e_ref_univ.get().strip()
        if not ref:
            return
        produits = m3.chercher_par_reference(ref)
        lignes = [{**p, "vehicule": f"(trouvé via {p.get('origine_match', 'réf.')})",
                   "position": "", "certitude": "", "categorie_nom": ""}
                  for p in produits]
        self._afficher_resultats_vehicule(lignes)

    def _afficher_resultats_vehicule(self, resultats):
        certitudes = {"confirme": "✅ Confirmé", "probable": "🟡 Probable",
                      "a_verifier": "⚠ À vérifier"}
        t = self.tab_vehic
        t.delete(*t.get_children())
        for i, r in enumerate(resultats):
            stock = r.get("stock_vente", 0) or 0
            tags = ("rupture",) if stock <= 0 else ()
            t.insert("", tk.END, iid=f"{r['id']}_{i}", tags=zebre(i, tags), values=(
                r["reference"], r["nom"], r.get("categorie_nom") or "—",
                r.get("marque") or "—", r.get("vehicule") or "—",
                r.get("position") or "—",
                certitudes.get(r.get("certitude"), ""),
                stock, fmt_money(r.get("prix_vente", 0)),
                r.get("emplacement") or "—"))
        dispo = sum(1 for r in resultats if (r.get("stock_vente") or 0) > 0)
        self.lbl_vehic_resume.configure(
            text=f"{len(resultats)} pièce(s) · {dispo} en rayon")
        if not resultats:
            self.statut("Aucune pièce trouvée — pensez à lier vos produits aux véhicules",
                        COULEURS["warning"])

    def _vendre_depuis_vehicule(self):
        sel = self.tab_vehic.selection()
        if not sel:
            return
        produit_id = int(sel[0].split("_")[0])
        p = db.get_produit(produit_id)
        if not p:
            return
        if (p.get("stock_vente") or 0) <= 0:
            messagebox.showwarning(
                "Rupture en rayon",
                f"« {p['nom'] } » n'est plus en rayon.\n"
                f"Réserve : {p.get('stock_reserve', 0)} — faites un transfert.",
                parent=self.root)
            return
        self.afficher_caisse()
        self._ajouter_produit_panier(produit_id, 1)
        self.statut(f"« {p['nom']} » ajouté au panier", COULEURS["success"])

    def _lier_compatibilite(self):
        produits = db.get_produits(inclure_inactifs=False)
        if not produits:
            messagebox.showwarning("Aucun produit", "Créez d'abord des produits.",
                                   parent=self.root)
            return
        d = DialogueCompatibilite(self.root, produits, m3.get_marques())
        if d.resultat:
            self.statut(d.resultat, COULEURS["success"])
            self._chercher_vehicule()

    def _nouveau_modele(self):
        d = DialogueModele(self.root)
        if d.resultat:
            self.statut(d.resultat, COULEURS["success"])
            self.cb_marque.configure(values=["(toutes)"] + m3.get_marques())

    # ═══════════════════════════════════════════════════
    #  🏬 DÉPÔTS
    # ═══════════════════════════════════════════════════

    def afficher_depots(self):
        if not self.peut("stock"):
            return self._refus()
        self._nouvelle_page("🏬 Dépôts et emplacements", self._idx_menu("Dépôts"))

        Bouton(self.zone_actions, "➕ Nouveau dépôt", "primary",
               self._nouveau_depot, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "🔄 Transférer du stock", "info",
               self._transferer_stock, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "🗑️ Supprimer", "danger",
               self._supprimer_depot, petit=True).pack(side=tk.LEFT, padx=3)

        conteneur = tk.Frame(self.zone, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        c1 = Carte(conteneur, "Dépôts")
        c1.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 6))
        c1.configure(width=520)
        c1.pack_propagate(False)
        self.tab_depots = TableauTriable(c1.corps, [
            ("code", "Code", 65, "center", False),
            ("nom", "Nom", 165, "w", False),
            ("type", "Type", 90, "w", False),
            ("vente", "Vente", 60, "center", False),
            ("articles", "Articles", 70, "center", True),
            ("valeur", "Valeur stock", 110, "e", True)], height=16)
        self.tab_depots.pack(fill=tk.BOTH, expand=True)
        self.tab_depots.bind("<Double-1>", lambda e: self._modifier_depot())
        self.tab_depots.bind("<<TreeviewSelect>>", lambda e: self._charger_depot_contenu())

        c2 = Carte(conteneur, "Contenu du dépôt")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self.rech_depot = EntreeRecherche(c2.corps, "Filtrer les articles…", 30,
                                          callback=self._charger_depot_contenu)
        self.rech_depot.pack(anchor="w", pady=(0, 6))
        self.tab_depot_contenu = TableauTriable(c2.corps, [
            ("ref", "Référence", 110, "w", False),
            ("nom", "Produit", 220, "w", False),
            ("qte", "Quantité", 75, "center", True),
            ("mini", "Mini", 55, "center", True),
            ("cump", "CUMP", 95, "e", True),
            ("valeur", "Valeur", 105, "e", True),
            ("empl", "Emplacement", 130, "w", False)], height=15)
        self.tab_depot_contenu.pack(fill=tk.BOTH, expand=True)
        self.lbl_depot_resume = tk.Label(c2.corps, text="", font=(POLICE, 9, "bold"),
                                         bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_depot_resume.pack(anchor="w", pady=(6, 0))

        self._charger_depots()

    def _charger_depots(self):
        conn = db.get_connection()
        stats = {r["depot_id"]: dict(r) for r in conn.execute(
            """SELECT sd.depot_id,
                      COUNT(CASE WHEN sd.quantite > 0 THEN 1 END) AS nb_articles,
                      COALESCE(SUM(sd.quantite * COALESCE(p.cump, p.prix_achat)), 0) AS valeur
               FROM stock_depot sd JOIN produits p ON p.id = sd.produit_id
               GROUP BY sd.depot_id""").fetchall()}
        conn.close()

        types = {"boutique": "🏪 Boutique", "reserve": "📦 Réserve",
                 "magasin": "🏬 Magasin", "vehicule": "🚚 Véhicule", "autre": "📍 Autre"}
        t = self.tab_depots
        t.delete(*t.get_children())
        for i, d in enumerate(m3.get_depots(actifs_seulement=False)):
            info = stats.get(d["id"], {})
            tags = () if d["actif"] else ("inactif",)
            t.insert("", tk.END, iid=d["id"], tags=zebre(i, tags), values=(
                d["code"], d["nom"] + ("" if d["actif"] else " (inactif)"),
                types.get(d["type"], d["type"]),
                "✅" if d["autorise_vente"] else "—",
                info.get("nb_articles", 0), fmt_money(info.get("valeur", 0))))
        enfants = t.get_children()
        if enfants:
            t.selection_set(enfants[0])
        self._charger_depot_contenu()

    def _charger_depot_contenu(self):
        sel = self.tab_depots.selection()
        t = self.tab_depot_contenu
        t.delete(*t.get_children())
        if not sel:
            self.lbl_depot_resume.configure(text="")
            return
        recherche = self.rech_depot.get() if hasattr(self, "rech_depot") else ""
        conn = db.get_connection()
        sql = """SELECT p.reference, p.nom, sd.quantite, sd.stock_mini,
                        COALESCE(p.cump, p.prix_achat) AS cump,
                        sd.quantite * COALESCE(p.cump, p.prix_achat) AS valeur,
                        sd.emplacement
                 FROM stock_depot sd JOIN produits p ON p.id = sd.produit_id
                 WHERE sd.depot_id = ? AND p.actif = 1"""
        params = [int(sel[0])]
        if recherche:
            sql += " AND (p.nom LIKE ? OR p.reference LIKE ?)"
            params += [f"%{recherche}%"] * 2
        sql += " ORDER BY sd.quantite DESC, p.nom"
        lignes = conn.execute(sql, params).fetchall()
        conn.close()

        total_qte = total_val = 0
        for i, l in enumerate(lignes):
            if not l["quantite"] and not recherche:
                continue
            total_qte += l["quantite"]
            total_val += l["valeur"] or 0
            tags = ("rupture",) if l["quantite"] <= 0 else (
                ("alerte",) if l["stock_mini"] and l["quantite"] <= l["stock_mini"] else ())
            t.insert("", tk.END, tags=zebre(i, tags), values=(
                l["reference"], l["nom"], l["quantite"], l["stock_mini"] or "—",
                fmt_money(l["cump"]), fmt_money(l["valeur"]), l["emplacement"] or "—"))
        self.lbl_depot_resume.configure(
            text=f"{total_qte} article(s) · valeur {fmt_money(total_val, self.devise)}")

    def _nouveau_depot(self):
        d = DialogueDepot(self.root)
        if d.resultat:
            self.statut(d.resultat, COULEURS["success"])
            self._charger_depots()

    def _modifier_depot(self):
        sel = self.tab_depots.selection()
        if not sel:
            return
        depot = next((x for x in m3.get_depots(actifs_seulement=False)
                      if x["id"] == int(sel[0])), None)
        if depot:
            d = DialogueDepot(self.root, depot)
            if d.resultat:
                self.statut(d.resultat, COULEURS["success"])
                self._charger_depots()

    def _supprimer_depot(self):
        if not self.peut("supprimer"):
            return self._refus()
        sel = self.tab_depots.selection()
        if not sel:
            return
        if not messagebox.askyesno("Confirmer", "Supprimer ce dépôt ?\n"
                                   "Il doit être vide.", parent=self.root):
            return
        ok, msg = m3.delete_depot(int(sel[0]))
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self._charger_depots()

    def _transferer_stock(self):
        depots = m3.get_depots()
        if len(depots) < 2:
            messagebox.showwarning("Impossible",
                                   "Il faut au moins 2 dépôts pour un transfert.",
                                   parent=self.root)
            return
        produits = db.get_produits(inclure_inactifs=False)
        d = DialogueTransfert(self.root, produits, depots)
        if d.resultat:
            self.statut(d.resultat, COULEURS["success"])
            self._charger_depots()
            self._maj_badge_alertes()

    # ═══════════════════════════════════════════════════
    #  ↩️ RETOURS
    # ═══════════════════════════════════════════════════

    def afficher_retours(self):
        if not self.peut("caisse"):
            return self._refus()
        self._nouvelle_page("↩️ Retours et avoirs", self._idx_menu("Retours"))

        Bouton(self.zone_actions, "➕ Enregistrer un retour", "primary",
               self._nouveau_retour, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "🔄 Actualiser", "secondary",
               self.afficher_retours, petit=True).pack(side=tk.LEFT, padx=3)

        conteneur = tk.Frame(self.zone, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        c1 = Carte(conteneur, "Retours enregistrés")
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self.tab_retours = TableauTriable(c1.corps, [
            ("num", "N° retour", 125, "w", False),
            ("date", "Date", 130, "w", False),
            ("vente", "Vente d'origine", 130, "w", False),
            ("client", "Client", 150, "w", False),
            ("motif", "Motif", 175, "w", False),
            ("nb", "Lignes", 55, "center", True),
            ("total", "Montant", 105, "e", True),
            ("mode", "Remboursement", 120, "w", False)], height=16)
        self.tab_retours.pack(fill=tk.BOTH, expand=True)
        self.tab_retours.bind("<<TreeviewSelect>>", lambda e: self._charger_retour_lignes())

        c2 = Carte(conteneur, "Détail du retour")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, padx=(6, 0))
        c2.configure(width=400)
        c2.pack_propagate(False)
        self.tab_retour_lignes = TableauTriable(c2.corps, [
            ("ref", "Réf.", 90, "w", False),
            ("nom", "Article", 145, "w", False),
            ("qte", "Qté", 45, "center", True),
            ("total", "Total", 85, "e", True),
            ("stock", "En stock", 70, "center", False)], height=16)
        self.tab_retour_lignes.pack(fill=tk.BOTH, expand=True)
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
                             "✅ Oui" if l["remis_en_stock"] else f"❌ {l['etat']}"))
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

    # ═══════════════════════════════════════════════════
    #  📉 PRÉVISIONS DE RUPTURE
    # ═══════════════════════════════════════════════════

    def afficher_previsions(self):
        if not self.peut("stock"):
            return self._refus()
        self._nouvelle_page("📉 Prévisions de rupture", self._idx_menu("Prévisions"))

        Bouton(self.zone_actions, "🛒 Créer la commande", "primary",
               self._commander_depuis_prevision, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "📤 Exporter", "info",
               self._exporter_previsions, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "🔤 Recalculer ABC", "secondary",
               self._recalculer_abc, petit=True).pack(side=tk.LEFT, padx=3)

        barre = tk.Frame(self.zone, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        tk.Label(barre, text="Horizon :", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.cb_horizon = ttk.Combobox(barre, state="readonly", width=12, font=(POLICE, 9),
                                       values=["7 jours", "14 jours", "30 jours", "60 jours"])
        self.cb_horizon.current(2)
        self.cb_horizon.pack(side=tk.LEFT, padx=(4, 14))
        self.cb_horizon.bind("<<ComboboxSelected>>", lambda e: self._charger_previsions())
        self.lbl_prev_resume = tk.Label(barre, text="", font=(POLICE, 9, "bold"),
                                        bg=COULEURS["bg"], fg=COULEURS["danger"])
        self.lbl_prev_resume.pack(side=tk.RIGHT, padx=8)

        # ── Courbe du CA (préférence : linéaire) ──
        graphe = Carte(self.zone, "Évolution du chiffre d'affaires (30 jours)")
        graphe.pack(fill=tk.X, pady=(0, 8))
        try:
            stats = db.get_dashboard_stats()
            self._dessiner_graphe(graphe.corps, stats.get("ventes_30j", []),
                                  jours_affiches=30, titre_court=False)
        except Exception:
            tk.Label(graphe.corps, text="Graphique indisponible", font=(POLICE, 9),
                     bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack()

        cadre = Carte(self.zone, "Produits à réapprovisionner")
        cadre.pack(fill=tk.BOTH, expand=True)
        zone_tab = tk.Frame(cadre.corps, bg=COULEURS["card"])
        zone_tab.pack(fill=tk.BOTH, expand=True)
        self.tab_previsions = TableauTriable(zone_tab, [
            ("urg", "Urgence", 90, "center", False),
            ("ref", "Référence", 110, "w", False),
            ("nom", "Produit", 210, "w", False),
            ("fourn", "Fournisseur", 145, "w", False),
            ("stock", "Rayon", 60, "center", True),
            ("vitesse", "Vent./jour", 80, "center", True),
            ("couv", "Couverture", 90, "center", True),
            ("rupture", "Rupture le", 95, "w", False),
            ("route", "En route", 70, "center", True),
            ("cmd", "À commander", 100, "center", True),
            ("valeur", "Coût estimé", 110, "e", True)])
        ajouter_scrollbars(zone_tab, self.tab_previsions)

        self._charger_previsions()

    def _charger_previsions(self):
        horizon = int(_num(self.cb_horizon.get().split()[0], 30))
        prev = m3.prevision_rupture(horizon_jours=horizon)
        self._previsions_courantes = prev
        icones = {"critique": "🔴 Critique", "haute": "🟠 Haute", "moyenne": "🟡 Moyenne"}
        t = self.tab_previsions
        t.delete(*t.get_children())
        cout = 0.0
        for i, p in enumerate(prev):
            cout += p["valeur_commande"]
            tags = ("rupture",) if p["urgence"] == "critique" else (
                ("alerte",) if p["urgence"] == "haute" else ())
            t.insert("", tk.END, iid=p["produit_id"], tags=zebre(i, tags), values=(
                icones.get(p["urgence"], p["urgence"]), p["reference"], p["nom"],
                p["fournisseur_nom"] or "—", p["stock"],
                f"{p['vitesse_jour']:.2f}",
                "—" if p["couverture_jours"] is None else f"{p['couverture_jours']:.0f} j",
                p["date_rupture"] or "—", p["qte_en_route"] or "—",
                p["qte_a_commander"], fmt_money(p["valeur_commande"])))
        critiques = sum(1 for p in prev if p["urgence"] == "critique")
        self.lbl_prev_resume.configure(
            text=f"{len(prev)} produit(s) · {critiques} critique(s) · "
                 f"budget {fmt_money(cout, self.devise)}")
        if not prev:
            self.statut("Aucune rupture prévue sur cet horizon 👍", COULEURS["success"])

    def _commander_depuis_prevision(self):
        prev = getattr(self, "_previsions_courantes", [])
        a_commander = [p for p in prev if p["qte_a_commander"] > 0]
        if not a_commander:
            messagebox.showinfo("Rien à commander",
                                "Aucune quantité à commander sur cet horizon.",
                                parent=self.root)
            return
        # Regroupement par fournisseur
        conn = db.get_connection()
        fournisseurs = {p["id"]: p["fournisseur_id"] for p in
                        [dict(r) for r in conn.execute(
                            "SELECT id, fournisseur_id FROM produits").fetchall()]}
        conn.close()
        par_fourn = {}
        for p in a_commander:
            fid = fournisseurs.get(p["produit_id"])
            par_fourn.setdefault(fid, []).append(p)

        sans_fourn = len(par_fourn.get(None, []))
        message = (f"{len(a_commander)} produit(s) à commander répartis sur "
                   f"{len([f for f in par_fourn if f])} fournisseur(s).\n")
        if sans_fourn:
            message += (f"\n⚠ {sans_fourn} produit(s) sans fournisseur seront ignorés.\n")
        message += "\nCréer les commandes en brouillon ?"
        if not messagebox.askyesno("Créer les commandes", message, parent=self.root):
            return

        crees = []
        for fid, produits in par_fourn.items():
            if not fid:
                continue
            items = [(p["produit_id"], "", p["qte_a_commander"],
                      p["valeur_commande"] / p["qte_a_commander"]
                      if p["qte_a_commander"] else 0) for p in produits]
            ok, msg, _ = m3.creer_commande(fid, items,
                                           notes="Générée depuis les prévisions de rupture")
            if ok:
                crees.append(msg)
        if crees:
            messagebox.showinfo("Commandes créées",
                                f"{len(crees)} commande(s) créée(s) en brouillon :\n\n"
                                + "\n".join(crees)
                                + "\n\nRetrouvez-les dans le menu Achats.", parent=self.root)
            self.statut(f"{len(crees)} commande(s) créée(s)", COULEURS["success"])
        else:
            messagebox.showwarning("Aucune commande",
                                   "Aucune commande n'a pu être créée.", parent=self.root)

    def _exporter_previsions(self):
        prev = getattr(self, "_previsions_courantes", [])
        if not prev:
            messagebox.showinfo("Rien à exporter", "Aucune prévision affichée.",
                                parent=self.root)
            return
        lignes = [[p["urgence"], p["reference"], p["nom"], p["fournisseur_nom"],
                   p["stock"], p["vitesse_jour"],
                   p["couverture_jours"] if p["couverture_jours"] is not None else "",
                   p["date_rupture"] or "", p["qte_en_route"], p["qte_a_commander"],
                   f"{p['valeur_commande']:.0f}"] for p in prev]
        chemin = db.export_csv(
            f"previsions_rupture_{datetime.now():%Y%m%d_%H%M}.csv",
            ["Urgence", "Référence", "Produit", "Fournisseur", "Stock rayon",
             "Ventes/jour", "Couverture (j)", "Rupture le", "En route",
             "À commander", "Coût estimé"], lignes)
        self._proposer_ouverture(chemin)

    def _recalculer_abc(self):
        ok, msg = m3.calculer_classes_abc()
        messagebox.showinfo("Classement ABC" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self.statut(msg, COULEURS["success"])

    # ═══════════════════════════════════════════════════
    #  Utilitaire d'index de menu
    # ═══════════════════════════════════════════════════

    def _idx_menu(self, libelle):
        """Retrouve l'index du bouton de menu portant ce libellé."""
        for i, b in enumerate(getattr(self, "boutons_menu", [])):
            try:
                if libelle in b.cget("text"):
                    return i
            except tk.TclError:
                continue
        return -1


# ═══════════════════════════════════════════════════════
#  DIALOGUES v3
# ═══════════════════════════════════════════════════════

class _Base(simpledialog.Dialog):
    """Socle commun : fond thémé + résultat."""

    def __init__(self, parent, titre):
        self.resultat = None
        super().__init__(parent, titre)

    def _label(self, master, texte, ligne):
        tk.Label(master, text=texte, font=(POLICE, 10), bg=COULEURS["card"],
                 fg=COULEURS["text"], anchor="w").grid(row=ligne, column=0,
                                                       sticky="w", pady=4)

    def _entree(self, master, ligne, largeur=26, defaut=""):
        e = tk.Entry(master, font=(POLICE, 10), width=largeur, bd=1, relief=tk.SOLID,
                     bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                     insertbackground=COULEURS["input_fg"])
        if defaut:
            e.insert(0, str(defaut))
        e.grid(row=ligne, column=1, sticky="w", padx=8, pady=4, ipady=3)
        return e


class DialogueDepot(_Base):
    def __init__(self, parent, depot=None):
        self.depot = depot
        super().__init__(parent, "Modifier le dépôt" if depot else "Nouveau dépôt")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        d = self.depot or {}
        self._label(master, "Code (3 lettres)", 0)
        self.e_code = self._entree(master, 0, 10, d.get("code", ""))
        self._label(master, "Nom du dépôt", 1)
        self.e_nom = self._entree(master, 1, 28, d.get("nom", ""))
        self._label(master, "Type", 2)
        self.cb_type = ttk.Combobox(master, state="readonly", width=20, font=(POLICE, 10),
                                    values=["boutique", "reserve", "magasin",
                                            "vehicule", "autre"])
        self.cb_type.set(d.get("type", "boutique"))
        self.cb_type.grid(row=2, column=1, sticky="w", padx=8, pady=4)
        self._label(master, "Responsable", 3)
        self.e_resp = self._entree(master, 3, 28, d.get("responsable", ""))
        self._label(master, "Téléphone", 4)
        self.e_tel = self._entree(master, 4, 20, d.get("telephone", ""))
        self._label(master, "Adresse", 5)
        self.e_adr = self._entree(master, 5, 28, d.get("adresse", ""))

        self.var_vente = tk.BooleanVar(value=bool(d.get("autorise_vente", 1)))
        tk.Checkbutton(master, text="On peut vendre depuis ce dépôt",
                       variable=self.var_vente, font=(POLICE, 10), bg=COULEURS["card"],
                       fg=COULEURS["text"], selectcolor=COULEURS["card"],
                       activebackground=COULEURS["card"]).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.var_actif = tk.BooleanVar(value=bool(d.get("actif", 1)))
        if self.depot:
            tk.Checkbutton(master, text="Dépôt actif", variable=self.var_actif,
                           font=(POLICE, 10), bg=COULEURS["card"], fg=COULEURS["text"],
                           selectcolor=COULEURS["card"],
                           activebackground=COULEURS["card"]).grid(
                row=7, column=0, columnspan=2, sticky="w")
        tk.Label(master, text="Un dépôt « réserve » sert au stockage : le stock n'y est\n"
                              "pas vendable tant qu'il n'est pas transféré en boutique.",
                 font=(POLICE, 8), bg=COULEURS["card"],
                 fg=COULEURS["text_secondary"], justify="left").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))
        return self.e_code

    def apply(self):
        code = self.e_code.get().strip().upper()
        nom = self.e_nom.get().strip()
        if self.depot:
            ok, msg = m3.update_depot(
                self.depot["id"], code=code, nom=nom, type=self.cb_type.get(),
                responsable=self.e_resp.get().strip(), telephone=self.e_tel.get().strip(),
                adresse=self.e_adr.get().strip(),
                autorise_vente=1 if self.var_vente.get() else 0,
                actif=1 if self.var_actif.get() else 0)
        else:
            ok, msg = m3.add_depot(code, nom, self.cb_type.get(),
                                   self.e_adr.get().strip(), self.e_resp.get().strip(),
                                   self.e_tel.get().strip(), self.var_vente.get())
        if ok:
            self.resultat = msg
        else:
            messagebox.showwarning("Impossible", msg, parent=self.parent)


class DialogueTransfert(_Base):
    def __init__(self, parent, produits, depots):
        self.produits = produits
        self.depots = depots
        super().__init__(parent, "Transférer du stock entre dépôts")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        self._label(master, "Produit", 0)
        self.cb_produit = ttk.Combobox(
            master, width=42, font=(POLICE, 10),
            values=[f"{p['reference']} — {p['nom']} (stock {p['stock']})"
                    for p in self.produits])
        self.cb_produit.grid(row=0, column=1, sticky="w", padx=8, pady=4)
        self.cb_produit.bind("<<ComboboxSelected>>", lambda e: self._maj_dispo())

        self._label(master, "Depuis le dépôt", 1)
        self.cb_source = ttk.Combobox(master, state="readonly", width=30, font=(POLICE, 10),
                                      values=[f"{d['code']} — {d['nom']}" for d in self.depots])
        self.cb_source.current(0)
        self.cb_source.grid(row=1, column=1, sticky="w", padx=8, pady=4)
        self.cb_source.bind("<<ComboboxSelected>>", lambda e: self._maj_dispo())

        self._label(master, "Vers le dépôt", 2)
        self.cb_dest = ttk.Combobox(master, state="readonly", width=30, font=(POLICE, 10),
                                    values=[f"{d['code']} — {d['nom']}" for d in self.depots])
        self.cb_dest.current(min(1, len(self.depots) - 1))
        self.cb_dest.grid(row=2, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Quantité", 3)
        self.e_qte = self._entree(master, 3, 10, "1")
        self._label(master, "Note (facultatif)", 4)
        self.e_note = self._entree(master, 4, 32)

        self.lbl_dispo = tk.Label(master, text="", font=(POLICE, 9, "bold"),
                                  bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_dispo.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        return self.cb_produit

    def _produit_courant(self):
        idx = self.cb_produit.current()
        return self.produits[idx] if 0 <= idx < len(self.produits) else None

    def _maj_dispo(self):
        p = self._produit_courant()
        if not p:
            return
        etat = m3.get_stock_par_depot(p["id"])
        detail = " · ".join(f"{d['code']} : {d['quantite']}" for d in etat)
        self.lbl_dispo.configure(text=f"Stock actuel — {detail}")

    def validate(self):
        if not self._produit_courant():
            messagebox.showwarning("Produit requis", "Choisissez un produit.", parent=self)
            return False
        if self.cb_source.current() == self.cb_dest.current():
            messagebox.showwarning("Dépôts identiques",
                                   "Choisissez deux dépôts différents.", parent=self)
            return False
        if _num(self.e_qte.get()) <= 0:
            messagebox.showwarning("Quantité invalide",
                                   "Saisissez une quantité supérieure à 0.", parent=self)
            return False
        return True

    def apply(self):
        p = self._produit_courant()
        ok, msg = m3.transferer(p["id"], self.depots[self.cb_source.current()]["id"],
                                self.depots[self.cb_dest.current()]["id"],
                                int(_num(self.e_qte.get())), self.e_note.get().strip())
        if ok:
            self.resultat = msg
        else:
            messagebox.showwarning("Impossible", msg, parent=self.parent)


class DialogueCommande(_Base):
    """Création d'une commande fournisseur multi-lignes."""

    def __init__(self, parent, devise="F CFA"):
        self.devise = devise
        self.fournisseurs = db.get_fournisseurs()
        self.depots = m3.get_depots()
        self.produits = db.get_produits(inclure_inactifs=False)
        self.lignes = []
        super().__init__(parent, "Nouvelle commande fournisseur")

    def body(self, master):
        master.configure(bg=COULEURS["card"])

        haut = tk.Frame(master, bg=COULEURS["card"])
        haut.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(haut, text="Fournisseur", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=0, column=0, sticky="w")
        self.cb_fourn = ttk.Combobox(haut, state="readonly", width=30, font=(POLICE, 10),
                                     values=[f["nom"] for f in self.fournisseurs])
        self.cb_fourn.current(0)
        self.cb_fourn.grid(row=0, column=1, sticky="w", padx=8)

        tk.Label(haut, text="Dépôt de réception", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.cb_depot = ttk.Combobox(haut, state="readonly", width=22, font=(POLICE, 10),
                                     values=[f"{d['code']} — {d['nom']}" for d in self.depots])
        # Par défaut : la réserve si elle existe
        idx_res = next((i for i, d in enumerate(self.depots)
                        if not d["autorise_vente"]), 0)
        self.cb_depot.current(idx_res)
        self.cb_depot.grid(row=0, column=3, sticky="w", padx=8)

        tk.Label(haut, text="Livraison prévue", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.e_prevue = tk.Entry(haut, font=(POLICE, 10), width=14, bd=1, relief=tk.SOLID)
        self.e_prevue.insert(0, (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))
        self.e_prevue.grid(row=1, column=1, sticky="w", padx=8, pady=(6, 0))

        tk.Label(haut, text="Frais (transport…)", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(6, 0))
        self.e_frais = tk.Entry(haut, font=(POLICE, 10), width=12, bd=1, relief=tk.SOLID,
                                justify="right")
        self.e_frais.insert(0, "0")
        self.e_frais.grid(row=1, column=3, sticky="w", padx=8, pady=(6, 0))

        # ── Ajout de ligne ──
        ajout = tk.Frame(master, bg=COULEURS["bg"], padx=8, pady=8)
        ajout.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        tk.Label(ajout, text="Article", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.cb_prod = ttk.Combobox(
            ajout, width=34, font=(POLICE, 9),
            values=[f"{p['reference']} — {p['nom']}" for p in self.produits])
        self.cb_prod.pack(side=tk.LEFT, padx=4)
        self.cb_prod.bind("<<ComboboxSelected>>", lambda e: self._prix_suggere())
        tk.Label(ajout, text="Qté", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT, padx=(8, 0))
        self.e_qte = tk.Entry(ajout, font=(POLICE, 9), width=6, bd=1, relief=tk.SOLID,
                              justify="center")
        self.e_qte.insert(0, "1")
        self.e_qte.pack(side=tk.LEFT, padx=4)
        tk.Label(ajout, text="P.U. achat", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT, padx=(8, 0))
        self.e_pu = tk.Entry(ajout, font=(POLICE, 9), width=10, bd=1, relief=tk.SOLID,
                             justify="right")
        self.e_pu.pack(side=tk.LEFT, padx=4)
        Bouton(ajout, "➕ Ajouter", "success", self._ajouter_ligne,
               petit=True).pack(side=tk.LEFT, padx=8)
        Bouton(ajout, "🗑️ Retirer", "danger", self._retirer_ligne,
               petit=True).pack(side=tk.LEFT)

        # ── Tableau des lignes ──
        self.tab = TableauTriable(master, [
            ("ref", "Référence", 110, "w", False),
            ("nom", "Article", 230, "w", False),
            ("qte", "Qté", 60, "center", True),
            ("pu", "P.U.", 95, "e", True),
            ("total", "Total", 105, "e", True)], height=8)
        self.tab.grid(row=2, column=0, sticky="nsew")
        master.rowconfigure(2, weight=1)
        master.columnconfigure(0, weight=1)

        self.lbl_total = tk.Label(master, text="Total : 0", font=(POLICE, 12, "bold"),
                                  bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_total.grid(row=3, column=0, sticky="e", pady=(6, 0))

        tk.Label(master, text="Notes", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.e_notes = tk.Entry(master, font=(POLICE, 10), bd=1, relief=tk.SOLID)
        self.e_notes.grid(row=5, column=0, sticky="ew", ipady=3)
        return self.cb_prod

    def _prix_suggere(self):
        idx = self.cb_prod.current()
        if 0 <= idx < len(self.produits):
            p = self.produits[idx]
            self.e_pu.delete(0, tk.END)
            self.e_pu.insert(0, f"{p.get('cump') or p.get('prix_achat') or 0:.0f}")

    def _ajouter_ligne(self):
        idx = self.cb_prod.current()
        if idx < 0:
            messagebox.showwarning("Article requis", "Choisissez un article.", parent=self)
            return
        p = self.produits[idx]
        qte = int(_num(self.e_qte.get(), 0))
        pu = _num(self.e_pu.get(), 0)
        if qte <= 0:
            messagebox.showwarning("Quantité invalide", "Quantité > 0 requise.", parent=self)
            return
        # Cumul si l'article est déjà dans la commande au même prix
        for l in self.lignes:
            if l["produit_id"] == p["id"] and abs(l["pu"] - pu) < 0.01:
                l["qte"] += qte
                break
        else:
            self.lignes.append({"produit_id": p["id"], "reference": p["reference"],
                                "nom": p["nom"], "qte": qte, "pu": pu})
        self.e_qte.delete(0, tk.END)
        self.e_qte.insert(0, "1")
        self._rafraichir()

    def _retirer_ligne(self):
        sel = self.tab.selection()
        if not sel:
            return
        i = int(sel[0])
        if 0 <= i < len(self.lignes):
            self.lignes.pop(i)
            self._rafraichir()

    def _rafraichir(self):
        self.tab.delete(*self.tab.get_children())
        total = 0.0
        for i, l in enumerate(self.lignes):
            total += l["qte"] * l["pu"]
            self.tab.insert("", tk.END, iid=str(i), tags=zebre(i), values=(
                l["reference"], l["nom"], l["qte"], fmt_money(l["pu"]),
                fmt_money(l["qte"] * l["pu"])))
        frais = _num(self.e_frais.get(), 0)
        self.lbl_total.configure(
            text=f"Articles : {fmt_money(total, self.devise)}  +  "
                 f"frais {fmt_money(frais, self.devise)}  =  "
                 f"{fmt_money(total + frais, self.devise)}")

    def validate(self):
        if not self.lignes:
            messagebox.showwarning("Commande vide",
                                   "Ajoutez au moins un article.", parent=self)
            return False
        return True

    def apply(self):
        fid = self.fournisseurs[self.cb_fourn.current()]["id"]
        items = [(l["produit_id"], "", l["qte"], l["pu"]) for l in self.lignes]
        self.resultat = (fid, items, self.depots[self.cb_depot.current()]["id"],
                         _num(self.e_frais.get(), 0), self.e_prevue.get().strip(),
                         self.e_notes.get().strip())


class DialogueReception(_Base):
    """Saisie des quantités reçues, ligne par ligne."""

    def __init__(self, parent, commande_id, lignes, devise="F CFA"):
        self.commande_id = commande_id
        self.lignes = lignes
        self.devise = devise
        self.depots = m3.get_depots()
        self.depot_id = None
        self.entrees = {}
        super().__init__(parent, "Réceptionner la commande")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        tk.Label(master, text="Saisissez les quantités RÉELLEMENT reçues.\n"
                              "Laissez la valeur proposée pour tout réceptionner.",
                 font=(POLICE, 10), bg=COULEURS["card"], fg=COULEURS["text"],
                 justify="left").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        tk.Label(master, text="Dépôt de réception", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.cb_depot = ttk.Combobox(master, state="readonly", width=26, font=(POLICE, 10),
                                     values=[f"{d['code']} — {d['nom']}" for d in self.depots])
        idx_res = next((i for i, d in enumerate(self.depots) if not d["autorise_vente"]), 0)
        self.cb_depot.current(idx_res)
        self.cb_depot.grid(row=1, column=1, columnspan=3, sticky="w", padx=8, pady=(0, 8))

        for col, titre in enumerate(("Article", "Commandé", "Déjà reçu", "Reçu maintenant")):
            tk.Label(master, text=titre, font=(POLICE, 9, "bold"), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).grid(row=2, column=col, sticky="w",
                                                         padx=4, pady=(0, 4))
        for i, l in enumerate(self.lignes):
            r = 3 + i
            tk.Label(master, text=f"{l['reference'] or ''} {l['produit_nom'] or l['designation']}",
                     font=(POLICE, 10), bg=COULEURS["card"], fg=COULEURS["text"],
                     anchor="w").grid(row=r, column=0, sticky="w", padx=4, pady=2)
            tk.Label(master, text=str(l["quantite"]), font=(POLICE, 10),
                     bg=COULEURS["card"]).grid(row=r, column=1, padx=4)
            tk.Label(master, text=str(l["quantite_recue"]), font=(POLICE, 10),
                     bg=COULEURS["card"]).grid(row=r, column=2, padx=4)
            e = tk.Entry(master, font=(POLICE, 10, "bold"), width=8, bd=1,
                         relief=tk.SOLID, justify="center")
            e.insert(0, str(l["quantite"] - l["quantite_recue"]))
            e.grid(row=r, column=3, padx=4, pady=2, ipady=2)
            self.entrees[l["id"]] = e

        tk.Label(master, text="⚠ La réception met à jour le CUMP (coût moyen pondéré) "
                              "et donc la valeur de votre stock.",
                 font=(POLICE, 8), bg=COULEURS["card"], fg=COULEURS["warning"],
                 justify="left").grid(row=3 + len(self.lignes), column=0, columnspan=4,
                                      sticky="w", pady=(10, 0))
        return None

    def validate(self):
        total = 0
        for lid, e in self.entrees.items():
            q = _num(e.get(), -1)
            if q < 0:
                messagebox.showwarning("Quantité invalide",
                                       "Les quantités doivent être positives.", parent=self)
                return False
            total += q
        if total <= 0:
            messagebox.showwarning("Rien à réceptionner",
                                   "Saisissez au moins une quantité.", parent=self)
            return False
        return True

    def apply(self):
        self.depot_id = self.depots[self.cb_depot.current()]["id"]
        self.resultat = {lid: int(_num(e.get(), 0))
                         for lid, e in self.entrees.items() if _num(e.get(), 0) > 0}


class DialogueOuvrirInventaire(_Base):
    def __init__(self, parent, depots, categories):
        self.depots = depots
        self.categories = categories
        super().__init__(parent, "Ouvrir un inventaire")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        self._label(master, "Dépôt à inventorier", 0)
        self.cb_depot = ttk.Combobox(master, state="readonly", width=30, font=(POLICE, 10),
                                     values=[f"{d['code']} — {d['nom']}" for d in self.depots])
        self.cb_depot.current(0)
        self.cb_depot.grid(row=0, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Catégorie (facultatif)", 1)
        self.cb_cat = ttk.Combobox(
            master, state="readonly", width=30, font=(POLICE, 10),
            values=["(toutes les catégories)"] + [c["nom"] for c in self.categories])
        self.cb_cat.current(0)
        self.cb_cat.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Notes", 2)
        self.e_notes = self._entree(master, 2, 32)

        tk.Label(master, text="Le stock théorique de chaque produit est figé à l'ouverture.\n"
                              "Vous comptez ensuite physiquement, puis vous clôturez.",
                 font=(POLICE, 8), bg=COULEURS["card"], fg=COULEURS["text_secondary"],
                 justify="left").grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        return self.cb_depot

    def apply(self):
        cat_id = None
        if self.cb_cat.current() > 0:
            cat_id = self.categories[self.cb_cat.current() - 1]["id"]
        self.resultat = (self.depots[self.cb_depot.current()]["id"], cat_id,
                         self.e_notes.get().strip())


class DialogueComptage(_Base):
    def __init__(self, parent, ligne, motifs):
        self.ligne = ligne
        self.motifs = [m.strip() for m in motifs if m.strip()]
        super().__init__(parent, "Saisir le comptage")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        l = self.ligne
        tk.Label(master, text=f"{l['reference']} — {l['produit_nom']}",
                 font=(POLICE, 11, "bold"), bg=COULEURS["card"],
                 fg=COULEURS["text"]).grid(row=0, column=0, columnspan=2,
                                           sticky="w", pady=(0, 4))
        tk.Label(master, text=f"Stock théorique : {l['stock_theorique']}   ·   "
                              f"Emplacement : {l['emplacement'] or '—'}",
                 font=(POLICE, 9), bg=COULEURS["card"],
                 fg=COULEURS["text_secondary"]).grid(row=1, column=0, columnspan=2,
                                                     sticky="w", pady=(0, 10))

        self._label(master, "Quantité comptée", 2)
        self.e_compte = tk.Entry(master, font=(POLICE, 14, "bold"), width=10, bd=1,
                                 relief=tk.SOLID, justify="center")
        valeur = l["stock_compte"] if l["stock_compte"] is not None else l["stock_theorique"]
        self.e_compte.insert(0, str(valeur))
        self.e_compte.select_range(0, tk.END)
        self.e_compte.grid(row=2, column=1, sticky="w", padx=8, pady=4, ipady=3)
        self.e_compte.bind("<KeyRelease>", lambda e: self._maj_ecart())

        self._label(master, "Motif de l'écart", 3)
        self.cb_motif = ttk.Combobox(master, width=24, font=(POLICE, 10),
                                     values=[""] + self.motifs)
        self.cb_motif.set(l["motif"] or "")
        self.cb_motif.grid(row=3, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Notes", 4)
        self.e_notes = self._entree(master, 4, 28, l["notes"] or "")

        self.lbl_ecart = tk.Label(master, text="", font=(POLICE, 11, "bold"),
                                  bg=COULEURS["card"])
        self.lbl_ecart.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._maj_ecart()
        return self.e_compte

    def _maj_ecart(self):
        compte = _num(self.e_compte.get(), None)
        if compte is None:
            return
        ecart = int(compte) - self.ligne["stock_theorique"]
        valeur = ecart * (self.ligne["cump_unitaire"] or 0)
        if ecart == 0:
            self.lbl_ecart.configure(text="✅ Conforme au stock théorique",
                                     fg=COULEURS["success"])
        else:
            self.lbl_ecart.configure(
                text=f"{'📈' if ecart > 0 else '📉'} Écart {ecart:+d} "
                     f"→ {fmt_money(valeur)}",
                fg=COULEURS["warning"] if ecart > 0 else COULEURS["danger"])

    def validate(self):
        if _num(self.e_compte.get(), -1) < 0:
            messagebox.showwarning("Quantité invalide",
                                   "La quantité comptée doit être >= 0.", parent=self)
            return False
        return True

    def apply(self):
        self.resultat = (int(_num(self.e_compte.get(), 0)), self.cb_motif.get().strip(),
                         self.e_notes.get().strip())


class DialogueRetour(_Base):
    """Retour partiel d'une vente."""

    def __init__(self, parent, ventes, devise="F CFA"):
        self.ventes = ventes
        self.devise = devise
        self.lignes_vente = []
        self.entrees = {}
        super().__init__(parent, "Enregistrer un retour")

    def body(self, master):
        master.configure(bg=COULEURS["card"])

        tk.Label(master, text="Vente d'origine", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=0, column=0, sticky="w", pady=4)
        self.cb_vente = ttk.Combobox(
            master, width=52, font=(POLICE, 10),
            values=[f"{v['numero'] or v['id']} — {v['client_nom']} — "
                    f"{fmt_money(v['total'])} — {fmt_date(v['date_vente'], False)}"
                    for v in self.ventes])
        self.cb_vente.grid(row=0, column=1, columnspan=3, sticky="w", padx=8, pady=4)
        self.cb_vente.bind("<<ComboboxSelected>>", lambda e: self._charger_lignes())

        tk.Label(master, text="Motif du retour", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=1, column=0, sticky="w", pady=4)
        self.cb_motif = ttk.Combobox(master, width=32, font=(POLICE, 10),
                                     values=["Ne correspond pas au véhicule",
                                             "Pièce défectueuse", "Erreur de référence",
                                             "Client a changé d'avis", "Doublon", "Autre"])
        self.cb_motif.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        tk.Label(master, text="Remboursement", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=1, column=2, sticky="w", padx=(16, 0))
        self.cb_mode = ttk.Combobox(master, state="readonly", width=14, font=(POLICE, 10),
                                    values=["Espèces", "Avoir", "Échange",
                                            "Wave", "Orange Money"])
        self.cb_mode.current(0)
        self.cb_mode.grid(row=1, column=3, sticky="w", padx=8)

        self.zone_lignes = tk.Frame(master, bg=COULEURS["bg"], padx=8, pady=8)
        self.zone_lignes.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(10, 0))
        master.rowconfigure(2, weight=1)
        tk.Label(self.zone_lignes, text="Choisissez d'abord une vente.",
                 font=(POLICE, 10), bg=COULEURS["bg"],
                 fg=COULEURS["text_secondary"]).pack(anchor="w")

        self.lbl_total_retour = tk.Label(master, text="", font=(POLICE, 12, "bold"),
                                         bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_total_retour.grid(row=3, column=0, columnspan=4, sticky="e", pady=(8, 0))
        return self.cb_vente

    def _charger_lignes(self):
        for w in self.zone_lignes.winfo_children():
            w.destroy()
        self.entrees.clear()
        idx = self.cb_vente.current()
        if idx < 0:
            return
        vente_id = self.ventes[idx]["id"]
        _, lignes = db.get_vente_details(vente_id)

        # Quantités déjà retournées
        conn = db.get_connection()
        deja = {r["produit_id"]: r["q"] for r in conn.execute(
            """SELECT rd.produit_id, SUM(rd.quantite) AS q
               FROM retours_details rd JOIN retours r ON r.id = rd.retour_id
               WHERE r.vente_id = ? AND r.statut = 'valide'
               GROUP BY rd.produit_id""", (vente_id,)).fetchall()}
        conn.close()

        for col, titre in enumerate(("Article", "Vendu", "Déjà rendu", "À rendre",
                                     "Remettre en stock", "État")):
            tk.Label(self.zone_lignes, text=titre, font=(POLICE, 9, "bold"),
                     bg=COULEURS["bg"], fg=COULEURS["text_secondary"]).grid(
                row=0, column=col, sticky="w", padx=4, pady=(0, 4))

        self.lignes_vente = []
        for i, l in enumerate(lignes):
            if not l["produit_id"]:
                continue
            rendu = deja.get(l["produit_id"], 0)
            reste = l["quantite"] - rendu
            if reste <= 0:
                continue
            r = 1 + len(self.lignes_vente)
            tk.Label(self.zone_lignes, text=f"{l['reference']} {l['produit_nom']}",
                     font=(POLICE, 10), bg=COULEURS["bg"], anchor="w").grid(
                row=r, column=0, sticky="w", padx=4, pady=2)
            tk.Label(self.zone_lignes, text=str(l["quantite"]), font=(POLICE, 10),
                     bg=COULEURS["bg"]).grid(row=r, column=1, padx=4)
            tk.Label(self.zone_lignes, text=str(rendu), font=(POLICE, 10),
                     bg=COULEURS["bg"]).grid(row=r, column=2, padx=4)
            e = tk.Entry(self.zone_lignes, font=(POLICE, 10, "bold"), width=6, bd=1,
                         relief=tk.SOLID, justify="center")
            e.insert(0, "0")
            e.grid(row=r, column=3, padx=4, pady=2)
            e.bind("<KeyRelease>", lambda ev: self._maj_total())
            var_stock = tk.BooleanVar(value=True)
            tk.Checkbutton(self.zone_lignes, variable=var_stock, bg=COULEURS["bg"],
                           activebackground=COULEURS["bg"],
                           selectcolor=COULEURS["card"]).grid(row=r, column=4)
            cb_etat = ttk.Combobox(self.zone_lignes, state="readonly", width=8,
                                   font=(POLICE, 9), values=["neuf", "abime", "hs"])
            cb_etat.current(0)
            cb_etat.grid(row=r, column=5, padx=4)
            self.entrees[l["produit_id"]] = (e, var_stock, cb_etat, l["prix_unitaire"], reste)
            self.lignes_vente.append(l)

        if not self.lignes_vente:
            tk.Label(self.zone_lignes,
                     text="Tous les articles de cette vente ont déjà été retournés.",
                     font=(POLICE, 10), bg=COULEURS["bg"],
                     fg=COULEURS["danger"]).grid(row=1, column=0, columnspan=6, sticky="w")
        self._maj_total()

    def _maj_total(self):
        total = 0.0
        for (e, _v, _c, pu, _reste) in self.entrees.values():
            total += _num(e.get(), 0) * pu
        self.lbl_total_retour.configure(
            text=f"Montant du retour : {fmt_money(total, self.devise)}")

    def validate(self):
        if self.cb_vente.current() < 0:
            messagebox.showwarning("Vente requise", "Choisissez la vente d'origine.",
                                   parent=self)
            return False
        total_qte = 0
        for pid, (e, _v, _c, _pu, reste) in self.entrees.items():
            q = _num(e.get(), -1)
            if q < 0:
                messagebox.showwarning("Quantité invalide",
                                       "Les quantités doivent être positives.", parent=self)
                return False
            if q > reste:
                messagebox.showwarning(
                    "Quantité trop élevée",
                    f"Vous ne pouvez rendre que {reste} unité(s) de cet article.",
                    parent=self)
                return False
            total_qte += q
        if total_qte <= 0:
            messagebox.showwarning("Retour vide",
                                   "Saisissez au moins une quantité à rendre.", parent=self)
            return False
        return True

    def apply(self):
        vente_id = self.ventes[self.cb_vente.current()]["id"]
        items = []
        for pid, (e, var_stock, cb_etat, pu, _reste) in self.entrees.items():
            q = int(_num(e.get(), 0))
            if q > 0:
                items.append((pid, q, pu, var_stock.get(), cb_etat.get()))
        ok, msg, _ = m3.creer_retour(vente_id, items, self.cb_motif.get().strip(),
                                     self.cb_mode.get())
        if ok:
            self.resultat = msg
        else:
            messagebox.showwarning("Impossible", msg, parent=self.parent)


class DialogueCompatibilite(_Base):
    """Lier une pièce à un ou plusieurs modèles de véhicule."""

    def __init__(self, parent, produits, marques):
        self.produits = produits
        self.marques = marques
        super().__init__(parent, "Lier une pièce à un véhicule")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        self._label(master, "Pièce", 0)
        self.cb_prod = ttk.Combobox(
            master, width=44, font=(POLICE, 10),
            values=[f"{p['reference']} — {p['nom']}" for p in self.produits])
        self.cb_prod.grid(row=0, column=1, sticky="w", padx=8, pady=4)
        self.cb_prod.bind("<<ComboboxSelected>>", lambda e: self._maj_existants())

        self._label(master, "Marque", 1)
        self.cb_marque = ttk.Combobox(master, state="readonly", width=20, font=(POLICE, 10),
                                      values=self.marques)
        if self.marques:
            self.cb_marque.current(0)
        self.cb_marque.grid(row=1, column=1, sticky="w", padx=8, pady=4)
        self.cb_marque.bind("<<ComboboxSelected>>", lambda e: self._maj_modeles())

        self._label(master, "Modèle / motorisation", 2)
        self.cb_modele = ttk.Combobox(master, state="readonly", width=44, font=(POLICE, 10))
        self.cb_modele.grid(row=2, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Position", 3)
        self.cb_pos = ttk.Combobox(master, width=18, font=(POLICE, 10),
                                   values=["", "avant", "arrière", "avant gauche",
                                           "avant droit", "arrière gauche", "arrière droit"])
        self.cb_pos.grid(row=3, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Fiabilité de l'info", 4)
        self.cb_cert = ttk.Combobox(master, state="readonly", width=18, font=(POLICE, 10),
                                    values=["confirme", "probable", "a_verifier"])
        self.cb_cert.current(0)
        self.cb_cert.grid(row=4, column=1, sticky="w", padx=8, pady=4)

        # ── Références croisées ──
        tk.Frame(master, bg=COULEURS["border"], height=1).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=10)
        tk.Label(master, text="Ajouter aussi une référence équivalente (facultatif)",
                 font=(POLICE, 9, "bold"), bg=COULEURS["card"],
                 fg=COULEURS["text_secondary"]).grid(row=6, column=0, columnspan=2,
                                                     sticky="w")
        self._label(master, "Référence", 7)
        self.e_ref = self._entree(master, 7, 22)
        self._label(master, "Type", 8)
        self.cb_type_ref = ttk.Combobox(master, state="readonly", width=18, font=(POLICE, 10),
                                        values=["oem", "equivalent", "fournisseur",
                                                "ancienne", "code_barres"])
        self.cb_type_ref.current(1)
        self.cb_type_ref.grid(row=8, column=1, sticky="w", padx=8, pady=4)
        self._label(master, "Marque de l'équivalent", 9)
        self.e_marque_ref = self._entree(master, 9, 22)

        self.lbl_existants = tk.Label(master, text="", font=(POLICE, 9),
                                      bg=COULEURS["card"], fg=COULEURS["primary"],
                                      justify="left", wraplength=460)
        self.lbl_existants.grid(row=10, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self._maj_modeles()
        return self.cb_prod

    def _maj_modeles(self):
        modeles = m3.get_modeles(self.cb_marque.get())
        self._modeles = modeles
        self.cb_modele.configure(values=[
            f"{m['modele']} {m['motorisation']} "
            f"({m['annee_debut'] or '?'}–{m['annee_fin'] or 'auj.'})".replace("  ", " ")
            for m in modeles])
        if modeles:
            self.cb_modele.current(0)

    def _maj_existants(self):
        idx = self.cb_prod.current()
        if idx < 0:
            return
        p = self.produits[idx]
        compats = m3.get_compatibilites_produit(p["id"])
        refs = m3.get_references_produit(p["id"])
        parties = []
        if compats:
            parties.append("Véhicules déjà liés : " + ", ".join(
                f"{c['marque']} {c['modele']}" for c in compats[:6]))
        if refs:
            parties.append("Références : " + ", ".join(
                f"{r['reference']} ({r['type']})" for r in refs[:5]))
        self.lbl_existants.configure(text="\n".join(parties) or "Aucune liaison existante.")

    def validate(self):
        if self.cb_prod.current() < 0:
            messagebox.showwarning("Pièce requise", "Choisissez une pièce.", parent=self)
            return False
        if self.cb_modele.current() < 0:
            messagebox.showwarning("Modèle requis", "Choisissez un modèle de véhicule.",
                                   parent=self)
            return False
        return True

    def apply(self):
        p = self.produits[self.cb_prod.current()]
        modele = self._modeles[self.cb_modele.current()]
        messages = []
        ok, msg = m3.lier_compatibilite(p["id"], modele["id"], self.cb_pos.get().strip(),
                                        self.cb_cert.get())
        messages.append(msg)
        ref = self.e_ref.get().strip()
        if ref:
            ok2, msg2 = m3.add_reference(p["id"], ref, self.cb_type_ref.get(),
                                         self.e_marque_ref.get().strip())
            messages.append(msg2)
        self.resultat = " · ".join(messages)


class DialogueModele(_Base):
    def __init__(self, parent):
        super().__init__(parent, "Nouveau modèle de véhicule")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        self._label(master, "Marque", 0)
        self.cb_marque = ttk.Combobox(master, width=24, font=(POLICE, 10),
                                      values=m3.get_marques())
        self.cb_marque.grid(row=0, column=1, sticky="w", padx=8, pady=4)
        self._label(master, "Modèle", 1)
        self.e_modele = self._entree(master, 1, 26)
        self._label(master, "Motorisation", 2)
        self.e_moteur = self._entree(master, 2, 26)
        self._label(master, "Carburant", 3)
        self.cb_carb = ttk.Combobox(master, state="readonly", width=18, font=(POLICE, 10),
                                    values=["essence", "diesel", "hybride", "GPL"])
        self.cb_carb.current(0)
        self.cb_carb.grid(row=3, column=1, sticky="w", padx=8, pady=4)
        self._label(master, "Année de début", 4)
        self.e_debut = self._entree(master, 4, 10)
        self._label(master, "Année de fin (0 = encore produit)", 5)
        self.e_fin = self._entree(master, 5, 10, "0")
        return self.cb_marque

    def validate(self):
        if not self.cb_marque.get().strip() or not self.e_modele.get().strip():
            messagebox.showwarning("Champs requis", "Marque et modèle sont obligatoires.",
                                   parent=self)
            return False
        return True

    def apply(self):
        ok, msg, _ = m3.add_modele(
            self.cb_marque.get().strip(), self.e_modele.get().strip(),
            self.e_moteur.get().strip(), self.cb_carb.get(),
            int(_num(self.e_debut.get(), 0)), int(_num(self.e_fin.get(), 0)))
        if ok:
            self.resultat = msg
        else:
            messagebox.showwarning("Impossible", msg, parent=self.parent)
