"""
SODIPAC - Gestion des Créances Clients & Historique des Règlements (Version Améliorée)

Fonctionnalités :
- Tableau de bord KPI synthétique (Total créances, Retards > 15j, Clients débiteurs, Règlements du mois).
- Filtres intelligents (Par client, Par recherche texte/téléphone, Par statut d'ancienneté : Toutes / Retards / À suivre / Récentes).
- Double-clic & Bouton "💰 Encaisser un acompte / solde" avec génération automatique du reçu de règlement.
- Vue combinée "Encours par client" (gauche) et "Factures non soldées" (droite).
- Historique complet des règlements effectués avec ré-impression des reçus d'encaissement.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import database as db
import metier_v3 as m3
import factures
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, EntreeRecherche,
                        TableauTriable, ajouter_scrollbars, fmt_date, fmt_money, zebre,
                        parse_float, KPI)
from dialogues import DemanderMontant


class CreancesMixin:
    """Gestion des créances clients & encaissements d'acomptes."""

    def afficher_creances(self):
        if not self.peut("rapports"):
            return self._refus()
        self._nouvelle_page("💳 Gestion des créances clients & Règlements", self._idx_menu("Créances"))

        self._filtre_statut_creance = "toutes"  # toutes | retard | suivre | recentes

        # ── Actions dans l'en-tête de page ──
        Bouton(self.zone_actions, "💰 Encaisser créance (F2)", "success",
               self._encaisser_creance, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "📑 Imprimer Relances CSV", "info",
               self._imprimer_creances, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "📜 Historique Règlements", "secondary",
               self._voir_historique_reglements, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "🔄 Actualiser", "secondary",
               self.afficher_creances, petit=True, outline=True).pack(side=tk.LEFT, padx=3)

        # ── Conteneur principal ──
        grille = tk.Frame(self.zone, bg=COULEURS["bg"])
        grille.pack(fill=tk.BOTH, expand=True)

        # --- Section 1 : Bandeau KPI Synthèse Créances ---
        self.cadre_kpi_creance = tk.Frame(grille, bg=COULEURS["bg"])
        self.cadre_kpi_creance.pack(fill=tk.X, pady=(0, 10))

        # --- Section 2 : Barre de Filtres Avancés ---
        carte_filtres = Carte(grille)
        carte_filtres.pack(fill=tk.X, pady=(0, 10))
        cf = carte_filtres.corps

        # Recherche client / téléphone
        self.rech_creances = EntreeRecherche(cf, "Chercher nom client, téléphone ou n° facture…", 34,
                                             callback=self._charger_creances)
        self.rech_creances.pack(side=tk.LEFT, padx=(0, 12))

        # Pilules de filtres par ancienneté
        f_pilules = tk.Frame(cf, bg=COULEURS["card"])
        f_pilules.pack(side=tk.LEFT, padx=4)

        self.btn_cr_toutes = Bouton(f_pilules, "Toutes", "primary", lambda: self._filtrer_ancienneté("toutes"), petit=True)
        self.btn_cr_toutes.pack(side=tk.LEFT, padx=2)

        self.btn_cr_retard = Bouton(f_pilules, "🔴 En retard (>15j)", "danger", lambda: self._filtrer_ancienneté("retard"), petit=True, outline=True)
        self.btn_cr_retard.pack(side=tk.LEFT, padx=2)

        self.btn_cr_suivre = Bouton(f_pilules, "🟠 À suivre (7-15j)", "warning", lambda: self._filtrer_ancienneté("suivre"), petit=True, outline=True)
        self.btn_cr_suivre.pack(side=tk.LEFT, padx=2)

        self.btn_cr_recentes = Bouton(f_pilules, "🟢 Récentes (<7j)", "success", lambda: self._filtrer_ancienneté("recentes"), petit=True, outline=True)
        self.btn_cr_recentes.pack(side=tk.LEFT, padx=2)

        self.lbl_resume_creances = tk.Label(cf, text="", font=(POLICE, 9, "bold"),
                                            bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_resume_creances.pack(side=tk.RIGHT, padx=6)

        # --- Section 3 : Layout à 2 colonnes (Encours par client / Liste des factures) ---
        conteneur = tk.Frame(grille, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        # ── Colonne Gauche : Clients Débiteurs ──
        c1 = Carte(conteneur, "👥 Clients Débiteurs & Encours")
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        # Bouton Réinitialiser filtre client dans son propre frame (pack)
        f_btn_c1 = tk.Frame(c1.corps, bg=COULEURS["card"])
        f_btn_c1.pack(fill=tk.X, pady=(0, 6))
        Bouton(f_btn_c1, "🌐 Tous les clients", "secondary",
               self._reinitialiser_filtre_client, petit=True, outline=True).pack(anchor="w")

        # Frame dédié à la table client (grid via ajouter_scrollbars)
        f_tree_c1 = tk.Frame(c1.corps, bg=COULEURS["card"])
        f_tree_c1.pack(fill=tk.BOTH, expand=True)

        self.tab_creances_client = TableauTriable(f_tree_c1, [
            ("client", "Nom du Client", 150, "w", False),
            ("tel", "Téléphone", 100, "w", False),
            ("nb", "Fact.", 45, "center", True),
            ("du", "Total dû", 105, "e", True)], height=16)
        ajouter_scrollbars(f_tree_c1, self.tab_creances_client)
        self.tab_creances_client.bind("<<TreeviewSelect>>", lambda e: self._charger_creances_detail())

        # ── Colonne Droite : Factures Dues ──
        c2 = Carte(conteneur, "📄 Factures Non Soldées")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        # Frame dédié à la table des factures
        f_tree_c2 = tk.Frame(c2.corps, bg=COULEURS["card"])
        f_tree_c2.pack(fill=tk.BOTH, expand=True)

        self.tab_creances = TableauTriable(f_tree_c2, [
            ("num", "N° Facture", 120, "w", False),
            ("client", "Client", 145, "w", False),
            ("date", "Date Vente", 95, "w", False),
            ("ech", "Échéance", 90, "w", False),
            ("total", "Total Net", 95, "e", True),
            ("paye", "Déjà Payé", 95, "e", True),
            ("reste", "Reste Dû", 105, "e", True),
            ("age", "Jours", 55, "center", True),
            ("statut", "Statut", 90, "center", False)], height=16)
        ajouter_scrollbars(f_tree_c2, self.tab_creances)

        self.tab_creances.bind("<Double-1>", lambda e: self._encaisser_creance())
        self.root.bind("<F2>", lambda e: self._encaisser_creance())

        self.lbl_creances_info = tk.Label(
            c2.corps, text="💡 Double-cliquez sur une facture (ou touche F2) pour encaisser un acompte.",
            font=(POLICE, 9, "italic"), bg=COULEURS["card"], fg=COULEURS["text_secondary"])
        self.lbl_creances_info.pack(anchor="w", pady=(6, 0))

        self._charger_creances()

    def _filtrer_ancienneté(self, statut: str):
        self._filtre_statut_creance = statut
        self.btn_cr_toutes.configure(bg=COULEURS["primary"] if statut == "toutes" else COULEURS["card"], fg="white" if statut == "toutes" else COULEURS["primary"])
        self.btn_cr_retard.configure(bg=COULEURS["danger"] if statut == "retard" else COULEURS["card"], fg="white" if statut == "retard" else COULEURS["danger"])
        self.btn_cr_suivre.configure(bg=COULEURS["warning"] if statut == "suivre" else COULEURS["card"], fg="white" if statut == "suivre" else COULEURS["warning"])
        self.btn_cr_recentes.configure(bg=COULEURS["success"] if statut == "recentes" else COULEURS["card"], fg="white" if statut == "recentes" else COULEURS["success"])
        self._charger_creances_detail()

    def _reinitialiser_filtre_client(self):
        if hasattr(self, 'tab_creances_client'):
            self.tab_creances_client.selection_remove(self.tab_creances_client.selection())
        self._charger_creances_detail()

    def _kpis_creances(self, kpi: dict):
        for w in self.cadre_kpi_creance.winfo_children():
            w.destroy()

        self.cadre_kpi_creance.columnconfigure(0, weight=1)
        self.cadre_kpi_creance.columnconfigure(1, weight=1)
        self.cadre_kpi_creance.columnconfigure(2, weight=1)
        self.cadre_kpi_creance.columnconfigure(3, weight=1)

        seuil = int(parse_float(self.params.get("alerte_creance_jours", 15), 15))

        kpis_data = [
            ("💳", fmt_money(kpi["creances_total"], self.devise), f"{int(kpi['creances_nb'])} facture(s) en cours", COULEURS["warning"]),
            ("⚠️", fmt_money(kpi["creances_retard"], self.devise), f"Retard (> {seuil} j) : {int(kpi['creances_nb_retard'])} factures", COULEURS["danger"]),
            ("👥", f"{int(kpi.get('nb_clients_debiteurs', kpi['creances_nb']))} client(s)", "Portefeuille débiteurs", COULEURS["primary"]),
            ("💰", fmt_money(kpi.get("reglements_mois", 0), self.devise), "Encaissements reçus ce mois", COULEURS["success"]),
        ]

        for i, (icone, val, label, coul) in enumerate(kpis_data):
            k = KPI(self.cadre_kpi_creance, icone, val, label, couleur=coul)
            k.grid(row=0, column=i, sticky="ew", padx=4)

    def _charger_creances(self):
        kpi = m3.kpi_v3()
        # Nombre de clients débiteurs
        clients_creances = m3.get_creances_par_client()
        kpi["nb_clients_debiteurs"] = len(clients_creances)

        # Calculer encaissements du mois
        conn = db.get_connection()
        m_start = datetime.now().strftime("%Y-%m-01 00:00:00")
        row_m = conn.execute("SELECT COALESCE(SUM(montant),0) FROM reglements WHERE sens='encaissement' AND date_reglement >= ?", (m_start,)).fetchone()
        kpi["reglements_mois"] = float(row_m[0]) if row_m else 0.0

        self._kpis_creances(kpi)

        # Charger la liste des clients à gauche
        t1 = self.tab_creances_client
        t1.delete(*t1.get_children())
        seuil = int(parse_float(self.params.get("alerte_creance_jours", 15), 15))
        recherche = self.rech_creances.get().strip().lower() if hasattr(self, 'rech_creances') else ""

        for i, c in enumerate(clients_creances):
            nom_c = str(c.get("client_nom", "")).lower()
            tel_c = str(c.get("telephone", "")).lower()
            if recherche and (recherche not in nom_c and recherche not in tel_c):
                continue

            retard = (c.get("plus_ancienne_jours") or 0) >= seuil
            t1.insert("", tk.END, iid=str(c["client_id"]),
                      tags=zebre(i, ("alerte",) if retard else ()),
                      values=(c["client_nom"], c.get("telephone") or "—", c["nb_factures"],
                              fmt_money(c["total_du"])))

        self._charger_creances_detail()

    def _charger_creances_detail(self):
        if not hasattr(self, 'tab_creances') or not hasattr(self, 'tab_creances_client'):
            return
        sel = self.tab_creances_client.selection()
        client_id = int(sel[0]) if sel and sel[0].isdigit() and int(sel[0]) > 0 else None
        creances = m3.get_creances(client_id=client_id)
        seuil = int(parse_float(self.params.get("alerte_creance_jours", 15), 15))

        recherche = self.rech_creances.get().strip().lower() if hasattr(self, 'rech_creances') else ""
        t = self.tab_creances
        t.delete(*t.get_children())
        total_du_filtre = 0.0
        count = 0

        for i, c in enumerate(creances):
            num = str(c.get("numero") or "").lower()
            cli = str(c.get("client_nom") or "").lower()
            if recherche and (recherche not in num and recherche not in cli):
                continue

            j = int(c.get("anciennete_jours") or 0)

            # Filtre par pilules d'état
            if self._filtre_statut_creance == "retard" and j < seuil:
                continue
            if self._filtre_statut_creance == "suivre" and (j < 7 or j >= seuil):
                continue
            if self._filtre_statut_creance == "recentes" and j >= 7:
                continue

            count += 1
            total_du_filtre += c["reste_du"]

            if j >= seuil:
                statut_label, tags = "🔴 Retard", ("rupture",)
            elif j >= 7:
                statut_label, tags = "🟠 À suivre", ("alerte",)
            else:
                statut_label, tags = "🟢 Récent", ()

            t.insert("", tk.END, iid=c["vente_id"],
                      tags=zebre(i, tags),
                      values=(c["numero"] or f"#{c['vente_id']}", c["client_nom"],
                              fmt_date(c["date_vente"], False),
                              c.get("date_echeance") or "—",
                              fmt_money(c["total"]), fmt_money(c["total_paye"]),
                              fmt_money(c["reste_du"]), j, statut_label))

        self.lbl_creances_info.configure(
            text=f"{count} facture(s) affichée(s)  ·  Reste dû total : {fmt_money(total_du_filtre, self.devise)}")

    def _encaisser_creance(self):
        sel = self.tab_creances.selection()
        if not sel:
            messagebox.showinfo("Encaissement", "Sélectionnez une facture à encaisser dans le tableau.", parent=self.root)
            return
        vente_id = int(sel[0])
        creances_all = m3.get_creances()
        creance = next((c for c in creances_all if c["vente_id"] == vente_id), None)
        if not creance:
            messagebox.showinfo("Information", "Cette facture est déjà entièrement soldée.", parent=self.root)
            self._charger_creances()
            return

        d = DemanderMontant(
            self.root, "💰 Encaisser un acompte / solde",
            f"Facture : {creance['numero']}  ·  Client : {creance['client_nom']}\n\n"
            f"Total Facture : {fmt_money(creance['total'], self.devise)}\n"
            f"Déjà Réglé : {fmt_money(creance['total_paye'], self.devise)}\n"
            f"Reste à Payer : {fmt_money(creance['reste_du'], self.devise)}",
            montant_max=creance["reste_du"])

        if not d.resultat:
            return

        montant, mode, ref = d.resultat
        ok, msg = m3.encaisser_creance(vente_id, montant, mode, ref)

        if ok:
            self.statut(f"✅ {msg}", COULEURS["success"])
            if messagebox.askyesno("Reçu de Règlement", f"{msg}\n\nSouhaitez-vous générer le bon d'encaissement / reçu de règlement ?", parent=self.root):
                try:
                    ok_p, res_p = factures.imprimer_facture(vente_id)
                    if ok_p:
                        self.statut("Reçu de règlement généré", COULEURS["success"])
                except Exception as exc:
                    messagebox.showerror("Reçu", f"Erreur lors de l'impression : {exc}", parent=self.root)
            self.afficher_creances()
        else:
            messagebox.showerror("Encaissement impossible", msg, parent=self.root)

    def _voir_historique_reglements(self):
        top = tk.Toplevel(self.root)
        top.title("📜 Historique des Règlements & Acomptes Encaissés")
        top.geometry("820x520")
        top.configure(bg=COULEURS["bg"])
        top.transient(self.root)

        tk.Label(top, text="📜 Historique des règlements encaissés", font=(POLICE, 12, "bold"),
                 bg=COULEURS["bg"], fg=COULEURS["primary"]).pack(anchor="w", padx=16, pady=12)

        cadre = tk.Frame(top, bg=COULEURS["card"])
        cadre.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        tab_reg = TableauTriable(cadre, [
            ("date", "Date Règlement", 120, "w", False),
            ("num", "Facture", 120, "w", False),
            ("client", "Client", 160, "w", False),
            ("montant", "Montant Encaissé", 120, "e", True),
            ("mode", "Mode", 100, "w", False),
            ("ref", "Référence Doc", 100, "w", False),
            ("user", "Caissier", 90, "w", False)
        ])
        ajouter_scrollbars(cadre, tab_reg)

        reglements = m3.get_reglements(limit=300)
        conn = db.get_connection()

        for i, r in enumerate(reglements):
            c_name = "Client"
            if r.get("client_id"):
                cli = conn.execute("SELECT nom FROM clients WHERE id=?", (r["client_id"],)).fetchone()
                if cli:
                    c_name = cli[0]

            v_num = "—"
            if r.get("vente_id"):
                v = conn.execute("SELECT numero FROM ventes WHERE id=?", (r["vente_id"],)).fetchone()
                if v:
                    v_num = v[0]

            tab_reg.insert("", tk.END, iid=r["id"], tags=zebre(i), values=(
                fmt_date(r["date_reglement"], True),
                v_num,
                c_name,
                fmt_money(r["montant"], self.devise),
                r.get("mode_paiement") or "Espèces",
                r.get("reference_doc") or "—",
                r.get("utilisateur") or "—"
            ))

    def _imprimer_creances(self):
        seuil = int(parse_float(self.params.get("alerte_creance_jours", 15), 15))
        retards = m3.get_creances(seuil_jours=seuil)
        if not retards:
            messagebox.showinfo("Aucune relance",
                                f"Aucune facture en retard de plus de {seuil} jours.", parent=self.root)
            return
        lignes = [[c["numero"], c["client_nom"], fmt_date(c["date_vente"], False),
                   c.get("date_echeance") or "", f"{c['total']:.0f}",
                   f"{c['total_paye']:.0f}", f"{c['reste_du']:.0f}",
                   int(c.get("anciennete_jours") or 0)] for c in retards]
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
