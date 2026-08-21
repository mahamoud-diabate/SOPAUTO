# Plan d'Étude et de Développement C++ — SOPAUTO From Scratch

Ce plan est conçu pour vous faire passer de zéro à la maîtrise du langage **C++ moderne (C++20)** et vous rendre **100% autonome sans assistance d'IA**.

---

## 1. Feuille de Route par Phases

```
PHASE 1 : Fondations (Syntaxe & Fonctions)
  └─► PHASE 2 : Mémoire (Pointeurs & RAII)
        └─► PHASE 3 : Orienté Objet & STL (vector, map)
              └─► PHASE 4 : SQLite C API (Database Engine)
                    └─► PHASE 5 : Win32 API (GUI Native)
                          └─► PHASE 6 : Assemblage SOPAUTO C++
```

---

### Phase 1 : Les Fondations du C++ Moderne
**Objectif** : Maîtriser la syntaxe, les types et la transmission des données.

- **Variables & Types** : `int`, `double`, `bool`, `char`, `std::string`.
- **Contrôle de flux** : `if/else`, `switch`, boucles `for` (classique et range-based `for (const auto& item : collection)`).
- **Transmission par Valeur vs Référence** :
  - *Par valeur* (`void f(std::string s)`) : crée une copie lourde en mémoire.
  - *Par référence constante* (`void f(const std::string& s)`) : **méthode standard C++** (rapide, sans copie, lecture seule).

---

### Phase 2 : La Gestion Mémoire & Les Pointeurs (Le Cœur du C++)
**Objectif** : Comprendre exactement où vivent vos données.

- **Stack (Pile)** vs **Heap (Tas)** :
  - *Stack* : mémoire automatique, très rapide, nettoyée à la sortie du bloc `{}`.
  - *Heap* : mémoire dynamique, allouée à la main.
- **Pointeurs & Références** :
  - Pointeur (`T* p`) : stocke l'adresse mémoire d'un objet.
  - Référence (`T& r`) : alias direct vers une variable existante.
- **Principe RAII (*Resource Acquisition Is Initialization*)** :
  - En C++ moderne, on ne fait jamais `new` et `delete` manuellement.
  - On utilise des **pointeurs intelligents** (`std::unique_ptr<T>` et `std::shared_ptr<T>`) qui libèrent la mémoire automatiquement quand l'objet est détruit.

---

### Phase 3 : Orienté Objet & Standard Template Library (STL)
**Objectif** : Structurer l'application et utiliser les conteneurs standard.

- **Classes & Structures** :
  - `struct` : membres `public` par défaut (utilisé pour les objets de données simples / DTO).
  - `class` : membres `private` par défaut (encapsulation métier).
  - Constructeurs, destructeurs, `explicit`, `const methods`.
- **Conteneurs STL à maîtriser absolument** :
  - `std::vector<T>` : tableau dynamique (le conteneur #1 en C++).
  - `std::unordered_map<Key, Value>` : dictionnaire clé-valeur rapide.
  - `std::optional<T>` : pour gérer l'absence de valeur sans utiliser de pointeur nul.

---

### Phase 4 : Base de Données — Intégration SQLite C API
**Objectif** : Interagir avec `gestion_piece_auto.db` en C++.

- Inclusion du header `<sqlite3.h>` et liaison avec `sqlite3.dll` / `sqlite3.o`.
- **Cycle de vie des requêtes préparées** :
  1. `sqlite3_open()` — ouvrir la connexion.
  2. `sqlite3_prepare_v2()` — compiler la requête SQL.
  3. `sqlite3_bind_text()` / `sqlite3_bind_int()` — injecter les paramètres (sécurité anti-injection SQL).
  4. `sqlite3_step()` — exécuter la ligne / lire les résultats.
  5. `sqlite3_finalize()` — libérer la mémoire de la requête.

---

### Phase 5 : Interface Graphique Native Windows (Win32 API)
**Objectif** : Créer des fenêtres, boutons et tableaux natifs sans framework lourd.

- **Boucle de Messages Windows** :
  ```cpp
  MSG msg = {};
  while (GetMessage(&msg, NULL, 0, 0)) {
      TranslateMessage(&msg);
      DispatchMessage(&msg);
  }
  ```
- **Procédure de Fenêtre (`WndProc`)** : Gestion des événements (`WM_CREATE`, `WM_COMMAND`, `WM_PAINT`, `WM_DESTROY`).
- **Contrôles Natifs (`CreateWindowEx`)** :
  - Boutons (`"BUTTON"`), Zones de saisie (`"EDIT"`), Labels (`"STATIC"`).
  - Grilles de données (`WC_LISTVIEW` avec style `LVS_REPORT`).

---

## 2. Rappels Critiques sur les Pièges à Éviter

| Piège C++ classique | Solution C++ Moderne |
|---|---|
| Fuite mémoire avec `new` sans `delete` | Utiliser `std::make_unique<T>()` |
| Modification accidentelle d'un objet | Déclarer les méthodes et paramètres en `const` |
| Inclusions circulaires de headers (`#include`) | Utiliser `#pragma once` et les déclarations anticipées (*forward declarations*) |
| Copie involontaire de gros tableaux | Passer par référence constante (`const std::vector<T>&`) |

---

## 3. Méthodologie d'Étude Autonome (Se passer de l'IA)

### Vos 3 ressources de référence indispensables :
1. **[cppreference.com](https://fr.cppreference.com/)** : La documentation officielle et exhaustive du langage et de la STL.
2. **[learncpp.com](https://www.learncpp.com/)** : Le meilleur cours complet et gratuit existant (suivez-le chapitre par chapitre).
3. **La documentation Microsoft Win32** (`docs.microsoft.com`) pour les fonctions d'interface Windows.

### La méthode de travail pratique :
- **Apprendre à lire les erreurs du compilateur** :
  Compilez toujours avec les flags stricts : `g++ -Wall -Wextra -Wpedantic -std=c++20 main.cpp -o main.exe`.
  Le compilateur `g++` vous indique la ligne exacte et la raison précise des erreurs.
- **Utiliser le débogueur (`gdb` ou Visual Studio)** :
  Posez des points d'arrêt (*breakpoints*), exécutez pas-à-pas (`F10`) et inspectez la valeur de vos variables en mémoire au lieu d'ajouter des `std::cout`.
- **Prototypage isolé** :
  Ne développez jamais directement dans le grand projet. Écrivez un petit fichier de test (ex: `test_sqlite.cpp`) de 30 lignes, faites-le marcher, puis intégrez le code dans votre architecture.

---

### Structure recommandée pour votre dossier C++ (`C:\Users\diaba\SOPAUTO_CPP`) :

```
SOPAUTO_CPP/
├── include/           # Fichiers d'en-tête (.h / .hpp)
│   ├── Database.hpp
│   ├── Produit.hpp
│   └── MainWindow.hpp
├── src/               # Code source (.cpp)
│   ├── Database.cpp
│   ├── Produit.cpp
│   ├── MainWindow.cpp
│   └── main.cpp
├── lib/               # Bibliothèques (sqlite3.lib / .a)
├── build.bat          # Script de compilation g++
└── gestion_piece_auto.db
```
