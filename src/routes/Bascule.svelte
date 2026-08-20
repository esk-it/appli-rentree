<script>
  import { onMount } from "svelte";
  import FolderTree from "@lucide/svelte/icons/folder-tree";
  import Download from "@lucide/svelte/icons/download";
  import Check from "@lucide/svelte/icons/check";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Modale from "$lib/components/Modale.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import Cloud from "@lucide/svelte/icons/cloud";
  import Check2 from "@lucide/svelte/icons/check";
  import X from "@lucide/svelte/icons/x";
  import Loader from "@lucide/svelte/icons/loader-2";
  import RotateCcw from "@lucide/svelte/icons/rotate-ccw";
  import { annees, bascule, enregistrerFichierBase64, googleApi, sites } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let listeSites = $state(/** @type {any[]} */ ([]));

  let anneeId = $state(/** @type {number | null} */ (null));
  let phase = $state("pre_rentree");
  let filtreSite = $state("");

  let rapport = $state(/** @type {any} */ (null));
  let chargement = $state(true);
  let erreur = $state("");
  let telechargement = $state(false);
  let confirmation = $state(false);
  let demandeConfirmation = $state(false);

  let optionsPhase = [
    { id: "pre_rentree", label: "1. Placement pré-rentrée" },
    { id: "definitive", label: "2. Bascule de rentrée" },
  ];

  // --- Canal d'application ------------------------------------------------
  // Le CSV reste le mode nominal et le secours : si Google refuse un compte,
  // on ne veut pas être bloqué. L'API évite l'aller-retour par la console.
  let canal = $state(/** @type {"csv"|"api"} */ ("csv"));
  let statutApi = $state(/** @type {any} */ (null));

  let job = $state(/** @type {any} */ (null));
  let lancement = $state(false);
  let sondage = /** @type {any} */ (null);

  let apiUtilisable = $derived(
    statutApi?.bibliotheques_disponibles && statutApi?.configuration_complete,
  );

  // Les lignes traitées d'abord, puis celle en cours : on regarde ce qui
  // vient de se passer, pas la fin d'une liste de mille noms.
  let etapesAffichees = $derived.by(() => {
    if (!job) return [];
    const faites = job.etapes.filter((e) => e.statut !== "attente");
    const echecs = faites.filter((e) => e.statut === "echec");
    // Les échecs restent visibles en tête : ce sont eux qui demandent une action
    return [...echecs, ...faites.filter((e) => e.statut !== "echec").slice(-60).reverse()];
  });

  let releve = $state(false);

  async function releverOu() {
    if (!anneeId) return;
    releve = true;
    try {
      const r = await bascule.relever({ anneeId, siteId: filtreSite || null });
      job = await googleApi.suivreJob(r.job_id);
      demarrerSondage();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      releve = false;
    }
  }

  async function lancerJob() {
    if (!anneeId) return;
    lancement = true;
    try {
      job = await googleApi.lancerJob({
        siteId: filtreSite || null,
        typePersonne: "eleve",
        anneeCibleId: anneeId,
        anneeSourceId: null,
        phase,
      });
      demarrerSondage();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      lancement = false;
    }
  }

  function demarrerSondage() {
    arreterSondage();
    sondage = setInterval(async () => {
      if (!job) return arreterSondage();
      try {
        job = await googleApi.suivreJob(job.id);
        if (job.est_termine) {
          arreterSondage();
          await rafraichir();
          const quoi = job.phase === "releve" ? "OU relevée(s)" : "déplacement(s) appliqué(s)";
          if (job.nb_echecs === 0) {
            notify.succes(`${job.nb_reussies} ${quoi}`);
          } else {
            notify.erreur(
              `${job.nb_echecs} échec(s) sur ${job.total} — voir le détail`,
            );
          }
        }
      } catch (e) {
        arreterSondage();
        notify.erreur(String(e).replace(/^Error:\s*/, ""));
      }
    }, 700);
  }

  function arreterSondage() {
    if (sondage) clearInterval(sondage);
    sondage = null;
  }

  async function annuler() {
    if (!job) return;
    try {
      job = await googleApi.annulerJob(job.id);
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    }
  }

  async function rejouer() {
    if (!job) return;
    try {
      job = await googleApi.rejouerEchecs(job.id);
      demarrerSondage();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    }
  }

  $effect(() => () => arreterSondage());

  // Les mouvements réellement à faire d'abord : c'est ce qu'on relit avant
  // d'importer. Les « déjà en place » n'apportent rien à la relecture.
  let aDeplacer = $derived(
    rapport ? rapport.mouvements.filter((m) => m.statut === "a_deplacer") : [],
  );
  let bloques = $derived(
    rapport ? rapport.mouvements.filter((m) => m.statut === "bloque") : [],
  );

  let parClasse = $derived.by(() => {
    /** @type {Map<string, any[]>} */
    const m = new Map();
    for (const mv of aDeplacer) {
      const cle = `${mv.site} · ${mv.classe ?? "sans classe"}`;
      if (!m.has(cle)) m.set(cle, []);
      m.get(cle).push(mv);
    }
    return [...m.entries()];
  });

  onMount(async () => {
    try {
      [listeAnnees, listeSites] = await Promise.all([annees.lister(), sites.lister()]);
      try {
        statutApi = await googleApi.statut();
      } catch {
        statutApi = null; // mode API indisponible : le CSV suffit
      }
      const triees = [...listeAnnees].sort((a, b) => b.libelle.localeCompare(a.libelle));
      anneeId = triees[0]?.id ?? null;
    } catch (e) {
      erreur = String(e);
    }
    await rafraichir();
  });

  async function rafraichir() {
    if (!anneeId) {
      chargement = false;
      return;
    }
    chargement = true;
    erreur = "";
    try {
      rapport = await bascule.planifier({ anneeId, phase, siteId: filtreSite || null });
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
      rapport = null;
    } finally {
      chargement = false;
    }
  }

  async function telechargerCsv() {
    telechargement = true;
    try {
      const r = await bascule.csv({ anneeId, phase, siteId: filtreSite || null });
      const { chemin, annule } = await enregistrerFichierBase64(
        r.nom_fichier, r.contenu_base64, "text/csv",
      );
      if (annule) return;
      notify.succes(
        `${r.nb_lignes} déplacement(s) — ${chemin ?? `${r.nom_fichier} dans ton dossier Téléchargements`}`,
        { duree: 8000 },
      );
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      telechargement = false;
    }
  }

  async function confirmerApplication() {
    confirmation = true;
    try {
      const r = await bascule.confirmer({
        anneeId, phase, siteId: filtreSite || null, mode: "reel",
      });
      notify.succes(r.message);
      demandeConfirmation = false;
      await rafraichir();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      confirmation = false;
    }
  }
</script>

<section class="space-y-4">
  <EnTetePage
    icon={FolderTree}
    titre="Bascule des OU Google"
    description="Les deux temps de la rentrée : d'abord tout le monde dans l'OU d'attente du site, puis chacun dans l'OU de sa classe le jour J."
  />

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  <div class="card p-3">
    <Segments bind:valeur={phase} options={optionsPhase} onChange={rafraichir} />

    <div class="mt-3 flex flex-wrap items-end gap-3 border-t border-stone-100 pt-3 dark:border-stone-800">
      <div>
        <label class="libelle-champ" for="b-annee">Année</label>
        <select id="b-annee" class="champ w-44" bind:value={anneeId} onchange={rafraichir}>
          {#each listeAnnees as a (a.id)}
            <option value={a.id}>{a.libelle}</option>
          {/each}
        </select>
      </div>
      <div>
        <label class="libelle-champ" for="b-site">Portée</label>
        <select id="b-site" class="champ w-48" bind:value={filtreSite} onchange={rafraichir}>
          <option value="">Les trois sites</option>
          {#each listeSites as s (s.id)}
            <option value={s.id}>{s.nom} seulement</option>
          {/each}
        </select>
      </div>

      <div class="ml-auto flex items-end gap-2">
        {#if apiUtilisable}
          <div>
            <span class="libelle-champ">Canal</span>
            <Segments
              bind:valeur={canal}
              taille="sm"
              options={[
                { id: "csv", label: "Fichier CSV" },
                { id: "api", label: "API Google" },
              ]}
            />
          </div>
        {/if}

        {#if canal === "csv"}
          <!--
            Bloqué aussi quand des élèves n'ont pas d'OU : télécharger un CSV
            partiel mènerait à l'importer sans pouvoir l'enregistrer ensuite,
            et la trace des OU appliquées divergerait de la réalité.
          -->
          <Bouton
            icon={Download}
            occupe={telechargement}
            disabled={!rapport || rapport.nb_a_deplacer === 0 || !rapport.est_applicable}
            onclick={telechargerCsv}
          >
            Télécharger le CSV
          </Bouton>
          <Bouton
            variante="primary"
            icon={Check}
            disabled={!rapport || rapport.nb_a_deplacer === 0 || !rapport.est_applicable}
            onclick={() => (demandeConfirmation = true)}
          >
            J'ai importé
          </Bouton>
        {:else}
          <!--
            Sans relevé, le programme ne connaît que les OU qu'il a lui-même
            demandées : pour un compte antérieur, il affiche « ? » faute de
            point de départ.
          -->
          <Bouton
            icon={RotateCcw}
            occupe={releve}
            disabled={job && !job.est_termine}
            onclick={releverOu}
          >
            Relever les OU actuelles
          </Bouton>
          <Bouton
            variante="primary"
            icon={Cloud}
            occupe={lancement}
            disabled={!rapport || rapport.nb_a_deplacer === 0 || !rapport.est_applicable
              || (job && !job.est_termine)}
            onclick={lancerJob}
          >
            Déplacer {rapport?.nb_a_deplacer ?? 0} élève(s)
          </Bouton>
        {/if}
      </div>
    </div>

    <p class="mt-3 text-xs text-stone-500 dark:text-stone-400">
      {#if phase === "pre_rentree"}
        Tous les élèves de l'année — entrants comme montants — rejoignent l'OU
        d'attente de leur site. Les listes de classe bougent encore à ce stade :
        les répartir maintenant obligerait à tout refaire.
      {:else}
        Chaque élève quitte l'OU d'attente pour l'OU définitive de sa classe.
        À faire une fois les répartitions arrêtées.
      {/if}
    </p>
  </div>

  {#if job}
    <div class="card overflow-hidden">
      <div class="flex flex-wrap items-center gap-3 border-b border-stone-200 px-3 py-2 dark:border-stone-700">
        <h2 class="text-sm font-semibold">{job.libelle}</h2>
        <span class="text-xs tabular-nums text-stone-500 dark:text-stone-400">
          {job.nb_traitees} / {job.total}
        </span>
        {#if job.nb_reussies > 0}
          <span class="text-xs text-emerald-700 dark:text-emerald-400">
            {job.nb_reussies} appliqué(s)
          </span>
        {/if}
        {#if job.nb_echecs > 0}
          <span class="text-xs font-medium text-red-700 dark:text-red-400">
            {job.nb_echecs} en échec
          </span>
        {/if}

        <div class="ml-auto flex gap-2">
          {#if !job.est_termine}
            <Bouton taille="sm" onclick={annuler}>Arrêter</Bouton>
          {:else if job.nb_echecs > 0}
            <Bouton taille="sm" icon={RotateCcw} onclick={rejouer}>
              Rejouer les {job.nb_echecs} échec(s)
            </Bouton>
          {/if}
          {#if job.est_termine}
            <Bouton taille="sm" onclick={() => (job = null)}>Fermer</Bouton>
          {/if}
        </div>
      </div>

      <!-- Barre d'avancement : la seule information lisible d'un coup d'œil
           quand mille lignes défilent. -->
      <div class="h-1.5 w-full bg-stone-200 dark:bg-stone-700">
        <div
          class="h-full transition-all duration-300 {job.nb_echecs > 0
            ? 'bg-amber-500'
            : 'bg-emerald-600'}"
          style="width: {Math.round(job.progression * 100)}%"
        ></div>
      </div>

      {#if job.erreur_fatale}
        <p class="border-b border-stone-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-stone-700 dark:bg-red-900/20 dark:text-red-300">
          {job.erreur_fatale}
        </p>
      {/if}
      {#if job.annule}
        <p class="border-b border-stone-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-stone-700 dark:bg-amber-900/20 dark:text-amber-200">
          Arrêté à ta demande. Ce qui était déjà appliqué l'est resté — relance
          pour traiter le reste.
        </p>
      {/if}

      <div class="max-h-96 overflow-auto">
        <table class="tableau w-full text-sm">
          <tbody>
            {#each etapesAffichees as e (e.index)}
              <tr class:ligne-douteuse={e.statut === "echec"}>
                <td class="w-8 px-3 py-1.5">
                  {#if e.statut === "reussi"}
                    <Check2 class="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                  {:else if e.statut === "echec"}
                    <X class="h-4 w-4 text-red-600 dark:text-red-400" />
                  {:else}
                    <Loader class="h-4 w-4 animate-spin text-stone-400" />
                  {/if}
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 font-mono text-xs">{e.email}</td>
                <td class="px-3 py-1.5 text-xs text-stone-600 dark:text-stone-400">
                  {#if e.statut === "echec"}
                    <span class="text-red-700 dark:text-red-400">{e.message}</span>
                  {:else}
                    {e.ou_visee ?? e.libelle}
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}

  {#if chargement}
    <div class="card p-4">
      <Squelette variante="ligne-tableau" nb={6} colonnes={5} />
    </div>
  {:else if !anneeId}
    <div class="card p-4">
      <EtatVide
        icon={FolderTree}
        titre="Aucune année ingérée"
        message="Dépose d'abord un export Charlemagne dans l'onglet Snapshots d'années."
      />
    </div>
  {:else if rapport}
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <div class="card p-3">
        <p class="text-xs uppercase tracking-wide text-stone-500 dark:text-stone-400">À déplacer</p>
        <p class="mt-1 text-2xl font-semibold tabular-nums">{rapport.nb_a_deplacer}</p>
      </div>
      <div class="card p-3">
        <p class="text-xs uppercase tracking-wide text-stone-500 dark:text-stone-400">Déjà en place</p>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-stone-500 dark:text-stone-400">
          {rapport.nb_deja_en_place}
        </p>
      </div>
      <div class="card p-3 {rapport.nb_bloques ? 'ring-1 ring-red-300 dark:ring-red-800' : ''}">
        <p class="text-xs uppercase tracking-wide text-stone-500 dark:text-stone-400">Bloqués</p>
        <p class="mt-1 text-2xl font-semibold tabular-nums {rapport.nb_bloques ? 'text-red-700 dark:text-red-400' : ''}">
          {rapport.nb_bloques}
        </p>
      </div>
    </div>

    {#if bloques.length}
      <div class="card border-l-4 border-red-500 p-3">
        <h2 class="flex items-center gap-2 text-sm font-semibold text-red-800 dark:text-red-300">
          <TriangleAlert class="h-4 w-4" />
          {bloques.length} élève(s) sans OU calculable — la bascule est refusée
        </h2>
        <p class="mt-1 text-xs text-stone-600 dark:text-stone-400">
          Aucune OU par défaut n'est attribuée : complète la Table de
          correspondance, puis reviens ici.
        </p>
        <ul class="mt-2 space-y-0.5 text-xs">
          {#each bloques.slice(0, 15) as m (m.personne_id)}
            <li class="text-stone-600 dark:text-stone-400">
              <span class="font-mono">{m.cle_pivot}</span>
              {m.prenom} {m.nom} — {m.motif}
            </li>
          {/each}
          {#if bloques.length > 15}
            <li class="text-stone-500">… et {bloques.length - 15} autre(s)</li>
          {/if}
        </ul>
      </div>
    {/if}

    {#if rapport.nb_a_deplacer === 0}
      <div class="card p-4">
        <EtatVide
          icon={Check}
          titre="Rien à déplacer"
          message={rapport.nb_deja_en_place > 0
            ? "Tous les élèves concernés sont déjà dans l'OU visée pour cette phase."
            : "Aucun élève ne correspond à cette année et cette portée."}
        />
      </div>
    {:else}
      <div class="space-y-4">
        {#each parClasse as [groupe, membres] (groupe)}
          <div class="card overflow-hidden">
            <div class="flex items-baseline justify-between bg-stone-100 px-3 py-1.5 dark:bg-stone-800">
              <h2 class="text-sm font-semibold">{groupe}</h2>
              <span class="text-xs tabular-nums text-stone-500 dark:text-stone-400">{membres.length}</span>
            </div>
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Nom</th>
                  <th class="text-left">Prénom</th>
                  <th class="text-left">Adresse mail</th>
                  <th class="text-left">Déplacement</th>
                </tr>
              </thead>
              <tbody>
                {#each membres as m (m.personne_id)}
                  <tr>
                    <td class="whitespace-nowrap font-medium">{m.nom}</td>
                    <td class="whitespace-nowrap">{m.prenom}</td>
                    <td class="whitespace-nowrap font-mono text-xs">{m.email ?? "—"}</td>
                    <td class="text-xs">
                      <span class="inline-flex items-center gap-1.5 font-mono">
                        <span class="text-stone-500 dark:text-stone-400">
                          {#if m.ou_appliquee}
                            {m.ou_appliquee}
                          {:else}
                            <span class="italic">OU inconnue</span>
                          {/if}
                        </span>
                        <ArrowRight class="h-3 w-3 shrink-0 text-stone-400" />
                        <span class="text-emerald-700 dark:text-emerald-400">{m.ou_visee}</span>
                      </span>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</section>

{#if demandeConfirmation}
  <Modale titre="Confirmer l'import dans Google" onFermer={() => (demandeConfirmation = false)}>
    <div class="space-y-3 text-sm text-stone-600 dark:text-stone-300">
      <p>
        Le programme n'agit pas sur Google : il prend acte de ce que
        <strong>tu</strong> as fait dans la console Admin.
      </p>
      <p>
        Confirme uniquement si tu as bien importé le CSV de
        <strong>{rapport?.phase_libelle}</strong> pour
        <strong>{rapport?.sites.join(", ")}</strong>.
        {rapport?.nb_a_deplacer} déplacement(s) seront alors enregistrés comme
        appliqués, et ne te seront plus proposés.
      </p>
    </div>

    {#snippet actions()}
      <Bouton onclick={() => (demandeConfirmation = false)}>Annuler</Bouton>
      <Bouton variante="primary" occupe={confirmation} onclick={confirmerApplication}>
        Oui, c'est importé
      </Bouton>
    {/snippet}
  </Modale>
{/if}
