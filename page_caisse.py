"""
SODIPAC - Point de vente (registre)
Recherche + suggestions en temps réel + enregistrement.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

import database as db
import factures
from dialogues import DialoguePaiementSimple
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, fmt_money)


class CaisseMixin:
    """Point de vente — registre, pas caisse temps réel."""

    def afficher_caisse(self):
        if not self.peut("caisse"):
            return self._refus()
        self._nouvelle_page("📝 Enregistrer une vente", 1)

        self.enregistrement = []  # liste de dicts: {id, nom, quantite, pu}

        carte = Carte(self.zone, "")
        carte.pack(fill=tk.BOTH, expand=True)
        c = carte.corps
        c.columnconfigure(0, weight=1)

        # ── Barre de recherche ──
        recherche_frame = tk.Frame(c, bg=COULEURS["card"])
        recherche_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(recherche_frame, text="Chercher un produit (réf, nom, marque)…",
                 font=(POLICE, 9), bg=COULEURS["card"],
                 fg=COULEURS["text_secondary"]).pack(anchor="w")

        self.e_recherche = tk.Entry(recherche_frame, font=(POLICE, 13),
                                    bd=1, relief=tk.SOLID,
                                    bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                                    insertbackground=COULEURS["input_fg"])
        self.e_recherche.pack(fill=tk.X, ipady=8, pady=(2, 0))
        self.e_recherche.bind("<KeyRelease>", self._recherche_typing)
        self.e_recherche.bind("<Return>", self._ajouter_premier)
        self.e_recherche.focus_set()

        # ── Suggestions ──
        self._frame_suggestions = tk.Frame(c, bg=COULEURS["card"])
        self._frame_suggestions.pack(fill=tk.X)

        # ── Ligne qté ──
        ligne_qte = tk.Frame(c, bg=COULEURS["card"])
        ligne_qte.pack(fill=tk.X, pady=(8, 0))
        tk.Label(ligne_qte, text="Quantité", font=(POLICE, 9),
                 bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(side=tk.LEFT)
        self.var_qte = tk.StringVar(value="1")
        tk.Spinbox(ligne_qte, from_=1, to=9999, textvariable=self.var_qte,
                   font=(POLICE, 11), width=4, justify="center").pack(side=tk.LEFT, padx=6)

        # ── Enregistrement ──
        tk.Label(c, text="Enregistrement", font=(POLICE, 10, "bold"),
                 bg=COULEURS["card"], fg=COULEURS["text"]).pack(anchor="w", pady=(16, 4))

        self._frame_enreg = tk.Frame(c, bg=COULEURS["card"],
                                     highlightbackground=COULEURS["border"],
                                     highlightthickness=1)
        self._frame_enreg.pack(fill=tk.BOTH, expand=True)

        # Zone scrollable pour les lignes
        self._canvas_enreg = tk.Canvas(self._frame_enreg, bg=COULEURS["card"],
                                       highlightthickness=0, height=180)
        self._scrollbar = tk.Scrollbar(self._frame_enreg, orient="vertical",
                                       command=self._canvas_enreg.yview)
        self._lignes_frame = tk.Frame(self._canvas_enreg, bg=COULEURS["card"])
        self._lignes_frame.bind("<Configure>",
            lambda e: self._canvas_enreg.configure(scrollregion=self._canvas_enreg.bbox("all")))
        self._canvas_enreg.create_window((0, 0), window=self._lignes_frame, anchor="nw")
        self._canvas_enreg.configure(yscrollcommand=self._scrollbar.set)
        self._canvas_enreg.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Scrollbar visible seulement si nécessaire
        self._lignes_frame.bind("<Configure>", self._maj_scrollbar, add="+")

        # ── Total + bouton ──
        pied = tk.Frame(c, bg=COULEURS["card"])
        pied.pack(fill=tk.X, pady=(8, 0))

        self.lbl_total = tk.Label(pied, text="Total : " + fmt_money(0, self.devise),
                                  font=(POLICE, 18, "bold"),
                                  bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_total.pack(side=tk.LEFT, pady=6)

        btn_enreg = Bouton(pied, "✍️  Enregistrer  (F8)", "success", self._enregistrer, pady=10)
        btn_enreg.pack(side=tk.RIGHT)
        self.root.bind("<F8>", lambda e: self._enregistrer())

        # Message vide
        self._msg_vide = tk.Label(self._lignes_frame,
                                  text="Aucun article. Cherchez un produit ci-dessus.",
                                  font=(POLICE, 10), bg=COULEURS["card"],
                                  fg=COULEURS["text_secondary"])
        self._msg_vide.pack(pady=30)

        self._maj_total()

    # ── Recherche avec suggestions ──

    def _recherche_typing(self, event=None):
        texte = self.e_recherche.get().strip()

        # Vider les suggestions
        for w in self._frame_suggestions.winfo_children():
            w.destroy()

        if not texte:
            return

        resultats = db.get_produits(search=texte, inclure_inactifs=False)[:20]

        for p in resultats:
            cadre = tk.Frame(self._frame_suggestions, bg=COULEURS["card"])
            cadre.pack(fill=tk.X, pady=1)
            cadre._pid = p["id"]

            nom_marque = p["nom"]
            if p.get("marque"):
                nom_marque += f" — {p['marque']}"
            tk.Label(cadre, text=nom_marque, font=(POLICE, 10, "bold"),
                     bg=COULEURS["card"], fg=COULEURS["text"],
                     anchor="w").pack(side=tk.LEFT, padx=8, pady=4)

            sv = p.get("stock_vente", p["stock"])
            stock_label = f"{sv} en rayon"
            stock_color = COULEURS["success"] if sv > p.get("stock_mini", 0) else COULEURS["warning"]
            if sv <= 0:
                stock_color = COULEURS["danger"]

            tk.Label(cadre, text=fmt_money(p["prix_vente"], self.devise),
                     font=(POLICE, 10, "bold"), bg=COULEURS["card"],
                     fg=COULEURS["primary"]).pack(side=tk.RIGHT, padx=8)

            tk.Label(cadre, text=stock_label, font=(POLICE, 8),
                     bg=COULEURS["card"], fg=stock_color).pack(side=tk.RIGHT, padx=4)

            # Clic = ajouter
            for widget in (cadre,) + tuple(cadre.winfo_children()):
                widget.bind("<Button-1>", lambda e, pid=p["id"]: self._ajouter_produit(pid))
                widget.configure(cursor="hand2")

        if not resultats:
            tk.Label(self._frame_suggestions, text="Aucun résultat",
                     font=(POLICE, 10), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).pack(pady=8)

    def _ajouter_premier(self, event=None):
        """Enter dans la recherche = ajouter le 1er résultat."""
        texte = self.e_recherche.get().strip()
        if not texte:
            return

        # Chercher d'abord par scan (réf exacte ou code-barres)
        produit = db.trouver_produit(texte)
        if not produit:
            resultats = db.get_produits(search=texte, inclure_inactifs=False)
            if len(resultats) == 1:
                produit = resultats[0]
            elif len(resultats) > 1:
                produit = resultats[0]  # 1er résultat
            else:
                # Produit introuvable → proposer ajout rapide
                if messagebox.askyesno(
                        "Produit introuvable",
                        f"« {texte} » n'est pas dans le catalogue.\n\n"
                        "L'ajouter maintenant ?",
                        parent=self.root):
                    self._ajout_rapide(texte)
                return

        if produit:
            self._ajouter_produit(produit["id"])
            self.e_recherche.delete(0, tk.END)
            self.e_recherche.focus_set()
            self._recherche_typing()

    def _ajouter_produit(self, produit_id):
        produit = db.get_produit(produit_id)
        if not produit:
            return
        stock_vente = produit.get("stock_vente", produit["stock"])
        qte = int(self.var_qte.get() or 1)

        if produit["prix_vente"] <= 0:
            messagebox.showwarning("Prix manquant",
                                   f"« {produit['nom']} » n'a pas de prix de vente.",
                                   parent=self.root)
            return

        # Cumuler avec la ligne existante si même produit
        for ligne in self.enregistrement:
            if ligne["id"] == produit_id:
                ligne["quantite"] += qte
                self._rafraichir_enregistrement()
                return

        self.enregistrement.append({
            "id": produit_id,
            "nom": produit["nom"],
            "quantite": qte,
            "pu": produit["prix_vente"]
        })
        self.var_qte.set("1")
        self._rafraichir_enregistrement()

    def _ajout_rapide(self, nom_suggere=""):
        """Creer un produit a la volee et l'ajouter."""
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
            messagebox.showerror("Erreur", "Le prix doit être > 0.", parent=self.root)
            return

        ref = f"PRD-TMP-{int(datetime.now().timestamp())}"
        cats = db.get_categories()
        cat_id = next((c["id"] for c in cats if c["nom"].lower().startswith("non")), None)
        if not cat_id and cats:
            cat_id = cats[0]["id"]

        ok, msg = db.add_produit(
            ref, nom.strip(), prix_vente=prix, prix_achat=0,
            stock_vente=1, stock_reserve=0, categorie_id=cat_id or 1,
            description="Ajouté depuis le point de vente")
        if not ok:
            messagebox.showerror("Erreur", msg, parent=self.root)
            return

        produit = db.trouver_produit(ref) or db.get_produits(search=nom.strip(), inclure_inactifs=False)
        if produit:
            pid = produit[0]["id"] if isinstance(produit, list) else produit["id"]
            self._ajouter_produit(pid)
            self.statut(f"✅ {nom.strip()} ajouté", COULEURS["success"])

    # ── Enregistrement (ex-panier) ──

    def _rafraichir_enregistrement(self):
        for w in self._lignes_frame.winfo_children():
            w.destroy()

        if not self.enregistrement:
            self._msg_vide = tk.Label(self._lignes_frame,
                                      text="Aucun article. Cherchez un produit ci-dessus.",
                                      font=(POLICE, 10), bg=COULEURS["card"],
                                      fg=COULEURS["text_secondary"])
            self._msg_vide.pack(pady=30)
        else:
            for i, ligne in enumerate(self.enregistrement):
                bg = COULEURS["row_alt"] if i % 2 == 0 else COULEURS["card"]
                rang = tk.Frame(self._lignes_frame, bg=bg)
                rang.pack(fill=tk.X, ipady=4)

                tk.Label(rang, text=ligne["nom"], font=(POLICE, 10, "bold"),
                         bg=bg, fg=COULEURS["text"], anchor="w").pack(
                    side=tk.LEFT, padx=12, pady=4)

                # Quantité
                qte_frame = tk.Frame(rang, bg=bg)
                qte_frame.pack(side=tk.RIGHT, padx=8)
                qte_frame.bind("<Double-1>", lambda e, idx=i: self._modifier_qte(idx))

                tk.Label(qte_frame, text=f"×{ligne['quantite']}",
                         font=(POLICE, 11), bg=bg,
                         fg=COULEURS["text_secondary"]).pack(side=tk.LEFT, padx=4)
                tk.Label(qte_frame, text="(double-clic)", font=(POLICE, 7),
                         bg=bg, fg=COULEURS["text_secondary"]).pack(side=tk.LEFT)

                # Prix
                total_ligne = ligne["quantite"] * ligne["pu"]
                tk.Label(rang, text=fmt_money(total_ligne, self.devise),
                         font=(POLICE, 10, "bold"), bg=bg,
                         fg=COULEURS["primary"]).pack(side=tk.RIGHT, padx=12)

                # Bouton supprimer
                btn_x = tk.Label(rang, text="✕", font=(POLICE, 11, "bold"),
                                 bg=bg, fg=COULEURS["danger"], cursor="hand2")
                btn_x.pack(side=tk.RIGHT, padx=4)
                btn_x.bind("<Button-1>", lambda e, idx=i: self._retirer_ligne(idx))

        self._maj_total()

    def _maj_scrollbar(self, event=None):
        """Affiche la scrollbar uniquement si des articles sont présents ET débordent."""
        if not self.enregistrement:
            self._scrollbar.pack_forget()
            return
        # after() pour laisser le canvas se stabiliser
        self.root.after(50, self._verifier_scrollbar)

    def _verifier_scrollbar(self):
        try:
            if self._lignes_frame.winfo_reqheight() > self._canvas_enreg.winfo_height():
                self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                self._scrollbar.pack_forget()
        except tk.TclError:
            pass

    def _maj_total(self):
        total = sum(l["quantite"] * l["pu"] for l in self.enregistrement)
        nb = sum(l["quantite"] for l in self.enregistrement)
        self.lbl_total.configure(
            text=f"Total : {fmt_money(total, self.devise)}  ·  {nb} article(s)")

    def _modifier_qte(self, idx):
        ligne = self.enregistrement[idx]
        nouvelle = simpledialog.askinteger(
            "Quantité", f"Quantité pour « {ligne['nom']} » :",
            initialvalue=ligne["quantite"], minvalue=0, maxvalue=99999, parent=self.root)
        if nouvelle is None:
            return
        if nouvelle == 0:
            del self.enregistrement[idx]
        else:
            produit = db.get_produit(ligne["id"])
            if produit and nouvelle > produit.get("stock_vente", produit["stock"]):
                messagebox.showwarning("Stock insuffisant",
                                       f"Seulement {produit.get('stock_vente', produit['stock'])} en rayon.",
                                       parent=self.root)
                return
            ligne["quantite"] = nouvelle
        self._rafraichir_enregistrement()

    def _retirer_ligne(self, idx):
        del self.enregistrement[idx]
        self._rafraichir_enregistrement()

    # ── Encaissement ──

    def _enregistrer(self):
        if not self.enregistrement:
            messagebox.showinfo("Enregistrement vide",
                                "Ajoutez au moins un article.", parent=self.root)
            return

        sous_total = sum(l["quantite"] * l["pu"] for l in self.enregistrement)
        items = [dict(l) for l in self.enregistrement]

        d = DialoguePaiementSimple(self.root, sous_total, items, db.get_clients())
        infos = d.attendre()
        if not infos:
            return

        ok, message, vente_id = db.create_vente(
            infos["client_nom"], infos["items_reels"],
            remise=infos["remise"],
            mode_paiement=infos["mode_paiement"],
            montant_paye=infos["montant_paye"],
            client_id=infos["client_id"])
        if not ok:
            messagebox.showerror("Vente refusée", message, parent=self.root)
            return

        self.enregistrement.clear()
        self._rafraichir_enregistrement()
        self._recherche_typing()
        self._maj_badge_alertes()
        self.statut(f"✅ Vente {message} enregistrée", COULEURS["success"])
        self.e_recherche.focus_set()
        self._sync_cloud()
