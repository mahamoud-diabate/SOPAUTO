"""
SODIPAC - Dialogues Modaux Native PyQt6 (Produits, Clients, Paiements Caisse, Mouvements)
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QMessageBox, QFormLayout, QSpinBox, QDoubleSpinBox
)
import database as db
from ui_qt import PALETTES_QT, THEME_ACTUEL


class DialoguePaiementQt(QDialog):
    """Dialogue d'encaissement Caisse avec calcul automatique de la monnaie."""

    def __init__(self, total, parent=None):
        super().__init__(parent)
        self.total = total
        self.resultat = None
        self.setWindowTitle("💳 Encaissement - Règlement Caisse")
        self.setFixedSize(400, 320)
        c = PALETTES_QT[THEME_ACTUEL[0]]
        self.setStyleSheet(f"background-color: {c['card']}; color: {c['text']};")

        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(12)

        lbl_tot = QLabel(f"Total à Encaisser : {total:,.0f} F CFA")
        lbl_tot.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {c['primary']};")
        lbl_tot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(lbl_tot)

        form = QFormLayout()
        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["Espèces", "Carte Bancaire", "Chèque", "Virement", "Crédit Client"])
        form.addRow("Mode de paiement :", self.cb_mode)

        self.txt_recu = QLineEdit()
        self.txt_recu.setPlaceholderText(f"{total:,.0f}")
        self.txt_recu.textChanged.connect(self._calculer_monnaie)
        form.addRow("Montant reçu :", self.txt_recu)

        self.lbl_monnaie = QLabel("0 F CFA")
        self.lbl_monnaie.setStyleSheet("font-size: 16px; font-weight: bold; color: #10b981;")
        form.addRow("Monnaie à rendre :", self.lbl_monnaie)

        l.addLayout(form)

        btn_box = QHBoxLayout()
        btn_valider = QPushButton("✅ Valider l'encaissement")
        btn_valider.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        btn_valider.clicked.connect(self._valider)
        btn_box.addWidget(btn_valider)

        btn_annuler = QPushButton("❌ Annuler")
        btn_annuler.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        btn_annuler.clicked.connect(self.reject)
        btn_box.addWidget(btn_annuler)

        l.addLayout(btn_box)

    def _calculer_monnaie(self, txt):
        try:
            val = float(txt.replace(" ", ""))
            diff = val - self.total
            if diff >= 0:
                self.lbl_monnaie.setText(f"{diff:,.0f} F CFA")
                self.lbl_monnaie.setStyleSheet("font-size: 16px; font-weight: bold; color: #10b981;")
            else:
                self.lbl_monnaie.setText(f"Manque {abs(diff):,.0f} F")
                self.lbl_monnaie.setStyleSheet("font-size: 16px; font-weight: bold; color: #ef4444;")
        except Exception:
            self.lbl_monnaie.setText("0 F CFA")

    def _valider(self):
        mode = self.cb_mode.currentText().lower()
        if mode == "espèces" or mode == "especes":
            try:
                recu = float(self.txt_recu.text().replace(" ", ""))
                if recu < self.total:
                    QMessageBox.warning(self, "Montant insuffisant", "Le montant reçu est inférieur au total.")
                    return
            except Exception:
                pass

        self.resultat = {
            "mode": mode,
            "montant_recu": self.txt_recu.text()
        }
        self.accept()


class DialogueProduitQt(QDialog):
    """Dialogue de création / édition de Produit."""

    def __init__(self, produit=None, parent=None):
        super().__init__(parent)
        self.produit = produit
        self.setWindowTitle("📦 Nouveaux Produit" if not produit else f"✏️ Modifier {produit['nom']}")
        self.setFixedSize(480, 420)
        c = PALETTES_QT[THEME_ACTUEL[0]]
        self.setStyleSheet(f"background-color: {c['card']}; color: {c['text']};")

        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        self.txt_ref = QLineEdit(produit["reference"] if produit else "")
        form.addRow("Référence :", self.txt_ref)

        self.txt_nom = QLineEdit(produit["nom"] if produit else "")
        form.addRow("Nom du produit :", self.txt_nom)

        self.cb_cat = QComboBox()
        try:
            cats = db.get_categories()
            for ct in cats:
                self.cb_cat.addItem(ct["nom"], ct["id"])
        except Exception:
            pass
        form.addRow("Catégorie :", self.cb_cat)

        self.txt_px_achat = QLineEdit(str(produit["prix_achat"]) if produit else "0")
        form.addRow("Prix d'Achat :", self.txt_px_achat)

        self.txt_px_vente = QLineEdit(str(produit["prix_vente"]) if produit else "0")
        form.addRow("Prix de Vente :", self.txt_px_vente)

        self.sp_qte = QSpinBox()
        self.sp_qte.setRange(0, 999999)
        self.sp_qte.setValue(produit["quantite"] if produit else 1)
        form.addRow("Stock initial :", self.sp_qte)

        self.sp_min = QSpinBox()
        self.sp_min.setRange(0, 99999)
        self.sp_min.setValue(produit["quantite_min"] if produit else 5)
        form.addRow("Seuil alerte :", self.sp_min)

        l.addLayout(form)

        btn_box = QHBoxLayout()
        btn_save = QPushButton("💾 Enregistrer")
        btn_save.setStyleSheet("background-color: #6366f1; color: white; font-weight: bold; padding: 8px;")
        btn_save.clicked.connect(self._enregistrer)
        btn_box.addWidget(btn_save)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        l.addLayout(btn_box)

    def _enregistrer(self):
        ref = self.txt_ref.text().strip()
        nom = self.txt_nom.text().strip()
        if not ref or not nom:
            QMessageBox.warning(self, "Champs requis", "La référence et le nom sont obligatoires.")
            return
        try:
            px_a = float(self.txt_px_achat.text().replace(" ", ""))
            px_v = float(self.txt_px_vente.text().replace(" ", ""))
            cat_id = self.cb_cat.currentData()

            if not self.produit:
                db.ajouter_produit(ref, nom, cat_id, px_a, px_v, self.sp_qte.value(), self.sp_min.value())
            else:
                db.modifier_produit(self.produit["id"], ref, nom, cat_id, px_a, px_v, self.sp_qte.value(), self.sp_min.value())

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))


class DialogueClientQt(QDialog):
    """Dialogue de création / édition de Client."""

    def __init__(self, client=None, parent=None):
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("👥 Nouveau Client" if not client else f"✏️ Modifier {client['nom']}")
        self.setFixedSize(420, 300)
        c = PALETTES_QT[THEME_ACTUEL[0]]
        self.setStyleSheet(f"background-color: {c['card']}; color: {c['text']};")

        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        self.txt_nom = QLineEdit(client["nom"] if client else "")
        form.addRow("Nom Complet :", self.txt_nom)

        self.txt_tel = QLineEdit(client.get("telephone", "") if client else "")
        form.addRow("Téléphone :", self.txt_tel)

        self.txt_plafond = QLineEdit(str(client.get("plafond_credit", 0)) if client else "100000")
        form.addRow("Plafond Crédit (F CFA) :", self.txt_plafond)

        l.addLayout(form)

        btn_box = QHBoxLayout()
        btn_save = QPushButton("💾 Enregistrer")
        btn_save.setStyleSheet("background-color: #6366f1; color: white; font-weight: bold; padding: 8px;")
        btn_save.clicked.connect(self._enregistrer)
        btn_box.addWidget(btn_save)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        l.addLayout(btn_box)

    def _enregistrer(self):
        nom = self.txt_nom.text().strip()
        if not nom:
            QMessageBox.warning(self, "Champ requis", "Le nom du client est obligatoire.")
            return
        try:
            tel = self.txt_tel.text().strip()
            plafond = float(self.txt_plafond.text().replace(" ", ""))
            if not self.client:
                db.ajouter_client(nom, tel, "", plafond)
            else:
                db.modifier_client(self.client["id"], nom, tel, "", plafond)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
