# Lance le backend FastAPI en mode dev avec hot reload.
# À lancer dans un terminal séparé de `npm run tauri:dev`.

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt | Out-Null

$env:PYTHONPATH = "."
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8020
