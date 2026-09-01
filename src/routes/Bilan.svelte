<script>
  /**
   * Le bilan de rentrée.
   *
   * Chaque étape rend son propre compte rendu, et chacun est vrai dans son
   * coin : « 595 déplacements appliqués », « 596 appartenances posées ».
   * Aucun ne répond à la question qu'on se pose une fois tout lancé — est-ce
   * que tout le monde est en place ?
   *
   * Trois sections, dans cet ordre, parce que c'est l'ordre où l'on regarde :
   * ce qui est en place, ce qui cloche, ce qui reste.
   *
   * La distinction entre **écart** et **reste** est ce qui rend l'écran
   * lisible. Un élève encore en unité d'attente n'est pas mal rangé : il
   * n'est pas encore basculé. Les compter ensemble noyait cinq vrais
   * problèmes sous seize cents lignes.
   */
  import { onMount } from "svelte";
  import ClipboardCheck from "@lucide/svelte/icons/clipboard-check";
  import Search from "@lucide/svelte/icons/search";
  import ShieldAlert from "@lucide/svelte/icons/shield-alert";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import StatCard from "$lib/components/StatCard.svelte";
  import { annees as anneesApi, bilan as bilanApi, sites as sitesApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let listeSites = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));
  let anneeSourceId = $state(/** @type {number | null} */ (null));
  let siteId = $state(/** @type {number | null} */ (null));
  let rapport = $state(/** @type {any} */ (null));
  let occupe = $state(false);
  let chargement = $state(true);

  onMount(async () => {
    try {
      const [a, s] = await Promise.all([anneesApi.lister(), sitesApi.lister()]);
      listeAnnees = a;
      listeSites = s;
      const triees = [...a].sort((x, y) => y.libelle.localeCompare(x.libelle));
      anneeId = triees[0]?.id ?? null;
      anneeSourceId = triees[1]?.id ?? null;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      chargement = false;
    }
  });

  async function dresser() {
    if (!anneeId) return;
    occupe = true;
    try {
      rapport = await bilanApi.dresser({ anneeId, anneeSourceId, siteId });
    } catch (e) {
      rapport = null;
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  // Un écart par personne se lit mal quand la même personne en cumule
  // trois : on regroupe par genre, et le détail se déplie.
  let parGenre = $derived.by(() => {
    if (!rapport) return [];
    const m = new Map();
    for (const c of rapport.constats) {
      if (!m.has(c.genre)) m.set(c.genre, { genre: c.genre, gravite: c.gravite, geste: c.geste, lignes: [] });
      m.get(c.genre).lignes.push(c);
    }
    return [...m.values()];
  });

  const LIBELLES = {
    compte_absent: "Sans compte Google",
    compte_suspendu: "Compte suspendu",
    ou_inattendue: "Rangé dans une unité inattendue",
    groupe_manquant: "Absent du groupe de sa classe",
    groupe_en_trop: "Membre du groupe d'une autre classe",
    identifiant_discordant: "Identifiant Charlemagne discordant",
    sans_classe: "Inscrit sans classe",
  };
</script>

<section class="space-y-5">
  <EnTetePage
    icon={ClipboardCheck}
    titre="Bilan de rentrée"
    description="Confronte tout le référentiel à tout Google : qui est en place, qui reste à traiter, et ce qui cloche. Ne modifie rien — chaque écart porte le geste à faire."
  />

  {#if chargement}
    <p class="text-sm text-stone-500 dark:text-stone-400">Chargement…</p>
  {:else}
    <div class="card space-y-3 p-4">
      <div class="flex flex-wrap items-end gap-3">
        <label class="block">
          <span class="libelle-champ">Année</span>
          <select class="champ w-40" bind:value={anneeId} onchange={() => (rapport = null)}>
            {#each listeAnnees as a (a.id)}<option value={a.id}>{a.libelle}</option>{/each}
          </select>
        </label>
        <label class="block">
          <span class="libelle-champ">Année précédente</span>
          <select class="champ w-40" bind:value={anneeSourceId} onchange={() => (rapport = null)}>
            <option value={null}>Aucune</option>
            {#each listeAnnees as a (a.id)}<option value={a.id}>{a.libelle}</option>{/each}
          </select>
        </label>
        <label class="block">
          <span class="libelle-champ">Portée</span>
          <select class="champ w-40" bind:value={siteId} onchange={() => (rapport = null)}>
            <option value={null}>Les trois sites</option>
            {#each listeSites as s (s.id)}<option value={s.id}>{s.nom}</option>{/each}
          </select>
        </label>
        <Bouton icon={Search} variante="primary" occupe={occupe} onclick={dresser}>
          Dresser le bilan
        </Bouton>
      </div>
      <p class="text-xs text-stone-500 dark:text-stone-400">
        La lecture parcourt tous les comptes du domaine et les membres de
        chaque groupe de classe : compte une minute. Sans année précédente,
        les sortants ne sont pas repérés — le contrôle est omis plutôt que
        rendu faux.
      </p>
    </div>

    {#if rapport}
      <!-- 1. Ce qui est en place -->
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Inscrits" value={rapport.chiffres.inscrits} />
        <StatCard
          label="Avec un compte"
          value={rapport.chiffres.avec_compte}
          variante={rapport.chiffres.sans_compte ? "danger" : "success"}
          hint={rapport.chiffres.sans_compte
            ? `${rapport.chiffres.sans_compte} sans compte`
            : "personne ne manque"}
        />
        <StatCard
          label="Dans l'OU de leur classe"
          value={rapport.chiffres.en_ou_definitive}
          hint="{rapport.chiffres.en_ou_attente} encore en attente"
        />
        <StatCard
          label="Dans leur groupe"
          value={rapport.chiffres.dans_leur_groupe}
        />
      </div>

      <div class="card p-4">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Par site
        </h2>
        <div class="mt-2 overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="text-xs uppercase text-stone-500 dark:text-stone-400">
              <tr>
                <th class="px-2 py-1 text-left">Site</th>
                <th class="px-2 py-1 text-right">Inscrits</th>
                <th class="px-2 py-1 text-right">Comptes</th>
                <th class="px-2 py-1 text-right">En OU de classe</th>
                <th class="px-2 py-1 text-right">En attente</th>
                <th class="px-2 py-1 text-right">En groupe</th>
              </tr>
            </thead>
            <tbody>
              {#each Object.entries(rapport.par_site) as [nom, c] (nom)}
                <tr class="border-t border-stone-100 dark:border-stone-800">
                  <td class="px-2 py-1 font-medium">{nom}</td>
                  <td class="px-2 py-1 text-right tabular-nums">{c.inscrits}</td>
                  <td class="px-2 py-1 text-right tabular-nums {c.sans_compte ? 'text-rose-600 dark:text-rose-400' : ''}">
                    {c.avec_compte}
                  </td>
                  <td class="px-2 py-1 text-right tabular-nums">{c.en_ou_definitive}</td>
                  <td class="px-2 py-1 text-right tabular-nums">{c.en_ou_attente}</td>
                  <td class="px-2 py-1 text-right tabular-nums">{c.dans_leur_groupe}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>

      <!-- 2. Ce qui cloche -->
      {#if rapport.tout_est_en_place}
        <div class="card flex items-center gap-3 border-emerald-300 p-4 dark:border-emerald-800">
          <CheckCircle2 class="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <p class="text-sm">
            Aucun écart : chaque inscrit a son compte, il est là où sa classe
            l'attend, et dans la liste qui va avec.
          </p>
        </div>
      {:else}
        <div class="card space-y-3 p-4">
          <div class="flex items-baseline justify-between gap-2">
            <h2 class="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
              <ShieldAlert class="h-4 w-4 text-rose-500" />
              Écarts
            </h2>
            <span class="text-xs text-stone-500 dark:text-stone-400">
              {rapport.nb_bloquants} bloquant(s) · {rapport.nb_attention} à surveiller
            </span>
          </div>

          {#each parGenre as g (g.genre)}
            <details
              class="rounded-lg border p-3 {g.gravite === 'bloquant'
                ? 'border-rose-300 bg-rose-50 dark:border-rose-800 dark:bg-rose-950/30'
                : 'border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30'}"
              open={g.gravite === "bloquant"}
            >
              <summary class="cursor-pointer text-sm font-medium">
                {LIBELLES[g.genre] ?? g.genre}
                <span class="ml-1 text-stone-500 dark:text-stone-400">
                  — {g.lignes.length}
                </span>
              </summary>
              <p class="mt-2 text-xs {g.gravite === 'bloquant' ? 'text-rose-800 dark:text-rose-300' : 'text-amber-800 dark:text-amber-300'}">
                {g.geste}
              </p>
              <ul class="mt-2 space-y-1">
                {#each g.lignes as c (c.personne_id + c.genre)}
                  <li class="rounded-md bg-white/70 px-2 py-1 text-sm dark:bg-stone-900/60">
                    <span class="font-medium">{c.prenom} {c.nom}</span>
                    <span class="text-stone-500 dark:text-stone-400">
                      · {c.site ?? "—"} · {c.classe ?? "sans classe"}
                    </span>
                    <span class="block text-xs text-stone-500 dark:text-stone-400">{c.detail}</span>
                  </li>
                {/each}
              </ul>
            </details>
          {/each}
        </div>
      {/if}

      <!-- 3. Ce qui reste -->
      {#if rapport.restes.length}
        <div class="card space-y-3 p-4">
          <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
            Reste à faire
          </h2>
          <p class="text-xs text-stone-500 dark:text-stone-400">
            Ce n'est pas une erreur : ce sont des étapes qu'on n'a pas encore
            faites, ou qu'on a choisi de ne pas faire.
          </p>
          {#each rapport.restes as r (r.genre)}
            <div class="rounded-lg border border-stone-200 bg-stone-50 p-3 dark:border-stone-700 dark:bg-stone-800">
              <p class="text-sm">
                <strong class="tabular-nums">{r.nombre}</strong>
                {r.libelle}
              </p>
              <p class="mt-1 text-xs text-stone-600 dark:text-stone-300">{r.geste}</p>
              {#if r.exemples.length}
                <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
                  par exemple : {r.exemples.join(" · ")}
                </p>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    {/if}
  {/if}
</section>
