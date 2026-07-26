"""
SODIPAC — Dialogues (pont vers le package dialogues/)

Ce fichier existe pour rétrocompatibilité. Tout le code est dans dialogues/.
"""
from dialogues import (
    DialogueBase, DialogueConnexion,
    DialogueProduit, DialogueCategorie, DialogueFournisseur,
    DialogueClient, DialogueUtilisateur,
    DialogueMouvement, DialoguePaiement,
    DemanderMontant, _Base,
    DialogueDepot, DialogueTransfert, DialogueCommande,
    DialogueReception, DialogueOuvrirInventaire, DialogueComptage,
    DialogueRetour, DialogueCompatibilite, DialogueModele,
    DialogueHistoriquePrix, DialoguePrixConseille,
)
