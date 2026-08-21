"""
SOPAUTO - Thème, helpers et widgets réutilisables
"""
import tkinter as tk
from tkinter import ttk
from typing import Any

# ─── PALETTES CLAIR / SOMBRE ─────────────────────────

PALETTES = {
    "clair": {
        "primary": "#4f46e5",
        "primary_dark": "#4338ca",
        "primary_light": "#e0e7ff",
        "secondary": "#64748b",
        "success": "#059669",
        "success_light": "#d1fae5",
        "danger": "#dc2626",
        "danger_light": "#fee2e2",
        "warning": "#d97706",
        "warning_light": "#fef3c7",
        "info": "#0284c7",
        "info_light": "#e0f2fe",
        "bg": "#f8fafc",
        "card": "#ffffff",
        "sidebar": "#0f172a",
        "sidebar_text": "#94a3b8",
        "sidebar_hover": "#1e3a5f",
        "sidebar_active": "#1e3a5f",
        "sidebar_active_pill": "#6366f1",
        "sidebar_accent": "#818cf8",
        "sidebar_sep": "#1e293b",
        "sidebar_disabled": "#374151",
        "text": "#0f172a",
        "text_secondary": "#64748b",
        "border": "#cbd5e1",
        "row_alt": "#e2e8f0",
        "alerte_bg": "#fffbeb",
        "rupture_bg": "#fef2f2",
        "heading": "#e2e8f0",
        "heading_hover": "#cbd5e1",
        "selection": "#e0e7ff",
        "selection_fg": "#3730a3",
        "statusbar": "#f1f5f9",
        "input_bg": "#ffffff",
        "input_fg": "#0f172a",
        "total_bg": "#eff6ff",
        "canvas_grid": "#eef1f5",
        "bar_other": "#818cf8",
        "tooltip_bg": "#0f172a",
        "table_header_bg": "#e0e7ff",
        "table_header_fg": "#3730a3",
        "table_even": "#f8fafc",
        "table_odd": "#ffffff",
    },
    "sombre": {
        "primary": "#6366f1",
        "primary_dark": "#4f46e5",
        "primary_light": "#252e4a",
        "secondary": "#94a3b8",
        "success": "#10b981",
        "success_light": "#064e3b",
        "danger": "#ef4444",
        "danger_light": "#7f1d1d",
        "warning": "#f59e0b",
        "warning_light": "#78350f",
        "info": "#06b6d4",
        "info_light": "#164e63",
        "bg": "#0b0f19",
        "card": "#151c2c",
        "sidebar": "#070a12",
        "sidebar_text": "#94a3b8",
        "sidebar_hover": "#0d2137",
        "sidebar_active": "#0d2137",
        "sidebar_active_pill": "#6366f1",
        "sidebar_accent": "#818cf8",
        "sidebar_sep": "#1a2236",
        "sidebar_disabled": "#374151",
        "text": "#f1f5f9",
        "text_secondary": "#94a3b8",
        "border": "#26334d",
        "row_alt": "#1a2336",
        "alerte_bg": "#451a03",
        "rupture_bg": "#450a0a",
        "heading": "#1e293b",
        "heading_hover": "#334155",
        "selection": "#312e81",
        "selection_fg": "#ffffff",
        "statusbar": "#151c2c",
        "input_bg": "#0b0f19",
        "input_fg": "#f1f5f9",
        "total_bg": "#1e1b4b",
        "canvas_grid": "#26334d",
        "bar_other": "#6366f1",
        "tooltip_bg": "#1e293b",
        "graph_line": "#818cf8",
        "table_even": "#151c2c",
        "table_odd": "#1a2336",
        # Ces deux cles manquaient au theme sombre : `.get()` retombait sur
        # l'indigo clair du theme clair et les en-tetes de tableaux restaient
        # clairs sur fond sombre.
        "table_header_bg": "#252e4a",
        "table_header_fg": "#a5b4fc",
    },
}

COULEURS = dict(PALETTES["clair"])
THEME_ACTUEL = ["clair"]


def appliquer_palette(nom: str) -> str:
    """Bascule la palette globale (clair / sombre)."""
    nom = nom if nom in PALETTES else "clair"
    COULEURS.clear()
    COULEURS.update(PALETTES[nom])
    THEME_ACTUEL[0] = nom
    return nom


POLICE = "Segoe UI"


def appliquer_theme(root, factor=1.0) -> ttk.Style | None:
    """Configure les styles ttk de l'application avec taille adaptative."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    taille_base = max(8, min(14, int(10 * factor)))
    taille_titre = max(9, min(15, int(10 * factor)))
    row_h = max(26, min(42, int(34 * factor)))

    style.configure(".", font=(POLICE, taille_base))
    style.configure(".", background=COULEURS["bg"], foreground=COULEURS["text"])

    style.configure("Treeview",
                    background=COULEURS["card"],
                    fieldbackground=COULEURS["card"],
                    foreground=COULEURS["text"],
                    rowheight=row_h,
                    borderwidth=1,
                    relief="solid",
                    font=(POLICE, taille_base))
    style.configure("Treeview.Heading",
                    background=COULEURS["table_header_bg"],
                    foreground=COULEURS["table_header_fg"],
                    relief="solid",
                    borderwidth=1,
                    font=(POLICE, taille_titre, "bold"),
                    padding=(10, 8))
    style.map("Treeview.Heading",
              background=[("active", COULEURS.get("primary_light", "#c7d2fe"))],
              foreground=[("active", COULEURS.get("primary", "#4f46e5"))])
    style.map("Treeview",
              background=[("selected", COULEURS["selection"])],
              foreground=[("selected", COULEURS["selection_fg"])])

    style.configure("TNotebook", background=COULEURS["bg"], borderwidth=0)
    style.configure("TNotebook.Tab",
                    padding=(20, 10),
                    font=(POLICE, 10),
                    background=COULEURS["heading"],
                    foreground=COULEURS["text"])
    style.map("TNotebook.Tab",
              background=[("selected", COULEURS["card"]), ("!selected", COULEURS["heading_hover"])],
              foreground=[("selected", COULEURS["text"])])

    style.configure("TCombobox", padding=5, arrowsize=14,
                    fieldbackground=COULEURS["input_bg"],
                    background=COULEURS["heading"],
                    foreground=COULEURS["input_fg"],
                    arrowcolor=COULEURS["text"])
    style.map("TCombobox",
              fieldbackground=[("readonly", COULEURS["input_bg"])],
              foreground=[("readonly", COULEURS["input_fg"])],
              selectbackground=[("readonly", COULEURS["input_bg"])],
              selectforeground=[("readonly", COULEURS["input_fg"])])
    root.option_add("*TCombobox*Listbox.background", COULEURS["card"])
    root.option_add("*TCombobox*Listbox.foreground", COULEURS["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", COULEURS["selection"])
    root.option_add("*TCombobox*Listbox.selectForeground", COULEURS["selection_fg"])

    style.configure("TEntry", padding=5,
                    fieldbackground=COULEURS["input_bg"],
                    foreground=COULEURS["input_fg"])
    style.configure("Vertical.TScrollbar", background=COULEURS["heading_hover"],
                    troughcolor=COULEURS["bg"], arrowcolor=COULEURS["text"])
    style.configure("Horizontal.TScrollbar", background=COULEURS["heading_hover"],
                    troughcolor=COULEURS["bg"], arrowcolor=COULEURS["text"])
    style.configure("TProgressbar", background=COULEURS["primary"],
                    troughcolor=COULEURS["heading"])

    # Labels d'état
    style.configure("Etat.TLabel", font=(POLICE, 9, "bold"), padding=(6, 2, 6, 2))

    return style


def config_lignes_alternees(tree) -> None:
    """Active le zébrage + les couleurs d'état standard sur un Treeview."""
    tree.tag_configure("impair", background=COULEURS["row_alt"])
    tree.tag_configure("pair", background=COULEURS["card"])
    tree.tag_configure("alerte", background=COULEURS["alerte_bg"])
    tree.tag_configure("rupture", background=COULEURS["rupture_bg"],
                       foreground=COULEURS["danger"])
    tree.tag_configure("inactif", foreground=COULEURS["text_secondary"])
    tree.tag_configure("annulee", foreground=COULEURS["danger"])
    tree.tag_configure("entree", foreground=COULEURS["success"])
    tree.tag_configure("sortie", foreground=COULEURS["danger"])


def zebre(index: int, extra: list | dict = ()) -> tuple:
    """Retourne les tags de ligne (zébrage + tags additionnels)."""
    return (("pair",) if index % 2 == 0 else ("impair",)) + tuple(extra)


def fmt_money(valeur: float, devise: str = "") -> str:
    try:
        texte = f"{float(valeur or 0):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        texte = "0"
    return f"{texte} {devise}".strip()


def fmt_date(valeur: float, avec_heure: bool = True) -> str:
    if not valeur:
        return ""
    texte = str(valeur)
    try:
        d, h = texte[:10], texte[11:16]
        annee, mois, jour = d.split("-")
        return f"{jour}/{mois}/{annee}" + (f" {h}" if avec_heure and h else "")
    except (ValueError, IndexError):
        return texte[:16]


def centrer_fenetre(fenetre, largeur: Any = None, hauteur: Any = None) -> None:
    fenetre.update_idletasks()
    w = largeur or fenetre.winfo_width()
    h = hauteur or fenetre.winfo_height()
    x = max(0, (fenetre.winfo_screenwidth() - w) // 2)
    y = max(0, (fenetre.winfo_screenheight() - h) // 3)
    fenetre.geometry(f"{w}x{h}+{x}+{y}")


# ─── WIDGETS ─────────────────────────────────────────

class Bouton(tk.Button):
    """Bouton plat avec couleur, survol et curseur main."""

    def __init__(self, master, texte="", couleur="primary", commande=None,
                 petit=False, outline=False, **kwargs):
        if outline:
            bg = COULEURS["card"]
            fg = COULEURS.get(couleur, couleur)
            self._bg = bg
            self._bg_hover = COULEURS.get(couleur + "_light", COULEURS["primary_light"])
        else:
            bg = COULEURS.get(couleur, couleur)
            fg = "white"
            self._bg = bg
            self._bg_hover = self._assombrir(bg)
        self._outline = outline
        super().__init__(
            master, text=texte, command=commande,
            font=(POLICE, 9 if petit else 10, "bold" if not petit else "normal"),
            bg=bg, fg=fg,
            activebackground=self._bg_hover,
            activeforeground=COULEURS.get(couleur, couleur) if outline else "white",
            bd=0, relief=tk.FLAT, cursor="hand2",
            padx=kwargs.pop("padx", 12 if petit else 18),
            pady=kwargs.pop("pady", 4 if petit else 8),
            highlightthickness=0, **kwargs)
        self.bind("<Enter>", lambda e: self.configure(bg=self._bg_hover))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg))

    @staticmethod
    def _assombrir(couleur_hex, facteur: float = 0.85):
        try:
            couleur_hex = couleur_hex.lstrip("#")
            r, g, b = (int(couleur_hex[i:i + 2], 16) for i in (0, 2, 4))
            return f"#{int(r*facteur):02x}{int(g*facteur):02x}{int(b*facteur):02x}"
        except ValueError:
            return couleur_hex


class Carte(tk.Frame):
    """Conteneur blanc type « carte »."""

    def __init__(self, master, titre: Any = None, **kwargs):
        super().__init__(master, bg=COULEURS["card"],
                         highlightbackground=COULEURS["border"],
                         highlightthickness=1, **kwargs)
        if titre:
            entete = tk.Frame(self, bg=COULEURS["card"])
            entete.pack(fill=tk.X, padx=14, pady=(12, 4))
            tk.Label(entete, text=titre, font=(POLICE, 11, "bold"),
                     bg=COULEURS["card"], fg=COULEURS["text"]).pack(side=tk.LEFT)
            self.entete = entete
            tk.Frame(self, bg=COULEURS["border"], height=1).pack(fill=tk.X, padx=0)
        self.corps = tk.Frame(self, bg=COULEURS["card"])
        self.corps.pack(fill=tk.BOTH, expand=True, padx=14, pady=(8, 12))


class EntreeRecherche(tk.Frame):
    """Champ de recherche avec icône, effacement et déclenchement différé (anti-lag)."""

    def __init__(self, master, placeholder="Rechercher…", largeur=30,
                 callback=None, delai=250, bg=None):
        bg = bg or COULEURS["bg"]
        super().__init__(master, bg=bg)
        self.callback = callback
        self.delai = delai
        self._apres = None

        cadre = tk.Frame(self, bg=COULEURS["card"],
                         highlightbackground=COULEURS["heading_hover"],
                         highlightthickness=1, highlightcolor=COULEURS["primary"])
        cadre.pack(fill=tk.X)

        tk.Label(cadre, text="🔍", bg=COULEURS["card"],
                 fg=COULEURS["text_secondary"]).pack(side=tk.LEFT, padx=(8, 2))

        self.var = tk.StringVar()
        self.entry = tk.Entry(cadre, textvariable=self.var, font=(POLICE, 10),
                              width=largeur, bd=0, bg=COULEURS["card"],
                              fg=COULEURS["text"], highlightthickness=0,
                              insertbackground=COULEURS["primary"])
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)

        self.btn_clear = tk.Label(cadre, text="✕", bg=COULEURS["card"],
                                  fg=COULEURS["text_secondary"], cursor="hand2")
        self.btn_clear.pack(side=tk.RIGHT, padx=8)
        self.btn_clear.bind("<Button-1>", lambda e: self.effacer())

        self._placeholder = placeholder
        self._afficher_placeholder()
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        # FocusIn avec highlight bleu
        cadre.bind("<FocusIn>", lambda e: cadre.configure(highlightcolor=COULEURS["primary"]),
                   add="+")
        self.var.trace_add("write", self._on_change)

    def _afficher_placeholder(self):
        if not self.var.get():
            self.entry.configure(fg=COULEURS["text_secondary"])
            self._placeholder_actif = True
            self.entry.insert(0, self._placeholder)

    def _on_focus_in(self, _e):
        if getattr(self, "_placeholder_actif", False):
            self.entry.delete(0, tk.END)
            self.entry.configure(fg=COULEURS["text"])
            self._placeholder_actif = False

    def _on_focus_out(self, _e):
        if not self.entry.get():
            self._afficher_placeholder()

    def _on_change(self, *_a):
        if getattr(self, "_placeholder_actif", False):
            return
        if self._apres:
            self.after_cancel(self._apres)
        if self.callback:
            self._apres = self.after(self.delai, self.callback)

    def get(self) -> str:
        return "" if getattr(self, "_placeholder_actif", False) else self.var.get().strip()

    def effacer(self) -> None:
        self._placeholder_actif = False
        self.var.set("")
        self._afficher_placeholder()
        if self.callback:
            self.callback()

    def focus(self) -> None:
        self.entry.focus_set()


class TableauTriable(ttk.Treeview):
    """Treeview avec tri au clic sur les en-têtes et ajustement automatique au texte."""

    def __init__(self, master, colonnes, largeurs=None, **kwargs):
        """
        colonnes: liste de tuples (nom, titre) OU (nom, titre, largeur, ancre, numerique)
        largeurs: dict optionnel {nom: largeur} si format simple utilisé
        """
        self._colonnes_manuelles = set()
        self._largeurs_initiales = {}
        self._numeriques = set()
        self._sens = {}
        self._ajustement_prevu = None

        # Détecter le format
        if colonnes and len(colonnes[0]) == 2:
            noms = [c[0] for c in colonnes]
            super().__init__(master, columns=noms, show="headings", **kwargs)
            largeurs = largeurs or {}
            for nom, titre in colonnes:
                w = largeurs.get(nom, 100)
                self._largeurs_initiales[nom] = w
                self.heading(nom, text=titre, command=lambda c=nom: self.trier(c))
                self.column(nom, width=w, minwidth=max(40, int(w * 0.6)), anchor="center", stretch=True)
        else:
            super().__init__(master, columns=[c[0] for c in colonnes], show="headings", **kwargs)
            for nom, titre, largeur, ancre, numerique in colonnes:
                self._largeurs_initiales[nom] = largeur
                self.heading(nom, text=titre, anchor=ancre, command=lambda c=nom: self.trier(c))
                self.column(nom, width=largeur, minwidth=max(40, int(largeur * 0.6)), anchor=ancre, stretch=True)
                if numerique:
                    self._numeriques.add(nom)
        try:
            self.column("#0", width=0, stretch=False)
        except Exception:
            pass
        config_lignes_alternees(self)
        self.bind("<ButtonRelease-1>", self._sur_redimensionnement_manuel, add="+")

    def _sur_redimensionnement_manuel(self, event):
        """Mémorise les colonnes redimensionnées manuellement à la souris par l'utilisateur."""
        try:
            region = self.identify_region(event.x, event.y)
            if region in ("separator", "heading"):
                col = self.identify_column(event.x)
                if col:
                    idx = int(col.replace("#", "")) - 1
                    cols = self["columns"]
                    if 0 <= idx < len(cols):
                        self._colonnes_manuelles.add(cols[idx])
        except Exception:
            pass

    def ajuster_largeurs_auto(self, max_lignes: int = 100) -> None:
        """Ajuste la largeur des colonnes au texte, sans passer sous la largeur initiale."""
        try:
            children = self.get_children("")
            if not children:
                return
            colonnes = [c for c in self["columns"] if c not in self._colonnes_manuelles]
            if not colonnes:
                return

            # Une seule lecture par ligne (`values`) plutôt qu'un aller-retour Tcl
            # par cellule : sur 11 colonnes, ça divise les appels par onze.
            maxi = {c: len(str(self.heading(c).get("text", "")).rstrip(" ▲▼"))
                    for c in colonnes}
            index_col = {c: list(self["columns"]).index(c) for c in colonnes}
            for child in children[:max_lignes]:
                valeurs = self.item(child, "values")
                for c in colonnes:
                    i = index_col[c]
                    if i < len(valeurs) and valeurs[i]:
                        longueur = len(str(valeurs[i]))
                        if longueur > maxi[c]:
                            maxi[c] = longueur

            for c in colonnes:
                largeur_min = self._largeurs_initiales.get(c, 70)
                self.column(c, width=max(largeur_min, min(450, maxi[c] * 9 + 32)))
        except tk.TclError:
            pass

    def _ajuster_bientot(self) -> None:
        """Regroupe les ajustements en un seul, quand la boucle redevient inactive.

        Chaque insert() relançait un balayage complet du tableau : remplir
        1 900 lignes déclenchait 1 900 balayages, soit ~2 millions d'appels Tcl
        et 14 secondes d'attente. L'ajustement ne dépend que du contenu final,
        une seule passe suffit donc.
        """
        if self._ajustement_prevu is not None:
            return
        try:
            self._ajustement_prevu = self.after_idle(self._ajuster_maintenant)
        except tk.TclError:
            self._ajustement_prevu = None

    def _ajuster_maintenant(self) -> None:
        self._ajustement_prevu = None
        try:
            if self.winfo_exists():
                self.ajuster_largeurs_auto()
        except tk.TclError:
            pass

    def insert(self, parent, index, iid=None, **kwargs):
        res = super().insert(parent, index, iid=iid, **kwargs)
        self._ajuster_bientot()
        return res

    def trier(self, colonne: str) -> None:
        descendant = not self._sens.get(colonne, False)
        self._sens[colonne] = descendant

        def cle(iid):
            v = self.set(iid, colonne)
            if colonne in self._numeriques:
                try:
                    return float(v.replace(" ", "").replace(",", ".")
                                 .replace("F", "").replace("CFA", "").strip() or 0)
                except ValueError:
                    return 0.0
            return v.lower()

        enfants = sorted(self.get_children(""), key=cle, reverse=descendant)
        for i, iid in enumerate(enfants):
            self.move(iid, "", i)
            tags = [t for t in self.item(iid, "tags") if t not in ("pair", "impair")]
            self.item(iid, tags=zebre(i, tags))

        for c in self["columns"]:
            titre = self.heading(c)["text"].rstrip(" ▲▼")
            self.heading(c, text=titre + (" ▼" if descendant else " ▲") if c == colonne else titre)

    def ajouter(self, valeurs: tuple) -> None:
        """Ajoute une ligne au tableau."""
        self.insert("", "end", values=valeurs)


class AutocompleteCombobox(ttk.Combobox):
    """Combobox filtrant les valeurs au fur et à mesure de la saisie."""

    def __init__(self, master: Any = None, **kwargs):
        self._liste = []
        super().__init__(master, **kwargs)
        self.bind("<KeyRelease>", self._on_keyrelease)

    def set_completion_list(self, liste: list | dict) -> None:
        self._liste = sorted(liste, key=str.lower)
        self["values"] = self._liste

    def _on_keyrelease(self, event):
        if event.keysym in ("Left", "Right", "Up", "Down", "Tab", "Return", "Escape"):
            return
        saisi = self.get().lower().strip()
        if not saisi:
            self["values"] = self._liste
            return
        mots = saisi.split()
        self["values"] = [i for i in self._liste if all(m in i.lower() for m in mots)] or self._liste


class KPI(tk.Frame):
    """Widget carte KPI (icône + valeur + label)."""

    def __init__(self, master, icone: str, valeur: str, label: str, tendance: str = None, couleur: str = "primary", **kwargs):
        super().__init__(master, bg=COULEURS["card"], highlightbackground=COULEURS["border"], highlightthickness=1, **kwargs)
        self.pack_propagate(False)

        # Couleur d'accent à gauche
        accent = tk.Frame(self, bg=couleur if isinstance(couleur, str) and couleur.startswith("#") else COULEURS.get(couleur, COULEURS["primary"]), width=4)
        accent.pack(side=tk.LEFT, fill=tk.Y)

        contenu = tk.Frame(self, bg=COULEURS["card"])
        contenu.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Icône + Valeur
        haut = tk.Frame(contenu, bg=COULEURS["card"])
        haut.pack(fill=tk.X)
        tk.Label(haut, text=icone, font=(POLICE, 18), bg=COULEURS["card"], fg=COULEURS["text"]).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(haut, text=valeur, font=(POLICE, 20, "bold"), bg=COULEURS["card"], fg=COULEURS["text"]).pack(side=tk.LEFT)

        # Label
        tk.Label(contenu, text=label, font=(POLICE, 9), bg=COULEURS["card"], fg=COULEURS["text_secondary"]).pack(anchor="w", pady=(4, 0))

        # Tendance optionnelle
        if tendance:
            tk.Label(contenu, text=tendance, font=(POLICE, 8, "bold"), bg=COULEURS["card"], fg=COULEURS["success"]).pack(anchor="w")


class Badge(tk.Label):
    """Badge coloré pour numérotation/états."""

    COULEURS_BADGE = {
        "primary": ("#2563eb", "#dbeafe"),
        "success": ("#16a34a", "#dcfce7"),
        "warning": ("#ea580c", "#ffedd5"),
        "danger": ("#dc2626", "#fee2e2"),
        "info": ("#0284c7", "#e0f2fe"),
        "secondary": ("#64748b", "#e2e8f0"),
    }

    def __init__(self, master, texte: str, variante: str = "primary", **kwargs):
        fg, bg = self.COULEURS_BADGE.get(variante, self.COULEURS_BADGE["primary"])
        super().__init__(master, text=texte, font=(POLICE, 8, "bold"), bg=bg, fg=fg, padx=6, pady=1, **kwargs)


def ajouter_scrollbars(parent, widget) -> tuple:
    """Place un widget avec scrollbars dans une grille tout en verrouillant l'alignement à gauche."""
    vsb = ttk.Scrollbar(parent, orient="vertical", command=widget.yview)
    hsb = ttk.Scrollbar(parent, orient="horizontal", command=widget.xview)
    widget.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    widget.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    parent.rowconfigure(0, weight=1)
    parent.columnconfigure(0, weight=1)

    try:
        widget.column("#0", width=0, stretch=False)
    except Exception:
        pass

    def _recadrer(e=None):
        try:
            widget.xview_moveto(0)
        except Exception:
            pass

    parent.bind("<Configure>", _recadrer, add="+")
    return vsb, hsb


def infobulle(widget, texte: str) -> None:
    """Affiche une infobulle au survol."""
    fenetre = {"w": None}

    def afficher(_e):
        if fenetre["w"] or not texte:
            return
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        w = tk.Toplevel(widget)
        w.wm_overrideredirect(True)
        w.wm_geometry(f"+{x}+{y}")
        tk.Label(w, text=texte, bg=COULEURS["tooltip_bg"], fg="white", font=(POLICE, 9),
                 padx=10, pady=5, justify="left").pack()
        fenetre["w"] = w

    def cacher(_e):
        if fenetre["w"]:
            fenetre["w"].destroy()
            fenetre["w"] = None

    widget.bind("<Enter>", afficher, add="+")
    widget.bind("<Leave>", cacher, add="+")


import re

# ── Utilitaire partagé ──
def parse_float(valeur, defaut: float = 0.0) -> float:
    """Convertit une valeur en float de manière universelle et blindée contre les fautes de frappe."""
    if valeur is None:
        return defaut
    if isinstance(valeur, (int, float)):
        return float(valeur)
    s = str(valeur).strip()
    if not s:
        return defaut
    # Conserver uniquement les chiffres, virgules, points et signe moins
    s = re.sub(r'[^\d.,\-+]', '', s)
    if not s or s in ('-', '+'):
        return defaut
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif '.' in s and ',' not in s:
        parts = s.split('.')
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            s = s.replace('.', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return defaut