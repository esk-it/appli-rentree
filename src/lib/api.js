/**
 * Client API du backend FastAPI.
 *
 * - En dev (`npm run dev` / `tauri dev`) : `/api` relatif, Vite proxy vers 127.0.0.1:8020
 * - En prod (binaire Tauri) : URL absolue car il n'y a plus de proxy Vite
 *
 * Depuis la refonte identité (v0.22.0), le client expose uniquement les
 * endpoints du Lot 1 : personnes, sites, table de correspondance, années,
 * établissements, paramètres. Les modules de traitement seront ajoutés lot
 * par lot.
 */

const BASE = import.meta.env.PROD ? "http://127.0.0.1:8020/api" : "/api";

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

// ---------------------------------------------------------------------------
// Personnes — référentiel d'identité
// ---------------------------------------------------------------------------
export const personnes = {
  async lister({ type = null, site = null } = {}) {
    const p = new URLSearchParams();
    if (type) p.set("type", type);
    if (site) p.set("site", site);
    const qs = p.toString();
    return jsonOrThrow(await fetch(`${BASE}/personnes${qs ? `?${qs}` : ""}`));
  },
  async obtenir(id) {
    return jsonOrThrow(await fetch(`${BASE}/personnes/${id}`));
  },
  async parClePivot(cle) {
    return jsonOrThrow(await fetch(`${BASE}/personnes/par-cle-pivot/${encodeURIComponent(cle)}`));
  },
};

// ---------------------------------------------------------------------------
// Sites
// ---------------------------------------------------------------------------
export const sites = {
  async lister() {
    return jsonOrThrow(await fetch(`${BASE}/sites`));
  },
  async creer(payload) {
    return jsonOrThrow(
      await fetch(`${BASE}/sites`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
    );
  },
  async modifier(id, payload) {
    return jsonOrThrow(
      await fetch(`${BASE}/sites/${id}`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
    );
  },
  async supprimer(id) {
    return jsonOrThrow(await fetch(`${BASE}/sites/${id}`, { method: "DELETE" }));
  },
};

// ---------------------------------------------------------------------------
// Table de correspondance classe → OU/Groupe Google
// ---------------------------------------------------------------------------
export const tableCorrespondance = {
  async lister({ site = null } = {}) {
    const p = new URLSearchParams();
    if (site) p.set("site", site);
    const qs = p.toString();
    return jsonOrThrow(await fetch(`${BASE}/table-correspondance${qs ? `?${qs}` : ""}`));
  },
  async creer(payload) {
    return jsonOrThrow(
      await fetch(`${BASE}/table-correspondance`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
    );
  },
  async modifier(id, payload) {
    return jsonOrThrow(
      await fetch(`${BASE}/table-correspondance/${id}`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
    );
  },
  async supprimer(id) {
    return jsonOrThrow(
      await fetch(`${BASE}/table-correspondance/${id}`, { method: "DELETE" }),
    );
  },
};

// ---------------------------------------------------------------------------
// Années scolaires
// ---------------------------------------------------------------------------
export const annees = {
  async lister() {
    return jsonOrThrow(await fetch(`${BASE}/annees`));
  },
  async supprimer(id) {
    return jsonOrThrow(await fetch(`${BASE}/annees/${id}`, { method: "DELETE" }));
  },
};

// ---------------------------------------------------------------------------
// Établissements (côté Charlemagne — 02-COL, 03-LY, 04-LP)
// ---------------------------------------------------------------------------
export const etablissements = {
  async lister() {
    return jsonOrThrow(await fetch(`${BASE}/etablissements`));
  },
};

// ---------------------------------------------------------------------------
// Paramètres
// ---------------------------------------------------------------------------
export const parametres = {
  async lister() {
    return jsonOrThrow(await fetch(`${BASE}/parametres`));
  },
  async mettreAJour(cle, valeur) {
    return jsonOrThrow(
      await fetch(`${BASE}/parametres/${encodeURIComponent(cle)}`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ valeur }),
      }),
    );
  },
};

// ---------------------------------------------------------------------------
// Helpers de téléchargement — utiles pour les futurs exports
// ---------------------------------------------------------------------------
export function telechargerFichier(nom, contenu, mime = "text/csv") {
  const blob = new Blob([contenu], { type: `${mime};charset=utf-8` });
  declencherDownload(nom, blob);
}

export function telechargerFichierBase64(nom, contenuBase64, mime) {
  const binaire = atob(contenuBase64);
  const octets = new Uint8Array(binaire.length);
  for (let i = 0; i < binaire.length; i++) octets[i] = binaire.charCodeAt(i);
  const blob = new Blob([octets], { type: mime ?? "application/octet-stream" });
  declencherDownload(nom, blob);
}

function declencherDownload(nom, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nom;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
