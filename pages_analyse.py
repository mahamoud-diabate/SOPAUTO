"""
SODIPAC — Écran « Analyse commerciale »
=======================================

Mixin regroupant 4 onglets qui répondent aux questions que se pose un
patron de boutique de pièces auto :

  1. 💰 Prix pratiqués  — est-ce qu'on brade ou est-ce qu'on majore ?
  2. 📊 Tendances       — qu'est-ce qui monte, qu'est-ce qui décroche ?
  3. 🚨 Alertes         — qu'est-ce que je dois traiter aujourd'hui ?
  4. 👥 Qui négocie     — quel vendeur brade, quel client obtient les remises ?

Tous les graphiques sont des COURBES linéaires (préférence utilisateur).
"""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import analyse_prix as ap
import database as db
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, TableauTriable,
                        ajouter_scrollbars, fmt_date, fmt_money, zebre)

# Périodes proposées partout dans l'écran
PERIODES = [("7 jours", 7), ("30 jours", 30), ("90 jours", 90),
            ("6 mois", 180), ("1 an", 365)]


class PageAnalyse:
    """Mixin ajouté à Application : l'écran d'analyse commerciale."""

    # ═══════════════════════════════════════════════════
    #  Page principale
    # ═══════════════════════════════════════════════════

    def afficher_analyse(self):
        if not self.peut("rapports"):
            return self._refus()
        self._nouvelle_page("💰 Analyse commerciale — prix et tendances",
                            self._idx_menu("Analyse"))

        onglets = ttk.Notebook(self.zone)
        onglets.pack(fill=tk.BOTH, expand=True)

        self._onglet_prix(onglets)
        self._onglet_tendances(onglets)
        self._onglet_alertes(onglets)
        self._onglet_negociation(onglets)

    # ── Petit utilitaire : sélecteur de période ──
    def _selecteur_periode(self, parent, variable, callback, defaut=90):
        cadre = tk.Frame(parent, bg=parent["bg"])
        tk.Label(cadre, text="Période :", font=(POLICE, 9),
                 bg=parent["bg"], fg=COULEURS["text"]).pack(side=tk.LEFT)
        combo = ttk.Combobox(cadre, state="readonly", width=11, font=(POLICE, 9),
                             values=[libelle for libelle, _ in PERIODES])
        index = next((i for i, (_, j) in enumerate(PERIODES) if j == defaut), 2)
        combo.current(index)
        combo.pack(side=tk.LEFT, padx=(4, 12))
        combo.bind("<<ComboboxSelected>>", lambda e: callback())
        setattr(self, variable, combo)
        return cadre

    def _jours_de(self, attribut, defaut=90):
        combo = getattr(self, attribut, None)
        if combo is None:
            return defaut
        libelle = combo.get()
        return next((j for lib, j in PERIODES if lib == libelle), defaut)

    # ═══════════════════════════════════════════════════
    #  ONGLET 1 — PRIX PRATIQUÉS
    # ═══════════════════════════════════════════════════

    def _onglet_prix(self, parent):
        page = tk.Frame(parent, bg=COULEURS["bg"], padx=12, pady=12)
        parent.add(page, text="  💰 Prix pratiqués  ")

        barre = tk.Frame(page, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        self._selecteur_periode(barre, "cb_periode_prix",
                                self._charger_prix).pack(side=tk.LEFT)

        tk.Label(barre, text="Afficher :", font=(POLICE, 9),
                 bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.cb_filtre_prix = ttk.Combobox(
            barre, state="readonly", width=20, font=(POLICE, 9),
            values=["Tout", "Bradés (sous le prix)", "Majorés (sur le prix)",
                    "Vendus au prix", "⚠ Ventes à perte"])
        self.cb_filtre_prix.current(0)
        self.cb_filtre_prix.pack(side=tk.LEFT, padx=(4, 12))
        self.cb_filtre_prix.bind("<<ComboboxSelected>>", lambda e: self._charger_prix())

        Bouton(barre, "💡 Prix conseillé", "primary", self._voir_prix_conseille,
               petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(barre, "📜 Historique", "info", self._voir_historique_prix,
               petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(barre, "📤 Exporter", "secondary", self._exporter_prix,
               petit=True).pack(side=tk.LEFT, padx=3)

        # ── Verdict global : la phrase qui résume tout ──
        self.cadre_verdict = tk.Frame(page, bg=COULEURS["card"], padx=16, pady=12,
                                      highlightbackground=COULEURS["border"],
                                      highlightthickness=1)
        self.cadre_verdict.pack(fill=tk.X, pady=(0, 8))
        self.lbl_verdict = tk.Label(self.cadre_verdict, text="", font=(POLICE, 12, "bold"),
                                    bg=COULEURS["card"], fg=COULEURS["text"],
                                    justify="left", wraplength=1100, anchor="w")
        self.lbl_verdict.pack(anchor="w")
        self.lbl_verdict_detail = tk.Label(self.cadre_verdict, text="", font=(POLICE, 9),
                                           bg=COULEURS["card"],
                                           fg=COULEURS["text_secondary"],
                                           justify="left", anchor="w")
        self.lbl_verdict_detail.pack(anchor="w", pady=(6, 0))

        # ── KPI ──
        self.zone_kpi_prix = tk.Frame(page, bg=COULEURS["bg"])
        self.zone_kpi_prix.pack(fill=tk.X, pady=(0, 8))

        # ── Tableau ──
        cadre = Carte(page, "Détail par produit — trié par impact financier")
        cadre.pack(fill=tk.BOTH, expand=True)
        zone_tab = tk.Frame(cadre.corps, bg=COULEURS["card"])
        zone_tab.pack(fill=tk.BOTH, expand=True)
        self.tab_prix = TableauTriable(zone_tab, [
            ("tend", "Tendance", 105, "center", False),
            ("ref", "Référence", 105, "w", False),
            ("nom", "Produit", 200, "w", False),
            ("cat", "Catégorie", 115, "w", False),
            ("catalogue", "Prix affiché", 100, "e", True),
            ("moyen", "Prix réel moyen", 115, "e", True),
            ("mini", "Mini", 85, "e", True),
            ("maxi", "Maxi", 85, "e", True),
            ("ecart", "Écart %", 75, "center", True),
            ("nb", "Ventes", 60, "center", True),
            ("taux", "% remisé", 75, "center", True),
            ("impact", "Impact total", 110, "e", True),
            ("marge", "Marge réelle", 95, "center", True),
            ("theo", "Marge affichée", 100, "center", True)])
        ajouter_scrollbars(zone_tab, self.tab_prix)
        self.tab_prix.bind("<Double-1>", lambda e: self._voir_historique_prix())

        self.lbl_prix_info = tk.Label(
            cadre.corps, text="Double-cliquez sur un produit pour voir "
                              "l'historique de ses prix de vente.",
            font=(POLICE, 9), bg=COULEURS["card"], fg=COULEURS["text_secondary"])
        self.lbl_prix_info.pack(anchor="w", pady=(6, 0))

        self._charger_prix()

    def _charger_prix(self):
        jours = self._jours_de("cb_periode_prix")
        synthese = ap.synthese_prix_global(jours)
        self._analyse_prix_courante = ap.analyse_prix_pratiques(jours)

        # ── Verdict ──
        couleurs_tendance = {"remise": COULEURS["danger"],
                             "majoration": COULEURS["success"],
                             "au prix": COULEURS["info"]}
        icones = {"remise": "📉", "majoration": "📈", "au prix": "✅"}
        tend = synthese["tendance"]
        self.lbl_verdict.configure(
            text=f"{icones.get(tend, 'ℹ️')}  {synthese['verdict']}",
            fg=couleurs_tendance.get(tend, COULEURS["text"]))
        if synthese["nb_lignes"]:
            self.lbl_verdict_detail.configure(
                text=f"{synthese['nb_lignes']} ligne(s) de vente analysée(s) sur "
                     f"{synthese['nb_produits']} produit(s) · "
                     f"{synthese['taux_negociation_pct']:.0f} % des lignes ont été "
                     f"négociées ({synthese['lignes_sous']} sous le prix, "
                     f"{synthese['lignes_sur']} au-dessus, "
                     f"{synthese['lignes_au_prix']} au prix affiché)")
        else:
            self.lbl_verdict_detail.configure(text="")

        # ── KPI ──
        for w in self.zone_kpi_prix.winfo_children():
            w.destroy()
        impact = synthese["impact_total"]
        cartes = [
            ("CA encaissé", fmt_money(synthese["ca_reel"], self.devise),
             COULEURS["primary"], "ce que vous avez réellement reçu"),
            ("CA si prix affichés", fmt_money(synthese["ca_theorique"], self.devise),
             COULEURS["secondary"], "sans aucune négociation"),
            ("Manque à gagner" if impact < 0 else "Bonus négociation",
             fmt_money(abs(impact), self.devise),
             COULEURS["danger"] if impact < 0 else COULEURS["success"],
             f"{synthese['impact_pct']:+.1f} % vs prix affichés"),
            ("Marge réelle", f"{synthese['marge_reelle_pct']:.1f} %",
             COULEURS["warning"],
             f"au lieu de {synthese['marge_theorique_pct']:.1f} % affichée"),
            ("Ventes à perte", str(int(synthese["nb_alertes_sous_cout"])),
             COULEURS["danger"] if synthese["nb_alertes_sous_cout"] else COULEURS["success"],
             "sous le coût"),
        ]
        for titre, valeur, couleur, sous in cartes:
            c = tk.Frame(self.zone_kpi_prix, bg=COULEURS["card"], padx=14, pady=10,
                         highlightbackground=COULEURS["border"], highlightthickness=1)
            c.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
            tk.Label(c, text=titre, font=(POLICE, 8), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"], anchor="w").pack(anchor="w", fill=tk.X)
            tk.Label(c, text=valeur, font=(POLICE, 15, "bold"), bg=COULEURS["card"],
                     fg=couleur, anchor="w").pack(anchor="w", fill=tk.X)
            tk.Label(c, text=sous, font=(POLICE, 7), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"], anchor="w",
                     wraplength=190, justify="left").pack(anchor="w", fill=tk.X)

        # ── Filtrage ──
        filtre = self.cb_filtre_prix.get()
        donnees = self._analyse_prix_courante
        if filtre.startswith("Bradés"):
            donnees = [p for p in donnees if p["tendance"] == "remise"]
        elif filtre.startswith("Majorés"):
            donnees = [p for p in donnees if p["tendance"] == "majoration"]
        elif filtre.startswith("Vendus"):
            donnees = [p for p in donnees if p["tendance"] == "au prix"]
        elif "perte" in filtre:
            donnees = [p for p in donnees if p["nb_sous_cout"]]

        libelles = {"remise": "📉 Bradé", "majoration": "📈 Majoré",
                    "au prix": "✅ Au prix"}
        t = self.tab_prix
        t.delete(*t.get_children())
        for i, p in enumerate(donnees):
            if p["nb_sous_cout"]:
                tags = ("rupture",)
            elif p["tendance"] == "remise" and p["ecart_pct"] <= -10:
                tags = ("alerte",)
            else:
                tags = ()
            t.insert("", tk.END, iid=p["produit_id"], tags=zebre(i, tags), values=(
                libelles.get(p["tendance"], p["tendance"]),
                p["reference"], p["nom"], p["categorie_nom"],
                fmt_money(p["prix_catalogue"]), fmt_money(p["prix_moyen"]),
                fmt_money(p["prix_min"]), fmt_money(p["prix_max"]),
                f"{p['ecart_pct']:+.1f} %", p["nb_lignes"],
                f"{p['taux_remise_pct']:.0f} %",
                fmt_money(p["impact_total"]),
                f"{p['marge_reelle_pct']:.1f} %",
                f"{p['marge_theorique_pct']:.1f} %"))
        self.lbl_prix_info.configure(
            text=f"{len(donnees)} produit(s) affiché(s) · double-clic = historique "
                 f"des prix · 🔴 vente à perte · 🟠 remise de plus de 10 %")

    def _produit_prix_selectionne(self):
        sel = self.tab_prix.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez un produit.",
                                parent=self.root)
            return None
        return int(sel[0])

    def _voir_prix_conseille(self):
        pid = self._produit_prix_selectionne()
        if pid is None:
            return
        jours = self._jours_de("cb_periode_prix")
        conseil = ap.prix_conseille(pid, jours)
        if not conseil["possible"]:
            messagebox.showinfo("Prix conseillé", conseil["message"], parent=self.root)
            return
        DialoguePrixConseille(self.root, pid, conseil, self.devise, self)

    def _voir_historique_prix(self):
        pid = self._produit_prix_selectionne()
        if pid is None:
            return
        DialogueHistoriquePrix(self.root, pid, self.devise)

    def _exporter_prix(self):
        chemin = ap.exporter_analyse_prix(self._jours_de("cb_periode_prix"))
        self._proposer_ouverture(chemin)

    # ═══════════════════════════════════════════════════
    #  ONGLET 2 — TENDANCES
    # ═══════════════════════════════════════════════════

    def _onglet_tendances(self, parent):
        page = tk.Frame(parent, bg=COULEURS["bg"], padx=12, pady=12)
        parent.add(page, text="  📊 Tendances de vente  ")

        barre = tk.Frame(page, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        tk.Label(barre, text="Comparer les", font=(POLICE, 9),
                 bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.cb_fenetre_tend = ttk.Combobox(
            barre, state="readonly", width=11, font=(POLICE, 9),
            values=["7 jours", "14 jours", "30 jours", "60 jours", "90 jours"])
        self.cb_fenetre_tend.current(2)
        self.cb_fenetre_tend.pack(side=tk.LEFT, padx=4)
        self.cb_fenetre_tend.bind("<<ComboboxSelected>>", lambda e: self._charger_tendances())
        tk.Label(barre, text="aux mêmes jours de la période précédente",
                 font=(POLICE, 9), bg=COULEURS["bg"],
                 fg=COULEURS["text_secondary"]).pack(side=tk.LEFT, padx=(4, 14))

        tk.Label(barre, text="Afficher :", font=(POLICE, 9),
                 bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.cb_filtre_tend = ttk.Combobox(
            barre, state="readonly", width=22, font=(POLICE, 9),
            values=["Tout", "📉 En baisse seulement", "📈 En hausse seulement",
                    "⛔ Ne se vendent plus", "🆕 Nouveaux"])
        self.cb_filtre_tend.current(0)
        self.cb_filtre_tend.pack(side=tk.LEFT, padx=(4, 12))
        self.cb_filtre_tend.bind("<<ComboboxSelected>>", lambda e: self._charger_tendances())

        Bouton(barre, "📤 Exporter", "secondary", self._exporter_tendances,
               petit=True).pack(side=tk.LEFT, padx=3)

        # ── Courbe du CA (linéaire) ──
        graphe = Carte(page, "Évolution du chiffre d'affaires (30 derniers jours)")
        graphe.pack(fill=tk.X, pady=(0, 8))
        try:
            stats = db.get_dashboard_stats()
            self._dessiner_graphe(graphe.corps, stats.get("ventes_30j", []),
                                  jours_affiches=30, titre_court=False)
        except Exception:
            tk.Label(graphe.corps, text="Graphique indisponible", font=(POLICE, 9),
                     bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack()

        self.zone_kpi_tend = tk.Frame(page, bg=COULEURS["bg"])
        self.zone_kpi_tend.pack(fill=tk.X, pady=(0, 8))

        cadre = Carte(page, "Produits — évolution des quantités vendues")
        cadre.pack(fill=tk.BOTH, expand=True)
        zone_tab = tk.Frame(cadre.corps, bg=COULEURS["card"])
        zone_tab.pack(fill=tk.BOTH, expand=True)
        self.tab_tendances = TableauTriable(zone_tab, [
            ("tend", "Tendance", 125, "center", False),
            ("ref", "Référence", 105, "w", False),
            ("nom", "Produit", 210, "w", False),
            ("cat", "Catégorie", 120, "w", False),
            ("avant", "Avant", 65, "center", True),
            ("apres", "Maintenant", 85, "center", True),
            ("var", "Variation", 85, "center", True),
            ("varpct", "Variation %", 95, "center", True),
            ("ca_av", "CA avant", 100, "e", True),
            ("ca_ap", "CA maintenant", 110, "e", True),
            ("stock", "Stock", 60, "center", True),
            ("capital", "Capital immobilisé", 130, "e", True),
            ("derniere", "Dernière vente", 110, "w", False)])
        ajouter_scrollbars(zone_tab, self.tab_tendances)

        self.lbl_tend_info = tk.Label(cadre.corps, text="", font=(POLICE, 9),
                                      bg=COULEURS["card"],
                                      fg=COULEURS["text_secondary"])
        self.lbl_tend_info.pack(anchor="w", pady=(6, 0))

        self._charger_tendances()

    def _charger_tendances(self):
        fenetre = int(self.cb_fenetre_tend.get().split()[0])
        tous = ap.tendances_ventes(fenetre)
        self._tendances_courantes = tous

        # ── KPI ──
        for w in self.zone_kpi_tend.winfo_children():
            w.destroy()
        compte = {}
        for t in tous:
            compte[t["tendance"]] = compte.get(t["tendance"], 0) + 1
        capital_declin = sum(t["capital_immobilise"] for t in tous
                             if t["tendance"] in ("baisse", "forte_baisse", "arrete"))
        cartes = [
            ("🚀 Forte hausse", compte.get("forte_hausse", 0), COULEURS["success"],
             "+50 % ou plus"),
            ("📈 En hausse", compte.get("hausse", 0), COULEURS["success"], "+15 à 50 %"),
            ("➡️ Stables", compte.get("stable", 0), COULEURS["info"], "±15 %"),
            ("↘️ En baisse", compte.get("baisse", 0), COULEURS["warning"], "−15 à −50 %"),
            ("📉 Forte baisse", compte.get("forte_baisse", 0), COULEURS["danger"],
             "−50 % ou pire"),
            ("⛔ Arrêtés", compte.get("arrete", 0), COULEURS["danger"],
             "plus aucune vente"),
        ]
        for titre, valeur, couleur, sous in cartes:
            c = tk.Frame(self.zone_kpi_tend, bg=COULEURS["card"], padx=12, pady=10,
                         highlightbackground=COULEURS["border"], highlightthickness=1)
            c.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            tk.Label(c, text=titre, font=(POLICE, 8), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).pack(anchor="w")
            tk.Label(c, text=str(valeur), font=(POLICE, 17, "bold"),
                     bg=COULEURS["card"], fg=couleur).pack(anchor="w")
            tk.Label(c, text=sous, font=(POLICE, 7), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).pack(anchor="w")

        # ── Filtrage ──
        filtre = self.cb_filtre_tend.get()
        donnees = tous
        if "baisse" in filtre:
            donnees = [t for t in tous if t["tendance"] in ("baisse", "forte_baisse")]
        elif "hausse" in filtre:
            donnees = [t for t in tous if t["tendance"] in ("hausse", "forte_hausse")]
        elif "plus" in filtre:
            donnees = [t for t in tous if t["tendance"] == "arrete"]
        elif "Nouveaux" in filtre:
            donnees = [t for t in tous if t["tendance"] == "nouveau"]

        t = self.tab_tendances
        t.delete(*t.get_children())
        for i, d in enumerate(donnees):
            if d["tendance"] in ("forte_baisse", "arrete"):
                tags = ("rupture",)
            elif d["tendance"] == "baisse":
                tags = ("alerte",)
            else:
                tags = ()
            t.insert("", tk.END, iid=d["produit_id"], tags=zebre(i, tags), values=(
                d["libelle"], d["reference"], d["nom"], d["categorie_nom"],
                d["qte_precedente"], d["qte_recente"],
                f"{d['variation_qte']:+d}", f"{d['variation_qte_pct']:+.0f} %",
                fmt_money(d["ca_precedent"]), fmt_money(d["ca_recent"]),
                d["stock"], fmt_money(d["capital_immobilise"]),
                fmt_date(d["derniere_vente"], False) if d["derniere_vente"] else "jamais"))

        self.lbl_tend_info.configure(
            text=f"{len(donnees)} produit(s) affiché(s) · "
                 f"capital immobilisé sur les produits en baisse : "
                 f"{fmt_money(capital_declin, self.devise)}")

    def _exporter_tendances(self):
        fenetre = int(self.cb_fenetre_tend.get().split()[0])
        chemin = ap.exporter_tendances(fenetre)
        self._proposer_ouverture(chemin)

    # ═══════════════════════════════════════════════════
    #  ONGLET 3 — ALERTES
    # ═══════════════════════════════════════════════════

    def _onglet_alertes(self, parent):
        page = tk.Frame(parent, bg=COULEURS["bg"], padx=12, pady=12)
        parent.add(page, text="  🚨 Alertes commerciales  ")

        barre = tk.Frame(page, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        tk.Label(barre, text="Ce qu'il faut regarder aujourd'hui, "
                             "du plus grave au moins urgent.",
                 font=(POLICE, 10, "bold"), bg=COULEURS["bg"],
                 fg=COULEURS["text"]).pack(side=tk.LEFT)
        Bouton(barre, "🔄 Actualiser", "secondary", self._charger_alertes,
               petit=True).pack(side=tk.RIGHT, padx=3)
        Bouton(barre, "📦 Voir le produit", "info", self._alerte_vers_produit,
               petit=True).pack(side=tk.RIGHT, padx=3)

        self.zone_kpi_alertes = tk.Frame(page, bg=COULEURS["bg"])
        self.zone_kpi_alertes.pack(fill=tk.X, pady=(0, 8))

        cadre = Carte(page, "Alertes")
        cadre.pack(fill=tk.BOTH, expand=True)
        zone_tab = tk.Frame(cadre.corps, bg=COULEURS["card"])
        zone_tab.pack(fill=tk.BOTH, expand=True)
        self.tab_alertes = TableauTriable(zone_tab, [
            ("niveau", "Gravité", 95, "center", False),
            ("cat", "Type", 185, "w", False),
            ("titre", "Produit / situation", 320, "w", False),
            ("detail", "Explication", 520, "w", False)])
        ajouter_scrollbars(zone_tab, self.tab_alertes)

        self.lbl_alertes_info = tk.Label(cadre.corps, text="", font=(POLICE, 9),
                                         bg=COULEURS["card"],
                                         fg=COULEURS["text_secondary"])
        self.lbl_alertes_info.pack(anchor="w", pady=(6, 0))

        self._charger_alertes()

    def _charger_alertes(self):
        alertes = ap.alertes_commerciales(30)
        self._alertes_courantes = alertes

        for w in self.zone_kpi_alertes.winfo_children():
            w.destroy()
        compte = {}
        for a in alertes:
            compte[a["niveau"]] = compte.get(a["niveau"], 0) + 1
        cartes = [
            ("🔴 Critique", compte.get("critique", 0), COULEURS["danger"],
             "vous perdez de l'argent"),
            ("🟠 Haute", compte.get("haute", 0), COULEURS["warning"],
             "à traiter cette semaine"),
            ("🟡 Moyenne", compte.get("moyenne", 0), COULEURS["info"],
             "à surveiller"),
            ("🔵 Information", compte.get("info", 0), COULEURS["secondary"],
             "opportunités"),
        ]
        for titre, valeur, couleur, sous in cartes:
            c = tk.Frame(self.zone_kpi_alertes, bg=COULEURS["card"], padx=16, pady=12,
                         highlightbackground=COULEURS["border"], highlightthickness=1)
            c.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
            tk.Label(c, text=titre, font=(POLICE, 9), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).pack(anchor="w")
            tk.Label(c, text=str(valeur), font=(POLICE, 19, "bold"),
                     bg=COULEURS["card"], fg=couleur).pack(anchor="w")
            tk.Label(c, text=sous, font=(POLICE, 8), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).pack(anchor="w")

        niveaux = {"critique": "🔴 Critique", "haute": "🟠 Haute",
                   "moyenne": "🟡 Moyenne", "info": "🔵 Info"}
        t = self.tab_alertes
        t.delete(*t.get_children())
        for i, a in enumerate(alertes):
            tags = ("rupture",) if a["niveau"] == "critique" else (
                ("alerte",) if a["niveau"] == "haute" else ())
            t.insert("", tk.END, iid=str(i), tags=zebre(i, tags), values=(
                niveaux.get(a["niveau"], a["niveau"]), a["categorie"],
                a["titre"], a["detail"].replace("\n", " ")))

        if not alertes:
            self.lbl_alertes_info.configure(
                text="✅ Aucune alerte : vos prix et vos ventes sont sains.")
        else:
            self.lbl_alertes_info.configure(
                text=f"{len(alertes)} alerte(s) · sélectionnez une ligne puis "
                     f"« Voir le produit » pour agir dessus")

    def _alerte_vers_produit(self):
        sel = self.tab_alertes.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez une alerte.",
                                parent=self.root)
            return
        alertes = getattr(self, "_alertes_courantes", [])
        index = int(sel[0])
        if index >= len(alertes):
            return
        pid = alertes[index].get("produit_id")
        if not pid:
            messagebox.showinfo("Information",
                                "Cette alerte ne cible pas un produit précis.",
                                parent=self.root)
            return
        DialogueHistoriquePrix(self.root, pid, self.devise)

    # ═══════════════════════════════════════════════════
    #  ONGLET 4 — QUI NÉGOCIE
    # ═══════════════════════════════════════════════════

    def _onglet_negociation(self, parent):
        page = tk.Frame(parent, bg=COULEURS["bg"], padx=12, pady=12)
        parent.add(page, text="  👥 Qui négocie  ")

        barre = tk.Frame(page, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        self._selecteur_periode(barre, "cb_periode_nego",
                                self._charger_negociation).pack(side=tk.LEFT)
        tk.Label(barre, text="Un écart négatif = tendance à accorder des remises.",
                 font=(POLICE, 9), bg=COULEURS["bg"],
                 fg=COULEURS["text_secondary"]).pack(side=tk.LEFT, padx=8)

        conteneur = tk.Frame(page, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        c1 = Carte(conteneur, "Par vendeur — qui tient les prix ?")
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self.tab_nego_vendeur = TableauTriable(c1.corps, [
            ("vendeur", "Vendeur", 135, "w", False),
            ("tend", "Tendance", 100, "center", False),
            ("nb", "Lignes", 60, "center", True),
            ("ca", "CA encaissé", 110, "e", True),
            ("theo", "CA affiché", 110, "e", True),
            ("ecart", "Écart %", 80, "center", True),
            ("impact", "Impact", 105, "e", True),
            ("taux", "% remisé", 80, "center", True),
            ("marge", "Marge %", 75, "center", True)], height=15)
        self.tab_nego_vendeur.pack(fill=tk.BOTH, expand=True)

        c2 = Carte(conteneur, "Par client — qui obtient les meilleurs prix ?")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self.tab_nego_client = TableauTriable(c2.corps, [
            ("client", "Client", 155, "w", False),
            ("type", "Type", 90, "w", False),
            ("tend", "Tendance", 100, "center", False),
            ("nb", "Lignes", 60, "center", True),
            ("ca", "CA encaissé", 110, "e", True),
            ("remise", "Remise moy.", 100, "center", True),
            ("impact", "Impact", 105, "e", True),
            ("marge", "Marge %", 75, "center", True)], height=15)
        self.tab_nego_client.pack(fill=tk.BOTH, expand=True)

        self.lbl_nego_info = tk.Label(page, text="", font=(POLICE, 9),
                                      bg=COULEURS["bg"],
                                      fg=COULEURS["text_secondary"])
        self.lbl_nego_info.pack(anchor="w", pady=(8, 0))

        self._charger_negociation()

    def _charger_negociation(self):
        jours = self._jours_de("cb_periode_nego")
        libelles = {"remise": "📉 Brade", "majoration": "📈 Majore",
                    "au prix": "✅ Au prix"}

        vendeurs = ap.analyse_prix_par_vendeur(jours)
        t = self.tab_nego_vendeur
        t.delete(*t.get_children())
        for i, v in enumerate(vendeurs):
            tags = ("alerte",) if v["ecart_pct"] <= -10 else (
                ("rupture",) if v["nb_sous_cout"] else ())
            t.insert("", tk.END, tags=zebre(i, tags), values=(
                v["vendeur"], libelles.get(v["tendance"], v["tendance"]),
                v["nb_lignes"], fmt_money(v["ca_reel"]), fmt_money(v["ca_theorique"]),
                f"{v['ecart_pct']:+.1f} %", fmt_money(v["impact_total"]),
                f"{v['taux_remise_pct']:.0f} %", f"{v['marge_pct']:.1f} %"))

        clients = ap.analyse_prix_par_client(jours, min_lignes=2)
        t2 = self.tab_nego_client
        t2.delete(*t2.get_children())
        for i, c in enumerate(clients):
            tags = ("alerte",) if c["ecart_pct"] <= -10 else ()
            t2.insert("", tk.END, tags=zebre(i, tags), values=(
                c["client"], c["type_client"],
                libelles.get(c["tendance"], c["tendance"]), c["nb_lignes"],
                fmt_money(c["ca_reel"]),
                f"{c['remise_moyenne_pct']:+.1f} %" if c["remise_moyenne_pct"] else "—",
                fmt_money(c["impact_total"]), f"{c['marge_pct']:.1f} %"))

        self.lbl_nego_info.configure(
            text=f"{len(vendeurs)} vendeur(s) et {len(clients)} client(s) "
                 f"ayant au moins 2 lignes de vente sur la période.")


# ═══════════════════════════════════════════════════════
#  DIALOGUES
# ═══════════════════════════════════════════════════════

class DialogueHistoriquePrix(tk.Toplevel):
    """Historique complet des prix pratiqués pour un produit + courbe."""

    def __init__(self, parent, produit_id, devise="F CFA"):
        super().__init__(parent)
        self.devise = devise
        detail = ap.detail_prix_produit(produit_id, jours=365)
        if not detail["produit"]:
            self.destroy()
            messagebox.showinfo("Information", "Produit introuvable.", parent=parent)
            return

        p = detail["produit"]
        self.title(f"Historique des prix — {p['reference']} {p['nom']}")
        self.configure(bg=COULEURS["bg"], padx=14, pady=14)
        self.geometry("1000x680")
        self.transient(parent)

        # ── En-tête ──
        entete = tk.Frame(self, bg=COULEURS["card"], padx=16, pady=12,
                          highlightbackground=COULEURS["border"], highlightthickness=1)
        entete.pack(fill=tk.X, pady=(0, 10))
        tk.Label(entete, text=f"{p['reference']} — {p['nom']}",
                 font=(POLICE, 14, "bold"), bg=COULEURS["card"],
                 fg=COULEURS["text"]).pack(anchor="w")
        prix = [l["prix_unitaire"] for l in detail["lignes"]]
        if prix:
            moyen = sum(l["prix_unitaire"] * l["quantite"] for l in detail["lignes"]) / \
                    max(1, sum(l["quantite"] for l in detail["lignes"]))
            tk.Label(entete,
                     text=f"Prix affiché : {fmt_money(p['prix_catalogue'], devise)}   ·   "
                          f"Coût de revient : {fmt_money(p['cout'], devise)}   ·   "
                          f"Prix réel moyen : {fmt_money(moyen, devise)}   ·   "
                          f"Amplitude : {fmt_money(min(prix), devise)} → "
                          f"{fmt_money(max(prix), devise)}",
                     font=(POLICE, 10), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(4, 0))

        # ── Courbe des prix pratiqués ──
        graphe = Carte(self, "Prix pratiqués dans le temps (courbe) — "
                             "ligne pleine = prix affiché, pointillés = coût")
        graphe.pack(fill=tk.X, pady=(0, 10))
        self._courbe_prix(graphe.corps, detail, p)

        # ── Paliers ──
        if detail["paliers"]:
            paliers = Carte(self, "Prix les plus fréquents")
            paliers.pack(fill=tk.X, pady=(0, 10))
            texte = "     ".join(
                f"{fmt_money(pal['prix'], devise)} ({pal['nb']}× — {pal['part_pct']:.0f} %)"
                for pal in detail["paliers"][:6])
            tk.Label(paliers.corps, text=texte, font=(POLICE, 10),
                     bg=COULEURS["card"], fg=COULEURS["text"],
                     justify="left", wraplength=940).pack(anchor="w")

        # ── Tableau ──
        cadre = Carte(self, f"{len(detail['lignes'])} ligne(s) de vente")
        cadre.pack(fill=tk.BOTH, expand=True)
        zone_tab = tk.Frame(cadre.corps, bg=COULEURS["card"])
        zone_tab.pack(fill=tk.BOTH, expand=True)
        tab = TableauTriable(zone_tab, [
            ("date", "Date", 130, "w", False),
            ("num", "Facture", 125, "w", False),
            ("client", "Client", 150, "w", False),
            ("vendeur", "Vendeur", 105, "w", False),
            ("qte", "Qté", 50, "center", True),
            ("pu", "Prix unitaire", 105, "e", True),
            ("ecart", "Écart", 95, "e", True),
            ("ecartpct", "Écart %", 75, "center", True),
            ("cout", "Coût", 95, "e", True),
            ("marge", "Marge unit.", 100, "e", True)])
        ajouter_scrollbars(zone_tab, tab)
        for i, l in enumerate(detail["lignes"]):
            tags = ("rupture",) if l["sous_cout"] else (
                ("alerte",) if l["ecart_pct"] <= -10 else ())
            tab.insert("", tk.END, tags=zebre(i, tags), values=(
                fmt_date(l["date_vente"]), l["numero"] or "—", l["client_nom"],
                l["utilisateur"] or "—", l["quantite"],
                fmt_money(l["prix_unitaire"]), fmt_money(l["ecart"]),
                f"{l['ecart_pct']:+.1f} %", fmt_money(l["cout"]),
                fmt_money(l["marge_unitaire"])))

        Bouton(self, "Fermer", "secondary", self.destroy,
               petit=True).pack(anchor="e", pady=(10, 0))

    def _courbe_prix(self, parent, detail, produit):
        """Courbe linéaire des prix pratiqués, du plus ancien au plus récent."""
        canvas = tk.Canvas(parent, height=190, bg=COULEURS["card"],
                           highlightthickness=0)
        canvas.pack(fill=tk.X)
        # Ordre chronologique (les lignes arrivent en DESC)
        lignes = list(reversed(detail["lignes"]))
        if not lignes:
            return
        catalogue = produit["prix_catalogue"]
        cout = produit["cout"]

        def redessiner(_e=None):
            try:
                if not canvas.winfo_exists():
                    return
                canvas.delete("all")
            except tk.TclError:
                return
            largeur = canvas.winfo_width() or 900
            hauteur = 190
            marge_g, marge_d, marge_h, marge_b = 70, 20, 20, 30
            zone_h = hauteur - marge_h - marge_b
            zone_l = largeur - marge_g - marge_d

            valeurs = [l["prix_unitaire"] for l in lignes] + [catalogue]
            if cout:
                valeurs.append(cout)
            maxi, mini = max(valeurs), min(valeurs)
            if maxi == mini:
                maxi, mini = maxi * 1.1 or 1, mini * 0.9
            etendue = maxi - mini

            def y_de(valeur):
                return marge_h + zone_h - ((valeur - mini) / etendue) * zone_h

            # Grille + échelle
            for frac in (0, 0.25, 0.5, 0.75, 1):
                valeur = mini + etendue * frac
                y = y_de(valeur)
                canvas.create_line(marge_g, y, largeur - marge_d, y,
                                   fill=COULEURS["canvas_grid"])
                canvas.create_text(marge_g - 8, y, anchor="e", font=(POLICE, 7),
                                   fill=COULEURS["text_secondary"],
                                   text=fmt_money(valeur))

            # Repère prix catalogue (ligne pleine)
            y_cat = y_de(catalogue)
            canvas.create_line(marge_g, y_cat, largeur - marge_d, y_cat,
                               fill=COULEURS["info"], width=2)
            canvas.create_text(largeur - marge_d - 4, y_cat - 8, anchor="e",
                               font=(POLICE, 7, "bold"), fill=COULEURS["info"],
                               text="prix affiché")

            # Repère coût de revient (pointillés)
            if cout:
                y_cout = y_de(cout)
                canvas.create_line(marge_g, y_cout, largeur - marge_d, y_cout,
                                   fill=COULEURS["danger"], width=1, dash=(4, 3))
                canvas.create_text(largeur - marge_d - 4, y_cout + 9, anchor="e",
                                   font=(POLICE, 7, "bold"), fill=COULEURS["danger"],
                                   text="coût de revient")

            # La courbe des prix pratiqués
            n = max(1, len(lignes) - 1)
            pas = zone_l / n
            points = []
            for i, l in enumerate(lignes):
                points.append((marge_g + i * pas, y_de(l["prix_unitaire"]), l))

            if len(points) > 1:
                ligne_plate = []
                for x, y, _ in points:
                    ligne_plate += [x, y]
                canvas.create_line(ligne_plate, fill=COULEURS["primary"], width=2,
                                   smooth=True, splinesteps=10)

            for x, y, l in points:
                couleur = (COULEURS["danger"] if l["sous_cout"]
                           else COULEURS["success"] if l["ecart"] >= 0
                           else COULEURS["warning"])
                canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=couleur,
                                   outline=COULEURS["card"], width=1)

            # Étiquettes de dates (début / milieu / fin)
            for idx in {0, len(points) // 2, len(points) - 1}:
                if 0 <= idx < len(points):
                    x, _, l = points[idx]
                    date = str(l["date_vente"])[:10]
                    try:
                        libelle = datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m")
                    except ValueError:
                        libelle = date
                    canvas.create_text(x, marge_h + zone_h + 14, text=libelle,
                                       font=(POLICE, 8),
                                       fill=COULEURS["text_secondary"])

        canvas.bind("<Configure>", redessiner)
        canvas.after(120, redessiner)


class DialoguePrixConseille(tk.Toplevel):
    """Suggestion de prix catalogue + application en un clic."""

    def __init__(self, parent, produit_id, conseil, devise, app):
        super().__init__(parent)
        self.produit_id = produit_id
        self.conseil = conseil
        self.app = app
        self.title("Prix conseillé")
        self.configure(bg=COULEURS["bg"], padx=18, pady=18)
        self.transient(parent)
        self.resizable(False, False)

        produit = db.get_produit(produit_id)
        nom = f"{produit['reference']} — {produit['nom']}" if produit else ""

        tk.Label(self, text=nom, font=(POLICE, 13, "bold"), bg=COULEURS["bg"],
                 fg=COULEURS["text"]).pack(anchor="w", pady=(0, 12))

        grille = tk.Frame(self, bg=COULEURS["card"], padx=16, pady=14,
                          highlightbackground=COULEURS["border"], highlightthickness=1)
        grille.pack(fill=tk.X)
        lignes = [
            ("Prix actuellement affiché", fmt_money(conseil["prix_catalogue"], devise),
             COULEURS["text"]),
            ("Coût de revient (CUMP)", fmt_money(conseil["cout"], devise),
             COULEURS["text_secondary"]),
            ("Prix médian réellement pratiqué", fmt_money(conseil["prix_median"], devise),
             COULEURS["primary"]),
            ("Amplitude constatée",
             f"{fmt_money(conseil['prix_min'], devise)} → "
             f"{fmt_money(conseil['prix_max'], devise)}", COULEURS["text_secondary"]),
            (f"Plancher pour {conseil['marge_cible_pct']:.0f} % de marge",
             fmt_money(conseil["prix_plancher"], devise), COULEURS["warning"]),
            ("PRIX CONSEILLÉ", fmt_money(conseil["prix_conseille"], devise),
             COULEURS["success"]),
        ]
        for i, (libelle, valeur, couleur) in enumerate(lignes):
            gras = "bold" if libelle.isupper() else "normal"
            tk.Label(grille, text=libelle, font=(POLICE, 10, gras),
                     bg=COULEURS["card"], fg=COULEURS["text"], anchor="w").grid(
                row=i, column=0, sticky="w", pady=3)
            tk.Label(grille, text=valeur,
                     font=(POLICE, 12 if libelle.isupper() else 10, "bold"),
                     bg=COULEURS["card"], fg=couleur, anchor="e").grid(
                row=i, column=1, sticky="e", padx=(30, 0), pady=3)
        grille.columnconfigure(1, weight=1)

        if conseil["palier_dominant"]:
            pal = conseil["palier_dominant"]
            tk.Label(self, text=f"Prix le plus souvent pratiqué : "
                                f"{fmt_money(pal['prix'], devise)} "
                                f"({pal['nb']} fois, {pal['part_pct']:.0f} % des ventes)",
                     font=(POLICE, 9), bg=COULEURS["bg"],
                     fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(10, 0))

        tk.Label(self, text=conseil["message"], font=(POLICE, 10),
                 bg=COULEURS["bg"], fg=COULEURS["text"], justify="left",
                 wraplength=520).pack(anchor="w", pady=(12, 0))

        tk.Label(self, text=f"Basé sur {conseil['nb_ventes']} vente(s) réelle(s).",
                 font=(POLICE, 8), bg=COULEURS["bg"],
                 fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(8, 14))

        boutons = tk.Frame(self, bg=COULEURS["bg"])
        boutons.pack(fill=tk.X)
        Bouton(boutons, f"✅ Appliquer {fmt_money(conseil['prix_conseille'], devise)}",
               "success", self._appliquer, petit=True).pack(side=tk.LEFT)
        Bouton(boutons, "Fermer", "secondary", self.destroy,
               petit=True).pack(side=tk.RIGHT)

    def _appliquer(self):
        produit = db.get_produit(self.produit_id)
        if not produit:
            return
        nouveau = self.conseil["prix_conseille"]
        if not messagebox.askyesno(
                "Confirmer",
                f"Remplacer le prix affiché de « {produit['nom']} » :\n\n"
                f"{produit['prix_vente']:,.0f}  →  {nouveau:,.0f} F CFA\n\n"
                f"Les ventes déjà enregistrées ne changent pas.", parent=self):
            return
        ok, msg = db.update_produit(
            self.produit_id, produit["reference"], produit["nom"],
            description=produit.get("description", ""),
            categorie_id=produit.get("categorie_id"),
            fournisseur_id=produit.get("fournisseur_id"),
            marque=produit.get("marque", ""),
            prix_achat=produit.get("prix_achat", 0),
            prix_vente=nouveau,
            stock_mini=produit.get("stock_mini", 5),
            emplacement=produit.get("emplacement", ""),
            code_barres=produit.get("code_barres", ""),
            actif=produit.get("actif", 1),
            emplacement_type=produit.get("emplacement_type", "vente"))
        if ok:
            # Trace le changement dans l'historique des prix
            conn = db.get_connection()
            try:
                with conn:
                    db._tracer_prix(conn, self.produit_id, "vente",
                                    produit["prix_vente"], nouveau,
                                    "prix conseillé", "", "analyse")
            finally:
                conn.close()
            messagebox.showinfo("Prix mis à jour",
                                f"Nouveau prix affiché : {nouveau:,.0f} F CFA",
                                parent=self)
            self.app.statut(f"Prix de « {produit['nom']} » mis à jour",
                            COULEURS["success"])
            try:
                self.app._charger_prix()
            except Exception:
                pass
            self.destroy()
        else:
            messagebox.showwarning("Impossible", msg, parent=self)
