"""Dialogues: v3"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

import database as db
import metier_v3 as m3
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, fmt_date, fmt_money,
                        parse_float, TableauTriable, ajouter_scrollbars, zebre,
                        EntreeRecherche)


class _Base(simpledialog.Dialog):
    """Socle commun : fond thémé + résultat."""

    def __init__(self, parent, titre):
        self.resultat = None
        super().__init__(parent, titre)

    def _label(self, master, texte, ligne):
        tk.Label(master, text=texte, font=(POLICE, 10), bg=COULEURS["card"],
                 fg=COULEURS["text"], anchor="w").grid(row=ligne, column=0,
                                                       sticky="w", pady=4)

    def _entree(self, master, ligne, largeur=26, defaut=""):
        e = tk.Entry(master, font=(POLICE, 10), width=largeur, bd=1, relief=tk.SOLID,
                     bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                     insertbackground=COULEURS["input_fg"])
        if defaut:
            e.insert(0, str(defaut))
        e.grid(row=ligne, column=1, sticky="w", padx=8, pady=4, ipady=3)
        return e

class DialogueDepot(_Base):
    def __init__(self, parent, depot=None):
        self.depot = depot
        super().__init__(parent, "Modifier le dépôt" if depot else "Nouveau dépôt")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        d = self.depot or {}
        self._label(master, "Code (3 lettres)", 0)
        self.e_code = self._entree(master, 0, 10, d.get("code", ""))
        self._label(master, "Nom du dépôt", 1)
        self.e_nom = self._entree(master, 1, 28, d.get("nom", ""))
        self._label(master, "Type", 2)
        self.cb_type = ttk.Combobox(master, state="readonly", width=20, font=(POLICE, 10),
                                    values=["boutique", "reserve", "magasin",
                                            "vehicule", "autre"])
        self.cb_type.set(d.get("type", "boutique"))
        self.cb_type.grid(row=2, column=1, sticky="w", padx=8, pady=4)
        self._label(master, "Responsable", 3)
        self.e_resp = self._entree(master, 3, 28, d.get("responsable", ""))
        self._label(master, "Téléphone", 4)
        self.e_tel = self._entree(master, 4, 20, d.get("telephone", ""))
        self._label(master, "Adresse", 5)
        self.e_adr = self._entree(master, 5, 28, d.get("adresse", ""))

        self.var_vente = tk.BooleanVar(value=bool(d.get("autorise_vente", 1)))
        tk.Checkbutton(master, text="On peut vendre depuis ce dépôt",
                       variable=self.var_vente, font=(POLICE, 10), bg=COULEURS["card"],
                       fg=COULEURS["text"], selectcolor=COULEURS["card"],
                       activebackground=COULEURS["card"]).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.var_actif = tk.BooleanVar(value=bool(d.get("actif", 1)))
        if self.depot:
            tk.Checkbutton(master, text="Dépôt actif", variable=self.var_actif,
                           font=(POLICE, 10), bg=COULEURS["card"], fg=COULEURS["text"],
                           selectcolor=COULEURS["card"],
                           activebackground=COULEURS["card"]).grid(
                row=7, column=0, columnspan=2, sticky="w")
        tk.Label(master, text="Un dépôt « réserve » sert au stockage : le stock n'y est\n"
                              "pas vendable tant qu'il n'est pas transféré en boutique.",
                 font=(POLICE, 8), bg=COULEURS["card"],
                 fg=COULEURS["text_secondary"], justify="left").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))
        return self.e_code

    def apply(self):
        code = self.e_code.get().strip().upper()
        nom = self.e_nom.get().strip()
        if self.depot:
            ok, msg = m3.update_depot(
                self.depot["id"], code=code, nom=nom, type=self.cb_type.get(),
                responsable=self.e_resp.get().strip(), telephone=self.e_tel.get().strip(),
                adresse=self.e_adr.get().strip(),
                autorise_vente=1 if self.var_vente.get() else 0,
                actif=1 if self.var_actif.get() else 0)
        else:
            ok, msg = m3.add_depot(code, nom, self.cb_type.get(),
                                   self.e_adr.get().strip(), self.e_resp.get().strip(),
                                   self.e_tel.get().strip(), self.var_vente.get())
        if ok:
            self.resultat = msg
        else:
            messagebox.showwarning("Impossible", msg, parent=self.parent)

class DialogueTransfert(_Base):
    def __init__(self, parent, produits, depots):
        self.produits = produits
        self.depots = depots
        super().__init__(parent, "Transférer du stock entre dépôts")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        self._label(master, "Produit", 0)
        self.cb_produit = ttk.Combobox(
            master, width=42, font=(POLICE, 10),
            values=[f"{p['reference']} — {p['nom']} (stock {p['stock']})"
                    for p in self.produits])
        self.cb_produit.grid(row=0, column=1, sticky="w", padx=8, pady=4)
        self.cb_produit.bind("<<ComboboxSelected>>", lambda e: self._maj_dispo())

        self._label(master, "Depuis le dépôt", 1)
        self.cb_source = ttk.Combobox(master, state="readonly", width=30, font=(POLICE, 10),
                                      values=[f"{d['code']} — {d['nom']}" for d in self.depots])
        self.cb_source.current(0)
        self.cb_source.grid(row=1, column=1, sticky="w", padx=8, pady=4)
        self.cb_source.bind("<<ComboboxSelected>>", lambda e: self._maj_dispo())

        self._label(master, "Vers le dépôt", 2)
        self.cb_dest = ttk.Combobox(master, state="readonly", width=30, font=(POLICE, 10),
                                    values=[f"{d['code']} — {d['nom']}" for d in self.depots])
        self.cb_dest.current(min(1, len(self.depots) - 1))
        self.cb_dest.grid(row=2, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Quantité", 3)
        self.e_qte = self._entree(master, 3, 10, "1")
        self._label(master, "Note (facultatif)", 4)
        self.e_note = self._entree(master, 4, 32)

        self.lbl_dispo = tk.Label(master, text="", font=(POLICE, 9, "bold"),
                                  bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_dispo.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        return self.cb_produit

    def _produit_courant(self):
        idx = self.cb_produit.current()
        return self.produits[idx] if 0 <= idx < len(self.produits) else None

    def _maj_dispo(self):
        p = self._produit_courant()
        if not p:
            return
        etat = m3.get_stock_par_depot(p["id"])
        detail = " · ".join(f"{d['code']} : {d['quantite']}" for d in etat)
        self.lbl_dispo.configure(text=f"Stock actuel — {detail}")

    def validate(self):
        if not self._produit_courant():
            messagebox.showwarning("Produit requis", "Choisissez un produit.", parent=self)
            return False
        if self.cb_source.current() == self.cb_dest.current():
            messagebox.showwarning("Dépôts identiques",
                                   "Choisissez deux dépôts différents.", parent=self)
            return False
        if parse_float(self.e_qte.get()) <= 0:
            messagebox.showwarning("Quantité invalide",
                                   "Saisissez une quantité supérieure à 0.", parent=self)
            return False
        return True

    def apply(self):
        p = self._produit_courant()
        ok, msg = m3.transferer(p["id"], self.depots[self.cb_source.current()]["id"],
                                self.depots[self.cb_dest.current()]["id"],
                                int(parse_float(self.e_qte.get())), self.e_note.get().strip())
        if ok:
            self.resultat = msg
        else:
            messagebox.showwarning("Impossible", msg, parent=self.parent)

class DialogueCommande(_Base):
    """Création d'une commande fournisseur multi-lignes."""

    def __init__(self, parent, devise="F CFA"):
        self.devise = devise
        self.fournisseurs = db.get_fournisseurs()
        self.depots = m3.get_depots()
        self.produits = db.get_produits(inclure_inactifs=False)
        self.lignes = []
        super().__init__(parent, "Nouvelle commande fournisseur")

    def body(self, master):
        master.configure(bg=COULEURS["card"])

        haut = tk.Frame(master, bg=COULEURS["card"])
        haut.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(haut, text="Fournisseur", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=0, column=0, sticky="w")
        self.cb_fourn = ttk.Combobox(haut, state="readonly", width=30, font=(POLICE, 10),
                                     values=[f["nom"] for f in self.fournisseurs])
        self.cb_fourn.current(0)
        self.cb_fourn.grid(row=0, column=1, sticky="w", padx=8)

        tk.Label(haut, text="Dépôt de réception", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.cb_depot = ttk.Combobox(haut, state="readonly", width=22, font=(POLICE, 10),
                                     values=[f"{d['code']} — {d['nom']}" for d in self.depots])
        # Par défaut : la réserve si elle existe
        idx_res = next((i for i, d in enumerate(self.depots)
                        if not d["autorise_vente"]), 0)
        self.cb_depot.current(idx_res)
        self.cb_depot.grid(row=0, column=3, sticky="w", padx=8)

        tk.Label(haut, text="Livraison prévue", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.e_prevue = tk.Entry(haut, font=(POLICE, 10), width=14, bd=1, relief=tk.SOLID)
        self.e_prevue.insert(0, (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))
        self.e_prevue.grid(row=1, column=1, sticky="w", padx=8, pady=(6, 0))

        tk.Label(haut, text="Frais (transport…)", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(6, 0))
        self.e_frais = tk.Entry(haut, font=(POLICE, 10), width=12, bd=1, relief=tk.SOLID,
                                justify="right")
        self.e_frais.insert(0, "0")
        self.e_frais.grid(row=1, column=3, sticky="w", padx=8, pady=(6, 0))

        # ── Ajout de ligne ──
        ajout = tk.Frame(master, bg=COULEURS["bg"], padx=8, pady=8)
        ajout.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        tk.Label(ajout, text="Article", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.cb_prod = ttk.Combobox(
            ajout, width=34, font=(POLICE, 9),
            values=[f"{p['reference']} — {p['nom']}" for p in self.produits])
        self.cb_prod.pack(side=tk.LEFT, padx=4)
        self.cb_prod.bind("<<ComboboxSelected>>", lambda e: self._prix_suggere())
        tk.Label(ajout, text="Qté", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT, padx=(8, 0))
        self.e_qte = tk.Entry(ajout, font=(POLICE, 9), width=6, bd=1, relief=tk.SOLID,
                              justify="center")
        self.e_qte.insert(0, "1")
        self.e_qte.pack(side=tk.LEFT, padx=4)
        tk.Label(ajout, text="P.U. achat", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT, padx=(8, 0))
        self.e_pu = tk.Entry(ajout, font=(POLICE, 9), width=10, bd=1, relief=tk.SOLID,
                             justify="right")
        self.e_pu.pack(side=tk.LEFT, padx=4)
        Bouton(ajout, "➕ Ajouter", "success", self._ajouter_ligne,
               petit=True).pack(side=tk.LEFT, padx=8)
        Bouton(ajout, "🗑️ Retirer", "danger", self._retirer_ligne,
               petit=True).pack(side=tk.LEFT)

        # ── Tableau des lignes ──
        self.tab = TableauTriable(master, [
            ("ref", "Référence", 110, "w", False),
            ("nom", "Article", 230, "w", False),
            ("qte", "Qté", 60, "center", True),
            ("pu", "P.U.", 95, "e", True),
            ("total", "Total", 105, "e", True)], height=8)
        self.tab.grid(row=2, column=0, sticky="nsew")
        master.rowconfigure(2, weight=1)
        master.columnconfigure(0, weight=1)

        self.lbl_total = tk.Label(master, text="Total : 0", font=(POLICE, 12, "bold"),
                                  bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_total.grid(row=3, column=0, sticky="e", pady=(6, 0))

        tk.Label(master, text="Notes", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.e_notes = tk.Entry(master, font=(POLICE, 10), bd=1, relief=tk.SOLID)
        self.e_notes.grid(row=5, column=0, sticky="ew", ipady=3)
        return self.cb_prod

    def _prix_suggere(self):
        idx = self.cb_prod.current()
        if 0 <= idx < len(self.produits):
            p = self.produits[idx]
            self.e_pu.delete(0, tk.END)
            self.e_pu.insert(0, f"{p.get('cump') or p.get('prix_achat') or 0:.0f}")

    def _ajouter_ligne(self):
        idx = self.cb_prod.current()
        if idx < 0:
            messagebox.showwarning("Article requis", "Choisissez un article.", parent=self)
            return
        p = self.produits[idx]
        qte = int(parse_float(self.e_qte.get(), 0))
        pu = parse_float(self.e_pu.get(), 0)
        if qte <= 0:
            messagebox.showwarning("Quantité invalide", "Quantité > 0 requise.", parent=self)
            return
        # Cumul si l'article est déjà dans la commande au même prix
        for l in self.lignes:
            if l["produit_id"] == p["id"] and abs(l["pu"] - pu) < 0.01:
                l["qte"] += qte
                break
        else:
            self.lignes.append({"produit_id": p["id"], "reference": p["reference"],
                                "nom": p["nom"], "qte": qte, "pu": pu})
        self.e_qte.delete(0, tk.END)
        self.e_qte.insert(0, "1")
        self._rafraichir()

    def _retirer_ligne(self):
        sel = self.tab.selection()
        if not sel:
            return
        i = int(sel[0])
        if 0 <= i < len(self.lignes):
            self.lignes.pop(i)
            self._rafraichir()

    def _rafraichir(self):
        self.tab.delete(*self.tab.get_children())
        total = 0.0
        for i, l in enumerate(self.lignes):
            total += l["qte"] * l["pu"]
            self.tab.insert("", tk.END, iid=str(i), tags=zebre(i), values=(
                l["reference"], l["nom"], l["qte"], fmt_money(l["pu"]),
                fmt_money(l["qte"] * l["pu"])))
        frais = parse_float(self.e_frais.get(), 0)
        self.lbl_total.configure(
            text=f"Articles : {fmt_money(total, self.devise)}  +  "
                 f"frais {fmt_money(frais, self.devise)}  =  "
                 f"{fmt_money(total + frais, self.devise)}")

    def validate(self):
        if not self.lignes:
            messagebox.showwarning("Commande vide",
                                   "Ajoutez au moins un article.", parent=self)
            return False
        return True

    def apply(self):
        fid = self.fournisseurs[self.cb_fourn.current()]["id"]
        items = [(l["produit_id"], "", l["qte"], l["pu"]) for l in self.lignes]
        self.resultat = (fid, items, self.depots[self.cb_depot.current()]["id"],
                         parse_float(self.e_frais.get(), 0), self.e_prevue.get().strip(),
                         self.e_notes.get().strip())

class DialogueReception(_Base):
    """Saisie des quantités reçues, ligne par ligne."""

    def __init__(self, parent, commande_id, lignes, devise="F CFA"):
        self.commande_id = commande_id
        self.lignes = lignes
        self.devise = devise
        self.depots = m3.get_depots()
        self.depot_id = None
        self.entrees = {}
        super().__init__(parent, "Réceptionner la commande")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        tk.Label(master, text="Saisissez les quantités RÉELLEMENT reçues.\n"
                              "Laissez la valeur proposée pour tout réceptionner.",
                 font=(POLICE, 10), bg=COULEURS["card"], fg=COULEURS["text"],
                 justify="left").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        tk.Label(master, text="Dépôt de réception", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.cb_depot = ttk.Combobox(master, state="readonly", width=26, font=(POLICE, 10),
                                     values=[f"{d['code']} — {d['nom']}" for d in self.depots])
        idx_res = next((i for i, d in enumerate(self.depots) if not d["autorise_vente"]), 0)
        self.cb_depot.current(idx_res)
        self.cb_depot.grid(row=1, column=1, columnspan=3, sticky="w", padx=8, pady=(0, 8))

        for col, titre in enumerate(("Article", "Commandé", "Déjà reçu", "Reçu maintenant")):
            tk.Label(master, text=titre, font=(POLICE, 9, "bold"), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).grid(row=2, column=col, sticky="w",
                                                         padx=4, pady=(0, 4))
        for i, l in enumerate(self.lignes):
            r = 3 + i
            tk.Label(master, text=f"{l['reference'] or ''} {l['produit_nom'] or l['designation']}",
                     font=(POLICE, 10), bg=COULEURS["card"], fg=COULEURS["text"],
                     anchor="w").grid(row=r, column=0, sticky="w", padx=4, pady=2)
            tk.Label(master, text=str(l["quantite"]), font=(POLICE, 10),
                     bg=COULEURS["card"]).grid(row=r, column=1, padx=4)
            tk.Label(master, text=str(l["quantite_recue"]), font=(POLICE, 10),
                     bg=COULEURS["card"]).grid(row=r, column=2, padx=4)
            e = tk.Entry(master, font=(POLICE, 10, "bold"), width=8, bd=1,
                         relief=tk.SOLID, justify="center")
            e.insert(0, str(l["quantite"] - l["quantite_recue"]))
            e.grid(row=r, column=3, padx=4, pady=2, ipady=2)
            self.entrees[l["id"]] = e

        tk.Label(master, text="⚠ La réception met à jour le CUMP (coût moyen pondéré) "
                              "et donc la valeur de votre stock.",
                 font=(POLICE, 8), bg=COULEURS["card"], fg=COULEURS["warning"],
                 justify="left").grid(row=3 + len(self.lignes), column=0, columnspan=4,
                                      sticky="w", pady=(10, 0))
        return None

    def validate(self):
        total = 0
        for lid, e in self.entrees.items():
            q = parse_float(e.get(), -1)
            if q < 0:
                messagebox.showwarning("Quantité invalide",
                                       "Les quantités doivent être positives.", parent=self)
                return False
            total += q
        if total <= 0:
            messagebox.showwarning("Rien à réceptionner",
                                   "Saisissez au moins une quantité.", parent=self)
            return False
        return True

    def apply(self):
        self.depot_id = self.depots[self.cb_depot.current()]["id"]
        self.resultat = {lid: int(parse_float(e.get(), 0))
                         for lid, e in self.entrees.items() if parse_float(e.get(), 0) > 0}

class DialogueOuvrirInventaire(_Base):
    def __init__(self, parent, depots, categories):
        self.depots = depots
        self.categories = categories
        super().__init__(parent, "Ouvrir un inventaire")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        self._label(master, "Dépôt à inventorier", 0)
        self.cb_depot = ttk.Combobox(master, state="readonly", width=30, font=(POLICE, 10),
                                     values=[f"{d['code']} — {d['nom']}" for d in self.depots])
        self.cb_depot.current(0)
        self.cb_depot.grid(row=0, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Catégorie (facultatif)", 1)
        self.cb_cat = ttk.Combobox(
            master, state="readonly", width=30, font=(POLICE, 10),
            values=["(toutes les catégories)"] + [c["nom"] for c in self.categories])
        self.cb_cat.current(0)
        self.cb_cat.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Notes", 2)
        self.e_notes = self._entree(master, 2, 32)

        tk.Label(master, text="Le stock théorique de chaque produit est figé à l'ouverture.\n"
                              "Vous comptez ensuite physiquement, puis vous clôturez.",
                 font=(POLICE, 8), bg=COULEURS["card"], fg=COULEURS["text_secondary"],
                 justify="left").grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        return self.cb_depot

    def apply(self):
        cat_id = None
        if self.cb_cat.current() > 0:
            cat_id = self.categories[self.cb_cat.current() - 1]["id"]
        self.resultat = (self.depots[self.cb_depot.current()]["id"], cat_id,
                         self.e_notes.get().strip())

class DialogueComptage(_Base):
    def __init__(self, parent, ligne, motifs):
        self.ligne = ligne
        self.motifs = [m.strip() for m in motifs if m.strip()]
        super().__init__(parent, "Saisir le comptage")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        l = self.ligne
        tk.Label(master, text=f"{l['reference']} — {l['produit_nom']}",
                 font=(POLICE, 11, "bold"), bg=COULEURS["card"],
                 fg=COULEURS["text"]).grid(row=0, column=0, columnspan=2,
                                           sticky="w", pady=(0, 4))
        tk.Label(master, text=f"Stock théorique : {l['stock_theorique']}   ·   "
                              f"Emplacement : {l['emplacement'] or '—'}",
                 font=(POLICE, 9), bg=COULEURS["card"],
                 fg=COULEURS["text_secondary"]).grid(row=1, column=0, columnspan=2,
                                                     sticky="w", pady=(0, 10))

        self._label(master, "Quantité comptée", 2)
        self.e_compte = tk.Entry(master, font=(POLICE, 14, "bold"), width=10, bd=1,
                                 relief=tk.SOLID, justify="center")
        valeur = l["stock_compte"] if l["stock_compte"] is not None else l["stock_theorique"]
        self.e_compte.insert(0, str(valeur))
        self.e_compte.select_range(0, tk.END)
        self.e_compte.grid(row=2, column=1, sticky="w", padx=8, pady=4, ipady=3)
        self.e_compte.bind("<KeyRelease>", lambda e: self._maj_ecart())

        self._label(master, "Motif de l'écart", 3)
        self.cb_motif = ttk.Combobox(master, width=24, font=(POLICE, 10),
                                     values=[""] + self.motifs)
        self.cb_motif.set(l["motif"] or "")
        self.cb_motif.grid(row=3, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Notes", 4)
        self.e_notes = self._entree(master, 4, 28, l["notes"] or "")

        self.lbl_ecart = tk.Label(master, text="", font=(POLICE, 11, "bold"),
                                  bg=COULEURS["card"])
        self.lbl_ecart.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._maj_ecart()
        return self.e_compte

    def _maj_ecart(self):
        compte = parse_float(self.e_compte.get(), None)
        if compte is None:
            return
        ecart = int(compte) - self.ligne["stock_theorique"]
        valeur = ecart * (self.ligne["cump_unitaire"] or 0)
        if ecart == 0:
            self.lbl_ecart.configure(text="✅ Conforme au stock théorique",
                                     fg=COULEURS["success"])
        else:
            self.lbl_ecart.configure(
                text=f"{'📈' if ecart > 0 else '📉'} Écart {ecart:+d} "
                     f"→ {fmt_money(valeur)}",
                fg=COULEURS["warning"] if ecart > 0 else COULEURS["danger"])

    def validate(self):
        if parse_float(self.e_compte.get(), -1) < 0:
            messagebox.showwarning("Quantité invalide",
                                   "La quantité comptée doit être >= 0.", parent=self)
            return False
        return True

    def apply(self):
        self.resultat = (int(parse_float(self.e_compte.get(), 0)), self.cb_motif.get().strip(),
                         self.e_notes.get().strip())

class DialogueRetour(_Base):
    """Retour partiel d'une vente."""

    def __init__(self, parent, ventes, devise="F CFA"):
        self.ventes = ventes
        self.devise = devise
        self.lignes_vente = []
        self.entrees = {}
        super().__init__(parent, "Enregistrer un retour")

    def body(self, master):
        master.configure(bg=COULEURS["card"])

        tk.Label(master, text="Vente d'origine", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=0, column=0, sticky="w", pady=4)
        self.cb_vente = ttk.Combobox(
            master, width=52, font=(POLICE, 10),
            values=[f"{v['numero'] or v['id']} — {v['client_nom']} — "
                    f"{fmt_money(v['total'])} — {fmt_date(v['date_vente'], False)}"
                    for v in self.ventes])
        self.cb_vente.grid(row=0, column=1, columnspan=3, sticky="w", padx=8, pady=4)
        self.cb_vente.bind("<<ComboboxSelected>>", lambda e: self._charger_lignes())

        tk.Label(master, text="Motif du retour", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=1, column=0, sticky="w", pady=4)
        self.cb_motif = ttk.Combobox(master, width=32, font=(POLICE, 10),
                                     values=["Ne correspond pas au véhicule",
                                             "Pièce défectueuse", "Erreur de référence",
                                             "Client a changé d'avis", "Doublon", "Autre"])
        self.cb_motif.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        tk.Label(master, text="Remboursement", font=(POLICE, 10),
                 bg=COULEURS["card"]).grid(row=1, column=2, sticky="w", padx=(16, 0))
        self.cb_mode = ttk.Combobox(master, state="readonly", width=14, font=(POLICE, 10),
                                    values=["Espèces", "Avoir", "Échange",
                                            "Wave", "Orange Money"])
        self.cb_mode.current(0)
        self.cb_mode.grid(row=1, column=3, sticky="w", padx=8)

        self.zone_lignes = tk.Frame(master, bg=COULEURS["bg"], padx=8, pady=8)
        self.zone_lignes.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(10, 0))
        master.rowconfigure(2, weight=1)
        tk.Label(self.zone_lignes, text="Choisissez d'abord une vente.",
                 font=(POLICE, 10), bg=COULEURS["bg"],
                 fg=COULEURS["text_secondary"]).pack(anchor="w")

        self.lbl_total_retour = tk.Label(master, text="", font=(POLICE, 12, "bold"),
                                         bg=COULEURS["card"], fg=COULEURS["primary"])
        self.lbl_total_retour.grid(row=3, column=0, columnspan=4, sticky="e", pady=(8, 0))
        return self.cb_vente

    def _charger_lignes(self):
        for w in self.zone_lignes.winfo_children():
            w.destroy()
        self.entrees.clear()
        idx = self.cb_vente.current()
        if idx < 0:
            return
        vente_id = self.ventes[idx]["id"]
        _, lignes = db.get_vente_details(vente_id)

        # Quantités déjà retournées
        conn = db.get_connection()
        deja = {r["produit_id"]: r["q"] for r in conn.execute(
            """SELECT rd.produit_id, SUM(rd.quantite) AS q
               FROM retours_details rd JOIN retours r ON r.id = rd.retour_id
               WHERE r.vente_id = ? AND r.statut = 'valide'
               GROUP BY rd.produit_id""", (vente_id,)).fetchall()}
        

        for col, titre in enumerate(("Article", "Vendu", "Déjà rendu", "À rendre",
                                     "Remettre en stock", "État")):
            tk.Label(self.zone_lignes, text=titre, font=(POLICE, 9, "bold"),
                     bg=COULEURS["bg"], fg=COULEURS["text_secondary"]).grid(
                row=0, column=col, sticky="w", padx=4, pady=(0, 4))

        self.lignes_vente = []
        for i, l in enumerate(lignes):
            if not l["produit_id"]:
                continue
            rendu = deja.get(l["produit_id"], 0)
            reste = l["quantite"] - rendu
            if reste <= 0:
                continue
            r = 1 + len(self.lignes_vente)
            tk.Label(self.zone_lignes, text=f"{l['reference']} {l['produit_nom']}",
                     font=(POLICE, 10), bg=COULEURS["bg"], anchor="w").grid(
                row=r, column=0, sticky="w", padx=4, pady=2)
            tk.Label(self.zone_lignes, text=str(l["quantite"]), font=(POLICE, 10),
                     bg=COULEURS["bg"]).grid(row=r, column=1, padx=4)
            tk.Label(self.zone_lignes, text=str(rendu), font=(POLICE, 10),
                     bg=COULEURS["bg"]).grid(row=r, column=2, padx=4)
            e = tk.Entry(self.zone_lignes, font=(POLICE, 10, "bold"), width=6, bd=1,
                         relief=tk.SOLID, justify="center")
            e.insert(0, "0")
            e.grid(row=r, column=3, padx=4, pady=2)
            e.bind("<KeyRelease>", lambda ev: self._maj_total())
            var_stock = tk.BooleanVar(value=True)
            tk.Checkbutton(self.zone_lignes, variable=var_stock, bg=COULEURS["bg"],
                           activebackground=COULEURS["bg"],
                           selectcolor=COULEURS["card"]).grid(row=r, column=4)
            cb_etat = ttk.Combobox(self.zone_lignes, state="readonly", width=8,
                                   font=(POLICE, 9), values=["neuf", "abime", "hs"])
            cb_etat.current(0)
            cb_etat.grid(row=r, column=5, padx=4)
            self.entrees[l["produit_id"]] = (e, var_stock, cb_etat, l["prix_unitaire"], reste)
            self.lignes_vente.append(l)

        if not self.lignes_vente:
            tk.Label(self.zone_lignes,
                     text="Tous les articles de cette vente ont déjà été retournés.",
                     font=(POLICE, 10), bg=COULEURS["bg"],
                     fg=COULEURS["danger"]).grid(row=1, column=0, columnspan=6, sticky="w")
        self._maj_total()

    def _maj_total(self):
        total = 0.0
        for (e, _v, _c, pu, _reste) in self.entrees.values():
            total += parse_float(e.get(), 0) * pu
        self.lbl_total_retour.configure(
            text=f"Montant du retour : {fmt_money(total, self.devise)}")

    def validate(self):
        if self.cb_vente.current() < 0:
            messagebox.showwarning("Vente requise", "Choisissez la vente d'origine.",
                                   parent=self)
            return False
        total_qte = 0
        for pid, (e, _v, _c, _pu, reste) in self.entrees.items():
            q = parse_float(e.get(), -1)
            if q < 0:
                messagebox.showwarning("Quantité invalide",
                                       "Les quantités doivent être positives.", parent=self)
                return False
            if q > reste:
                messagebox.showwarning(
                    "Quantité trop élevée",
                    f"Vous ne pouvez rendre que {reste} unité(s) de cet article.",
                    parent=self)
                return False
            total_qte += q
        if total_qte <= 0:
            messagebox.showwarning("Retour vide",
                                   "Saisissez au moins une quantité à rendre.", parent=self)
            return False
        return True

    def apply(self):
        vente_id = self.ventes[self.cb_vente.current()]["id"]
        items = []
        for pid, (e, var_stock, cb_etat, pu, _reste) in self.entrees.items():
            q = int(parse_float(e.get(), 0))
            if q > 0:
                items.append((pid, q, pu, var_stock.get(), cb_etat.get()))
        ok, msg, _ = m3.creer_retour(vente_id, items, self.cb_motif.get().strip(),
                                     self.cb_mode.get())
        if ok:
            self.resultat = msg
        else:
            messagebox.showwarning("Impossible", msg, parent=self.parent)

class DialogueCompatibilite(_Base):
    """Lier une pièce à un ou plusieurs modèles de véhicule."""

    def __init__(self, parent, produits, marques):
        self.produits = produits
        self.marques = marques
        super().__init__(parent, "Lier une pièce à un véhicule")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        self._label(master, "Pièce", 0)
        self.cb_prod = ttk.Combobox(
            master, width=44, font=(POLICE, 10),
            values=[f"{p['reference']} — {p['nom']}" for p in self.produits])
        self.cb_prod.grid(row=0, column=1, sticky="w", padx=8, pady=4)
        self.cb_prod.bind("<<ComboboxSelected>>", lambda e: self._maj_existants())

        self._label(master, "Marque", 1)
        self.cb_marque = ttk.Combobox(master, state="readonly", width=20, font=(POLICE, 10),
                                      values=self.marques)
        if self.marques:
            self.cb_marque.current(0)
        self.cb_marque.grid(row=1, column=1, sticky="w", padx=8, pady=4)
        self.cb_marque.bind("<<ComboboxSelected>>", lambda e: self._maj_modeles())

        self._label(master, "Modèle / motorisation", 2)
        self.cb_modele = ttk.Combobox(master, state="readonly", width=44, font=(POLICE, 10))
        self.cb_modele.grid(row=2, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Position", 3)
        self.cb_pos = ttk.Combobox(master, width=18, font=(POLICE, 10),
                                   values=["", "avant", "arrière", "avant gauche",
                                           "avant droit", "arrière gauche", "arrière droit"])
        self.cb_pos.grid(row=3, column=1, sticky="w", padx=8, pady=4)

        self._label(master, "Fiabilité de l'info", 4)
        self.cb_cert = ttk.Combobox(master, state="readonly", width=18, font=(POLICE, 10),
                                    values=["confirme", "probable", "a_verifier"])
        self.cb_cert.current(0)
        self.cb_cert.grid(row=4, column=1, sticky="w", padx=8, pady=4)

        # ── Références croisées ──
        tk.Frame(master, bg=COULEURS["border"], height=1).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=10)
        tk.Label(master, text="Ajouter aussi une référence équivalente (facultatif)",
                 font=(POLICE, 9, "bold"), bg=COULEURS["card"],
                 fg=COULEURS["text_secondary"]).grid(row=6, column=0, columnspan=2,
                                                     sticky="w")
        self._label(master, "Référence", 7)
        self.e_ref = self._entree(master, 7, 22)
        self._label(master, "Type", 8)
        self.cb_type_ref = ttk.Combobox(master, state="readonly", width=18, font=(POLICE, 10),
                                        values=["oem", "equivalent", "fournisseur",
                                                "ancienne", "code_barres"])
        self.cb_type_ref.current(1)
        self.cb_type_ref.grid(row=8, column=1, sticky="w", padx=8, pady=4)
        self._label(master, "Marque de l'équivalent", 9)
        self.e_marque_ref = self._entree(master, 9, 22)

        self.lbl_existants = tk.Label(master, text="", font=(POLICE, 9),
                                      bg=COULEURS["card"], fg=COULEURS["primary"],
                                      justify="left", wraplength=460)
        self.lbl_existants.grid(row=10, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self._maj_modeles()
        return self.cb_prod

    def _maj_modeles(self):
        modeles = m3.get_modeles(self.cb_marque.get())
        self._modeles = modeles
        self.cb_modele.configure(values=[
            f"{m['modele']} {m['motorisation']} "
            f"({m['annee_debut'] or '?'}–{m['annee_fin'] or 'auj.'})".replace("  ", " ")
            for m in modeles])
        if modeles:
            self.cb_modele.current(0)

    def _maj_existants(self):
        idx = self.cb_prod.current()
        if idx < 0:
            return
        p = self.produits[idx]
        compats = m3.get_compatibilites_produit(p["id"])
        refs = m3.get_references_produit(p["id"])
        parties = []
        if compats:
            parties.append("Véhicules déjà liés : " + ", ".join(
                f"{c['marque']} {c['modele']}" for c in compats[:6]))
        if refs:
            parties.append("Références : " + ", ".join(
                f"{r['reference']} ({r['type']})" for r in refs[:5]))
        self.lbl_existants.configure(text="\n".join(parties) or "Aucune liaison existante.")

    def validate(self):
        if self.cb_prod.current() < 0:
            messagebox.showwarning("Pièce requise", "Choisissez une pièce.", parent=self)
            return False
        if self.cb_modele.current() < 0:
            messagebox.showwarning("Modèle requis", "Choisissez un modèle de véhicule.",
                                   parent=self)
            return False
        return True

    def apply(self):
        p = self.produits[self.cb_prod.current()]
        modele = self._modeles[self.cb_modele.current()]
        messages = []
        ok, msg = m3.lier_compatibilite(p["id"], modele["id"], self.cb_pos.get().strip(),
                                        self.cb_cert.get())
        messages.append(msg)
        ref = self.e_ref.get().strip()
        if ref:
            ok2, msg2 = m3.add_reference(p["id"], ref, self.cb_type_ref.get(),
                                         self.e_marque_ref.get().strip())
            messages.append(msg2)
        self.resultat = " · ".join(messages)

class DialogueModele(_Base):
    def __init__(self, parent):
        super().__init__(parent, "Nouveau modèle de véhicule")

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        self._label(master, "Marque", 0)
        self.cb_marque = ttk.Combobox(master, width=24, font=(POLICE, 10),
                                      values=m3.get_marques())
        self.cb_marque.grid(row=0, column=1, sticky="w", padx=8, pady=4)
        self._label(master, "Modèle", 1)
        self.e_modele = self._entree(master, 1, 26)
        self._label(master, "Motorisation", 2)
        self.e_moteur = self._entree(master, 2, 26)
        self._label(master, "Carburant", 3)
        self.cb_carb = ttk.Combobox(master, state="readonly", width=18, font=(POLICE, 10),
                                    values=["essence", "diesel", "hybride", "GPL"])
        self.cb_carb.current(0)
        self.cb_carb.grid(row=3, column=1, sticky="w", padx=8, pady=4)
        self._label(master, "Année de début", 4)
        self.e_debut = self._entree(master, 4, 10)
        self._label(master, "Année de fin (0 = encore produit)", 5)
        self.e_fin = self._entree(master, 5, 10, "0")
        return self.cb_marque

    def validate(self):
        if not self.cb_marque.get().strip() or not self.e_modele.get().strip():
            messagebox.showwarning("Champs requis", "Marque et modèle sont obligatoires.",
                                   parent=self)
            return False
        return True

    def apply(self):
        ok, msg, _ = m3.add_modele(
            self.cb_marque.get().strip(), self.e_modele.get().strip(),
            self.e_moteur.get().strip(), self.cb_carb.get(),
            int(parse_float(self.e_debut.get(), 0)), int(parse_float(self.e_fin.get(), 0)))
        if ok:
            self.resultat = msg
        else:
            messagebox.showwarning("Impossible", msg, parent=self.parent)

