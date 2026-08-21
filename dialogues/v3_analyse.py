"""Dialogues: analyse commerciale"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import analyse_prix as ap
import database as db
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, TableauTriable,
                        ajouter_scrollbars, fmt_date, fmt_money, zebre)

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
                 font=(POLICE, 16, "bold"), bg=COULEURS["card"],
                 fg=COULEURS["text"]).pack(anchor="w")
        prix = [l["prix_unitaire"] for l in detail["lignes"]]
        if prix:
            moyen = sum(l["prix_unitaire"] * l["quantite"] for l in detail["lignes"]) / \
                    max(1, sum(l["quantite"] for l in detail["lignes"]))
            tk.Label(entete,
                     text=f"Prix affiché : {fmt_money(p['prix_catalogue'], devise)} ·"
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
                canvas.create_text(marge_g - 8, y, anchor="e", font=(POLICE, 9),
                                   fill=COULEURS["text_secondary"],
                                   text=fmt_money(valeur))

            # Repère prix catalogue (ligne pleine)
            y_cat = y_de(catalogue)
            canvas.create_line(marge_g, y_cat, largeur - marge_d, y_cat,
                               fill=COULEURS["info"], width=2)
            canvas.create_text(largeur - marge_d - 4, y_cat - 8, anchor="e",
                               font=(POLICE, 9, "bold"), fill=COULEURS["info"],
                               text="prix affiché")

            # Repère coût de revient (pointillés)
            if cout:
                y_cout = y_de(cout)
                canvas.create_line(marge_g, y_cout, largeur - marge_d, y_cout,
                                   fill=COULEURS["danger"], width=1, dash=(4, 3))
                canvas.create_text(largeur - marge_d - 4, y_cout + 9, anchor="e",
                                   font=(POLICE, 9, "bold"), fill=COULEURS["danger"],
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
                                       font=(POLICE, 9),
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

        tk.Label(self, text=nom, font=(POLICE, 12, "bold"), bg=COULEURS["bg"],
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
            tk.Label(self, text=f"Prix le plus souvent pratiqué :"
                                f"{fmt_money(pal['prix'], devise)} "
                                f"({pal['nb']} fois, {pal['part_pct']:.0f} % des ventes)",
                     font=(POLICE, 9), bg=COULEURS["bg"],
                     fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(10, 0))

        tk.Label(self, text=conseil["message"], font=(POLICE, 10),
                 bg=COULEURS["bg"], fg=COULEURS["text"], justify="left",
                 wraplength=520).pack(anchor="w", pady=(12, 0))

        tk.Label(self, text=f"Basé sur {conseil['nb_ventes']} vente(s) réelle(s).",
                 font=(POLICE, 9), bg=COULEURS["bg"],
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
                pass
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
