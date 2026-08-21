
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import database as db
import metier_v3 as m3
from ui_widgets import (COULEURS, POLICE, Bouton, Carte,
                        EntreeRecherche, TableauTriable, fmt_date, fmt_money,
                        zebre, ajouter_scrollbars, parse_float)
from dialogues import (DialogueCompatibilite, DialogueModele)

class VehiculesMixin:
    """Mixin : Recherche par véhicule."""

# ═══════════════════════════════════════════════════
    #  🚗 RECHERCHE PAR VÉHICULE
    # ═══════════════════════════════════════════════════

    def afficher_recherche_vehicule(self):
        self._nouvelle_page("Quelle pièce pour quel véhicule ?",
                            self._idx_menu("Véhicules"))

        Bouton(self.zone_actions, "Lier une pièce", "primary",
               self._lier_compatibilite, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "Nouveau modèle", "info",
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

        Bouton(ligne, "Chercher", "primary", self._chercher_vehicule,
               petit=True).pack(side=tk.LEFT, padx=4)
        Bouton(ligne, "Réinitialiser", "secondary", self._reset_vehicule,
               petit=True).pack(side=tk.LEFT, padx=4)

        ligne2 = tk.Frame(filtre.corps, bg=COULEURS["card"])
        ligne2.pack(fill=tk.X, pady=(8, 0))
        tk.Label(ligne2, text="Ou par référence / code-barres / équivalent :",
                 font=(POLICE, 9), bg=COULEURS["card"]).pack(side=tk.LEFT)
        self.e_ref_univ = tk.Entry(ligne2, font=(POLICE, 10), width=26, bd=1, relief=tk.SOLID)
        self.e_ref_univ.pack(side=tk.LEFT, padx=6, ipady=2)
        self.e_ref_univ.bind("<Return>", lambda e: self._chercher_reference())
        Bouton(ligne2, "Chercher la référence", "info", self._chercher_reference,
               petit=True).pack(side=tk.LEFT, padx=4)

        self.lbl_vehic_resume = tk.Label(ligne2, text="", font=(POLICE, 9),
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
            annee=int(parse_float(self.e_annee.get(), 0)),
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
        certitudes = {"confirme": "Confirmé", "probable": "Probable",
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
        self.var_qte.set("1")
        self._ajouter_produit(produit_id)
        self.statut(f"« {p['nom']} » ajouté à l'enregistrement", COULEURS["success"])

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
