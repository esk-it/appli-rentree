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
  /** Fige l'adresse mail. `""` rétablit l'adresse calculée. */
  async definirEmail(id, email) {
    return jsonOrThrow(
      await fetch(`${BASE}/personnes/${id}/email`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      }),
    );
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
  /** Bascule l'année dans les chemins d'OU (2026 → 2027). Simulation par défaut. */
  async rotationOu({ chercher, remplacer, siteId = null, mode = "simulation" }) {
    return jsonOrThrow(
      await fetch(`${BASE}/table-correspondance/rotation-ou`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ chercher, remplacer, site_id: siteId, mode }),
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
  async purger({ compteIds = null, cible = null }) {
    return jsonOrThrow(
      await fetch(`${BASE}/suivi/purger`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          compte_ids: compteIds, cible, confirmation: true,
        }),
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
// Mode API Google Workspace (optionnel)
// ---------------------------------------------------------------------------
export const googleApi = {
  async statut() {
    return jsonOrThrow(await fetch(`${BASE}/google/statut`));
  },
  async testerConnexion() {
    return jsonOrThrow(await fetch(`${BASE}/google/tester-connexion`, { method: "POST" }));
  },
  async plan({ siteId, typePersonne, anneeCibleId, anneeSourceId, csvKoxoBase64 = null, phase = "pre_rentree" }) {
    return jsonOrThrow(
      await fetch(`${BASE}/google/plan`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          site_id: siteId, type_personne: typePersonne,
          annee_cible_id: anneeCibleId, annee_source_id: anneeSourceId,
          csv_koxo_base64: csvKoxoBase64, phase,
        }),
      }),
    );
  },
  /** Lance l'exécution suivie ; retourne le job à interroger ensuite. */
  async lancerJob({ siteId, typePersonne, anneeCibleId, anneeSourceId, csvKoxoBase64 = null, phase = "pre_rentree" }) {
    return jsonOrThrow(
      await fetch(`${BASE}/google/jobs`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          site_id: siteId, type_personne: typePersonne,
          annee_cible_id: anneeCibleId, annee_source_id: anneeSourceId,
          csv_koxo_base64: csvKoxoBase64, phase, confirmation: true,
        }),
      }),
    );
  },
  /** Liste les comptes présents sous une branche d'OU, avec leur identité. */
  async inspecterOu(ou) {
    return jsonOrThrow(
      await fetch(`${BASE}/google/inspecter-ou?ou=${encodeURIComponent(ou)}`),
    );
  },
  /** Ce que la vidange ferait — n'envoie rien. */
  async planVidange({ ou, anneeDepart = null, ouArchivage = null, suspendre = false }) {
    const p = new URLSearchParams({ ou });
    if (anneeDepart) p.set("annee_depart", String(anneeDepart));
    if (ouArchivage) p.set("ou_archivage", ouArchivage);
    if (suspendre) p.set("suspendre", "true");
    return jsonOrThrow(await fetch(`${BASE}/google/vidange-ou/plan?${p}`));
  },
  /** Suspend et archive les comptes de la branche. Retourne un job. */
  async lancerVidange({ ou, anneeDepart = null, ouArchivage = null, suspendre = false }) {
    return jsonOrThrow(
      await fetch(`${BASE}/google/vidange-ou`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          ou, annee_depart: anneeDepart, ou_archivage: ouArchivage,
          suspendre, creer_destination: true, confirmation: true,
        }),
      }),
    );
  },
  // --- Mise en conformité de Google -------------------------------------
  /** Écart entre l'arborescence réelle et ce que vise la Table. */
  async conformiteOu({ anneeSource = null, anneeCible = null, renommer = true }) {
    const q = new URLSearchParams();
    if (anneeSource) q.set("annee_source", anneeSource);
    if (anneeCible) q.set("annee_cible", anneeCible);
    if (!renommer) q.set("renommer", "false");
    return jsonOrThrow(await fetch(`${BASE}/google/ou/conformite?${q}`));
  },
  async appliquerOu({ anneeSource = null, anneeCible = null, renommer = true }) {
    return jsonOrThrow(
      await fetch(`${BASE}/google/ou/appliquer`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          annee_source: anneeSource, annee_cible: anneeCible,
          renommer, confirmation: true,
        }),
      }),
    );
  },
  /** Personnes dont l'adresse enregistrée n'existe pas dans Google. */
  async divergences({ anneeId = null } = {}) {
    const q = anneeId ? `?annee_id=${anneeId}` : "";
    return jsonOrThrow(await fetch(`${BASE}/google/adresses/divergences${q}`));
  },
  async corrigerAdresses({ anneeId = null, mode = "simulation" }) {
    return jsonOrThrow(
      await fetch(`${BASE}/google/adresses/corriger`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ annee_id: anneeId, mode }),
      }),
    );
  },
  /** Qui doit entrer et sortir de chaque groupe de classe. */
  async diffGroupes({ anneeId, siteId = null }) {
    const q = new URLSearchParams({ annee_id: String(anneeId) });
    if (siteId) q.set("site_id", String(siteId));
    return jsonOrThrow(await fetch(`${BASE}/google/groupes/diff?${q}`));
  },
  /** Groupes déclarés dans la Table que Google ne connaît pas. */
  async groupesACreer({ anneeId, siteId = null }) {
    const q = new URLSearchParams({ annee_id: String(anneeId) });
    if (siteId) q.set("site_id", String(siteId));
    return jsonOrThrow(await fetch(`${BASE}/google/groupes/a-creer?${q}`));
  },
  async creerGroupes({ anneeId, siteId = null, adresses = null, seulementUtiles = false }) {
    return jsonOrThrow(
      await fetch(`${BASE}/google/groupes/creer`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          annee_id: anneeId, site_id: siteId, adresses,
          seulement_utiles: seulementUtiles, confirmation: true,
        }),
      }),
    );
  },
  async synchroniserGroupes({ anneeId, siteId = null, retirer = true }) {
    return jsonOrThrow(
      await fetch(`${BASE}/google/groupes/synchroniser`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          annee_id: anneeId, site_id: siteId, retirer, confirmation: true,
        }),
      }),
    );
  },
  /** Les OU de sortie existantes, avec leurs échéances et leur état. */
  async destinationsSortie({ pourOu = null } = {}) {
    const q = new URLSearchParams();
    if (pourOu) q.set("pour_ou", pourOu);
    return jsonOrThrow(await fetch(`${BASE}/google/sortie/destinations?${q}`));
  },
  /** Qui occupe une OU de sortie, lu dans Google. Sert à prévenir avant purge. */
  async occupantsSortie({ ou }) {
    const q = new URLSearchParams({ ou });
    return jsonOrThrow(await fetch(`${BASE}/google/sortie/occupants?${q}`));
  },
  async suivreJob(jobId) {
    return jsonOrThrow(await fetch(`${BASE}/google/jobs/${jobId}`));
  },
  async annulerJob(jobId) {
    return jsonOrThrow(await fetch(`${BASE}/google/jobs/${jobId}/annuler`, { method: "POST" }));
  },
  async rejouerEchecs(jobId) {
    return jsonOrThrow(
      await fetch(`${BASE}/google/jobs/${jobId}/rejouer-echecs`, { method: "POST" }),
    );
  },
  async executer({ siteId, typePersonne, anneeCibleId, anneeSourceId, csvKoxoBase64 = null, phase = "pre_rentree" }) {
    return jsonOrThrow(
      await fetch(`${BASE}/google/executer`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          site_id: siteId, type_personne: typePersonne,
          annee_cible_id: anneeCibleId, annee_source_id: anneeSourceId,
          csv_koxo_base64: csvKoxoBase64, phase,
          confirmation: true,
        }),
      }),
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
// ---------------------------------------------------------------------------
// Nouveaux arrivants — liste de relecture humaine (≠ exports vers les cibles)
// ---------------------------------------------------------------------------
export const nouveaux = {
  _qs({ anneeId, siteId = null, type = null, anneeSourceId = null, inclureAVerifier = true }) {
    const p = new URLSearchParams({ annee_id: String(anneeId) });
    if (siteId) p.set("site_id", String(siteId));
    if (type) p.set("type", type);
    if (anneeSourceId) p.set("annee_source_id", String(anneeSourceId));
    if (!inclureAVerifier) p.set("inclure_a_verifier", "false");
    return p.toString();
  },
  async lister(options) {
    return jsonOrThrow(await fetch(`${BASE}/nouveaux?${nouveaux._qs(options)}`));
  },
  async csv(options) {
    return jsonOrThrow(await fetch(`${BASE}/nouveaux/csv?${nouveaux._qs(options)}`));
  },
};

// ---------------------------------------------------------------------------
// Bascule des OU Google (pré-rentrée → définitive)
// ---------------------------------------------------------------------------
export const bascule = {
  _qs({ anneeId, phase, siteId = null }) {
    const p = new URLSearchParams({ annee_id: String(anneeId), phase });
    if (siteId) p.set("site_id", String(siteId));
    return p.toString();
  },
  async planifier(options) {
    return jsonOrThrow(await fetch(`${BASE}/bascule?${bascule._qs(options)}`));
  },
  async csv(options) {
    return jsonOrThrow(await fetch(`${BASE}/bascule/csv?${bascule._qs(options)}`));
  },
  /** Lit l'OU actuelle de chaque élève dans Google. Retourne un job. */
  async relever({ anneeId, siteId = null }) {
    const p = new URLSearchParams({ annee_id: String(anneeId) });
    if (siteId) p.set("site_id", String(siteId));
    return jsonOrThrow(
      await fetch(`${BASE}/bascule/relever?${p}`, { method: "POST" }),
    );
  },
  async confirmer({ anneeId, phase, siteId = null, mode = "simulation" }) {
    return jsonOrThrow(
      await fetch(`${BASE}/bascule/confirmer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          annee_id: anneeId,
          phase,
          site_id: siteId || null,
          mode,
        }),
      }),
    );
  },
};

// ---------------------------------------------------------------------------
// Sortants — où ils devraient être, où ils sont vraiment
// ---------------------------------------------------------------------------
export const sortants = {
  async lister({ siteId = null, seulementEchus = false } = {}) {
    const p = new URLSearchParams();
    if (siteId) p.set("site_id", String(siteId));
    if (seulementEchus) p.set("seulement_echus", "true");
    const qs = p.toString();
    return jsonOrThrow(await fetch(`${BASE}/sortants${qs ? `?${qs}` : ""}`));
  },
  /** Confronte chaque compte à Google. Ne modifie rien — retourne un job. */
  async verifier({ siteId = null } = {}) {
    const qs = siteId ? `?site_id=${siteId}` : "";
    return jsonOrThrow(
      await fetch(`${BASE}/sortants/verifier${qs}`, { method: "POST" }),
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
// Enregistrement de fichiers
// ---------------------------------------------------------------------------
//
// Dans l'application packagée, un simple lien `download` fait déposer le
// fichier par WebView2 dans le dossier Téléchargements, sans rien demander :
// l'utilisateur ne sait pas où son export a atterri. On passe donc par la
// boîte d'enregistrement de Tauri, qui laisse choisir l'emplacement et
// retourne le chemin exact — affichable ensuite dans une notification.
//
// Le navigateur reste utilisé en dev, et en secours si l'écriture est
// refusée (dossier hors du périmètre autorisé).

function estDansTauri() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function base64EnOctets(contenuBase64) {
  const binaire = atob(contenuBase64);
  const octets = new Uint8Array(binaire.length);
  for (let i = 0; i < binaire.length; i++) octets[i] = binaire.charCodeAt(i);
  return octets;
}

/**
 * Propose d'enregistrer un fichier et retourne où il a été écrit.
 *
 * @returns {Promise<{chemin: string|null, annule: boolean}>}
 *   `chemin` vaut `null` quand le navigateur a pris le relais (dossier de
 *   téléchargement par défaut) ; `annule` est vrai si l'utilisateur a fermé
 *   la boîte de dialogue.
 */
export async function enregistrerFichierBase64(nom, contenuBase64, mime) {
  const octets = base64EnOctets(contenuBase64);

  if (estDansTauri()) {
    try {
      const { save } = await import("@tauri-apps/plugin-dialog");
      const extension = nom.split(".").pop() ?? "";
      const chemin = await save({
        defaultPath: nom,
        filters: extension ? [{ name: extension.toUpperCase(), extensions: [extension] }] : [],
      });
      if (chemin === null) return { chemin: null, annule: true };

      const { writeFile } = await import("@tauri-apps/plugin-fs");
      await writeFile(chemin, octets);
      return { chemin, annule: false };
    } catch (e) {
      // Écriture refusée (hors périmètre) ou plugin indisponible : plutôt que
      // de perdre l'export, on retombe sur le téléchargement navigateur.
      console.warn("Enregistrement Tauri impossible, repli navigateur :", e);
    }
  }

  declencherDownload(nom, new Blob([octets], { type: mime ?? "application/octet-stream" }));
  return { chemin: null, annule: false };
}

export function telechargerFichier(nom, contenu, mime = "text/csv") {
  const blob = new Blob([contenu], { type: `${mime};charset=utf-8` });
  declencherDownload(nom, blob);
}

/** @deprecated Préférer `enregistrerFichierBase64`, qui dit où le fichier va. */
export function telechargerFichierBase64(nom, contenuBase64, mime) {
  const blob = new Blob([base64EnOctets(contenuBase64)], {
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
