<script>
  import { onMount } from "svelte";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Info from "@lucide/svelte/icons/info";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Compass from "@lucide/svelte/icons/compass";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Image from "@lucide/svelte/icons/image";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Nombre from "$lib/components/Nombre.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import BandeauChiffres from "$lib/components/BandeauChiffres.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import { TEINTES } from "$lib/familles.js";
  import { annees as anneesApi, statistiques } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  /**
   * L'entrée de « L'année » : ce qui cloche, et le geste qui le règle.
   *
   * ## Pourquoi cet écran remplace un tableau de bord d'étapes
   *
   * L'accueil annonçait « 8 étapes faites sur 15 » et « prochaine étape :
   * vider l'arbre de l'année révolue ». C'est le bon écran en août, quand
   * la campagne se déroule dans un ordre connu. Le reste de l'année, la
   * question n'est plus « où en est le parcours » mais « qu'est-ce qui ne
   * colle pas, aujourd'hui » — et cette question-là n'avait aucune réponse.
   *
   * ## Un constat n'est utile que s'il porte son geste
   *
   * Afficher « 4 classes hors table » sans dire où aller, c'est laisser le
   * travail de traduction à celui qui lit. Chaque constat connaît donc
   * l'écran qui le règle, et le bouton y mène directement.
   *
   * ## Ce qui est lu tout de suite, et ce qui ne l'est pas
   *
   * Les anomalies se calculent dans la base locale : instantané, à chaque
   * ouverture. Deux choses ne s'y trouvent pas et coûtent cher :
   *
   * - les **photos**, un accès disque par élève sur un partage réseau ;
   * - l'état réel de **Google**, plusieurs centaines d'appels.
   *
   * Elles ne partent donc pas d'elles-mêmes. Elles sont annoncées comme
   * non vérifiées — ce qui est distinct de « tout va bien » — et se
   * demandent d'un clic.
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  let anomalies = $state(/** @type {any} */ (null));
  let stats = $state(/** @type {any} */ (null));
  let annee = $state(/** @type {any} */ (null));
  let chargement = $state(true);
  let erreur = $state("");
  let photosVerifiees = $state(false);
  let relecture = $state(false);

  /**
   * Où va-t-on pour régler chaque anomalie.
   *
   * La table vit ici plutôt que dans le service : le backend décrit ce
   * qu'il constate, l'interface sait par quel écran on y remédie. Une
   * anomalie sans destination reste affichée — sans bouton, mais visible.
   */
  const OU_REGLER = {
    classe_hors_table: { page: "table_correspondance", geste: "Compléter la Table" },
    classe_sans_groupe: { page: "table_correspondance", geste: "Compléter la Table" },
    arbitrage_en_attente: { page: "arbitrage", geste: "Trancher" },
    personne_sans_site: { page: "personnes", geste: "Voir les fiches" },
    personne_sans_email: { page: "personnes", geste: "Voir les fiches" },
    collision_email: { page: "departager", geste: "Départager" },
    doublon_fiche: { page: "departager", geste: "Réunir" },
    compte_purge_echue: { page: "sortants", geste: "Décider" },
    photo_orpheline: { page: "exports", geste: "Voir les photos" },
  };

  const GRAVITES = {
    bloquant: {
      barre: "border-l-red-500",
      nb: "text-red-700 dark:text-red-400",
      icone: AlertTriangle,
      iconeClasse: "text-red-600 dark:text-red-400",
    },
    attention: {
      barre: "border-l-amber-500",
      nb: "text-amber-700 dark:text-amber-400",
      icone: AlertTriangle,
      iconeClasse: "text-amber-600 dark:text-amber-400",
    },
    information: {
      barre: "border-l-stone-300 dark:border-l-stone-600",
      nb: "text-stone-600 dark:text-stone-300",
      icone: Info,
      iconeClasse: "text-stone-400 dark:text-stone-500",
    },
  };

  /** Les bloquants d'abord : ce sont eux qui empêchent un traitement. */
  const ORDRE = { bloquant: 0, attention: 1, information: 2 };
  let triees = $derived(
    [...(anomalies?.anomalies ?? [])].sort(
      (a, b) => ORDRE[a.gravite] - ORDRE[b.gravite] || b.nb_concernes - a.nb_concernes,
    ),
  );

  let effectifs = $derived.by(() => {
    const par = new Map();
    for (const e of stats?.effectifs_par_site_type ?? []) {
      par.set(e.site, (par.get(e.site) ?? 0) + e.nb);
    }
    return [...par.entries()].sort((a, b) => b[1] - a[1]);
  });

  onMount(charger);

  async function charger({ avecPhotos = false } = {}) {
    if (avecPhotos) relecture = true;
    else chargement = true;
    erreur = "";
    try {
      const liste = await anneesApi.lister();
      // L'année préparée est la plus récente par libellé, comme partout
      // ailleurs. `est_active` ne départage rien : il est vrai sur les deux
      // années à la fois, et s'y fier affichait 2025-2026 en préparation.
      annee = [...liste].sort((a, b) => b.libelle.localeCompare(a.libelle))[0] ?? null;
      const [a, s] = await Promise.all([
        statistiques.anomalies({
          anneeId: annee?.id ?? null,
          verifierPhotos: avecPhotos,
        }),
        statistiques.referentiel(),
      ]);
      anomalies = a;
      stats = s;
      if (avecPhotos) photosVerifiees = true;
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
    } finally {
      chargement = false;
      relecture = false;
    }
  }

  /** Le vert des constats sains — celui de la famille KoXo. */
  const VERT = TEINTES.koxo;

  /**
   * Les personnes sans site méritent le rouge dans la répartition.
   *
   * Sans site, aucune cible n'est calculable : elles sortent de tous
   * les exports sans que rien ne le signale. Les afficher comme une
   * ligne de plus dans la liste des sites, c'est les cacher parmi les
   * autres.
   */
  function sansSite(nom) {
    const n = String(nom ?? '').trim().toLowerCase();
    return !n || n === '—' || n === '-' || n.startsWith('sans');
  }

  /**
   * Le libellé porte déjà son compte, et ce n'est pas toujours celui de
   * `nb_concernes` : « 29 adresse(s) mail visée(s) » pour 58 personnes.
   * Afficher 58 en grand à côté d'un titre qui dit 29 met deux nombres qui
   * se contredisent sur la même ligne — et celui qu'on lit en premier est
   * le gros, donc le faux.
   *
   * On sort le nombre du libellé pour le montrer en grand, et
   * `nb_concernes` redevient ce qu'il est : combien de personnes sont
   * derrière.
   */
  function decouper(a) {
    const m = /^(\d[\d\s  ]*)\s+(.+)$/.exec(a.libelle ?? "");
    if (!m) return { nombre: a.nb_concernes, texte: a.libelle ?? "", personnes: 0 };
    const nombre = Number(m[1].replace(/\D/g, ""));
    return {
      nombre,
      texte: m[2],
      personnes: a.nb_concernes !== nombre ? a.nb_concernes : 0,
    };
  }

  function aller(page) {
    onNaviguer?.(page);
  }
</script>

<section class="space-y-6">
  <EnTetePage
    icon={Compass}
    titre="Où ça coince"
    description="Ce que le programme constate dans le référentiel, maintenant. Chaque ligne porte le geste qui la règle."
  >
    {#snippet actions()}
      <Bouton taille="sm" icon={RefreshCw} occupe={chargement && !relecture} onclick={() => charger()}>
        Relire
      </Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  <!-- L'état des lieux : le contexte chiffré, avant les problèmes. -->
  {#if chargement && !stats}
    <Squelette variante="ligne-tableau" nb={1} colonnes={4} />
  {:else if stats}
    <BandeauChiffres
      chiffres={[
        {
          libelle: "Au référentiel",
          valeur: stats.nb_personnes_total,
          detail: `${stats.nb_eleves_total} élèves · ${stats.nb_adultes_total} adultes`,
        },
        {
          libelle: "Année préparée",
          valeur: annee?.libelle ?? "—",
          detail: `${stats.nb_classes_table} classes dans la Table`,
        },
        {
          libelle: "Par site",
          valeur: "",
          lignes: effectifs.map(([site, nb]) => ({
            texte: site,
            valeur: nb,
            alerte: sansSite(site),
          })),
        },
        {
          libelle: "Arbitrages",
          valeur: stats.nb_arbitrages_en_attente,
          teinte: stats.nb_arbitrages_en_attente
            ? "var(--color-amber-600)"
            : undefined,
          detail: `en attente · ${stats.nb_arbitrages_tranches} tranchés`,
        },
      ]}
    />
  {/if}

  <!-- Les constats. Le nombre d'abord, en grand : c'est lui qu'on cherche. -->
  {#if chargement && !anomalies}
    <Squelette variante="ligne-tableau" nb={3} colonnes={3} />
  {:else if anomalies}
    {#if triees.length === 0}
      <div class="flex items-center gap-3.5 py-4">
        <CheckCircle2 class="h-7 w-7 shrink-0" style="color: {VERT};" />
        <div>
          <p class="titre-affiche text-lg">Rien ne cloche dans le référentiel.</p>
          <p class="text-sm text-stone-600 dark:text-stone-400">
            Les huit contrôles passent. Ce qui se vérifie dans Google reste à
            demander séparément, plus bas.
          </p>
        </div>
      </div>
    {:else}
      <p class="text-sm text-stone-600 dark:text-stone-400">
        <b class="text-stone-900 dark:text-stone-100">{triees.length} chose{triees.length > 1 ? "s" : ""}</b>
        demande{triees.length > 1 ? "nt" : ""} ton attention{#if anomalies.nb_bloquants}, dont
          <b class="text-red-700 dark:text-red-400">{anomalies.nb_bloquants}</b>
          qui bloque{anomalies.nb_bloquants > 1 ? "nt" : ""} un traitement{/if}.
      </p>

      <div>
        {#each triees as a (a.type)}
          {@const dest = OU_REGLER[a.type]}
          {@const bloquant = a.gravite === "bloquant"}
          {@const c = decouper(a)}
          <div class="grid grid-cols-[6rem_minmax(0,1fr)_auto] items-center gap-6 border-b border-stone-200 py-5 dark:border-stone-800">
            <span
              class="titre-affiche text-[52px] leading-none tabular-nums"
              style="color: {bloquant
                ? 'var(--color-red-700)'
                : a.gravite === 'attention'
                  ? 'var(--color-amber-700)'
                  : 'var(--color-stone-500)'};"
            >
              {c.nombre}
            </span>
            <div class="min-w-0">
              <p class="text-lg font-bold">{c.texte}</p>
              {#if c.personnes || a.action_suggeree}
                <p class="mt-1 max-w-3xl text-sm leading-relaxed text-stone-600 dark:text-stone-400">
                  {#if c.personnes}<b>{c.personnes} personnes concernées.</b>&nbsp;{/if}{a.action_suggeree ?? ""}
                </p>
              {/if}
              {#if a.details.length}
                <p class="mt-1 truncate text-xs text-stone-500 dark:text-stone-400">
                  {a.details.slice(0, 6).join(" · ")}{a.details.length > 6 ? " …" : ""}
                </p>
              {/if}
            </div>
            {#if dest}
              <Bouton
                variante={bloquant ? "primary" : "secondary"}
                onclick={() => aller(dest.page)}
              >
                {dest.geste}
              </Bouton>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  {/if}

  <!-- Ce qui n'a pas été vérifié, et qui n'est pas « tout va bien ». -->
  <div>
    <h2 class="titre-affiche text-xl">Ce qui n'a pas été vérifié</h2>
    <p class="mt-1 text-[13px] text-stone-600 dark:text-stone-400">
      Tant que ces contrôles n'ont pas tourné, leur silence ne veut rien dire.
    </p>

    <div class="mt-3 flex items-center gap-3.5 border-b border-stone-200 py-3.5 dark:border-stone-800">
      <span class="h-2.5 w-2.5 shrink-0 rounded-full bg-amber-500"></span>
      <p class="flex-grow text-sm">
        <b>Les photos</b>
        <span class="text-stone-600 dark:text-stone-400">
          Un accès disque par élève sur le partage réseau.
        </span>
      </p>
      {#if photosVerifiees}
        <Pastille etat="pret" texte="Vérifiées à la dernière relecture" />
      {:else}
        <Bouton taille="sm" occupe={relecture} onclick={() => charger({ avecPhotos: true })}>
          Vérifier les photos
        </Bouton>
      {/if}
    </div>

    <div class="flex items-center gap-3.5 border-b border-stone-200 py-3.5 dark:border-stone-800">
      <span class="h-2.5 w-2.5 shrink-0 rounded-full bg-amber-500"></span>
      <p class="flex-grow text-sm">
        <b>L'état réel de Google</b>
        <span class="text-stone-600 dark:text-stone-400">
          Unités, groupes, comptes suspendus : plusieurs centaines d'appels.
        </span>
      </p>
      <Bouton taille="sm" onclick={() => aller("conformite_google")}>
        Aller à la Conformité
      </Bouton>
    </div>

    <p class="mt-3 text-[13px] text-stone-500 dark:text-stone-400">
      Pour comparer Charlemagne, le référentiel, Google et KoXo sur la classe de
      chacun, c'est la <button
        type="button"
        class="font-semibold underline decoration-dotted"
        style="color: {TEINTES.koxo};"
        onclick={() => aller("concordance")}>Concordance</button
      > — elle demande un export Charlemagne frais, donc elle ne peut pas tourner
      toute seule.
    </p>
  </div>
</section>
