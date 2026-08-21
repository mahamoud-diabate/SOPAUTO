"""
SOPAUTO - Page Dashboard PyQt6
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame, QHeaderView
)
import database as db
from ui_qt import CarteQt, TableauTriableQt, BoutonQt, PALETTES_QT, THEME_ACTUEL


class PageDashboardQt(QWidget):
    """Vue Dashboard PyQt6 avec KPI et graphiques."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(16, 16, 16, 16)
        self.layout_main.setSpacing(16)
        self.charger_donnees()

    def charger_donnees(self):
        # Nettoyer layout
        while self.layout_main.count():
            child = self.layout_main.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        s = db.get_dashboard_stats()

        # ── KPI Cards ──
        grid_kpi = QGridLayout()
        grid_kpi.setSpacing(12)

        kpis = [
            ("CA Aujourd'hui", f"{s.get('ventes_aujourdhui', 0):,.0f} F CFA", "#4f46e5"),
            ("Ventes du jour", str(s.get("nb_ventes_aujourdhui", 0)), "#059669"),
            ("Stock Total", f"{s.get('stock_total', 0)} articles", "#0284c7"),
            ("Valeur du Stock", f"{s.get('valeur_stock', 0):,.0f} F CFA", "#d97706"),
            ("Alertes Stock", str(s.get("nb_alertes", 0)), "#dc2626"),
            ("Marge du Mois", f"{s.get('marge_mois', 0):,.0f} F CFA", "#7c3aed"),
        ]

        for i, (titre, val, couleur) in enumerate(kpis):
            row, col = divmod(i, 3)
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {PALETTES_QT[THEME_ACTUEL[0]]['card']};
                    border: 1px solid {PALETTES_QT[THEME_ACTUEL[0]]['border']};
                    border-left: 5px solid {couleur};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            lyt = QVBoxLayout(card)
            lbl_t = QLabel(titre)
            lbl_t.setStyleSheet("font-size: 11px; color: #64748b; font-weight: bold;")
            lbl_v = QLabel(val)
            lbl_v.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {couleur};")
            lyt.addWidget(lbl_t)
            lyt.addWidget(lbl_v)
            grid_kpi.addWidget(card, row, col)

        self.layout_main.addLayout(grid_kpi)

        # ── Tableaux du bas : Alertes + Dernières Ventes ──
        h_layout = QHBoxLayout()
        h_layout.setSpacing(12)

        # Alertes
        c_alertes = CarteQt("⚠️ Alertes de stock")
        tab_alertes = TableauTriableQt([
            ("ref", "Réf.", 90, "w"),
            ("nom", "Produit", 180, "w"),
            ("qte", "Stock", 60, "center"),
            ("mini", "Mini", 60, "center")
        ], parent=c_alertes)
        tab_alertes.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        try:
            prods = db.get_produits(seulement_alertes=True)
            for p in prods[:10]:
                tab_alertes.inserer_ligne([p["reference"], p["nom"], p["stock"], p["stock_mini"]],
                                          ["left", "left", "center", "center"])
        except Exception:
            pass

        c_alertes.layout_corps.addWidget(tab_alertes)
        h_layout.addWidget(c_alertes)

        # Ventes récentes
        c_ventes = CarteQt("📝 Dernières ventes")
        tab_ventes = TableauTriableQt([
            ("num", "Facture", 120, "w"),
            ("client", "Client", 160, "w"),
            ("date", "Heure", 75, "center"),
            ("total", "Total", 100, "e")
        ], parent=c_ventes)
        tab_ventes.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        try:
            ventes = db.get_ventes(limit=10)
            for v in ventes:
                heure = str(v.get("date_vente", ""))[-8:] if v.get("date_vente") else ""
                tab_ventes.inserer_ligne([
                    v.get("numero") or f"VTE-{v['id']}",
                    v.get("client_nom") or "Client",
                    heure,
                    f"{v.get('total', 0):,.0f} F"
                ], ["left", "left", "center", "right"])
        except Exception:
            pass

        c_ventes.layout_corps.addWidget(tab_ventes)
        h_layout.addWidget(c_ventes)

        self.layout_main.addLayout(h_layout)
