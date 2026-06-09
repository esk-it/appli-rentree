# Appli Rentrée — Ensemble Scolaire du Kreisker

Application interne pour préparer la rentrée scolaire : lit l'export Charlemagne, calcule entrants/restants/sortants en comparant avec l'année précédente, et génère les fichiers d'import pour les logiciels métier (KoXo, Google Workspace, PMB, SmartAir, CardStudio).

## Stack

- **Tauri 2** (Rust) — fenêtre native + auto-updater signé
- **Svelte 5** + **Vite** + **Tailwind 4** — frontend
- **FastAPI** (Python 3.12+) en sidecar — backend HTTP/REST embarqué
- **SQLite** via SQLAlchemy — persistance N et N-1
- **GitHub Actions** — build .exe + signature, déclenché par tag `v*`

## Pour publier une nouvelle version (workflow quotidien)

C'est le **seul** workflow que tu utilises en pratique :

```bash
# 1. Incrémenter la version dans src-tauri/tauri.conf.json
#    (ex. 0.1.0 → 0.2.0 pour une nouvelle fonctionnalité)

# 2. Commit + push sur main
git add .
git commit -m "v0.2.0 — description"
git push origin main

# 3. Tag + push (déclenche le build sur GitHub)
git tag v0.2.0
git push origin v0.2.0
```

GitHub Actions s'occupe de tout : build du backend Python, build Tauri signé, création de la release, génération du `latest.json` pour l'auto-updater.

Sur ton poste, l'app installée détecte la nouvelle release au prochain lancement et propose la mise à jour. **Aucune commande à connaître côté utilisateur.**

## Développement local (uniquement quand tu codes)

Une seule fois, à l'installation :

```powershell
npm install --legacy-peer-deps   # crée aussi le stub de sidecar dev
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Pour développer, **deux terminaux** :

```powershell
# Terminal 1 — backend FastAPI (hot reload uvicorn)
.\start_backend.ps1
```

```powershell
# Terminal 2 — fenêtre Tauri + Vite
npm run tauri:dev
```

C'est tout. Les modifs de code (Python ou Svelte) se rechargent à chaud.

## Structure

```
appli_rentree/
├── src/                       # Frontend Svelte
│   ├── App.svelte             # shell (sidebar + routing simple)
│   ├── main.js                # entrée Vite
│   ├── app.css                # Tailwind + thème
│   ├── lib/
│   │   ├── api.js             # client HTTP du backend
│   │   └── components/        # StatCard, DataTable…
│   └── routes/                # une page par grande étape
├── backend/                   # Backend FastAPI (sidecar)
│   ├── main.py                # app FastAPI + routes /api/*
│   ├── config.py              # chemins (data dir, port)
│   ├── services/
│   │   └── parser_charlemagne.py
│   ├── routers/               # endpoints REST par domaine
│   ├── models/                # tables SQLAlchemy (à venir)
│   └── schemas/               # schémas Pydantic (à venir)
├── src-tauri/                 # Coquille Tauri Rust
│   ├── tauri.conf.json        # version + bundle + updater endpoint
│   ├── Cargo.toml
│   └── src/lib.rs             # démarre le sidecar (prod uniquement)
├── data/
│   ├── input/                 # exports Charlemagne, SmartAir N-1 (gitignored)
│   └── output/                # fichiers générés (gitignored)
├── .github/workflows/
│   └── release.yml            # build + signature + release sur tag v*
├── scripts/
│   └── ensure-dev-sidecar.mjs # crée un stub vide pour `npm run tauri:dev`
├── backend.spec               # config PyInstaller (utilisée par GitHub Actions)
├── run_backend.py             # entrée PyInstaller
├── package.json               # Node/Svelte/Tauri/Tailwind
└── requirements.txt           # FastAPI/pandas/openpyxl/lxml/SQLAlchemy…
```

## Sécurité

- Aucun mot de passe en clair dans les fichiers versionnés
- Bases `.db`, fichiers `.env`, dossier `data/` : ignorés par git
- Clé de signature de mise à jour : `src-tauri/keys/` (gitignored localement) + secret GitHub `TAURI_SIGNING_PRIVATE_KEY`
