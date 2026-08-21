"""
SODIPAC - Gestion Pièce Auto - Noyau de l'application
Menu, navigation, thème, permissions, structure.
"""
import os
import traceback
import shutil
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

# DPI awareness pour Windows - texte net
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)  # 1 = Per-Monitor DPI Aware
except Exception:
    try:
        windll.user32.SetProcessDPIAware()
    except Exception:
        # DPI awareness non supporté, on continue sans
        pass

import database as db
from pages_analyse import PageAnalyse
from ui_widgets import (COULEURS, POLICE, Bouton, appliquer_theme,
                        appliquer_palette, THEME_ACTUEL, centrer_fenetre,
                        infobulle, fmt_money)

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
from page_creances import CreancesMixin
from page_achats import AchatsMixin
from page_inventaire import InventaireMixin
from page_vehicules import VehiculesMixin
from page_depots import DepotsMixin
from page_retours import RetoursMixin
from page_previsions import PrevisionsMixin

PERMISSIONS = {
    "gerant": {"caisse", "produits", "stock", "rapports"},
    "vendeur": {"caisse"},
    "superviseur": {"caisse", "produits", "stock", "rapports", "admin", "supprimer"},
}


class Application(PageAnalyse, DashboardMixin, CaisseMixin,
                  ProduitsMixin, StockMixin, ClientsMixin, CategoriesMixin,
                  FournisseursMixin, MouvementsMixin, ParametresMixin,
                  RapportsMixin, AideMixin,
                  CreancesMixin, AchatsMixin, InventaireMixin,
                  VehiculesMixin, DepotsMixin, RetoursMixin,
                  PrevisionsMixin):
    """Application principale SODIPAC — caisse, stock, clients, rapports.

    Architecture : Application hérite de 18 mixins (1 par écran).
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
        try:
            root.state("zoomed")
        except Exception:
            # Mode zoomé non pris en charge sur toutes les plateformes OS
            self._mode_zoome_erreur = True
        root.configure(bg=COULEURS["bg"])
        appliquer_theme(root)

        # Écouteur de redimensionnement de la fenêtre désactivé pour éviter le ralentissement Tkinter
        pass

        self.page_courante = None
        self._apres_planifies = set()
        self._construire_interface()
        self._raccourcis()
        # Mode vendeur simplifié : ouverture directe sur la caisse
        if self.role in ("vendeur", "gerant"):
            self.afficher_caisse()
        else:
            self.afficher_dashboard()
        root.protocol("WM_DELETE_WINDOW", self.quitter)
        root.bind("<Destroy>", self._sur_destruction, add="+")
        self._tic_horloge()
        self._planifier(3600000, self._sauvegarde_auto_horaire)


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
            try:
                db.close_connection()
            except Exception:
                # Log pour diagnostic sans bloquer la fermeture
                import traceback
                traceback.print_exc()

    # ── permissions ──

    def peut(self, droit):
        return droit in self.droits


    def _refus(self):
        messagebox.showwarning(
            "Accès refusé",
            f"Votre rôle « {self.role} » ne permet pas cette action.\n"
            "Contactez un administrateur.", parent=self.root)

    def _idx_menu(self, libelle):
        """Retrouve l'index du bouton de menu portant ce libellé."""
        for i, b in enumerate(getattr(self, "boutons_menu", [])):
            try:
                # Une entrée de menu est une Frame (`row`) qui porte son libellé
                # dans le Label `_texte` : elle n'a pas d'option `text`. Lire
                # directement `b.cget("text")` levait donc TclError sur chaque
                # entrée et la fonction renvoyait toujours -1 — aucun écran
                # ouvert via _idx_menu() n'était surligné dans le menu.
                etiquette = getattr(b, "_texte", None)
                texte = etiquette.cget("text") if etiquette is not None else b.cget("text")
                if libelle in texte:
                    return i
            except tk.TclError:
                continue
        return -1

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
        barre = tk.Frame(parent, bg=COULEURS["sidebar"], width=248)
        barre.pack(side=tk.LEFT, fill=tk.Y)
        barre.pack_propagate(False)

        # ── Logo ──────────────────────────────────────────
        logo_frame = tk.Frame(barre, bg=COULEURS["sidebar"])
        logo_frame.pack(fill=tk.X, pady=(20, 0))

        # Icône dans un badge coloré
        badge = tk.Frame(logo_frame, bg="#6366f1", width=52, height=52)
        badge.pack()
        badge.pack_propagate(False)
        tk.Label(badge, text="🚗", font=(POLICE, 22),
                 bg="#6366f1", fg="white").place(relx=.5, rely=.5, anchor="center")

        tk.Label(logo_frame,
                 text=self.params.get("entreprise_nom", "SODIPAC"),
                 font=(POLICE, 15, "bold"), bg=COULEURS["sidebar"],
                 fg="white").pack(pady=(8, 0))
        tk.Label(logo_frame, text="Gestion Pièce Auto", font=(POLICE, 8),
                 bg=COULEURS["sidebar"],
                 fg=COULEURS["sidebar_accent"]).pack(pady=(1, 10))

        # Séparateur lumineux
        sep_grad = tk.Frame(barre, bg="#6366f1", height=2)
        sep_grad.pack(fill=tk.X, padx=24, pady=(0, 6))

        # ── Pied ancré en bas AVANT la zone scrollable ──
        pied = tk.Frame(barre, bg=COULEURS["sidebar"])
        pied.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Frame(pied, bg=COULEURS["sidebar_sep"], height=1).pack(
            fill=tk.X, padx=16, pady=(0, 10))

        # Carte utilisateur
        user_card = tk.Frame(pied, bg=COULEURS["sidebar_hover"],
                             padx=10, pady=8)
        user_card.pack(fill=tk.X, padx=12, pady=(0, 8))

        role_colors = {"superviseur": "#818cf8", "gerant": "#34d399",
                       "vendeur": "#fbbf24", "administrateur": "#f472b6"}
        role_color = role_colors.get(self.role, "#94a3b8")

        # Avatar initiale
        nom_affiche = (self.utilisateur.get("nom_complet")
                       or self.utilisateur["nom_utilisateur"])
        initiale = nom_affiche[0].upper() if nom_affiche else "?"

        avatar = tk.Frame(user_card, bg=role_color, width=32, height=32)
        avatar.pack(side=tk.LEFT, padx=(0, 8))
        avatar.pack_propagate(False)
        tk.Label(avatar, text=initiale, font=(POLICE, 11, "bold"),
                 bg=role_color, fg="white").place(relx=.5, rely=.5,
                                                   anchor="center")

        texte_frame = tk.Frame(user_card, bg=COULEURS["sidebar_hover"])
        texte_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(texte_frame, text=nom_affiche,
                 font=(POLICE, 9, "bold"), bg=COULEURS["sidebar_hover"],
                 fg="white", anchor="w").pack(fill=tk.X)
        tk.Label(texte_frame, text=self.role.capitalize(),
                 font=(POLICE, 8), bg=COULEURS["sidebar_hover"],
                 fg=role_color, anchor="w").pack(fill=tk.X)

        Bouton(pied, "⇄  Changer d'utilisateur", "secondary",
               self.deconnexion, petit=True, outline=True).pack(
                   fill=tk.X, padx=12, pady=(0, 10))

        # ── Zone de navigation scrollable ──
        zone = tk.Frame(barre, bg=COULEURS["sidebar"])
        zone.pack(fill=tk.BOTH, expand=True)

        nav_canvas = tk.Canvas(zone, bg=COULEURS["sidebar"],
                               highlightthickness=0, bd=0)
        nav_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        nav = tk.Frame(nav_canvas, bg=COULEURS["sidebar"])
        fenetre = nav_canvas.create_window((0, 0), window=nav,
                                           anchor="nw", width=248)

        def _maj_region(_e=None):
            try:
                nav_canvas.configure(scrollregion=nav_canvas.bbox("all"))
                besoin = nav.winfo_reqheight() > nav_canvas.winfo_height()
                if besoin and not vsb.winfo_ismapped():
                    vsb.pack(side=tk.RIGHT, fill=tk.Y)
                elif not besoin and vsb.winfo_ismapped():
                    vsb.pack_forget()
            except tk.TclError:
                pass

        vsb = tk.Scrollbar(zone, orient="vertical", command=nav_canvas.yview,
                           width=5, bg=COULEURS["sidebar"],
                           troughcolor=COULEURS["sidebar"], bd=0,
                           highlightthickness=0,
                           activebackground="#6366f1")
        nav_canvas.configure(yscrollcommand=vsb.set)
        nav.bind("<Configure>", _maj_region)
        nav_canvas.bind("<Configure>",
                        lambda e: (nav_canvas.itemconfigure(fenetre, width=e.width),
                                   _maj_region()))

        def _molette(event):
            try:
                if (nav_canvas.winfo_exists() and
                        nav.winfo_reqheight() > nav_canvas.winfo_height()):
                    nav_canvas.yview_scroll(-1 * (event.delta // 120), "units")
            except tk.TclError:
                pass

        nav_canvas.bind("<Enter>",
                        lambda e: nav_canvas.bind_all("<MouseWheel>", _molette))
        nav_canvas.bind("<Leave>",
                        lambda e: nav_canvas.unbind_all("<MouseWheel>"))

        # Label section
        tk.Label(nav, text="MENU", font=(POLICE, 7, "bold"),
                 bg=COULEURS["sidebar"],
                 fg=COULEURS["sidebar_text"],
                 anchor="w").pack(fill=tk.X, padx=20, pady=(8, 2))

        self.entrees_menu = [
            ("📊", "Tableau de bord", self.afficher_dashboard, None, "F12"),
            ("📝", "Enregistrer vente", self.afficher_caisse, "caisse", "F2"),
            ("📦", "Produits", self.afficher_produits, None, "F3"),
            ("📋", "Stock", self.afficher_stock, "stock", "F4"),
            ("👥", "Clients", self.afficher_clients, None, "F5"),
            ("💳", "Créances", self.afficher_creances, "rapports", "F9"),
            ("💰", "Analyse", self.afficher_analyse, "rapports", "F10"),
        ]

        self.entrees_menu_second = [
            ("⚙️", "Paramètres", self.afficher_parametres, "admin", None),
        ]

        self.boutons_menu = []

        for icone, libelle, action, droit, touche in self.entrees_menu:
            self._ajouter_bouton_menu(nav, icone, libelle, action, droit, touche)

        # Séparateur avant section secondaire
        tk.Frame(nav, bg=COULEURS["sidebar_sep"], height=1).pack(
            fill=tk.X, padx=20, pady=(8, 4))
        tk.Label(nav, text="GESTION", font=(POLICE, 7, "bold"),
                 bg=COULEURS["sidebar"],
                 fg=COULEURS["sidebar_text"],
                 anchor="w").pack(fill=tk.X, padx=20, pady=(0, 2))

        for icone, libelle, action, droit, touche in self.entrees_menu_second:
            self._ajouter_bouton_menu(nav, icone, libelle, action, droit, touche)

        # ── Accordéon « Plus » ──
        self._plus_ouvert = False

        plus_header = tk.Frame(nav, bg=COULEURS["sidebar"])
        plus_header.pack(fill=tk.X, padx=8, pady=(2, 0))

        self._icone_chevron = tk.StringVar(value="▸")
        self._btn_plus = tk.Button(
            plus_header,
            text="  🗂   Plus",
            font=(POLICE, 10), bg=COULEURS["sidebar"],
            fg=COULEURS["sidebar_text"],
            activebackground=COULEURS["sidebar_hover"],
            activeforeground="white",
            bd=0, anchor="w", padx=6, pady=9,
            highlightthickness=0, cursor="hand2",
            command=self._basculer_plus)
        self._btn_plus.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._lbl_chevron = tk.Label(
            plus_header, text="▸", font=(POLICE, 9),
            bg=COULEURS["sidebar"], fg=COULEURS["sidebar_text"])
        self._lbl_chevron.pack(side=tk.RIGHT, padx=(0, 14))

        for w in (self._btn_plus, self._lbl_chevron, plus_header):
            w.bind("<Enter>", lambda e: (
                self._btn_plus.configure(bg=COULEURS["sidebar_hover"],
                                         fg="white"),
                self._lbl_chevron.configure(bg=COULEURS["sidebar_hover"],
                                            fg="white")))
            w.bind("<Leave>", lambda e: (
                self._btn_plus.configure(bg=COULEURS["sidebar"],
                                         fg=COULEURS["sidebar_text"]),
                self._lbl_chevron.configure(bg=COULEURS["sidebar"],
                                            fg=COULEURS["sidebar_text"])))

        # Frame caché des entrées supplémentaires
        self._frame_plus = tk.Frame(nav, bg=COULEURS["sidebar"])

        entrees_plus = [
            ("💹", "Rapports", self.afficher_rapports, "rapports"),
            ("📈", "Mouvements", self.afficher_mouvements, None),
            ("🛒", "Achats", self.afficher_achats, "stock"),
            ("📋", "Inventaire", self.afficher_inventaire, "stock"),
            ("↩️", "Retours", self.afficher_retours, "caisse"),
            ("📉", "Prévisions", self.afficher_previsions, "stock"),
            ("🏬", "Dépôts", self.afficher_depots, "stock"),
            ("📁", "Catégories", self.afficher_categories, "produits"),
            ("🏭", "Fournisseurs", self.afficher_fournisseurs, "produits"),
            ("❓", "Aide", self.afficher_aide, None),
        ]
        for icone, libelle, action, droit in entrees_plus:
            self._ajouter_bouton_menu(self._frame_plus, icone, libelle,
                                      action, droit, None)

        self._planifier(120, _maj_region)


    def _basculer_plus(self):
        """Affiche/masque les entrées supplémentaires avec chevron animé."""
        if self._plus_ouvert:
            self._frame_plus.pack_forget()
            self._lbl_chevron.configure(text="▸")
            self._plus_ouvert = False
        else:
            self._frame_plus.pack(fill=tk.X)
            self._lbl_chevron.configure(text="▾")
            self._plus_ouvert = True


    def _ajouter_bouton_menu(self, parent, icone, libelle, action, droit, touche):
        actif = droit is None or self.peut(droit)

        row = tk.Frame(parent, bg=COULEURS["sidebar"], cursor="hand2" if actif else "arrow")
        row.pack(fill=tk.X, padx=8, pady=1)

        # Indicateur pill vertical (coloré quand actif, transparent sinon)
        pill = tk.Frame(row, bg=COULEURS["sidebar"], width=3)
        pill.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))

        # Icône dans un mini-cadre
        icone_lbl = tk.Label(row, text=icone, font=(POLICE, 13),
                             bg=COULEURS["sidebar"],
                             fg="white" if actif else COULEURS["sidebar_disabled"],
                             width=2)
        icone_lbl.pack(side=tk.LEFT, pady=7)

        texte_lbl = tk.Label(row, text=libelle, font=(POLICE, 10),
                             bg=COULEURS["sidebar"],
                             fg="white" if actif else COULEURS["sidebar_disabled"],
                             anchor="w")
        texte_lbl.pack(side=tk.LEFT, padx=(6, 0), pady=7, fill=tk.X, expand=True)

        def _entrer(e=None):
            if row is not getattr(self, "_menu_actif", None):
                for w in (row, icone_lbl, texte_lbl, pill):
                    w.configure(bg=COULEURS["sidebar_hover"])

        def _quitter(e=None):
            if row is not getattr(self, "_menu_actif", None):
                for w in (row, icone_lbl, texte_lbl, pill):
                    w.configure(bg=COULEURS["sidebar"])

        def _clic(e=None):
            if actif:
                action()
            else:
                self._refus()

        if actif:
            for w in (row, icone_lbl, texte_lbl):
                w.bind("<Enter>", _entrer)
                w.bind("<Leave>", _quitter)
                w.bind("<Button-1>", _clic)

        # Stocker les refs pour pouvoir activer/désactiver
        row._pill = pill
        row._icone = icone_lbl
        row._texte = texte_lbl
        row._actif = actif

        if touche:
            infobulle(row, f"Raccourci : {touche}")

        self.boutons_menu.append(row)


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
        r.bind("<F2>", lambda e: self.afficher_caisse() if self.peut("caisse") else self._refus())
        r.bind("<F3>", lambda e: self.afficher_produits())
        r.bind("<F4>", lambda e: self.afficher_stock() if self.peut("stock") else self._refus())
        r.bind("<F5>", lambda e: self.afficher_clients())
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
            try:
                w.destroy()
            except tk.TclError:
                pass
        for w in self.zone_actions.winfo_children():
            try:
                w.destroy()
            except tk.TclError:
                pass
        self.lbl_titre.configure(text=titre)

        for i, row in enumerate(self.boutons_menu):
            try:
                pill = getattr(row, "_pill", None)
                icone = getattr(row, "_icone", None)
                texte = getattr(row, "_texte", None)
                if pill is None:
                    continue  # entrées non-row (compatibilité)
                if i == index_menu:
                    # État actif : fond coloré + pill violet
                    for w in (row, icone, texte):
                        w.configure(bg=COULEURS["sidebar_active"])
                    pill.configure(bg=COULEURS["sidebar_active_pill"])
                    self._menu_actif = row
                else:
                    # État inactif : retour au fond sidebar
                    for w in (row, icone, texte):
                        w.configure(bg=COULEURS["sidebar"])
                    pill.configure(bg=COULEURS["sidebar"])
            except tk.TclError:
                pass

        self._maj_badge_alertes()


    def _maj_badge_alertes(self):
        try:
            nb = db.get_nb_alertes()
        except Exception:
            nb = 0
        try:
            if hasattr(self, 'lbl_alertes') and self.lbl_alertes.winfo_exists():
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
            traceback.print_exc()
        self._sync_cloud()
        self.root.destroy()

    def _sauvegarde_auto_horaire(self):
        """Sauvegarde automatique en arrière-plan toutes les heures sans déranger l'utilisateur."""
        try:
            db.sauvegarder_base()
            self._sync_cloud()
        except Exception:
            self._sauvegarde_auto_erreur = True
        self._planifier(3600000, self._sauvegarde_auto_horaire)

    def _sync_cloud(self):
        """Copie la base vers le dossier partage (OneDrive, reseau...).
        
        Force un checkpoint WAL avant copie pour garantir un .db complet.
        """
        dossier = self.params.get("dossier_synchro", "")
        if not dossier or not os.path.isdir(dossier):
            return
        try:
            # Forcer l'écriture du WAL dans le .db principal
            conn = db.get_connection()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            cible = os.path.join(dossier, "gestion_piece_auto.db")
            shutil.copy2(db.DB_PATH, cible)
        except Exception:
            traceback.print_exc()  # ne jamais bloquer la caisse, mais tracer l'erreur

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
