
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import database as db
import metier_v3 as m3
from ui_widgets import (COULEURS, POLICE, Bouton, Carte,
                        TableauTriable, fmt_date, fmt_money, zebre,
                        ajouter_scrollbars)
from dialogues import (DemanderMontant, DialogueCommande, DialogueReception)

class AchatsMixin:
    """Mixin : Achats fournisseur."""

# ═══════════════════════════════════════════════════
    #  🛒 ACHATS / COMMANDES FOURNISSEUR
    # ═══════════════════════════════════════════════════

    def afficher_achats(self):
        if not self.peut("stock"):
            return self._refus()
        self._nouvelle_page("🛒 Achats — commandes fournisseur", self._idx_menu("Achats"))

        Bouton(self.zone_actions, "➕ Nouvelle commande", "primary",
               self._nouvelle_commande, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "📨 Marquer envoyée", "info",
               self._envoyer_commande, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "📥 Réceptionner", "success",
               self._receptionner_commande, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "💸 Payer", "warning",
               self._payer_fournisseur, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(self.zone_actions, "✕ Annuler", "danger",
               self._annuler_commande, petit=True).pack(side=tk.LEFT, padx=3)

        barre = tk.Frame(self.zone, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        tk.Label(barre, text="Statut :", font=(POLICE, 9), bg=COULEURS["bg"]).pack(side=tk.LEFT)
        self.filtre_cmd = ttk.Combobox(
            barre, state="readonly", width=14, font=(POLICE, 9),
            values=["Toutes", "Brouillon", "Envoyée", "Partielle", "Reçue", "Annulée"])
        self.filtre_cmd.current(0)
        self.filtre_cmd.pack(side=tk.LEFT, padx=(4, 14))
        self.filtre_cmd.bind("<<ComboboxSelected>>", lambda e: self._charger_commandes())
        self.lbl_resume_cmd = tk.Label(barre, text="", font=(POLICE, 9, "bold"),
                                       bg=COULEURS["bg"], fg=COULEURS["primary"])
        self.lbl_resume_cmd.pack(side=tk.RIGHT, padx=8)

        conteneur = tk.Frame(self.zone, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        c1 = Carte(conteneur, "Commandes")
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        f_tree_c1 = tk.Frame(c1.corps, bg=COULEURS["card"])
        f_tree_c1.pack(fill=tk.BOTH, expand=True)
        self.tab_commandes = TableauTriable(f_tree_c1, [
            ("num", "N° commande", 130, "w", False),
            ("fourn", "Fournisseur", 170, "w", False),
            ("date", "Date", 100, "w", False),
            ("prevue", "Prévue le", 95, "w", False),
            ("depot", "Dépôt", 110, "w", False),
            ("lignes", "Lignes", 55, "center", True),
            ("total", "Total", 105, "e", True),
            ("reste", "À recevoir", 85, "center", True),
            ("statut", "Statut", 95, "center", False)], height=15)
        ajouter_scrollbars(f_tree_c1, self.tab_commandes)
        self.tab_commandes.bind("<<TreeviewSelect>>", lambda e: self._charger_cmd_lignes())

        c2 = Carte(conteneur, "Détail de la commande")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        f_tree_c2 = tk.Frame(c2.corps, bg=COULEURS["card"])
        f_tree_c2.pack(fill=tk.BOTH, expand=True)
        self.tab_cmd_lignes = TableauTriable(f_tree_c2, [
            ("ref", "Réf.", 90, "w", False),
            ("nom", "Article", 150, "w", False),
            ("cmd", "Cmdé", 50, "center", True),
            ("recu", "Reçu", 50, "center", True),
            ("pu", "P.U.", 80, "e", True)], height=15)
        ajouter_scrollbars(f_tree_c2, self.tab_cmd_lignes)
        self.lbl_cmd_detail = tk.Label(c2.corps, text="Sélectionnez une commande",
                                       font=(POLICE, 9), bg=COULEURS["card"],
                                       fg=COULEURS["text_secondary"], justify="left")
        self.lbl_cmd_detail.pack(anchor="w", pady=(8, 0))

        self._charger_commandes()

    def _charger_commandes(self):
        statuts = {"Toutes": "", "Brouillon": "brouillon", "Envoyée": "envoyee",
                   "Partielle": "partielle", "Reçue": "recue", "Annulée": "annulee"}
        cmds = m3.get_commandes(statut=statuts.get(self.filtre_cmd.get(), ""))
        libelles = {"brouillon": "📝 Brouillon", "envoyee": "📨 Envoyée",
                    "partielle": "📦 Partielle", "recue": "✅ Reçue",
                    "annulee": "❌ Annulée"}
        t = self.tab_commandes
        t.delete(*t.get_children())
        total = 0.0
        for i, c in enumerate(cmds):
            if c["statut"] != "annulee":
                total += c["total"]
            tags = ("alerte",) if c["statut"] == "partielle" else ()
            t.insert("", tk.END, iid=c["id"], tags=zebre(i, tags), values=(
                c["numero"] or f"#{c['id']}", c["fournisseur_nom"] or "—",
                fmt_date(c["date_commande"], False), c["date_prevue"] or "—",
                c["depot_nom"] or "—", c["nb_lignes"], fmt_money(c["total"]),
                c["reste_a_recevoir"] or 0,
                libelles.get(c["statut"], c["statut"])))
        self.lbl_resume_cmd.configure(
            text=f"{len(cmds)} commande(s) · {fmt_money(total, self.devise)}")
        self._charger_cmd_lignes()

    def _charger_cmd_lignes(self):
        sel = self.tab_commandes.selection()
        t = self.tab_cmd_lignes
        t.delete(*t.get_children())
        if not sel:
            self.lbl_cmd_detail.configure(text="Sélectionnez une commande")
            return
        cid = int(sel[0])
        for i, l in enumerate(m3.get_commande_details(cid)):
            manque = l["quantite"] > l["quantite_recue"]
            t.insert("", tk.END, iid=l["id"], tags=zebre(i, ("alerte",) if manque else ()),
                     values=(l["reference"] or "—",
                             l["produit_nom"] or l["designation"] or "—",
                             l["quantite"], l["quantite_recue"],
                             fmt_money(l["prix_unitaire"])))
        cmd = next((c for c in m3.get_commandes() if c["id"] == cid), None)
        if cmd:
            dette = next((d for d in m3.get_dettes_fournisseur()
                          if d["commande_id"] == cid), None)
            texte = (f"Sous-total : {fmt_money(cmd['sous_total'], self.devise)}\n"
                     f"Remise : {fmt_money(cmd['remise'], self.devise)}  ·  "
                     f"Frais : {fmt_money(cmd['frais'], self.devise)}\n"
                     f"TOTAL : {fmt_money(cmd['total'], self.devise)}")
            if dette:
                texte += (f"\nPayé : {fmt_money(dette['total_paye'], self.devise)}\n"
                          f"RESTE À PAYER : {fmt_money(dette['reste_a_payer'], self.devise)}")
            elif cmd["statut"] in ("recue", "partielle"):
                texte += "\n✅ Intégralement payée"
            if cmd["notes"]:
                texte += f"\nNotes : {cmd['notes']}"
            self.lbl_cmd_detail.configure(text=texte)

    def _nouvelle_commande(self):
        fournisseurs = db.get_fournisseurs()
        if not fournisseurs:
            messagebox.showwarning("Aucun fournisseur",
                                   "Créez d'abord un fournisseur (menu Fournisseurs).",
                                   parent=self.root)
            return
        d = DialogueCommande(self.root, self.devise)
        if d.resultat:
            fid, items, depot_id, frais, prevue, notes = d.resultat
            ok, msg, _ = m3.creer_commande(fid, items, depot_id=depot_id, frais=frais,
                                           date_prevue=prevue, notes=notes)
            messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
            if ok:
                self.statut(msg, COULEURS["success"])
                self._charger_commandes()

    def _cmd_selectionnee(self):
        sel = self.tab_commandes.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez une commande.",
                                parent=self.root)
            return None
        return int(sel[0])

    def _envoyer_commande(self):
        cid = self._cmd_selectionnee()
        if cid is None:
            return
        ok, msg = m3.envoyer_commande(cid)
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self._charger_commandes()

    def _receptionner_commande(self):
        cid = self._cmd_selectionnee()
        if cid is None:
            return
        lignes = [l for l in m3.get_commande_details(cid)
                  if l["quantite"] > l["quantite_recue"]]
        if not lignes:
            messagebox.showinfo("Information",
                                "Cette commande est entièrement réceptionnée.",
                                parent=self.root)
            return
        d = DialogueReception(self.root, cid, lignes, self.devise)
        if d.resultat is None:
            return
        ok, msg = m3.receptionner_commande(cid, d.resultat or None, d.depot_id)
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self.statut(msg, COULEURS["success"])
            self._charger_commandes()
            self._maj_badge_alertes()

    def _payer_fournisseur(self):
        cid = self._cmd_selectionnee()
        if cid is None:
            return
        dette = next((d for d in m3.get_dettes_fournisseur() if d["commande_id"] == cid), None)
        if not dette:
            messagebox.showinfo("Information",
                                "Rien à payer sur cette commande "
                                "(non réceptionnée ou déjà soldée).", parent=self.root)
            return
        d = DemanderMontant(
            self.root, "Payer le fournisseur",
            f"Commande {dette['numero']} — {dette['fournisseur_nom']}\n"
            f"Total {fmt_money(dette['total'], self.devise)} · "
            f"payé {fmt_money(dette['total_paye'], self.devise)}\n"
            f"Reste à payer : {fmt_money(dette['reste_a_payer'], self.devise)}",
            montant_max=dette["reste_a_payer"])
        if not d.resultat:
            return
        montant, mode, ref = d.resultat
        ok, msg = m3.payer_fournisseur(cid, montant, mode, ref)
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self._charger_commandes()

    def _annuler_commande(self):
        cid = self._cmd_selectionnee()
        if cid is None:
            return
        if not messagebox.askyesno("Confirmer", "Annuler cette commande ?",
                                   parent=self.root, icon="warning"):
            return
        ok, msg = m3.annuler_commande(cid)
        messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
        if ok:
            self._charger_commandes()
