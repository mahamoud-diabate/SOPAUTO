# DEVELOPER.md — Guide du développeur

Documentation technique pour la maintenance et l'extension de SODIPAC.
Pour l'usage courant, voir [`README.md`](README.md).

---

## Architecture

```
main.py                  Point d'entrée
core.py                  Application, hérite de 18 mixins
├── page_dashboard       Tableau de bord
├── page_caisse          Caisse / POS
├── page_produits        Catalogue
├── page_stock           Gestion stock
├── page_clients         Clients
├── page_categories      Catégories
├── page_fournisseurs    Fournisseurs
├── page_mouvements      Historique
├── page_parametres      Admin
├── page_rapports        Rapports
├── page_aide            Aide
├── page_creances        Créances clients
├── page_achats          Commandes fournisseur
├── page_inventaire      Inventaire physique
├── page_vehicules       Recherche véhicule
├── page_depots          Multi-dépôt
├── page_retours         Retours / avoirs
├── page_previsions      Prévisions rupture
├── pages_analyse.py     Analyse commerciale (4 onglets)
│
├── dialogues.py          Pont → package dialogues/
├── dialogues/            Package dialogues (20 classes)
│   ├── core.py           DialogueBase, DialogueConnexion
│   ├── formulaires.py    Produit, Client, Catégorie, Fournisseur, Utilisateur
│   ├── operations.py     Mouvement, Paiement, DemanderMontant
│   ├── v3.py             Dépôt, Transfert, Commande, Réception, Inventaire…
│   └── v3_analyse.py     HistoriquePrix, PrixConseille
│
├── database.py           Accès DB, schéma, CRUD, exports, sauvegardes
├── metier_v3.py          Logique métier (CUMP, créances, achats…)
├── analyse_prix.py      Analyse des prix pratiqués
├── factures.py          Génération HTML factures/tickets
├── export_pdf.py        HTML → PDF via navigateur headless
├── ui_widgets.py        Thème, TableauTriable, Bouton, Carte, helpers
├── schema_v3.py         Migration additive du schéma v3
└── db_helpers.py        Helpers partagés (colonnes, ajouter_colonne)
```

**Pattern :** Chaque écran est un **mixin** — une classe avec uniquement les
méthodes de son domaine. `Application` hérite de tous les mixins.

---

## Convention des mixins

```python
# page_nouveau.py
class NouveauMixin:
    """Mixin : description de l'écran."""

    def afficher_nouveau(self) -> None:
        """Affiche l'écran."""
        self._nouvelle_page("🆕 Titre", self._idx_menu("Nouveau"))
        # construire l'interface...
```

Dans `core.py` :
```python
from page_nouveau import NouveauMixin

class Application(..., NouveauMixin):
    ...
```

---

## Base de données

23 tables, 3 vues, 33 index. SQLite WAL, `foreign_keys = ON`.

### Migration

`init_database()` est **idempotent** et **non destructif** :
1. `CREATE TABLE IF NOT EXISTS` pour le socle v2
2. `ajouter_colonne()` pour les colonnes ajoutées après coup
3. `schema_v3.migrer(cursor)` pour tout le v3 (try/except protégé)

### Tables clés v3

| Table | Rôle |
|---|---|
| `depots` / `stock_depot` | Stock par produit ET par dépôt — source de vérité |
| `produit_references` | OEM, équivalents, code-barres |
| `prix_historique` | Chaque changement de prix |
| `commandes` / `commandes_details` | Achats fournisseur, réception partielle |
| `reglements` | Encaissements clients ET décaissements fournisseurs |
| `inventaires` / `inventaire_lignes` | Comptage physique et écarts |
| `retours` / `retours_details` | Retours partiels, remise en stock optionnelle |

### CUMP (coût moyen pondéré)

```
CUMP = (stock_avant × cump_avant + qté_entrée × prix_entrée) / (stock_avant + qté_entrée)
```

`ventes_details.prix_achat` est un **snapshot** figé au moment de la vente.

---

## Tests

| Fichier | Portée | Assertions |
|---|---|---|
| `test_app.py` | Métier v2, factures HTML | 84 |
| `test_v3.py` | CUMP, dépôts, créances, achats, inventaire, retours | 141 |
| `test_analyse_prix.py` | Prix pratiqués, tendances, alertes | 86 |
| `test_critical.py` | _sync_cloud, _maj_cump, régression except:pass | 8 |
| `test_mechant.py` | Tests adversariaux | — |
| `test_ui.py` | Interface v2 headless | — |
| `test_ui_v3.py` | 7 écrans v3 + non-régression | 53 |
| `test_ui_analyse.py` | Écran analyse, dialogues, PDF | 54 |

**Total : 319 assertions, 0 échec.** Chaque test utilise une base jetable.

### Pattern de test

```python
BASE = os.path.dirname(os.path.abspath(__file__))
DB_TEST = os.path.join(BASE, "test_xxx.db")

# Rediriger DB_PATH AVANT l'import de database
import database as db
db.DB_PATH = DB_TEST
db.init_database()
# ... tests ...
# Nettoyer
for s in ("", "-wal", "-shm"):
    try: os.remove(DB_TEST + s)
    except OSError: pass
```

---

## Conventions

| Règle | Exemple |
|-------|---------|
| **Français** | Fonctions, variables, messages, commentaires |
| **Type hints** | `def get_produits() -> list[dict]:` |
| **Retour métier** | `tuple[bool, str]` ou `tuple[bool, str, int \| None]` |
| **Écritures** | `with conn:` (transactions atomiques) |
| **Logs** | `log_action(action, details)` pour opérations sensibles |
| **Erreurs** | `traceback.print_exc()` — jamais `except: pass` silencieux |
| **Montants** | `fmt_money(valeur)` — jamais de formatage manuel |
| **Dates** | `fmt_date(valeur, avec_heure=True)` |
| **Treeview** | `zebre(index, extra)` pour lignes alternées |
| **Tags couleur** | `alerte` (orange), `rupture` (rouge), `inactif` (grisé), `annulee` (barré) |
| **parse_float** | `parse_float("12,5")` → 12.5 — une seule définition dans `ui_widgets.py` |

---

## Points d'attention

### Transactions atomiques
Toujours `with conn:` pour les écritures multi-lignes.

### Horodatage
`_maintenant()` produit l'heure locale. `CURRENT_TIMESTAMP` SQLite est UTC —
ne pas l'utiliser directement pour les dates métier.

### Tkinter : pack vs grid
`ajouter_scrollbars()` utilise `grid()`. Isoler dans un `Frame` dédié.

### Export PDF
Utilise Edge (toujours présent sur Windows 10/11) en mode headless.

---

## Ajouter un écran

1. Créer `page_nouveau.py` avec `class NouveauMixin`
2. Dans `core.py`, importer et ajouter à l'héritage de `Application`
3. Ajouter l'entrée dans `entrees_menu` ou `entrees_menu_second`
4. Ajouter un test dans `test_ui_v3.py`
5. Documenter dans `page_aide.py`
