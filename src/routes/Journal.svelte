<script>
  import { onMount } from "svelte";
  import History from "@lucide/svelte/icons/history";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import Search from "@lucide/svelte/icons/search";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { journal } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Ce qui a été fait, et quand.
   *
   * ## Pourquoi il fallait le montrer
   *
   * Le programme journalise depuis toujours : chaque ingestion, chaque
   * export, chaque déplacement laisse une trace avec ses paramètres et son
   * résultat. Aucun écran ne les montrait — la table existait pour personne.
   *
   * Or la question revient : *« pourquoi ce compte est-il là ? »*,
   * *« quand ai-je synchronisé KoXo pour la dernière fois ? »*, *« qu'est-ce
   * que j'ai importé le 15 septembre ? »*. En août prochain, quand le
   * référentiel ne collera pas à Charlemagne, c'est ici qu'on saura si
   * c'était un accident ou une décision.
   *
   * ## Ce qu'une ligne montre, et ce qu'elle cache
   *
   * Le résumé d'abord — quoi, quand, sur quelle année, avec quel résultat.
   * Le détail complet se déplie : paramètres et résultat tels qu'ils ont été
   * enregistrés. Les mots de passe n'y sont jamais : le journal les écarte à
   * l'écriture, et il vaut mieux perdre une information de mise au point que
   * consigner un secret.
   */

  let lignes = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let erreur = $state("");
  let depliee = $state(/** @type {number | null} */ (null));
  let filtreType = $state("");
  let recherche = $state("");

  const LIBELLES = {
    ingestion: "Ingestion",
    amorcage: "Amorçage",
    import_table: "Import de table",
    export: "Export",
    cycle_vie: "Cycle de vie",
    identifiant: "Identifiant",
    mouvement: "Mouvement",
    desinscription: "Désinscription",
  };

  const TEINTES = {
    ingestion: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
    export: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
    mouvement: "bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300",
    desinscription: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
    identifiant: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  };

  const teinte = (t) =>
    TEINTES[t] ?? "bg-stone-100 text-stone-700 dark:bg-stone-700 dark:text-stone-300";

  onMount(charger);

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      lignes = await journal.lister({ limite: 300 });
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
      notify.erreur(erreur);
    } finally {
      chargement = false;
    }
  }

  function quand(iso) {
    const d = new Date(iso);
    return d.toLocaleString("fr-FR", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  }

  /** Le chiffre qui résume l'opération, quand elle en porte un. */
  function resume(l) {
    const r = l.resultat ?? {};
    const parts = [];
    for (const [cle, valeur] of Object.entries(r)) {
      if (typeof valeur === "number" && valeur !== 0) {
        parts.push(`${valeur} ${cle.replace(/^nb_/, "").replace(/_/g, " ")}`);
      }
    }
    return parts.slice(0, 4).join(" · ");
  }

  let types = $derived([...new Set(lignes.map((l) => l.type_operation))].sort());

  let listeFiltree = $derived.by(() => {
    let r = lignes;
    if (filtreType) r = r.filter((l) => l.type_operation === filtreType);
    const q = recherche.trim().toLowerCase();
    if (q) {
      r = r.filter((l) =>
        `${l.type_operation} ${l.cible ?? ""} ${l.notes ?? ""} ${l.annee_libelle ?? ""}`
          .toLowerCase()
          .includes(q),
      );
    }
    return r;
  });
</script>

<section class="space-y-5">
  <EnTetePage
    icon={History}
    titre="Ce qui a été fait"
    description="Chaque ingestion, export et déplacement laisse une trace. C'est ici qu'on répond à « pourquoi ce compte est-il là ? », des mois plus tard."
  >
    {#snippet actions()}
      <Bouton icon={RefreshCw} occupe={chargement} onclick={charger}>Relire</Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if chargement && !lignes.length}
    <Squelette variante="ligne-tableau" nb={6} colonnes={4} />
  {:else if !lignes.length}
    <EtatVide
      icon={History}
      titre="Aucune opération enregistrée"
      message="Le journal se remplit au fil des ingestions, des exports et des déplacements."
    />
  {:else}
    <div class="card p-3">
      <div class="flex flex-wrap items-center gap-3">
        <div class="relative min-w-56 flex-1">
          <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
          <input class="champ pl-9" placeholder="Cible, note, année…" bind:value={recherche} />
        </div>
        <div class="flex flex-wrap gap-1">
          <button
            class="rounded-full border px-2.5 py-1 text-xs transition {filtreType === ''
              ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
              : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
            onclick={() => (filtreType = "")}
          >
            Tout <span class="tabular-nums">{lignes.length}</span>
          </button>
          {#each types as t (t)}
            <button
              class="rounded-full border px-2.5 py-1 text-xs transition {filtreType === t
                ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
              onclick={() => (filtreType = t)}
            >
              {LIBELLES[t] ?? t}
              <span class="tabular-nums">
                {lignes.filter((l) => l.type_operation === t).length}
              </span>
            </button>
          {/each}
        </div>
      </div>
    </div>

    <div class="card overflow-hidden">
      <div class="max-h-[max(24rem,calc(100vh-24rem))] overflow-auto">
        <table class="tableau">
          <thead class="entete-tableau">
            <tr>
              <th class="px-3 py-2 text-left"></th>
              <th class="px-3 py-2 text-left">Quand</th>
              <th class="px-3 py-2 text-left">Opération</th>
              <th class="px-3 py-2 text-left">Cible</th>
              <th class="px-3 py-2 text-left">Année</th>
              <th class="px-3 py-2 text-left">Résultat</th>
            </tr>
          </thead>
          <tbody class="corps-tableau">
            {#each listeFiltree as l (l.id)}
              <tr
                class="cursor-pointer transition-colors hover:bg-emerald-50/40 dark:hover:bg-emerald-900/20"
                onclick={() => (depliee = depliee === l.id ? null : l.id)}
              >
                <td class="py-1.5 pl-3 pr-1">
                  <ChevronRight
                    class="h-3.5 w-3.5 text-stone-300 transition-transform duration-150 dark:text-stone-600 {depliee === l.id ? 'rotate-90' : ''}"
                  />
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 text-xs tabular-nums text-stone-600 dark:text-stone-300">
                  {quand(l.date_creation)}
                </td>
                <td class="px-3 py-1.5">
                  <span class="rounded-full px-2 py-0.5 text-xs font-medium {teinte(l.type_operation)}">
                    {LIBELLES[l.type_operation] ?? l.type_operation}
                  </span>
                  {#if l.mode}
                    <span class="ml-1 text-xs text-stone-400">{l.mode}</span>
                  {/if}
                </td>
                <td class="px-3 py-1.5 text-xs">{l.cible ?? "—"}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-xs text-stone-500">
                  {l.annee_libelle ?? "—"}
                </td>
                <td class="px-3 py-1.5 text-xs text-stone-600 dark:text-stone-300">
                  {l.notes || resume(l) || "—"}
                </td>
              </tr>
              {#if depliee === l.id}
                <tr class="bg-stone-50/80 dark:bg-stone-800/50">
                  <td colspan="6" class="px-5 py-3">
                    <div class="grid gap-4 lg:grid-cols-2">
                      {#each [["Ce qui a été demandé", l.parametres], ["Ce qui en est sorti", l.resultat]] as [titre, bloc] (titre)}
                        <div>
                          <p class="mb-1 text-[11px] font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
                            {titre}
                          </p>
                          {#if bloc && Object.keys(bloc).length}
                            <dl class="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs">
                              {#each Object.entries(bloc) as [cle, valeur] (cle)}
                                <dt class="text-stone-500 dark:text-stone-400">{cle}</dt>
                                <dd class="min-w-0 break-words font-mono">
                                  {Array.isArray(valeur)
                                    ? valeur.slice(0, 12).join(", ") +
                                      (valeur.length > 12 ? ` … (${valeur.length})` : "")
                                    : String(valeur)}
                                </dd>
                              {/each}
                            </dl>
                          {:else}
                            <p class="text-xs text-stone-400">rien d'enregistré</p>
                          {/if}
                        </div>
                      {/each}
                    </div>
                    <p class="mt-2 text-[11px] text-stone-400">
                      Les mots de passe ne figurent jamais ici : le journal les
                      écarte à l'écriture.
                    </p>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
</section>
