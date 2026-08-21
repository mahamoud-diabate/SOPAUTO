# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Core
        'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
        'tkinter.simpledialog', 'sqlite3', 'hashlib', 'csv', 'shutil',
        'core', 'main', 'database', 'ui_widgets', 'db_helpers',
        # Business
        'analyse_prix', 'factures', 'export_pdf',
        'metier_v3', 'metier', 'metier._metier',
        'pages_analyse', 'schema_v3',
        # Database package
        'db', 'db._database',
        # Dialogues package
        'dialogues', 'dialogues.core', 'dialogues.formulaires',
        'dialogues.operations', 'dialogues.v3', 'dialogues.v3_analyse',
        # UI Mixins (18 total)
        'page_dashboard', 'page_caisse', 'page_produits', 'page_stock',
        'page_clients', 'page_categories', 'page_fournisseurs',
        'page_mouvements', 'page_parametres', 'page_rapports', 'page_aide',
        'page_creances', 'page_achats', 'page_inventaire',
        'page_vehicules', 'page_depots', 'page_retours', 'page_previsions',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'PIL', 'pillow'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SOPAUTO',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
