"""
SODIPAC - Gestion Pièce Auto - Noyau de l'application
Menu, navigation, thème, permissions, structure.
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime, timedelta
from typing import Any

import database as db
import analyse_prix
import factures
import export_pdf
from dialogues import (DialogueCategorie, DialogueClient, DialogueMouvement, DialoguePaiement,
                       DialogueProduit, DialogueUtilisateur, DialogueFournisseur)
from pages_v3 import PagesV3
from pages_analyse import PageAnalyse
from ui_widgets import (COULEURS, POLICE, Bouton, Carte, EntreeRecherche,
                        TableauTriable, ajouter_scrollbars, appliquer_theme,
                        appliquer_palette, THEME_ACTUEL, centrer_fenetre,
                        fmt_date, fmt_money, infobulle, zebre)

# Imports des mixins
from page_dashboard import DashboardMixin
from page_caisse import CaisseMixin
from page_produits import ProduitsMixin
from page_stock import StockMixin
from page_clients import ClientsMixin
from page_categories import CategoriesMixin
from page_fournisseurs import FournisseursMixin
from page_mouvements import MouvementsMixin
from page_parametres import ParametresMixin
from page_rapports import RapportsMixin
from page_aide import AideMixin

PERMISSIONS = {
    "gerant": {"caisse", "produits", "stock", "rapports"},
    "vendeur": {"caisse"},
    "superviseur": {"caisse", "produits", "stock", "rapports", "admin", "supprimer"},
}


class Application(PagesV3, PageAnalyse, DashboardMixin, CaisseMixin,
                  ProduitsMixin, StockMixin, ClientsMixin, CategoriesMixin,
                  FournisseursMixin, MouvementsMixin, ParametresMixin,
                  RapportsMixin, AideMixin):
    """Application principale SODIPAC — caisse, stock, clients, rapports.

    Architecture : Application herite de 13 mixins (1 par ecran).
    Chaque mixin est dans son propre fichier page_*.py.

    Methodes cles :
        _nouvelle_page()           — change l'ecran affiche
        _construire_menu_lateral() — barre de navigation gauche
        peut(droit)                — verifie permissions du role
        statut(texte, couleur)     — message barre d'etat
    """

    def __init__(self, root, utilisateur):
        self.root = root
        self.utilisateur = utilisateur
        self.role = utilisateur.get("role", "vendeur")
        self.droits = PERMISSIONS.get(self.role, PERMISSIONS["vendeur"])
        db.set_utilisateur_courant(utilisateur["nom_utilisateur"])

        self.params = db.get_parametres()
        self.devise = self.params.get("devise", "F CFA")

        root.title(f"{self.params.get('entreprise_nom', 'SODIPAC')} — Gestion Pièce Auto "
                   f"[{utilisateur['nom_utilisateur']} · {self.role}]")
        root.geometry("1400x820")
        root.minsize(1100, 680)
        root.configure(bg=COULEURS["bg"])
        appliquer_theme(root)

        self.page_courante = None
        self._apres_planifies = set()
        self._construire_interface()
        self._raccourcis()
        # Mode vendeur simplifié : ouverture directe sur la caisse
        if self.role in ("vendeur", "gerant"):
            self.afficher_caisse()
        else:
            self.afficher_dashboard()
        centrer_fenetre(root, 1400, 820)
        root.protocol("WM_DELETE_WINDOW", self.quitter)
        root.bind("<Destroy>", self._sur_destruction, add="+")
        self._tic_horloge()


    def _planifier(self, delai, fonction):
        """after() dont l'identifiant est mémorisé pour pouvoir être annulé."""
        identifiant = self.root.after(delai, fonction)
        self._apres_planifies.add(identifiant)
        return identifiant


    def _sur_destruction(self, event=None):
        """Annule tous les callbacks en attente quand la fenêtre est fermée."""
        if event is not None and event.widget is not self.root:
            return
        for identifiant in list(self._apres_planifies):
            try:
                self.root.after_cancel(identifiant)
            except (tk.TclError, ValueError):
                pass
        self._apres_planifies.clear()

    # ── permissions ──

    def peut(self, droit):
        return droit in self.droits


    def _refus(self):
        messagebox.showwarning(
            "Accès refusé",
            f"Votre rôle « {self.role} » ne permet pas cette action.\n"
            "Contactez un administrateur.", parent=self.root)

    # ─── STRUCTURE ────────────────────────────────────


    def _construire_interface(self):
        conteneur = tk.Frame(self.root, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        self._construire_menu_lateral(conteneur)

        droite = tk.Frame(conteneur, bg=COULEURS["bg"])
        droite.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._construire_entete(droite)

        self.zone = tk.Frame(droite, bg=COULEURS["bg"])
        self.zone.pack(fill=tk.BOTH, expand=True, padx=16, pady=(10, 6))

        self._construire_barre_statut(droite)


    def _construire_menu_lateral(self, parent):
        barre = tk.Frame(parent, bg=COULEURS["sidebar"], width=240)
        barre.pack(side=tk.LEFT, fill=tk.Y)
        barre.pack_propagate(False)

        # Logo + nom entreprise
        logo = tk.Frame(barre, bg=COULEURS["sidebar"])
        logo.pack(fill=tk.X, pady=(18, 6))
        lbl_icone = tk.Label(logo, text="🚗", font=(POLICE, 30),
                             bg=COULEURS["sidebar"], fg="#60a5fa")
        lbl_icone.pack()
        tk.Label(logo, text=self.params.get("entreprise_nom", "SODIPAC"),
                 font=(POLICE, 16, "bold"), bg=COULEURS["sidebar"],
                 fg="white").pack()
        tk.Label(logo, text="Gestion Pièce Auto", font=(POLICE, 8),
                 bg=COULEURS["sidebar"],
                 fg=COULEURS["sidebar_text"]).pack(pady=(1, 0))

        # ── Pied de page (ancré AVANT la zone défilante pour rester visible) ──
        pied = tk.Frame(barre, bg=COULEURS["sidebar"])
        pied.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        tk.Frame(pied, bg=COULEURS["sidebar_sep"], height=1).pack(fill=tk.X, padx=18, pady=(0, 8))
        info_user = tk.Frame(pied, bg=COULEURS["sidebar"])
        info_user.pack(fill=tk.X, padx=18)
        tk.Label(info_user,
                 text=f"👤 {self.utilisateur.get('nom_complet') or self.utilisateur['nom_utilisateur']}",
                 font=(POLICE, 10, "bold"), bg=COULEURS["sidebar"],
                 fg="white", anchor="w").pack(fill=tk.X)
        role_colors = {"superviseur": "#60a5fa", "gerant": "#34d399",
                       "vendeur": "#fbbf24"}
        tk.Label(info_user, text=self.role.capitalize(), font=(POLICE, 8),
                 bg=COULEURS["sidebar"],
                 fg=role_colors.get(self.role, COULEURS["sidebar_text"]),
                 anchor="w").pack(fill=tk.X)
        Bouton(pied, "Changer d'utilisateur", "secondary",
               self.deconnexion, petit=True, outline=True).pack(
                   fill=tk.X, padx=18, pady=(8, 0))

        # ── Zone de navigation défilante ──
        # 18 entrées ne tiennent pas sur un écran de portable : on rend la
        # navigation scrollable pour ne jamais masquer une rubrique.
        zone = tk.Frame(barre, bg=COULEURS["sidebar"])
        zone.pack(fill=tk.BOTH, expand=True)
        nav_canvas = tk.Canvas(zone, bg=COULEURS["sidebar"], highlightthickness=0,
                               bd=0, width=232)
        nav_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        nav = tk.Frame(nav_canvas, bg=COULEURS["sidebar"])
        fenetre = nav_canvas.create_window((0, 0), window=nav, anchor="nw", width=232)

        def _maj_region(_e=None):
            try:
                nav_canvas.configure(scrollregion=nav_canvas.bbox("all"))
                # Barre de défilement affichée seulement si nécessaire
                besoin = nav.winfo_reqheight() > nav_canvas.winfo_height()
                if besoin and not vsb.winfo_ismapped():
                    vsb.pack(side=tk.RIGHT, fill=tk.Y)
                elif not besoin and vsb.winfo_ismapped():
                    vsb.pack_forget()
            except tk.TclError:
                pass

        vsb = tk.Scrollbar(zone, orient="vertical", command=nav_canvas.yview,
                           width=8, bg=COULEURS["sidebar"],
                           troughcolor=COULEURS["sidebar"], bd=0,
                           highlightthickness=0, activebackground=COULEURS["secondary"])
        nav_canvas.configure(yscrollcommand=vsb.set)
        nav.bind("<Configure>", _maj_region)
        nav_canvas.bind("<Configure>",
                        lambda e: (nav_canvas.itemconfigure(fenetre, width=e.width),
                                   _maj_region()))

        def _molette(event):
            try:
                if nav_canvas.winfo_exists() and nav.winfo_reqheight() > nav_canvas.winfo_height():
                    nav_canvas.yview_scroll(-1 * (event.delta // 120), "units")
            except tk.TclError:
                pass

        nav_canvas.bind("<Enter>", lambda e: nav_canvas.bind_all("<MouseWheel>", _molette))
        nav_canvas.bind("<Leave>", lambda e: nav_canvas.unbind_all("<MouseWheel>"))

        # Séparateur
        tk.Frame(nav, bg=COULEURS["sidebar_sep"], height=1).pack(
            fill=tk.X, padx=20, pady=(6, 4))
        tk.Label(nav, text="NAVIGATION", font=(POLICE, 8, "bold"),
                 bg=COULEURS["sidebar"],
                 fg=COULEURS["sidebar_text"]).pack(anchor="w", padx=22, pady=(2, 4))

        self.entrees_menu = [
                    ("📊", "Tableau de bord", self.afficher_dashboard, None, "F12"),
                    ("🧾", "Caisse", self.afficher_caisse, "caisse", "F2"),
                    ("📦", "Produits", self.afficher_produits, None, "F3"),
                    ("📋", "Stock", self.afficher_stock, "stock", "F4"),
                    ("👥", "Clients", self.afficher_clients, None, "F5"),
                    ("💳", "Créances", self.afficher_creances, "rapports", "F9"),
                    ("💰", "Analyse", self.afficher_analyse, "rapports", "F10"),
                ]

        self.entrees_menu_second = [
            ("🛒", "Achats", self.afficher_achats, "stock", None),
            ("🏬", "Dépôts", self.afficher_depots, "stock", None),
            ("📋", "Inventaire", self.afficher_inventaire, "stock", None),
            ("↩️", "Retours", self.afficher_retours, "caisse", None),
            ("📉", "Prévisions", self.afficher_previsions, "stock", None),
            ("📁", "Catégories", self.afficher_categories, "produits", None),
            ("🏭", "Fournisseurs", self.afficher_fournisseurs, "produits", None),
            ("📈", "Mouvements", self.afficher_mouvements, None, None),
            ("💹", "Rapports", self.afficher_rapports, "rapports", "F6"),
            ("⚙️", "Paramètres", self.afficher_parametres, "admin", None),
            ("❓", "Aide", self.afficher_aide, None, "F1"),
        ]

        self.boutons_menu = []

        for icone, libelle, action, droit, touche in self.entrees_menu:
            self._ajouter_bouton_menu(nav, icone, libelle, action, droit, touche)

        tk.Frame(nav, bg=COULEURS["sidebar_sep"], height=1).pack(fill=tk.X, padx=20, pady=6)
        tk.Label(nav, text="GESTION", font=(POLICE, 8, "bold"),
                 bg=COULEURS["sidebar"],
                 fg=COULEURS["sidebar_text"]).pack(anchor="w", padx=22, pady=(2, 4))

        for icone, libelle, action, droit, touche in self.entrees_menu_second:
            self._ajouter_bouton_menu(nav, icone, libelle, action, droit, touche)

        self._planifier(120, _maj_region)


    def _ajouter_bouton_menu(self, parent, icone, libelle, action, droit, touche):
        actif = droit is None or self.peut(droit)
        b = tk.Button(
            parent, text=f"    {icone}     {libelle}",
            font=(POLICE, 10),
            bg=COULEURS["sidebar"],
            fg="white" if actif else COULEURS["sidebar_disabled"],
            activebackground=COULEURS["sidebar_hover"],
            activeforeground="white",
            bd=0, anchor="w", padx=0, pady=10,
            highlightthickness=0,
            cursor="hand2" if actif else "arrow",
            command=action if actif else self._refus)
        b.pack(fill=tk.X, padx=8)
        b._index = len(self.boutons_menu)
        if actif:
            b.bind("<Enter>", lambda e, x=b:
                   x.configure(bg=COULEURS["sidebar_hover"])
                   if x is not getattr(self, "_menu_actif", None) else None)
            b.bind("<Leave>", lambda e, x=b:
                   x.configure(bg=COULEURS["sidebar"])
                   if x is not getattr(self, "_menu_actif", None) else None)
        if touche:
            infobulle(b, f"Raccourci : {touche}")
        self.boutons_menu.append(b)


    def _construire_entete(self, parent):
        entete = tk.Frame(parent, bg=COULEURS["card"], height=62)
        entete.pack(fill=tk.X)
        entete.pack_propagate(False)
        # Barre colorée sous l'en-tête
        tk.Frame(parent, bg=COULEURS["primary"], height=3).pack(fill=tk.X)

        # Titre de page à gauche
        self.lbl_titre = tk.Label(entete, text="Tableau de bord",
                                  font=(POLICE, 16, "bold"),
                                  bg=COULEURS["card"], fg=COULEURS["text"])
        self.lbl_titre.pack(side=tk.LEFT, padx=24)

        self.zone_actions = tk.Frame(entete, bg=COULEURS["card"])
        self.zone_actions.pack(side=tk.LEFT, padx=8, pady=4)

        # Horloge + alertes à droite
        droite_info = tk.Frame(entete, bg=COULEURS["card"])
        droite_info.pack(side=tk.RIGHT, padx=20)

        self.lbl_alertes = tk.Label(droite_info, text="", font=(POLICE, 10, "bold"),
                                    bg=COULEURS["card"], fg=COULEURS["danger"],
                                    cursor="hand2")
        self.lbl_alertes.pack(side=tk.RIGHT, padx=(0, 6))
        self.lbl_alertes.bind("<Button-1>",
                              lambda e: self.afficher_produits(alertes=True))

        # Bouton bascule thème clair/sombre
        self.btn_theme = tk.Label(droite_info,
                                  text="🌙" if THEME_ACTUEL[0] == "clair" else "☀️",
                                  font=(POLICE, 13), bg=COULEURS["card"],
                                  fg=COULEURS["text_secondary"], cursor="hand2")
        self.btn_theme.pack(side=tk.RIGHT, padx=(0, 12))
        self.btn_theme.bind("<Button-1>", lambda e: self.basculer_theme())
        infobulle(self.btn_theme, "Basculer le thème clair / sombre")

        self.lbl_horloge = tk.Label(droite_info, text="", font=(POLICE, 10),
                                    bg=COULEURS["card"], fg=COULEURS["text_secondary"])
        self.lbl_horloge.pack(side=tk.RIGHT)


    def _construire_barre_statut(self, parent):
        barre = tk.Frame(parent, bg=COULEURS["statusbar"], height=28)
        barre.pack(fill=tk.X, side=tk.BOTTOM)
        barre.pack_propagate(False)
        self.lbl_statut = tk.Label(barre, text="Prêt", font=(POLICE, 9),
                                   bg=COULEURS["statusbar"], fg=COULEURS["text_secondary"],
                                   anchor="w")
        self.lbl_statut.pack(side=tk.LEFT, padx=16)
        tk.Label(barre, text="F1 Aide · F2 Caisse · F3 Produits · F4 Stock · F7 Véhicules · "
                             "F9 Créances · F10 Analyse · F12 Tableau de bord · Ctrl+S Sauvegarde",
                 font=(POLICE, 8), bg=COULEURS["statusbar"],
                 fg=COULEURS["text_secondary"]).pack(side=tk.RIGHT, padx=16)


    def basculer_theme(self):
        nouveau = "sombre" if THEME_ACTUEL[0] == "clair" else "clair"
        appliquer_palette(nouveau)
        db.set_parametre("theme", nouveau)
        # Reconstruction complète de l'interface avec la nouvelle palette
        self._sur_destruction()
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=COULEURS["bg"])
        appliquer_theme(self.root)
        self._construire_interface()
        if self.role in ("vendeur", "gerant"):
            self.afficher_caisse()
        else:
            self.afficher_dashboard()
        self._tic_horloge()
        self.statut(f"Thème {nouveau} activé", COULEURS["success"])


    def _raccourcis(self):
        r = self.root
        r.bind("<F1>", lambda e: self.afficher_aide())
        r.bind("<F2>", lambda e: self.afficher_caisse() if self.peut("caisse") else self._refus())
        r.bind("<F3>", lambda e: self.afficher_produits())
        r.bind("<F4>", lambda e: self.afficher_stock() if self.peut("stock") else self._refus())
        r.bind("<F5>", lambda e: self.afficher_clients())
        r.bind("<F6>", lambda e: self.afficher_rapports() if self.peut("rapports") else self._refus())
        r.bind("<F9>", lambda e: self.afficher_creances() if self.peut("rapports") else self._refus())
        r.bind("<F10>", lambda e: self.afficher_analyse() if self.peut("rapports") else self._refus())
        r.bind("<Control-s>", lambda e: self.sauvegarder())
        r.bind("<Control-S>", lambda e: self.sauvegarder())
        r.bind("<Control-n>", lambda e: self.nouveau_produit())
        r.bind("<F12>", lambda e: self.afficher_dashboard())


    def _tic_horloge(self):
        """Horloge de l'en-tête. S'arrête proprement quand la fenêtre est détruite."""
        try:
            if not self.lbl_horloge.winfo_exists():
                return
            self.lbl_horloge.configure(
                text=datetime.now().strftime("%A %d %B %Y — %H:%M:%S").capitalize())
            self._id_horloge = self._planifier(1000, self._tic_horloge)
        except tk.TclError:
            return


    def statut(self, texte, couleur=None):
        """Message temporaire dans la barre d'état."""
        try:
            self.lbl_statut.configure(text=texte, fg=couleur or COULEURS["text_secondary"])
        except tk.TclError:
            return

        def reinitialiser():
            try:
                if self.lbl_statut.winfo_exists():
                    self.lbl_statut.configure(text="Prêt", fg=COULEURS["text_secondary"])
            except tk.TclError:
                pass

        self._planifier(6000, reinitialiser)


    def _nouvelle_page(self, titre, index_menu):
        for w in self.zone.winfo_children():
            w.destroy()
        for w in self.zone_actions.winfo_children():
            w.destroy()
        self.lbl_titre.configure(text=titre)
        for i, b in enumerate(self.boutons_menu):
            if i == index_menu:
                b.configure(bg=COULEURS["sidebar_active"], fg="white")
                self._menu_actif = b
            elif b.cget("bg") in (COULEURS["primary"], COULEURS["sidebar_active"]):
                b.configure(bg=COULEURS["sidebar"], fg="white")
        self._maj_badge_alertes()


    def _maj_badge_alertes(self):
        try:
            nb = db.get_dashboard_stats()["nb_alertes"]
        except Exception:
            nb = 0
        try:
            if self.lbl_alertes.winfo_exists():
                self.lbl_alertes.configure(
                    text=f"⚠ {nb} alerte(s) de stock" if nb else "✅ Stocks OK",
                    fg=COULEURS["danger"] if nb else COULEURS["success"])
        except tk.TclError:
            pass

    # ═══ TABLEAU DE BORD ═══════════════════════════════


    def deconnexion(self):
        if messagebox.askyesno("Changer d'utilisateur",
                               "Fermer la session en cours ?", parent=self.root):
            self._sur_destruction()
            self.root.destroy()
            # Relancer l'application depuis main
            import main as _main
            _main.lancer()


    def quitter(self):
        if getattr(self, "panier", None):
            if not messagebox.askyesno("Panier en cours",
                                       "Le panier n'est pas encaissé. Quitter quand même ?",
                                       parent=self.root):
                return
        self._sur_destruction()
        try:
            db.sauvegarder_base()
        except Exception:
            pass
        self._sync_cloud()
        self.root.destroy()

    def _sync_cloud(self):
        """Copie la base vers le dossier partage (OneDrive, reseau...).
        
        Force un checkpoint WAL avant copie pour garantir un .db complet.
        """
        dossier = self.params.get("dossier_synchro", "")
        if not dossier or not os.path.isdir(dossier):
            return
        try:
            import shutil
            # Forcer l'écriture du WAL dans le .db principal
            conn = db.get_connection()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
            cible = os.path.join(dossier, "gestion_piece_auto.db")
            shutil.copy2(db.DB_PATH, cible)
        except Exception:
            pass  # silencieux — ne jamais bloquer la caisse

    def sauvegarder(self):
        try:
            chemin = db.sauvegarder_base()
        except Exception as e:
            messagebox.showerror("Erreur", f"Sauvegarde impossible :\n{e}", parent=self.root)
            return
        self.statut(f"Sauvegarde créée : {os.path.basename(chemin)}", COULEURS["success"])
        if hasattr(self, "tab_sauvegardes") and self.tab_sauvegardes.winfo_exists():
            self._charger_sauvegardes()
        else:
            messagebox.showinfo("Sauvegarde", f"Base sauvegardée :\n{chemin}", parent=self.root)
