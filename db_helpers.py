"""
SOPAUTO — Helpers base de données partagés.

Fonctions utilisées à la fois par database.py et schema_v3.py
sans créer d'import circulaire.
"""


def colonnes(cursor, table: str) -> set:
    """Retourne l'ensemble des noms de colonnes d'une table."""
    return {r[1] for r in cursor.execute(f"PRAGMA table_info({table})")}


def ajouter_colonne(cursor, table: str, colonne: str, definition: str) -> bool:
    """Ajoute une colonne si elle n'existe pas déjà. Retourne True si ajoutée."""
    if colonne not in colonnes(cursor, table):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")
        return True
    return False
