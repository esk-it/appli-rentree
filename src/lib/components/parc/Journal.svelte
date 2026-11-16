<script>
  import Search from "@lucide/svelte/icons/search";
  import Squelette from "$lib/components/Squelette.svelte";
  import { parc } from "$lib/api.js";
  import { GESTES, messageErreur } from "$lib/parc.js";

  /**
   * Tout ce qui a été fait au parc, du plus récent au plus ancien.
   *
   * C'est la réponse à « à qui avais-je donné cette machine en
   * septembre ? » et à « combien de casses cette année ? ». Les lignes ne
   * se modifient pas : un geste annulé se corrige par un autre geste.
   *
   * @typedef {Object} Props
   * @property {Record<string, string>} raisons
   * @property {any[]} personnes
   * @property {(serie: string) => void} onOuvrir
   * @property {number} [version] - change après chaque geste : on relit
   */
  /** @type {Props} */
  let { raisons = {}, personnes = [], onOuvrir, version = 0 } = $props();

  let lignes = $state(/** @type {any[] | null} */ (null));
  let erreur = $state("");
  let recherche = $state("");
  let geste = $state("");

  async function charger() {
    try {
      lignes = await parc.journal({ limite: 1000 });
    } catch (e) {
      erreur = messageErreur(e);
    }
  }
  // Relu à l'ouverture, puis après chaque geste.
  $effect(() => {
    version;
    charger();
  });

  const noms = $derived(new Map(personnes.map((p) => [p.adresse, `${p.prenom} ${p.nom}`])));
  const qui = (x) => (x ? noms.get(x) ?? x : "");

  let filtrees = $derived.by(() => {
    const q = recherche.trim().toLowerCase();
    return (lignes ?? []).filter((m) => {
      if (geste && m.geste !== geste) return false;
      if (!q) return true;
      return [m.serie, m.autre_serie, m.de, m.vers, qui(m.de), qui(m.vers), m.precision, raisons[m.raison]]
        .some((c) => (c ?? "").toLowerCase().includes(q));
    });
  });

  /** Combien de chaque raison : « combien de casses cette année ». */
  let parRaison = $derived.by(() => {
    const r = {};
    for (const m of lignes ?? []) {
      // Un échange écrit deux lignes : on compte celle de la machine qui part.
      if (!m.raison || m.objet !== "chromebook" || m.de === "stock") continue;
      if (!["echange", "reprise", "reforme"].includes(m.geste)) continue;
      r[m.raison] = (r[m.raison] ?? 0) + 1;
    }
    return Object.entries(r).sort((a, b) => b[1] - a[1]);
  });

  const heure = (iso) =>
    new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
</script>

<div class="space-y-3">
  {#if parRaison.length}
    <p class="text-sm text-stone-600 dark:text-stone-300">
      Machines remplacées ou reprises :
      {#each parRaison as [r, n], i (r)}
        <span class="whitespace-nowrap"><strong class="tabular-nums">{n}</strong> {(raisons[r] ?? r).toLowerCase()}</span>{i < parRaison.length - 1 ? " · " : ""}
      {/each}
    </p>
  {/if}

  <div class="flex flex-wrap items-center gap-2">
    <div class="relative min-w-64 flex-1">
      <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
      <input class="champ pl-9" placeholder="Série, personne, précision…" bind:value={recherche} />
    </div>
    <select class="champ max-w-48 text-xs" bind:value={geste} aria-label="Filtrer par geste">
      <option value="">Tous les gestes</option>
      {#each Object.entries(GESTES) as [id, label] (id)}
        <option value={id}>{label}</option>
      {/each}
    </select>
  </div>

  {#if erreur}
    <p class="text-sm text-red-700">{erreur}</p>
  {:else if lignes === null}
    <Squelette variante="ligne-tableau" nb={5} colonnes={4} />
  {:else if !filtrees.length}
    <p class="py-8 text-center text-sm text-stone-500">
      {lignes.length ? "Aucun geste ne correspond." : "Aucun geste noté pour l'instant : le journal commence avec le premier échange."}
    </p>
  {:else}
    <div class="overflow-x-auto">
      <table class="tableau min-w-[52rem]">
        <thead class="entete-tableau">
          <tr>
            <th class="px-3 py-2 text-left">Quand</th>
            <th class="px-3 py-2 text-left">Geste</th>
            <th class="px-3 py-2 text-left">Quoi</th>
            <th class="px-3 py-2 text-left">De → vers</th>
            <th class="px-3 py-2 text-left">Pourquoi</th>
          </tr>
        </thead>
        <tbody class="corps-tableau">
          {#each filtrees as m (m.id)}
            <tr>
              <td class="whitespace-nowrap px-3 py-1.5 text-xs tabular-nums text-stone-500">{heure(m.quand)}</td>
              <td class="px-3 py-1.5 text-sm font-medium">{GESTES[m.geste] ?? m.geste}</td>
              <td class="px-3 py-1.5">
                {#if m.objet === "chromebook"}
                  <button class="font-mono text-xs text-emerald-700 hover:underline dark:text-emerald-400" onclick={() => onOuvrir(m.serie)}>
                    {m.serie}
                  </button>
                {:else}
                  <span class="font-mono text-xs">{m.serie}</span>
                {/if}
                {#if m.autre_serie}
                  <span class="text-xs text-stone-500">⇄ {m.autre_serie}</span>
                {/if}
              </td>
              <td class="px-3 py-1.5 text-sm">
                {qui(m.de)}{#if m.de && m.vers} → {/if}{qui(m.vers)}
                {#if m.google}<span class="block text-xs text-stone-500">Google : {m.google}</span>{/if}
              </td>
              <td class="px-3 py-1.5 text-xs text-stone-600 dark:text-stone-300">
                {#if m.raison}{raisons[m.raison] ?? m.raison}{/if}{#if m.raison && m.precision} — {/if}{m.precision ?? ""}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
