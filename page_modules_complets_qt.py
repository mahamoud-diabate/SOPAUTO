"""
SODIPAC - Modules Complémentaires PyQt6 (Achats, Inventaire, Retours, Prévisions, Dépôts, Catégories, Fournisseurs, Véhicules, Mouvements, Paramètres, Aide)
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QComboBox, QSplitter
)
import database as db
from ui_qt import CarteQt, TableauTriableQt, BoutonQt, PALETTES_QT, THEME_ACTUEL


class PageAchatsQt(QWidget):
    """Vue Achats & Commandes Fournisseurs PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("🛒 Achats & Approvisionnements")
        self.tab = TableauTriableQt([
            ("num", "N° Commande", 120, "w"),
            ("date", "Date", 130, "w"),
            ("fourn", "Fournisseur", 180, "w"),
            ("montant", "Total Net", 120, "e"),
            ("statut", "Statut", 100, "center")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            achats = db.get_achats() if hasattr(db, 'get_achats') else []
            for a in achats:
                self.tab.inserer_ligne([
                    a.get("numero", "-"), a.get("date", "-"), a.get("fournisseur_nom", "-"),
                    f"{a.get('total', 0):,.0f} F CFA", a.get("statut", "Reçu")
                ], ["left", "left", "left", "right", "center"])
        except Exception:
            pass


class PageInventaireQt(QWidget):
    """Vue Inventaire & Comptage PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("📋 Session d'Inventaire de Stock")
        self.tab = TableauTriableQt([
            ("num", "N° Inventaire", 120, "w"),
            ("depot", "Dépôt", 120, "w"),
            ("date", "Ouvert le", 140, "w"),
            ("ecarts", "Écarts", 80, "center"),
            ("statut", "Statut", 100, "center")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            invs = db.get_inventaires() if hasattr(db, 'get_inventaires') else []
            for i in invs:
                self.tab.inserer_ligne([
                    i.get("numero", "-"), i.get("depot_nom", "Principal"), i.get("date_ouverture", "-"),
                    i.get("nb_ecarts", 0), i.get("statut", "En cours")
                ], ["left", "left", "left", "center", "center"])
        except Exception:
            pass


class PageRetoursQt(QWidget):
    """Vue Retours Clients PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("↩️ Retours Clients & Avoirs")
        self.tab = TableauTriableQt([
            ("num", "N° Retour", 120, "w"),
            ("date", "Date", 130, "w"),
            ("facture", "Facture Origine", 130, "w"),
            ("client", "Client", 180, "w"),
            ("total", "Montant Remboursé", 120, "e")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            retours = db.get_retours() if hasattr(db, 'get_retours') else []
            for r in retours:
                self.tab.inserer_ligne([
                    r.get("numero", "-"), r.get("date", "-"), r.get("numero_facture", "-"),
                    r.get("client_nom", "-"), f"{r.get('total', 0):,.0f} F CFA"
                ], ["left", "left", "left", "left", "right"])
        except Exception:
            pass


class PagePrevisionsQt(QWidget):
    """Vue Prévisions & Réapprovisionnements PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("📉 Prévisions des Ventes & Suggestions de Réapprovisionnement")
        self.tab = TableauTriableQt([
            ("ref", "Référence", 110, "w"),
            ("nom", "Produit", 220, "w"),
            ("qte", "Stock Actuel", 90, "center"),
            ("vente_mois", "Ventes (30j)", 90, "center"),
            ("sugg", "Commande Suggérée", 130, "center")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            prods = db.get_produits()
            for p in prods:
                if p["quantite"] <= p["quantite_min"]:
                    sugg = max(10, p["quantite_min"] * 2 - p["quantite"])
                    self.tab.inserer_ligne([
                        p["reference"], p["nom"], p["quantite"], p.get("nb_ventes_30j", 0), f"{sugg} unités"
                    ], ["left", "left", "center", "center", "center"])
        except Exception:
            pass


class PageDepotsQt(QWidget):
    """Vue Dépôts & Transferts PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("🏬 Dépôts & Magasins de Stock")
        self.tab = TableauTriableQt([
            ("code", "Code", 80, "center"),
            ("nom", "Nom du Dépôt", 200, "w"),
            ("type", "Type", 120, "w"),
            ("nb", "Articles Stockés", 120, "center"),
            ("valeur", "Valeur Stock", 130, "e")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            depots = db.get_depots() if hasattr(db, 'get_depots') else [{"code": "D01", "nom": "Dépôt Principal", "type": "Vente", "nb": len(db.get_produits()), "valeur": 0}]
            for d in depots:
                self.tab.inserer_ligne([
                    d.get("code", "D01"), d.get("nom", "Principal"), d.get("type", "Magasin"),
                    d.get("nb", 0), f"{d.get('valeur', 0):,.0f} F CFA"
                ], ["center", "left", "left", "center", "right"])
        except Exception:
            pass


class PageCategoriesQt(QWidget):
    """Vue Catégories PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("📁 Catégories d'Articles")
        self.tab = TableauTriableQt([
            ("id", "ID", 60, "center"),
            ("nom", "Nom de la Catégorie", 250, "w"),
            ("nb", "Nombre d'Articles", 130, "center")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            cats = db.get_categories()
            for ct in cats:
                self.tab.inserer_ligne([ct["id"], ct["nom"], ct.get("nb_produits", 0)], ["center", "left", "center"])
        except Exception:
            pass


class PageFournisseursQt(QWidget):
    """Vue Fournisseurs PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("🏭 Répertoire des Fournisseurs")
        self.tab = TableauTriableQt([
            ("id", "ID", 60, "center"),
            ("nom", "Raison Sociale / Nom", 220, "w"),
            ("tel", "Téléphone", 130, "w"),
            ("email", "Email", 180, "w")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            fourns = db.get_fournisseurs()
            for f in fourns:
                self.tab.inserer_ligne([f["id"], f["nom"], f.get("telephone", "-"), f.get("email", "-")], ["center", "left", "left", "left"])
        except Exception:
            pass


class PageVehiculesQt(QWidget):
    """Vue Véhicules PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("🚗 Véhicules & Compatibilités Pièces")
        self.tab = TableauTriableQt([
            ("immat", "Immatriculation / Vin", 140, "w"),
            ("marque", "Marque", 130, "w"),
            ("modele", "Modèle", 140, "w"),
            ("client", "Propriétaire", 180, "w")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            vehs = db.get_vehicules() if hasattr(db, 'get_vehicules') else []
            for v in vehs:
                self.tab.inserer_ligne([
                    v.get("immatriculation", "-"), v.get("marque", "-"), v.get("modele", "-"), v.get("client_nom", "-")
                ], ["left", "left", "left", "left"])
        except Exception:
            pass


class PageMouvementsQt(QWidget):
    """Vue Mouvements de Stock PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("📈 Journal des Mouvements de Stock")
        self.tab = TableauTriableQt([
            ("id", "ID", 60, "center"),
            ("date", "Date & Heure", 150, "w"),
            ("prod", "Article", 200, "w"),
            ("type", "Type Mouvement", 120, "center"),
            ("qte", "Quantité", 80, "center"),
            ("user", "Utilisateur", 110, "w")
        ], parent=c)
        c.layout_corps.addWidget(self.tab)
        lyt.addWidget(c)
        self.charger()

    def charger(self):
        self.tab.vider()
        try:
            mvs = db.get_mouvements(limite=50) if hasattr(db, 'get_mouvements') else []
            for m in mvs:
                self.tab.inserer_ligne([
                    m.get("id", "-"), m.get("date_mouvement", "-"), m.get("produit_nom", "-"),
                    m.get("type_mouvement", "-"), m.get("quantite", 0), m.get("utilisateur", "Admin")
                ], ["center", "left", "left", "center", "center", "left"])
        except Exception:
            pass


class PageParametresQt(QWidget):
    """Vue Paramètres PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("⚙️ Paramètres & Configuration Système")
        lbl = QLabel("Configuration générale de SODIPAC (Entreprise, Devise, Sauvegardes).")
        lbl.setStyleSheet("font-size: 13px; color: #64748b;")
        c.layout_corps.addWidget(lbl)
        lyt.addWidget(c)


class PageAideQt(QWidget):
    """Vue Aide & Raccourcis PyQt6."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        c = CarteQt("❓ Guide & Raccourcis Clavier")
        lbl = QLabel("F2: Caisse | F3: Produits | F4: Stock | F5: Clients | F9: Créances | F10: Analyse | F12: Dashboard")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #6366f1;")
        c.layout_corps.addWidget(lbl)
        lyt.addWidget(c)
