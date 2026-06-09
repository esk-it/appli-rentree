/**
 * Vérification et installation des mises à jour Tauri.
 *
 * L'app interroge le `latest.json` publié sur GitHub Releases au démarrage.
 * Si une nouvelle version est dispo et que l'utilisateur accepte, on télécharge
 * et installe en arrière-plan, puis on relance l'app.
 */
import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import { invoke } from "@tauri-apps/api/core";

/**
 * @typedef {Object} ProgressionMaj
 * @property {string} phase  - "verification" | "telechargement" | "installation" | "termine"
 * @property {number} pourcentage
 * @property {string} version - version cible (si dispo)
 */

/**
 * Vérifie s'il y a une mise à jour disponible.
 * @returns {Promise<{disponible: boolean, version?: string, update?: any}>}
 */
export async function verifierMaj() {
  try {
    const update = await check();
    if (update?.available) {
      return { disponible: true, version: update.version, update };
    }
    return { disponible: false };
  } catch (e) {
    // En dev (sans signature/endpoint), check() peut lever — on l'ignore.
    console.warn("[updater] Vérification impossible :", e);
    return { disponible: false };
  }
}

/**
 * Télécharge et installe la mise à jour, puis relance l'app.
 *
 * IMPORTANT : on tue d'abord le sidecar Python avant de lancer l'installeur,
 * sinon NSIS échoue avec "Error opening file for writing:
 * appli-rentree-backend.exe" car le processus tient le fichier ouvert.
 *
 * @param {any} update - objet retourné par check()
 * @param {(p: ProgressionMaj) => void} onProgress - callback de progression
 */
export async function installerMaj(update, onProgress) {
  let totalOctets = 0;
  let octetsRecus = 0;

  onProgress({ phase: "preparation", pourcentage: 0, version: update.version });
  // Arrête le sidecar pour libérer appli-rentree-backend.exe
  try {
    await invoke("kill_backend");
  } catch (e) {
    console.warn("[updater] kill_backend a échoué :", e);
  }
  // Laisse Windows le temps de libérer le handle de fichier
  await new Promise((r) => setTimeout(r, 600));

  await update.downloadAndInstall((event) => {
    if (event.event === "Started") {
      totalOctets = event.data.contentLength ?? 0;
      onProgress({
        phase: "telechargement",
        pourcentage: 0,
        version: update.version,
      });
    } else if (event.event === "Progress") {
      octetsRecus += event.data.chunkLength;
      const p = totalOctets > 0 ? Math.round((octetsRecus / totalOctets) * 100) : 0;
      onProgress({
        phase: "telechargement",
        pourcentage: p,
        version: update.version,
      });
    } else if (event.event === "Finished") {
      onProgress({
        phase: "installation",
        pourcentage: 100,
        version: update.version,
      });
    }
  });

  onProgress({ phase: "termine", pourcentage: 100, version: update.version });
  // Relance après installation pour appliquer la nouvelle version
  await relaunch();
}
