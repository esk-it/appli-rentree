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

  /**
   * Ingère un fichier déjà déposé dans data/input/ comme nouveau snapshot.
   * @param {string} nomFichier
   * @param {string} libelleAnnee  ex. "2025-2026"
   * @param {boolean} [remplacerSiExiste=false]
   */
  async ingerer(nomFichier, libelleAnnee, remplacerSiExiste = false) {
    return jsonOrThrow(
      await fetch(`${BASE}/charlemagne/ingerer`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          nom_fichier: nomFichier,
          libelle_annee: libelleAnnee,
          remplacer_si_existe: remplacerSiExiste,
        }),
      }),
    );
  },
};

export const annees = {
  async lister() {
    return jsonOrThrow(await fetch(`${BASE}/annees`));
  },

  async supprimer(id) {
    return jsonOrThrow(await fetch(`${BASE}/annees/${id}`, { method: "DELETE" }));
  },
};

export const eleves = {
  async lister(libelleAnnee) {
    const params = new URLSearchParams({ annee: libelleAnnee });
    return jsonOrThrow(await fetch(`${BASE}/eleves?${params}`));
  },
};

export const chambres = {
  async lister(libelleAnnee = null) {
    const params = new URLSearchParams();
    if (libelleAnnee) params.set("annee", libelleAnnee);
    return jsonOrThrow(await fetch(`${BASE}/chambres?${params}`));
  },
  async creer(payload) {
    return jsonOrThrow(
      await fetch(`${BASE}/chambres`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
    );
  },
  async modifier(id, payload) {
    return jsonOrThrow(
      await fetch(`${BASE}/chambres/${id}`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
    );
  },
  async supprimer(id) {
    return jsonOrThrow(
      await fetch(`${BASE}/chambres/${id}`, { method: "DELETE" }),
    );
  },
  async affecter(eleveSnapshotId, chambreId) {
    return jsonOrThrow(
      await fetch(`${BASE}/chambres/affectations`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          eleve_snapshot_id: eleveSnapshotId,
          chambre_id: chambreId,
        }),
      }),
    );
  },
  async listerAffectations(libelleAnnee) {
    const params = new URLSearchParams({ annee: libelleAnnee });
    return jsonOrThrow(
      await fetch(`${BASE}/chambres/affectations?${params}`),
    );
  },
};

export const historique = {
  async lister(limite = 100, cible = null) {
    const params = new URLSearchParams({ limite: String(limite) });
    if (cible) params.set("cible", cible);
    return jsonOrThrow(await fetch(`${BASE}/historique?${params}`));
  },
  async supprimer(id) {
    return jsonOrThrow(
      await fetch(`${BASE}/historique/${id}`, { method: "DELETE" }),
    );
  },
};

export const recherche = {
  async rechercher(terme, limite = 30) {
    const params = new URLSearchParams({ q: terme, limite: String(limite) });
    return jsonOrThrow(await fetch(`${BASE}/recherche?${params}`));
  },
};

export const adultes = {
  async lister(libelleAnnee) {
    const params = new URLSearchParams({ annee: libelleAnnee });
    return jsonOrThrow(await fetch(`${BASE}/adultes?${params}`));
  },
  async ingerer(nomFichier, libelleAnnee, remplacerSiExiste = false) {
    return jsonOrThrow(
      await fetch(`${BASE}/adultes/ingerer`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          nom_fichier: nomFichier,
          libelle_annee: libelleAnnee,
          remplacer_si_existe: remplacerSiExiste,
        }),
      }),
    );
  },
};

export const etablissements = {
  async lister() {
    return jsonOrThrow(await fetch(`${BASE}/etablissements`));
  },
};

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

export const statistiques = {
  async annee(libelleAnnee) {
    const params = new URLSearchParams({ annee: libelleAnnee });
    return jsonOrThrow(await fetch(`${BASE}/statistiques?${params}`));
  },
};

export const comparaison = {
  /**
   * Compare deux snapshots et renvoie entrants/restants/sortants.
   * @param {string} anneeN  ex. "2026-2027"
   * @param {string} anneeNMoinsUn  ex. "2025-2026"
   */
  async comparer(anneeN, anneeNMoinsUn) {
    const params = new URLSearchParams({
      annee_n: anneeN,
      annee_n_minus_1: anneeNMoinsUn,
    });
    return jsonOrThrow(await fetch(`${BASE}/comparaison?${params}`));
  },
};

export const exports = {
  /**
   * Génère les CSV KoXo pour l'année N (et N-1 optionnellement).
   * @param {string} anneeN
   * @param {string|null} anneeNMoinsUn
   */
  async koxo(anneeN, anneeNMoinsUn = null) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/koxo`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          annee_n: anneeN,
          annee_n_minus_1: anneeNMoinsUn,
        }),
      }),
    );
  },

  /**
   * Génère les CSV PMB pour l'année N (un par instance PMB : SU et NDK).
   * @param {string} anneeN
   */
  async pmb(anneeN) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/pmb`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ annee_n: anneeN }),
      }),
    );
  },

  /**
   * Génère les XLSX CardStudio pour l'année N (un par groupe).
   * Les contenus sont en base64 dans la réponse.
   * @param {string} anneeN
   */
  async cardstudio(anneeN) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/cardstudio`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ annee_n: anneeN }),
      }),
    );
  },

  /**
   * Génère le CSV SmartAir pour l'année N.
   * @param {string} anneeN
   * @param {string|null} contenuSmartairNMoinsUn  Contenu CSV d'un précédent export SmartAir (optionnel)
   */
  async smartair(anneeN, contenuSmartairNMoinsUn = null) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/smartair`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          annee_n: anneeN,
          contenu_smartair_n_minus_1: contenuSmartairNMoinsUn,
        }),
      }),
    );
  },

  /**
   * Génère les CSV Google Workspace bulk-import pour l'année N.
   * @param {string} anneeN
   * @param {string|null} anneeNMoinsUn  Si fourni, génère aussi "Nouveaux".
   */
  async google(anneeN, anneeNMoinsUn = null) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/google`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          annee_n: anneeN,
          annee_n_minus_1: anneeNMoinsUn,
        }),
      }),
    );
  },

  async koxoAdultes(anneeN, anneeNMoinsUn = null) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/koxo-adultes`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          annee_n: anneeN,
          annee_n_minus_1: anneeNMoinsUn,
        }),
      }),
    );
  },

  async googleAdultes(anneeN, anneeNMoinsUn = null) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/google-adultes`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          annee_n: anneeN,
          annee_n_minus_1: anneeNMoinsUn,
        }),
      }),
    );
  },

  /**
   * Lance tous les générateurs et retourne un ZIP unique organisé par cible.
   * @param {string} anneeN
   * @param {string|null} anneeNMoinsUn
   * @param {string|null} contenuSmartairNMoinsUn
   */
  async tout(anneeN, anneeNMoinsUn = null, contenuSmartairNMoinsUn = null) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/tout`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          annee_n: anneeN,
          annee_n_minus_1: anneeNMoinsUn,
          contenu_smartair_n_minus_1: contenuSmartairNMoinsUn,
        }),
      }),
    );
  },
};

/**
 * Déclenche le téléchargement d'un fichier texte côté navigateur.
 * @param {string} nom
 * @param {string} contenu
 * @param {string} [mime]
 */
export function telechargerFichier(nom, contenu, mime = "text/csv") {
  const blob = new Blob([contenu], { type: `${mime};charset=utf-8` });
  declencherDownload(nom, blob);
}

/**
 * Déclenche le téléchargement d'un fichier binaire à partir d'un base64.
 * @param {string} nom
 * @param {string} contenuBase64
 * @param {string} [mime]
 */
export function telechargerFichierBase64(nom, contenuBase64, mime) {
  const binaire = atob(contenuBase64);
  const octets = new Uint8Array(binaire.length);
  for (let i = 0; i < binaire.length; i++) octets[i] = binaire.charCodeAt(i);
  const blob = new Blob([octets], {
    type: mime ?? "application/octet-stream",
  });
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
