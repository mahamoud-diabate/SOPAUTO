"""
SODIPAC - Clients
"""
import tkinter as tk
from tkinter import messagebox

import database as db
from dialogues import DialogueClient
from ui_widgets import (COULEURS, POLICE, Bouton, EntreeRecherche,
                        TableauTriable, ajouter_scrollbars, fmt_money, zebre)


class ClientsMixin:
    """Gestion des clients — CRUD, plafond crédit, historique.

    Double-clic sur un client pour voir ses ventes et créances.
    """

    def afficher_clients(self):
        self._nouvelle_page("👥 Clients", 4)
        Bouton(self.zone_actions, "➕ Nouveau client", "primary",
               self._nouveau_client, petit=True).pack(side=tk.LEFT, padx=3)

        barre = tk.Frame(self.zone, bg=COULEURS["bg"])
        barre.pack(fill=tk.X, pady=(0, 8))
        self.rech_clients = EntreeRecherche(barre, "Nom, téléphone, véhicule…", 36,
                                            callback=self._charger_clients)
        self.rech_clients.pack(side=tk.LEFT)
        self.lbl_resume_clients = tk.Label(barre, text="", font=(POLICE, 9, "bold"),
                                           bg=COULEURS["bg"], fg=COULEURS["primary"])
        self.lbl_resume_clients.pack(side=tk.RIGHT, padx=8)

        cadre = tk.Frame(self.zone, bg=COULEURS["card"])
        cadre.pack(fill=tk.BOTH, expand=True)
        self.tab_clients = TableauTriable(cadre, [
            ("nom", "Nom", 200, "w", False),
            ("tel", "Téléphone", 130, "w", False),
            ("email", "Email", 190, "w", False),
            ("vehicule", "Véhicule", 170, "w", False),
            ("nb", "Achats", 70, "center", True),
            ("total", "Total dépensé", 130, "e", True),
            ("notes", "Notes", 200, "w", False)])
        ajouter_scrollbars(cadre, self.tab_clients)
        self.tab_clients.bind("<Double-1>", lambda e: self._modifier_client())

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="✏️  Modifier", command=self._modifier_client)
        menu.add_command(label="🗑️  Supprimer", command=self._supprimer_client)

        def clic_droit(e):
            iid = self.tab_clients.identify_row(e.y)
            if iid:
                self.tab_clients.selection_set(iid)
                menu.tk_popup(e.x_root, e.y_root)

        self.tab_clients.bind("<Button-3>", clic_droit)
        self._charger_clients()


    def _charger_clients(self):
        clients = db.get_clients(self.rech_clients.get())
        t = self.tab_clients
        t.delete(*t.get_children())
        for i, c in enumerate(clients):
            t.insert("", tk.END, iid=c["id"], tags=zebre(i), values=(
                c["nom"], c["telephone"], c["email"], c["vehicule"],
                c["nb_achats"], fmt_money(c["total_achats"]), c["notes"]))
        self.lbl_resume_clients.configure(text=f"{len(clients)} client(s)")


    def _nouveau_client(self):
        d = DialogueClient(self.root)
        if d.attendre():
            self.statut(d.result, COULEURS["success"])
            self._charger_clients()


    def _modifier_client(self):
        sel = self.tab_clients.selection()
        if not sel:
            return
        client = next((c for c in db.get_clients() if c["id"] == int(sel[0])), None)
        if client:
            d = DialogueClient(self.root, client)
            if d.attendre():
                self.statut(d.result, COULEURS["success"])
                self._charger_clients()


    def _supprimer_client(self):
        if not self.peut("supprimer"):
            return self._refus()
        sel = self.tab_clients.selection()
        if sel and messagebox.askyesno("Confirmer", "Supprimer ce client ?\n"
                                       "Ses ventes seront conservées.", parent=self.root):
            db.delete_client(int(sel[0]))
            self._charger_clients()

    # ═══ CATÉGORIES ════════════════════════════════════


