"""
SODIPAC - Page Caisse PyQt6 (Avec Dialogue Paiement & Monnaie)
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QMessageBox, QFrame, QSplitter
)
import database as db
from ui_qt import CarteQt, TableauTriableQt, BoutonQt, PALETTES_QT, THEME_ACTUEL
from dialogues_qt import DialoguePaiementQt


class PageCaisseQt(QWidget):
    """Vue Point de Vente / Caisse PyQt6."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.panier = []
        self.client_courant = None
        self.layout_main = QHBoxLayout(self)
        self.layout_main.setContentsMargins(16, 16, 16, 16)
        self.layout_main.setSpacing(16)
        self._construire_ui()

    def _construire_ui(self):
        # ── Colonne Gauche : Recherche & Panier ──
        col_gauche = QWidget()
        l_gauche = QVBoxLayout(col_gauche)
        l_gauche.setContentsMargins(0, 0, 0, 0)
        l_gauche.setSpacing(12)

        # Recherche Produit
        c_rech = CarteQt("🔎 Recherche de produit")
        l_rech = QHBoxLayout()
        self.txt_rech = QLineEdit()
        self.txt_rech.setPlaceholderText("Code-barres, référence ou nom du produit…")
        self.txt_rech.textChanged.connect(self._filtrer_produits)
        l_rech.addWidget(self.txt_rech)

        self.cb_produits = QComboBox()
        self.cb_produits.currentIndexChanged.connect(self._selectionner_produit)
        l_rech.addWidget(self.cb_produits)

        btn_ajouter = BoutonQt("➕ Ajouter", "primary", self._ajouter_au_panier)
        l_rech.addWidget(btn_ajouter)

        c_rech.layout_corps.addLayout(l_rech)
        l_gauche.addWidget(c_rech)

        # Table Panier
        c_panier = CarteQt("🛒 Panier de vente")
        self.tab_panier = TableauTriableQt([
            ("ref", "Réf.", 90, "w"),
            ("nom", "Article", 180, "w"),
            ("pu", "P.U.", 90, "e"),
            ("qte", "Qté", 60, "center"),
            ("total", "Total", 100, "e")
        ], parent=c_panier)

        c_panier.layout_corps.addWidget(self.tab_panier)
        l_gauche.addWidget(c_panier)

        self.layout_main.addWidget(col_gauche, stretch=2)

        # ── Colonne Droite : Total & Encaisser ──
        col_droite = QWidget()
        l_droite = QVBoxLayout(col_droite)
        l_droite.setContentsMargins(0, 0, 0, 0)
        l_droite.setSpacing(12)

        # Client
        c_client = CarteQt("👤 Client")
        self.cb_clients = QComboBox()
        self.cb_clients.addItem("Client Comptant (Anonyme)", None)
        try:
            for cl in db.get_clients():
                self.cb_clients.addItem(f"{cl['nom']} ({cl['telephone'] or 'Pas de tél'})", cl["id"])
        except Exception:
            pass
        c_client.layout_corps.addWidget(self.cb_clients)
        l_droite.addWidget(c_client)

        # Total Card
        c_total = CarteQt("💰 Total à payer")
        c_total.setStyleSheet(f"""
            QFrame {{
                background-color: {PALETTES_QT[THEME_ACTUEL[0]]['primary']};
                color: #ffffff;
                border-radius: 10px;
                padding: 16px;
            }}
        """)
        l_tot = QVBoxLayout()
        self.lbl_total = QLabel("0 F CFA")
        self.lbl_total.setStyleSheet("font-size: 28px; font-weight: bold; color: #ffffff;")
        self.lbl_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l_tot.addWidget(self.lbl_total)

        btn_encaisser = BoutonQt("💳 ENCAISSER (F8)", "success", self._valider_vente)
        btn_encaisser.setStyleSheet("background-color: #10b981; color: white; font-size: 16px; padding: 12px;")
        l_tot.addWidget(btn_encaisser)

        btn_vider = BoutonQt("🗑️ Vider le panier", "danger", self._vider_panier)
        l_tot.addWidget(btn_vider)

        c_total.layout_corps.addLayout(l_tot)
        l_droite.addWidget(c_total)

        self.layout_main.addWidget(col_droite, stretch=1)
        self._charger_catalogue()

    def _charger_catalogue(self):
        try:
            self.prods_cache = db.get_produits()
            self.cb_produits.clear()
            for p in self.prods_cache[:50]:
                self.cb_produits.addItem(f"{p['reference']} - {p['nom']} ({p['prix_vente']:,.0f} F | Stock: {p['quantite']})", p["id"])
        except Exception:
            self.prods_cache = []

    def _filtrer_produits(self, txt):
        if not txt:
            self._charger_catalogue()
            return
        txt_l = txt.lower()
        self.cb_produits.clear()
        for p in getattr(self, 'prods_cache', []):
            if txt_l in p['nom'].lower() or txt_l in p['reference'].lower():
                self.cb_produits.addItem(f"{p['reference']} - {p['nom']} ({p['prix_vente']:,.0f} F)", p["id"])

    def _selectionner_produit(self, idx):
        pass

    def _ajouter_au_panier(self):
        p_id = self.cb_produits.currentData()
        if not p_id:
            return
        p = db.get_produit_par_id(p_id)
        if not p:
            return
        if p["quantite"] <= 0:
            QMessageBox.warning(self, "Stock épuisé", f"Le produit {p['nom']} est en rupture de stock !")
            return

        for ligne in self.panier:
            if ligne["id"] == p["id"]:
                if ligne["qte"] + 1 > p["quantite"]:
                    QMessageBox.warning(self, "Stock insuffisant", "Stock maximum atteint dans le panier.")
                    return
                ligne["qte"] += 1
                ligne["total"] = ligne["qte"] * ligne["pu"]
                self._rafraichir_panier()
                return

        self.panier.append({
            "id": p["id"],
            "reference": p["reference"],
            "nom": p["nom"],
            "pu": p["prix_vente"],
            "qte": 1,
            "total": p["prix_vente"]
        })
        self._rafraichir_panier()

    def _rafraichir_panier(self):
        self.tab_panier.vider()
        total_gen = 0
        for item in self.panier:
            total_gen += item["total"]
            self.tab_panier.inserer_ligne([
                item["reference"], item["nom"], f"{item['pu']:,.0f}", item["qte"], f"{item['total']:,.0f}"
            ], ["left", "left", "right", "center", "right"])

        self.lbl_total.setText(f"{total_gen:,.0f} F CFA")

    def _vider_panier(self):
        self.panier.clear()
        self._rafraichir_panier()

    def _valider_vente(self):
        if not self.panier:
            QMessageBox.warning(self, "Panier vide", "Ajoutez au moins un produit au panier.")
            return

        total_gen = sum(item["total"] for item in self.panier)
        dlg = DialoguePaiementQt(total_gen, parent=self)
        if dlg.exec() == DialoguePaiementQt.DialogCode.Accepted and dlg.resultat:
            client_id = self.cb_clients.currentData()
            lignes_vente = [{"produit_id": item["id"], "quantite": item["qte"], "prix_unitaire": item["pu"]} for item in self.panier]

            try:
                res = db.enregistrer_vente(lignes_vente, mode_paiement=dlg.resultat["mode"], client_id=client_id)
                QMessageBox.information(self, "Vente enregistrée", f"Facture N° {res['numero_facture']} enregistrée avec succès !")
                self._vider_panier()
                self._charger_catalogue()
            except Exception as e:
                QMessageBox.critical(self, "Erreur vente", str(e))
