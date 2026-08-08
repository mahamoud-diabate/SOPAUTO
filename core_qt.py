"""
SODIPAC - Application Principale PyQt6 (QMainWindow, Sidebar, 18 Modules)
"""
from datetime import datetime
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QCursor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFrame, QMessageBox, QScrollArea
)

import database as db
from ui_qt import get_qss, PALETTES_QT, THEME_ACTUEL
from page_dashboard_qt import PageDashboardQt
from page_caisse_qt import PageCaisseQt
from page_produits_qt import PageProduitsQt
from page_modules_qt import PageStockQt, PageClientsQt, PageCreancesQt, PageRapportsQt
from page_modules_complets_qt import (
    PageAchatsQt, PageInventaireQt, PageRetoursQt, PagePrevisionsQt, PageDepotsQt,
    PageCategoriesQt, PageFournisseursQt, PageVehiculesQt, PageMouvementsQt,
    PageParametresQt, PageAideQt
)


class SidebarButtonQt(QFrame):
    """Bouton de navigation Sidebar avec pill-indicator vertical."""

    def __init__(self, icone, texte, index, callback, parent=None):
        super().__init__(parent)
        self.index = index
        self.callback = callback
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        l = QHBoxLayout(self)
        l.setContentsMargins(4, 6, 12, 6)
        l.setSpacing(10)

        self.pill = QFrame()
        self.pill.setFixedWidth(4)
        self.pill.setStyleSheet("background-color: transparent; border-radius: 2px;")
        l.addWidget(self.pill)

        lbl_ic = QLabel(icone)
        lbl_ic.setStyleSheet("font-size: 15px; color: #ffffff;")
        l.addWidget(lbl_ic)

        self.lbl_tx = QLabel(texte)
        self.lbl_tx.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: bold;")
        l.addWidget(self.lbl_tx, stretch=1)

    def mousePressEvent(self, event):
        if self.callback:
            self.callback(self.index)

    def set_actif(self, actif):
        c = PALETTES_QT[THEME_ACTUEL[0]]
        if actif:
            self.setStyleSheet(f"background-color: {c['sidebar_active']}; border-radius: 6px;")
            self.pill.setStyleSheet(f"background-color: {c['sidebar_pill']}; border-radius: 2px;")
            self.lbl_tx.setStyleSheet("font-size: 12px; color: #ffffff; font-weight: bold;")
        else:
            self.setStyleSheet("background-color: transparent;")
            self.pill.setStyleSheet("background-color: transparent;")
            self.lbl_tx.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: bold;")


class ApplicationQt(QMainWindow):
    """Fenêtre principale SODIPAC PyQt6 avec 18 modules."""

    def __init__(self, utilisateur):
        super().__init__()
        self.utilisateur = utilisateur
        self.role = utilisateur.get("role", "vendeur")
        db.set_utilisateur_courant(utilisateur["nom_utilisateur"])
        self.params = db.get_parametres()

        self.setWindowTitle(f"{self.params.get('entreprise_nom', 'SODIPAC')} — Gestion Pièce Auto [{utilisateur['nom_utilisateur']}]")
        self.resize(1366, 768)

        self.w_central = QWidget()
        self.w_central.setObjectName("CentralWidget")
        self.setCentralWidget(self.w_central)

        self.l_main = QHBoxLayout(self.w_central)
        self.l_main.setContentsMargins(0, 0, 0, 0)
        self.l_main.setSpacing(0)

        self._construire_sidebar()

        # Zone Droite
        w_droite = QWidget()
        l_droite = QVBoxLayout(w_droite)
        l_droite.setContentsMargins(0, 0, 0, 0)
        l_droite.setSpacing(0)

        self._construire_header(l_droite)

        self.stack = QStackedWidget()
        l_droite.addWidget(self.stack, stretch=1)

        self._construire_pages()

        self.l_main.addWidget(w_droite, stretch=1)

        self.changer_theme(THEME_ACTUEL[0])
        self.naviguer(0)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._maj_horloge)
        self.timer.start(1000)

    def _construire_sidebar(self):
        w_side = QFrame()
        c = PALETTES_QT[THEME_ACTUEL[0]]
        w_side.setFixedWidth(248)
        w_side.setStyleSheet(f"background-color: {c['sidebar']}; border: none;")

        l_side = QVBoxLayout(w_side)
        l_side.setContentsMargins(8, 16, 8, 16)
        l_side.setSpacing(8)

        # Logo Header
        lbl_logo = QLabel("🚗 SODIPAC")
        lbl_logo.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
        lbl_sub = QLabel("Gestion Pièce Auto")
        lbl_sub.setStyleSheet("font-size: 11px; color: #6366f1; font-weight: bold;")
        l_side.addWidget(lbl_logo)
        l_side.addWidget(lbl_sub)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #1e293b;")
        l_side.addWidget(sep)

        # Scroll Area pour la Sidebar
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        w_scroll = QWidget()
        l_scroll = QVBoxLayout(w_scroll)
        l_scroll.setContentsMargins(0, 0, 0, 0)
        l_scroll.setSpacing(4)

        self.btn_menu_list = []

        # Menu Principal (7 modules principaux)
        entrees_principales = [
            ("📊", "Tableau de bord"),
            ("📝", "Enregistrer vente"),
            ("📦", "Produits"),
            ("📋", "Stock"),
            ("👥", "Clients"),
            ("💳", "Créances"),
            ("💹", "Rapports"),
        ]

        for idx, (ic, txt) in enumerate(entrees_principales):
            btn = SidebarButtonQt(ic, txt, idx, self.naviguer)
            self.btn_menu_list.append(btn)
            l_scroll.addWidget(btn)

        # Bouton Accordéon "Plus ▸"
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background-color: #1e293b;")
        l_scroll.addWidget(sep2)

        self.btn_plus = QPushButton("  🗂   Plus ▾")
        self.btn_plus.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_plus.setStyleSheet("background: transparent; color: #94a3b8; font-weight: bold; text-align: left; padding: 8px; border: none;")
        self.btn_plus.clicked.connect(self._toggle_plus)
        l_scroll.addWidget(self.btn_plus)

        # Zone Accordéon Cachée (11 modules secondaires)
        self.w_plus = QWidget()
        l_plus = QVBoxLayout(self.w_plus)
        l_plus.setContentsMargins(0, 0, 0, 0)
        l_plus.setSpacing(4)

        entrees_secondaires = [
            ("🛒", "Achats"),
            ("📋", "Inventaire"),
            ("↩️", "Retours"),
            ("📉", "Prévisions"),
            ("🏬", "Dépôts"),
            ("📁", "Catégories"),
            ("🏭", "Fournisseurs"),
            ("🚗", "Véhicules"),
            ("📈", "Mouvements"),
            ("⚙️", "Paramètres"),
            ("❓", "Aide"),
        ]

        for idx, (ic, txt) in enumerate(entrees_secondaires, start=7):
            btn = SidebarButtonQt(ic, txt, idx, self.naviguer)
            self.btn_menu_list.append(btn)
            l_plus.addWidget(btn)

        l_scroll.addWidget(self.w_plus)
        scroll.setWidget(w_scroll)
        l_side.addWidget(scroll, stretch=1)

        # Profil Utilisateur bas
        user_card = QFrame()
        user_card.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 8px;")
        l_u = QVBoxLayout(user_card)
        lbl_u = QLabel(f"👤 {self.utilisateur.get('nom_complet') or self.utilisateur['nom_utilisateur']}")
        lbl_u.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
        lbl_r = QLabel(self.role.capitalize())
        lbl_r.setStyleSheet("color: #34d399; font-size: 10px;")
        l_u.addWidget(lbl_u)
        l_u.addWidget(lbl_r)

        l_side.addWidget(user_card)

        self.l_main.addWidget(w_side)

    def _toggle_plus(self):
        visible = not self.w_plus.isVisible()
        self.w_plus.setVisible(visible)
        self.btn_plus.setText("  🗂   Plus ▾" if visible else "  🗂   Plus ▸")

    def _construire_header(self, layout):
        h_frame = QFrame()
        h_frame.setFixedHeight(56)
        c = PALETTES_QT[THEME_ACTUEL[0]]
        h_frame.setStyleSheet(f"background-color: {c['card']}; border-bottom: 2px solid {c['primary']};")

        l_h = QHBoxLayout(h_frame)
        l_h.setContentsMargins(20, 0, 20, 0)

        self.lbl_titre_page = QLabel("Tableau de bord")
        self.lbl_titre_page.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {c['text']};")
        l_h.addWidget(self.lbl_titre_page)

        l_h.addStretch()

        self.lbl_horloge = QLabel("")
        self.lbl_horloge.setStyleSheet(f"color: {c['text_secondary']}; font-weight: bold;")
        l_h.addWidget(self.lbl_horloge)

        self.btn_th = QPushButton("🌙" if THEME_ACTUEL[0] == "clair" else "☀️")
        self.btn_th.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_th.setStyleSheet("border: none; font-size: 16px;")
        self.btn_th.clicked.connect(self._toggle_theme)
        l_h.addWidget(self.btn_th)

        layout.addWidget(h_frame)

    def _construire_pages(self):
        # 18 Vues PyQt6
        self.pages = [
            PageDashboardQt(),
            PageCaisseQt(),
            PageProduitsQt(),
            PageStockQt(),
            PageClientsQt(),
            PageCreancesQt(),
            PageRapportsQt(),
            PageAchatsQt(),
            PageInventaireQt(),
            PageRetoursQt(),
            PagePrevisionsQt(),
            PageDepotsQt(),
            PageCategoriesQt(),
            PageFournisseursQt(),
            PageVehiculesQt(),
            PageMouvementsQt(),
            PageParametresQt(),
            PageAideQt(),
        ]

        for p in self.pages:
            self.stack.addWidget(p)

    def naviguer(self, index):
        self.stack.setCurrentIndex(index)
        titles = [
            "Tableau de bord", "Enregistrer Vente", "Catalogue Produits", "Gestion des Stocks",
            "Clients", "Créances", "Rapports & Ventes", "Achats & Approvisionnements",
            "Inventaire de Stock", "Retours Clients", "Prévisions & Reappro", "Dépôts & Magasins",
            "Catégories Articles", "Fournisseurs", "Véhicules & Compatibilités", "Mouvements de Stock",
            "Paramètres Système", "Aide & Guide"
        ]
        if index < len(titles):
            self.lbl_titre_page.setText(titles[index])

        for btn in self.btn_menu_list:
            btn.set_actif(btn.index == index)

        w = self.stack.currentWidget()
        if hasattr(w, 'charger_donnees'):
            w.charger_donnees()
        elif hasattr(w, 'charger'):
            w.charger()

    def _maj_horloge(self):
        self.lbl_horloge.setText(datetime.now().strftime("%A %d %B %Y — %H:%M:%S").capitalize())

    def _toggle_theme(self):
        nouveau = "sombre" if THEME_ACTUEL[0] == "clair" else "clair"
        self.changer_theme(nouveau)

    def changer_theme(self, theme):
        THEME_ACTUEL[0] = theme
        self.setStyleSheet(get_qss(theme))
        self.btn_th.setText("🌙" if theme == "clair" else "☀️")
