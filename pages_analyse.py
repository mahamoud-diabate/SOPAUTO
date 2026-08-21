"""
SOPAUTO — Écran « Analyse commerciale »
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
from dialogues import DialogueHistoriquePrix, DialoguePrixConseille
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

    def afficher_analyse(self) -> None:
        """Affiche l'écran d'analyse commerciale avec 4 onglets."""
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
        f_tree_nv = tk.Frame(c1.corps, bg=COULEURS["card"])
        f_tree_nv.pack(fill=tk.BOTH, expand=True)
        self.tab_nego_vendeur = TableauTriable(f_tree_nv, [
            ("vendeur", "Vendeur", 135, "w", False),
            ("tend", "Tendance", 100, "center", False),
            ("nb", "Lignes", 60, "center", True),
            ("ca", "CA encaissé", 110, "e", True),
            ("theo", "CA affiché", 110, "e", True),
            ("ecart", "Écart %", 80, "center", True),
            ("impact", "Impact", 105, "e", True),
            ("taux", "% remisé", 80, "center", True),
            ("marge", "Marge %", 75, "center", True)], height=15)
        ajouter_scrollbars(f_tree_nv, self.tab_nego_vendeur)

        c2 = Carte(conteneur, "Par client — qui obtient les meilleurs prix ?")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        f_tree_nc = tk.Frame(c2.corps, bg=COULEURS["card"])
        f_tree_nc.pack(fill=tk.BOTH, expand=True)
        self.tab_nego_client = TableauTriable(f_tree_nc, [
            ("client", "Client", 155, "w", False),
            ("type", "Type", 90, "w", False),
            ("tend", "Tendance", 100, "center", False),
            ("nb", "Lignes", 60, "center", True),
            ("ca", "CA encaissé", 110, "e", True),
            ("remise", "Remise moy.", 100, "center", True),
            ("impact", "Impact", 105, "e", True),
            ("marge", "Marge %", 75, "center", True)], height=15)
        ajouter_scrollbars(f_tree_nc, self.tab_nego_client)

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
