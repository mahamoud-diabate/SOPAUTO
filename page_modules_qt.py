"""
SOPAUTO - Pages Stock, Clients, Créances, Rapports PyQt6 (Avec Dialogues)
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox
import database as db
from ui_qt import CarteQt, TableauTriableQt, BoutonQt
from dialogues_qt import DialogueClientQt


class PageStockQt(QWidget):
    """Vue Stock PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("📋 Mouvements & Suivi des Stocks")
        self.tab = TableauTriableQt([
            ("id", "ID", 50, "center"),
            ("ref", "Référence", 120, "w"),
            ("nom", "Produit", 280, "w"),
            ("qte", "Stock Rayon", 100, "center"),
            ("mini", "Seuil Mini", 100, "center"),
            ("valeur", "Valeur Totale", 140, "e")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            for p in db.get_produits():
                stock = p.get("stock", p.get("quantite", 0))
                mini = p.get("stock_mini", p.get("quantite_min", 5))
                valeur = stock * p.get("prix_achat", 0)
                self.tab.inserer_ligne([
                    p["id"], p["reference"], p["nom"], stock, mini, f"{valeur:,.0f} F CFA"
                ], ["center", "left", "left", "center", "center", "right"])
        except Exception:
            pass


class PageClientsQt(QWidget):
    """Vue Clients PyQt6 (Avec Création / Édition)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)

        barre = QHBoxLayout()
        btn_add = BoutonQt("➕ Nouveau Client", "primary", self._nouveau_client)
        barre.addWidget(btn_add)
        btn_edit = BoutonQt("✏️ Modifier Client", "secondary", self._modifier_client)
        barre.addWidget(btn_edit)
        barre.addStretch()
        lyt.addLayout(barre)

        c = CarteQt("👥 Répertoire des Clients")
        self.tab = TableauTriableQt([
            ("id", "ID", 50, "center"),
            ("nom", "Nom Complet", 220, "w"),
            ("tel", "Téléphone", 140, "w"),
            ("ville", "Adresse", 160, "w"),
            ("encours", "Encours / Créance", 130, "e"),
            ("plafond", "Plafond Crédit", 130, "e")
        ], parent=c)
        self.tab.doubleClicked.connect(self._modifier_client)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            for cl in db.get_clients():
                self.tab.inserer_ligne([
                    cl["id"], cl["nom"], cl.get("telephone") or "-",
                    cl.get("adresse") or "-",
                    f"{cl.get('solde_creance', 0):,.0f} F CFA",
                    f"{cl.get('plafond_credit', 0):,.0f} F CFA"
                ], ["center", "left", "left", "left", "right", "right"])
        except Exception:
            pass

    def _nouveau_client(self):
        dlg = DialogueClientQt(parent=self)
        if dlg.exec() == DialogueClientQt.DialogCode.Accepted:
            self.charger()

    def _modifier_client(self):
        row = self.tab.currentRow()
        if row < 0:
            QMessageBox.information(self, "Sélection requise", "Sélectionnez un client à modifier.")
            return
        cl_id_item = self.tab.item(row, 0)
        if not cl_id_item:
            return
        cl_id = int(cl_id_item.text())
        cl = db.get_client_par_id(cl_id) if hasattr(db, 'get_client_par_id') else None
        if not cl:
            for c_obj in db.get_clients():
                if c_obj["id"] == cl_id:
                    cl = c_obj
                    break
        if cl:
            dlg = DialogueClientQt(client=cl, parent=self)
            if dlg.exec() == DialogueClientQt.DialogCode.Accepted:
                self.charger()


class PageCreancesQt(QWidget):
    """Vue Créances PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("💳 Suivi des Créances & Encours Clients")
        self.tab = TableauTriableQt([
            ("client", "Client", 240, "w"),
            ("tel", "Téléphone", 140, "w"),
            ("creance", "Solde Dû", 140, "e"),
            ("plafond", "Plafond", 140, "e")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            for cl in db.get_clients():
                solde = cl.get("solde_creances", cl.get("solde_creance", 0))
                if solde > 0:
                    self.tab.inserer_ligne([
                        cl["nom"], cl.get("telephone") or "-", f"{solde:,.0f} F CFA", f"{cl.get('plafond_credit', 0):,.0f} F CFA"
                    ], ["left", "left", "right", "right"])
        except Exception:
            pass


class PageRapportsQt(QWidget):
    """Vue Rapports PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("💹 Historique Ventes & Rapports")
        self.tab = TableauTriableQt([
            ("fact", "N° Facture", 140, "w"),
            ("date", "Date & Heure", 160, "center"),
            ("client", "Client", 200, "w"),
            ("total", "Total Net", 130, "e"),
            ("mode", "Paiement", 120, "center")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            ventes = db.get_ventes(limit=50)
            for v in ventes:
                self.tab.inserer_ligne([
                    v.get("numero") or f"VTE-{v['id']}",
                    v.get("date_vente", "-"),
                    v.get("client_nom") or "Client Comptant",
                    f"{v.get('total', 0):,.0f} F CFA",
                    v.get("mode_paiement") or "Espèces"
                ], ["left", "center", "left", "right", "center"])
        except Exception:
            pass
