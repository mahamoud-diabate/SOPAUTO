"""
SODIPAC - Interface PyQt6 (Design System & Palette identique à Tkinter)
"""
import sys
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon, QPalette, QCursor
from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QScrollArea, QSplitter
)

# ─── PALETTE IDENTIQUE À TKINTER ─────────────────────────
PALETTES_QT = {
    "clair": {
        "primary": "#4f46e5",
        "primary_dark": "#4338ca",
        "primary_light": "#e0e7ff",
        "secondary": "#64748b",
        "success": "#059669",
        "danger": "#dc2626",
        "warning": "#d97706",
        "info": "#0284c7",
        "bg": "#f8fafc",
        "card": "#ffffff",
        "sidebar": "#0f172a",
        "sidebar_text": "#94a3b8",
        "sidebar_hover": "#1e3a5f",
        "sidebar_active": "#1e3a5f",
        "sidebar_pill": "#6366f1",
        "sidebar_sep": "#1e293b",
        "sidebar_disabled": "#374151",
        "text": "#0f172a",
        "text_secondary": "#64748b",
        "border": "#cbd5e1",
        "row_alt": "#f1f5f9",
        "statusbar": "#f1f5f9",
        "input_bg": "#ffffff",
        "input_fg": "#0f172a",
        "table_header": "#e0e7ff",
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
        "danger": "#ef4444",
        "warning": "#f59e0b",
        "info": "#06b6d4",
        "bg": "#0b0f19",
        "card": "#151c2c",
        "sidebar": "#070a12",
        "sidebar_text": "#94a3b8",
        "sidebar_hover": "#0d2137",
        "sidebar_active": "#0d2137",
        "sidebar_pill": "#6366f1",
        "sidebar_sep": "#1a2236",
        "sidebar_disabled": "#374151",
        "text": "#f1f5f9",
        "text_secondary": "#94a3b8",
        "border": "#26334d",
        "row_alt": "#1a2336",
        "statusbar": "#151c2c",
        "input_bg": "#0b0f19",
        "input_fg": "#f1f5f9",
        "table_header": "#1e293b",
        "table_header_fg": "#818cf8",
        "table_even": "#151c2c",
        "table_odd": "#1a2336",
    }
}

THEME_ACTUEL = ["clair"]


def get_qss(theme="clair"):
    c = PALETTES_QT[theme]
    return f"""
        QMainWindow, QWidget#CentralWidget {{
            background-color: {c['bg']};
            color: {c['text']};
            font-family: 'Segoe UI', 'SF Pro Text', Arial, sans-serif;
            font-size: 13px;
        }}
        QFrame#Carte {{
            background-color: {c['card']};
            border: 1px solid {c['border']};
            border-radius: 8px;
        }}
        QLabel#CarteTitre {{
            font-weight: bold;
            font-size: 14px;
            color: {c['text']};
            background: transparent;
        }}
        QTableWidget {{
            background-color: {c['card']};
            color: {c['text']};
            border: 1px solid {c['border']};
            gridline-color: {c['border']};
            border-radius: 6px;
            font-size: 12px;
            selection-background-color: {c['primary_light']};
            selection-color: {c['primary_dark']};
        }}
        QHeaderView::section {{
            background-color: {c['table_header']};
            color: {c['table_header_fg']};
            font-weight: bold;
            font-size: 12px;
            padding: 8px;
            border: none;
            border-bottom: 2px solid {c['primary']};
        }}
        QLineEdit {{
            background-color: {c['input_bg']};
            color: {c['input_fg']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 13px;
        }}
        QLineEdit:focus {{
            border: 2px solid {c['primary']};
        }}
        QComboBox {{
            background-color: {c['card']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 5px 10px;
        }}
        QPushButton {{
            border-radius: 6px;
            padding: 7px 14px;
            font-weight: bold;
            font-size: 12px;
        }}
    """


class CarteQt(QFrame):
    """Carte conteneur professionnelle identique au style Tkinter SODIPAC."""

    def __init__(self, titre="", parent=None):
        super().__init__(parent)
        self.setObjectName("Carte")
        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setContentsMargins(14, 14, 14, 14)
        self.layout_principal.setSpacing(10)

        if titre:
            self.lbl_titre = QLabel(titre)
            self.lbl_titre.setObjectName("CarteTitre")
            self.layout_principal.addWidget(self.lbl_titre)

        self.corps = QWidget()
        self.layout_corps = QVBoxLayout(self.corps)
        self.layout_corps.setContentsMargins(0, 0, 0, 0)
        self.layout_principal.addWidget(self.corps)


class TableauTriableQt(QTableWidget):
    """Tableau réutilisable avec entêtes soignées et lignes alternées."""

    def __init__(self, colonnes, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(colonnes))
        headers = [c[1] for c in colonnes]
        self.setHorizontalHeaderLabels(headers)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        for i, col in enumerate(colonnes):
            largeur = col[2]
            self.setColumnWidth(i, largeur)

        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)

    def inserer_ligne(self, valeurs, alignements=None):
        row_idx = self.rowCount()
        self.insertRow(row_idx)
        for col_idx, val in enumerate(valeurs):
            item = QTableWidgetItem(str(val))
            if alignements and col_idx < len(alignements):
                align = alignements[col_idx]
                if align == "center":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif align == "e" or align == "right":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(row_idx, col_idx, item)

    def vider(self):
        self.setRowCount(0)


class BoutonQt(QPushButton):
    """Bouton stylisé identique au composant Bouton Tkinter SODIPAC."""

    def __init__(self, texte, variante="primary", callback=None, parent=None):
        super().__init__(texte, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        c = PALETTES_QT[THEME_ACTUEL[0]]
        bg = c.get(variante, c["primary"])
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {bg}dd;
            }}
        """)
        if callback:
            self.clicked.connect(callback)


class EntreeRechercheQt(QLineEdit):
    """Champ de recherche réactif."""

    def __init__(self, placeholder="Rechercher…", callback=None, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        if callback:
            self.textChanged.connect(callback)
