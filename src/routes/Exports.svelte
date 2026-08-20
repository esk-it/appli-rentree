<script>
  import { onMount } from "svelte";
  import Download from "@lucide/svelte/icons/download";
  import FileDown from "@lucide/svelte/icons/file-down";
  import Upload from "@lucide/svelte/icons/upload";
  import Info from "@lucide/svelte/icons/info";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import Cloud from "@lucide/svelte/icons/cloud";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Bouton from "$lib/components/Bouton.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import {
    annees,
    exportsCible,
    googleApi,
    sites as sitesApi,
    enregistrerFichierBase64,
  } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let listeSites = $state([]);
  let listeAnnees = $state([]);

  let cible = $state(
    /** @type {"koxo"|"google"|"groupes"|"pmb"|"jpm"|"cardstudio"} */ ("koxo"),
  );

  // Groupes Google : quelles familles inclure
  let inclureEleves = $state(true);
  let inclureProfs = $state(true);
  let siteId = $state(/** @type {null | number} */ (null));
  let typePersonne = $state(/** @type {"eleve"|"adulte"} */ ("eleve"));
  let categorie = $state(/** @type {"tous"|"nouveaux"|"anciens"} */ ("tous"));
  // Phase visée par le plan API — même découpage que l'onglet Bascule des OU.
  let phaseApi = $state(/** @type {"pre_rentree"|"definitive"} */ ("pre_rentree"));
  let anneeCibleId = $state(/** @type {null | number} */ (null));
  let anneeSourceId = $state(/** @type {null | number} */ (null));

  let dernierRapport = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  // Boucle KoXo → Google (Lot 8b) — MDP transportés en mémoire uniquement
  let fichierKoxoEnrichi = $state(/** @type {File|null} */ (null));

  // Enregistrement du cycle de vie : inscrit les personnes du fichier en
  // CompteCible(etat="prevu") — c'est ce qui alimente l'écran Suivi.
  let enregistrerPrevus = $state(true);

  // Mode API Google (optionnel — le mode fichier reste le mode nominal)
  let statutApi = $state(/** @type {null | any} */ (null));
  let planApi = $state(/** @type {null | any} */ (null));
  let apiEnCours = $state(false);

  async function chargerStatutApi() {
    try {
      statutApi = await googleApi.statut();
    } catch (e) {
      statutApi = null;
    }
  }

  async function csvKoxoEnBase64() {
    if (!fichierKoxoEnrichi) return null;
    const buffer = await fichierKoxoEnrichi.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, /** @type {any} */ (bytes.subarray(i, i + chunk)));
    }
    return btoa(binary);
  }

  let testEnCours = $state(false);

  async function testerConnexion() {
    testEnCours = true;
    try {
      const r = await googleApi.testerConnexion();
      notify.succes(
        `Connexion Google établie — ${r.nb_utilisateurs_visibles} utilisateur(s) lu(s). ` +
          "Aucune modification n'a été faite.",
        { duree: 8000 },
      );
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      testEnCours = false;
    }
  }

  async function calculerPlanApi() {
    if (!siteId || !anneeCibleId || !anneeSourceId) {
      notify.avertissement("Site et deux années requis pour le plan API");
      return;
    }
    apiEnCours = true;
    try {
      planApi = await googleApi.plan({
        siteId, typePersonne,
        anneeCibleId, anneeSourceId,
        csvKoxoBase64: await csvKoxoEnBase64(),
        phase: phaseApi,
      });
      if (!planApi.est_executable) {
        notify.avertissement(
          `${planApi.nb_bloques} élève(s) sans OU calculable — complète la Table de correspondance`,
        );
      } else {
        notify.info(`${planApi.nb_total} opération(s) planifiée(s) — rien n'a été envoyé`);
      }
    } catch (e) {
      notify.erreur(String(e));
    } finally {
      apiEnCours = false;
    }
  }

  async function executerPlanApi() {
    if (!planApi) return;
    apiEnCours = true;
    try {
      const r = await googleApi.executer({
        siteId, typePersonne,
        anneeCibleId, anneeSourceId,
        csvKoxoBase64: await csvKoxoEnBase64(),
        phase: phaseApi,
      });
      if (r.tout_reussi) {
        notify.succes(`${r.nb_reussies} opération(s) appliquée(s) sur Google`);
      } else {
        notify.erreur(`${r.nb_echecs} échec(s) sur ${r.nb_reussies + r.nb_echecs}`);
      }
      planApi = null;
    } catch (e) {
      notify.erreur(String(e));
    } finally {
      apiEnCours = false;
    }
  }

  onMount(async () => {
    try {
      listeSites = await sitesApi.lister();
      listeAnnees = await annees.lister();
      if (listeAnnees.length >= 1) anneeCibleId = listeAnnees[0].id;
      if (listeAnnees.length >= 2) anneeSourceId = listeAnnees[1].id;
    } catch (e) {
      erreur = String(e);
    }
    await chargerStatutApi();
  });

  let anneeSourceRequise = $derived(categorie === "nouveaux" || categorie === "anciens");

  async function generer() {
    if (!siteId || !anneeCibleId) return;
    if (anneeSourceRequise && !anneeSourceId) {
      notify.avertissement("Année source requise pour cette catégorie");
      return;
    }
    chargement = true;
    erreur = "";
    try {
      const params = {
        siteId,
        typePersonne,
        categorie,
        anneeCibleId,
        anneeSourceId: anneeSourceRequise ? anneeSourceId : null,
        enregistrerPrevus,
      };
      let r;
      if (cible === "koxo") {
        r = await exportsCible.koxo(params);
      } else if (cible === "google") {
        r = fichierKoxoEnrichi
          ? await exportsCible.googleAvecMdp({ fichierKoxo: fichierKoxoEnrichi, ...params })
          : await exportsCible.google(params);
      } else if (cible === "groupes") {
        r = await exportsCible.googleGroupes({
          siteId, anneeId: anneeCibleId, inclureEleves, inclureProfs,
        });
      } else if (cible === "pmb") {
        r = await exportsCible.pmb(params);
      } else if (cible === "jpm") {
        r = await exportsCible.jpm({
          siteId, anneeCibleId, anneeSourceId, enregistrerPrevus,
        });
      } else if (cible === "cardstudio") {
        r = await exportsCible.cardstudio({
          siteId, categorie, anneeCibleId, anneeSourceId, enregistrerPrevus,
        });
      }
      const labelCible = cible === "google" && fichierKoxoEnrichi ? "google (avec MDP)" : cible;
      dernierRapport = { ...r, cible: labelCible };
      const { chemin, annule } = await enregistrerFichierBase64(
        r.nom_fichier, r.contenu_base64, "text/csv",
      );
      if (annule) return;
      const parts = [];
      if (r.nb_sans_ou > 0) parts.push(`${r.nb_sans_ou} sans OU — classe hors table`);
      if (r.nb_prevus_enregistres > 0) parts.push(`${r.nb_prevus_enregistres} compte(s) suivi(s)`);
      const suffixe = parts.length ? ` (${parts.join(" ; ")})` : "";
      const nb = r.nb_lignes ?? r.nb_total ?? 0;
      notify.succes(
        `${nb} ligne(s) — ${chemin ?? `${r.nom_fichier} dans ton dossier Téléchargements`}${suffixe}`,
        { duree: 8000 },
      );
    } catch (e) {
      erreur = String(e);
      notify.erreur(erreur);
    } finally {
      chargement = false;
    }
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Exports vers les cibles
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Génère les fichiers à importer dans les systèmes tiers. Pour l'instant
      seul <strong>KoXo</strong> est disponible (Lot 8a) — Google, PMB, JPM,
      CardStudio viennent dans les lots suivants.
    </p>
  </header>

  {#if listeSites.length === 0 || listeAnnees.length === 0}
    <div class="card border-amber-200 bg-amber-50/50 p-4 text-sm dark:border-amber-800 dark:bg-amber-900/20">
      <div class="flex items-start gap-3">
        <AlertTriangle class="mt-0.5 h-5 w-5 text-amber-700 dark:text-amber-400" />
        <div>
          <p class="font-medium text-amber-900 dark:text-amber-200">Données manquantes</p>
          <p class="mt-1 text-stone-700 dark:text-stone-300">
            Il faut au moins un <strong>Site</strong> et une <strong>année scolaire</strong>
            {#if listeAnnees.length === 0}(via un amorçage ou une ingestion){/if} pour
            générer un export.
          </p>
        </div>
      </div>
    </div>
  {/if}

  <div class="card p-5 space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold">Génération d'un CSV</h2>
      <Segments
        bind:valeur={cible}
        taille="sm"
        options={[
          { id: "koxo", label: "KoXo" },
          { id: "google", label: "Google" },
          { id: "groupes", label: "Groupes" },
          { id: "pmb", label: "PMB" },
          { id: "jpm", label: "JPM" },
          { id: "cardstudio", label: "CardStudio" },
        ]}
      />
    </div>

    <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Site cible
        </span>
        <select
          bind:value={siteId}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value={null}>— Choisir —</option>
          {#each listeSites as s (s.id)}
            <option value={s.id}>{s.nom}</option>
          {/each}
        </select>
      </label>
      <label class="block {cible === 'groupes' ? 'opacity-40 pointer-events-none' : ''}">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Type de population
        </span>
        <select
          bind:value={typePersonne}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value="eleve">Élèves</option>
          <option value="adulte">Adultes / Profs</option>
        </select>
      </label>
      <label class="block {cible === 'groupes' ? 'opacity-40 pointer-events-none' : ''}">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Catégorie
        </span>
        <select
          bind:value={categorie}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value="tous">Tous (état complet visé)</option>
          <option value="nouveaux">Nouveaux (à créer)</option>
          <option value="anciens">Anciens (à supprimer)</option>
        </select>
      </label>
    </div>

    {#if cible === "groupes"}
      <div class="flex flex-wrap gap-4 rounded-lg border border-stone-200 bg-stone-50 p-3 dark:border-stone-700 dark:bg-stone-800">
        <label class="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            bind:checked={inclureEleves}
            class="h-4 w-4 rounded border-stone-300 text-emerald-700 focus:ring-emerald-500"
          />
          Mailing lists de classe (élèves)
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            bind:checked={inclureProfs}
            class="h-4 w-4 rounded border-stone-300 text-emerald-700 focus:ring-emerald-500"
          />
          Groupes d'enseignants
        </label>
      </div>
    {/if}

    <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Année cible (à traiter)
        </span>
        <select
          bind:value={anneeCibleId}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value={null}>— Choisir —</option>
          {#each listeAnnees as a (a.id)}
            <option value={a.id}>{a.libelle}</option>
          {/each}
        </select>
      </label>
      {#if anneeSourceRequise}
        <label class="block">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
            Année source (référentiel)
          </span>
          <select
            bind:value={anneeSourceId}
            class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
          >
            <option value={null}>— Choisir —</option>
            {#each listeAnnees as a (a.id)}
              <option value={a.id}>{a.libelle}</option>
            {/each}
          </select>
        </label>
      {/if}
    </div>

    <div class="rounded-lg border border-stone-200 bg-stone-50 p-3 text-xs dark:border-stone-700 dark:bg-stone-800">
      <div class="flex items-start gap-2 text-stone-700 dark:text-stone-300">
        <Info class="mt-0.5 h-4 w-4 shrink-0" />
        <div class="space-y-1">
          {#if cible === "groupes"}
            <p>
              Appartenances aux groupes Google — un fichier à charger dans
              <strong>Admin Google → Groupes → Importer des membres</strong>.
            </p>
            <p>
              Les adresses viennent de la <strong>Table de correspondance</strong> :
              colonne <em>groupe Google</em> pour les élèves de la classe, colonne
              <em>groupe profs</em> pour les enseignants.
            </p>
            <p class="text-stone-500">
              Les enseignants sont déduits du champ Charlemagne « Liste des classes
              (prof principal) » — un intervenant qui n'est pas professeur principal
              n'y figure pas. Le rapport signale les groupes restés vides.
            </p>
          {:else if cible === "koxo"}
            {#if categorie === "tous"}
              <p>Toutes les personnes du site+type ayant un snapshot dans l'année cible. Utile pour un import massif initial ou une resynchronisation.</p>
            {:else if categorie === "nouveaux"}
              <p>Uniquement les entrants (présents cible, absents source). KoXo <strong>générera les mots de passe à l'import</strong>.</p>
            {:else}
              <p>Uniquement les sortants (présents source, absents cible). À utiliser pour supprimer les comptes obsolètes côté KoXo.</p>
            {/if}
          {:else}
            {#if categorie === "tous"}
              <p>État complet visé — chaque personne est placée dans son OU définitive (via Table de correspondance).</p>
            {:else if categorie === "nouveaux"}
              <p>Nouveaux comptes Google — placés dans l'<strong>OU pré-rentrée</strong>, mot de passe vide (sera rempli à partir de KoXo au Lot 8b), forçage du changement de MDP à la 1<sup>re</sup> connexion.</p>
            {:else}
              <p>Sortants — à déplacer manuellement vers <code>/7. Sortis/…</code> (l'automatisation viendra plus tard).</p>
            {/if}
            <p class="text-stone-500">Format Google Admin bulk-import : 40 colonnes, UTF-8 avec BOM. Ce CSV se charge dans Admin Google → Utilisateurs → Importer utilisateurs.</p>
          {/if}
        </div>
      </div>
    </div>

    {#if cible === "google" && categorie === "nouveaux"}
      <div class="rounded-lg border-2 border-dashed border-emerald-300 bg-emerald-50/40 p-3 dark:border-emerald-700 dark:bg-emerald-900/10">
        <p class="text-xs font-medium text-emerald-900 dark:text-emerald-200 mb-2">
          Boucle de retour KoXo → Google (Lot 8b)
        </p>
        <p class="text-xs text-stone-700 dark:text-stone-300 mb-2">
          Si tu as déjà importé le CSV KoXo Nouveaux et re-exporté les comptes avec
          leurs mots de passe, dépose ce fichier ici — le CSV Google sera enrichi
          des MDP correspondants. <strong>Aucun MDP n'est stocké côté serveur.</strong>
        </p>
        <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-xs text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
          <Upload class="h-3.5 w-3.5" />
          {fichierKoxoEnrichi?.name ?? "Choisir le CSV KoXo (avec MDP)"}
          <input
            type="file"
            accept=".csv"
            onchange={(e) => (fichierKoxoEnrichi = e.target.files?.[0] ?? null)}
            class="hidden"
          />
        </label>
        {#if fichierKoxoEnrichi}
          <button
            class="ml-2 text-xs text-stone-500 hover:text-red-600"
            onclick={() => (fichierKoxoEnrichi = null)}
          >
            × retirer
          </button>
        {/if}
      </div>
    {/if}

    {#if categorie === "nouveaux"}
      <label class="flex items-start gap-2 text-xs text-stone-700 dark:text-stone-300">
        <input
          type="checkbox"
          bind:checked={enregistrerPrevus}
          class="mt-0.5 h-4 w-4 rounded border-stone-300 text-emerald-700 focus:ring-emerald-500"
        />
        <span>
          <strong>Enregistrer le suivi</strong> — inscrit les personnes du fichier
          comme comptes <em>prévus</em> sur cette cible. C'est ce qui alimente
          l'onglet <strong>Suivi</strong> ; tu confirmeras la création réelle
          après l'import.
        </span>
      </label>
    {/if}

    <div class="flex gap-2">
      <Bouton
        variante="primary"
        icon={FileDown}
        occupe={chargement}
        disabled={!siteId || !anneeCibleId || (anneeSourceRequise && !anneeSourceId)}
        onclick={generer}
      >
        {cible === "google" && fichierKoxoEnrichi
          ? "Générer Google avec MDP"
          : "Générer et télécharger"}
      </Bouton>
    </div>

    {#if erreur}
      <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
        {erreur}
      </p>
    {/if}
  </div>

  <!-- Mode API Google — canal alternatif au CSV -->
  {#if cible === "google" && statutApi}
    <div class="card p-4 space-y-3">
      <div class="flex items-center justify-between gap-2">
        <h2 class="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
          <Cloud class="h-4 w-4" />
          Mode API (optionnel)
        </h2>
        {#if statutApi.configuration_complete}
          <span class="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
            <CheckCircle2 class="h-3.5 w-3.5" />
            Configuré
          </span>
        {:else}
          <span class="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-600 dark:bg-stone-800 dark:text-stone-400">
            Non configuré
          </span>
        {/if}
      </div>

      {#if statutApi.bibliotheques_disponibles}
        <div class="mb-3">
          <Bouton icon={Cloud} occupe={testEnCours} onclick={testerConnexion}>
            Tester la connexion
          </Bouton>
          <span class="ml-2 text-xs text-stone-500 dark:text-stone-400">
            Lit un seul utilisateur, ne modifie rien.
          </span>
        </div>
      {/if}

      {#if !statutApi.configuration_complete}
        <div class="rounded-lg border border-stone-200 bg-stone-50 p-3 text-xs dark:border-stone-700 dark:bg-stone-800">
          <p class="text-stone-700 dark:text-stone-300">
            Le mode API applique les changements directement dans Google, sans
            passer par l'import manuel du CSV. <strong>Le mode fichier
            ci-dessus reste le mode nominal</strong> et fonctionne sans cette
            configuration.
          </p>
          {#if statutApi.problemes.length > 0}
            <ul class="mt-2 space-y-0.5 text-stone-600 dark:text-stone-400">
              {#each statutApi.problemes as p}
                <li>• {p}</li>
              {/each}
            </ul>
          {/if}
          {#if !statutApi.bibliotheques_disponibles}
            <p class="mt-2 text-stone-500">{statutApi.message_bibliotheques}</p>
          {/if}
        </div>
      {:else}
        <!--
          Deux écrans savaient appliquer un déplacement d'OU, sans que rien
          ne dise lequel choisir. Celui-ci reste utile pour les créations et
          les suspensions ; pour les OU, la Bascule montre l'avancement.
        -->
        <p class="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-900 dark:bg-emerald-900/20 dark:text-emerald-200">
          Pour <strong>déplacer les élèves d'OU</strong>, préfère l'onglet
          <strong>Bascule des OU</strong> : même traitement, mais avec
          l'avancement élève par élève et la reprise des échecs. Cette
          section-ci sert aux créations de comptes et aux suspensions.
        </p>

        <div class="mb-3">
          <span class="libelle-champ">Phase de rentrée</span>
          <Segments
            bind:valeur={phaseApi}
            taille="sm"
            options={[
              { id: "pre_rentree", label: "1. Pré-rentrée" },
              { id: "definitive", label: "2. Rentrée" },
            ]}
            onChange={() => (planApi = null)}
          />
          <p class="mt-1.5 text-xs text-stone-500 dark:text-stone-400">
            Même découpage que l'onglet <strong>Bascule des OU</strong> : les
            déplacements sont calculés par le même service, les deux canaux ne
            peuvent pas diverger.
          </p>
        </div>

        <div class="flex flex-wrap gap-2">
          <button class="btn-secondary" onclick={calculerPlanApi} disabled={apiEnCours}>
            <Cloud class="h-4 w-4" />
            Calculer le plan
          </button>
          {#if planApi && planApi.nb_total > 0 && planApi.est_executable}
            <button class="btn-primary" onclick={executerPlanApi} disabled={apiEnCours}>
              Appliquer les {planApi.nb_total} opération(s)
            </button>
          {/if}
        </div>

        {#if planApi}
          <div class="rounded-lg border border-stone-200 p-3 text-sm dark:border-stone-700">
            <p class="font-medium">
              {planApi.nb_creations} création(s) · {planApi.nb_deplacements} déplacement(s)
              · {planApi.nb_suspensions} suspension(s)
            </p>
            <p class="mt-1 text-xs text-stone-500">
              Aucun compte n'est jamais supprimé — un sortant est suspendu et
              déplacé en OU d'archivage.
            </p>
            {#if !planApi.est_executable}
              <p class="mt-2 rounded bg-red-50 px-2 py-1.5 text-xs text-red-700 dark:bg-red-900/30 dark:text-red-300">
                {planApi.nb_bloques} élève(s) sans OU calculable — exécution
                refusée. Complète la Table de correspondance : le programme
                n'attribue jamais d'OU par défaut.
              </p>
            {/if}
            {#if planApi.avertissements.length > 0}
              <ul class="mt-2 space-y-0.5 text-xs text-amber-700 dark:text-amber-400">
                {#each planApi.avertissements.slice(0, 10) as a}
                  <li>⚠ {a}</li>
                {/each}
              </ul>
            {/if}
            {#if planApi.operations.length > 0}
              <details class="mt-2">
                <summary class="cursor-pointer text-xs text-sky-700 dark:text-sky-400">
                  Voir les opérations
                </summary>
                <ul class="mt-1 space-y-0.5 text-xs text-stone-600 dark:text-stone-400">
                  {#each planApi.operations.slice(0, 50) as o}
                    <li>{o.libelle}</li>
                  {/each}
                </ul>
              </details>
            {/if}
          </div>
        {/if}
      {/if}
    </div>
  {/if}

  {#if dernierRapport}
    <div class="card p-4">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm font-semibold text-stone-900 dark:text-stone-100">
            Dernier export : <code>{dernierRapport.nom_fichier}</code>
          </p>
          <p class="text-xs text-stone-500 dark:text-stone-400">
            {dernierRapport.nb_lignes} ligne(s) — {dernierRapport.cible}, site {dernierRapport.site_nom},
            {dernierRapport.type_personne}s, catégorie {dernierRapport.categorie}
          </p>
          {#if dernierRapport.nb_sans_ou > 0}
            <p class="text-xs text-amber-700 dark:text-amber-400">
              ⚠ {dernierRapport.nb_sans_ou} ligne(s) sans OU — leur classe n'est pas dans la Table de correspondance.
            </p>
          {/if}
          {#if dernierRapport.classes_sans_groupe?.length > 0}
            <p class="text-xs text-amber-700 dark:text-amber-400">
              ⚠ {dernierRapport.classes_sans_groupe.length} classe(s) sans adresse de groupe :
              <span class="font-mono">{dernierRapport.classes_sans_groupe.join(", ")}</span>
            </p>
          {/if}
          {#if dernierRapport.groupes_profs_vides?.length > 0}
            <p class="text-xs text-stone-500">
              {dernierRapport.groupes_profs_vides.length} groupe(s) profs sans aucun
              enseignant rattaché — le champ « prof principal » ne couvre pas tous
              les intervenants.
            </p>
          {/if}
        </div>
        <button
          class="btn-secondary text-xs"
          onclick={() => enregistrerFichierBase64(dernierRapport.nom_fichier, dernierRapport.contenu_base64, "text/csv")}
        >
          <Download class="h-3.5 w-3.5" />
          Ré-enregistrer
        </button>
      </div>
    </div>
  {/if}
</section>
