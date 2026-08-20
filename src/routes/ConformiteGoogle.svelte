<script>
  import { onMount } from "svelte";
  import ShieldCheck from "@lucide/svelte/icons/shield-check";
  import FolderTree from "@lucide/svelte/icons/folder-tree";
  import AtSign from "@lucide/svelte/icons/at-sign";
  import UsersRound from "@lucide/svelte/icons/users-round";
  import Check from "@lucide/svelte/icons/check";
  import X from "@lucide/svelte/icons/x";
  import Loader from "@lucide/svelte/icons/loader-2";
  import Search from "@lucide/svelte/icons/search";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import { annees, googleApi, sites } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let statutApi = $state(/** @type {any} */ (null));
  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let listeSites = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));

  let volet = $state("arborescence");
  let job = $state(/** @type {any} */ (null));
  let sondage = /** @type {any} */ (null);

  let apiUtilisable = $derived(
    statutApi?.bibliotheques_disponibles && statutApi?.configuration_complete,
  );

  // --- Arborescence ---------------------------------------------------------
  let anneeSource = $state("");
  let anneeCible = $state("");
  let renommer = $state(true);
  let confOu = $state(/** @type {any} */ (null));
  let chargeOu = $state(false);

  async function analyserOu() {
    chargeOu = true;
    try {
      confOu = await googleApi.conformiteOu({
        anneeSource: anneeSource || null,
        anneeCible: anneeCible || null,
        renommer,
      });
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      chargeOu = false;
    }
  }

  async function appliquerOu() {
    chargeOu = true;
    try {
      job = await googleApi.appliquerOu({
        anneeSource: anneeSource || null,
        anneeCible: anneeCible || null,
        renommer,
      });
      confOu = null;
      sonder();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      chargeOu = false;
    }
  }

  // --- Adresses -------------------------------------------------------------
  let divergences = $state(/** @type {any} */ (null));
  let chargeAdr = $state(false);

  async function analyserAdresses() {
    chargeAdr = true;
    try {
      divergences = await googleApi.divergences({ anneeId });
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      chargeAdr = false;
    }
  }

  async function corrigerAdresses() {
    chargeAdr = true;
    try {
      const r = await googleApi.corrigerAdresses({ anneeId, mode: "reel" });
      notify.succes(`${r.nb_corrigees} adresse(s) alignée(s) sur Google`);
      await analyserAdresses();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      chargeAdr = false;
    }
  }

  // --- Groupes --------------------------------------------------------------
  let diffGroupes = $state(/** @type {any} */ (null));
  let chargeGrp = $state(false);
  let retirerMembres = $state(true);

  async function analyserGroupes() {
    if (!anneeId) return;
    chargeGrp = true;
    try {
      diffGroupes = await googleApi.diffGroupes({ anneeId });
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      chargeGrp = false;
    }
  }

  async function synchroniserGroupes() {
    chargeGrp = true;
    try {
      job = await googleApi.synchroniserGroupes({ anneeId, retirer: retirerMembres });
      diffGroupes = null;
      sonder();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      chargeGrp = false;
    }
  }

  // --- Suivi commun ---------------------------------------------------------
  function sonder() {
    arreter();
    sondage = setInterval(async () => {
      if (!job) return arreter();
      try {
        job = await googleApi.suivreJob(job.id);
        if (job.est_termine) {
          arreter();
          notify.info(
            `${job.nb_reussies} réussie(s), ${job.nb_echecs} échec(s) sur ${job.total}`,
            { duree: 8000 },
          );
        }
      } catch (e) {
        arreter();
        notify.erreur(String(e).replace(/^Error:\s*/, ""));
      }
    }, 700);
  }

  function arreter() {
    if (sondage) clearInterval(sondage);
    sondage = null;
  }

  $effect(() => () => arreter());

  let etapesVues = $derived.by(() => {
    if (!job) return [];
    const faites = job.etapes.filter((e) => e.statut !== "attente");
    const echecs = faites.filter((e) => e.statut === "echec");
    return [...echecs, ...faites.filter((e) => e.statut !== "echec").slice(-40).reverse()];
  });

  onMount(async () => {
    try {
      [listeAnnees, listeSites] = await Promise.all([annees.lister(), sites.lister()]);
      const triees = [...listeAnnees].sort((a, b) => b.libelle.localeCompare(a.libelle));
      anneeId = triees[0]?.id ?? null;
      // L'arborescence porte l'année qui se termine : celle de la rentrée
      // préparée moins une pour la source, plus une pour la cible.
      const fin = triees[0]?.libelle?.split("-")?.[1];
      if (fin) {
        anneeCible = fin;
        anneeSource = String(Number(fin) - 2);
      }
      statutApi = await googleApi.statut();
    } catch {
      statutApi = null;
    }
  });
</script>

<section class="space-y-4">
  <EnTetePage
    icon={ShieldCheck}
    titre="Conformité Google"
    description="Ce que le programme peut mettre en accord avec le référentiel : l'arborescence des unités d'organisation, les adresses, et la composition des groupes de classe."
  />

  {#if !apiUtilisable}
    <div class="card p-4">
      <EtatVide
        icon={ShieldCheck}
        titre="Mode API non configuré"
        message="Ces opérations lisent et écrivent dans Google. Renseigne le compte de service dans Paramètres — voir l'aide, section « Compte de service Google »."
      />
    </div>
  {:else}
    <div class="card p-3">
      <Segments
        bind:valeur={volet}
        options={[
          { id: "arborescence", label: "Arborescence" },
          { id: "adresses", label: "Adresses" },
          { id: "groupes", label: "Groupes" },
        ]}
      />
    </div>

    {#if volet === "arborescence"}
      <div class="card p-4 space-y-3">
        <h2 class="titre-section flex items-center gap-2">
          <FolderTree class="h-4 w-4" /> Unités d'organisation
        </h2>
        <p class="text-xs text-stone-600 dark:text-stone-400">
          Google refuse un déplacement vers une OU absente, et rien en amont ne
          l'annonce : l'échec se constate élève par élève. Deux façons de
          préparer l'année — <strong>recycler</strong> l'arbre révolu, qui
          emporte ses classes d'un geste, ou <strong>créer</strong> exactement
          ce que décrit la Table. Elles se combinent.
        </p>

        <div class="flex flex-wrap items-end gap-3">
          <div>
            <label class="libelle-champ" for="an-src">Recycler l'arbre</label>
            <input id="an-src" class="champ w-24 font-mono" bind:value={anneeSource} />
          </div>
          <div>
            <label class="libelle-champ" for="an-cbl">vers</label>
            <input id="an-cbl" class="champ w-24 font-mono" bind:value={anneeCible} />
          </div>
          <label class="flex items-center gap-2 pb-2 text-sm">
            <input type="checkbox" bind:checked={renommer} class="rounded" />
            Renommer plutôt que tout créer
          </label>
          <Bouton icon={Search} occupe={chargeOu} onclick={analyserOu}>Analyser</Bouton>
          {#if confOu && !confOu.est_conforme}
            <Bouton variante="primary" occupe={chargeOu} onclick={appliquerOu}>
              Appliquer
            </Bouton>
          {/if}
        </div>

        {#if confOu}
          <div class="rounded-lg border border-stone-200 p-3 text-sm dark:border-stone-700">
            {#if confOu.est_conforme}
              <p class="text-emerald-700 dark:text-emerald-400">
                L'arborescence correspond déjà à la Table — rien à faire.
              </p>
            {:else}
              <p>
                <strong>{confOu.nb_deja_conformes}</strong> OU déjà en place ·
                <strong>{confOu.renommages.length}</strong> renommage(s) ·
                <strong class="text-emerald-700 dark:text-emerald-400">{confOu.nb_a_creer}</strong>
                à créer
              </p>
            {/if}
            {#each confOu.avertissements as a}
              <p class="mt-2 rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">{a}</p>
            {/each}
            {#each confOu.renommages as r}
              <p class="mt-2 font-mono text-xs">
                {r.ancien} → {r.nouveau}
                <span class="text-stone-500">({r.nb_sous_ou} classes suivent)</span>
              </p>
            {/each}
            {#if confOu.a_creer.length}
              <ul class="mt-2 max-h-64 overflow-auto font-mono text-xs text-stone-600 dark:text-stone-400">
                {#each confOu.a_creer as c}<li>{c}</li>{/each}
              </ul>
            {/if}
          </div>
        {/if}
      </div>

    {:else if volet === "adresses"}
      <div class="card p-4 space-y-3">
        <h2 class="titre-section flex items-center gap-2">
          <AtSign class="h-4 w-4" /> Adresses divergentes
        </h2>
        <p class="text-xs text-stone-600 dark:text-stone-400">
          Quand l'adresse enregistrée n'existe pas dans Google, le déplacement
          échoue et l'export des nouveaux crée un doublon à côté du compte réel.
          Seuls les écarts <strong>sans ambiguïté</strong> sont corrigés : un
          homonyme rendrait l'attribution arbitraire.
        </p>

        <div class="flex flex-wrap items-end gap-3">
          <Bouton icon={Search} occupe={chargeAdr} onclick={analyserAdresses}>
            Analyser
          </Bouton>
          {#if divergences && divergences.nb_resolvables > 0}
            <Bouton variante="primary" occupe={chargeAdr} onclick={corrigerAdresses}>
              Corriger {divergences.nb_resolvables} adresse(s)
            </Bouton>
          {/if}
        </div>

        {#if divergences}
          <p class="text-sm">
            {divergences.nb_examines} examinée(s) ·
            <strong class="text-emerald-700 dark:text-emerald-400">{divergences.nb_resolvables}</strong>
            corrigeable(s) ·
            <strong class="text-amber-700 dark:text-amber-400">{divergences.nb_ambigus}</strong>
            à trancher
          </p>
          {#if divergences.divergences.length}
            <div class="max-h-96 overflow-auto">
              <table class="tableau w-full text-sm">
                <thead>
                  <tr>
                    <th class="text-left">Élève</th>
                    <th class="text-left">Enregistrée</th>
                    <th class="text-left">Dans Google</th>
                  </tr>
                </thead>
                <tbody>
                  {#each divergences.divergences as d (d.personne_id)}
                    <tr class:ligne-douteuse={!d.resolvable}>
                      <td class="whitespace-nowrap">{d.prenom} {d.nom}</td>
                      <td class="whitespace-nowrap font-mono text-xs text-stone-500 dark:text-stone-400">
                        {d.adresse_enregistree}
                      </td>
                      <td class="font-mono text-xs">
                        {#if d.adresse_google}
                          <span class="text-emerald-700 dark:text-emerald-400">{d.adresse_google}</span>
                        {:else}
                          <span class="font-sans text-amber-700 dark:text-amber-400">{d.motif}</span>
                        {/if}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        {/if}
      </div>

    {:else}
      <div class="card p-4 space-y-3">
        <h2 class="titre-section flex items-center gap-2">
          <UsersRound class="h-4 w-4" /> Groupes de classe
        </h2>
        <p class="text-xs text-stone-600 dark:text-stone-400">
          L'export CSV <strong>ajoute</strong> des membres sans jamais en
          retirer : un groupe de 3e garde ses élèves d'il y a deux ans. Ici la
          composition est calculée par différence, dans les deux sens. Les
          membres inconnus du référentiel — enseignants, adresses de service —
          ne sont jamais retirés.
        </p>

        <div class="flex flex-wrap items-end gap-3">
          <div>
            <label class="libelle-champ" for="grp-annee">Année</label>
            <select id="grp-annee" class="champ w-40" bind:value={anneeId}>
              {#each listeAnnees as a (a.id)}<option value={a.id}>{a.libelle}</option>{/each}
            </select>
          </div>
          <label class="flex items-center gap-2 pb-2 text-sm">
            <input type="checkbox" bind:checked={retirerMembres} class="rounded" />
            Retirer aussi les anciens
          </label>
          <Bouton icon={Search} occupe={chargeGrp} onclick={analyserGroupes}>Analyser</Bouton>
          {#if diffGroupes && (diffGroupes.nb_a_ajouter > 0 || diffGroupes.nb_a_retirer > 0)}
            <Bouton variante="primary" occupe={chargeGrp} onclick={synchroniserGroupes}>
              Synchroniser
            </Bouton>
          {/if}
        </div>

        {#if diffGroupes}
          <p class="text-sm">
            <strong class="text-emerald-700 dark:text-emerald-400">{diffGroupes.nb_a_ajouter}</strong>
            entrée(s) ·
            <strong class="text-red-700 dark:text-red-400">{diffGroupes.nb_a_retirer}</strong>
            sortie(s) ·
            {diffGroupes.nb_inconnus} membre(s) laissés en place
          </p>

          {#if diffGroupes.sites_sans_eleve.length}
            <div class="rounded-lg border border-red-300 bg-red-50 p-3 text-sm dark:border-red-800 dark:bg-red-900/20">
              <p class="font-medium text-red-900 dark:text-red-200">
                Aucun élève pour l'année préparée sur :
                {diffGroupes.sites_sans_eleve.join(", ")}
              </p>
              <p class="mt-1 text-xs text-red-800 dark:text-red-300">
                Les groupes de ce ou ces sites ne seront pas touchés. Une classe
                vide est banale — un site entier, non : l'export Charlemagne
                correspondant n'a probablement pas été chargé.
              </p>
            </div>
          {/if}

          {#if diffGroupes.groupes_absents.length}
            <div class="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-900/20">
              <p class="font-medium text-amber-900 dark:text-amber-200">
                {diffGroupes.groupes_absents.length} groupe(s) déclarés dans la
                Table n'existent pas dans Google
              </p>
              <p class="mt-1 text-xs text-amber-800 dark:text-amber-300">
                Un groupe vide et un groupe absent se ressemblent — aucun des
                deux n'a de membre. Écrire dans le second échoue pourtant élève
                par élève. Les <strong>{diffGroupes.nb_retenus}</strong> ajouts
                qui leur étaient destinés sont retenus : à créer dans la console
                Google, ou à corriger dans la Table de correspondance.
              </p>
              <ul class="mt-2 max-h-40 overflow-auto font-mono text-xs text-amber-900 dark:text-amber-200">
                {#each diffGroupes.groupes_absents as g}<li>{g}</li>{/each}
              </ul>
            </div>
          {/if}
          {#each diffGroupes.avertissements as a}
            <p class="rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">{a}</p>
          {/each}
          <div class="max-h-96 overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Classe</th>
                  <th class="text-left">Groupe</th>
                  <th class="text-right">En place</th>
                  <th class="text-right">Entrent</th>
                  <th class="text-right">Sortent</th>
                </tr>
              </thead>
              <tbody>
                {#each diffGroupes.diffs as d (d.groupe)}
                  <tr class:ligne-douteuse={!d.existe || d.a_retirer.length > 0}>
                    <td class="whitespace-nowrap font-medium">{d.site} · {d.classe}</td>
                    <td class="whitespace-nowrap font-mono text-xs">
                      {d.groupe}
                      {#if !d.existe}
                        <span class="ml-1 rounded bg-amber-200 px-1 text-[10px] font-sans font-medium text-amber-900 dark:bg-amber-800 dark:text-amber-100">
                          absent
                        </span>
                      {/if}
                    </td>
                    <td class="text-right tabular-nums text-stone-500">{d.deja_membres}</td>
                    <td class="text-right tabular-nums">
                      {#if !d.existe}
                        <span class="text-amber-700 dark:text-amber-400">({d.retenus.length})</span>
                      {:else}
                        <span class="text-emerald-700 dark:text-emerald-400">{d.a_ajouter.length || ""}</span>
                      {/if}
                    </td>
                    <td class="text-right tabular-nums text-red-700 dark:text-red-400">
                      {d.a_retirer.length || ""}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    {/if}

    {#if job}
      <div class="card overflow-hidden">
        <div class="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
          <span class="font-semibold">{job.libelle}</span>
          <span class="tabular-nums text-stone-500 dark:text-stone-400">
            {job.nb_traitees} / {job.total}
          </span>
          {#if job.nb_echecs > 0}
            <span class="font-medium text-red-700 dark:text-red-400">{job.nb_echecs} échec(s)</span>
          {/if}
          {#if job.est_termine}
            <Bouton taille="sm" classe="ml-auto" onclick={() => (job = null)}>Fermer</Bouton>
          {/if}
        </div>
        <div class="h-1.5 w-full bg-stone-200 dark:bg-stone-700">
          <div
            class="h-full transition-all duration-300 {job.nb_echecs > 0 ? 'bg-amber-500' : 'bg-emerald-600'}"
            style="width: {Math.round(job.progression * 100)}%"
          ></div>
        </div>
        <div class="max-h-80 overflow-auto">
          <table class="tableau w-full text-sm">
            <tbody>
              {#each etapesVues as e (e.index)}
                <tr class:ligne-douteuse={e.statut === "echec"}>
                  <td class="w-8 px-3 py-1.5">
                    {#if e.statut === "reussi"}
                      <Check class="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                    {:else if e.statut === "echec"}
                      <X class="h-4 w-4 text-red-600 dark:text-red-400" />
                    {:else}
                      <Loader class="h-4 w-4 animate-spin text-stone-400" />
                    {/if}
                  </td>
                  <td class="px-3 py-1.5 text-xs">{e.libelle}</td>
                  <td class="px-3 py-1.5 text-xs">
                    {#if e.statut === "echec"}
                      <span class="text-red-700 dark:text-red-400">{e.message}</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}
  {/if}
</section>
