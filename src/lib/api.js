/**
 * Client API du backend FastAPI.
 *
 * - En dev (`npm run dev` / `tauri dev`) : `/api` relatif, Vite proxy vers 127.0.0.1:8020
 * - En prod (binaire Tauri) : URL absolue car il n'y a plus de proxy Vite
 */

const BASE = import.meta.env.PROD
  ? "http://127.0.0.1:8020/api"
  : "/api";

/**
 * Parse la réponse en JSON, ou lève une erreur lisible si le serveur renvoie
 * du HTML (signe que le backend ne tourne pas et que Tauri sert l'index.html
 * en fallback).
 */
async function jsonOrThrow(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!response.ok) {
    const corps = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status} ${response.statusText} — ${corps.slice(0, 200)}`);
  }
  if (!contentType.includes("application/json")) {
    const corps = await response.text().catch(() => "");
    throw new Error(
      `Le backend n'a pas répondu en JSON (contenu type: "${contentType}"). ` +
        `Le sidecar Python est probablement en cours de démarrage ou en erreur. ` +
        `Aperçu : ${corps.slice(0, 100)}`,
    );
  }
  return response.json();
}

/** Health check avec retry exponentiel pour attendre le démarrage du sidecar. */
export async function attendreBackend({ maxTentatives = 20, baseDelai = 250 } = {}) {
  let derniereErreur = null;
  for (let i = 0; i < maxTentatives; i++) {
    try {
      const r = await fetch(`${BASE}/health`, { cache: "no-store" });
      if (r.ok && (r.headers.get("content-type") || "").includes("application/json")) {
        return await r.json();
      }
    } catch (e) {
      derniereErreur = e;
    }
    // Backoff : 250, 500, 750, ... plafonné à 2s
    const delai = Math.min(baseDelai * (i + 1), 2000);
    await new Promise((r) => setTimeout(r, delai));
  }
  throw new Error(
    `Backend injoignable après ${maxTentatives} tentatives. ` +
      `Dernière erreur : ${derniereErreur?.message ?? "aucune réponse"}`,
  );
}

export async function health() {
  return jsonOrThrow(await fetch(`${BASE}/health`));
}

export const charlemagne = {
  async listerFichiers() {
    return jsonOrThrow(await fetch(`${BASE}/charlemagne/fichiers`));
  },

  async apercu(nom, limite = 200) {
    const params = new URLSearchParams({ nom, limite: String(limite) });
    return jsonOrThrow(await fetch(`${BASE}/charlemagne/apercu?${params}`));
  },

  async upload(fichier) {
    const form = new FormData();
    form.append("fichier", fichier);
    return jsonOrThrow(
      await fetch(`${BASE}/charlemagne/upload`, {
        method: "POST",
        body: form,
      }),
    );
  },
};
