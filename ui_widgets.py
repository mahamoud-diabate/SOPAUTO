"""SODIPAC - Thème, helpers et widgets réutilisables"""

import tkinter as tk
from tkinter import ttk
from typing import Any

# ─── PALETTES CLAIR / SOMBRE ─────────────────────────

PALETTES = {
    "clair": {
        "primary": "#2563eb",
        "primary_dark": "#1d4ed8",
        "primary_light": "#dbeafe",
        "secondary": "#64748b",
        "success": "#16a34a",
        "success_light": "#dcfce7",
        "danger": "#dc2626",
        "danger_light": "#fee2e2",
        "warning": "#ea580c",
        "warning_light": "#ffedd5",
        "info": "#0284c7",
        "info_light": "#e0f2fe",
        "bg": "#f1f5f9",
        "card": "#ffffff",
        "sidebar": "#0f172a",
        "sidebar_text": "#94a3b8",
        "sidebar_hover": "#1e293b",
        "sidebar_active": "#1e3a5f",
        "sidebar_sep": "#1e293b",
        "sidebar_disabled": "#475569",
        "text": "#0f172a",
        "text_secondary": "#64748b",
        "border": "#e2e8f0",
        "row_alt": "#f8fafc",
        "alerte_bg": "#fef2f2",
        "rupture_bg": "#fecaca",
        "heading": "#e2e8f0",
        "heading_hover": "#cbd5e1",
        "selection": "#dbeafe",
        "selection_fg": "#0f172a",
        "statusbar": "#e2e8f0",
        "input_bg": "#ffffff",
        "input_fg": "#0f172a",
        "total_bg": "#f7f9fc",
        "canvas_grid": "#eef1f5",
        "bar_other": "#7aa7e8",
        "tooltip_bg": "#1e293b",
        "graph_line": "#2563eb",
    },
    "sombre": {
        "primary": "#3b82f6",
        "primary_dark": "#2563eb",
        "primary_light": "#1e3a5f",
        "secondary": "#94a3b8",
        "success": "#4ade80",
        "success_light": "#14532d",
        "danger": "#f87171",
        "danger_light": "#7f1d1d",
        "warning": "#fb923c",
        "warning_light": "#7c2d12",
        "info": "#38bdf8",
        "info_light": "#0c4a6e",
        "bg": "#0f172a",
        "card": "#1e293b",
        "sidebar": "#020617",
        "sidebar_text": "#94a3b8",
        "sidebar_hover": "#1e293b",
        "sidebar_active": "#1e3a5f",
        "sidebar_sep": "#1e293b",
        "sidebar_disabled": "#475569",
        "text": "#e2e8f0",
        "text_secondary": "#94a3b8",
        "border": "#334155",
        "row_alt": "#243247",
        "alerte_bg": "#452a12",
        "rupture_bg": "#5f1e1e",
        "heading": "#334155",
        "heading_hover": "#475569",
        "selection": "#1e3a5f",
        "selection_fg": "#e2e8f0",
        "statusbar": "#1e293b",
        "input_bg": "#0f172a",
        "input_fg": "#e2e8f0",
        "total_bg": "#16223a",
        "canvas_grid": "#293548",
        "bar_other": "#3b5f8f",
        "tooltip_bg": "#334155",
        "graph_line": "#60a5fa",
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


def appliquer_theme(root) -> ttk.Style | None:
    """Configure les styles ttk de l'application."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", font=(POLICE, 10))
    style.configure(".", background=COULEURS["bg"], foreground=COULEURS["text"])

    style.configure("Treeview",
                    background=COULEURS["card"],
                    fieldbackground=COULEURS["card"],
                    foreground=COULEURS["text"],
                    rowheight=30,
                    borderwidth=0,
                    font=(POLICE, 10))
    style.configure("Treeview.Heading",
                    background=COULEURS["heading"],
                    foreground=COULEURS["text"],
                    relief="flat",
                    font=(POLICE, 10, "bold"),
                    padding=(8, 7))
    style.map("Treeview.Heading", background=[("active", COULEURS["heading_hover"])],
              foreground=[("active", COULEURS["primary"])])
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
    """Treeview avec tri au clic sur les en-têtes."""

    def __init__(self, master, colonnes: list | dict, **kwargs):
        super().__init__(master, columns=[c[0] for c in colonnes], show="headings", **kwargs)
        self._numeriques = set()
        self._sens = {}
        for nom, titre, largeur, ancre, numerique in colonnes:
            self.heading(nom, text=titre, command=lambda c=nom: self.trier(c))
            self.column(nom, width=largeur, anchor=ancre, stretch=(nom in ("nom", "produit")))
            if numerique:
                self._numeriques.add(nom)
        config_lignes_alternees(self)

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


def ajouter_scrollbars(parent, widget) -> tuple:
    """Place un widget avec scrollbars verticale et horizontale dans une grille."""
    vsb = ttk.Scrollbar(parent, orient="vertical", command=widget.yview)
    hsb = ttk.Scrollbar(parent, orient="horizontal", command=widget.xview)
    widget.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    widget.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    parent.rowconfigure(0, weight=1)
    parent.columnconfigure(0, weight=1)
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
