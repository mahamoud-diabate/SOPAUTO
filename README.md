# SODIPAC — Gestion Pièce Auto

Application de gestion commerciale pour pièces automobiles — **caisse, stock, créances, achats, inventaire, analyses**.

![Version](https://img.shields.io/badge/version-3.0-blue)
![Python](https://img.shields.io/badge/python-3.12-green)
![Tests](https://img.shields.io/badge/tests-319%20passing-brightgreen)
![Licence](https://img.shields.io/badge/licence-Propri%C3%A9taire-red)

---

## Fonctionnalités

| Module | Description |
|---|---|
| 🛒 **Caisse** | Vente rapide, recherche live, suggestion client, prix catalogue et négocié, marge temps réel |
| 📦 **Stock** | Multi-dépôts, CUMP, alertes rupture, mouvements entrée/sortie |
| 💰 **Créances** | Suivi crédit clients, plafond, règlements, historique |
| 📋 **Achats** | Commandes fournisseur, réception, décaissements |
| 🔍 **Inventaire** | Comptage physique, écarts, régularisation |
| 📊 **Dashboard** | KPIs, courbe CA 7 jours, objectif mensuel, alertes, top ventes |
| 📈 **Analyse** | Rentabilité, tendances prix, prévisions rupture, saisonnalité |
| 🚗 **Véhicules** | Recherche par marque/modèle/moteur, fiches techniques |
| 🔄 **Retours** | Avoirs, remboursement, remise en stock |
| 📄 **Rapports** | PDF/CSV : ventes, stock, créances, marges, journal |
| 🧾 **Factures** | Génération PDF avec en-tête boutique personnalisable |
| ⚙️ **Paramètres** | Boutique, utilisateurs, rôles (vendeur/gérant/superviseur), sauvegardes |

---

## Architecture

- **Langage** : Python 3.12
- **Interface** : Tkinter (thème moderne Azure, responsive)
- **Base de données** : SQLite (WAL, 23 tables, 3 vues, 33 index)
- **Architecture** : 18 mixins modulaires, connexion persistante
- **Déploiement** : Exécutable unique `.exe` via PyInstaller (aucune dépendance)
- **Tests** : 319 assertions, 8 suites de test, bases jetables

```
main.py → core.py (Application)
  ├── 18 mixins (page_*.py)
  ├── dialogues/ (20 classes de dialogues)
  ├── metier/ (logique métier : CUMP, créances…)
  ├── database.py (CRUD, exports, sauvegardes)
  ├── analyse_prix.py (analyse commerciale)
  ├── factures.py (HTML → PDF)
  ├── export_pdf.py (Edge headless)
  └── ui_widgets.py (thème, widgets réutilisables)
```

---

## Prérequis

- **Python 3.11 ou supérieur** — [Télécharger](https://www.python.org/downloads/)
  - ⚠️ Cocher **"Add Python to PATH"** lors de l'installation
- Aucune dépendance externe (Tkinter et SQLite inclus dans Python)

---

## Lancement

Double-cliquer sur **`Lancer_SODIPAC.bat`** (affiche une fenêtre console) ou sur **`Lancer_SODIPAC.vbs`** (lancement silencieux, sans console).

### Déploiement (version compilée)

La version `.exe` est dans le dossier `dist/` :
```
dist/
├── SODIPAC.exe
├── gestion_piece_auto.db
└── Lancer.bat
```
Copier ces 3 fichiers sur n'importe quel PC Windows — aucun Python requis.

---

## Connexion par défaut

| Utilisateur | Mot de passe | Rôle |
|---|---|---|
| `admin` | `admin` | Administrateur (accès complet) |

> ⚠️ **Changer le mot de passe admin dès la première connexion** via Paramètres → Utilisateurs.

---

## Rôles et permissions

| Rôle | Accès |
|---|---|
| **Vendeur** | Caisse uniquement |
| **Gérant** | Caisse + Produits + Stock + Rapports |
| **Superviseur** | Accès complet + Paramètres + Suppression |

---

## Raccourcis clavier

| Touche | Action |
|---|---|
| `F2` | Caisse |
| `F3` | Produits |
| `F4` | Stock |
| `F5` | Clients |
| `F8` | Encaissement rapide (1 champ prix) |
| `F9` | Créances |
| `F10` | Analyse |
| `F12` | Tableau de bord |
| `Ctrl+S` | Sauvegarde manuelle |

---

## Structure des données

| Fichier/Dossier | Contenu |
|---|---|
| `gestion_piece_auto.db` | Base de données principale |
| `sauvegardes/` | Sauvegardes automatiques (rotation 30 max) |
| `exports/` | Exports CSV générés |
| `factures/` | Factures PDF générées |
| `rapports/` | Rapports PDF générés |

---

## Tests

```bash
python test_v3.py          # Métier v3 : CUMP, dépôts, créances (141 assertions)
python test_app.py         # Métier v2, factures (84 assertions)
python test_analyse_prix.py # Analyse prix, tendances (86 assertions)
python test_ui_v3.py       # Interface : 7 écrans (53 assertions)
python test_ui_analyse.py  # Écran analyse, dialogues, PDF (54 assertions)
python test_critical.py    # Chemins critiques
```

**Total : 319 assertions, 0 échec.**

---

## En cas de problème

1. Fermer et relancer l'application
2. Si l'erreur persiste, copier le message d'erreur et contacter le support
3. Restaurer depuis `sauvegardes/` si nécessaire

---

## Licence

Logiciel propriétaire — © 2026 Mahamoud Diabate. Tous droits réservés.

---

*SODIPAC v3 — Juillet 2026*
