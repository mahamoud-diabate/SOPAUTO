"""
SODIPAC - Caisse
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

import database as db
import factures
from dialogues import DialoguePaiement, DialoguePaiementSimple
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, EntreeRecherche,
                        TableauTriable, ajouter_scrollbars, fmt_money,
                        infobulle, zebre)


class CaisseMixin:
    """Point de vente — scan, panier, encaissement avec prix négocié par ligne.

    Flux : recherche/scan → ajout panier → ajustement qté → encaissement F8
    → dialogue prix réel par ligne → paiement → ticket.
    """

    def afficher_caisse(self):
        if not self.peut("caisse"):
            return self._refus()
        self._nouvelle_page("🧾 Caisse — Point de vente", 1)

        self.panier = []
        produits = db.get_produits(inclure_inactifs=False)

        paned = tk.Frame(self.zone, bg=COULEURS["bg"])
        paned.pack(fill=tk.BOTH, expand=True)

        # ── Gauche : saisie ──
        gauche = Carte(paned, "🛒 Nouvelle vente")
        gauche.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        g = gauche.corps

        # ── Champ unique : scan + recherche ──
        self.recherche_caisse = EntreeRecherche(
            g, "Scannez un code-barres ou cherchez (réf, nom, marque, catégorie)…", 50,
            callback=lambda: self._charger_catalogue_caisse(), bg=COULEURS["card"])
        self.recherche_caisse.pack(fill=tk.X, pady=(0, 4))
        self.recherche_caisse.var.trace_add("write", lambda *_: self._recherche_caisse_typing())

        ligne_qte = tk.Frame(g, bg=COULEURS["card"])
        ligne_qte.pack(fill=tk.X, pady=(0, 8))
        tk.Label(ligne_qte, text="Qté", font=(POLICE, 9),
                 bg=COULEURS["card"]).pack(side=tk.LEFT, padx=(0, 4))
        self.var_qte = tk.StringVar(value="1")
        tk.Spinbox(ligne_qte, from_=1, to=9999, textvariable=self.var_qte,
                   font=(POLICE, 12), width=5, justify="center").pack(side=tk.LEFT, ipady=3)
        Bouton(ligne_qte, "➕ Ajouter au panier", "primary",
               self._ajouter_panier).pack(side=tk.LEFT, padx=(12, 0))
        # Enter dans le champ recherche = ajouter
        self.recherche_caisse.entry.bind("<Return>", lambda e: self._ajouter_panier())
        self.lbl_compteur_cat = tk.Label(ligne_qte, text="", font=(POLICE, 9),
                                         bg=COULEURS["card"], fg=COULEURS["text_secondary"])
        self.lbl_compteur_cat.pack(side=tk.RIGHT, padx=4)

        cadre_cat = tk.Frame(g, bg=COULEURS["card"])
        cadre_cat.pack(fill=tk.BOTH, expand=True)
        self.tab_catalogue = TableauTriable(cadre_cat, [
            ("ref", "Référence", 100, "w", False),
            ("nom", "Produit", 230, "w", False),
            ("marque", "Marque", 90, "w", False),
            ("stock", "Rayon", 60, "center", True),
            ("pv", "Prix", 90, "e", True)], height=11)
        ajouter_scrollbars(cadre_cat, self.tab_catalogue)
        self.tab_catalogue.bind("<Double-1>", lambda e: self._ajouter_depuis_catalogue())
        infobulle(self.tab_catalogue, "Double-clic pour ajouter au panier")
        self._produits_caisse = produits
        self._charger_catalogue_caisse()

        # Focus sur la recherche
        self.recherche_caisse.entry.focus_set()

        # ── Droite : panier ──
        droite = Carte(paned, "🧺 Panier")
        droite.pack(side=tk.LEFT, fill=tk.BOTH, padx=(8, 0))
        droite.configure(width=470)
        droite.pack_propagate(False)
        d = droite.corps

        cadre_panier = tk.Frame(d, bg=COULEURS["card"])
        cadre_panier.pack(fill=tk.BOTH, expand=True)
        self.tab_panier = ttk.Treeview(cadre_panier, show="headings", height=12,
                                       columns=("nom", "qte", "pu", "total"))
        for col, titre, largeur, ancre in (("nom", "Article", 190, "w"), ("qte", "Qté", 45, "center"),
                                           ("pu", "P.U.", 80, "e"), ("total", "Total", 90, "e")):
            self.tab_panier.heading(col, text=titre)
            self.tab_panier.column(col, width=largeur, anchor=ancre)
        ajouter_scrollbars(cadre_panier, self.tab_panier)
        self.tab_panier.bind("<Delete>", lambda e: self._retirer_panier())
        self.tab_panier.bind("<Double-1>", lambda e: self._modifier_qte_panier())

        actions = tk.Frame(d, bg=COULEURS["card"])
        actions.pack(fill=tk.X, pady=6)
        b1 = Bouton(actions, "➖", "warning", lambda: self._qte_rapide(-1), petit=True)
        b1.pack(side=tk.LEFT, padx=2); infobulle(b1, "Réduire la quantité de 1")
        b2 = Bouton(actions, "➕", "success", lambda: self._qte_rapide(1), petit=True)
        b2.pack(side=tk.LEFT, padx=2); infobulle(b2, "Augmenter la quantité de 1")
        b3 = Bouton(actions, "✎ Quantité", "info", self._modifier_qte_panier, petit=True)
        b3.pack(side=tk.LEFT, padx=2); infobulle(b3, "Saisir une quantité précise")
        b4 = Bouton(actions, "🗑 Vider", "secondary", self._vider_panier, petit=True)
        b4.pack(side=tk.LEFT, padx=2); infobulle(b4, "Vider tout le panier")

        cadre_total = tk.Frame(d, bg=COULEURS["total_bg"], highlightbackground=COULEURS["border"],
                               highlightthickness=1)
        cadre_total.pack(fill=tk.X, pady=8)
        self.lbl_articles = tk.Label(cadre_total, text="0 article", font=(POLICE, 9),
                                     bg=COULEURS["total_bg"], fg=COULEURS["text_secondary"])
        self.lbl_articles.pack(anchor="w", padx=12, pady=(8, 0))
        self.lbl_total_panier = tk.Label(cadre_total, text=fmt_money(0, self.devise),
                                         font=(POLICE, 26, "bold"), bg=COULEURS["total_bg"],
                                         fg=COULEURS["primary"])
        self.lbl_total_panier.pack(anchor="w", padx=12, pady=(0, 10))

        btn_enc = Bouton(d, "✅  ENCAISSER  (F8)", "success", self._encaisser,
               pady=12)
        btn_enc.pack(fill=tk.X)
        infobulle(btn_enc, "Raccourci : F8 — Ouvre le dialogue de paiement")
        self.root.bind("<F8>", lambda e: self._encaisser())

        historique = tk.Frame(d, bg=COULEURS["card"])
        historique.pack(fill=tk.X, pady=(10, 0))
        tk.Label(historique, text="Dernières ventes", font=(POLICE, 9, "bold"),
                 bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(anchor="w")
        self.tab_hist_caisse = ttk.Treeview(historique, show="headings", height=5,
                                            columns=("num", "total", "heure"))
        for col, titre, largeur, ancre in (("num", "N°", 130, "w"), ("total", "Total", 100, "e"),
                                           ("heure", "Heure", 70, "center")):
            self.tab_hist_caisse.heading(col, text=titre)
            self.tab_hist_caisse.column(col, width=largeur, anchor=ancre)
        self.tab_hist_caisse.pack(fill=tk.X)
        self.tab_hist_caisse.bind("<Double-1>",
                                  lambda e: self._imprimer_selection(self.tab_hist_caisse, True))
        infobulle(self.tab_hist_caisse, "Double-clic : réimprimer le reçu")
        self._charger_hist_caisse()
        self._maj_total_panier()


    def _charger_catalogue_caisse(self):
        recherche = self.recherche_caisse.get()
        self._produits_caisse = db.get_produits(search=recherche, inclure_inactifs=False)
        t = self.tab_catalogue
        t.delete(*t.get_children())
        for i, p in enumerate(self._produits_caisse):
            sv = p.get("stock_vente", p["stock"])
            etat = ("rupture",) if sv <= 0 else (("alerte",) if p["stock"] <= p["stock_mini"] else ())
            t.insert("", tk.END, iid=p["id"], tags=zebre(i, etat),
                     values=(p["reference"], p["nom"], p["marque"], sv,
                             fmt_money(p["prix_vente"])))
        self.lbl_compteur_cat.configure(text=f"{len(self._produits_caisse)} produit(s)")


    def _recherche_caisse_typing(self):
        """Déclenché à chaque frappe dans la barre de recherche unique."""
        self._charger_catalogue_caisse()


    def _ajouter_depuis_catalogue(self):
        sel = self.tab_catalogue.selection()
        if sel:
            self._ajouter_produit_panier(int(sel[0]), int(self.var_qte.get() or 1))


    def _ajouter_panier(self):
        code = self.recherche_caisse.get().strip()
        if not code:
            self._ajouter_depuis_catalogue()
            return
        produit = db.trouver_produit(code)
        if not produit:
            resultats = db.get_produits(search=code, inclure_inactifs=False)
            if len(resultats) == 1:
                produit = resultats[0]
            elif len(resultats) > 1:
                self.recherche_caisse.var.set(code)
                self.recherche_caisse._placeholder_actif = False
                self._charger_catalogue_caisse()
                self.statut(f"{len(resultats)} resultats — choisissez dans la liste",
                            COULEURS["warning"])
                return
            else:
                # Produit introuvable → proposer ajout rapide
                if messagebox.askyesno(
                        "Produit introuvable",
                        f"« {code} » n'est pas dans le catalogue.\n\n"
                        "Voulez-vous l'ajouter maintenant et le mettre dans le panier ?",
                        parent=self.root):
                    self._ajout_rapide(code)
                return
        self._ajouter_produit_panier(produit["id"], int(self.var_qte.get() or 1))
        self.recherche_caisse.effacer()
        self.recherche_caisse.entry.focus_set()


    def _ajout_rapide(self, nom_suggere=""):
        """Creer un produit a la volee (nom + prix) et l'ajouter au panier."""
        from tkinter import simpledialog
        nom = simpledialog.askstring(
            "Ajout rapide", "Nom du produit :",
            initialvalue=nom_suggere or "", parent=self.root)
        if not nom or not nom.strip():
            return
        prix_str = simpledialog.askstring(
            "Ajout rapide", f"Prix de vente pour « {nom.strip()} » (F CFA) :",
            initialvalue="", parent=self.root)
        if not prix_str:
            return
        try:
            prix = float(prix_str.replace(" ", "").replace(",", "."))
        except ValueError:
            messagebox.showerror("Erreur", "Prix invalide.", parent=self.root)
            return
        if prix <= 0:
            messagebox.showerror("Erreur", "Le prix doit etre superieur a 0.", parent=self.root)
            return

        qte = int(self.var_qte.get() or 1)
        ref = f"PRD-TMP-{int(datetime.now().timestamp())}"

        # Chercher une categorie "Non classe" ou la premiere disponible
        cats = db.get_categories()
        cat_id = next((c["id"] for c in cats if c["nom"].lower().startswith("non")), None)
        if not cat_id and cats:
            cat_id = cats[0]["id"]

        ok, msg = db.add_produit(
            ref, nom.strip(), prix_vente=prix, prix_achat=0,
            stock_vente=qte, stock_reserve=0, categorie_id=cat_id or 1,
            description="Ajouté depuis la caisse")
        if not ok:
            messagebox.showerror("Erreur", msg, parent=self.root)
            return

        produit = db.trouver_produit(ref) or db.get_produits(search=nom.strip(), inclure_inactifs=False)
        if produit:
            pid = produit[0]["id"] if isinstance(produit, list) else produit["id"]
            self._ajouter_produit_panier(pid, qte)
            self.recherche_caisse.effacer()
            self.recherche_caisse.entry.focus_set()
            self._charger_catalogue_caisse()
            self.statut(f"✅ {nom.strip()} ajoute au catalogue et au panier", COULEURS["success"])


    def _ajouter_produit_panier(self, produit_id, quantite):
        produit = db.get_produit(produit_id)
        if not produit:
            return
        stock_vente = produit.get("stock_vente", produit["stock"])
        deja = sum(l["quantite"] for l in self.panier if l["id"] == produit_id)
        if deja + quantite > stock_vente:
            en_reserve = produit.get("stock_reserve", 0)
            messagebox.showwarning(
                "Stock vente insuffisant",
                f"« {produit['nom']} » : {stock_vente} en rayon"
                + (f", déjà {deja} dans le panier." if deja else ".")
                + (f"\n({en_reserve} en réserve — faites un transfert d'abord.)"
                   if en_reserve else ""), parent=self.root)
            return
        if produit["prix_vente"] <= 0:
            messagebox.showwarning("Prix manquant",
                                   f"« {produit['nom']} » n'a pas de prix de vente défini.",
                                   parent=self.root)
            return

        for ligne in self.panier:
            if ligne["id"] == produit_id:
                ligne["quantite"] += quantite
                break
        else:
            self.panier.append({"id": produit_id, "nom": produit["nom"],
                                "quantite": quantite, "pu": produit["prix_vente"]})
        self.var_qte.set("1")
        self._rafraichir_panier()
        self.statut(f"+{quantite} × {produit['nom']}", COULEURS["success"])


    def _rafraichir_panier(self):
        t = self.tab_panier
        t.delete(*t.get_children())
        for i, l in enumerate(self.panier):
            t.insert("", tk.END, iid=str(i),
                     tags=("pair",) if i % 2 == 0 else ("impair",),
                     values=(l["nom"], l["quantite"], fmt_money(l["pu"]),
                             fmt_money(l["quantite"] * l["pu"])))
        t.tag_configure("impair", background=COULEURS["row_alt"])
        self._maj_total_panier()


    def _maj_total_panier(self):
        total = sum(l["quantite"] * l["pu"] for l in self.panier)
        nb = sum(l["quantite"] for l in self.panier)
        self.lbl_total_panier.configure(text=fmt_money(total, self.devise))
        self.lbl_articles.configure(
            text=f"{nb} article(s) · {len(self.panier)} ligne(s)" if nb else "Panier vide")


    def _retirer_panier(self):
        sel = self.tab_panier.selection()
        if not sel:
            return
        del self.panier[int(sel[0])]
        self._rafraichir_panier()


    def _qte_rapide(self, delta):
        """➕/➖ : ajuste la quantité de la ligne sélectionnée du panier."""
        sel = self.tab_panier.selection()
        if not sel:
            return
        index = int(sel[0])
        ligne = self.panier[index]
        nouvelle = ligne["quantite"] + delta
        if nouvelle <= 0:
            del self.panier[index]
            self._rafraichir_panier()
            return
        produit = db.get_produit(ligne["id"])
        if produit and nouvelle > produit.get("stock_vente", produit["stock"]):
            messagebox.showwarning(
                "Stock vente insuffisant",
                f"Seulement {produit.get('stock_vente', produit['stock'])} en rayon.",
                parent=self.root)
            return
        ligne["quantite"] = nouvelle
        self._rafraichir_panier()
        self.tab_panier.selection_set(sel[0])


    def _modifier_qte_panier(self):
        sel = self.tab_panier.selection()
        if not sel:
            return
        index = int(sel[0])
        ligne = self.panier[index]
        from tkinter import simpledialog
        nouvelle = simpledialog.askinteger(
            "Quantité", f"Quantité pour « {ligne['nom']} » :",
            initialvalue=ligne["quantite"], minvalue=0, maxvalue=99999, parent=self.root)
        if nouvelle is None:
            return
        if nouvelle == 0:
            del self.panier[index]
        else:
            produit = db.get_produit(ligne["id"])
            if produit and nouvelle > produit.get("stock_vente", produit["stock"]):
                messagebox.showwarning(
                    "Stock vente insuffisant",
                    f"Seulement {produit.get('stock_vente', produit['stock'])} en rayon.",
                    parent=self.root)
                return
            ligne["quantite"] = nouvelle
        self._rafraichir_panier()


    def _vider_panier(self):
        if self.panier and messagebox.askyesno("Confirmer", "Vider le panier ?", parent=self.root):
            self.panier.clear()
            self._rafraichir_panier()


    def _encaisser(self):
        if not self.panier:
            messagebox.showinfo("Panier vide", "Ajoutez au moins un article.", parent=self.root)
            return
        sous_total = sum(l["quantite"] * l["pu"] for l in self.panier)
        d = DialoguePaiementSimple(self.root, sous_total, [dict(l) for l in self.panier], db.get_clients())
        infos = d.attendre()
        if not infos:
            return
        items = infos["items_reels"]
        ok, message, vente_id = db.create_vente(
            infos["client_nom"], items, remise=infos["remise"],
            mode_paiement=infos["mode_paiement"], montant_paye=infos["montant_paye"],
            client_id=infos["client_id"])
        if not ok:
            messagebox.showerror("Vente refusee", message, parent=self.root)
            return
        self.panier.clear()
        self._rafraichir_panier()
        self._charger_catalogue_caisse()
        self._charger_hist_caisse()
        self._maj_badge_alertes()
        statut = "Vente " + message + " enregistree"
        self.statut(statut, COULEURS["success"])
        if infos["imprimer"]:
            factures.imprimer_facture(vente_id, format_ticket=True)
        else:
            messagebox.showinfo("Vente enregistree", "Facture " + message, parent=self.root)
        self.recherche_caisse.entry.focus_set()
        # Synchronisation cloud après chaque vente
        self._sync_cloud()


    def _charger_hist_caisse(self):
        t = self.tab_hist_caisse
        t.delete(*t.get_children())
        for v in db.get_ventes(limit=10, inclure_annulees=False):
            t.insert("", tk.END, iid=v["id"],
                     values=(v["numero"] or ("#" + str(v["id"])), fmt_money(v["total"]),
                             str(v["date_vente"])[11:16]))

    # =========== PRODUITS ======================================


