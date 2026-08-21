"""
SOPAUTO - Aide
"""
import tkinter as tk
from tkinter import ttk

import database as db
import factures
from ui_widgets import COULEURS, POLICE, Bouton, Carte


class AideMixin:
    """Écran d'aide — raccourcis clavier, guide de démarrage.

    Liste tous les F1-F12, Ctrl+S/N et les étapes initiales.
    """

    def afficher_aide(self):
        self._nouvelle_page("Aide — Comment faire ?", 10)

        conteneur = tk.Frame(self.zone, bg=COULEURS["bg"])
        conteneur.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(conteneur, bg=COULEURS["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(conteneur, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        interieur = tk.Frame(canvas, bg=COULEURS["bg"])
        canvas.create_window((0, 0), window=interieur, anchor="nw")
        interieur.bind("<Configure>",
                       lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units")
                        if canvas.winfo_exists() else None)

        sections = [
            ("Comment faire une VENTE", [
                "1. Cliquez sur « Caisse » dans le menu à gauche (ou touche F2).",
                "2. Tapez le nom de la pièce dans la grande case en haut, puis appuyez sur Entrée.",
                "   Ou bien : double-cliquez sur la pièce dans la liste en dessous.",
                "3. La pièce apparaît dans le Panier à droite.",
                "4. Quand toutes les pièces sont ajoutées, cliquez sur le gros bouton vert « ENCAISSER ».",
                "5. Choisissez comment le client paie (Espèces, Wave, Orange Money…).",
                "6. Tapez le montant donné par le client : la monnaie à rendre s'affiche toute seule.",
                "7. Cliquez sur « Valider » : le reçu s'imprime automatiquement."]),
            ("Comment CHERCHER une pièce", [
                "1. Cliquez sur « Produits » dans le menu (ou touche F3).",
                "2. Tapez le nom, la référence ou la marque dans la case de recherche.",
                "3. La liste se filtre automatiquement pendant que vous tapez.",
                "• 🔴 rouge = plus en stock • 🟠 orange = bientôt fini • normal = disponible"]),
            ("Comment AJOUTER du stock (arrivage)", [
                "1. Cliquez sur « Stock » dans le menu (ou touche F4).",
                "2. Double-cliquez sur la pièce reçue.",
                "3. Tapez la quantité reçue et validez. Le stock se met à jour tout seul."]),
            ("↩ Le client rapporte un article (annulation)", [
                "1. Allez dans « Rapports » puis l'onglet « Historique des ventes ».",
                "2. Cherchez la vente avec le numéro du reçu ou le nom du client.",
                "3. Cliquez sur la vente, puis sur « Annuler la vente ».",
                "4. Les pièces retournent automatiquement dans le stock.",
                "⚠ Seul un administrateur peut annuler une vente."]),
            ("Réimprimer un reçu", [
                "• Dans la Caisse : double-cliquez sur la vente dans « Dernières ventes » en bas à droite.",
                "• Ou dans Rapports > Historique des ventes : sélectionnez puis « Ticket » ou « Facture A4 »."]),
            ("Savoir si on VEND TROP BAS ou trop haut", [
                "Ici, on compare le prix AFFICHÉ au prix RÉELLEMENT encaissé après négociation.",
                "1. Cliquez sur « Analyse » dans le menu (ou touche F10).",
                "2. La grande phrase colorée en haut vous dit tout de suite si vous bradez ou non.",
                "3. Le tableau liste chaque pièce : prix affiché, prix réel moyen, écart en %.",
                "• Bradé = vous vendez en dessous du prix affiché",
                "• Majoré = vous vendez au-dessus (votre prix affiché est trop bas !)",
                "• Au prix = pas de négociation",
                "4. Ligne 🔴 ROUGE = pièce vendue SOUS son prix d'achat : vous perdez de l'argent.",
                "5. Sélectionnez une pièce puis « Prix conseillé » : l'appli calcule le bon prix",
                "   à partir de ce que vos clients acceptent vraiment de payer.",
                "6. Double-cliquez sur une pièce pour voir la courbe de tous ses prix de vente.",
            ]),
            ("Savoir ce qui se vend DE MOINS EN MOINS", [
                "1. Menu « Analyse » puis onglet « Tendances de vente ».",
                "2. L'appli compare les 30 derniers jours aux 30 jours d'avant.",
                "• Forte hausse / En hausse = ça décolle, ne tombez pas en rupture !",
                "• ↘ En baisse / Forte baisse = ça décroche, attention au stock mort",
                "• Ne se vend plus = plus aucune vente sur la période récente",
                "3. La colonne « Capital immobilisé » montre l'argent bloqué dans ces pièces.",
                "4. Filtrez sur « En baisse seulement » pour voir uniquement les problèmes.",
            ]),
            ("Ce que je dois regarder aujourd'hui", [
                "Menu « Analyse » puis onglet « Alertes commerciales ».",
                "Tout est classé du plus grave au moins urgent :",
                "• 🔴 Critique = vous perdez de l'argent maintenant (vente sous le coût)",
                "• 🟠 Haute = remise trop forte, ou pièce qui décroche avec du stock",
                "• Info = opportunité (vous pourriez augmenter un prix)",
                "Sélectionnez une alerte puis « Voir le produit » pour agir dessus.",
            ]),
            ("Savoir QUI négocie le plus", [
                "Menu « Analyse » puis onglet « Qui négocie ».",
                "• À gauche : par vendeur — qui accorde le plus de remises.",
                "• À droite : par client — qui obtient systématiquement les meilleurs prix.",
                "Un écart négatif (en rouge) = tendance à baisser les prix.",
            ]),
            ("Savoir QUI ME DOIT DE L'ARGENT", [
                "1. Cliquez sur « Créances » dans le menu (ou touche F9).",
                "2. À gauche : la liste des clients et combien chacun doit.",
                "3. À droite : les factures non payées, avec l'ancienneté en jours.",
                "4. Les lignes en rouge sont en retard : à relancer en priorité.",
                "5. Pour encaisser : double-cliquez sur la facture, tapez le montant reçu.",
                "   Un client peut payer en plusieurs fois : chaque acompte est enregistré.",
                "⚠ Pour vendre à crédit, le client doit avoir un plafond dans sa fiche.",
            ]),
            ("Trouver une pièce pour un véhicule", [
                "1. Cliquez sur « Véhicules » dans le menu (ou touche F7).",
                "2. Choisissez la marque, le modèle, l'année : ex. Toyota / Yaris / 2008.",
                "3. La liste montre les pièces compatibles avec le stock et le prix.",
                "4. Double-cliquez sur une pièce : elle part directement dans le panier.",
                "• Vous pouvez aussi taper une référence OEM ou un équivalent dans la case du bas.",
                "• Pour lier une nouvelle pièce à un véhicule : bouton « Lier une pièce ».",
            ]),
            ("Commander chez un fournisseur", [
                "1. Menu « Achats » puis « Nouvelle commande ».",
                "2. Choisissez le fournisseur, ajoutez les articles avec quantité et prix d'achat.",
                "3. Quand la commande part : bouton « Marquer envoyée ».",
                "4. Quand la marchandise arrive : bouton « Réceptionner ».",
                "   Vous pouvez ne réceptionner qu'une partie si tout n'est pas arrivé.",
                "5. Le stock ET le coût moyen se mettent à jour automatiquement.",
                "6. Pour payer le fournisseur : bouton « Payer ».",
            ]),
            ("Faire l'inventaire (compter le stock réel)", [
                "1. Menu « Inventaire » puis « Ouvrir un inventaire ».",
                "2. Choisissez le dépôt (boutique ou réserve).",
                "3. Comptez physiquement, puis double-cliquez sur chaque pièce pour saisir",
                "   la quantité réellement trouvée. L'écart s'affiche automatiquement.",
                "4. Indiquez le motif de l'écart : Vol, Casse, Erreur de saisie…",
                "5. Quand tout est compté : bouton « Clôturer ».",
                "   • Oui = le stock est corrigé sur votre comptage",
                "   • Non = les écarts sont notés sans toucher au stock",
            ]),
            ("Gérer plusieurs dépôts", [
                "L'appli distingue la BOUTIQUE (où on vend) de la RÉSERVE (stockage).",
                "1. Menu « Dépôts » pour voir le contenu et la valeur de chaque dépôt.",
                "2. « Transférer du stock » pour déplacer des pièces de la réserve au rayon.",
                "⚠ On ne peut vendre que ce qui est dans un dépôt autorisé à la vente.",
            ]),
            ("↩ Un client rapporte une pièce", [
                "1. Menu « Retours » puis « Enregistrer un retour ».",
                "2. Choisissez la vente d'origine dans la liste.",
                "3. Saisissez la quantité rendue pour chaque article (retour partiel possible).",
                "4. Décochez « Remettre en stock » si la pièce est cassée ou inutilisable.",
                "5. Choisissez le mode de remboursement : Espèces, Avoir ou Échange.",
                "L'appli vous empêche de reprendre plus que ce qui a été vendu.",
            ]),
            ("Anticiper les ruptures", [
                "1. Menu « Prévisions ».",
                "2. L'appli calcule la vitesse de vente de chaque pièce et la date de rupture.",
                "• 🔴 Critique = rupture avant l'arrivée d'une commande",
                "• 🟠 Haute / Moyenne = à surveiller",
                "3. La colonne « À commander » propose la quantité à acheter.",
                "4. Bouton « Créer la commande » : l'appli génère les commandes fournisseur",
                "   automatiquement, regroupées par fournisseur.",
            ]),
            ("Enregistrer une facture en PDF", [
                "Partout où vous voyez le bouton vert « PDF », un vrai fichier PDF est créé.",
                "• Rapports > Historique des ventes : sélectionnez la vente puis « PDF ».",
                "• Rapports > Ventes & marges : bouton « PDF » pour le rapport complet.",
                "• Rapports > Valorisation du stock : « Bon en PDF ».",
                "Les PDF sont rangés dans le dossier « factures » à côté de l'application.",
            ]),
            ("⌨ Touches rapides", [
                "F1 = cette aide    F2 = Caisse    F3 = Produits    F4 = Stock",
                "F5 = Clients    F6 = Rapports    F7 = Véhicules",
                "F8 = Encaisser    F9 = Créances    F10 = Analyse",
                "F12 = Tableau de bord    Ctrl+S = Sauvegarde",
            ]),
            ("En cas de problème", [
                "• L'application sauvegarde les données automatiquement à chaque fermeture.",
                "• Ne supprimez jamais le fichier « gestion_piece_auto.db » : il contient TOUT.",
                "• En cas d'erreur, fermez et rouvrez l'application, les données sont conservées.",
                "• Les 30 dernières sauvegardes sont conservées dans le dossier « sauvegardes ».",
            ]),
        ]
        for titre, lignes in sections:
            c = Carte(interieur, titre)
            c.pack(fill=tk.X, pady=(0, 10), padx=(0, 12))
            for ligne in lignes:
                tk.Label(c.corps, text=ligne, font=(POLICE, 10), bg=COULEURS["card"],
                         fg=COULEURS["text"], anchor="w", justify="left",
                         wraplength=900).pack(anchor="w", pady=1)


