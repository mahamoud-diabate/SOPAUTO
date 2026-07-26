# DEVELOPER.md — Notes techniques

Documentation destinée à la maintenance du code. Pour l'usage courant, voir
`README.md`.

---

## Architecture

```
main.py               Point d'entrée (lancer, connexion)
core.py               Application, hérite de 13 mixins
├── page_dashboard    Tableau de bord
├── page_caisse       Caisse / POS
├── page_produits     Catalogue
├── page_stock        Gestion stock
├── page_clients      Clients
├── page_categories   Catégories
├── page_fournisseurs Fournisseurs
├── page_mouvements   Historique mouvements
├── page_parametres   Admin (entreprise, users, backup)
├── page_rapports     Rapports
└── page_aide         Aide
│
├── pages_v3.py       Mixin PagesV3 : 7 écrans métier
├── pages_analyse.py  Mixin PageAnalyse : analyse commerciale
├── dialogues.py      Boîtes de dialogue (DialogueBase > tous les dialogues)
├── database.py       Accès DB, schéma, CRUD
├── metier_v3.py      Logique métier pure
├── schema_v3.py      Migration additive v3
├── analyse_prix.py   Analyse des prix pratiqués
├── factures.py       Génération HTML factures/tickets
├── export_pdf.py     HTML → PDF via navigateur headless
└── ui_widgets.py     Thème, TableauTriable, Bouton, Carte, helpers
```

**Pattern :** Chaque écran est un **mixin** — une classe avec uniquement les
méthodes de son domaine. `Application` hérite de tous les mixins. Pas d'imports
circulaires : les mixins n'importent jamais `core` ni `main`.

---

## Convention des mixins

```python
# page_nouveau.py
class NouveauMixin:
    """Docstring expliquant le rôle de cet écran."""

    def afficher_nouveau(self):
        self._nouvelle_page("...", self._idx_menu("Nouveau"))
        # construire l'interface...
```

Dans `core.py` :
```python
class Application(PagesV3, PageAnalyse, ..., NouveauMixin):
    ...
```

---

## Base de données

23 tables, 3 vues, 33 index. SQLite WAL, `foreign_keys = ON`.

### Migration

`init_database()` est **idempotent** et **non destructif** :
1. `CREATE TABLE IF NOT EXISTS` pour le socle v2
2. `_ajouter_colonne()` pour les colonnes ajoutées après coup
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

### Vues
- `v_creances` — reste dû par vente
- `v_dettes_fournisseur` — reste à payer par commande
- `v_stock_produit` — stock consolidé au CUMP

### CUMP (coût moyen pondéré)
```
CUMP = (stock_avant × cump_avant + qté_entrée × prix_entrée) / (stock_avant + qté_entrée)
```
`ventes_details.prix_achat` est un **snapshot** figé au moment de la vente.

---

## Points d'attention

### Transactions atomiques
Toujours `with conn:` pour les écritures multi-lignes. Validation de toutes
les lignes AVANT d'écrire la première.

### Horodatage
`_maintenant()` produit l'heure locale. `CURRENT_TIMESTAMP` SQLite est UTC —
ne pas l'utiliser directement pour les dates métier.

### Tkinter : pack vs grid
`ajouter_scrollbars()` utilise `grid()`. Impossible de `pack()` dans le même
parent. Isoler dans un `Frame` dédié.

### Callbacks after() et widgets détruits
Tout callback différé doit vérifier `winfo_exists()`. Utiliser
`self._planifier()` qui enregistre les IDs pour annulation au `_sur_destruction`.

### Export PDF
Aucune dépendance Python. Utilise Edge (toujours présent sur Windows 10/11)
en mode headless. L'écriture est asynchrone → attente active avec contrôle
de taille.

---

## Tests

| Fichier | Portée | Assertions |
|---|---|---|
| `test_app.py` | Métier v2, factures HTML | 84 |
| `test_v3.py` | CUMP, dépôts, créances, achats, inventaire, retours | 141 |
| `test_analyse_prix.py` | Prix pratiqués, tendances, alertes | 86 |
| `test_mechant.py` | Tests adversariaux | — |
| `test_ui.py` | Interface v2 headless | — |
| `test_ui_v3.py` | 7 écrans v3 + non-régression | 53 |
| `test_ui_analyse.py` | Écran analyse, dialogues, PDF | 54 |

**Total : 419, 0 échec.** Chaque test utilise une base jetable (redirection
de `db.DB_PATH` avant import) et la supprime en sortie.

### Écrire un test qui date une vente dans le passé
```python
ok, num, vid = db.create_vente(...)
date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
conn = db.get_connection()
with conn:
    conn.execute("UPDATE ventes SET date_vente=?", (date, vid))
conn.close()
```

---

## Conventions

- **Français** partout : fonctions, variables, messages, commentaires
- Fonctions métier : `-> tuple[bool, str]` ou `tuple[bool, str, int | None]`
- Écritures : toujours `with conn:`
- Logs : `log_action(action, details)` pour toute opération sensible
- Montants : `fmt_money(valeur)` — jamais de formatage manuel
- Dates : `fmt_date(valeur, avec_heure=True)`
- Tags Treeview : `zebre(index, extra)` pour lignes alternées
- Tags de couleur : `alerte` (orange), `rupture` (rouge), `inactif` (grisé),
  `annulee` (barré)

---

## Ajouter un écran

1. Créer `page_nouveau.py` :
```python
class NouveauMixin:
    """Description du nouvel écran."""

    def afficher_nouveau(self):
        self._nouvelle_page("🆕 Nouveau", self._idx_menu("Nouveau"))
        # ...
```

2. Dans `core.py`, importer et ajouter à l'héritage :
```python
from page_nouveau import NouveauMixin

class Application(PagesV3, PageAnalyse, ..., NouveauMixin):
    ...
```

3. Ajouter l'entrée menu dans `entrees_menu` ou `entrees_menu_second`

4. Optionnel : lier une touche dans `_raccourcis()`

5. Ajouter un test dans `test_ui_v3.py` ou `test_ui_analyse.py`

6. Documenter dans la section Aide (`page_aide.py`)
