<script>
  /**
   * La porte d'entrée des fichiers : qui attend quoi, et depuis quand.
   *
   * ## Ce que cet écran n'est pas
   *
   * Ce n'est pas un producteur. Chaque système veut ses propres réponses
   * avant de rendre un fichier — KoXo veut un site, une population, une
   * base ; PMB veut un export Charlemagne ; CardStudio veut la liste des
   * élèves cochés. Un bouton « Générer » unique mentirait sur ce que
   * coûte chacun.
   *
   * C'est une **table des matières** : ce que chaque fichier contient, à
   * quand remonte le dernier, et la porte qui mène au geste. Sans elle,
   * il fallait connaître par cœur l'onglet où chaque export se cache.
   *
   * ## Sodexo n'a pas de bouton
   *
   * Le programme ne fabrique pas ce fichier : il naît d'un classeur
   * Google qui transforme l'export Charlemagne. Sa ligne le dit et mène à
   * la procédure — plutôt qu'un bouton qui échouerait, ou pire, qui
   * produirait un fichier ressemblant.
   *
   * ## Le bandeau rouge avant tout
   *
   * Une adresse revendiquée par deux personnes, une personne sans site :
   * ces points-là font échouer un import ligne par ligne, sans nommer la
   * cause. Les voir avant de produire coûte un coup d'œil ; les découvrir
   * après coûte un fichier à refaire.
   */
  import { onMount } from "svelte";
  import FileDown from "@lucide/svelte/icons/file-down";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import ExternalLink from "@lucide/svelte/icons/external-link";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import {
    annees as anneesApi,
    envois as envoisApi,
    statistiques,
  } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { TEINTES } from "$lib/familles.js";

  let { onNaviguer } = $props();

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));
  let etats = $state(/** @type {Record<string, any>} */ ({}));
  let bloquants = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);

  /**
   * Ce qu'on produit, dans l'ordre où la rentrée le sert.
   *
   * KoXo d'abord parce que rien n'ouvre une session sans lui ; Google
   * ensuite ; puis ce qui se voit — le CDI, la carte, le self, la porte ;
   * et en dernier ce qui s'imprime pour les classes.
   *
   * Deux lignes ne suivent pas de « dernier envoi », chacune pour sa
   * raison : la centrale d'accès est elle-même la mémoire de ce qu'elle a
   * reçu, et des listes imprimées ne sont transmises à aucun système.
   */
  const SYSTEMES = [
    {
      id: "koxo",
      nom: "KoXo",
      teinte: TEINTES.koxo,
      contenu:
        "Import des comptes réseau : nouveaux comptes et changements de classe.",
      demande: "un site, une population et la base du serveur",
      vers: "exports",
      cible: "koxo",
    },
    {
      id: "google",
      nom: "Google",
      teinte: TEINTES.google,
      contenu: "Comptes, unités et groupes à créer ou à modifier.",
      demande: "un site et une population",
      vers: "exports",
      cible: "google",
    },
    {
      id: "pmb",
      nom: "PMB",
      teinte: TEINTES.materiel,
      contenu: "Import des lecteurs du CDI.",
      demande: "un export Charlemagne — tout est dans le fichier",
      vers: "exports",
      cible: "pmb",
    },
    {
      id: "cardstudio",
      nom: "CardStudio",
      teinte: TEINTES.photos,
      contenu: "Liste des cartes à fabriquer, photos comprises.",
      demande: "les élèves cochés",
      vers: "cartes",
    },
    {
      id: "sodexo",
      nom: "Sodexo",
      teinte: TEINTES.repas,
      contenu: "Élèves et classes transmis à la restauration.",
      demande: null,
      vers: "sodexo",
      // Le programme ne fabrique pas ce fichier : il naît d'un classeur
      // Google. Le dire ici évite de chercher un bouton qui n'existe pas.
      sansBouton:
        "Le fichier naît du classeur Google, pas du programme. L'écran Sodexo porte la procédure et dit ce qui a changé depuis le dernier envoi.",
    },
    {
      // Vers « Badges et accès », pas vers l'onglet JPM des exports.
      //
      // L'onglet compare deux années du référentiel et laisse le CardId
      // vide sur les modifications : il ignore ce que la centrale contient
      // vraiment. Le différentiel TS1000 part de l'état réel de la
      // centrale, reprend le CardId, et ne sort personne d'un groupe
      // d'accès sans preuve. Une porte d'entrée doit mener au geste sûr.
      id: "jpm",
      nom: "Badges",
      teinte: TEINTES.materiel,
      contenu:
        "Ajouts, déplacements et retraits pour la centrale d'accès, en quatre lots numérotés.",
      demande: "l'export Users.xls de la centrale TS1000",
      vers: "ts1000",
      // Chaque calcul part de l'état réel de la centrale : un lot déjà
      // joué n'y réapparaît pas. Il n'y a pas d'envoi à retenir — la
      // centrale est elle-même la mémoire.
      nonSuivi: "La centrale fait foi",
    },
    {
      // Des documents qu'on imprime, pas un envoi à un système : rien à
      // comparer à un « dernier envoi ». La colonne le dit plutôt que
      // d'afficher un « jamais envoyé » qui ferait croire à un oubli.
      id: "listes",
      nom: "Listes & étiquettes",
      teinte: TEINTES.fichiers,
      contenu:
        "Liste de tous les élèves, liste des entrants, et étiquettes des entrants — une planche par classe.",
      demande: "l'export KoXo du site, mots de passe inclus",
      vers: "exports",
      cible: "listes",
      nonSuivi: "Documents imprimés",
    },
  ];

  /** « il y a trois jours », plutôt qu'un horodatage à déchiffrer. */
  function age(iso) {
    if (!iso) return null;
    const h = Math.round((Date.now() - new Date(iso + "Z").getTime()) / 3600000);
    if (h < 1) return "à l'instant";
    if (h < 24) return `il y a ${h} h`;
    const j = Math.round(h / 24);
    return j === 1 ? "hier" : `il y a ${j} jours`;
  }

  onMount(async () => {
    try {
      listeAnnees = await anneesApi.lister();
      const triees = [...listeAnnees].sort((a, b) =>
        b.libelle.localeCompare(a.libelle),
      );
      anneeId = triees[0]?.id ?? null;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    }
    await charger();
    chargement = false;
  });

  async function charger() {
    // Chaque état est lu à part : un système muet ne doit pas emporter
    // les quatre autres.
    const lus = await Promise.all(
      SYSTEMES.filter((s) => !s.nonSuivi).map(async (s) => {
        try {
          return [s.id, await envoisApi.etat(s.id, anneeId)];
        } catch {
          return [s.id, null];
        }
      }),
    );
    etats = Object.fromEntries(lus);

    try {
      const a = await statistiques.anomalies({ anneeId });
      bloquants = (a.anomalies ?? []).filter((x) => x.gravite === "bloquant");
    } catch {
      bloquants = [];
    }
  }

  function ouvrir(s) {
    onNaviguer?.(s.vers, s.cible ? { cibleInitiale: s.cible } : undefined);
  }
</script>

<section class="space-y-5">
  <EnTetePage
    icon={FileDown}
    titre="Produire un fichier"
    description="Ce que chaque système attend, et à quand remonte le dernier envoi. La production se fait dans l'écran de chacun — ils ne demandent pas les mêmes choses."
  >
    {#snippet actions()}
      <select class="champ w-40" bind:value={anneeId} onchange={charger}>
        {#each listeAnnees as a (a.id)}<option value={a.id}>{a.libelle}</option>{/each}
      </select>
    {/snippet}
  </EnTetePage>

  {#if bloquants.length}
    <!-- Ces points-là font échouer un import ligne par ligne, sans nommer
         la cause. Les voir avant coûte un coup d'œil. -->
    <div class="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl bg-red-50 px-5 py-3 text-sm dark:bg-red-500/10">
      <AlertTriangle class="h-4 w-4 shrink-0 text-red-700 dark:text-red-400" />
      <span class="text-stone-800 dark:text-stone-200">
        <strong>{bloquants.length} point{bloquants.length > 1 ? "s" : ""}</strong>
        bloque{bloquants.length > 1 ? "nt" : ""} un traitement : à régler avant de
        produire les fichiers.
      </span>
      <button
        class="ml-auto font-bold text-red-700 hover:underline dark:text-red-400"
        onclick={() => onNaviguer?.("ou_ca_coince")}
      >
        Voir Où ça coince →
      </button>
    </div>
  {/if}

  {#if chargement}
    <Squelette variante="ligne-tableau" nb={5} colonnes={4} />
  {:else}
    <div>
      <div class="grid grid-cols-[14px_130px_minmax(0,1fr)_170px_150px] items-center gap-4 border-b border-stone-200 py-2 dark:border-stone-800">
        <span></span>
        <span class="libelle-champ">Système</span>
        <span class="libelle-champ">Contenu</span>
        <span class="libelle-champ">Dernier envoi</span>
        <span></span>
      </div>

      {#each SYSTEMES as s (s.id)}
        {@const e = etats[s.id]}
        <div class="grid grid-cols-[14px_130px_minmax(0,1fr)_170px_150px] items-center gap-4 border-b border-stone-100 py-4 text-sm dark:border-stone-800/70">
          <span class="h-2.5 w-2.5 shrink-0 rounded-full" style="background: {s.teinte};"></span>
          <strong>{s.nom}</strong>
          <span class="min-w-0 text-stone-600 dark:text-stone-400">
            {s.contenu}
            {#if s.demande}
              <span class="block text-xs text-stone-500 dark:text-stone-500">
                Demande {s.demande}.
              </span>
            {/if}
          </span>

          <span class="text-stone-600 dark:text-stone-400">
            {#if s.nonSuivi}
              <span class="text-xs text-stone-500 dark:text-stone-400">{s.nonSuivi}</span>
            {:else if !e}
              <span class="text-stone-400">—</span>
            {:else if !e.envoye_le}
              Jamais envoyé
            {:else}
              <span class="font-semibold text-stone-800 dark:text-stone-200">
                {age(e.envoye_le)}
              </span>
              <span class="block text-xs">
                {e.nb_envoyes} ligne{e.nb_envoyes > 1 ? "s" : ""}{#if e.declare}, déclaré{/if}
                {#if e.nb_changements}
                  · <strong style="color: var(--color-amber-600);">
                    {e.nb_changements} changement{e.nb_changements > 1 ? "s" : ""} depuis
                  </strong>
                {/if}
              </span>
            {/if}
          </span>

          {#if s.sansBouton}
            <Bouton icon={ExternalLink} onclick={() => ouvrir(s)}>
              Voir l'écran
            </Bouton>
          {:else}
            <Bouton icon={ArrowRight} onclick={() => ouvrir(s)}>Produire</Bouton>
          {/if}
        </div>

        {#if s.sansBouton}
          <p class="border-b border-stone-100 py-2 pl-[calc(14px+1rem)] text-[13px] text-stone-500 dark:border-stone-800/70 dark:text-stone-400">
            {s.sansBouton}
          </p>
        {/if}
      {/each}
    </div>

    <p class="text-[13px] leading-relaxed text-stone-600 dark:text-stone-400">
      <strong>« Dernier envoi »</strong> ne se devine pas : il est noté quand le
      programme produit le fichier, et déclaré à la main pour Sodexo, dont le
      fichier naît ailleurs. Un envoi déclaré vaut ce que vaut la parole de
      celui qui l'a déclaré — c'est pourquoi l'écran le distingue.
    </p>
  {/if}
</section>
