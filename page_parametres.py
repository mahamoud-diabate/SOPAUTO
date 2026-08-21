"""
SOPAUTO - Paramètres
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess

import database as db
import factures
from dialogues import DialogueUtilisateur
from ui_widgets import (COULEURS, POLICE, Bouton, TableauTriable,
                        fmt_date, zebre, ajouter_scrollbars)


class ParametresMixin:
    """Paramètres & administration — entreprise, utilisateurs, sauvegardes.

    Infos entreprise (sur factures), CRUD utilisateurs (3 rôles),
    sauvegardes auto + manuelles, paramètres généraux.
    """

    def afficher_parametres(self):
        if not self.peut("admin"):
            return self._refus()
        self._nouvelle_page("Paramètres", 9)

        onglets = ttk.Notebook(self.zone)
        onglets.pack(fill=tk.BOTH, expand=True)

        # ── Entreprise ──
        page = tk.Frame(onglets, bg=COULEURS["bg"], padx=20, pady=20)
        onglets.add(page, text="Entreprise")

        champs = [("entreprise_nom", "Nom de l'entreprise"),
                  ("entreprise_activite", "Activité"),
                  ("entreprise_adresse", "Adresse"),
                  ("entreprise_telephone", "Téléphone"),
                  ("entreprise_email", "Email"),
                  ("devise", "Devise (ex : F CFA)"),
                  ("prefixe_facture", "Préfixe des factures"),
                  ("pied_facture", "Mention en pied de facture"),
                  ("objectif_ca_mois", "Objectif de CA mensuel (0 = desactive)"),
                  ("dossier_synchro", "Dossier partage (OneDrive, reseau... vide = desactive)")]
        self.champs_params = {}
        params = db.get_parametres()
        for i, (cle, libelle) in enumerate(champs):
            tk.Label(page, text=libelle, font=(POLICE, 10), bg=COULEURS["bg"],
                     anchor="w").grid(row=i, column=0, sticky="w", pady=5)
            e = tk.Entry(page, font=(POLICE, 10), width=42, bd=1, relief=tk.SOLID,
                         bg=COULEURS["input_bg"], fg=COULEURS["input_fg"],
                         insertbackground=COULEURS["input_fg"])
            e.insert(0, params.get(cle, ""))
            e.grid(row=i, column=1, sticky="ew", padx=10, pady=5, ipady=3)
            self.champs_params[cle] = e
        page.columnconfigure(1, weight=1)
        Bouton(page, "Enregistrer les paramètres", "primary",
               self._sauver_params).grid(row=len(champs), column=1, sticky="w", padx=10, pady=16)
        tk.Label(page, text="Ces informations apparaissent sur les factures et les rapports.",
                 font=(POLICE, 9), bg=COULEURS["bg"], fg=COULEURS["text_secondary"]).grid(
            row=len(champs) + 1, column=0, columnspan=2, sticky="w")

        # ── Utilisateurs ──
        page2 = tk.Frame(onglets, bg=COULEURS["bg"], padx=12, pady=12)
        onglets.add(page2, text="Utilisateurs")
        barre = tk.Frame(page2, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        Bouton(barre, "Nouvel utilisateur", "primary",
               self._nouvel_utilisateur, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(barre, "Modifier", "info", self._modifier_utilisateur,
               petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(barre, "Supprimer", "danger", self._supprimer_utilisateur,
               petit=True).pack(side=tk.LEFT, padx=3)

        f_tree_util = tk.Frame(page2, bg=COULEURS["bg"])
        f_tree_util.pack(fill=tk.BOTH, expand=True)
        self.tab_utilisateurs = TableauTriable(f_tree_util, [
            ("login", "Identifiant", 150, "w", False),
            ("nom", "Nom complet", 200, "w", False),
            ("role", "Rôle", 140, "w", False),
            ("actif", "Actif", 70, "center", False),
            ("cree", "Créé le", 140, "w", False),
            ("acces", "Dernier accès", 150, "w", False)], height=12)
        ajouter_scrollbars(f_tree_util, self.tab_utilisateurs)
        self.tab_utilisateurs.bind("<Double-1>", lambda e: self._modifier_utilisateur())
        self._charger_utilisateurs()

        # ── Sauvegardes ──
        page3 = tk.Frame(onglets, bg=COULEURS["bg"], padx=12, pady=12)
        onglets.add(page3, text="Sauvegardes")
        barre = tk.Frame(page3, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        Bouton(barre, "Sauvegarder maintenant (Ctrl+S)", "success",
               self.sauvegarder, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(barre, "Restaurer la sélection", "danger",
               self._restaurer, petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(barre, "Ouvrir le dossier", "secondary",
               lambda: self._ouvrir_dossier(db.BACKUP_DIR), petit=True).pack(side=tk.LEFT, padx=3)
        Bouton(barre, "Choisir emplacement...", "info",
               self._choisir_dossier_sauvegardes, petit=True).pack(side=tk.LEFT, padx=3)

        # Afficher le dossier actuel
        lbl_dossier = tk.Label(page3, text="", font=(POLICE, 9),
                               bg=COULEURS["bg"], fg=COULEURS["text_secondary"])
        lbl_dossier.pack(anchor="w", pady=(4, 8))
        self._lbl_dossier_sauvegardes = lbl_dossier
        self._maj_label_dossier()

        f_tree_sauv = tk.Frame(page3, bg=COULEURS["bg"])
        f_tree_sauv.pack(fill=tk.BOTH, expand=True)
        self.tab_sauvegardes = TableauTriable(f_tree_sauv, [
            ("nom", "Fichier", 340, "w", False),
            ("date", "Date", 170, "w", False),
            ("taille", "Taille", 110, "e", True)], height=12)
        ajouter_scrollbars(f_tree_sauv, self.tab_sauvegardes)
        tk.Label(page3, text="⚠ La restauration remplace toutes les données actuelles. "
                             "Une sauvegarde de sécurité est créée automatiquement avant.",
                 font=(POLICE, 9), bg=COULEURS["bg"], fg=COULEURS["danger"]).pack(anchor="w", pady=8)
        self._charger_sauvegardes()

        # ── Journal ──
        page4 = tk.Frame(onglets, bg=COULEURS["bg"], padx=12, pady=12)
        onglets.add(page4, text="Journal d'activité")
        f_tree_journal = tk.Frame(page4, bg=COULEURS["bg"])
        f_tree_journal.pack(fill=tk.BOTH, expand=True)
        t = TableauTriable(f_tree_journal, [
            ("date", "Date", 160, "w", False),
            ("user", "Utilisateur", 140, "w", False),
            ("action", "Action", 220, "w", False),
            ("details", "Détails", 420, "w", False)], height=18)
        ajouter_scrollbars(f_tree_journal, t)
        for i, j in enumerate(db.get_journal(400)):
            t.insert("", tk.END, tags=zebre(i), values=(
                fmt_date(j["date_action"]), j["utilisateur"], j["action"], j["details"]))


    def _sauver_params(self) -> None:
        """Enregistre tous les paramètres en 1 transaction (au lieu de N)."""
        parametres = {cle: entry.get().strip() for cle, entry in self.champs_params.items()}
        db.set_parametres_batch(parametres)
        self.params = db.get_parametres()
        self.devise = self.params.get("devise", "F CFA")
        messagebox.showinfo("Enregistré",
                            "Paramètres enregistrés.\nCertains libellés seront actualisés "
                            "au prochain démarrage.", parent=self.root)
        self.statut("Paramètres enregistrés", COULEURS["success"])


    def _nouvel_utilisateur(self):
        d = DialogueUtilisateur(self.root)
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            self._charger_utilisateurs()


    def _modifier_utilisateur(self):
        sel = self.tab_utilisateurs.selection()
        if not sel:
            return
        u = next((x for x in db.get_utilisateurs() if x["id"] == int(sel[0])), None)
        if u:
            d = DialogueUtilisateur(self.root, u)
            if d.attendre():
                self.statut(d.result, COULEURS["success"])
                self._charger_utilisateurs()


    def _supprimer_utilisateur(self):
        sel = self.tab_utilisateurs.selection()
        if not sel:
            return
        if int(sel[0]) == self.utilisateur["id"]:
            messagebox.showwarning("Impossible",
                                   "Vous ne pouvez pas supprimer votre propre compte.",
                                   parent=self.root)
            return
        if messagebox.askyesno("Confirmer", "Supprimer cet utilisateur ?", parent=self.root):
            ok, msg = db.delete_utilisateur(int(sel[0]))
            messagebox.showinfo("Résultat" if ok else "Impossible", msg, parent=self.root)
            self._charger_utilisateurs()


    def _charger_utilisateurs(self):
        t = self.tab_utilisateurs
        t.delete(*t.get_children())
        for i, u in enumerate(db.get_utilisateurs()):
            t.insert("", tk.END, iid=u["id"], tags=zebre(i, () if u["actif"] else ("inactif",)),
                     values=(u["nom_utilisateur"], u["nom_complet"], u["role"],
                             "Actif" if u["actif"] else "Inactif", fmt_date(u["date_creation"]),
                             fmt_date(u["dernier_acces"]) if u["dernier_acces"] else "jamais"))


    def _charger_sauvegardes(self):
        t = self.tab_sauvegardes
        t.delete(*t.get_children())
        for i, s in enumerate(db.lister_sauvegardes()):
            t.insert("", tk.END, iid=s["chemin"], tags=zebre(i),
                     values=(s["nom"], s["date"].strftime("%d/%m/%Y %H:%M:%S"),
                             f"{s['taille'] / 1024:,.0f} Ko".replace(",", " ")))


    def _restaurer(self):
        sel = self.tab_sauvegardes.selection()
        if not sel:
            messagebox.showinfo("Information", "Sélectionnez une sauvegarde.", parent=self.root)
            return
        if not messagebox.askyesno(
                "Restaurer",
                "Toutes les données actuelles seront remplacées par cette sauvegarde.\n\n"
                "L'application se fermera ensuite : relancez-la pour voir les données "
                "restaurées.\n\nContinuer ?", parent=self.root, icon="warning"):
            return
        ok, msg = db.restaurer_base(sel[0])
        if ok:
            messagebox.showinfo("Restauration terminée",
                                f"{msg}\n\nL'application va se fermer.", parent=self.root)
            self.root.destroy()
        else:
            messagebox.showerror("Erreur", msg, parent=self.root)


    def _ouvrir_dossier(self, chemin):
        os.makedirs(chemin, exist_ok=True)
        try:
            os.startfile(chemin)
        except (AttributeError, OSError):
            try:
                import subprocess
                subprocess.run(["explorer", chemin], shell=True)
            except Exception:
                messagebox.showinfo("Dossier", chemin, parent=self.root)

    def _choisir_dossier_sauvegardes(self):
        """Laisse l'utilisateur choisir où stocker les sauvegardes."""
        dossier = filedialog.askdirectory(
            title="Dossier de sauvegarde",
            initialdir=db.BACKUP_DIR,
            parent=self.root)
        if dossier and os.path.isdir(dossier):
            db.set_parametre("backup_dir", dossier)
            db.BACKUP_DIR = dossier
            self.statut("Sauvegardes -> " + dossier, COULEURS["success"])
            self._maj_label_dossier()

    def _maj_label_dossier(self):
        if hasattr(self, "_lbl_dossier_sauvegardes"):
            lbl = getattr(self, "_lbl_dossier_sauvegardes", None)
            if lbl:
                lbl.configure(text="Dossier : " + db.BACKUP_DIR)

    # ═══ SESSION ═══════════════════════════════════════

    # ═══ AIDE ══════════════════════════════════════════


