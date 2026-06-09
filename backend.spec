# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec pour bundler le backend FastAPI.

Génère un seul exécutable autonome (`backend.exe`) que Tauri embarque comme
sidecar binary. Construit en CI avec `pyinstaller --noconfirm backend.spec`.
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="backend",
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
