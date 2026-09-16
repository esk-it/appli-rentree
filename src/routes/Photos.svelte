<script>
  import { onMount } from "svelte";
  import Camera from "@lucide/svelte/icons/camera";
  import Download from "@lucide/svelte/icons/download";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Search from "@lucide/svelte/icons/search";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import { annees as anneesApi, photos } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";

  /**
   * Qui a sa photo, qui ne l'a pas.
   *
   * ## Pourquoi un écran et non une anomalie
   *
   * Le manque était détecté comme une anomalie parmi huit : un compteur qui
   * disait « 9 photos orphelines » sans dire lesquelles. Or la question est
   * toujours nominative — *« la liste, avec nom, prénom et classe »* — parce
   * qu'elle sert à relancer les professeurs principaux, classe par classe.
   *
   * ## Pourquoi le relevé ne part pas tout seul
   *
   * Un accès disque par élève sur un partage réseau. C'est trop cher pour
   * une ouverture d'écran ; ici c'est le sujet, alors on le demande et on
   * l'attend. Le résultat survit ensuite à la navigation.
   */

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));
  let inventaire = $state(lire("photos.inventaire", /** @type {any} */ (null)));
  let releveLe = $state(lire("photos.releveLe", /** @type {number | null} */ (null)));
  let occupe = $state(false);
  let erreur = $state("");
  let recherche = $state("");
  let classeRetenue = $state("");

  $effect(() => ecrire("photos.inventaire", inventaire));
  $effect(() => ecrire("photos.releveLe", releveLe));

  onMount(async () => {
    try {
      const a = await anneesApi.lister();
      listeAnnees = a;
      anneeId =
        [...a].sort((x, y) => y.libelle.localeCompare(x.libelle))[0]?.id ?? null;
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
    }
  });

  async function relever() {
    if (!anneeId) return;
    occupe = true;
    erreur = "";
    try {
      inventaire = await photos.inventaire(anneeId);
      releveLe = Date.now();
      notify.succes(
        inventaire.nb_sans === 0
          ? "Tout le monde a sa photo."
          : `${inventaire.nb_sans} photo(s) manquante(s) sur ${inventaire.nb_eleves}`,
        { duree: 8000 },
      );
    } catch (e) {
      inventaire = null;
      erreur = String(e).replace(/^Error:\s*/, "");
      notify.erreur(erreur, { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  let age = $derived.by(() => {
    if (!releveLe) return "";
    const m = Math.round((Date.now() - releveLe) / 60000);
    if (m < 2) return "à l'instant";
    if (m < 60) return `il y a ${m} min`;
    const h = Math.round(m / 60);
    return h < 24 ? `il y a ${h} h` : `il y a ${Math.round(h / 24)} j`;
  });

  let manquantes = $derived.by(() => {
    let r = inventaire?.manquantes ?? [];
    if (classeRetenue) r = r.filter((e) => e.classe === classeRetenue);
    const q = recherche.trim().toLowerCase();
    if (q) r = r.filter((e) => `${e.nom} ${e.prenom}`.toLowerCase().includes(q));
    return r;
  });

  /** Les classes incomplètes, les pires d'abord — c'est l'ordre des relances. */
  let classes = $derived(
    (inventaire?.classes_incompletes ?? []).map((c) => ({
      code: c,
      sans: inventaire.par_classe[c]?.sans ?? 0,
      avec: inventaire.par_classe[c]?.avec ?? 0,
    })),
  );
</script>

<section class="space-y-5">
  <EnTetePage
    icon={Camera}
    titre="Les photos"
    description="Qui a sa photo sur le partage, et surtout qui ne l'a pas — nommément, par classe, pour relancer les professeurs principaux."
  >
    {#snippet actions()}
      {#if inventaire && anneeId}
        <a class="btn-secondary" href={photos.urlClasseur(anneeId)}>
          <Download class="h-4 w-4" /> La liste en classeur
        </a>
      {/if}
      <Bouton variante="primary" icon={RefreshCw} occupe={occupe} onclick={relever}>
        {inventaire ? "Relever à nouveau" : "Relever le partage"}
      </Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if !inventaire}
    <EtatVide
      icon={Camera}
      titre="Le partage n'a pas encore été relu"
      message="Un accès disque par élève, sur le réseau : c'est trop cher pour partir tout seul à chaque ouverture. Lance le relevé quand le partage est monté."
    />
  {:else}
    {#if age && age !== "à l'instant"}
      <p class="text-xs text-stone-500 dark:text-stone-400">
        Relevé retrouvé — il date de <strong>{age}</strong>. Relance-le si des
        photos ont été déposées depuis.
      </p>
    {/if}

    <div class="grid gap-px overflow-hidden rounded-xl border border-stone-200 bg-stone-200 dark:border-stone-700 dark:bg-stone-700 sm:grid-cols-2 lg:grid-cols-4">
      <div class="bg-white p-4 dark:bg-stone-800">
        <p class="libelle-champ">Photos en place</p>
        <p class="mt-1 text-2xl font-semibold tabular-nums">
          {inventaire.nb_avec}
          <span class="text-sm font-normal text-stone-500">/ {inventaire.nb_eleves}</span>
        </p>
        <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-700">
          <div
            class="h-full bg-emerald-500 transition-all duration-500"
            style="width: {Math.round(inventaire.taux * 100)}%"
          ></div>
        </div>
      </div>
      <div class="bg-white p-4 dark:bg-stone-800">
        <p class="libelle-champ">Manquantes</p>
        <p class="mt-1 text-2xl font-semibold tabular-nums {inventaire.nb_sans ? 'text-amber-700 dark:text-amber-400' : ''}">
          {inventaire.nb_sans}
        </p>
        <p class="text-xs text-stone-500 dark:text-stone-400">
          dans {classes.length} classe{classes.length > 1 ? "s" : ""}
        </p>
      </div>
      <div class="bg-white p-4 dark:bg-stone-800 sm:col-span-2">
        <p class="libelle-champ">Partage lu</p>
        <p class="mt-1 truncate font-mono text-xs text-stone-600 dark:text-stone-300">
          {inventaire.dossier}
        </p>
        <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
          Le fichier est cherché sous « NOM Prénom », « NOM_Prénom »,
          « Prénom NOM » et le numéro de badge — une photo présente sous une
          autre forme n'est pas déclarée manquante.
        </p>
      </div>
    </div>

    {#if inventaire.nb_sans === 0}
      <div class="card flex items-center gap-3 p-5">
        <CheckCircle2 class="h-6 w-6 shrink-0 text-emerald-600 dark:text-emerald-400" />
        <div>
          <p class="font-medium">Tout le monde a sa photo.</p>
          <p class="text-sm text-stone-500 dark:text-stone-400">
            {inventaire.nb_eleves} élèves, aucun fichier introuvable sur le partage.
          </p>
        </div>
      </div>
    {:else}
      <!-- Par classe : c'est à cette maille qu'on relance. -->
      <div class="card p-4">
        <h2 class="titre-section mb-2">Par classe, les plus incomplètes d'abord</h2>
        <div class="flex flex-wrap gap-1.5">
          <button
            class="rounded-full border px-2.5 py-1 text-xs transition {classeRetenue === ''
              ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
              : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
            onclick={() => (classeRetenue = "")}
          >
            Toutes <span class="tabular-nums">{inventaire.nb_sans}</span>
          </button>
          {#each classes as c (c.code)}
            <button
              class="rounded-full border px-2.5 py-1 text-xs transition {classeRetenue === c.code
                ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
              title="{c.avec} photo(s) en place sur {c.avec + c.sans}"
              onclick={() => (classeRetenue = c.code)}
            >
              {c.code} <span class="tabular-nums font-semibold">{c.sans}</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="card overflow-hidden">
        <div class="border-b border-stone-200 p-3 dark:border-stone-700">
          <div class="relative max-w-md">
            <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
            <input class="champ pl-9" placeholder="Nom ou prénom…" bind:value={recherche} />
          </div>
        </div>
        <div class="max-h-[max(24rem,calc(100vh-30rem))] overflow-auto">
          <table class="tableau">
            <thead class="entete-tableau">
              <tr>
                <th class="px-3 py-2 text-left">Classe</th>
                <th class="px-3 py-2 text-left">Nom</th>
                <th class="px-3 py-2 text-left">Prénom</th>
                <th class="px-3 py-2 text-left">Site</th>
                <th class="px-3 py-2 text-right">Badge</th>
                <th class="px-3 py-2 text-left">Fichier attendu</th>
              </tr>
            </thead>
            <tbody class="corps-tableau">
              {#each manquantes as e (e.personne_id)}
                <tr>
                  <td class="whitespace-nowrap px-3 py-1.5 text-xs font-medium">{e.classe}</td>
                  <td class="px-3 py-1.5 font-medium">{e.nom}</td>
                  <td class="px-3 py-1.5">{e.prenom}</td>
                  <td class="px-3 py-1.5 text-xs text-stone-500">{e.site ?? "—"}</td>
                  <td class="px-3 py-1.5 text-right font-mono text-xs tabular-nums text-stone-500">
                    {e.badge ?? "—"}
                  </td>
                  <td class="truncate px-3 py-1.5 font-mono text-[11px] text-stone-400">
                    {e.chemin_attendu ?? ""}
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
