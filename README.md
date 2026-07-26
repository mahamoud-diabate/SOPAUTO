# SODIPAC — Gestion Pièce Auto

Logiciel de gestion de stock, caisse et pilotage commercial pour boutique
de pièces automobiles. 100 % local, aucun abonnement, aucune connexion
internet requise.

**Python 3.11+ · Tkinter · SQLite** — Devise : F CFA — Interface en français.

---

## Démarrer

```
python main.py
```

Première connexion : **admin / admin123** (à changer dans Paramètres > Utilisateurs).

---

## Architecture

```
main.py                 31   Point d'entrée
core.py                473   Application (menu, navigation, thème, permissions)
│
├── page_dashboard.py  384   Tableau de bord (KPIs, graphique, alertes)
├── page_caisse.py     347   Caisse (scan, panier, encaissement)
├── page_produits.py   244   Catalogue produits
├── page_stock.py      164   Gestion du stock
├── page_clients.py    106   Clients
├── page_categories.py  97   Catégories
├── page_fournisseurs.py 107 Fournisseurs
├── page_mouvements.py 112   Historique mouvements
├── page_parametres.py 218   Paramètres, utilisateurs, sauvegardes
├── page_rapports.py   395   Rapports, historique ventes
└── page_aide.py       194   Aide
│
├── pages_v3.py      2 164   Achats, dépôts, inventaire, retours, créances…
├── pages_analyse.py   925   Analyse commerciale (prix, tendances)
├── dialogues.py       907   Boîtes de dialogue (produit, paiement, client…)
├── database.py      1 778   Accès base de données, schéma, CRUD
├── metier_v3.py     1 484   Logique métier (CUMP, créances, achats…)
├── schema_v3.py       570   Migration additive du schéma v3
├── analyse_prix.py    840   Analyse des prix pratiqués
├── factures.py        366   Génération HTML des factures et tickets
├── export_pdf.py      231   Conversion HTML → PDF via navigateur
├── ui_widgets.py      458   Thème clair/sombre, widgets réutilisables
│
└── tests/            2 303   Tests automatisés (419 assertions, 0 échec)
```

---

## Rôles et permissions

| Rôle         | Accès                                     | Menu grisé si refus |
|--------------|-------------------------------------------|---------------------|
| superviseur  | Tout (admin)                              | —                   |
| gérant       | Caisse, produits, stock, rapports         | Oui                 |
| vendeur      | Caisse seulement                          | Oui                 |

---

## Raccourcis clavier

| Touche   | Action                    | Touche   | Action            |
|----------|---------------------------|----------|-------------------|
| F1       | Aide                      | F8       | Encaisser         |
| F2       | Caisse                    | F9       | Créances          |
| F3       | Produits                  | F10      | Analyse           |
| F4       | Stock                     | F12      | Tableau de bord   |
| F5       | Clients                   | Ctrl+S   | Sauvegarder       |
| F6       | Rapports                  | Ctrl+N   | Nouveau produit   |

---

## Base de données

23 tables, 3 vues, 33 index. SQLite en mode WAL, foreign_keys = ON.

**Tables principales :** produits (29 colonnes), ventes, ventes_details, clients,
mouvements_stock, stock_depot, commandes, reglements, inventaires, retours,
utilisateurs, parametres, journal.

Migration : `database.init_database()` est idempotent et non destructif.
Les colonnes sont ajoutées via `ALTER TABLE ADD COLUMN`, les données jamais
supprimées.

---

## Tests

```bash
python test_app.py           # Logique métier v2 (84 assertions)
python test_v3.py            # Métier v3 (141)
python test_analyse_prix.py  # Analyse prix et tendances (86)
python test_mechant.py       # Tests adversariaux
python test_ui.py            # Interface v2 headless
python test_ui_v3.py         # Écrans v3 headless (53)
python test_ui_analyse.py    # Écran analyse headless (54)
```

**Total : 419 assertions, 0 échec.** Chaque test utilise une base jetable.

---

## Sauvegarde et restauration

- Automatique à chaque fermeture (30 dernières conservées)
- Manuelle : **Ctrl+S** ou Paramètres > Sauvegardes
- Restauration : Paramètres > Sauvegardes, sélectionnez puis « Restaurer »

⚠ **Ne supprimez jamais `gestion_piece_auto.db`.** Pour une copie externe,
copiez le dossier `sauvegardes/`.

---

## Ajouter un écran

1. Créer `page_nouveau.py` avec `class NouveauMixin`
2. Dans `core.py`, ajouter `from page_nouveau import NouveauMixin`
3. Ajouter `NouveauMixin` à la liste d'héritage de `Application`
4. Ajouter l'entrée dans `entrees_menu` ou `entrees_menu_second`
5. Ajouter un test dans `test_ui_v3.py` ou `test_ui_analyse.py`
