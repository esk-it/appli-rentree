<script>
  /**
   * L'état réel de Google, en quatre lignes.
   *
   * ## La question du matin
   *
   * Elle n'est pas « quelles unités manquent » ni « quels groupes sont
   * vides » — c'est « est-ce que tout est en place ». Quatre lignes y
   * répondent : les unités, les groupes, les comptes actifs, les comptes
   * suspendus. Chacune mène ensuite à l'écran qui la règle.
   *
   * Les outils qui règlent existaient déjà, répartis en onglets dans un
   * écran nommé « Conformité Google ». Il manquait la porte : on y
   * entrait en choisissant un onglet, donc en ayant déjà décidé ce qui
   * clochait.
   *
   * ## Pourquoi la relève ne part pas toute seule
   *
   * Elle parcourt l'arbre, tous les groupes et tous les comptes du
   * domaine : plusieurs centaines d'appels, une bonne minute. La faire à
   * l'ouverture la ferait payer à chaque passage — et personne ne la
   * lancerait plus jamais exprès, ce qui est la pire des économies.
   *
   * Le résultat survit donc à la navigation, avec son âge affiché. Un
   * constat de mardi reste un constat ; le prendre pour l'état du moment
   * serait l'erreur, et la date l'empêche.
   *
   * ## Les comptes suspendus ne sont pas des sortants
   *
   * Le cycle de sortie **déplace sans suspendre** : un compte suspendu
   * n'est donc pas un départ en règle, c'est une exception — une
   * suspension faite à la main, un compte bloqué par Google. Zéro est la
   * valeur attendue, et tout autre nombre se regarde un par un.
   */
  import ShieldCheck from "@lucide/svelte/icons/shield-check";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import Progression from "$lib/components/Progression.svelte";
  import { googleApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";
  import { TEINTES } from "$lib/familles.js";

  let { onNaviguer } = $props();

  let etat = $state(lire("conformite.etat", /** @type {any} */ (null)));
  let releveLe = $state(lire("conformite.releveLe", /** @type {number|null} */ (null)));
  let occupe = $state(false);

  $effect(() => ecrire("conformite.etat", etat));
  $effect(() => ecrire("conformite.releveLe", releveLe));

  /** « il y a deux jours », plutôt qu'un horodatage à déchiffrer. */
  let age = $derived.by(() => {
    if (!releveLe) return "";
    const m = Math.round((Date.now() - releveLe) / 60000);
    if (m < 2) return "à l'instant";
    if (m < 60) return `il y a ${m} min`;
    const h = Math.round(m / 60);
    if (h < 24) return `il y a ${h} h`;
    const j = Math.round(h / 24);
    return j === 1 ? "hier" : `il y a ${j} jours`;
  });

  let nbEcarts = $derived(
    (etat?.lignes ?? []).filter((l) => l.ecart !== "Aucun écart").length,
  );

  async function relever() {
    occupe = true;
    try {
      etat = await googleApi.etat();
      releveLe = Date.now();
      for (const a of etat.avertissements ?? []) {
        notify.avertissement(a, { duree: 12000 });
      }
      notify.succes(
        nbEcarts === 0
          ? "Google est conforme au référentiel."
          : `${nbEcarts} ligne(s) en écart.`,
        { duree: 8000 },
      );
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 14000 });
    } finally {
      occupe = false;
    }
  }

  const nombre = (n) => (n ?? 0).toLocaleString("fr-FR");
</script>

<section class="space-y-5">
  <EnTetePage
    icon={ShieldCheck}
    titre="Conformité"
    description="L'état réel de Google : unités, groupes et comptes suspendus."
  >
    {#snippet actions()}
      <Bouton variante="primary" icon={RefreshCw} occupe={occupe} onclick={relever}>
        Relever l'état de Google
      </Bouton>
    {/snippet}
  </EnTetePage>

  <div class="flex items-center gap-3 rounded-xl bg-amber-50 px-5 py-3 text-sm dark:bg-amber-400/10">
    <span class="h-2.5 w-2.5 shrink-0 rounded-full bg-amber-500"></span>
    <span class="text-stone-800 dark:text-stone-200">
      Cette relève demande plusieurs centaines d'appels à Google : elle ne
      tourne pas à chaque ouverture.
    </span>
  </div>

  {#if occupe}
    <Progression libelle="Lecture de l'arbre, des groupes et des comptes…" teinte={TEINTES.google} />
  {/if}

  {#if !etat}
    <p class="py-12 text-center text-sm text-stone-500 dark:text-stone-400">
      Aucune relève pour l'instant. Rien n'est affirmé de Google tant qu'on ne
      l'a pas lu.
    </p>
  {:else}
    <div class="flex items-baseline justify-between gap-4">
      <h2 class="titre-affiche text-xl">Dernière relève</h2>
      <span class="text-[13px] text-stone-500 dark:text-stone-400">{age}</span>
    </div>

    <div>
      <div class="grid grid-cols-[minmax(0,1fr)_170px_170px_minmax(0,1fr)_90px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
        <span class="libelle-champ">Élément</span>
        <span class="libelle-champ">Attendu (référentiel)</span>
        <span class="libelle-champ">Constaté (Google)</span>
        <span class="libelle-champ">Écart</span>
        <span></span>
      </div>

      {#each etat.lignes as l (l.cle)}
        <div class="grid grid-cols-[minmax(0,1fr)_170px_170px_minmax(0,1fr)_90px] items-center gap-3 border-b border-stone-100 py-3.5 text-sm dark:border-stone-800/70">
          <strong>{l.element}</strong>
          <span class="tabular-nums text-stone-600 dark:text-stone-400">
            {nombre(l.attendu)}
          </span>
          <span class="tabular-nums text-stone-600 dark:text-stone-400">
            {nombre(l.constate)}
          </span>
          <span>
            {#if l.ecart === "Aucun écart"}
              <Pastille etat="pret" texte="Aucun écart" />
            {:else}
              <Pastille etat="ecart" texte={l.ecart} />
            {/if}
          </span>
          {#if l.vers}
            <button
              class="flex items-center gap-1 text-left text-sm font-semibold hover:underline"
              style="color: {TEINTES.annee};"
              onclick={() => onNaviguer?.(l.vers)}
            >
              Voir <ArrowRight class="h-3.5 w-3.5" />
            </button>
          {:else}
            <span></span>
          {/if}
        </div>
      {/each}
    </div>

    {#if etat.avertissements?.length}
      <div class="flex items-start gap-2.5 rounded-xl bg-amber-50 p-4 dark:bg-amber-400/10">
        <TriangleAlert class="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
        <ul class="space-y-1 text-[13px] text-amber-900 dark:text-amber-200">
          {#each etat.avertissements as a (a)}<li>{a}</li>{/each}
        </ul>
      </div>
    {/if}

    <div class="space-y-1.5 text-[13px] text-stone-500 dark:text-stone-400">
      <p>
        <strong>Comptes hors référentiel</strong> : Google en porte toujours
        plus que le référentiel n'en connaît — les sortants y restent
        dix-huit mois, et les comptes de service n'ont jamais été ingérés.
        Le nombre n'est pas une faute en soi ; c'est sa variation qui se
        regarde.
      </p>
      <p>
        <strong>Comptes suspendus</strong> : le cycle de sortie déplace
        sans suspendre. Un compte suspendu n'est donc pas un départ en
        règle mais une exception, à regarder une par une.
      </p>
    </div>
  {/if}
</section>
