"""
SODIPAC - Page Produits PyQt6 (Avec création, modification, suppression, export)
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QComboBox
)
import database as db
import export_pdf
from ui_qt import CarteQt, TableauTriableQt, BoutonQt
from dialogues_qt import DialogueProduitQt


class PageProduitsQt(QWidget):
    """Vue Produits & Catalogue PyQt6."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(16, 16, 16, 16)
        self.layout_main.setSpacing(12)
        self._construire_ui()

    def _construire_ui(self):
        # Barre supérieure d'actions
        barre_act = QHBoxLayout()

        btn_nouveau = BoutonQt("➕ Nouveau produit", "primary", self._nouveau_produit)
        barre_act.addWidget(btn_nouveau)

        btn_edit = BoutonQt("✏️ Modifier", "secondary", self._modifier_produit)
        barre_act.addWidget(btn_edit)

        btn_delete = BoutonQt("🗑️ Supprimer", "danger", self._supprimer_produit)
        barre_act.addWidget(btn_delete)

        self.txt_cherche = QLineEdit()
        self.txt_cherche.setPlaceholderText("Rechercher par référence, nom ou catégorie…")
        self.txt_cherche.textChanged.connect(self._charger_produits)
        barre_act.addWidget(self.txt_cherche)

        btn_refresh = BoutonQt("🔄 Actualiser", "secondary", self._charger_produits)
        barre_act.addWidget(btn_refresh)

        self.layout_main.addLayout(barre_act)

        # Tableau des produits
        carte_table = CarteQt("📦 Catalogue des articles")
        self.tab_produits = TableauTriableQt([
            ("id", "ID", 50, "center"),
            ("ref", "Référence", 110, "w"),
            ("nom", "Nom du Produit", 220, "w"),
            ("cat", "Catégorie", 130, "w"),
            ("px_achat", "P. Achat", 95, "e"),
            ("px_vente", "P. Vente", 95, "e"),
            ("qte", "Stock", 70, "center"),
            ("statut", "Statut", 90, "center")
        ], parent=carte_table)

        self.tab_produits.doubleClicked.connect(self._modifier_produit)
        carte_table.layout_corps.addWidget(self.tab_produits)
        self.layout_main.addWidget(carte_table)

        self._charger_produits()

    def charger(self):
        self._charger_produits()

    def _charger_produits(self):
        self.tab_produits.vider()
        filtre = self.txt_cherche.text().strip().lower()
        try:
            prods = db.get_produits()
            for p in prods:
                if filtre and (filtre not in p["nom"].lower() and filtre not in p["reference"].lower()):
                    continue
                qte = p.get("stock", p.get("quantite", 0))
                mini = p.get("stock_mini", p.get("quantite_min", 5))
                statut = "OK"
                if qte <= 0:
                    statut = "🔴 Rupture"
                elif qte <= mini:
                    statut = "⚠️ Alerte"

                self.tab_produits.inserer_ligne([
                    p["id"], p["reference"], p["nom"], p.get("categorie_nom", "-"),
                    f"{p.get('prix_achat', 0):,.0f} F", f"{p.get('prix_vente', 0):,.0f} F",
                    qte, statut
                ], ["center", "left", "left", "left", "right", "right", "center", "center"])
        except Exception:
            pass

    def _nouveau_produit(self):
        dlg = DialogueProduitQt(parent=self)
        if dlg.exec() == DialogueProduitQt.DialogCode.Accepted:
            self._charger_produits()

    def _modifier_produit(self):
        row = self.tab_produits.currentRow()
        if row < 0:
            QMessageBox.information(self, "Sélection requise", "Sélectionnez un produit à modifier.")
            return
        p_id_item = self.tab_produits.item(row, 0)
        if not p_id_item:
            return
        p_id = int(p_id_item.text())
        p = db.get_produit_par_id(p_id)
        if p:
            dlg = DialogueProduitQt(produit=p, parent=self)
            if dlg.exec() == DialogueProduitQt.DialogCode.Accepted:
                self._charger_produits()

    def _supprimer_produit(self):
        row = self.tab_produits.currentRow()
        if row < 0:
            QMessageBox.information(self, "Sélection requise", "Sélectionnez un produit à supprimer.")
            return
        p_id_item = self.tab_produits.item(row, 0)
        if not p_id_item:
            return
        p_id = int(p_id_item.text())
        if QMessageBox.question(self, "Confirmation", "Voulez-vous vraiment supprimer ce produit ?") == QMessageBox.StandardButton.Yes:
            try:
                db.supprimer_produit(p_id)
                self._charger_produits()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", str(e))
