"""
SODIPAC - Dashboard
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


class DashboardMixin:
    """Tableau de bord — KPIs, graphique CA 7 jours, alertes stock, top ventes.

    Écran d'accueil pour gérant/superviseur : 6 KPI, objectif mensuel,
    graphique linéaire natif, alertes rupture, signaux commerciaux.
    """

    def afficher_dashboard(self):
        self._nouvelle_page("📊 Tableau de bord", 0)
        Bouton(self.zone_actions, "🔄 Actualiser", "secondary",
               self.afficher_dashboard, petit=True).pack(side=tk.LEFT, padx=3)
        if self.peut("rapports"):
            Bouton(self.zone_actions, "📄 Bon de réappro", "warning",
                   self.generer_reappro, petit=True).pack(side=tk.LEFT, padx=3)

        s = db.get_dashboard_stats()
        self._kpi_dashboard(s)
        self._objectif_mois(s)
        self._activite_mois(s)
        self._panneaux_bas(s)


    def _dessiner_graphe(self, parent, donnees, jours_affiches=7, titre_court=True):
        """Courbe linéaire du CA sur les N derniers jours (Canvas natif)."""
        canvas = tk.Canvas(parent, height=170, bg=COULEURS["card"], highlightthickness=0)
        canvas.pack(fill=tk.X)

        jours = {}
        for d in donnees:
            jours[d["jour"]] = d["ca"]
        serie = []
        for i in range(jours_affiches - 1, -1, -1):
            jour = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            serie.append((jour, jours.get(jour, 0)))

        etat = {"points": [], "survol": None}

        def redessiner(_event=None):
            # Le Canvas peut avoir été détruit par un changement de page avant
            # que le callback « after » ne se déclenche.
            try:
                if not canvas.winfo_exists():
                    return
                canvas.delete("all")
            except tk.TclError:
                return
            largeur = canvas.winfo_width() or 900
            hauteur = 170
            valeurs = [v for _, v in serie]
            maxi = max(valeurs, default=0) or 1
            marge_g, marge_d, marge_b, marge_h = 62, 16, 28, 22
            zone_h = hauteur - marge_b - marge_h
            zone_l = largeur - marge_g - marge_d
            n = max(1, len(serie) - 1)
            pas = zone_l / n

            # ── Grille horizontale + échelle ──
            for frac in (0, 0.25, 0.5, 0.75, 1):
                y = marge_h + zone_h * (1 - frac)
                canvas.create_line(marge_g, y, largeur - marge_d, y,
                                   fill=COULEURS["canvas_grid"])
                if frac in (0, 0.5, 1):
                    canvas.create_text(marge_g - 8, y, anchor="e", font=(POLICE, 7),
                                       fill=COULEURS["text_secondary"],
                                       text=fmt_money(maxi * frac))

            # ── Coordonnées des points ──
            points = []
            for i, (jour, valeur) in enumerate(serie):
                x = marge_g + i * pas
                y = marge_h + zone_h - (valeur / maxi) * zone_h
                points.append((x, y, jour, valeur))
            etat["points"] = points

            couleur = COULEURS.get("graph_line", COULEURS["primary"])

            # ── Aire de remplissage sous la courbe ──
            if len(points) > 1:
                polygone = [marge_g, marge_h + zone_h]
                for x, y, _, _ in points:
                    polygone += [x, y]
                polygone += [points[-1][0], marge_h + zone_h]
                canvas.create_polygon(polygone, fill=COULEURS["primary_light"],
                                      outline="", width=0)

                # ── La ligne ──
                ligne = []
                for x, y, _, _ in points:
                    ligne += [x, y]
                canvas.create_line(ligne, fill=couleur, width=2,
                                   smooth=True, splinesteps=12, capstyle=tk.ROUND)

            # ── Marqueurs + étiquettes ──
            aujourd_hui = datetime.now().strftime("%Y-%m-%d")
            pas_etiq = 1 if len(serie) <= 10 else max(1, len(serie) // 8)
            for i, (x, y, jour, valeur) in enumerate(points):
                est_auj = (jour == aujourd_hui)
                rayon = 5 if est_auj else 3
                canvas.create_oval(x - rayon, y - rayon, x + rayon, y + rayon,
                                   fill=COULEURS["card"], outline=couleur,
                                   width=2 if est_auj else 1.5)
                # Valeur affichée sur le dernier point et le maximum
                if valeur and (est_auj or valeur == maxi):
                    canvas.create_text(x, y - 12, text=fmt_money(valeur),
                                       font=(POLICE, 7, "bold"), fill=COULEURS["text"])
                if i % pas_etiq == 0 or est_auj:
                    fmt = "%a %d" if titre_court else "%d/%m"
                    etiquette = datetime.strptime(jour, "%Y-%m-%d").strftime(fmt)
                    canvas.create_text(x, marge_h + zone_h + 14,
                                       text=etiquette.capitalize(), font=(POLICE, 8),
                                       fill=couleur if est_auj else COULEURS["text_secondary"])

        def survol(event):
            """Repère vertical + valeur au passage de la souris."""
            try:
                if not canvas.winfo_exists() or not etat["points"]:
                    return
                canvas.delete("survol")
            except tk.TclError:
                return
            proche = min(etat["points"], key=lambda p: abs(p[0] - event.x))
            x, y, jour, valeur = proche
            canvas.create_line(x, 18, x, 148, fill=COULEURS["secondary"],
                               dash=(2, 3), tags="survol")
            libelle = f"{datetime.strptime(jour, '%Y-%m-%d').strftime('%d/%m')} : {fmt_money(valeur)}"
            largeur_txt = len(libelle) * 6 + 12
            bx = min(max(x, largeur_txt / 2 + 4), (canvas.winfo_width() or 900) - largeur_txt / 2 - 4)
            canvas.create_rectangle(bx - largeur_txt / 2, 2, bx + largeur_txt / 2, 18,
                                    fill=COULEURS["tooltip_bg"], outline="", tags="survol")
            canvas.create_text(bx, 10, text=libelle, font=(POLICE, 7, "bold"),
                               fill="#ffffff", tags="survol")

        def quitter_survol(_event=None):
            try:
                if canvas.winfo_exists():
                    canvas.delete("survol")
            except tk.TclError:
                pass

        canvas.bind("<Configure>", redessiner)
        canvas.bind("<Motion>", survol)
        canvas.bind("<Leave>", quitter_survol)

        def premier_trace():
            try:
                if canvas.winfo_exists():
                    redessiner()
            except tk.TclError:
                pass

        self._planifier(60, premier_trace)


    def _kpi_dashboard(self, s):
        """Rangée des KPI du tableau de bord."""
        def delta_txt(actuel, precedent):
            if precedent <= 0:
                return ("— pas de comparaison", COULEURS["text_secondary"])
            pct = (actuel - precedent) / precedent * 100
            c = COULEURS["success"] if pct >= 0 else COULEURS["danger"]
            return (f"▲ +{pct:.0f} % vs période préc." if pct >= 0
                    else f"▼ {pct:.0f} % vs période préc.", c)

        kpis = tk.Frame(self.zone, bg=COULEURS["bg"])
        kpis.pack(fill=tk.X, pady=(0, 8))
        d_jour = delta_txt(s["ventes_aujourdhui"], s["ventes_hier"])
        d_sem = delta_txt(s["ventes_semaine"], s["ventes_semaine_prec"])
        d_mois = delta_txt(s["ventes_mois"], s["ventes_mois_prec"])
        cartes = [
            ("💰", "Ventes du jour", fmt_money(s["ventes_aujourdhui"], self.devise),
             f"{s['nb_ventes_aujourdhui']} vente(s)", COULEURS["success"], d_jour),
            ("🗓️", "7 derniers jours", fmt_money(s["ventes_semaine"], self.devise),
             "vs 7 jours précédents", COULEURS["info"], d_sem),
            ("📅", "Ventes du mois", fmt_money(s["ventes_mois"], self.devise),
             f"marge {fmt_money(s['marge_mois'], self.devise)}", COULEURS["primary"], d_mois),
            ("🏷️", "Valeur du stock", fmt_money(s["valeur_stock"], self.devise),
             f"revente {fmt_money(s['valeur_stock_vente'], self.devise)}", COULEURS["info"], None),
            ("⚠️", "Alertes stock", f"{s['nb_alertes']}",
             f"{s['nb_ruptures']} rupture(s)",
             COULEURS["danger"] if s["nb_alertes"] else COULEURS["success"], None),
            ("📦", "Produits actifs", f"{s['total_produits']}",
             f"{s['stock_total']} unité(s)", COULEURS["secondary"], None),
        ]
        for icone, titre, valeur, sous, couleur, delta in cartes:
            c = tk.Frame(kpis, bg=COULEURS["card"],
                         highlightbackground=COULEURS["border"], highlightthickness=1, padx=0, pady=0)
            c.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
            tk.Frame(c, bg=couleur, height=4).pack(fill=tk.X)
            interieur = tk.Frame(c, bg=COULEURS["card"], padx=14, pady=10)
            interieur.pack(fill=tk.BOTH, expand=True)
            tk.Label(interieur, text=f"{icone} {titre}", font=(POLICE, 9),
                     bg=COULEURS["card"], fg=couleur).pack(anchor="w")
            tk.Label(interieur, text=valeur, font=(POLICE, 18, "bold"),
                     bg=COULEURS["card"], fg=COULEURS["text"]).pack(anchor="w", pady=(2, 0))
            tk.Label(interieur, text=sous, font=(POLICE, 8),
                     bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(anchor="w")
            if delta:
                tk.Label(interieur, text=delta[0], font=(POLICE, 8, "bold"),
                         bg=COULEURS["card"], fg=delta[1]).pack(anchor="w")


    def _objectif_mois(self, s):
        """Barre de l'objectif CA mensuel."""
        try:
            objectif = float(self.params.get("objectif_ca_mois", "0") or 0)
        except ValueError:
            objectif = 0
        if objectif <= 0:
            return
        c_obj = tk.Frame(self.zone, bg=COULEURS["card"],
                         highlightbackground=COULEURS["border"], highlightthickness=1)
        c_obj.pack(fill=tk.X, pady=(0, 8), padx=4)
        interieur = tk.Frame(c_obj, bg=COULEURS["card"], padx=14, pady=8)
        interieur.pack(fill=tk.X)
        pct = min(s["ventes_mois"] / objectif * 100, 100)
        atteint = s["ventes_mois"] >= objectif
        tk.Label(interieur,
                 text=f"🎯 Objectif du mois : {fmt_money(s['ventes_mois'], self.devise)} / "
                      f"{fmt_money(objectif, self.devise)}  ({pct:.0f} %)"
                      + ("  ✅ Objectif atteint !" if atteint else ""),
                 font=(POLICE, 10, "bold"), bg=COULEURS["card"],
                 fg=COULEURS["success"] if atteint else COULEURS["text"]).pack(anchor="w")
        barre = tk.Frame(interieur, bg=COULEURS["heading"], height=12)
        barre.pack(fill=tk.X, pady=(6, 2))
        barre.pack_propagate(False)
        rempli = tk.Frame(barre, bg=COULEURS["success"] if atteint else COULEURS["primary"])
        rempli.place(relx=0, rely=0, relwidth=pct / 100, relheight=1)


    def _activite_mois(self, s):
        """Graphique + activité par vendeur et paiement."""
        milieu = tk.Frame(self.zone, bg=COULEURS["bg"])
        milieu.pack(fill=tk.X, pady=(0, 8))
        graphe = Carte(milieu, "📈 Chiffre d'affaires — 7 derniers jours")
        graphe.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self._dessiner_graphe(graphe.corps, s["ventes_7j"])
        c_activite = Carte(milieu, "📊 Activité du mois")
        c_activite.pack(side=tk.LEFT, fill=tk.BOTH, padx=(6, 0))
        act = c_activite.corps
        tk.Label(act, text="Par vendeur", font=(POLICE, 9, "bold"),
                 bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(anchor="w")
        tv = ttk.Treeview(act, show="headings", height=3,
                          columns=("vendeur", "nb", "ca", "panier"))
        for col, titre, largeur, ancre in (("vendeur", "Vendeur", 110, "w"),
                                           ("nb", "Ventes", 55, "center"),
                                           ("ca", "CA", 100, "e"),
                                           ("panier", "Panier moy.", 90, "e")):
            tv.heading(col, text=titre)
            tv.column(col, width=largeur, anchor=ancre)
        for v in s["par_vendeur_mois"]:
            tv.insert("", tk.END, values=(v["vendeur"], v["nb"],
                                          fmt_money(v["ca"]), fmt_money(v["panier"])))
        tv.pack(fill=tk.X)
        tk.Label(act, text="Par mode de paiement", font=(POLICE, 9, "bold"),
                 bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(8, 0))
        tp = ttk.Treeview(act, show="headings", height=3,
                          columns=("mode", "nb", "ca"))
        for col, titre, largeur, ancre in (("mode", "Mode", 130, "w"),
                                           ("nb", "Nb", 50, "center"),
                                           ("ca", "Montant", 120, "e")):
            tp.heading(col, text=titre)
            tp.column(col, width=largeur, anchor=ancre)
        for p in s["par_paiement_mois"]:
            tp.insert("", tk.END, values=(p["mode"], p["nb"], fmt_money(p["ca"])))
        tp.pack(fill=tk.X)


    def _panneaux_bas(self, s):
        """Alertes, top ventes, dernières ventes."""
        bas = tk.Frame(self.zone, bg=COULEURS["bg"])
        bas.pack(fill=tk.BOTH, expand=True)
        c_alertes = Carte(bas, f"🚨 Alertes de stock ({s['nb_alertes']})")
        c_alertes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        if s["alertes_stock"]:
            t = TableauTriable(c_alertes.corps, [
                ("nom", "Produit", 130, "w", False), ("cat", "Catégorie", 80, "w", False),
                ("stock", "Stock", 45, "center", True), ("mini", "Seuil", 40, "center", True),
                ("rupture", "Rupture", 75, "center", False)], height=9)
            for i, a in enumerate(s["alertes_stock"]):
                text_r = ""
                if a.get("rupture_jours") is not None:
                    j = a["rupture_jours"]
                    text_r = f"⚠ {j}j" if j <= 7 else (f"⚠ {j}j" if j <= 15 else f"{j}j")
                t.insert("", tk.END, iid=a["id"],
                         tags=zebre(i, ("rupture",) if a["stock"] <= 0 else ("alerte",)),
                         values=(a["nom"], a["categorie_nom"] or "—", a["stock"], a["stock_mini"], text_r))
            t.pack(fill=tk.BOTH, expand=True)
            if self.peut("stock"):
                t.bind("<Double-1>", lambda e: self._entree_rapide(t))
                infobulle(t, "Double-clic : entrée de stock rapide")
        else:
            tk.Label(c_alertes.corps, text="✅ Tous les stocks sont suffisants",
                     font=(POLICE, 11), bg=COULEURS["card"],
                     fg=COULEURS["success"]).pack(pady=40)
        c_top = Carte(bas, "🏆 Top ventes (30 jours)")
        c_top.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)
        if s["top_produits"]:
            t = TableauTriable(c_top.corps, [
                ("nom", "Produit", 180, "w", False), ("qte", "Qté", 55, "center", True),
                ("ca", "CA", 100, "e", True)], height=9)
            for i, p in enumerate(s["top_produits"]):
                t.insert("", tk.END, tags=zebre(i),
                         values=(p["nom"], p["qte"], fmt_money(p["ca"])))
            t.pack(fill=tk.BOTH, expand=True)
        else:
            tk.Label(c_top.corps, text="Aucune vente sur 30 jours", font=(POLICE, 10),
                     bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(pady=40)
        c_ventes = Carte(bas, "🧾 Dernières ventes")
        c_ventes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        if s["dernieres_ventes"]:
            t = TableauTriable(c_ventes.corps, [
                ("num", "N°", 110, "w", False), ("client", "Client", 110, "w", False),
                ("total", "Total", 95, "e", True), ("date", "Date", 105, "w", False)], height=9)
            for i, v in enumerate(s["dernieres_ventes"]):
                etat = ("annulee",) if v["statut"] == "annulee" else ()
                t.insert("", tk.END, iid=v["id"], tags=zebre(i, etat),
                         values=(v["numero"] or f"#{v['id']}", v["client_nom"],
                                 fmt_money(v["total"]), fmt_date(v["date_vente"])))
            t.pack(fill=tk.BOTH, expand=True)
            t.bind("<Double-1>", lambda e: self._imprimer_selection(t))
            infobulle(t, "Double-clic : imprimer la facture")
        else:
            tk.Label(c_ventes.corps, text="Aucune vente enregistrée", font=(POLICE, 10),
                     bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(pady=40)

        self._panneau_alertes_commerciales()


    def _panneau_alertes_commerciales(self):
        """Bandeau des signaux prix / tendances, cliquable vers l'écran Analyse."""
        if not self.peut("rapports"):
            return
        try:
            alertes = analyse_prix.alertes_commerciales(30)
        except Exception:
            return
        if not alertes:
            return

        carte = Carte(self.zone, f"💰 Signaux commerciaux ({len(alertes)}) — "
                                 f"cliquez pour ouvrir l'analyse (F10)")
        carte.pack(fill=tk.X, pady=(8, 0))

        couleurs = {"critique": COULEURS["danger"], "haute": COULEURS["warning"],
                    "moyenne": COULEURS["info"], "secondary": COULEURS["secondary"]}
        for a in alertes[:4]:
            ligne = tk.Frame(carte.corps, bg=COULEURS["card"], cursor="hand2")
            ligne.pack(fill=tk.X, pady=1)
            couleur = couleurs.get(a["niveau"], COULEURS["text_secondary"])
            tk.Label(ligne, text="●", font=(POLICE, 12), bg=COULEURS["card"],
                     fg=couleur).pack(side=tk.LEFT, padx=(0, 6))
            tk.Label(ligne, text=a["categorie"], font=(POLICE, 9, "bold"),
                     bg=COULEURS["card"], fg=couleur, width=22,
                     anchor="w").pack(side=tk.LEFT)
            tk.Label(ligne, text=a["titre"], font=(POLICE, 9), bg=COULEURS["card"],
                     fg=COULEURS["text"], anchor="w").pack(side=tk.LEFT, padx=(4, 0))
            for widget in (ligne, *ligne.winfo_children()):
                widget.bind("<Button-1>", lambda e: self.afficher_analyse())

        if len(alertes) > 4:
            tk.Label(carte.corps,
                     text=f"… et {len(alertes) - 4} autre(s) signal(aux) — "
                          f"voir l'écran Analyse",
                     font=(POLICE, 8), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"], cursor="hand2").pack(
                anchor="w", pady=(4, 0))


