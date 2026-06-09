/**
 * Crée un binaire sidecar bidon à l'emplacement attendu par Tauri.
 *
 * Tauri 2 vérifie l'existence des `externalBin` au build (même en dev), donc
 * sans ce fichier, `npm run tauri:dev` échoue avant même de compiler le Rust.
 * En dev, notre code Rust (cf. src-tauri/src/lib.rs) ne tente jamais d'exécuter
 * ce sidecar — il sait qu'on lance le backend séparément en uvicorn.
 *
 * En prod (GitHub Actions), le workflow remplace ce fichier par le vrai
 * appli-rentree-backend.exe compilé par PyInstaller. Donc cette astuce n'a
 * aucun effet sur le binaire distribué.
 *
 * Ce script tourne automatiquement après `npm install` (hook postinstall).
 */
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const racine = join(__dirname, "..");
const cibleDir = join(racine, "src-tauri", "binaries");
const cible = join(cibleDir, "appli-rentree-backend-x86_64-pc-windows-msvc.exe");

if (existsSync(cible)) {
  console.log("[dev-sidecar] Stub déjà présent — rien à faire.");
  process.exit(0);
}

mkdirSync(cibleDir, { recursive: true });
writeFileSync(cible, "# Stub dev — remplacé par le vrai appli-rentree-backend.exe en CI\n");
console.log(`[dev-sidecar] Stub créé : ${cible}`);
