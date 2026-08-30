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
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import { annees, googleApi, sites } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  /** @type {{ onRotationTable?: (a: {chercher: string, remplacer: string}) => void }} */
  let { onRotationTable = null } = $props();

  let statutApi = $state(/** @type {any} */ (null));
  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let listeSites = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));

  let volet = $state("arborescence");

  // Vérification de comptes — lecture seule, après un import.
  let verification = $state(/** @type {any} */ (null));
  let verificationEnCours = $state(false);
  let adressesSaisies = $state("");
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

  // Deux avertissements ont leur propre encadré, plus lisible que la liste :
  // les répéter en dessous ferait douter qu'il s'agit du même. Le repère est
  // une portion de phrase, que les tests du service figent.
  let avertissementsRestants = $derived(
    (diffGroupes?.avertissements ?? []).filter(
      (a) =>
        !a.startsWith("Aucun élève pour l'année préparée") &&
        !a.includes("n'existent pas dans Google"),
    ),
  );

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

  let creations = $state(/** @type {any} */ (null));
  // Une classe sans effectif cette année n'a pas besoin de sa liste tout de
  // suite : créer quinze listes vides encombre la console sans rien débloquer.
  let seulementUtiles = $state(true);

  async function preparerCreations() {
    if (!anneeId) return;
    chargeGrp = true;
    try {
      creations = await googleApi.groupesACreer({ anneeId });
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      chargeGrp = false;
    }
  }

  async function creerGroupes() {
    chargeGrp = true;
    try {
      job = await googleApi.creerGroupes({ anneeId, seulementUtiles });
      creations = null;
      diffGroupes = null;
      sonder();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      chargeGrp = false;
    }
  }

  /**
   * Confronte quelques comptes Google au référentiel.
   *
   * Sans adresse saisie, le programme choisit lui-même : deux par site,
   * pris parmi les entrants — un compte ancien n'apprend rien sur l'import
   * du jour.
   */
  async function verifierComptes() {
    if (!anneeId) return;
    verificationEnCours = true;
    try {
      const adresses = adressesSaisies
        .split(/[\s,;]+/)
        .map((a) => a.trim())
        .filter(Boolean);
      verification = await googleApi.verifierComptes({
        anneeId,
        adresses: adresses.length ? adresses : null,
      });
      if (verification.tout_va_bien) {
        notify.succes(
          `${verification.nb_conformes} compte(s) conformes sur ${verification.nb_verifies}`,
        );
      } else {
        notify.avertissement(
          `${verification.nb_verifies - verification.nb_conformes} compte(s) à regarder`,
        );
      }
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      verificationEnCours = false;
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
          { id: "comptes", label: "Comptes" },
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
            <Bouton
              variante={confOu.avertissements.length ? "secondary" : "primary"}
              occupe={chargeOu}
              onclick={appliquerOu}
            >
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
              <p class="mt-2 rounded border border-amber-300 bg-amber-50 px-2 py-1.5 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
                {a}
              </p>
            {/each}
            {#if onRotationTable && confOu.annees_table.length === 1 && anneeCible && confOu.annees_table[0] !== anneeCible}
              <Bouton
                taille="sm"
                icon={RefreshCw}
                classe="mt-2"
                onclick={() =>
                  onRotationTable({
                    chercher: confOu.annees_table[0],
                    remplacer: anneeCible,
                  })}
              >
                Tourner la Table de {confOu.annees_table[0]} vers {anneeCible}
              </Bouton>
            {/if}
            {#each confOu.renommages as r}
              <p class="mt-2 font-mono text-xs {r.utile ? '' : 'text-stone-400 line-through dark:text-stone-500'}">
                {r.ancien} → {r.nouveau}
                <span class="text-stone-500">({r.nb_sous_ou} classes suivent)</span>
                {#if !r.utile}
                  <span class="ml-1 font-sans no-underline text-amber-700 dark:text-amber-400">
                    ne rapproche aucune OU attendue
                  </span>
                {/if}
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

    {:else if volet === "groupes"}
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

          <!-- Le calcul renvoyait déjà cette liste ; l'écran ne l'affichait
               pas. Deux classes de NDK — 61 élèves — n'avaient aucune adresse
               de groupe, et rien ici ne le disait. Un groupe absent de Google
               se voit ; une classe qui n'en déclare aucun ne se voit nulle
               part. -->
          {#if diffGroupes.classes_sans_groupe?.length}
            <div class="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-900/20">
              <p class="font-medium text-amber-900 dark:text-amber-200">
                {diffGroupes.classes_sans_groupe.length} classe(s) ne déclarent
                aucune adresse de groupe
              </p>
              <p class="mt-1 font-mono text-xs text-amber-900 dark:text-amber-200">
                {diffGroupes.classes_sans_groupe.join(", ")}
              </p>
              <p class="mt-1 text-xs text-amber-800 dark:text-amber-300">
                Leurs élèves n'entreront dans aucune liste, et rien d'autre ne
                le signalera : un groupe absent de Google se voit, une classe
                qui n'en déclare aucun ne se voit nulle part. Renseigne la
                colonne « Groupe Google » dans la
                <strong>Table de correspondance</strong>.
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
              {#if creations}
                <div class="mt-2 max-h-48 overflow-auto rounded bg-white/60 p-2 dark:bg-stone-900/40">
                  <table class="w-full text-xs">
                    <tbody>
                      {#each creations.groupes as g (g.adresse)}
                        <tr>
                          <td class="py-0.5 pr-3 font-mono">{g.adresse}</td>
                          <td class="py-0.5 pr-3">{g.nom}</td>
                          <td class="py-0.5 text-right tabular-nums text-stone-600 dark:text-stone-400">
                            {g.nb_membres_attendus} membre(s)
                          </td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
                <p class="mt-2 text-xs text-amber-800 dark:text-amber-300">
                  Le nom vient du libellé long de la Table — <code>2_1</code> ne
                  dit rien dans la console Google. Créer un groupe fait naître
                  une adresse de messagerie : rien n'est supprimé, jamais.
                </p>
              {:else}
                <ul class="mt-2 max-h-40 overflow-auto font-mono text-xs text-amber-900 dark:text-amber-200">
                  {#each diffGroupes.groupes_absents as g}<li>{g}</li>{/each}
                </ul>
              {/if}

              <div class="mt-3 flex flex-wrap gap-2">
                {#if !creations}
                  <Bouton taille="sm" icon={Search} occupe={chargeGrp} onclick={preparerCreations}>
                    Préparer la création
                  </Bouton>
                {:else}
                  <label class="flex items-center gap-2 text-xs text-amber-900 dark:text-amber-200">
                    <input type="checkbox" bind:checked={seulementUtiles} class="rounded" />
                    Seulement ceux qui débloquent des élèves
                    ({creations.nb_utiles} sur {creations.nb_a_creer})
                  </label>
                  <Bouton
                    taille="sm"
                    variante="primary"
                    occupe={chargeGrp}
                    onclick={creerGroupes}
                  >
                    Créer {seulementUtiles ? creations.nb_utiles : creations.nb_a_creer} groupe(s)
                  </Bouton>
                  <Bouton taille="sm" onclick={() => (creations = null)}>Annuler</Bouton>
                {/if}
              </div>
            </div>
          {/if}
          {#each avertissementsRestants as a}
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
    {:else if volet === "comptes"}
      <!-- Un import de masse repond « 238 creations reussies » et s'arrete la.
           Il ne dit pas ou les comptes ont atterri, ni s'ils sont actifs, ni
           si Google reclamera un changement de mot de passe. Ces trois-la
           decident pourtant si l'eleve pourra se connecter le jour J. -->
      <div class="card space-y-3 p-4">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Vérifier des comptes
        </h2>
        <p class="text-sm text-stone-600 dark:text-stone-400">
          Lit dans Google ce qu'un import a réellement produit, et le compare
          au référentiel. <strong>Lecture seule.</strong> Deux comptes par site
          suffisent : ils naissent du même fichier, d'un seul geste.
        </p>

        <label class="block">
          <span class="libelle-champ">Adresses (facultatif)</span>
          <input
            class="champ w-full font-mono text-sm"
            bind:value={adressesSaisies}
            placeholder="Laisse vide pour un échantillon d'entrants, deux par site"
          />
        </label>

        <div>
          <Bouton
            variante="primary"
            occupe={verificationEnCours}
            disabled={!apiUtilisable || !anneeId}
            onclick={verifierComptes}
          >
            Vérifier
          </Bouton>
        </div>

        {#if verification}
          <p class="text-sm">
            <strong class:text-emerald-700={verification.tout_va_bien}
                    class:dark:text-emerald-400={verification.tout_va_bien}>
              {verification.nb_conformes} / {verification.nb_verifies}
            </strong>
            conforme(s)
            {#if verification.nb_introuvables}
              · <strong class="text-red-700 dark:text-red-400">
                {verification.nb_introuvables} sans compte Google
              </strong>
            {/if}
          </p>

          <div class="overflow-x-auto">
            <table class="w-full text-left text-sm">
              <thead class="text-xs uppercase text-stone-500 dark:text-stone-400">
                <tr>
                  <th class="py-1 pr-3">Compte</th>
                  <th class="py-1 pr-3">Classe</th>
                  <th class="py-1 pr-3">Unité d'organisation</th>
                  <th class="py-1">État</th>
                </tr>
              </thead>
              <tbody>
                {#each verification.comptes as c (c.adresse)}
                  <tr class="border-t border-stone-200 align-top dark:border-stone-700">
                    <td class="py-1.5 pr-3 font-mono text-xs">{c.adresse}</td>
                    <td class="py-1.5 pr-3">{c.classe ?? "—"}</td>
                    <td class="py-1.5 pr-3 font-mono text-xs">
                      {c.ou_google ?? "—"}
                      {#if c.ou_reconnue === "pre_rentree"}
                        <span class="ml-1 text-xs text-stone-500">(OU d'attente)</span>
                      {:else if c.ou_reconnue === "definitive"}
                        <span class="ml-1 text-xs text-stone-500">(OU de classe)</span>
                      {/if}
                    </td>
                    <td class="py-1.5">
                      {#if c.est_conforme}
                        <span class="text-emerald-700 dark:text-emerald-400">conforme</span>
                      {:else}
                        <ul class="space-y-0.5 text-xs text-red-700 dark:text-red-400">
                          {#each c.anomalies as a}<li>• {a}</li>{/each}
                        </ul>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          {#each verification.avertissements as a}
            <p class="rounded-lg border border-stone-200 bg-stone-50 p-3 text-xs text-stone-700 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300">
              {a}
            </p>
          {/each}
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
