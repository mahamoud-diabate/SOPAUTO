"""
Amorçage commun aux tests, à importer en premier dans chaque fichier de test.

Deux rôles :

1. Rendre les modules de l'application importables. Les tests vivent dans
   `tests/` alors que le code reste à la racine : sans cet ajout, `import main`
   ou `import database` échouent, car Python ne cherche que le dossier du
   script lancé.

2. Forcer la sortie console en UTF-8. Les tests affichent des accents et des
   flèches « → » ; sur une console Windows par défaut (cp1252), l'affichage
   levait `UnicodeEncodeError` et interrompait la série en cours d'exécution —
   `test_v3.py` et `test_analyse_prix.py` s'arrêtaient ainsi avant la fin,
   masquant 227 des 319 tests.
"""
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

for flux in (sys.stdout, sys.stderr):
    # `reconfigure` existe depuis Python 3.7 ; absent si la sortie est déjà
    # redirigée vers un objet qui ne le supporte pas (on ignore alors).
    try:
        flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
