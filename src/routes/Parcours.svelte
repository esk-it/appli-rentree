<script>
  import { onMount, setContext } from "svelte";
  import Check from "@lucide/svelte/icons/check";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import ChevronLeft from "@lucide/svelte/icons/chevron-left";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import Target from "@lucide/svelte/icons/target";
  import HelpCircle from "@lucide/svelte/icons/help-circle";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Bouton from "$lib/components/Bouton.svelte";
  import { ETAPES, PHASES } from "$lib/parcours.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";

  import Sites from "./Sites.svelte";
  import TableCorrespondance from "./TableCorrespondance.svelte";
  import Amorcage from "./Amorcage.svelte";
  import Snapshots from "./Snapshots.svelte";
  import Arbitrage from "./Arbitrage.svelte";
  import Sortants from "./Sortants.svelte";
  import ConformiteGoogle from "./ConformiteGoogle.svelte";
  import ControleKoxo from "./ControleKoxo.svelte";
  import Exports from "./Exports.svelte";
  import Bascule from "./Bascule.svelte";
  import Chromebooks from "./Chromebooks.svelte";

  /**
   * La rentrée conduite, et non une boîte à outils.
   *
   * ## Ce que cet écran remplace
   *
   * Onze modules alignés dans un menu, et à l'utilisateur de savoir lequel
   * prendre, dans quel ordre, et ce qu'il fallait vérifier après. Cette
   * connaissance existait — elle était dans une frise décorative posée
   * au-dessus du menu, et dans la tête de qui avait fait la rentrée
   * précédente. Douze mois séparent deux campagnes : c'est plus qu'il n'en
   * faut pour tout oublier.
   *
   * Ici il n'y a plus de choix à faire. Il y a une étape courante, ce
   * qu'elle sert, ce qui peut mal tourner, l'outil pour la faire, et ce
   * qu'on doit voir quand elle a réussi. Le rail dit où l'on en est.
   *
   * ## Pourquoi l'outil est embarqué
   *
   * Envoyer vers le module et ramener ensuite laisserait l'aller-retour —
   * donc la possibilité de se perdre en route, et l'oubli de la
   * vérification au retour. L'écran du module s'affiche dans l'étape, sous
   * le rôle et les pièges, au-dessus de ce qu'on doit constater. Le
   * contexte `parcours.embarque` dit à son en-tête de s'effacer : l'étape
   * porte déjà le titre.
   *
   * ## Pourquoi on peut quand même sauter partout
   *
   * Une rentrée ne se déroule pas d'un trait. On revient sur une étape
   * faite, on en anticipe une autre, on reprend le lendemain. Le rail est
   * cliquable de bout en bout — l'ordre est une recommandation lourde, pas
   * une barrière.
   *
   * @typedef {Object} Props
   * @property {Record<string, any>} [etats]     - état calculé par le backend
   * @property {() => void} [onRelireAvancement]
   */
  /** @type {Props} */
  let { etats = {}, onRelireAvancement } = $props();

  setContext("parcours.embarque", true);

  /** L'étape ouverte survit à la navigation : une rentrée dure des jours. */
  let idEtape = $state(lire("parcours.etape", ETAPES[0].id));
  $effect(() => ecrire("parcours.etape", idEtape));

  let rang = $derived(Math.max(0, ETAPES.findIndex((e) => e.id === idEtape)));
  let etape = $derived(ETAPES[rang]);
  let phase = $derived(PHASES.find((p) => p.id === etape.phase));

  let nbFaites = $derived(
    ETAPES.filter((e) => etats[e.id]?.etat === "faite").length,
  );

  const COMPOSANTS = {
    sites: Sites,
    table_correspondance: TableCorrespondance,
    amorcage: Amorcage,
    snapshots: Snapshots,
    arbitrage: Arbitrage,
    sortants: Sortants,
    conformite_google: ConformiteGoogle,
    controle_koxo: ControleKoxo,
    exports: Exports,
    bascule: Bascule,
    chromebooks: Chromebooks,
  };

  let Outil = $derived(COMPOSANTS[etape.page] ?? null);

  const MARQUES = {
    faite: {
      pastille: "bg-emerald-500 text-white",
      texte: "text-stone-500 dark:text-stone-400",
    },
    a_faire: {
      pastille: "bg-stone-200 text-stone-500 dark:bg-stone-700 dark:text-stone-400",
      texte: "text-stone-700 dark:text-stone-300",
    },
    inconnu: {
      pastille: "bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-400",
      texte: "text-stone-700 dark:text-stone-300",
    },
  };

  const marque = (id) => MARQUES[etats[id]?.etat] ?? MARQUES.a_faire;

  function aller(pas) {
    const cible = ETAPES[rang + pas];
    if (cible) idEtape = cible.id;
  }

  onMount(() => onRelireAvancement?.());
</script>

<div class="flex flex-col gap-4">
  <!-- Où l'on en est, d'un coup d'œil -->
  <header class="flex flex-wrap items-baseline gap-x-4 gap-y-1">
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      La rentrée
    </h1>
    <p class="text-sm text-stone-500 dark:text-stone-400">
      étape <strong class="tabular-nums text-stone-700 dark:text-stone-200">{rang + 1}</strong>
      sur {ETAPES.length} · {nbFaites} constatée{nbFaites > 1 ? "s" : ""} faite{nbFaites > 1 ? "s" : ""}
    </p>
    <div class="ml-auto">
      <Bouton taille="sm" icon={RefreshCw} onclick={() => onRelireAvancement?.()}>
        Relire l'avancement
      </Bouton>
    </div>
  </header>

  <div class="grid gap-4 lg:grid-cols-[250px_minmax(0,1fr)]">
    <!-- Le rail : la progression, pas un menu -->
    <nav class="card h-fit p-2 lg:sticky lg:top-4" aria-label="Étapes de la rentrée">
      {#each PHASES as p (p.id)}
        <p class="px-2 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400 first:pt-1 dark:text-stone-500">
          {p.titre}
        </p>
        {#each ETAPES.filter((e) => e.phase === p.id) as e (e.id)}
          {@const i = ETAPES.indexOf(e)}
          {@const m = marque(e.id)}
          {@const actif = e.id === idEtape}
          <button
            class="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-[13px] transition-colors
                   {actif
                     ? 'bg-emerald-50 font-semibold text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-200'
                     : `${m.texte} hover:bg-stone-100 dark:hover:bg-stone-700/50`}"
            aria-current={actif ? "step" : undefined}
            onclick={() => (idEtape = e.id)}
          >
            <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold tabular-nums {m.pastille}">
              {#if etats[e.id]?.etat === "faite"}
                <Check class="h-3 w-3" />
              {:else if etats[e.id]?.etat === "inconnu"}
                ?
              {:else}
                {i + 1}
              {/if}
            </span>
            <span class="truncate">{e.titre}</span>
          </button>
        {/each}
      {/each}
    </nav>

    <!-- L'étape courante, en entier -->
    <div class="flex min-w-0 flex-col gap-4">
      <div class="card p-5">
        <p class="text-[11px] font-semibold uppercase tracking-widest text-emerald-700 dark:text-emerald-400">
          {phase?.titre} · étape {rang + 1}
        </p>
        <h2 class="mt-1 text-xl font-semibold text-stone-900 dark:text-stone-100">
          {etape.titre}
        </h2>
        <p class="mt-2 max-w-3xl text-sm leading-relaxed text-stone-600 dark:text-stone-300">
          {etape.role}
        </p>

        {#if etats[etape.id]}
          <p class="mt-3 flex items-start gap-1.5 text-xs text-stone-500 dark:text-stone-400">
            {#if etats[etape.id].etat === "faite"}
              <Check class="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
            {:else if etats[etape.id].etat === "inconnu"}
              <HelpCircle class="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-400" />
            {/if}
            {etats[etape.id].detail}
          </p>
        {/if}

        {#if etape.pieges?.length}
          <div class="mt-4 rounded-lg border-l-4 border-l-amber-500 bg-amber-50 p-3 dark:bg-amber-900/25">
            <p class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
              <AlertTriangle class="h-3.5 w-3.5" /> Ce qui peut mal tourner
            </p>
            <ul class="mt-1.5 flex flex-col gap-1.5">
              {#each etape.pieges as piege (piege)}
                <li class="text-sm leading-relaxed text-amber-900 dark:text-amber-200">
                  {piege}
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>

      <!-- L'outil de l'étape, chez elle -->
      {#if Outil}
        <div class="card p-5">
          {#if etape.ecran}
            <p class="mb-3 text-xs text-stone-500 dark:text-stone-400">
              Dans l'outil ci-dessous : <strong>{etape.ecran}</strong>.
            </p>
          {/if}
          <!-- `{#key}` remonte l'outil à chaque changement d'étape : deux
               étapes partagent parfois le même écran, et le réutiliser
               laisserait l'onglet de la précédente. -->
          {#key etape.id}
            <Outil />
          {/key}
        </div>
      {/if}

      <!-- Ce qu'on doit constater, et la suite -->
      <div class="card flex flex-wrap items-center gap-4 p-4">
        {#if etape.reperer}
          <div class="min-w-56 flex-1">
            <p class="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
              <Target class="h-3.5 w-3.5" /> Ce qu'on doit voir
            </p>
            <p class="mt-0.5 text-sm text-stone-700 dark:text-stone-200">{etape.reperer}</p>
          </div>
        {/if}
        <div class="ml-auto flex items-center gap-2">
          <Bouton icon={ChevronLeft} disabled={rang === 0} onclick={() => aller(-1)}>
            Précédente
          </Bouton>
          <Bouton
            variante="primary"
            disabled={rang >= ETAPES.length - 1}
            onclick={() => aller(1)}
          >
            Étape suivante
            <ChevronRight class="h-4 w-4" />
          </Bouton>
        </div>
      </div>
    </div>
  </div>
</div>
