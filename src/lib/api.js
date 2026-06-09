/**
 * Client API du backend FastAPI.
 * En dev, Vite proxy /api → http://127.0.0.1:8020.
 * En prod (Tauri), le backend tourne en sidecar local sur le même port.
 */

const BASE = "/api";

async function jsonOrThrow(response) {
  if (!response.ok) {
    const erreur = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status} ${response.statusText} — ${erreur}`);
  }
  return response.json();
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
