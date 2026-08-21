
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import database as db
import metier_v3 as m3
from ui_widgets import (COULEURS, POLICE, Bouton, Carte,
                        TableauTriable, fmt_date, fmt_money, zebre,
                        parse_float, ajouter_scrollbars)

class PrevisionsMixin:
    """Mixin : Prévisions de rupture."""

# ═══════════════════════════════════════════════════
    #  📉 PRÉVISIONS DE RUPTURE
    # ═══════════════════════════════════════════════════

    def afficher_previsions(self):
        if not self.peut("stock"):
            return self._refus()
        self._nouvelle_page("Prévisions de rupture", self._idx_menu("Prévisions"))

        Bouton(self.zone_actions, "Créer la commande", "primary",
               self._commander_depuis_prevision, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "Exporter", "info",
               self._exporter_previsions, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "Recalculer ABC", "secondary",
               self._recalculer_abc, petit=True).pack(side=tk.LEFT, padx=3)

        barre = tk.Frame(self.zone, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        tk.Label(barre, text="Horizon :", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.cb_horizon = ttk.Combobox(barre, state="readonly", width=12, font=(POLICE, 9),
                                       values=["7 jours", "14 jours", "30 jours", "60 jours"])
        self.cb_horizon.current(2)
        self.cb_horizon.pack(side=tk.LEFT, padx=(4, 14))
        self.cb_horizon.bind("<<ComboboxSelected>>", lambda e: self._charger_previsions())
        self.lbl_prev_resume = tk.Label(barre, text="", font=(POLICE, 9),
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
        horizon = int(parse_float(self.cb_horizon.get().split()[0], 30))
        prev = m3.prevision_rupture(horizon_jours=horizon)
        self._previsions_courantes = prev
        icones = {"critique": "🔴 Critique", "haute": "🟠 Haute", "moyenne": "Moyenne"}
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
            self.statut("Aucune rupture prévue sur cet horizon", COULEURS["success"])

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
