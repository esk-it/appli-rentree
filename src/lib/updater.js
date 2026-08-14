/**
 * Vérification et installation des mises à jour Tauri.
 *
 * L'app interroge le `latest.json` publié sur GitHub Releases au démarrage.
 * Si une nouvelle version est dispo et que l'utilisateur accepte, on télécharge
 * et installe en arrière-plan, puis on relance l'app.
 *
 * ## Pourquoi l'erreur est remontée et non avalée
 *
 * Une version antérieure se contentait d'un `console.warn` en cas d'échec.
 * La console n'étant pas accessible dans l'app packagée, un échec de
 * vérification (réseau, proxy d'établissement, GitHub injoignable, signature
 * invalide) se traduisait par... rien du tout. L'utilisateur constatait
 * l'absence de mise à jour sans pouvoir en connaître la cause.
 *
 * `verifierMaj()` retourne désormais le détail de l'échec, que l'interface
 * affiche et que le backend journalise dans `backend.log`.
 */
import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import { invoke } from "@tauri-apps/api/core";

const BASE = import.meta.env.PROD ? "http://127.0.0.1:8020/api" : "/api";

/**
 * @typedef {Object} ProgressionMaj
 * @property {string} phase  - "verification" | "telechargement" | "installation" | "termine"
 * @property {number} pourcentage
 * @property {string} version - version cible (si dispo)
 */

/**
 * @typedef {Object} ResultatVerification
 * @property {boolean} disponible
 * @property {string} [version]
 * @property {any} [update]
 * @property {string} [erreur]        - message lisible si la vérification a échoué
 * @property {boolean} [aEchoue]      - distingue « pas de maj » de « vérification impossible »
 */

/**
 * Envoie une trace au backend pour qu'elle atterrisse dans backend.log.
 *
 * Best-effort : si le backend ne répond pas, on n'aggrave pas la situation.
 */
async function tracerBackend(message) {
  try {
    await fetch(`${BASE}/trace-frontend`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ source: "updater", message }),
    });
  } catch {
    // Le backend est peut-être en train de démarrer — sans conséquence.
  }
}

/**
 * Vrai si l'on tourne dans le shell Tauri, faux dans un navigateur.
 *
 * Sert à ne pas signaler un « échec de mise à jour » quand on développe
 * avec `npm run dev` : hors Tauri, `check()` lève forcément, et afficher
 * une bannière d'erreur permanente serait du bruit trompeur.
 */
function dansTauri() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/**
 * Vérifie s'il y a une mise à jour disponible.
 * @returns {Promise<ResultatVerification>}
 */
export async function verifierMaj() {
  if (!dansTauri()) {
    return { disponible: false, aEchoue: false };
  }
  try {
    const update = await check();
    if (update?.available) {
      return { disponible: true, version: update.version, update };
    }
    return { disponible: false, aEchoue: false };
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.warn("[updater] Vérification impossible :", e);
    tracerBackend(`Vérification de mise à jour impossible : ${message}`);
    return { disponible: false, aEchoue: true, erreur: message };
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
  // Arrête le sidecar pour libérer appli-rentree-backend.exe.
  // Côté Rust, kill_backend fait taskkill + polling tasklist jusqu'à
  // confirmation que le process est mort + délai pour libérer le file handle.
  // Donc quand `invoke` retourne, on est sûrs que NSIS pourra écrire.
  try {
    await invoke("kill_backend");
  } catch (e) {
    // Le Rust nous remonte une erreur si le sidecar refuse de mourir en 3s.
    // On stoppe la maj plutôt que de tenter un install qui va planter.
    throw new Error(
      `Impossible d'arrêter le backend pour la mise à jour : ${e}`,
    );
  }

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
