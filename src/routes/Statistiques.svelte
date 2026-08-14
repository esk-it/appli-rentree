<script>
  import { onMount } from "svelte";
  import BarChart3 from "@lucide/svelte/icons/bar-chart-3";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Building2 from "@lucide/svelte/icons/building-2";
  import Scale from "@lucide/svelte/icons/scale";
  import ShieldAlert from "@lucide/svelte/icons/shield-alert";
  import ShieldCheck from "@lucide/svelte/icons/shield-check";
  import History from "@lucide/svelte/icons/history";
  import BarChart from "$lib/components/BarChart.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import StatCard from "$lib/components/StatCard.svelte";
  import { annees, journal, statistiques } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let ref = $state(/** @type {null | any} */ (null));
  let listeAnnees = $state([]);
  let anneeChoisie = $state(/** @type {null | number} */ (null));
  let statsAnnee = $state(/** @type {null | any} */ (null));
  let erreur = $state("");

  // Anomalies et journal
  let anomalies = $state(/** @type {null | any} */ (null));
  let verifierPhotos = $state(false);
  let historique = $state([]);
  let comparaisons = $state(/** @type {Record<number, any>} */ ({}));

  onMount(async () => {
    try {
      [ref, listeAnnees] = await Promise.all([statistiques.referentiel(), annees.lister()]);
      if (listeAnnees.length > 0) {
        anneeChoisie = listeAnnees[0].id;
        await chargerAnnee();
      }
      await Promise.all([chargerAnomalies(), chargerHistorique()]);
    } catch (e) {
      erreur = String(e);
    }
  });

  async function chargerAnomalies() {
    try {
      anomalies = await statistiques.anomalies({
        anneeId: anneeChoisie,
        verifierPhotos,
      });
    } catch (e) {
      erreur = String(e);
    }
  }

  async function chargerHistorique() {
    try {
      historique = await journal.lister({ limite: 30 });
    } catch (e) {
      erreur = String(e);
    }
  }

  async function comparer(g) {
    try {
      const c = await journal.comparaison(g.id);
      comparaisons = { ...comparaisons, [g.id]: c };
      if (!c.trouvee) {
        notify.info("Aucune opération comparable dans l'historique");
      } else if (c.nb_aberrations > 0) {
        notify.avertissement(`${c.nb_aberrations} écart(s) notable(s) détecté(s)`);
      }
    } catch (e) {
      notify.erreur(String(e));
    }
  }

  function couleurGravite(g) {
    return {
      bloquant: "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20",
      attention: "border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/20",
      information: "border-stone-200 bg-stone-50 dark:border-stone-700 dark:bg-stone-800",
    }[g] ?? "border-stone-200";
  }

  function formaterDate(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleString("fr-FR", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  }

  async function chargerAnnee() {
    if (!anneeChoisie) return;
    try {
      statsAnnee = await statistiques.annee(anneeChoisie);
      await chargerAnomalies();
    } catch (e) {
      erreur = String(e);
    }
  }

</script>

<section class="space-y-5">
  <EnTetePage
    icon={BarChart3}
    ton="sky"
    titre="Statistiques"
    description="Vue instantanée du référentiel, anomalies détectées et journal des opérations."
  />

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if ref}
    <div class="anim-cascade grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatCard
        label="Personnes"
        value={ref.nb_personnes_total}
        icon={Users2}
        hint="{ref.nb_eleves_total} él. · {ref.nb_adultes_total} ad."
      />
      <StatCard label="Sites" value={ref.nb_sites} icon={Building2} variante="info" />
      <StatCard
        label="Classes déclarées"
        value={ref.nb_classes_table ?? 0}
        icon={BarChart3}
      />
      <StatCard
        label="Arbitrages"
        value={ref.nb_arbitrages_en_attente}
        icon={Scale}
        variante={ref.nb_arbitrages_en_attente > 0 ? "warning" : "success"}
        hint="sur {ref.nb_arbitrages_en_attente + ref.nb_arbitrages_tranches} au total"
      />
    </div>
  {/if}

  {#if listeAnnees.length > 0}
    <div class="card p-4 space-y-3">
      <div class="flex items-center justify-between gap-3">
        <h2 class="text-lg font-semibold">Détail par année</h2>
        <select
          bind:value={anneeChoisie}
          onchange={chargerAnnee}
          class="rounded-lg border border-stone-300 px-3 py-1 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          {#each listeAnnees as a (a.id)}
            <option value={a.id}>{a.libelle}</option>
          {/each}
        </select>
      </div>

      {#if statsAnnee}
        <p class="text-sm font-semibold text-stone-700 dark:text-stone-300">
          {statsAnnee.nb_personnes} personne(s)
          — {statsAnnee.nb_eleves} él., {statsAnnee.nb_adultes} ad.
        </p>

        <div class="grid grid-cols-1 gap-5 md:grid-cols-2">
          <div>
            <h3 class="titre-section mb-2">Par site</h3>
            <BarChart
              donnees={statsAnnee.par_site.map((v) => ({ cle: v.label, valeur: v.valeur }))}
              couleur="bg-emerald-500"
              afficherPart
            />
          </div>

          <div>
            <h3 class="titre-section mb-2">Par régime</h3>
            <BarChart
              donnees={statsAnnee.par_regime.map((v) => ({ cle: v.label, valeur: v.valeur }))}
              couleur="bg-sky-500"
              afficherPart
            />
          </div>

          {#if statsAnnee.par_niveau.length > 0}
            <div>
              <h3 class="titre-section mb-2">Par niveau</h3>
              <BarChart
                donnees={statsAnnee.par_niveau.map((v) => ({ cle: v.label, valeur: v.valeur }))}
                couleur="bg-indigo-500"
                maxLignes={12}
              />
            </div>
          {/if}

          {#if statsAnnee.par_etablissement_charlemagne.length > 0}
            <div>
              <h3 class="titre-section mb-2">Par établissement Charlemagne</h3>
              <BarChart
                donnees={statsAnnee.par_etablissement_charlemagne.map((v) => ({
                  cle: v.label,
                  valeur: v.valeur,
                }))}
                couleur="bg-amber-500"
                afficherPart
              />
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  <!-- Anomalies -->
  {#if anomalies}
    <div class="card p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="flex items-center gap-2 text-lg font-semibold">
          {#if anomalies.est_sain}
            <ShieldCheck class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
          {:else}
            <ShieldAlert class="h-5 w-5 text-red-600 dark:text-red-400" />
          {/if}
          Anomalies
        </h2>
        <label class="flex items-center gap-2 text-xs text-stone-600 dark:text-stone-400">
          <input
            type="checkbox"
            bind:checked={verifierPhotos}
            onchange={chargerAnomalies}
            class="h-4 w-4 rounded border-stone-300 text-emerald-700 focus:ring-emerald-500"
          />
          Vérifier les photos (accès disque)
        </label>
      </div>

      {#if anomalies.anomalies.length === 0}
        <p class="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-200">
          Aucune anomalie détectée — le référentiel est cohérent.
        </p>
      {:else}
        {#each anomalies.anomalies as a (a.type)}
          <div class="rounded-lg border p-3 text-sm {couleurGravite(a.gravite)}">
            <div class="flex items-start justify-between gap-2">
              <p class="font-medium text-stone-900 dark:text-stone-100">{a.libelle}</p>
              <span class="shrink-0 rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide dark:bg-stone-900/40">
                {a.gravite}
              </span>
            </div>
            {#if a.action_suggeree}
              <p class="mt-1 text-xs text-stone-700 dark:text-stone-300">{a.action_suggeree}</p>
            {/if}
            {#if a.details.length > 0}
              <details class="mt-2">
                <summary class="cursor-pointer text-xs text-stone-600 dark:text-stone-400">
                  Voir le détail
                </summary>
                <ul class="mt-1 space-y-0.5 font-mono text-xs text-stone-600 dark:text-stone-400">
                  {#each a.details as d}
                    <li>{d}</li>
                  {/each}
                  {#if a.nb_concernes > a.details.length}
                    <li class="text-stone-400">… et {a.nb_concernes - a.details.length} autre(s)</li>
                  {/if}
                </ul>
              </details>
            {/if}
          </div>
        {/each}
      {/if}
    </div>
  {/if}

  <!-- Journal des opérations -->
  {#if historique.length > 0}
    <div class="card p-4 space-y-3">
      <h2 class="flex items-center gap-2 text-lg font-semibold">
        <History class="h-5 w-5 text-stone-500" />
        Journal des opérations
      </h2>
      <p class="text-xs text-stone-500 dark:text-stone-400">
        Chaque opération est tracée avec ses paramètres et ses compteurs.
        « Comparer » met le résultat en regard de la même opération sur une
        autre année, pour repérer un chiffre aberrant.
      </p>

      <div class="overflow-hidden rounded-lg border border-stone-200 dark:border-stone-700">
        <table class="min-w-full divide-y divide-stone-200 text-sm dark:divide-stone-700">
          <thead class="bg-stone-50 text-xs uppercase tracking-wide text-stone-500 dark:bg-stone-800">
            <tr>
              <th class="px-3 py-2 text-left">Date</th>
              <th class="px-3 py-2 text-left">Opération</th>
              <th class="px-3 py-2 text-left">Cible</th>
              <th class="px-3 py-2 text-left">Année</th>
              <th class="px-3 py-2 text-left">Résultat</th>
              <th class="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-stone-100 dark:divide-stone-800">
            {#each historique as g (g.id)}
              <tr class="hover:bg-stone-50 dark:hover:bg-stone-800/50 align-top">
                <td class="whitespace-nowrap px-3 py-1.5 text-xs text-stone-500">
                  {formaterDate(g.date_creation)}
                </td>
                <td class="px-3 py-1.5">
                  {g.type_operation}
                  {#if g.mode}
                    <span class="ml-1 text-xs text-stone-400">({g.mode})</span>
                  {/if}
                </td>
                <td class="px-3 py-1.5 font-mono text-xs">{g.cible ?? "—"}</td>
                <td class="px-3 py-1.5 text-xs">{g.annee_libelle ?? "—"}</td>
                <td class="px-3 py-1.5 text-xs text-stone-600 dark:text-stone-400">
                  {Object.entries(g.resultat).slice(0, 3).map(([k, v]) => `${k}=${v}`).join(", ") || "—"}
                </td>
                <td class="px-3 py-1.5 text-right">
                  <button
                    class="text-xs text-sky-700 hover:underline dark:text-sky-400"
                    onclick={() => comparer(g)}
                  >
                    Comparer
                  </button>
                </td>
              </tr>
              {#if comparaisons[g.id]}
                {@const c = comparaisons[g.id]}
                <tr class="bg-stone-50 dark:bg-stone-800/50">
                  <td colspan="6" class="px-3 py-2 text-xs">
                    {#if !c.trouvee}
                      <span class="text-stone-500">
                        Aucune opération comparable dans l'historique.
                      </span>
                    {:else}
                      <p class="mb-1 text-stone-500">
                        Comparé au {formaterDate(c.reference_date)}
                        {#if c.reference_annee}(année {c.reference_annee}){/if}
                      </p>
                      <ul class="space-y-0.5">
                        {#each c.ecarts as e (e.compteur)}
                          <li class={e.est_aberrant ? "font-medium text-red-700 dark:text-red-400" : "text-stone-600 dark:text-stone-400"}>
                            {e.compteur} : {e.valeur_precedente} → {e.valeur_courante}
                            <span class="ml-1">
                              ({e.ecart >= 0 ? "+" : ""}{e.ecart}{#if e.ecart_relatif !== null}, {e.ecart_relatif.toFixed(0)} %{/if})
                            </span>
                            {#if e.est_aberrant}<span class="ml-1">⚠</span>{/if}
                          </li>
                        {/each}
                      </ul>
                    {/if}
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
