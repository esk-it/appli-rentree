<script>
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import ExternalLink from "@lucide/svelte/icons/external-link";
  import Check from "@lucide/svelte/icons/check";
  import RotateCcw from "@lucide/svelte/icons/rotate-ccw";
  import Shuffle from "@lucide/svelte/icons/shuffle";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import { MOUVEMENTS, mouvementParId } from "$lib/consequences.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";

  /**
   * Ce qu'un mouvement entraîne.
   *
   * ## Pourquoi des cases à cocher et non un bouton
   *
   * Presque aucune conséquence n'est automatisable : elles vivent dans
   * Charlemagne, dans PMB, dans le portail Sodexo, ou au bout d'un
   * tournevis. Prétendre les enchaîner d'un clic obligerait à mentir sur
   * celles qu'on ne fait pas.
   *
   * Ce qu'on peut faire, c'est **ne rien oublier**. Un mouvement en cours
   * d'année est rare et isolé : trois en novembre, deux en février, et
   * entre les deux on a oublié qu'il fallait aussi reprendre PMB. Ce qu'on
   * oublie ne se voit pas tout de suite — la carte n'ouvre plus une porte
   * en janvier, l'élève n'est pas au self en mars, et personne ne fait le
   * lien.
   *
   * ## Le cochage survit
   *
   * Un mouvement se traite sur plusieurs jours : on crée le compte le
   * lundi, la carte arrive le jeudi. Les cases cochées survivent donc à la
   * navigation et à la fermeture de l'écran — jusqu'à ce qu'on reparte de
   * zéro pour la personne suivante.
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  let idMouvement = $state(lire("bouge.mouvement", MOUVEMENTS[0].id));
  let faites = $state(lire("bouge.faites", /** @type {Record<string, boolean>} */ ({})));
  let concerne = $state(lire("bouge.concerne", ""));

  $effect(() => ecrire("bouge.mouvement", idMouvement));
  $effect(() => ecrire("bouge.faites", faites));
  $effect(() => ecrire("bouge.concerne", concerne));

  let mouvement = $derived(mouvementParId(idMouvement));
  let cle = (c) => `${idMouvement}.${c.id}`;
  let nbFaites = $derived(mouvement.consequences.filter((c) => faites[cle(c)]).length);
  let reste = $derived(mouvement.consequences.length - nbFaites);

  const TONS = {
    emerald: "border-l-emerald-500",
    amber: "border-l-amber-500",
    sky: "border-l-sky-500",
  };

  const ICONES = { arrivee: ArrowRight, depart: RotateCcw, changement: Shuffle };

  function basculer(c) {
    faites = { ...faites, [cle(c)]: !faites[cle(c)] };
  }

  /** Repartir de zéro pour la personne suivante. */
  function recommencer() {
    const restant = { ...faites };
    for (const c of mouvement.consequences) delete restant[cle(c)];
    faites = restant;
    concerne = "";
  }
</script>

<section class="space-y-5">
  <EnTetePage
    icon={Shuffle}
    titre="Quelqu'un bouge"
    description="Un élève arrive, part ou change de classe — et sept ou huit systèmes doivent suivre. Voici lesquels, et ce qui casse si on en oublie un."
  />

  <!-- Le mouvement : trois cas, un seul à la fois. -->
  <div class="grid gap-3 sm:grid-cols-3">
    {#each MOUVEMENTS as m (m.id)}
      {@const Icone = ICONES[m.id] ?? ArrowRight}
      {@const actif = m.id === idMouvement}
      <button
        class="card flex flex-col gap-1 border-l-4 p-4 text-left transition-shadow {TONS[m.ton]}
               {actif ? 'ring-2 ring-emerald-500' : 'hover:shadow'}"
        onclick={() => (idMouvement = m.id)}
      >
        <span class="flex items-center gap-2 font-semibold">
          <Icone class="h-4 w-4 shrink-0" />
          {m.titre}
        </span>
        <span class="text-xs leading-relaxed text-stone-500 dark:text-stone-400">
          {m.resume}
        </span>
      </button>
    {/each}
  </div>

  <div class="card flex flex-wrap items-center gap-4 p-4">
    <div class="min-w-48 flex-1">
      <label class="libelle-champ" for="bouge-qui">De qui s'agit-il ?</label>
      <input
        id="bouge-qui"
        class="champ"
        placeholder="Nom de l'élève — pour t'y retrouver si tu reviens demain"
        bind:value={concerne}
      />
    </div>
    <div class="flex items-center gap-3">
      <p class="text-sm">
        <strong class="tabular-nums">{nbFaites}</strong>
        <span class="text-stone-500">/ {mouvement.consequences.length} fait{nbFaites > 1 ? "s" : ""}</span>
        {#if reste === 0}
          <span class="ml-2 text-emerald-700 dark:text-emerald-400">— rien n'a été oublié.</span>
        {/if}
      </p>
      {#if nbFaites > 0}
        <Bouton taille="sm" icon={RotateCcw} onclick={recommencer}>
          Personne suivante
        </Bouton>
      {/if}
    </div>
  </div>

  <div class="flex flex-col gap-2">
    {#each mouvement.consequences as c, i (c.id)}
      {@const fait = Boolean(faites[cle(c)])}
      <div
        class="card flex flex-wrap items-start gap-3 p-4 transition-opacity {fait ? 'opacity-60' : ''}"
      >
        <button
          class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border transition
                 {fait
                   ? 'border-emerald-600 bg-emerald-600 text-white'
                   : 'border-stone-300 text-transparent hover:border-emerald-400 dark:border-stone-600'}"
          aria-label="Marquer « {c.titre} » comme fait"
          aria-pressed={Boolean(fait)}
          onclick={() => basculer(c)}
        >
          <Check class="h-4 w-4" />
        </button>

        <div class="min-w-0 flex-1">
          <p class="font-medium {fait ? 'line-through decoration-stone-400' : ''}">
            <span class="mr-1.5 font-mono text-xs text-stone-400">{i + 1}</span>
            {c.titre}
            {#if c.ailleurs}
              <span class="ml-1.5 rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-normal text-stone-600 dark:bg-stone-700 dark:text-stone-300">
                {c.ailleurs}
              </span>
            {/if}
          </p>
          <p class="mt-0.5 text-sm text-stone-600 dark:text-stone-300">{c.pourquoi}</p>
          {#if c.piege}
            <p class="mt-1 flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
              <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {c.piege}
            </p>
          {/if}
        </div>

        {#if c.page}
          <Bouton taille="sm" icon={ArrowRight} onclick={() => onNaviguer?.(c.page)}>
            Y aller
          </Bouton>
        {:else}
          <span class="flex items-center gap-1 text-xs text-stone-400">
            <ExternalLink class="h-3.5 w-3.5" /> hors programme
          </span>
        {/if}
      </div>
    {/each}
  </div>
</section>
