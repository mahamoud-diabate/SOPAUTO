# DESIGN.md — Charte visuelle de SOPAUTO

Ce document verrouille les décisions visuelles du logiciel. Toute couleur, taille
de police ou bordure ajoutée hors de ces règles est une régression, même si elle
« rend bien » isolément.

**Public visé :** un vendeur debout derrière un comptoir de pièces auto, souvent
avec un client en face, sous éclairage néon. Il lui faut de la **densité**, du
**contraste** et des **chiffres lisibles à un mètre**. Ce n'est pas un tableau de
bord SaaS consulté au calme sur un portable — et ça ne doit pas y ressembler.

---

## 1. Couleur — règle 60-30-10

| Part | Rôle | Valeur (clair) | Valeur (sombre) |
|---|---|---|---|
| **60 %** | Fond neutre teinté | `#e9eff3` fond · `#ffffff` carte | `#212a31` fond · `#2b353e` carte |
| **30 %** | Dominante métier « acier » | `#33566f` | `#7fa6bd` |
| **10 %** | Accent orange sécurité | `#b5651d` | `#e09850` |

**Le thème sombre est « ardoise claire », pas noir.** Trois paliers nettement
écartés : menu `#1a2229` < page `#212a31` < carte `#2b353e`. La version
précédente empilait `#0a1116` / `#121c24` / `#16222b` — trois valeurs quasi
identiques, sans hiérarchie, qui donnaient un bloc boueux. Un thème sombre n'est
pas le thème clair aux valeurs inversées : il se compose pour lui-même.

**Le neutre est teinté, pas gris.** Le fond clair se cale sur la teinte de la
dominante (204° contre 205°) avec 29 % de saturation. Le `#f4f6f7` précédent
n'avait que 3 points d'écart entre ses composantes RVB : un gris par défaut, qui
se lit comme tel. Le fond sombre est un bleu-ardoise (`#121c24`), jamais du noir
pur — le noir absolu donne un contraste agressif sans profondeur.

Écart carte/fond mesuré : **14 %** en clair, **27 %** en sombre. C'est ce qui
remplace les bordures.

L'accent orange est **rare et signifiant** : badge d'identité du menu, entrée de
menu active, alertes. Il ne sert jamais à décorer.

### Règles fermes

- **Aucune valeur Tailwind par défaut.** `#6366f1` (indigo-500), `#4f46e5`,
  `#0f172a`, `#94a3b8`, `#1e293b`… sont interdits. Ils constituent la signature
  visuelle reconnaissable des interfaces générées ; le projet en comptait 21.
- **Pas de dégradé**, pas de halo, pas de violet.
- **La couleur porte une information, jamais une décoration.** Sur les tuiles du
  tableau de bord, seul le compteur d'alertes se colore, et uniquement s'il est
  non nul ; les variations (`▲ / ▼`) prennent vert ou rouge parce que le signe
  a un sens.
- **Les deux thèmes portent exactement les mêmes clés** (48 chacun). Une clé
  absente d'un thème retombe silencieusement sur la couleur de l'autre : c'est
  ainsi que les en-têtes de tableaux sont restés clairs en mode sombre.
- **Le menu latéral est sombre dans les deux thèmes.** Toute couleur qui s'y
  affiche (teintes de rôle) doit rester claire quel que soit le thème actif.

Source unique : `PALETTES` dans [`ui_widgets.py`](ui_widgets.py). Aucune couleur
codée en dur dans les écrans — on passe par `COULEURS[...]`.

---

## 2. Typographie — un duo, 5 crans

| Usage | Police | Pourquoi |
|---|---|---|
| **Titres** d'écran et de carte | **Bahnschrift** (repli : Segoe UI Semibold) | Grotesque condensée native Windows 10+, registre technique — le contrepoint à l'humanisme de Segoe UI |
| **Corps, tableaux, montants** | **Segoe UI** | Chiffres **tabulaires** (toutes largeurs identiques) : les colonnes de montants s'alignent |

Les deux sont natives : aucun téléchargement sur un poste de comptoir. La
disponibilité est vérifiée au démarrage par `police_titre()`, qui interroge le
système et retombe sur Segoe UI si Bahnschrift est absente.

> **Bahnschrift a des chiffres proportionnels** (largeurs 5, 8 et 9 px selon le
> chiffre). Elle ne doit jamais servir à afficher un montant ou une quantité,
> sous peine de colonnes désalignées. Titres en texte uniquement.

**Règle de répartition : Bahnschrift = chrome, Segoe UI = données.** Le chrome,
c'est le menu, les intitulés de section, le nom de l'enseigne, les titres d'écran
et de carte. Les données, c'est tout le reste — tableaux, montants, corps de
texte.

> **Ne jamais interroger le système pendant la construction d'un écran.**
> `font.families()` est un aller-retour Tcl : appelé depuis un widget en cours de
> création, il laisse les callbacks `<Configure>` en attente se déclencher au
> milieu d'une reconstruction, sur des tableaux déjà détruits. La police est
> résolue une seule fois par `resoudre_police_titre()` dans `appliquer_theme()` ;
> `police_titre()` ne fait ensuite aucun appel Tcl. Ignorer cette règle rendait
> `test_ui_v3.py` instable (3 succès sur 5).

| Taille | Rôle |
|---:|---|
| **9** | Légende, mention, unité, sous-texte |
| **10** | Corps de texte, cellules de tableau |
| **12** | Sous-titre, en-tête de section |
| **16** | Titre d'écran |
| **20** | Valeur KPI, total de caisse |

Le projet utilisait **15 tailles** (7 à 22, quasiment tous les entiers) : ce n'est
pas une échelle, c'est un ajustement au cas par cas. Une nouvelle taille ne
s'ajoute pas — on choisit le cran le plus proche.

**Le gras est réservé aux titres et aux valeurs.** Jamais sur le palier 9
(légende) : quand tout est gras, plus rien ne ressort. Le nombre d'occurrences de
`"bold"` est passé de 74 à 39 ; il ne doit pas remonter.

---

## 3. Mise en page — séparer par le fond, pas par des filets

- **Pas de bordure 1px autour des blocs.** Une carte se détache par son propre
  fond (`card` contre `bg`, environ 4 % d'écart) et par ses marges. Empiler des
  filets gris autour de chaque bloc — et de chaque bloc imbriqué — aplatit la
  lecture au lieu de la structurer.
- **Aucun bandeau coloré de 3-4 px** en haut ou à gauche d'une carte. C'est le
  marqueur le plus reconnaissable des composants générés.
- Marges intérieures de carte : `padx=16`, `pady=(14, 2)` en tête, `(10, 14)` au
  corps. Respiration plutôt que traits.
- Les tableaux (`Treeview`) sont **sans bordure** (`relief="flat"`,
  `borderwidth=0`) ; l'alternance de lignes suffit à guider l'œil.

---

## 4. Iconographie — l'information plutôt que l'emoji

Les emoji sont **proscrits du chrome** : titres d'écran, titres de cartes,
libellés de boutons, entrées de menu. Un jeu d'emoji appliqué uniformément est
l'équivalent desktop de l'icône générique dans un carré arrondi — ça décore sans
informer, et ça date immédiatement une interface.

**Ce qui les remplace dans le menu : le raccourci clavier** (`F2`, `F4`, `F9`…),
aligné à droite. C'est l'information dont un vendeur rapide se sert réellement.

Glyphes conservés, parce qu'ils sont **fonctionnels** :

| Glyphe | Fonction |
|---|---|
| `▸` `▾` | Chevron d'ouverture d'un sous-menu |
| `●` `○` | Pastille d'état |
| `▲` `▼` | Sens d'une variation chiffrée |
| `⚠` | Alerte |
| `🌙` | Bascule de thème |
| `🔴` `🟠` | Légende de couleur de l'écran d'aide (désigne de vraies couleurs de l'interface) |

---

## 5. Les 4 états de chaque écran

| État | Règle | Où c'est déjà fait |
|---|---|---|
| **Idle** | Densité maximale, rien de superflu | tous les écrans |
| **Loading** | Vider l'état source dès le succès pour qu'une action rejouée soit inoffensive | `_enregistrer()` vide le panier juste après `create_vente()` : un second F8 mis en file trouve un panier vide, jamais de vente en double |
| **Empty** | Jamais un écran blanc — indiquer l'action suivante | `_afficher_guide_demarrage()` : 5 étapes numérotées au premier lancement |
| **Error** | Une vraie boîte de dialogue expliquant quoi faire, jamais un échec muet | `messagebox` partout ; **à surveiller** : les `except Exception: pass` avalent l'erreur au lieu de la remonter |

> **Dette connue.** Le code compte encore une trentaine de `except Exception: pass`.
> Chacun est un écran d'erreur manquant. C'est ce mécanisme qui a masqué pendant
> des semaines le fait que `_idx_menu()` échouait sur chaque entrée de menu.

---

## 6. La règle des 30 secondes

Ne pas livrer un bloc de code qu'on ne peut pas expliquer en moins de 30 secondes
— y compris un `except` qui ne fait rien. Un `pass` silencieux est précisément du
code que personne n'a besoin d'expliquer, donc que personne ne relit.

---

## 7. Vérifier la charte

```bash
python tests/run_all.py --ui      # 323 tests, 0 échec
python generate_screenshots.py    # regénère docs/ sur une base de démo jetable
```

Les captures se relisent à l'œil après toute modification visuelle : plusieurs
défauts corrigés ici (en-têtes clairs en thème sombre, menu sans surlignage,
séparateur de milliers perdu) étaient invisibles pour les tests et évidents sur
une capture.
