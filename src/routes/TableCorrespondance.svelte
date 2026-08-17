<script>
  import { onMount } from "svelte";
  import Table from "@lucide/svelte/icons/table";
  import Upload from "@lucide/svelte/icons/upload";
  import PlayCircle from "@lucide/svelte/icons/play-circle";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Plus from "@lucide/svelte/icons/plus";
  import Pencil from "@lucide/svelte/icons/pencil";
  import Trash2 from "@lucide/svelte/icons/trash-2";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Modale from "$lib/components/Modale.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { tableCorrespondance, sites as sitesApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let liste = $state([]);
  let sites = $state([]);
  let filtreSite = $state("");
  let chargement = $state(true);
  let erreur = $state("");

  // Import XLSX
  let panneauImportOuvert = $state(false);
  let fichierImport = $state(/** @type {File|null} */ (null));
  let nomOngletForce = $state("");
  let rapportImport = $state(/** @type {null | any} */ (null));
  let importEnCours = $state(false);

  // Édition manuelle — indispensable pour les classes que le classeur
  // historique ne connaît pas (créations récentes, options nouvelles).
  let modale = $state(/** @type {null | {mode: "creer"|"modifier", id?: number}} */ (null));
  let form = $state(formulaireVide());
  let enregistrement = $state(false);

  function formulaireVide() {
    return {
      site_id: null,
      classe_code_court: "",
      classe_charlemagne_long: "",
      ou_pre_rentree: "",
      ou_definitive: "",
      groupe_google: "",
      groupe_profs_google: "",
    };
  }

  let filtree = $derived(
    filtreSite ? liste.filter((l) => l.site_nom === filtreSite) : liste,
  );

  /**
   * Ouvre le formulaire de création.
   *
   * Les OU sont pré-remplies à partir d'une ligne existante du même site :
   * elles suivent toutes le même motif, seul le code classe change. Cela
   * évite de retaper une arborescence entière au risque d'une faute de
   * frappe qui placerait l'élève dans une OU inexistante.
   */
  function ouvrirCreation(codePreRempli = "") {
    form = formulaireVide();
    form.classe_code_court = codePreRempli;
    const modele = filtree[0] ?? liste[0];
    if (modele) {
      form.site_id = modele.site_id;
      form.ou_pre_rentree = modele.ou_pre_rentree;
      form.ou_definitive = codePreRempli
        ? `${modele.ou_pre_rentree}/${codePreRempli}`
        : "";
    } else if (sites.length === 1) {
      form.site_id = sites[0].id;
    }
    modale = { mode: "creer" };
  }

  function ouvrirModification(l) {
    form = {
      site_id: l.site_id,
      classe_code_court: l.classe_code_court,
      classe_charlemagne_long: l.classe_charlemagne_long,
      ou_pre_rentree: l.ou_pre_rentree,
      ou_definitive: l.ou_definitive,
      groupe_google: l.groupe_google ?? "",
      groupe_profs_google: l.groupe_profs_google ?? "",
    };
    modale = { mode: "modifier", id: l.id };
  }

  // L'OU définitive suit le code classe tant que l'utilisateur ne l'a pas
  // éditée à la main — comportement attendu dans l'immense majorité des cas.
  function surChangementCode() {
    if (form.ou_pre_rentree && form.classe_code_court) {
      form.ou_definitive = `${form.ou_pre_rentree}/${form.classe_code_court}`;
    }
  }

  let formValide = $derived(
    !!form.site_id &&
      form.classe_code_court.trim() !== "" &&
      form.ou_pre_rentree.trim() !== "" &&
      form.ou_definitive.trim() !== "",
  );

  async function enregistrer() {
    if (!formValide) return;
    enregistrement = true;
    try {
      const payload = {
        site_id: Number(form.site_id),
        classe_code_court: form.classe_code_court.trim(),
        // Le libellé long est facultatif à la saisie : à défaut, on reprend
        // le code court plutôt que d'imposer une redite.
        classe_charlemagne_long:
          form.classe_charlemagne_long.trim() || form.classe_code_court.trim(),
        ou_pre_rentree: form.ou_pre_rentree.trim(),
        ou_definitive: form.ou_definitive.trim(),
        groupe_google: form.groupe_google.trim() || null,
        groupe_profs_google: form.groupe_profs_google.trim() || null,
      };
      if (modale.mode === "creer") {
        await tableCorrespondance.creer(payload);
        notify.succes(`Classe ${payload.classe_code_court} ajoutée`);
      } else {
        await tableCorrespondance.modifier(modale.id, payload);
        notify.succes(`Classe ${payload.classe_code_court} modifiée`);
      }
      modale = null;
      await recharger();
    } catch (e) {
      notify.erreur(String(e));
    } finally {
      enregistrement = false;
    }
  }

  async function supprimer(l) {
    if (!confirm(`Supprimer la classe ${l.classe_code_court} de la table ?`)) return;
    try {
      await tableCorrespondance.supprimer(l.id);
      notify.succes(`Classe ${l.classe_code_court} supprimée`);
      await recharger();
    } catch (e) {
      notify.erreur(String(e));
    }
  }

  onMount(recharger);

  async function recharger() {
    chargement = true;
    erreur = "";
    try {
      const [l, s] = await Promise.all([tableCorrespondance.lister(), sitesApi.lister()]);
      liste = l;
      sites = s;
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  function onSelectionImport(e) {
    fichierImport = e.target.files?.[0] ?? null;
    rapportImport = null;
  }

  async function lancerImport(mode) {
    if (!fichierImport) return;
    importEnCours = true;
    rapportImport = null;
    try {
      rapportImport = await tableCorrespondance.importerXlsx({
        fichier: fichierImport,
        mode,
        nomOnglet: nomOngletForce.trim() || null,
      });
      if (mode === "reel" && !rapportImport.est_bloque) {
        const c = rapportImport;
        notify.succes(
          `Import : +${c.nb_creations} créées, ${c.nb_mises_a_jour} MAJ, ${c.nb_identiques} inchangées`,
        );
        await recharger();
      } else if (rapportImport.est_bloque) {
        notify.erreur(rapportImport.erreurs.join(" ; "));
      } else {
        notify.info("Simulation terminée — rien n'a été écrit");
      }
    } catch (e) {
      notify.erreur(String(e));
    } finally {
      importEnCours = false;
    }
  }
</script>

<section class="space-y-4">
  <EnTetePage
    icon={Table}
    titre="Table de correspondance"
    description="Fait le pont entre les codes classe Charlemagne et les cibles : unité d'organisation Google (pré-rentrée + définitive) et adresses des groupes Google. Une classe absente est un cas bloquant à l'ingestion — le programme refuse plutôt que d'affecter par défaut."
  >
    {#snippet actions()}
      <button class="btn-secondary" onclick={() => (panneauImportOuvert = !panneauImportOuvert)}>
        <Upload class="h-4 w-4" />
        Importer XLSX
      </button>
      <button class="btn-primary" onclick={() => ouvrirCreation()}>
        <Plus class="h-4 w-4" />
        Ajouter une classe
      </button>
    {/snippet}
  </EnTetePage>

  {#if panneauImportOuvert}
    <div class="card p-5 space-y-4 border-emerald-200 dark:border-emerald-800">
      <h2 class="text-lg font-semibold">Importer depuis un classeur historique</h2>
      <p class="text-sm text-stone-600 dark:text-stone-400">
        Le fichier attendu est celui du prédécesseur (<code>Gestion bases - rentrée 20XX.xlsx</code>).
        L'onglet <code>Table</code> est détecté automatiquement. Le mode <strong>simulation</strong>
        te montre ce qui serait fait sans écrire, le mode <strong>réel</strong> commit.
      </p>

      <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
        <label class="block">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
            Fichier .xlsx
          </span>
          <label class="btn-secondary mt-1 inline-flex w-full cursor-pointer justify-center">
            <Upload class="h-4 w-4" />
            {fichierImport?.name ?? "Choisir un .xlsx"}
            <input type="file" accept=".xlsx" onchange={onSelectionImport} class="hidden" />
          </label>
        </label>
        <label class="block">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
            Nom d'onglet forcé (optionnel)
          </span>
          <input
            type="text"
            bind:value={nomOngletForce}
            placeholder="Table"
            class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
          />
        </label>
      </div>

      <div class="flex flex-wrap gap-2">
        <button
          class="btn-secondary"
          onclick={() => lancerImport("simulation")}
          disabled={!fichierImport || importEnCours}
        >
          <PlayCircle class="h-4 w-4" />
          Simuler
        </button>
        <button
          class="btn-primary"
          onclick={() => lancerImport("reel")}
          disabled={!fichierImport || importEnCours}
        >
          <Sparkles class="h-4 w-4" />
          Importer (réel)
        </button>
        {#if importEnCours}
          <span class="self-center text-sm text-stone-500">Traitement…</span>
        {/if}
      </div>

      {#if rapportImport}
        <div class="border-t border-stone-200 pt-4 dark:border-stone-700 space-y-3">
          <div class="flex items-center justify-between">
            <p class="text-sm font-semibold">
              Onglet lu : <code>{rapportImport.onglet_utilise || "?"}</code>
            </p>
            {#if rapportImport.est_bloque}
              <span class="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900/40 dark:text-red-300">
                <AlertTriangle class="h-3.5 w-3.5" />
                Bloqué
              </span>
            {:else if rapportImport.mode === "simulation"}
              <span class="inline-flex items-center gap-1 rounded-full bg-sky-100 px-2.5 py-0.5 text-xs font-medium text-sky-800 dark:bg-sky-900/40 dark:text-sky-300">
                Simulation
              </span>
            {:else}
              <span class="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
                <CheckCircle2 class="h-3.5 w-3.5" />
                Committé
              </span>
            {/if}
          </div>

          <div class="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
            <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
              <p class="text-xs text-stone-500">Lignes lues</p>
              <p class="text-lg font-semibold tabular-nums">{rapportImport.nb_lignes_lues}</p>
            </div>
            <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
              <p class="text-xs text-stone-500">Créées</p>
              <p class="text-lg font-semibold tabular-nums text-emerald-700 dark:text-emerald-400">
                +{rapportImport.nb_creations}
              </p>
            </div>
            <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
              <p class="text-xs text-stone-500">Mises à jour</p>
              <p class="text-lg font-semibold tabular-nums">{rapportImport.nb_mises_a_jour}</p>
            </div>
            <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
              <p class="text-xs text-stone-500">Inchangées</p>
              <p class="text-lg font-semibold tabular-nums">{rapportImport.nb_identiques}</p>
            </div>
          </div>

          {#if rapportImport.sites_inconnus?.length > 0}
            <div class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-900/20">
              <p class="font-medium text-amber-900 dark:text-amber-200">
                Sites lus mais absents de la base : {rapportImport.sites_inconnus.join(", ")}
              </p>
              <p class="mt-1 text-xs text-stone-700 dark:text-stone-300">
                Crée ces sites dans l'onglet <strong>Sites</strong> puis relance l'import.
              </p>
            </div>
          {/if}

          {#if rapportImport.lignes_rejetees?.length > 0}
            <details class="rounded-lg border border-stone-200 dark:border-stone-700">
              <summary class="cursor-pointer bg-stone-50 px-3 py-2 text-sm font-medium dark:bg-stone-800">
                {rapportImport.lignes_rejetees.length} ligne(s) rejetée(s)
              </summary>
              <ul class="max-h-64 overflow-auto p-3 space-y-1 text-xs">
                {#each rapportImport.lignes_rejetees as lr}
                  <li>
                    <span class="font-mono text-stone-500">L{lr.ligne_source}</span>
                    — {lr.raison}
                  </li>
                {/each}
              </ul>
            </details>
          {/if}

          {#if rapportImport.erreurs?.length > 0}
            <div class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm dark:border-red-800 dark:bg-red-900/20">
              <ul class="space-y-1">
                {#each rapportImport.erreurs as e}
                  <li>{e}</li>
                {/each}
              </ul>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">{erreur}</p>
  {/if}

  {#if sites.length > 0}
    <div class="card p-3">
      <div class="flex flex-wrap items-center gap-2">
        <button
          class="rounded-full border px-3 py-0.5 text-xs font-medium
                 {!filtreSite ? 'border-emerald-600 bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300' : 'border-stone-200 bg-white text-stone-600 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-400'}"
          onclick={() => (filtreSite = "")}
        >
          Tous
        </button>
        {#each sites as s (s.id)}
          <button
            class="rounded-full border px-3 py-0.5 text-xs font-medium
                   {filtreSite === s.nom ? 'border-emerald-600 bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300' : 'border-stone-200 bg-white text-stone-600 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-400'}"
            onclick={() => (filtreSite = s.nom)}
          >
            {s.nom}
          </button>
        {/each}
        <span class="ml-auto text-xs text-stone-500 dark:text-stone-400 tabular-nums">
          {filtree.length} / {liste.length}
        </span>
      </div>
    </div>
  {/if}

  <div class="card overflow-hidden">
    {#if chargement}
      <div class="p-4">
        <Squelette variante="ligne-tableau" nb={6} colonnes={6} />
      </div>
    {:else if liste.length === 0}
      <div class="p-4">
        <EtatVide
          icon={Table}
          titre="Table vide"
          message="Aucune classe n'est encore déclarée. Sans elle, l'ingestion refusera de s'exécuter — c'est volontaire : le programme n'affecte jamais une classe par défaut."
          ton="attention"
        >
          <button class="btn-primary text-xs" onclick={() => (panneauImportOuvert = true)}>
            <Upload class="h-3.5 w-3.5" />
            Importer depuis le classeur historique
          </button>
        </EtatVide>
      </div>
    {:else}
      <div class="max-h-[640px] overflow-auto">
        <table class="w-full text-sm">
          <thead class="sticky top-0 z-10 bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300">
            <tr>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Site</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Classe Charlemagne</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Code court</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Groupe Google</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">OU pré-rentrée</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">OU définitive</th>
              <th class="border-b border-stone-200 px-3 py-2 text-right font-semibold dark:border-stone-700"></th>
            </tr>
          </thead>
          <tbody>
            {#each filtree as l (l.id)}
              <tr class="border-b border-stone-100 dark:border-stone-800 hover:bg-emerald-50/40 dark:hover:bg-emerald-900/20">
                <td class="px-3 py-1.5 font-medium">{l.site_nom}</td>
                <td class="px-3 py-1.5 text-stone-700 dark:text-stone-300">{l.classe_charlemagne_long}</td>
                <td class="px-3 py-1.5 font-mono text-xs">{l.classe_code_court}</td>
                <td class="px-3 py-1.5 font-mono text-xs text-stone-600 dark:text-stone-400">{l.groupe_google ?? "—"}</td>
                <td class="px-3 py-1.5 font-mono text-xs text-stone-600 dark:text-stone-400">{l.ou_pre_rentree}</td>
                <td class="px-3 py-1.5 font-mono text-xs text-stone-600 dark:text-stone-400">{l.ou_definitive}</td>
                <td class="whitespace-nowrap px-3 py-1 text-right">
                  <button
                    class="rounded-md p-1.5 text-stone-400 transition hover:bg-stone-100 hover:text-stone-700 dark:hover:bg-stone-700 dark:hover:text-stone-200"
                    title="Modifier"
                    onclick={() => ouvrirModification(l)}
                  >
                    <Pencil class="h-3.5 w-3.5" />
                  </button>
                  <button
                    class="rounded-md p-1.5 text-stone-400 transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/30 dark:hover:text-red-400"
                    title="Supprimer"
                    onclick={() => supprimer(l)}
                  >
                    <Trash2 class="h-3.5 w-3.5" />
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</section>

<!-- Formulaire de saisie manuelle -->
{#if modale}
  <Modale
    largeur="lg"
    titre={modale.mode === "creer" ? "Ajouter une classe" : "Modifier la classe"}
    onFermer={() => (modale = null)}
  >
      <div class="grid grid-cols-2 gap-3">
        <label class="block">
          <span class="libelle-champ">Site *</span>
          <select bind:value={form.site_id} class="champ mt-1">
            <option value={null}>— Choisir —</option>
            {#each sites as s (s.id)}
              <option value={s.id}>{s.nom}</option>
            {/each}
          </select>
        </label>
        <label class="block">
          <span class="libelle-champ">Code classe Charlemagne *</span>
          <input
            type="text"
            bind:value={form.classe_code_court}
            oninput={surChangementCode}
            placeholder="1_ST2S1"
            class="champ mt-1 font-mono"
          />
        </label>
      </div>

      <label class="block">
        <span class="libelle-champ">Libellé long (facultatif)</span>
        <input
          type="text"
          bind:value={form.classe_charlemagne_long}
          placeholder="PREMIERE ST2S 1"
          class="champ mt-1"
        />
      </label>

      <label class="block">
        <span class="libelle-champ">OU pré-rentrée *</span>
        <input
          type="text"
          bind:value={form.ou_pre_rentree}
          oninput={surChangementCode}
          placeholder="/3. NDK/NDK2026"
          class="champ mt-1 font-mono text-xs"
        />
      </label>

      <label class="block">
        <span class="libelle-champ">OU définitive *</span>
        <input
          type="text"
          bind:value={form.ou_definitive}
          placeholder="/3. NDK/NDK2026/1_ST2S1"
          class="champ mt-1 font-mono text-xs"
        />
        <span class="mt-1 block text-xs text-stone-500 dark:text-stone-400">
          Complétée automatiquement à partir de l'OU pré-rentrée et du code
          classe — modifiable si ton arborescence diffère.
        </span>
      </label>

      <div class="grid grid-cols-2 gap-3">
        <label class="block">
          <span class="libelle-champ">Groupe Google élèves</span>
          <input
            type="text"
            bind:value={form.groupe_google}
            placeholder="1ere-st2s1@lekreisker.fr"
            class="champ mt-1 font-mono text-xs"
          />
        </label>
        <label class="block">
          <span class="libelle-champ">Groupe Google profs</span>
          <input
            type="text"
            bind:value={form.groupe_profs_google}
            placeholder="profs-1ere-st2s1@lekreisker.fr"
            class="champ mt-1 font-mono text-xs"
          />
        </label>
      </div>

    {#snippet actions()}
      <button class="btn-secondary" onclick={() => (modale = null)} disabled={enregistrement}>
        Annuler
      </button>
      <button class="btn-primary" onclick={enregistrer} disabled={!formValide || enregistrement}>
        {modale.mode === "creer" ? "Ajouter" : "Enregistrer"}
      </button>
    {/snippet}
  </Modale>
{/if}
