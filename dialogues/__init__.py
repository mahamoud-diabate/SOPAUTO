"""
SODIPAC — Dialogues (20 classes en 5 sous-modules)

Pour naviguer :  from dialogues.core import DialogueBase
                 from dialogues.v3 import DialogueCommande
"""
# Imports communs à tous les dialogues
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Any

import database as db
from ui_widgets import (COULEURS, POLICE, Bouton, AutocompleteCombobox,
                        centrer_fenetre, fmt_money)

# Sous-modules
from .core import DialogueBase, DialogueConnexion
from .formulaires import (DialogueProduit, DialogueCategorie, DialogueFournisseur,
                          DialogueClient, DialogueUtilisateur)
from .operations import DialogueMouvement, DialoguePaiement, DialoguePaiementSimple, DemanderMontant
from .v3 import (_Base, DialogueDepot, DialogueTransfert, DialogueCommande,
                 DialogueReception, DialogueOuvrirInventaire, DialogueComptage,
                 DialogueRetour, DialogueCompatibilite, DialogueModele)
from .v3_analyse import DialogueHistoriquePrix, DialoguePrixConseille
