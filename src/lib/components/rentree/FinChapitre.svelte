<script>
  import { CONTENU } from "$lib/rentree/etapes.js";

  /**
   * Un chapitre fini : ce qui a changé, constaté, et ce qui reste à
   * surveiller (maquette 7G). Le moment de souffler, et de voir que le
   * travail a laissé une trace.
   *
   * @typedef {Object} Props
   * @property {any} etat
   * @property {string} chapitreId
   * @property {(vue: any) => void} onAller
   */
  /** @type {Props} */
  let { etat, chapitreId, onAller } = $props();

  const TITRES = {
    ouvrir: "L'année est ouverte",
    eleves: "Les élèves et les professeurs sont chargés",
    comptes: "Tous les élèves ont leurs comptes",
    google: "Google est prêt pour la pré-rentrée",
    documents: "Les documents sont sortis",
    clore: "La rentrée est bouclée",
  };

  let rang = $derived(etat.chapitres.findIndex((c) => c.id === chapitreId));
  let chapitre = $derived(etat.chapitres[rang]);
  let suivant = $derived(etat.chapitres[rang + 1] ?? null);
  let etapes = $derived(etat.etapes.filter((e) => e.chapitre === chapitreId));
  let etapesSuivant = $derived(suivant ? etat.etapes.filter((e) => e.chapitre === suivant.id) : []);

  /** Avant → après, mesure par mesure, pour les étapes du chapitre. */
  let constats = $derived(
    etapes.flatMap((e) =>
      Object.entries(e.apres ?? {}).map(([id, apres]) => ({
        id,
        libelle: apres.libelle ?? id,
        avant: e.avant?.[id]?.valeur ?? null,
        apres: apres.valeur,
        bonne: apres.bonne,
      })),
    ),
  );
  let aSurveiller = $derived([
    ...etapes.flatMap((e) =>
      Object.values(e.apres ?? {})
        .filter((m) => m.bonne === false)
        .map((m) => ({ titre: m.libelle, texte: m.detail })),
    ),
    ...etapes
      .filter((e) => e.note)
      .map((e) => ({ titre: e.statut === "reportee" ? `${e.titre} — reportée` : e.titre, texte: e.note })),
  ]);
  let journal = $derived(
    etapes
      .flatMap((e) => [
        ...Object.entries(e.gestes_le ?? {}).map(([g, le]) => ({
          le,
          texte: CONTENU[e.id]?.gestes.find((x) => x.id === g)?.titre ?? g,
        })),
        ...(e.validee_le ? [{ le: e.validee_le, texte: `« ${e.titre} » validée`, validation: true }] : []),
      ])
      .sort((a, b) => a.le.localeCompare(b.le)),
  );

  const nombre = (n) => (n === null || n === undefined ? "—" : new Intl.NumberFormat("fr-FR").format(n));
  const heure = (iso) => iso.slice(11, 16);
  const jour = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
  let dates = $derived([...new Set(journal.map((j) => jour(j.le)))]);
</script>

{#if chapitre}
  <div
    class="grid min-h-[calc(100vh-9rem)] overflow-hidden rounded-2xl border border-stone-200 bg-white lg:grid-cols-[minmax(0,1fr)_400px] dark:border-stone-800 dark:bg-stone-950"
    style="--chap: {chapitre.couleur};"
  >
    <section class="flex flex-col px-8 py-10 lg:px-14">
      <button type="button" class="self-start text-sm text-stone-500 hover:underline dark:text-stone-400" onclick={() => onAller({ type: "fil" })}>
        ← La rentrée {etat.annee}
      </button>
      <p class="chap-texte mt-6 text-[11px] font-bold tracking-[0.08em] uppercase">Chapitre {rang + 1} terminé</p>
      <h1 class="titre-affiche mt-2 text-5xl leading-[1.05] text-balance text-stone-900 dark:text-stone-100">{TITRES[chapitre.id]}</h1>
      <p class="mt-4 max-w-xl text-[17px] text-stone-600 dark:text-stone-300">
        {etapes.length} étape{etapes.length > 1 ? "s" : ""}{dates.length ? `, ${dates.length > 1 ? `du ${dates[0]} au ${dates.at(-1)}` : `le ${dates[0]}`}` : ""}.
        {constats.length ? "Voici ce qui se constate maintenant." : ""}
      </p>

      {#if constats.length}
        <div class="mt-8 max-w-3xl">
          <div class="grid grid-cols-[minmax(0,1fr)_96px_96px] gap-4 pb-2 text-xs text-stone-500 dark:text-stone-400">
            <span>Ce qu'on a constaté</span><span class="text-right">Avant</span><span class="text-right">Après</span>
          </div>
          {#each constats as c (c.id)}
            {@const max = Math.max(c.avant ?? 0, c.apres ?? 0, 1)}
            <div class="grid grid-cols-[minmax(0,1fr)_96px_96px] items-center gap-4 border-t border-stone-200 py-3 dark:border-stone-800">
              <div class="min-w-0">
                <p class="text-sm font-semibold text-stone-900 dark:text-stone-100">{c.libelle}</p>
                <div class="relative mt-2 h-2 overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800">
                  <div class="absolute inset-y-0 left-0 rounded-full bg-stone-300 dark:bg-stone-600" style="width: {(100 * (c.avant ?? 0)) / max}%;"></div>
                  <div class="chap-plein absolute inset-y-0 left-0 rounded-full" style="width: {(100 * (c.apres ?? 0)) / max}%;"></div>
                </div>
              </div>
              <span class="text-right text-stone-500 tabular-nums dark:text-stone-400">{nombre(c.avant)}</span>
              <span class="titre-affiche text-right text-xl tabular-nums {c.bonne === false ? 'text-amber-700 dark:text-amber-400' : 'text-stone-900 dark:text-stone-100'}">{nombre(c.apres)}</span>
            </div>
          {/each}
        </div>
      {/if}

      <div class="mt-auto pt-10">
        {#if suivant}
          <button
            type="button"
            class="rounded-full px-7 py-3.5 text-[15px] font-bold text-white hover:brightness-110"
            style="background: color-mix(in srgb, {suivant.couleur} 58%, black);"
            onclick={() => onAller({ type: "etape", id: etapesSuivant.find((e) => e.statut !== "validee" && e.statut !== "reportee")?.id ?? etapesSuivant[0].id })}
          >
            Commencer le chapitre {rang + 2} · {suivant.titre} →
          </button>
          <p class="mt-2 text-sm text-stone-500 dark:text-stone-400">{etapesSuivant.length} étape{etapesSuivant.length > 1 ? "s" : ""}</p>
        {:else}
          <button type="button" class="chap-plein rounded-full px-7 py-3.5 text-[15px] font-bold text-white hover:brightness-110" onclick={() => onAller({ type: "fil" })}>
            Revenir au fil de la rentrée →
          </button>
        {/if}
      </div>
    </section>

    <aside class="flex flex-col gap-8 border-t border-stone-200 bg-stone-50 px-8 py-10 lg:border-t-0 lg:border-l dark:border-stone-800 dark:bg-stone-900/60">
      <div>
        <p class="libelle-champ">À garder à l'œil</p>
        {#if aSurveiller.length}
          <ul class="mt-3 flex flex-col gap-3 text-sm">
            {#each aSurveiller as s, i (i)}
              <li><b class="text-stone-900 dark:text-stone-100">{s.titre}</b> <span class="text-stone-600 dark:text-stone-300">— {s.texte}</span></li>
            {/each}
          </ul>
        {:else}
          <p class="mt-3 text-sm text-stone-600 dark:text-stone-300">Rien : tout ce qui se mesurait est bon.</p>
        {/if}
      </div>
      {#if journal.length}
        <div>
          <p class="libelle-champ">Ce qui a été fait</p>
          <ul class="mt-3 flex flex-col gap-2.5">
            {#each journal as j, i (i)}
              <li class="grid grid-cols-[96px_minmax(0,1fr)] gap-3 text-sm leading-snug">
                <span class="whitespace-nowrap text-stone-500 tabular-nums dark:text-stone-400">{jour(j.le)} · {heure(j.le)}</span>
                <span class="{j.validation ? 'chap-texte font-semibold' : 'text-stone-700 dark:text-stone-200'}">{j.texte}</span>
              </li>
            {/each}
          </ul>
        </div>
      {/if}
    </aside>
  </div>
{/if}

<style>
  .chap-texte {
    color: color-mix(in srgb, var(--chap) 62%, black);
  }
  :global(.dark) .chap-texte {
    color: color-mix(in srgb, var(--chap) 55%, white);
  }
  .chap-plein {
    background: color-mix(in srgb, var(--chap) 75%, black);
  }
</style>
