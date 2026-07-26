
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import database as db
import metier_v3 as m3
from ui_widgets import (COULEURS, POLICE, Bouton, Carte,
                        TableauTriable, fmt_date, fmt_money, zebre,
                        EntreeRecherche)
from dialogues import (DialogueDepot, DialogueTransfert)

class DepotsMixin:
    """Mixin : Gestion des dépôts."""

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
