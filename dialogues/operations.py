"""Dialogues: operations"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import database as db
import metier_v3 as m3
from ui_widgets import (COULEURS, POLICE, Bouton, AutocompleteCombobox,
                        centrer_fenetre, fmt_money, parse_float)
from .core import DialogueBase

class DialogueMouvement(DialogueBase):
    LIBELLES = {"entree": ("📥 Entrée de stock", "success"),
                "sortie": ("📤 Sortie de stock", "danger"),
                "correction": ("🔧 Correction d'inventaire", "warning"),
                "transfert": ("🔄 Transfert réserve ↔ vente", "info")}

    def __init__(self, parent, type_mvt, produit_id=None) -> None:
        titre, couleur = self.LIBELLES[type_mvt]
        super().__init__(parent, titre, 680, 560)
        self.type_mvt = type_mvt
        self.cible = None
        self.produits = db.get_produits(inclure_inactifs=False)

        f = self.corps
        r = 0

        tk.Label(f, text="Produit *", font=(POLICE, 10, "bold"), bg=COULEURS["bg"],
                 anchor="w").grid(row=r, column=0, sticky="w", pady=6)
        self.cb_prod = AutocompleteCombobox(f, font=(POLICE, 10), width=44)
        self._etiquettes = {f"{p['reference']} — {p['nom']} (Réserve: {p['stock_reserve']} | Rayon: {p['stock_vente']})": p
                            for p in self.produits}
        self.cb_prod.set_completion_list(list(self._etiquettes))
        self.cb_prod.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=6)
        f.columnconfigure(1, weight=1)
        r += 1

        if produit_id:
            for etiquette, p in self._etiquettes.items():
                if p["id"] == produit_id:
                    self.cb_prod.set(etiquette)
                    break

        self.lbl_info = tk.Label(f, text="", font=(POLICE, 9, "bold"), bg=COULEURS["bg"],
                                 fg=COULEURS["info"], justify="left")
        self.lbl_info.grid(row=r, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(0, 6))
        r += 1
        self.cb_prod.bind("<<ComboboxSelected>>", lambda e: self._maj_info())
        self.cb_prod.bind("<KeyRelease>", lambda e: self._maj_info())

        self.var_emp = tk.StringVar(value="vente")
        if type_mvt != "transfert":
            tk.Label(f, text="Emplacement :", font=(POLICE, 10, "bold"),
                     bg=COULEURS["bg"], anchor="w").grid(row=r, column=0, sticky="w", pady=6)
            cadre_emp = tk.Frame(f, bg=COULEURS["bg"])
            cadre_emp.grid(row=r, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=6)
            tk.Radiobutton(cadre_emp, text="Vente (Rayon)", variable=self.var_emp, value="vente",
                           bg=COULEURS["bg"], font=(POLICE, 9, "bold"), command=self._maj_info,
                           activebackground=COULEURS["bg"]).pack(side=tk.LEFT, padx=(0, 12))
            tk.Radiobutton(cadre_emp, text="Réserve (Entrepôt)", variable=self.var_emp, value="reserve",
                           bg=COULEURS["bg"], font=(POLICE, 9, "bold"), command=self._maj_info,
                           activebackground=COULEURS["bg"]).pack(side=tk.LEFT, padx=4)
            r += 1

        if type_mvt == "transfert":
            self.var_dir = tk.StringVar(value="vente")
            tk.Label(f, text="Direction :", font=(POLICE, 10, "bold"),
                     bg=COULEURS["bg"], anchor="w").grid(row=r, column=0, sticky="nw", pady=6)
            cadre_dir = tk.Frame(f, bg=COULEURS["bg"])
            cadre_dir.grid(row=r, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=6)
            tk.Radiobutton(cadre_dir, text="🔴 Réserve (Entrepôt) ➔ 🟢 Rayon (Vente)", variable=self.var_dir, value="vente",
                           bg=COULEURS["bg"], font=(POLICE, 10, "bold"), fg=COULEURS["primary"],
                           activebackground=COULEURS["bg"],
                           command=self._maj_info).pack(anchor="w", pady=(0, 4))
            tk.Radiobutton(cadre_dir, text="🟢 Rayon (Vente) ➔ 🔴 Réserve (Entrepôt)", variable=self.var_dir, value="reserve",
                           bg=COULEURS["bg"], font=(POLICE, 10, "bold"), fg=COULEURS["text"],
                           activebackground=COULEURS["bg"],
                           command=self._maj_info).pack(anchor="w")
            r += 1

        libelle_qte = "Nouveau stock réel *" if type_mvt == "correction" else "Quantité *"
        self.e_qte = self.champ(f, r, libelle_qte, 1); r += 1

        if type_mvt != "transfert":
            self.e_prix = self.champ(f, r, f"Prix unitaire ({db.get_devise()})", 0,
                                     aide="met à jour le prix d'achat" if type_mvt == "entree" else None); r += 1
        else:
            self.e_prix = tk.Entry(f)

        self.e_doc = self.champ(f, r, "Réf. document", "", aide="facture, bon de livraison…"); r += 1
        self.e_notes = self.champ(f, r, "Motif / Notes", ""); r += 1

        if type_mvt == "correction":
            tk.Label(f, text="ℹ️ Saisissez le stock physiquement compté pour l'emplacement sélectionné.",
                     font=(POLICE, 9), bg=COULEURS["bg"], fg=COULEURS["text_secondary"],
                     justify="left").grid(row=r, column=0, columnspan=2, sticky="w", pady=4)
        elif type_mvt == "transfert":
            tk.Label(f, text="ℹ️ Transférer des pièces entre l'entrepôt (réserve) et les rayons du magasin.",
                     font=(POLICE, 9), bg=COULEURS["bg"], fg=COULEURS["text_secondary"],
                     justify="left").grid(row=r, column=0, columnspan=2, sticky="w", pady=4)

        self.boutons("✅ Valider le mouvement")
        self._maj_info()
        self.cb_prod.focus_set()

    def _produit_selectionne(self) -> dict | None:
        val = self.cb_prod.get().strip()
        if not val:
            return None
        p_base = self._etiquettes.get(val)
        if not p_base:
            val_lower = val.lower()
            for p in self.produits:
                ref = str(p.get("reference", "")).lower()
                nom = str(p.get("nom", "")).lower()
                if val_lower == ref or val_lower == nom or (ref and ref in val_lower) or (nom and nom in val_lower):
                    p_base = p
                    break
        if p_base:
            fresh = db.get_produit(p_base["id"])
            return fresh or p_base
        return None

    def _maj_info(self) -> None:
        p = self._produit_selectionne()
        if not p:
            self.lbl_info.configure(text="")
            return
        sr = p.get("stock_reserve", 0)
        sv = p.get("stock_vente", 0)

        if self.type_mvt == "transfert":
            direction = self.var_dir.get() if hasattr(self, 'var_dir') else "vente"
            if direction == "vente":
                dispo = sr
                txt = f"📦 Stock en Réserve : {sr} pièce(s)   │   🛒 Stock en Rayon : {sv} pièce(s)\n👉 Disponible en Réserve pour transfert vers le Rayon : {dispo} pièce(s)"
            else:
                dispo = sv
                txt = f"📦 Stock en Réserve : {sr} pièce(s)   │   🛒 Stock en Rayon : {sv} pièce(s)\n👉 Disponible en Rayon pour transfert vers la Réserve : {dispo} pièce(s)"

            couleur = COULEURS["success"] if dispo > 0 else COULEURS["danger"]
            self.lbl_info.configure(text=txt, fg=couleur)
        else:
            emp = self.var_emp.get() if hasattr(self, 'var_emp') else "vente"
            stock_emp = sr if emp == "reserve" else sv
            nom_emp = "Réserve" if emp == "reserve" else "Rayon"
            txt = f"Stock en {nom_emp} : {stock_emp}   •   Stock total : {p.get('stock',0)}   •   Seuil : {p.get('stock_mini',5)}"
            self.lbl_info.configure(text=txt, fg=COULEURS["info"])
        if self.type_mvt == "entree" and hasattr(self, 'e_prix'):
            try:
                prix_actuel = float(self.e_prix.get().replace(",", ".").replace(" ", "") or 0)
            except ValueError:
                prix_actuel = 0
            if not prix_actuel:
                self.e_prix.delete(0, tk.END)
                self.e_prix.insert(0, f"{p.get('prix_achat', 0):.0f}")

    def valider(self) -> None:
        p = self._produit_selectionne()
        if not p:
            messagebox.showerror("Erreur", "Veuillez sélectionner un produit dans la liste.",
                                 parent=self.dialog)
            return
        try:
            qte_txt = self.e_qte.get().replace(" ", "").replace(",", ".").strip() if hasattr(self, 'e_qte') else "1"
            qte = int(float(qte_txt or 1))
            if qte <= 0:
                qte = 1
        except ValueError:
            messagebox.showerror("Erreur", "La quantité doit être un nombre entier positif.", parent=self.dialog)
            return

        try:
            prix_txt = self.e_prix.get().replace(" ", "").replace(",", ".").strip() if hasattr(self, 'e_prix') else "0"
            prix = float(prix_txt or 0)
        except ValueError:
            prix = 0.0

        doc_txt = self.e_doc.get().strip() if hasattr(self, 'e_doc') else ""
        notes_txt = self.e_notes.get().strip() if hasattr(self, 'e_notes') else ""

        if self.type_mvt == "transfert":
            cible = self.var_dir.get() if hasattr(self, 'var_dir') else "vente"
            ok, msg = db.add_mouvement(p["id"], "transfert", qte, 0,
                                       doc_txt, notes_txt, cible=cible)
        else:
            cible = self.var_emp.get() if hasattr(self, 'var_emp') else "vente"
            ok, msg = db.add_mouvement(p["id"], self.type_mvt, qte, prix,
                                       doc_txt, notes_txt, cible=cible)
        if ok:
            self.result = msg
            self.dialog.destroy()
        else:
            if self.type_mvt == "transfert" and "insuffisant" in msg.lower():
                direction = self.var_dir.get() if hasattr(self, 'var_dir') else "vente"
                source_nom = "Réserve (Entrepôt)" if direction == "vente" else "Rayon (Vente)"
                msg_detail = (f"❌ Transfert impossible !\n\n"
                              f"Le stock en {source_nom} pour « {p.get('nom','')} » est insuffisant (disponible : {p.get('stock_reserve' if direction=='vente' else 'stock_vente', 0)}).\n\n"
                              f"💡 Pour approvisionner la réserve, faites d'abord une « 📥 Entrée de stock » avec l'emplacement Réserve.")
                messagebox.showwarning("Stock Source Vide", msg_detail, parent=self.dialog)
            else:
                messagebox.showerror("Impossible", msg, parent=self.dialog)




# ─── PAIEMENT / ENCAISSEMENT ─────────────────────────

class DialoguePaiement(DialogueBase):
    '''Encaissement : prix reel par ligne, negociation article par article.'''

    MODES = ["Espèces", "Wave", "Orange Money", "MTN Money", "Moov Money", "Crédit"]

    def __init__(self, parent, sous_total, items, clients=None) -> None:
        n_lignes = len(items)
        hauteur = 80 + min(n_lignes, 6) * 72 + 380
        super().__init__(parent, " Encaissement", 860, hauteur)
        self.items = items
        self.clients = clients or []
        self.devise = db.get_devise()

        for l in self.items:
            l["prix_reel"] = l.get("prix_reel") or l["pu"]

        f = self.corps

        # Client
        tk.Label(f, text="Client", font=(POLICE, 10), bg=COULEURS["bg"],
                 anchor="w").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))
        self.cb_client = AutocompleteCombobox(f, font=(POLICE, 10), width=28)
        self._etiq_clients = {c["nom"] + (" - " + c["telephone"] if c["telephone"] else ""): c
                              for c in self.clients}
        self.cb_client.set_completion_list(["Client de passage"] + list(self._etiq_clients))
        self.cb_client.set("Client de passage")
        self.cb_client.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 2))
        f.columnconfigure(2, weight=1)
        self.lbl_dette = tk.Label(f, text="", font=(POLICE, 8), bg=COULEURS["bg"],
                                  fg=COULEURS["warning"], anchor="w")
        self.lbl_dette.grid(row=2, column=0, columnspan=3, sticky="w")

        # Lignes avec prix reel
        self._lignes = []
        start_row = 3
        for idx, l in enumerate(self.items):
            bg_ligne = COULEURS.get("row_alt", COULEURS["bg"]) if idx % 2 == 0 else COULEURS["bg"]
            lf = tk.Frame(f, bg=bg_ligne)
            lf.grid(row=start_row + idx, column=0, columnspan=3, sticky="ew", pady=1, ipady=4)

            infos = tk.Frame(lf, bg=bg_ligne)
            infos.pack(side=tk.LEFT, padx=8)
            tk.Label(infos, text=l["nom"], font=(POLICE, 10, "bold"),
                     bg=bg_ligne, fg=COULEURS["text"]).pack(anchor="w")
            qte_pu = "Qte %d x %s" % (l["quantite"], fmt_money(l["pu"], self.devise))
            tk.Label(infos, text=qte_pu, font=(POLICE, 8),
                     bg=bg_ligne, fg=COULEURS["text_secondary"]).pack(anchor="w")

            ctrl = tk.Frame(lf, bg=bg_ligne)
            ctrl.pack(side=tk.RIGHT, padx=8)
            tk.Label(ctrl, text="Prix vendu :", font=(POLICE, 9),
                     bg=bg_ligne, fg=COULEURS["warning"]).pack(side=tk.LEFT)
            var = tk.StringVar(value="%d" % l["prix_reel"])
            entry = tk.Entry(ctrl, textvariable=var, font=(POLICE, 12, "bold"), width=10,
                             bd=1, relief=tk.SOLID, justify="right",
                             bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                             insertbackground=COULEURS["input_fg"])
            entry.pack(side=tk.LEFT, padx=(4, 0), ipady=2)
            Bouton(ctrl, "cat.", "secondary",
                   lambda i=idx: self._reset_prix(i), petit=True).pack(side=tk.LEFT, padx=(4, 0))

            cout_ligne = 0.0
            try:
                p = db.get_produit(l.get("id", 0))
                if p:
                    cout_ligne = float(p.get("cump") or p.get("prix_achat") or 0) * l["quantite"]
            except Exception:
                import traceback; traceback.print_exc()

            self._lignes.append({
                "idx": idx, "entry": entry, "var": var, "cout": cout_ligne,
                "qte": l["quantite"], "pu_catalogue": l["pu"]
            })
            entry.bind("<KeyRelease>", lambda e, i=idx: self._recalculer())

        sep_row = start_row + n_lignes
        ttk.Separator(f, orient="horizontal").grid(row=sep_row, column=0, columnspan=3, sticky="ew", pady=8)

        tk.Label(f, text="Mode de paiement", font=(POLICE, 10), bg=COULEURS["bg"],
                 anchor="w").grid(row=sep_row + 1, column=0, sticky="w", pady=4)
        self.cb_mode = ttk.Combobox(f, state="readonly", font=(POLICE, 10),
                                    values=self.MODES, width=18)
        self.cb_mode.current(0)
        self.cb_mode.grid(row=sep_row + 1, column=1, sticky="w", padx=(8, 0), pady=4)

        tk.Label(f, text="Somme remise", font=(POLICE, 10, "bold"),
                 bg=COULEURS["bg"], fg=COULEURS["success"]).grid(
            row=sep_row + 2, column=0, sticky="w", pady=(4, 2))
        cadre_paye = tk.Frame(f, bg=COULEURS["bg"])
        cadre_paye.grid(row=sep_row + 2, column=1, columnspan=2, sticky="w", padx=(8, 0))
        self.e_paye = tk.Entry(cadre_paye, font=(POLICE, 15, "bold"), width=12,
                               bd=1, relief=tk.SOLID, justify="right",
                               bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                               insertbackground=COULEURS["input_fg"])
        self.e_paye.pack(side=tk.LEFT, ipady=4)
        self.e_paye.bind("<KeyRelease>", lambda e: self._recalculer())
        self._btns_billets = []
        for montant in (1000, 2000, 5000, 10000):
            b = Bouton(cadre_paye, "+%dk" % (montant // 1000), "secondary",
                       lambda m=montant: self._ajouter(m), petit=True)
            b.pack(side=tk.LEFT, padx=(4, 0))
            self._btns_billets.append(b)
        b = Bouton(cadre_paye, "= total reel", "info",
                   self._montant_exact, petit=True)
        b.pack(side=tk.LEFT, padx=(8, 0))
        self._btns_billets.append(b)

        recap_row = sep_row + 3
        recap = tk.Frame(f, bg=COULEURS["total_bg"], highlightbackground=COULEURS["border"],
                         highlightthickness=1)
        recap.grid(row=recap_row, column=0, columnspan=3, sticky="ew", pady=8)
        self.lbl_recap = tk.Label(recap, text="", font=(POLICE, 12, "bold"),
                                  bg=COULEURS["total_bg"], fg=COULEURS["text"])
        self.lbl_recap.pack(anchor="w", padx=12, pady=(8, 2))
        self.lbl_remise = tk.Label(recap, text="", font=(POLICE, 9),
                                   bg=COULEURS["total_bg"], fg=COULEURS["warning"])
        self.lbl_remise.pack(anchor="w", padx=12, pady=(0, 2))
        self.lbl_cout = tk.Label(recap, text="", font=(POLICE, 9, "bold"),
                                 bg=COULEURS["total_bg"], fg=COULEURS["danger"])
        self.lbl_cout.pack(anchor="w", padx=12)
        self.lbl_rendu = tk.Label(recap, text="", font=(POLICE, 16, "bold"),
                                  bg=COULEURS["total_bg"], fg=COULEURS["success"])
        self.lbl_rendu.pack(anchor="w", padx=12, pady=(2, 8))

        self.var_imprimer = tk.BooleanVar(value=True)
        tk.Checkbutton(f, text="Imprimer le recu apres validation", variable=self.var_imprimer,
                       bg=COULEURS["bg"], font=(POLICE, 9),
                       activebackground=COULEURS["bg"]).grid(row=recap_row + 1, column=0, columnspan=3,
                                                             sticky="w", pady=4)
        self.boutons("Encaisser (F8)")
        self.dialog.bind("<F8>", lambda e: self.valider())
        self._recalculer()

    def _valeur(self, entry, defaut=0.0) -> float:
        try:
            return float(entry.get().replace(" ", "").replace(",", ".") or defaut)
        except ValueError:
            return defaut

    def _client_choisi(self):
        return self._etiq_clients.get(self.cb_client.get().strip())

    def _maj_client(self) -> None:
        client = self._client_choisi()
        t = ""
        if client:
            try:
                import metier_v3
                du = metier_v3.solde_client(client["id"])
                if du > 0:
                    t = "Ce client doit deja " + fmt_money(du, self.devise)
                    plafond = client.get("plafond_credit")
                    if plafond:
                        t += "  (plafond credit: " + fmt_money(plafond, self.devise) + ")"
            except Exception:
                import traceback; traceback.print_exc()
        self.lbl_dette.configure(text=t)
        self._recalculer()

    def _reset_prix(self, idx):
        d = self._lignes[idx]
        d["entry"].delete(0, tk.END)
        d["entry"].insert(0, "%d" % d["pu_catalogue"])
        self._recalculer()

    def _ajouter(self, montant) -> None:
        self.e_paye.delete(0, tk.END)
        self.e_paye.insert(0, "%d" % (self._valeur(self.e_paye) + montant))
        self._recalculer()

    def _montant_exact(self) -> None:
        val = self._prix_reel_total()
        self.e_paye.delete(0, tk.END)
        self.e_paye.insert(0, "%d" % max(0, val))
        self._recalculer()

    def _prix_reel_total(self) -> float:
        return sum(self._valeur(d["entry"]) * d["qte"] for d in self._lignes)

    def _prix_catalogue_total(self) -> float:
        return sum(d["pu_catalogue"] * d["qte"] for d in self._lignes)

    def _recalculer(self) -> None:
        devise = self.devise
        cat_total = self._prix_catalogue_total()
        reel_total = self._prix_reel_total()
        remise = max(0.0, cat_total - reel_total)
        paye = self._valeur(self.e_paye)
        rendu = paye - reel_total
        cout_total = sum(d["cout"] for d in self._lignes)

        t = "Total affiche: %s  ->  Prix vendu: %s" % (
            fmt_money(cat_total, devise), fmt_money(reel_total, devise))
        self.lbl_recap.configure(text=t)

        if remise > 0 and cat_total > 0:
            self.lbl_remise.configure(
                text="Rabais accorde: %s (%.1f %%)" % (
                    fmt_money(remise, devise), remise / cat_total * 100),
                fg=COULEURS["warning"])
        else:
            self.lbl_remise.configure(text="Aucune remise", fg=COULEURS["secondary"])

        if cout_total > 0 and 0 < reel_total < cout_total:
            self.lbl_cout.configure(
                text="SOUS LE COUT DE REVIENT (%s) - perte %s" % (
                    fmt_money(cout_total, devise),
                    fmt_money(cout_total - reel_total, devise)))
        else:
            self.lbl_cout.configure(text="")

        if remise > cat_total:
            self.lbl_rendu.configure(text="Remise superieure au total catalogue",
                                     fg=COULEURS["danger"])
        elif self.cb_mode.get() == "Credit":
            client = self._client_choisi()
            txt = "Vente a credit - paiement differe"
            if not client:
                txt = "Credit: choisissez un client enregistre"
            self.lbl_rendu.configure(text=txt, fg=COULEURS["warning"])
        elif rendu >= 0:
            self.lbl_rendu.configure(text="Monnaie a rendre: " + fmt_money(rendu, devise),
                                     fg=COULEURS["success"])
        else:
            self.lbl_rendu.configure(text="Manque " + fmt_money(-rendu, devise),
                                     fg=COULEURS["danger"])

    def valider(self) -> None:
        items_reels = []
        reel_total = 0.0
        cat_total = self._prix_catalogue_total()
        for d in self._lignes:
            pr = max(0.0, self._valeur(d["entry"]))
            if pr <= 0:
                nom = self.items[d["idx"]]["nom"]
                messagebox.showerror("Erreur",
                                     "Le prix vendu de " + nom + " doit etre superieur a 0.",
                                     parent=self.dialog)
                return
            items_reels.append((self.items[d["idx"]]["id"], d["qte"], round(pr, 0)))
            reel_total += pr * d["qte"]

        remise = max(0.0, cat_total - reel_total)
        paye = self._valeur(self.e_paye)
        mode = self.cb_mode.get()

        if remise > cat_total:
            messagebox.showerror("Erreur", "La remise totale depasse le montant catalogue.",
                                 parent=self.dialog)
            return
        if mode == "Credit" and not self._client_choisi():
            messagebox.showerror("Client requis",
                                 "Une vente a credit doit etre liee a un client enregistre.",
                                 parent=self.dialog)
            return
        if mode != "Credit" and paye < reel_total:
            msg = "Le client donne %s pour un total reel de %s." % (
                fmt_money(paye, self.devise), fmt_money(reel_total, self.devise))
            messagebox.showerror("Paiement insuffisant", msg, parent=self.dialog)
            return
        cout_total = sum(d["cout"] for d in self._lignes)
        if cout_total > 0 and reel_total < cout_total:
            msg = ("Le total reel (%s) est INFERIEUR au cout de revient (%s)."
                   " Perte: %s. Confirmer quand meme ?") % (
                       fmt_money(reel_total, self.devise),
                       fmt_money(cout_total, self.devise),
                       fmt_money(cout_total - reel_total, self.devise))
            if not messagebox.askyesno("Vente a perte", msg, parent=self.dialog):
                return

        etiquette = self.cb_client.get().strip()
        client = self._etiq_clients.get(etiquette)
        self.result = {
            "items_reels": items_reels,
            "client_nom": client["nom"] if client else (etiquette or "Client de passage"),
            "client_id": client["id"] if client else None,
            "remise": remise,
            "mode_paiement": mode,
            "montant_paye": paye if mode != "Credit" else 0,
            "imprimer": self.var_imprimer.get(),
        }
        self.dialog.destroy()


# ─── UTILISATEUR ─────────────────────────────────────

class DemanderMontant(simpledialog.Dialog):
    """Petite boîte de dialogue : montant + mode de paiement + référence."""

    def __init__(self, parent, titre, message, montant_max=None,
                 modes=("Espèces", "Wave", "Orange Money", "MTN Money", "Moov Money", "Crédit")):
        self.message = message
        self.montant_max = montant_max
        self.modes = modes
        self.resultat = None
        super().__init__(parent, titre)

    def body(self, master):
        master.configure(bg=COULEURS["card"])
        tk.Label(master, text=self.message, font=(POLICE, 10), bg=COULEURS["card"],
                 fg=COULEURS["text"], justify="left", wraplength=380).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        tk.Label(master, text="Montant", font=(POLICE, 10), bg=COULEURS["card"]).grid(
            row=1, column=0, sticky="w", pady=4)
        self.e_montant = tk.Entry(master, font=(POLICE, 12, "bold"), width=16,
                                  bd=1, relief=tk.SOLID, justify="right")
        self.e_montant.grid(row=1, column=1, sticky="w", padx=8, pady=4, ipady=3)
        if self.montant_max:
            self.e_montant.insert(0, f"{self.montant_max:.0f}")
            self.e_montant.select_range(0, tk.END)

        tk.Label(master, text="Mode", font=(POLICE, 10), bg=COULEURS["card"]).grid(
            row=2, column=0, sticky="w", pady=4)
        self.cb_mode = ttk.Combobox(master, state="readonly", width=18,
                                    font=(POLICE, 10), values=list(self.modes))
        self.cb_mode.current(0)
        self.cb_mode.grid(row=2, column=1, sticky="w", padx=8, pady=4)

        tk.Label(master, text="Référence", font=(POLICE, 10), bg=COULEURS["card"]).grid(
            row=3, column=0, sticky="w", pady=4)
        self.e_ref = tk.Entry(master, font=(POLICE, 10), width=22, bd=1, relief=tk.SOLID)
        self.e_ref.grid(row=3, column=1, sticky="w", padx=8, pady=4, ipady=2)
        if self.montant_max:
            tk.Label(master, text=f"Maximum : {fmt_money(self.montant_max)}",
                     font=(POLICE, 8), bg=COULEURS["card"],
                     fg=COULEURS["text_secondary"]).grid(
                row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
        return self.e_montant

    def validate(self):
        montant = parse_float(self.e_montant.get())
        if montant <= 0:
            messagebox.showwarning("Montant invalide",
                                   "Saisissez un montant supérieur à 0.", parent=self)
            return False
        if self.montant_max and montant > self.montant_max + 0.01:
            messagebox.showwarning(
                "Montant trop élevé",
                f"Le maximum est {fmt_money(self.montant_max)}.", parent=self)
            return False
        return True

    def apply(self):
        self.resultat = (parse_float(self.e_montant.get()), self.cb_mode.get(),
                         self.e_ref.get().strip())


# ═══════════════════════════════════════════════════════
# DialoguePaiementSimple — 1 champ prix, 4 modes, ultra-rapide
# ═══════════════════════════════════════════════════════

class DialoguePaiementSimple(DialogueBase):
    """Enregistrement de vente — enregistrement rapide. Prix vendu + mode + client."""

    MODES = ["Espèces", "Wave", "Orange Money", "MTN Money", "Moov Money", "Crédit"]

    def __init__(self, parent, sous_total, items, clients=None) -> None:
        super().__init__(parent, "Enregistrer une vente", 500, 580)
        self.dialog.minsize(480, 560)
        self.items = items
        self.clients = clients or []
        self.devise = db.get_devise()
        self._cout_total = self._calculer_cout(items)
        self._prix_catalogue = sous_total

        f = self.corps

        # ── Résumé panier ──
        nb_articles = sum(l["quantite"] for l in items)
        nb_lignes = len(items)
        tk.Label(f, text=f"{nb_articles} article(s) · {nb_lignes} ligne(s)",
                 font=(POLICE, 10, "bold"), bg=COULEURS["bg"],
                 fg=COULEURS["text"]).pack(anchor="w")
        tk.Label(f, text=f"Total catalogue : {fmt_money(sous_total, self.devise)}",
                 font=(POLICE, 9), bg=COULEURS["bg"],
                 fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(0, 6))

        # ── Prix vendu ──
        tk.Label(f, text="Prix vendu net (F CFA)", font=(POLICE, 11, "bold"),
                 bg=COULEURS["bg"], fg=COULEURS["primary"]).pack(anchor="w")
        self.e_prix_vendu = tk.Entry(f, font=(POLICE, 18, "bold"), width=14,
                                     bd=2, relief=tk.SOLID, justify="center",
                                     bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                                     insertbackground=COULEURS["input_fg"])
        self.e_prix_vendu.insert(0, str(int(sous_total)))
        self.e_prix_vendu.pack(pady=(2, 0), ipady=4)
        self.e_prix_vendu.select_range(0, tk.END)
        self.e_prix_vendu.focus_set()

        # ── Alerte sous le coût ──
        self.lbl_alerte = tk.Label(f, text="", font=(POLICE, 9),
                                   bg=COULEURS["bg"], fg=COULEURS["danger"])
        self.lbl_alerte.pack(anchor="w", pady=(2, 0))
        self.e_prix_vendu.bind("<KeyRelease>", lambda e: self._maj_alerte())

        # ── Mode de paiement ──
        tk.Label(f, text="Mode de paiement :", font=(POLICE, 10, "bold"),
                 bg=COULEURS["bg"], fg=COULEURS["text"]).pack(anchor="w", pady=(8, 2))
        self.cb_mode = ttk.Combobox(f, state="readonly", font=(POLICE, 10),
                                    values=self.MODES, width=24)
        self.cb_mode.current(0)
        self.cb_mode.pack(anchor="w", ipady=2)
        self.cb_mode.bind("<<ComboboxSelected>>", lambda e: self._maj_ui())

        # ── Client (Toujours accessible & obligatoire en crédit) ──
        self._etiq_clients = {
            f"{c['nom']}" + (f" ({c['telephone']})" if c.get('telephone') else ""): c
            for c in self.clients
        }

        self._frame_client = tk.Frame(f, bg=COULEURS["bg"])
        self._frame_client.pack(fill=tk.X, pady=(8, 0))

        tk.Label(self._frame_client, text="Client de la vente :", font=(POLICE, 10, "bold"),
                 bg=COULEURS["bg"], fg=COULEURS["text"]).pack(anchor="w", pady=(0, 2))

        f_cl_input = tk.Frame(self._frame_client, bg=COULEURS["bg"])
        f_cl_input.pack(fill=tk.X)

        self.cb_client = AutocompleteCombobox(f_cl_input, font=(POLICE, 10))
        liste_cl = ["Client de passage (Comptant)"] + list(self._etiq_clients.keys())
        self.cb_client.set_completion_list(liste_cl)
        self.cb_client.set("Client de passage (Comptant)")
        self.cb_client.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cb_client.bind("<<ComboboxSelected>>", lambda e: self._maj_ui())

        Bouton(f_cl_input, "➕ Nouveau Client", "secondary", self._nouveau_client_rapide, petit=True).pack(side=tk.RIGHT, padx=(6, 0))

        self.lbl_credit_warn = tk.Label(self._frame_client, text="", font=(POLICE, 9, "bold"),
                                        bg=COULEURS["bg"], fg=COULEURS["warning"])
        self.lbl_credit_warn.pack(anchor="w", pady=(4, 0))

        self._maj_alerte()
        self._maj_ui()
        self.boutons("✍️ Enregistrer la vente")

    def _nouveau_client_rapide(self):
        nom = simpledialog.askstring("Nouveau client", "Nom complet du client :", parent=self.dialog)
        if not nom or not nom.strip():
            return
        tel = simpledialog.askstring("Nouveau client", f"Téléphone pour « {nom.strip()} » (optionnel) :", parent=self.dialog) or ""

        ok, msg = db.add_client(nom.strip(), tel.strip())
        if ok:
            self.clients = db.get_clients()
            self._etiq_clients = {
                f"{c['nom']}" + (f" ({c['telephone']})" if c.get('telephone') else ""): c
                for c in self.clients
            }
            liste_cl = ["Client de passage (Comptant)"] + list(self._etiq_clients.keys())
            self.cb_client.set_completion_list(liste_cl)

            cle = next((k for k, v in self._etiq_clients.items() if v["nom"].lower() == nom.strip().lower()), None)
            if cle:
                self.cb_client.set(cle)
            self._maj_ui()
        else:
            messagebox.showerror("Erreur", msg, parent=self.dialog)

    def _calculer_cout(self, items):
        total = 0.0
        for l in items:
            p = db.get_produit(l["id"])
            if p:
                total += float(p.get("cump") or p.get("prix_achat") or 0) * l["quantite"]
        return total

    def _prix_vendu(self):
        try:
            return float(self.e_prix_vendu.get().replace(" ", "").replace(",", "."))
        except ValueError:
            return 0.0

    def _maj_alerte(self):
        prix = self._prix_vendu()
        if prix > 0 and self._cout_total > 0 and prix < self._cout_total:
            perte = self._cout_total - prix
            self.lbl_alerte.configure(
                text=f"⚠️ Sous le coût ({fmt_money(self._cout_total, self.devise)}) — Perte : {fmt_money(perte, self.devise)}")
        else:
            self.lbl_alerte.configure(text="")

    def _maj_ui(self):
        mode = self.cb_mode.get()
        client = self._client_choisi()

        if mode == "Crédit":
            if not client:
                self.lbl_credit_warn.configure(text="⚠️ Vente à crédit exige de sélectionner ou créer un client !", fg=COULEURS["danger"])
            else:
                solde = float(client.get("solde_creances", 0) or client.get("dette", 0) or 0)
                txt = f"Vente à crédit attribuée à « {client['nom']} »"
                if solde > 0:
                    txt += f"  ·  ⚠️ Encours actuel : {fmt_money(solde, self.devise)}"
                self.lbl_credit_warn.configure(text=txt, fg=COULEURS["warning"])
        else:
            self.lbl_credit_warn.configure(text="", fg=COULEURS["text_secondary"])

    def _client_choisi(self):
        etiquette = self.cb_client.get().strip()
        if not etiquette or etiquette.startswith("Client de passage"):
            return None
        if etiquette in self._etiq_clients:
            return self._etiq_clients[etiquette]
        # Recherche tolérante par nom ou téléphone
        for k, v in self._etiq_clients.items():
            if v["nom"].lower() in etiquette.lower() or etiquette.lower() in k.lower():
                return v
        for c in self.clients:
            if c["nom"].lower() in etiquette.lower() or (c.get("telephone") and c["telephone"] in etiquette):
                return c
        return None

    def valider(self):
        prix_vendu = self._prix_vendu()
        if prix_vendu <= 0:
            messagebox.showerror("Erreur", "Le prix vendu doit être supérieur à 0.",
                                 parent=self.dialog)
            return

        mode = self.cb_mode.get()

        if mode == "Crédit":
            client = self._client_choisi()
            if not client:
                messagebox.showerror("Client requis",
                                     "Une vente à crédit nécessite un client enregistré.",
                                     parent=self.dialog)
                return

        # Alerte vente à perte
        if self._cout_total > 0 and prix_vendu < self._cout_total:
            msg = (f"Le prix vendu ({fmt_money(prix_vendu, self.devise)}) est "
                   f"inférieur au coût ({fmt_money(self._cout_total, self.devise)}).\n\n"
                   f"Perte : {fmt_money(self._cout_total - prix_vendu, self.devise)}\n\n"
                   f"Confirmer quand même ?")
            if not messagebox.askyesno("Vente à perte", msg, parent=self.dialog):
                return

        # Répartition proportionnelle
        items_reels = []
        cat_total = self._prix_catalogue
        ratio = prix_vendu / cat_total if cat_total > 0 else 1.0
        for l in self.items:
            pu_reel = round(l["pu"] * ratio, 0)
            items_reels.append((l["id"], l["quantite"], pu_reel))

        client = self._client_choisi() if mode == "Crédit" else None
        self.result = {
            "items_reels": items_reels,
            "client_nom": client["nom"] if client else "Client de passage",
            "client_id": client["id"] if client else None,
            "remise": 0.0,
            "mode_paiement": mode,
            "montant_paye": prix_vendu if mode != "Crédit" else 0,
            "imprimer": False,
        }
        self.dialog.destroy()

