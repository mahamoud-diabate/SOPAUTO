"""
SOPAUTO — Base de données (proxy vers db/_database.py)

`import database as db` continue de fonctionner. Les tests qui modifient
`db.DB_PATH` sont redirigés vers le vrai module db._database.
"""
from db._database import *

# Proxy DB_PATH — les tests le modifient, on doit propager vers _database
import db._database as _db
import sys as _sys

class _ModuleProxy:
    """Redirige les accès d'attributs vers db._database."""
    def __getattr__(self, name):
        return getattr(_db, name)
    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            setattr(_db, name, value)

_sys.modules[__name__] = _ModuleProxy()
