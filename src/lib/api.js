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
  async importerXlsx({ fichier, mode = "simulation", nomOnglet = null }) {
    const form = new FormData();
    form.append("fichier", fichier);
    form.append("mode", mode);
    if (nomOnglet) form.append("nom_onglet", nomOnglet);
    return jsonOrThrow(
      await fetch(`${BASE}/table-correspondance/import`, {
        method: "POST",
        body: form,
      }),
    );
  },
  async apercuXlsx({ fichier }) {
    const form = new FormData();
    form.append("fichier", fichier);
    return jsonOrThrow(
      await fetch(`${BASE}/table-correspondance/import/apercu`, {
        method: "POST",
        body: form,
      }),
    );
  },
};

// ---------------------------------------------------------------------------
// Ingestion Charlemagne
// ---------------------------------------------------------------------------

/** Encode un ArrayBuffer en base64 en évitant l'overflow de String.fromCharCode(...). */
function arrayBufferEnBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(
      null,
      /** @type {any} */ (bytes.subarray(i, i + chunk)),
    );
  }
  return btoa(binary);
}

export const ingestion = {
  async fichiersDispo() {
    return jsonOrThrow(await fetch(`${BASE}/ingestion/fichiers-dispo`));
  },
  /**
   * Ingère un export (élèves ou adultes) en mode simulation ou réel.
   *
   * Utilise l'endpoint `/ingestion/base64` (JSON) — le multipart natif du
   * webview Tauri échoue silencieusement sur certains fichiers .htm
   * (« TypeError: failed to fetch »). Encoder en base64 dans le JSON
   * contourne le problème et fonctionne aussi bien en dev qu'en prod.
   */
  async ingerer({ fichier, libelleAnnee, typePersonne = "auto", mode = "simulation" }) {
    if (!fichier) throw new Error("Aucun fichier fourni à l'ingestion");
    const buffer = await fichier.arrayBuffer();
    const fichier_base64 = arrayBufferEnBase64(buffer);
    return jsonOrThrow(
      await fetch(`${BASE}/ingestion/base64`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          fichier_base64,
          nom_fichier: fichier.name,
          libelle_annee: libelleAnnee,
          type_personne: typePersonne,
          mode,
        }),
      }),
    );
  },
};

// ---------------------------------------------------------------------------
// Réconciliation — comparaison de deux années
// ---------------------------------------------------------------------------
export const reconciliation = {
  async obtenir({ anneeSourceId, anneeCibleId, typePersonne = null } = {}) {
    const p = new URLSearchParams();
    p.set("annee_source_id", String(anneeSourceId));
    p.set("annee_cible_id", String(anneeCibleId));
    if (typePersonne) p.set("type_personne", typePersonne);
    return jsonOrThrow(await fetch(`${BASE}/reconciliation?${p.toString()}`));
  },
};

// ---------------------------------------------------------------------------
// Suivi (Lot 12) — cycle de vie des CompteCible
// ---------------------------------------------------------------------------
export const suivi = {
  async stats() {
    return jsonOrThrow(await fetch(`${BASE}/suivi/stats`));
  },
  async lister({ etat, cible = null }) {
    const p = new URLSearchParams();
    p.set("etat", etat);
    if (cible) p.set("cible", cible);
    return jsonOrThrow(await fetch(`${BASE}/suivi/liste?${p.toString()}`));
  },
  async purgesEchues() {
    return jsonOrThrow(await fetch(`${BASE}/suivi/purges-echues`));
  },
  async marquerSortant({ personneId, cible }) {
    return jsonOrThrow(
      await fetch(`${BASE}/suivi/marquer-sortant`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ personne_id: personneId, cible }),
      }),
    );
  },
  async confirmerCreation({ cible, siteId = null }) {
    return jsonOrThrow(
      await fetch(`${BASE}/suivi/confirmer-creation`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ cible, site_id: siteId }),
      }),
    );
  },
  async activer({ cible, siteId = null }) {
    return jsonOrThrow(
      await fetch(`${BASE}/suivi/activer`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ cible, site_id: siteId }),
      }),
    );
  },
  async traiterSortants({ anneeSourceId, anneeCibleId }) {
    return jsonOrThrow(
      await fetch(`${BASE}/suivi/traiter-sortants`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          annee_source_id: anneeSourceId, annee_cible_id: anneeCibleId,
        }),
      }),
    );
  },
};

// ---------------------------------------------------------------------------
// Statistiques (Lot 13)
// ---------------------------------------------------------------------------
export const statistiques = {
  async referentiel() {
    return jsonOrThrow(await fetch(`${BASE}/statistiques/referentiel`));
  },
  async annee(anneeId) {
    return jsonOrThrow(await fetch(`${BASE}/statistiques/annee/${anneeId}`));
  },
  async anomalies({ anneeId = null, verifierPhotos = false } = {}) {
    const p = new URLSearchParams();
    if (anneeId) p.set("annee_id", String(anneeId));
    if (verifierPhotos) p.set("verifier_photos", "true");
    const qs = p.toString();
    return jsonOrThrow(
      await fetch(`${BASE}/statistiques/anomalies${qs ? `?${qs}` : ""}`),
    );
  },
};

// ---------------------------------------------------------------------------
// Journal des opérations
// ---------------------------------------------------------------------------
export const journal = {
  async lister({ typeOperation = null, cible = null, anneeLibelle = null, limite = 100 } = {}) {
    const p = new URLSearchParams();
    if (typeOperation) p.set("type_operation", typeOperation);
    if (cible) p.set("cible", cible);
    if (anneeLibelle) p.set("annee_libelle", anneeLibelle);
    p.set("limite", String(limite));
    return jsonOrThrow(await fetch(`${BASE}/journal?${p.toString()}`));
  },
  async comparaison(generationId) {
    return jsonOrThrow(await fetch(`${BASE}/journal/${generationId}/comparaison`));
  },
};

// ---------------------------------------------------------------------------
// Simulation transverse (Lot 7)
// ---------------------------------------------------------------------------
export const simulation = {
  async obtenir({ anneeSourceId, anneeCibleId }) {
    const p = new URLSearchParams();
    p.set("annee_source_id", String(anneeSourceId));
    p.set("annee_cible_id", String(anneeCibleId));
    return jsonOrThrow(await fetch(`${BASE}/simulation?${p.toString()}`));
  },
  async exporter({ anneeSourceId, anneeCibleId, format = "texte" }) {
    const p = new URLSearchParams();
    p.set("annee_source_id", String(anneeSourceId));
    p.set("annee_cible_id", String(anneeCibleId));
    p.set("format", format);
    return jsonOrThrow(await fetch(`${BASE}/simulation/export?${p.toString()}`));
  },
};

// ---------------------------------------------------------------------------
// Exports vers les cibles (KoXo, Google, PMB, JPM…)
// ---------------------------------------------------------------------------
export const exportsCible = {
  async koxo({ siteId, typePersonne, categorie, anneeCibleId, anneeSourceId = null, enregistrerPrevus = false }) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/koxo`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          site_id: siteId,
          type_personne: typePersonne,
          categorie,
          annee_cible_id: anneeCibleId,
          annee_source_id: anneeSourceId,
          enregistrer_prevus: enregistrerPrevus,
        }),
      }),
    );
  },
  async google({ siteId, typePersonne, categorie, anneeCibleId, anneeSourceId = null, enregistrerPrevus = false }) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/google`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          site_id: siteId,
          type_personne: typePersonne,
          categorie,
          annee_cible_id: anneeCibleId,
          annee_source_id: anneeSourceId,
          enregistrer_prevus: enregistrerPrevus,
        }),
      }),
    );
  },
  async googleAvecMdp({ fichierKoxo, siteId, typePersonne, categorie, anneeCibleId, anneeSourceId = null }) {
    if (!fichierKoxo) throw new Error("Fichier KoXo enrichi requis");
    const buffer = await fichierKoxo.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, /** @type {any} */ (bytes.subarray(i, i + chunk)));
    }
    const csv_koxo_base64 = btoa(binary);
    return jsonOrThrow(
      await fetch(`${BASE}/exports/google-avec-mdp`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          csv_koxo_base64,
          site_id: siteId,
          type_personne: typePersonne,
          categorie,
          annee_cible_id: anneeCibleId,
          annee_source_id: anneeSourceId,
        }),
      }),
    );
  },
  async googleGroupes({ siteId, anneeId, inclureEleves = true, inclureProfs = true }) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/google-groupes`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          site_id: siteId, annee_id: anneeId,
          inclure_eleves: inclureEleves, inclure_profs: inclureProfs,
        }),
      }),
    );
  },
  async pmb({ siteId, typePersonne, categorie, anneeCibleId, anneeSourceId = null, enregistrerPrevus = false }) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/pmb`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          site_id: siteId, type_personne: typePersonne, categorie,
          annee_cible_id: anneeCibleId, annee_source_id: anneeSourceId,
          enregistrer_prevus: enregistrerPrevus,
        }),
      }),
    );
  },
  async jpm({ siteId, anneeCibleId, anneeSourceId, enregistrerPrevus = false }) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/jpm`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          site_id: siteId, annee_cible_id: anneeCibleId, annee_source_id: anneeSourceId,
          enregistrer_prevus: enregistrerPrevus,
        }),
      }),
    );
  },
  async cardstudio({ siteId, categorie, anneeCibleId, anneeSourceId = null, enregistrerPrevus = false }) {
    return jsonOrThrow(
      await fetch(`${BASE}/exports/cardstudio`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          site_id: siteId, categorie,
          annee_cible_id: anneeCibleId, annee_source_id: anneeSourceId,
          enregistrer_prevus: enregistrerPrevus,
        }),
      }),
    );
  },
};

// ---------------------------------------------------------------------------
// Amorçage — chargement des Personnes depuis KoXo
// ---------------------------------------------------------------------------
export const amorcage = {
  async koxo({ fichier, siteId, typePersonne, mode = "simulation" }) {
    if (!fichier) throw new Error("Aucun fichier fourni à l'amorçage");
    const buffer = await fichier.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, /** @type {any} */ (bytes.subarray(i, i + chunk)));
    }
    const fichier_base64 = btoa(binary);
    return jsonOrThrow(
      await fetch(`${BASE}/amorcage/koxo`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          fichier_base64,
          nom_fichier: fichier.name,
          site_id: siteId,
          type_personne: typePersonne,
          mode,
        }),
      }),
    );
  },
};

// ---------------------------------------------------------------------------
// Arbitrages — cas ambigus et décisions humaines
// ---------------------------------------------------------------------------
export const arbitrages = {
  async enAttente() {
    return jsonOrThrow(await fetch(`${BASE}/arbitrages/en-attente`));
  },
  async lister({ typeCas = null } = {}) {
    const p = new URLSearchParams();
    if (typeCas) p.set("type_cas", typeCas);
    const qs = p.toString();
    return jsonOrThrow(await fetch(`${BASE}/arbitrages${qs ? `?${qs}` : ""}`));
  },
  async trancher(id, { decision, note = null }) {
    return jsonOrThrow(
      await fetch(`${BASE}/arbitrages/${id}/trancher`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ decision, note }),
      }),
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
