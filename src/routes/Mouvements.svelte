<script>
  /**
   * Les mouvements d'un élève en cours d'année.
   *
   * Toute la chaîne de rentrée suppose une campagne, traitée en bloc. La
   * vie scolaire se fait à l'unité : un changement de classe en octobre,
   * une inscription en janvier.
   *
   * L'écran montre le plan avant de l'appliquer, et surtout **ce qui
   * restera à faire ailleurs** — KoXo n'a pas d'API. Un écran qui ferait
   * 60 % du travail sans nommer les 40 % restants serait plus dangereux
   * qu'un écran inerte.
   */
  import { onMount } from "svelte";
  import ArrowRightLeft from "@lucide/svelte/icons/arrow-right-left";
  import Search from "@lucide/svelte/icons/search";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Check from "@lucide/svelte/icons/check";
  import X from "@lucide/svelte/icons/x";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import {
    annees as anneesApi,
    mouvementsApi,
    personnes as personnesApi,
    tableCorrespondance,
  } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));
  let classes = $state(/** @type {any[]} */ ([]));
  let toutes = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);

  let requete = $state("");
  let choisi = $state(/** @type {any} */ (null));
  let nouvelleClasse = $state("");
  let plan = $state(/** @type {any} */ (null));
  let occupe = $state(false);

  /**
   * Google reste à l'écart tant que la rentrée n'est pas faite.
   *
   * Avant le jour J, les élèves attendent tous dans la même OU — la classe
   * n'y change rien — et leurs groupes sont volontairement vides. Ajouter
   * l'élève à sa nouvelle liste le remettrait dans un groupe qu'on a vidé,
   * et lui révélerait sa classe avant l'heure.
   */
  let appliquerGoogle = $state(false);

  onMount(async () => {
    try {
      const [a, tc, p] = await Promise.all([
        anneesApi.lister(),
        tableCorrespondance.lister(),
        personnesApi.lister({ type: "eleve" }),
      ]);
      listeAnnees = a;
      anneeId = [...a].sort((x, y) => x.libelle.localeCompare(y.libelle)).at(-1)?.id ?? null;
      classes = tc;
      toutes = p;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      chargement = false;
    }
  });

  // Sans accents ni casse : « guegan » doit trouver « Guégan ».
  function aplatir(t) {
    return (t ?? "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase();
  }

  let resultats = $derived.by(() => {
    const q = aplatir(requete.trim());
    if (q.length < 2) return [];
    return toutes
      .filter((p) => aplatir(`${p.nom} ${p.prenom} ${p.login} ${p.badge}`).includes(q))
      .slice(0, 12);
  });

  // Les classes déclarées, sans doublon, dans l'ordre.
  let codesClasses = $derived(
    [...new Set(classes.map((c) => c.classe_code_court))].sort(),
  );

  function choisir(p) {
    choisi = p;
    plan = null;
    nouvelleClasse = "";
    requete = "";
  }

  async function calculer() {
    if (!choisi || !nouvelleClasse || !anneeId) return;
    occupe = true;
    try {
      plan = await mouvementsApi.changerClasse({
        personneId: choisi.id,
        nouvelleClasse,
        anneeId,
        appliquerGoogle,
      });
    } catch (e) {
      plan = null;
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      occupe = false;
    }
  }

  async function appliquer() {
    if (!plan) return;
    occupe = true;
    try {
      const r = await mouvementsApi.changerClasse({
        personneId: choisi.id,
        nouvelleClasse,
        anneeId,
        mode: "reel",
        appliquerGoogle,
      });
      const echecs = (r.operations ?? []).filter((o) => !o.reussie).length;
      if (echecs) {
        notify.avertissement(
          `${r.prenom} ${r.nom} est passé en ${r.classe_apres}, mais ${echecs} opération(s) Google ont échoué.`,
        );
      } else {
        notify.succes(`${r.prenom} ${r.nom} est passé en ${r.classe_apres}.`);
      }
      plan = r;
      // Le référentiel a changé : la liste en mémoire doit suivre, sinon
      // un second mouvement partirait de l'ancienne classe.
      toutes = await personnesApi.lister({ type: "eleve" });
      choisi = toutes.find((p) => p.id === choisi.id) ?? choisi;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      occupe = false;
    }
  }
</script>

<section class="space-y-5">
  <EnTetePage
    icon={ArrowRightLeft}
    titre="Mouvements"
    description="Changer un élève de classe en cours d'année. Le référentiel bouge d'abord — sans lui, la bascule du jour J et la composition des groupes ramèneraient l'élève dans son ancienne classe."
  />

  {#if chargement}
    <p class="text-sm text-stone-500 dark:text-stone-400">Chargement…</p>
  {:else}
    <div class="card space-y-3 p-4">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
        L'élève
      </h2>

      {#if choisi}
        <div class="flex flex-wrap items-center gap-3">
          <p class="text-sm">
            <strong>{choisi.nom} {choisi.prenom}</strong>
            <span class="ml-2 font-mono text-xs text-stone-500 dark:text-stone-400">
              {choisi.login} · {choisi.badge}
            </span>
            <span class="ml-2 rounded bg-stone-100 px-1.5 py-0.5 text-xs dark:bg-stone-700">
              {choisi.classe ?? "sans classe"}
            </span>
          </p>
          <button class="text-xs text-stone-500 hover:text-red-600"
                  onclick={() => { choisi = null; plan = null; }}>
            × changer d'élève
          </button>
        </div>
      {:else}
        <label class="block">
          <span class="libelle-champ">Nom, prénom, identifiant ou ID unique</span>
          <input class="champ w-full max-w-lg" bind:value={requete}
                 placeholder="Deux caractères au moins" />
        </label>
        {#if resultats.length}
          <ul class="divide-y divide-stone-200 rounded-lg border border-stone-200 dark:divide-stone-700 dark:border-stone-700">
            {#each resultats as p (p.id)}
              <li>
                <button class="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-700/50"
                        onclick={() => choisir(p)}>
                  <span class="flex-1">{p.nom} {p.prenom}</span>
                  <span class="font-mono text-xs text-stone-500 dark:text-stone-400">{p.login}</span>
                  <span class="rounded bg-stone-100 px-1.5 py-0.5 text-xs dark:bg-stone-700">
                    {p.classe ?? "—"}
                  </span>
                </button>
              </li>
            {/each}
          </ul>
        {:else if requete.trim().length >= 2}
          <p class="text-sm text-stone-500 dark:text-stone-400">Aucun élève.</p>
        {/if}
      {/if}
    </div>

    {#if choisi}
      <div class="card space-y-3 p-4">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
          La nouvelle classe
        </h2>
        <div class="flex flex-wrap items-end gap-3">
          <label class="block">
            <span class="libelle-champ">Classe</span>
            <select class="champ w-48" bind:value={nouvelleClasse}
                    onchange={() => (plan = null)}>
              <option value="">Choisir…</option>
              {#each codesClasses as c (c)}<option value={c}>{c}</option>{/each}
            </select>
          </label>
          <label class="block">
            <span class="libelle-champ">Année</span>
            <select class="champ w-40" bind:value={anneeId}
                    onchange={() => (plan = null)}>
              {#each listeAnnees as a (a.id)}<option value={a.id}>{a.libelle}</option>{/each}
            </select>
          </label>
          <Bouton variante="primary" icon={Search} {occupe}
                  disabled={!nouvelleClasse} onclick={calculer}>
            Calculer
          </Bouton>
        </div>

        <label class="flex items-start gap-2 text-xs text-stone-700 dark:text-stone-300">
          <input type="checkbox" bind:checked={appliquerGoogle}
                 onchange={() => (plan = null)}
                 class="mt-0.5 h-4 w-4 rounded border-stone-300" />
          <span>
            <strong>Appliquer aussi dans Google</strong> — déplacement d'unité
            et échange des groupes. À laisser décoché avant la rentrée : les
            élèves attendent tous dans la même unité, et les ajouter à leur
            nouvelle liste de classe leur révélerait leur classe avant
            l'heure.
          </span>
        </label>
      </div>
    {/if}

    {#if plan}
      <div class="card space-y-3 p-4">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
            {plan.applique ? "Ce qui a été fait" : "Ce qui serait fait"}
          </h2>
          {#if !plan.applique}
            <Bouton variante="primary" {occupe} onclick={appliquer}>
              Appliquer
            </Bouton>
          {/if}
        </div>

        <p class="text-sm">
          <strong>{plan.prenom} {plan.nom}</strong>
          <span class="mx-2 font-mono">{plan.classe_avant ?? "—"} → {plan.classe_apres}</span>
        </p>

        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <tbody>
              <tr class="border-t border-stone-200 dark:border-stone-700">
                <td class="py-1.5 pr-4 text-stone-500 dark:text-stone-400">Référentiel</td>
                <td class="py-1.5">nouvelle photographie, portant la classe d'origine</td>
              </tr>
              <tr class="border-t border-stone-200 dark:border-stone-700">
                <td class="py-1.5 pr-4 text-stone-500 dark:text-stone-400">Unité d'organisation</td>
                <td class="py-1.5 font-mono text-xs">
                  {#if plan.deplacement_utile}
                    {plan.ou_avant ?? "—"} → {plan.ou_apres}
                  {:else}
                    <span class="font-sans text-stone-500 dark:text-stone-400">
                      inchangée — l'élève attend en OU de pré-rentrée
                    </span>
                  {/if}
                </td>
              </tr>
              <tr class="border-t border-stone-200 dark:border-stone-700">
                <td class="py-1.5 pr-4 text-stone-500 dark:text-stone-400">Groupes</td>
                <td class="py-1.5 font-mono text-xs">
                  {plan.groupe_quitte ?? "—"} → {plan.groupe_rejoint ?? "—"}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {#each plan.avertissements as a}
          <p class="rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
            {a}
          </p>
        {/each}

        {#if plan.operations?.length}
          <div>
            <p class="libelle-champ">Opérations Google</p>
            <ul class="mt-1 space-y-1 text-sm">
              {#each plan.operations as o}
                <li class="flex items-start gap-2">
                  {#if o.reussie}
                    <Check class="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  {:else}
                    <X class="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600 dark:text-red-400" />
                  {/if}
                  <span>
                    {o.libelle}
                    {#if o.message}
                      <span class="text-xs text-red-700 dark:text-red-400"> — {o.message}</span>
                    {/if}
                  </span>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        <!-- Ce que le programme ne sait pas faire, il le nomme. Un écran qui
             ferait 60 % du travail en silence serait pire qu'un écran inerte. -->
        <div class="rounded-lg border border-stone-200 bg-stone-50 p-3 dark:border-stone-700 dark:bg-stone-800">
          <p class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
            <TriangleAlert class="h-3.5 w-3.5" />
            Ce qui reste à faire ailleurs
          </p>
          <ul class="mt-1.5 space-y-1 text-sm text-stone-700 dark:text-stone-300">
            {#each plan.reste_a_faire as r}
              <li><strong>{r.systeme}</strong> — {r.geste}</li>
            {/each}
          </ul>
          <p class="mt-2 text-xs text-stone-500 dark:text-stone-400">
            Pour KoXo, le plus simple est de réexporter depuis l'onglet
            <strong>Exports</strong> : le fichier porte déjà la nouvelle classe.
          </p>
        </div>
      </div>
    {/if}
  {/if}
</section>
