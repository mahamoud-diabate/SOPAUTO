"""
SODIPAC — Logique métier v3 (proxy vers metier/_metier.py)

`import metier_v3 as m3` continue de fonctionner.
"""
from metier._metier import *
import metier._metier as _metier
import sys as _sys

class _M3Proxy:
    """Redirige les accès d'attributs vers metier._metier."""
    def __getattr__(self, name):
        return getattr(_metier, name)
    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            setattr(_metier, name, value)

_sys.modules[__name__] = _M3Proxy()
