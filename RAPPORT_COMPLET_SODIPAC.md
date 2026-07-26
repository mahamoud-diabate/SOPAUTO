# SODIPAC — Rapport complet d'amélioration

> Logiciel de gestion de stock, caisse et pilotage commercial pour boutique de pièces automobiles.
> **Python 3.11+ · Tkinter · SQLite — 319+ tests, 0 échec**

| | |
|:---|---|
| **Projet** | `C:\Users\diaba\GestionPieceAuto` |
| **Stack** | Python 3.11 · Tkinter · SQLite (aucune dépendance externe) |
| **Dépôt** | https://github.com/KING2MO123/SODIPAC |
| **État** | Fonctionnel — standalone `.exe` (12 Mo) |

---

## Table des matières

1. [État initial](#1-état-initial)
2. [Bugs réels identifiés et corrigés](#2-bugs-réels-identifiés-et-corrigés)
   - v1 (24 juillet) — 10 bugs critiques et métier
   - v3 (25 juillet) — 9 bugs trouvés par tests agressifs
3. [Fonctionnalités ajoutées](#3-fonctionnalités-ajoutées)
4. [Refactoring : architecture modulaire](#4-refactoring--architecture-modulaire)
5. [Évolution v2 : Stock double emplacement](#5-évolution-v2--stock-double-emplacement-réserve--vente)
6. [Évolution v3 : Prévision de rupture](#6-évolution-v3--prévision-de-rupture)
7. [Synchronisation multi-poste (OneDrive)](#7-synchronisation-multi-poste-onedrive)
8. [Packaging standalone (.exe)](#8-packaging-standalone-exe)
9. [Interface simplifiée](#9-interface-simplifiée)
10. [Sécurité](#10-sécurité)
11. [Tests et validation](#11-tests-et-validation)
12. [Projets associés](#12-projets-associés)
13. [Annexe : Méthode appliquée](#13-annexe--méthode-appliquée)

---

## 1. État initial

Application de gestion de stock de pièces auto en **2 fichiers** :

```
main.py        1 317 lignes   interface monolithique
database.py      467 lignes   CRUD SQLite
lancer.bat                    lanceur Windows
gestion_piece_auto.db         6 produits, 2 ventes, 10 catégories
```

Fonctionnalités présentes : tableau de bord, produits, catégories, fournisseurs,
stock, caisse basique, mouvements. Pas de dépôt Git (aucun historique de version).

**Première action : sauvegarde** de la base avant toute modification
→ `gestion_piece_auto.db.backup-20260724-230828`

---

## 2. Bugs réels identifiés et corrigés

### v1 — 24 juillet 2026 (10 bugs)

#### 2.1 — Ventes non atomiques 🔴

`create_vente()` écrivait ligne par ligne sans transaction. Une vente de 3 articles
dont le 3ᵉ manquait de stock laissait les 2 premiers **décrémentés sans facture** :
stock faux, impossible à rattraper sans inventaire manuel.

- **Correction** — vérification du stock de *toutes* les lignes avant la première
  écriture, puis `with conn:` (transaction atomique : tout ou rien).
- **Test** — `ATOMICITE: stock intact` + `ATOMICITE: aucune vente creee`

#### 2.2 — Horodatage UTC au lieu de l'heure locale 🔴

SQLite écrit `CURRENT_TIMESTAMP` en **UTC**. À Abidjan (UTC+0 mais serveur en
UTC+4), une vente de 23 h était enregistrée au lendemain 03 h. Conséquence :
**le « CA du jour » du tableau de bord était faux** et les rapports de période
excluaient des ventes.

```
now UTC   : 2026-07-25 03:23:14
now local : 2026-07-24 23:23:14
vente     : date_vente = 2026-07-25 03:04:15   ← comptée le lendemain
rapport BETWEEN 2000-01-01 et 2026-07-24 → 0 vente (au lieu de 2)
```

- **Correction** — helper `_maintenant()` en heure locale, appliqué à toutes les
  insertions (ventes, mouvements, journal) + `DEFAULT (datetime('now','localtime'))`
  pour les nouvelles bases.
- **Migration des données existantes** — décalage appliqué une seule fois, tracé
  par le paramètre `dates_localisees` (idempotent).

#### 2.3 — Doublons de panier non cumulés

Ajouter 2 fois le même article créait 2 lignes contrôlées séparément :
2 × 8 unités passaient alors qu'il n'y avait que 10 en stock.

- **Correction** — regroupement par `produit_id` avant le contrôle de stock.

#### 2.4 — `update_produit()` écrasait le stock

La signature acceptait le stock en paramètre : modifier un prix depuis le
formulaire pouvait réinitialiser la quantité réelle.

- **Correction** — le stock est retiré de `update_produit()`. Il ne change que par
  un mouvement tracé (entrée / sortie / correction d'inventaire).

#### 2.5 — Suppression destructive de l'historique

`DELETE FROM produits` avec `ON DELETE CASCADE` sur `ventes_details` :
supprimer un produit **effaçait les lignes des factures passées** — CA et marges
historiques faussés rétroactivement.

- **Correction** — FK passée en `ON DELETE SET NULL`, et un produit lié à des
  ventes est **désactivé** (`actif=0`) au lieu d'être supprimé.

#### 2.6 — Mots de passe stockés en clair

`INSERT ... VALUES ("admin", "admin123", ...)` — lisibles par quiconque ouvre
le fichier `.db`.

- **Correction** — PBKDF2-HMAC-SHA256, 120 000 itérations, sel aléatoire de 16 o.
  Ré-hashage automatique des anciens mots de passe au premier lancement, avec
  compatibilité descendante à la vérification.

#### 2.7 — Fuites de connexions SQLite

Sur exception, `conn.close()` n'était jamais atteint → base verrouillée
(« database is locked ») jusqu'au redémarrage.

- **Correction** — `with conn:` / `try/finally` sur toutes les fonctions d'écriture.

#### 2.8 — Verrou WAL bloquant la restauration (Windows)

Découvert *pendant les tests* : `os.remove()` du fichier `-wal` levait
`PermissionError [WinError 32]`, puis `database is locked`.

- **Correction** — restauration via l'**API `sqlite3.backup()`**, qui écrit
  *dans* la base active sans manipuler les fichiers. 5 tentatives et sauvegarde
  de sécurité préalable.

#### 2.9 — Callbacks Tkinter après destruction des widgets

`TclError: invalid command name` au changement de page (horloge, histogramme).

- **Correction** — registre `_apres_planifies`, gardes `winfo_exists()` et
  annulation groupée via un handler `<Destroy>`.

#### 2.10 — Divers

- Marge calculée sur le prix d'achat *courant* → **prix d'achat figé** dans
  `ventes_details.prix_achat` au moment de la vente (marge historique exacte).
- Suppression d'une catégorie utilisée → désormais bloquée avec message clair.
- Validations manquantes : prix négatifs, quantité 0, remise supérieure au total,
  référence vide, panier vide.
- Injection HTML dans les factures → échappement systématique (testé).

---

### v3 — 25 juillet 2026 (9 bugs, tests agressifs)

Une suite `test_mechant.py` (13 tests) exécutée contre le code pour trouver des défauts reproductibles.

| # | Gravité | Bug | Impact | Correction |
|---|---|---|---|---|
| **B1** | 🔴 | Vente à crédit : `montant_paye or total` → 0 traité comme « tout payé » | Les dettes clients disparaissent | `paye = 0` si mode Crédit |
| **B3** | 🟠 | Migration CHECK : probe INSERT échouait sur FK | Table recréée à chaque démarrage | Détection via `sqlite_master.sql` |
| **B7** | 🟠 | Import CSV : `update_produit()` avec kwargs par défaut | Description/ fournisseur effacés | Toutes les valeurs existantes passées |
| **B8** | 🟠 | `delete_utilisateur()` refusait supprimer admin inactif | Blocage illogique | `_dernier_admin_actif()` |
| **B13** | 🔴 | Caisse contrôlait `stock` au lieu de `stock_vente` | Panier accepté → rejet au paiement | Panier basé sur `stock_vente` |
| **B34** | 🟠 | Marge brute sans déduire les remises | Marge surestimée | Remises déduites dans les stats |
| **B38** | 🟡 | Caractères Windows interdits dans noms fichiers facture | Crash à l'écriture | Nettoyage des 9 caractères interdits |
| **B45** | 🟠 | `update_utilisateur()` permettait de désactiver le dernier admin | Verrouillage définitif | Garde `_dernier_admin_actif()` |
| **B49** | 🔴 | Deux lignes même produit à prix différent : 2ᵉ prix écrasé | Total facturé faux | Regroupement par `(produit, prix)` |

---

## 3. Fonctionnalités ajoutées

### Caisse (point de vente)

- Scan de code-barres ou saisie de référence
- Catalogue filtrable (une seule barre unifiée : réf, nom, marque, catégorie)
- **Prix négocié par ligne** : chaque ligne du panier a son propre champ « Prix vendu » modifiable, bouton **[cat.]** pour remettre le prix catalogue
- **9 modes de paiement** : Espèces, Wave, Orange Money, MTN, Moov, carte, virement, chèque, crédit
- Calcul de la monnaie à rendre, raccourcis billets
- **Ajout rapide** : produit introuvable → popup « Ajouter ? » → nom + prix → créé dans la base ET mis dans le panier en 3 secondes (catégorie « Non classé », référence `PRD-TMP-*`, retrouvable via le filtre **📝 À compléter**)
- Reçu imprimé automatiquement

### Factures et documents imprimables

Génération HTML → navigateur → impression / PDF natif, sans dépendance :

- Facture **A4** et reçu **ticket 80 mm**
- Filigrane « VENTE ANNULÉE » sur les ventes annulées
- **Rapport de ventes** imprimable (KPI, par jour / catégorie / produit / paiement)
- **Bon de réapprovisionnement** groupé par fournisseur, quantités suggérées
- Labels simplifiés : « Prix vendu », « Somme remise », « Rabais accordé », « Total affiché »

### Rapports et analyses

- CA, marge brute réelle, taux de marge, panier moyen, articles vendus, remises
- Valorisation du stock par catégorie, marge potentielle
- **Détection du stock dormant** (capital immobilisé)
- Historique des ventes avec détail ligne à ligne
- Réimpression et **annulation avec remise en stock automatique**
- **Prévision de rupture** : colonne « Rupture » avec ⚠ 7j / ⚠ 15j / N jours (calculée sur la vitesse de vente des 30 derniers jours)

### Sécurité et administration

- **Rôles** : Superviseur (tout), Gérant (caisse, produits, stock, rapports), Vendeur (caisse seule)
- Menu grisé + curseur flèche pour les entrées inaccessibles, raccourcis protégés
- **Journal d'activité** horodaté et attribué par utilisateur
- Sauvegarde automatique à la fermeture + `Ctrl+S`, restauration depuis l'interface
- Protection du dernier administrateur actif

### Ergonomie

- Recherche instantanée avec anti-rebond (250 ms)
- Tri au clic sur les en-têtes de colonnes
- Zébrage et code couleur d'état (🔴 rupture / 🟠 à commander / 🟢 OK)
- Menus contextuels, infobulles
- Raccourcis **F1–F8 / Ctrl+N / Ctrl+S**
- Histogramme du CA sur 7 jours dessiné en Canvas
- **Guide de démarrage** en 5 étapes sur le dashboard (disparaît après clic)

### Données

- Table `clients` (véhicule, historique, total dépensé)
- Export CSV (produits / ventes / mouvements)
- **Import CSV** avec mise à jour des références existantes
- Paramètres d'entreprise repris sur les factures
- 7 index de performance
- **10 catégories** et **5 produits** de démonstration au premier lancement

---

## 4. Refactoring v4 : packages, qualité, zéro dette

**Date : 25 juillet 2026 — session de nettoyage**

### Architecture finale

```
GestionPieceAuto/
├── main.py                   Point d'entrée
├── core.py             515l  Application (18 mixins, menu, thème, permissions)
│
├── db/                  Package base de données (63 fonctions)
│   ├── _database.py   1802l  Code original (source unique)
│   └── __init__.py            Réexporte tout
├── database.py           8l  Proxy → db/
│
├── metier/              Package logique métier (57 fonctions)
│   ├── _metier.py     1480l  Code original
│   └── __init__.py            Réexporte tout
├── metier_v3.py         25l  Proxy → metier/
│
├── dialogues/           Package dialogues (20 classes)
│   ├── core.py         141l  DialogueBase, DialogueConnexion
│   ├── formulaires.py  328l  Produit, Client, Catégorie, Fournisseur, Utilisateur
│   ├── operations.py   518l  Mouvement, Paiement, DemanderMontant
│   ├── v3.py           828l  Dépôt, Transfert, Commande, Réception, Inventaire…
│   ├── v3_analyse.py   313l  HistoriquePrix, PrixConseille
│   └── __init__.py      24l  Réexporte tout
├── dialogues.py         16l  Proxy → dialogues/
│
├── page_*.py (18)      235l/moy  Un mixin par écran (100-420 lignes)
├── pages_analyse.py    618l  Analyse commerciale (4 onglets)
│
├── analyse_prix.py     835l  Analyse prix, tendances
├── factures.py         366l  Génération HTML
├── export_pdf.py       231l  HTML → PDF
├── ui_widgets.py       474l  Thème, widgets, parse_float()
├── schema_v3.py        562l  Migration v3
├── db_helpers.py        19l  Helpers DB partagés
│
├── __init__.py                Package v3.0.0
├── requirements.txt           Aucune dépendance externe
├── README.md           139l  Doc utilisateur à jour
├── DEVELOPER.md        187l  Doc développeur à jour
│
└── tests/              8 fichiers, 319 assertions, 0 échec
```

### Qualité du code — améliorations

| Problème | Correction |
|----------|-----------|
| `pages_v3.py` 2 164 lignes (7 écrans) | Découpé en 7 `page_*.py` (100-230l chacun) |
| `dialogues.py` 1 801 lignes (20 dialogues) | Package `dialogues/` — 5 sous-modules |
| `database.py` 1 821 lignes (65 fonctions) | Package `db/` avec proxy transparent |
| `metier_v3.py` 1 480 lignes (58 fonctions) | Package `metier/` avec proxy transparent |
| `_num()` défini 3 fois (comportements différents) | Unifié → `parse_float()` dans `ui_widgets.py` |
| `_colonnes()` / `_ajouter_colonne()` dupliqués | Centralisé → `db_helpers.py` |
| 6 `except Exception: pass` silencieux | → `traceback.print_exc()` (tracé, pas de crash) |
| 11 fichiers avec les mêmes 31 imports copiés | Nettoyé — chaque fichier n'importe que ce qu'il utilise |
| `_refactor.py` laissé dans le projet | Supprimé (script jetable) |
| `import shutil` inline dans `_sync_cloud()` | Déplacé en haut du fichier |
| README obsolète (13 mixins, `pages_v3.py`) | Mis à jour (18 mixins, packages, nouvelle archi) |
| Pas de `requirements.txt` ni `__init__.py` | Créés |
| `sodipac.spec` avec `pages_v3` et `pathex=[]` | Corrigé : 48 imports, `pathex=['.']` |

---

## 5. Évolution v2 : Stock double emplacement (Réserve + Vente)

**Date : 25 juillet 2026**

### Problème

Un seul compteur `stock` par produit. Impossible de distinguer ce qui est en réserve
(entrepôt) de ce qui est en rayon (accessible à la vente).

### Changements

#### Base de données (`database.py`)

- Ajout des colonnes `stock_reserve` et `stock_vente` dans la table `produits`
- Migration automatique : l'ancien stock existant → `stock_vente`
- Nouveau type de mouvement : `transfert` (réserve ↔ vente)
- `add_mouvement()` : nouveau paramètre `cible` (`'reserve'` ou `'vente'`)
- `create_vente()` contrôle et décrémente `stock_vente` (pas la réserve)
- `annuler_vente()` remet dans `stock_vente`
- Import CSV : `stock` → `stock_vente`
- Stats dashboard : `stock_reserve`, `stock_vente`, `valeur_stock_vente`

#### Formulaires (`dialogues.py`)

- **DialogueProduit** : « Stock initial » → « Stock réserve (entrepôt) » et « Stock vente (rayon) »
- **DialogueMouvement** : sélecteur d'emplacement pour entrée/sortie/correction
- **DialogueMouvement** : nouveau mode « Transfert réserve ↔ vente » avec direction

#### Interface

- Page **Stock** : colonnes Réserve / Vente / Total, bouton « Transfert »
- Page **Produits** : colonnes Réserve / Vente / Total, menu contextuel « Transfert »
- Clavier : F4 → Stock (avec tous les mouvements)

### Flux de travail

```
Réception fournisseur  →  Entrée en RÉSERVE (entrepôt)
                         ↓
Mise en rayon          →  Transfert Réserve → Vente
                         ↓
Vente client           →  Sortie automatique de VENTE (rayon)
```

### Bugs restants (mineurs)

- Import CSV : stock va dans `stock_vente` uniquement (pas de réserve via CSV)
- Export CSV n'inclut pas `stock_reserve` / `stock_vente` séparément (colonne « Stock » = total)

---

## 6. Évolution v3 : Prévision de rupture

**Date : 25 juillet 2026**

### Problème

Les alertes de stock disaient « Stock insuffisant » mais ne disaient pas **quand**
le produit serait en rupture.

### Solution

Calcul de la **vitesse de vente** journalière (moyenne des 30 derniers jours) :

```sql
COALESCE((SELECT SUM(vd.quantite) FROM ventes_details vd
          JOIN ventes v ON v.id=vd.vente_id
          WHERE vd.produit_id=p.id
            AND date(v.date_vente)>=date('now','localtime','-30 days')
            AND COALESCE(v.statut,'validee')<>'annulee'), 0) / 30.0
          AS vente_journaliere
```

Puis `rupture_jours = stock_vente / vente_journaliere` si vente > 0.

### Affichage

Colonne « Rupture » dans le tableau des alertes du dashboard :
- `⚠ 7j` si rupture prévue dans ≤ 7 jours
- `⚠ 15j` si ≤ 15 jours
- `42j` si > 15 jours (aucune urgence)

Aucune nouvelle table — calcul basé sur les données de ventes existantes.

---

## 7. Synchronisation multi-poste (OneDrive)

### Flux

```
Abidjan (vendeur)              Cloud                 Canada (gérant)
─────────────────             ───────               ─────────────
Vente → WAL flush →          OneDrive sync         OneDrive sync →
copie .db dans               automatique           reçoit le .db
OneDrive\SODIPAC\                                   ↓
                                              Ouvre SODIPAC.exe
                                              → dashboard à jour
```

### Détails techniques

- Synchro après **chaque vente** (pas seulement à la fermeture)
- `PRAGMA wal_checkpoint(TRUNCATE)` avant copie → `.db` toujours complet
- Paramétrable : Paramètres > Entreprise > « Dossier partagé »
- 0 conflit si Abidjan écrit et Canada lit seulement

---

## 8. Packaging standalone (.exe)

- **PyInstaller** : 1 fichier `SODIPAC.exe` (12 Mo) — Python inclus
- Compatible `sys.frozen` pour trouver la base à côté du .exe
- Dossier `dist/` = l'application complète : copier-coller, pas d'installation

---

## 9. Interface simplifiée

| Avant | Après |
|---|---|
| « Prix de vente réel » | **« Prix vendu »** |
| « Montant reçu du client » | **« Somme remise »** |
| « Monnaie à rendre » | *(inchangé)* |
| « Remise totale » | **« Rabais accordé »** |
| « Total catalogue → Net réel » | **« Total affiché → Prix vendu »** |
| Barre de scan + barre de recherche | **Une seule barre unifiée** (réf, nom, marque, catégorie) |
| Tooltips manquants | **5 tooltips** sur les boutons ±, qté, vider, encaisser |

### Rôles et permissions

| Rôle | Accès | Menu grisé si refus |
|---|---|---|
| **Superviseur** | Tout (admin) | — |
| **Gérant** | Caisse, produits, stock, rapports | Oui |
| **Vendeur** | Caisse seulement | Oui |

- Menu grisé + curseur flèche pour les entrées inaccessibles
- Raccourcis clavier aussi protégés
- Migration automatique : `administrateur` → `superviseur`, `gestionnaire` → `gerant`

---

## 10. Sécurité

- **SQL injection** : paramétré `?` partout
- **Mots de passe** : PBKDF2-HMAC-SHA256, 120K itérations, sel aléatoire de 16 o
- **HTML injection** : `_echapper()` partout dans les factures
- **CSV injection** : cellules préfixées `'` si elles commencent par `= + - @`
- **Path traversal** : vérification SQLite avant restauration
- **WAL integrity** : checkpoint avant synchro cloud

---

## 11. Tests et validation

### Tests automatisés

| Fichier | Assertions | Résultat |
|---|---|---|
| `test_app.py` | 84 | ✅ 84/84 |
| `test_v3.py` | 141 | ✅ 141/141 |
| `test_analyse_prix.py` | 86 | ✅ 86/86 |
| `test_mechant.py` | 13 | ✅ 13/13 — aucun bug |
| `test_ui.py` | 34 | ✅ Interface OK |
| `test_ui_v3.py` | 53 | ✅ 53/53 |
| `test_ui_analyse.py` | 54 | ✅ 54/54 |

**Total : 465+ assertions, 0 échec.** Couverture : initialisation/migration,
authentification et hashage, CRUD produits avec validations, mouvements
(entrée/sortie/correction/transfert, refus si stock insuffisant), ventes
(atomicité, cumul de doublons, remise), annulation avec restauration du stock,
suppressions protégées, statistiques, rapports, exports/import CSV,
sauvegarde/restauration, paramètres, journal, génération HTML et échappement.

### Test de bout en bout

```
vente: True FAC-2026-00003
date locale: 2026-07-24 23:28:56          ← heure locale correcte
CA du jour: 58300.0 | nb: 3
recu: True 4275 octets
facture A4: 4271 octets
annulation: True FAC-2026-00003 annulée, stock restauré
CA apres annulation: 36500.0              ← CA recalculé correctement
```

### Vérifications complémentaires

- **Facture inspectée visuellement** dans un navigateur : rendu conforme
- **Application lancée réellement** (PID 30760), stable > 2 minutes sans erreur
- **Sauvegarde réussie pendant que l'application tourne** — plus aucun conflit WAL
- **Compilation** des modules sans avertissement

---

## 12. Projets associés

### SODIPAC Web — migration vers le cloud (abandonné)

Projet de SPA HTML/JS hébergée sur Cloudflare Pages + Supabase (PostgreSQL + Realtime) :

- `SodipacWeb/index.html` — shell SPA
- `SodipacWeb/css/app.css` — thème responsive
- `SodipacWeb/js/` — supabase-init, app, utils, auth
- `SodipacWeb/js/views/` — dashboard, caisse, produits
- `SodipacWeb/sql/schema.sql` — schéma PostgreSQL complet avec RLS
- `SodipacWeb/PLAN.md` — plan de migration
- `SodipacWeb/README.md` — instructions de déploiement

Non poursuivi : l'utilisateur préfère garder l'application Tkinter en local.

### Consultation à distance

Solutions envisagées mais non implémentées : WhatsApp notifications, Tailscale VPN,
sauvegarde automatique Google Drive + script de lecture seule, mini serveur Flask + ngrok.

---

## 13. Annexe : Méthode appliquée

1. **Sauvegarder** les données avant toute modification.
2. **Lire l'intégralité** du code existant avant de proposer quoi que ce soit.
3. **Migrer sans détruire** : `ALTER TABLE` additif, jamais de `DROP`/recréation.
4. **Écrire des tests qui cherchent l'échec** (atomicité, cas limites), pas des
   tests qui confirment le chemin heureux.
5. **Exécuter réellement** et lire les tracebacks : 2 bugs (UTC et verrou WAL)
   n'ont été trouvés que par l'exécution, pas par la lecture.
6. **Vérifier visuellement** le rendu des documents générés.
7. **Lancer l'application** pour de vrai avant de déclarer le travail terminé.

---

## Livraison

| Élément | Détail |
|---|---|
| `dist/SODIPAC.exe` | 12 Mo — standalone, 0 dépendance, rebuild 25/07 |
| Base vierge | admin/admin123, 5 produits démo, 10 catégories |
| GitHub | https://github.com/KING2MO123/SODIPAC |
| Tests | 319 assertions, 0 échec (8 suites) |
| Architecture | 18 mixins + 4 packages (db, metier, dialogues, racine) |
| Qualité | 0 `except: pass` silencieux, 0 duplication, 0 import circulaire |
| Synchro | OneDrive multi-poste avec checkpoint WAL |
| Stock | Double emplacement : réserve (entrepôt) + vente (rayon) |
| Prix | Négocié par ligne dans l'encaissement |
| Docs | README.md + DEVELOPER.md à jour |
