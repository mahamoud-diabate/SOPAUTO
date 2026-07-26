# SODIPAC — Gestion Pièce Auto

Logiciel de gestion de stock, caisse et pilotage commercial pour boutique
de pièces automobiles. 100 % local, aucun abonnement, aucune connexion
internet requise.

**Python 3.11+ · Tkinter · SQLite** — Devise : F CFA — Interface en français.

---

## Démarrage rapide

```bash
git clone <repo>
cd GestionPieceAuto
python main.py
```

Première connexion : **admin / admin123** (à changer dans Paramètres > Utilisateurs).

Aucune dépendance externe — Tkinter et SQLite sont inclus dans Python.

---

## Architecture

```
main.py                   Point d'entrée (connexion → application)
core.py                   Application (menu, navigation, thème, permissions)
│
├── page_dashboard.py     Tableau de bord (KPIs, graphique, alertes)
├── page_caisse.py        Caisse / POS (scan, panier, encaissement)
├── page_produits.py      Catalogue produits
├── page_stock.py         Gestion du stock
├── page_clients.py       Clients
├── page_categories.py    Catégories
├── page_fournisseurs.py  Fournisseurs
├── page_mouvements.py    Historique des mouvements
├── page_parametres.py    Administration (entreprise, users, backup)
├── page_rapports.py      Rapports et historique des ventes
├── page_aide.py          Aide et documentation
│
├── page_creances.py      Créances clients (qui doit quoi)
├── page_achats.py        Commandes fournisseur, réception, dettes
├── page_inventaire.py    Inventaire physique, écarts valorisés
├── page_vehicules.py     Recherche par véhicule, compatibilité
├── page_depots.py        Multi-dépôt, transferts
├── page_retours.py       Retours partiels et avoirs
├── page_previsions.py    Prévisions de rupture, classes ABC
│
├── pages_analyse.py      Analyse commerciale (prix, tendances, alertes)
│
├── database.py           Accès base de données, schéma, CRUD (65 fonctions)
├── metier_v3.py          Logique métier (CUMP, créances, achats, inventaire…)
├── dialogues.py          Boîtes de dialogue (connexion, formulaires, v3)
├── analyse_prix.py       Analyse des prix pratiqués
├── factures.py           Génération HTML des factures et tickets
├── export_pdf.py         Conversion HTML → PDF via navigateur
├── ui_widgets.py         Thème clair/sombre, widgets réutilisables
├── schema_v3.py          Migration additive du schéma v3
├── db_helpers.py         Helpers partagés database ↔ schema_v3
│
└── tests/                Tests automatisés (319 assertions, 0 échec)
```

**Pattern :** Chaque écran est un **mixin** — une classe avec uniquement les
méthodes de son domaine. `Application` hérite de 18 mixins. Pas d'imports
circulaires.

---

## Rôles et permissions

| Rôle         | Accès                                     |
|--------------|-------------------------------------------|
| superviseur  | Tout (admin)                              |
| gérant       | Caisse, produits, stock, rapports         |
| vendeur      | Caisse seulement                          |

---

## Raccourcis clavier

| Touche   | Action              | Touche   | Action            |
|----------|---------------------|----------|-------------------|
| F1       | Aide                | F8       | Encaisser         |
| F2       | Caisse              | F9       | Créances          |
| F3       | Produits            | F10      | Analyse           |
| F4       | Stock               | F12      | Tableau de bord   |
| F5       | Clients             | Ctrl+S   | Sauvegarder       |
| F6       | Rapports            | Ctrl+N   | Nouveau produit   |

---

## Base de données

23 tables, 3 vues, 33 index. SQLite en mode WAL, `foreign_keys = ON`.

**Tables principales :** produits (29 colonnes), ventes, ventes_details, clients,
mouvements_stock, stock_depot, commandes, reglements, inventaires, retours,
utilisateurs, parametres, journal.

Migration : `database.init_database()` est idempotent et non destructif.

---

## Tests

```bash
python test_app.py           # Logique métier v2 (84 assertions)
python test_v3.py            # Métier v3 (141)
python test_analyse_prix.py  # Analyse prix et tendances (86)
python test_critical.py      # Fonctions critiques (8)
python test_mechant.py       # Tests adversariaux
python test_ui.py            # Interface v2 headless
python test_ui_v3.py         # Écrans v3 headless (53)
python test_ui_analyse.py    # Écran analyse headless (54)
```

**Total : 319 assertions, 0 échec.** Chaque test utilise une base jetable.

---

## Qualité du code

- ✅ 18 mixins (1 par écran, 100-500 lignes chacun)
- ✅ Type hints sur les fonctions publiques de database et metier
- ✅ Aucun `except: pass` silencieux (tout est loggé via traceback)
- ✅ `_num()` unifié en `parse_float()` (3 duplications supprimées)
- ✅ `_colonnes()` / `_ajouter_colonne()` partagés via `db_helpers.py`
- ✅ `pages_v3.py` supprimé (contenu distribué dans les 7 mixins v3)
- ✅ 0 import circulaire

---

## Pour les développeurs

Voir [`DEVELOPER.md`](DEVELOPER.md) pour les conventions de code, l'architecture
détaillée, et comment ajouter un nouvel écran.
