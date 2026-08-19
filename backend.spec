# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec pour bundler le backend FastAPI.

Génère un seul exécutable autonome (`appli-rentree-backend.exe`) que Tauri
embarque comme sidecar binary. Le nom est explicite pour éviter toute confusion
avec d'autres apps Tauri du même utilisateur (ex: Dashboard-Web) qui ont aussi
un sidecar Python — éviter qu'un `taskkill /IM backend.exe` accidentel touche
les deux.

Construit en CI avec `pyinstaller --noconfirm backend.spec`.
"""

block_cipher = None


a = Analysis(
    ["run_backend.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # FastAPI/Starlette/Pydantic ont des imports dynamiques que PyInstaller
        # ne détecte pas toujours.
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # pandas a besoin de toutes ses libs de bas niveau
        "pandas",
        "openpyxl",
        "xlrd",
        "lxml",
        "lxml.html",
        "lxml.etree",
        # SQLAlchemy (certains dialectes sont chargés dynamiquement)
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.sql.default_comparator",
        # Google Workspace API — la découverte de service et les modules
        # crypto sont chargés dynamiquement, PyInstaller ne les voit pas.
        "googleapiclient",
        "googleapiclient.discovery",
        "googleapiclient.http",
        "googleapiclient.model",
        "googleapiclient.discovery_cache",
        "googleapiclient.discovery_cache.base",
        "google.auth",
        "google.auth.transport.requests",
        "google.oauth2",
        "google.oauth2.service_account",
        "google_auth_httplib2",
        "httplib2",
        "pyasn1_modules",
        "pyasn1_modules.rfc2459",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # On n'a pas besoin des bibliothèques de plot/notebook
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# googleapiclient embarque les fiches de découverte de TOUTES les API Google :
# 586 fichiers pour 102 Mo, soit plus que tout le reste de l'application. On
# n'appelle que l'Admin SDK Directory. Les garder doublerait le poids de
# l'exécutable, donc le temps de téléchargement de chaque mise à jour.
_FICHES_UTILES = {"admin.directory_v1.json", "admin.directoryv1.json"}


def _sans_fiches_inutiles(datas):
    gardees = []
    for entree in datas:
        chemin = entree[0].replace("\\", "/")
        if "discovery_cache/documents/" in chemin:
            if chemin.rsplit("/", 1)[-1] not in _FICHES_UTILES:
                continue
        gardees.append(entree)
    return gardees


a.datas = _sans_fiches_inutiles(a.datas)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="appli-rentree-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Garde la console pour les logs en dev ; on cachera en prod via Tauri
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
