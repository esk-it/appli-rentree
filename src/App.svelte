<script>
  import { onMount } from "svelte";
  import GraduationCap from "@lucide/svelte/icons/graduation-cap";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import ArrowRightLeft from "@lucide/svelte/icons/arrow-right-left";
  import KeyRound from "@lucide/svelte/icons/key-round";
  import Home from "@lucide/svelte/icons/home";
  import Database from "@lucide/svelte/icons/database";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Settings from "@lucide/svelte/icons/settings";
  import HelpCircle from "@lucide/svelte/icons/help-circle";
  import Search from "@lucide/svelte/icons/search";
  import Download from "@lucide/svelte/icons/download";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import BarChart3 from "@lucide/svelte/icons/bar-chart-3";
  import Building2 from "@lucide/svelte/icons/building-2";
  import TableIcon from "@lucide/svelte/icons/table";
  import GitCompareArrows from "@lucide/svelte/icons/git-compare-arrows";
  import UserPlus from "@lucide/svelte/icons/user-plus";
  import FolderTree from "@lucide/svelte/icons/folder-tree";
  import LogOut from "@lucide/svelte/icons/log-out";
  import ShieldCheck from "@lucide/svelte/icons/shield-check";
  import ClipboardCheck from "@lucide/svelte/icons/clipboard-check";
  import GitCompare from "@lucide/svelte/icons/git-compare";
  import Laptop from "@lucide/svelte/icons/laptop";
  import Scale from "@lucide/svelte/icons/scale";
  import Rocket from "@lucide/svelte/icons/rocket";
  import FileDown from "@lucide/svelte/icons/file-down";
  import Zap from "@lucide/svelte/icons/zap";
  import Activity from "@lucide/svelte/icons/activity";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import TableauDeBord from "./routes/TableauDeBord.svelte";
  import Coffre from "./routes/Coffre.svelte";
  import Arrivees from "./routes/Arrivees.svelte";
  import Bilan from "./routes/Bilan.svelte";
  import Concordance from "./routes/Concordance.svelte";
  import Mouvements from "./routes/Mouvements.svelte";
  import Personnes from "./routes/Personnes.svelte";
  import Sites from "./routes/Sites.svelte";
  import TableCorrespondance from "./routes/TableCorrespondance.svelte";
  import Amorcage from "./routes/Amorcage.svelte";
  import ControleKoxo from "./routes/ControleKoxo.svelte";
  import Snapshots from "./routes/Snapshots.svelte";
  import Bascule from "./routes/Bascule.svelte";
  import Sortants from "./routes/Sortants.svelte";
  import ConformiteGoogle from "./routes/ConformiteGoogle.svelte";
  import Chromebooks from "./routes/Chromebooks.svelte";
  import Nouveaux from "./routes/Nouveaux.svelte";
  import Reconciliation from "./routes/Reconciliation.svelte";
  import Arbitrage from "./routes/Arbitrage.svelte";
  import Simulation from "./routes/Simulation.svelte";
  import Exports from "./routes/Exports.svelte";
  import Suivi from "./routes/Suivi.svelte";
  import Statistiques from "./routes/Statistiques.svelte";
  import { annees as anneesApi, arbitrages, parcoursApi } from "$lib/api.js";
  import Parametres from "./routes/Parametres.svelte";
  import Aide from "./routes/Aide.svelte";
  import CommandPalette from "$lib/components/CommandPalette.svelte";
  import FriseRentree from "$lib/components/FriseRentree.svelte";
  import ToasterContainer from "$lib/components/ToasterContainer.svelte";
  import { notify } from "$lib/toasts.js";
  import { theme, basculerTheme } from "$lib/theme.js";
  import Sun from "@lucide/svelte/icons/sun";
  import Moon from "@lucide/svelte/icons/moon";
  import { attendreBackend } from "$lib/api.js";
  import { verifierMaj, installerMaj } from "$lib/updater.js";

  let backendOk = $state(/** @type {null | boolean} */ (null));
  let versionBackend = $state("");

  // Command Palette (Ctrl+K / Cmd+K)
  let paletteOuverte = $state(false);

  /**
   * Raccourcis de navigation.
   *
   * `Ctrl+1` à `Ctrl+9` suivent l'ordre visuel de la barre latérale, donc
   * l'ordre du travail : configuration, traitement, consultation. On atteint
   * ainsi une page fréquente sans quitter le clavier.
   */
  let ordreRaccourcis = $derived(sections.flatMap((s) => s.items.map((i) => i.id)));

  function gererTouchesGlobales(e) {
    // Ne pas détourner les touches pendant une saisie.
    const cible = e.target;
    const dansUnChamp =
      cible instanceof HTMLElement &&
      (cible.tagName === "INPUT" ||
        cible.tagName === "TEXTAREA" ||
        cible.tagName === "SELECT" ||
        cible.isContentEditable);

    // Ctrl+K ou Cmd+K — recherche, accessible même depuis un champ.
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      paletteOuverte = !paletteOuverte;
      return;
    }

    if (dansUnChamp) return;

    // Ctrl+1..9 — navigation directe
    if ((e.ctrlKey || e.metaKey) && /^[1-9]$/.test(e.key)) {
      const cible = ordreRaccourcis[Number(e.key) - 1];
      if (cible) {
        e.preventDefault();
        page = cible;
      }
      return;
    }

    // « ? » — aide, convention répandue
    if (e.key === "?" && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      page = "aide";
    }
  }
  let messageDemarrage = $state("Démarrage du backend…");
  let erreurDemarrage = $state("");

  // Mise à jour
  let majDisponible = $state(/** @type {null | {version: string, update: any}} */ (null));
  let majEnCours = $state(false);
  let majProgression = $state({ phase: "", pourcentage: 0, version: "" });
  let majErreur = $state("");
  let majVerifiee = $state(false);
  let majVerificationEnCours = $state(false);

  async function verifierMiseAJour({ manuelle = false } = {}) {
    majVerificationEnCours = true;
    majErreur = "";
    try {
      const maj = await verifierMaj();
      majVerifiee = true;
      if (maj.disponible) {
        majDisponible = { version: maj.version, update: maj.update };
      } else if (maj.aEchoue) {
        majErreur = maj.erreur ?? "cause inconnue";
        if (manuelle) notify.erreur(`Vérification impossible : ${majErreur}`, { duree: 8000 });
      } else if (manuelle) {
        notify.info(`Aucune mise à jour — tu es déjà en v${versionBackend}`);
      }
    } finally {
      majVerificationEnCours = false;
    }
  }

  // Page courante (très simple pour l'instant — on basculera sur svelte-spa-router quand on aura plus de routes)
  let page = $state("accueil");

  // Une intention formulée dans un écran et honorée dans un autre : la
  // Conformité constate le décalage d'année, la Table le corrige.
  let rotationDemandee = $state(/** @type {any} */ (null));

  /**
   * L'état de chaque étape du parcours, tel que le backend le calcule.
   *
   * Il portait autrefois cinq étapes sur quinze, déduites ici à la main :
   * toute la partie Google restait muette, et c'est justement là qu'on se
   * perd. Le calcul est passé au backend, qui lit aussi la rotation de la
   * Table, les constats KoXo et les OU qu'il a lui-même appliquées.
   *
   * Cinq étapes ne se constatent que dans Google. Elles restent à
   * `inconnu` — distinct de « à faire » — jusqu'à ce qu'on les demande
   * explicitement : les relire à chaque navigation coûterait plusieurs
   * appels réseau pour rien.
   */
  let etapesEtats = $state(/** @type {Record<string, any>} */ ({}));
  let etapesFaites = $derived(
    Object.fromEntries(
      Object.entries(etapesEtats).map(([id, e]) => [id, e.etat === "faite"]),
    ),
  );

  async function relireAvancement() {
    try {
      const annees = await anneesApi.lister();
      if (!annees.length) {
        etapesEtats = {};
        return;
      }
      // L'année préparée est la plus récente : les libellés `AAAA-AAAA`
      // s'ordonnent alphabétiquement.
      const annee = [...annees].sort((a, b) =>
        a.libelle.localeCompare(b.libelle),
      ).at(-1);
      const r = await parcoursApi.avancement(annee.id);
      etapesEtats = Object.fromEntries(r.etapes.map((e) => [e.id, e]));
    } catch {
      // Le backend n'est pas encore prêt : la frise reste neutre plutôt
      // que d'annoncer des étapes non faites qui le sont peut-être.
      etapesEtats = {};
    }
  }

  // Relu à chaque changement d'écran : une étape peut venir d'être franchie
  // dans celui qu'on quitte, et l'appel est local.
  $effect(() => {
    page;
    relireAvancement();
  });

  // Compteur d'arbitrages en attente — sert de badge dans la sidebar
  let nbArbitragesEnAttente = $state(0);

  async function rafraichirArbitrages() {
    try {
      const l = await arbitrages.enAttente();
      nbArbitragesEnAttente = l.length;
    } catch {
      // silencieux : si le backend n'est pas prêt, on retentera plus tard
    }
  }

  // Rafraîchit à chaque navigation vers Arbitrage (pour capter les décisions),
  // et périodiquement (peu coûteux : liste courte).
  $effect(() => {
    if (page === "arbitrage") rafraichirArbitrages();
  });

  onMount(async () => {
    // Raccourci Ctrl+K global
    window.addEventListener("keydown", gererTouchesGlobales);

    // 1. Connexion backend
    try {
      const h = await attendreBackend({ maxTentatives: 30, baseDelai: 300 });
      backendOk = h.ok;
      // La version vient de l'application elle-même, pas du backend : ce
      // dernier la portait dans une constante qu'aucune publication ne
      // touchait, et l'écran a affiché 0.75.1 pendant huit versions — au
      // point de faire douter du mécanisme de mise à jour, qui lui
      // fonctionnait.
      try {
        const { getVersion } = await import("@tauri-apps/api/app");
        versionBackend = await getVersion();
      } catch {
        versionBackend = h.version;
      }
    } catch (e) {
      backendOk = false;
      erreurDemarrage = e instanceof Error ? e.message : String(e);
    }

    // 2. Vérification de mise à jour (en parallèle de l'app qui démarre)
    await verifierMiseAJour();

    // 3. Compteur arbitrages en attente (badge sidebar)
    rafraichirArbitrages();
  });

  async function lancerMaj() {
    if (!majDisponible) return;
    majEnCours = true;
    try {
      await installerMaj(majDisponible.update, (p) => {
        majProgression = p;
      });
    } catch (e) {
      console.error("[updater] Échec :", e);
      majEnCours = false;
      notify.erreur(`Échec de la mise à jour : ${e?.message ?? e}`, {
        duree: 8000,
      });
    }
  }

  /**
   * Navigation groupée par moment d'usage plutôt qu'en liste plate.
   *
   * Quatorze entrées alignées sans hiérarchie obligeaient à toutes les lire
   * pour en trouver une. Les sections suivent l'ordre réel du travail :
   * on configure une fois, on traite à chaque campagne, on surveille ensuite.
   */
  /**
   * Le menu, rangé par usage plutôt que par module.
   *
   * Vingt entrées alignées demandaient de toutes les lire pour en trouver
   * une, et surtout : elles laissaient croire que naviguer était la façon
   * de travailler. Ce n'en est pas une. Une rentrée se conduit par le
   * parcours, qui donne l'ordre et l'état de chaque étape ; le menu ne
   * sert qu'à revenir sur un écran précis.
   *
   * Les onze écrans qui sont des **étapes** du parcours sont donc repliés :
   * on y arrive depuis la frise, qui sait où l'on en est. Restent dépliés
   * ceux qu'on consulte à tout moment, sans qu'ils appartiennent à une
   * étape.
   *
   * `repliable` n'est pas `caché` : un groupe replié s'ouvre d'un clic, et
   * son état se retient. Rien n'a été retiré.
   */
  const sections = [
    {
      titre: null, // le tableau de bord n'appartient à aucun groupe
      items: [{ id: "accueil", label: "Tableau de bord", icon: Home }],
    },
    {
      id: "parcours",
      titre: "Parcours de rentrée",
      repliable: true,
      items: [
        { id: "sites", label: "Sites", icon: Building2 },
        { id: "table_correspondance", label: "Table de correspondance", icon: TableIcon },
        { id: "amorcage", label: "Amorçage KoXo", icon: Rocket },
        { id: "snapshots", label: "Snapshots d'années", icon: Database },
        {
          id: "arbitrage",
          label: "Arbitrage",
          icon: Scale,
          badge: () => nbArbitragesEnAttente,
        },
        { id: "sortants", label: "Sortants", icon: LogOut },
        { id: "controle_koxo", label: "Contrôle KoXo", icon: ShieldCheck },
        { id: "exports", label: "Exports", icon: FileDown },
        // Vérifier avant d'agir : Conformité précède les écrans qui écrivent.
        { id: "conformite_google", label: "Conformité Google", icon: ShieldCheck },
        { id: "bascule", label: "Bascule des OU", icon: FolderTree },
        { id: "chromebooks", label: "Chromebooks", icon: Laptop },
        // Il clôt la campagne : c'est le geste qui dit si elle a abouti.
        // Croise les quatre sources : c'est lui qui dit ce qui a bougé
        // dans Charlemagne sans être redescendu ailleurs.
        { id: "concordance", label: "Concordance", icon: GitCompare },
        { id: "bilan", label: "Bilan de rentrée", icon: ClipboardCheck },
      ],
    },
    {
      id: "outils",
      titre: "Outils",
      repliable: true,
      items: [
        // Les deux écrans qui servent toute l'année, et non à la campagne.
        { id: "arrivees", label: "Arrivée", icon: UserPlus },
        { id: "mouvements", label: "Mouvements", icon: ArrowRightLeft },
        { id: "reconciliation", label: "Réconciliation", icon: GitCompareArrows },
        { id: "nouveaux", label: "Nouveaux arrivants", icon: UserPlus },
        { id: "simulation", label: "Simulation", icon: Zap },
      ],
    },
    {
      titre: "Consulter",
      items: [
        { id: "personnes", label: "Référentiel", icon: Users2 },
        // Retrouver un mot de passe est un geste de consultation, et
        // fréquent : il n'a pas à être replié derrière un groupe.
        { id: "coffre", label: "Coffre", icon: KeyRound },
        { id: "suivi", label: "Suivi", icon: Activity },
        { id: "statistiques", label: "Statistiques", icon: BarChart3 },
      ],
    },
    {
      titre: null,
      items: [
        { id: "parametres", label: "Paramètres", icon: Settings },
        { id: "aide", label: "Aide", icon: HelpCircle },
      ],
    },
  ];

  /**
   * Quels groupes sont ouverts. Retenu d'une session à l'autre : refermer
   * à chaque démarrage ce qu'on vient d'ouvrir serait une brimade.
   */
  const MEMOIRE_GROUPES = "menu.groupes.ouverts";
  let groupesOuverts = $state(
    /** @type {Record<string, boolean>} */ (
      (() => {
        try {
          return JSON.parse(localStorage.getItem(MEMOIRE_GROUPES) ?? "{}");
        } catch {
          return {};
        }
      })()
    ),
  );

  $effect(() => {
    try {
      localStorage.setItem(MEMOIRE_GROUPES, JSON.stringify(groupesOuverts));
    } catch {
      // Le stockage peut être refusé : le menu marche sans mémoire.
    }
  });

  // Un groupe replié qui contient l'écran courant s'ouvre de lui-même :
  // arriver quelque part sans voir où l'on est serait désorientant.
  let sectionsAffichees = $derived(
    sections.map((s) => ({
      ...s,
      ouvert:
        !s.repliable ||
        groupesOuverts[s.id] === true ||
        s.items.some((i) => i.id === page),
      alerte: s.items.some((i) => i.badge && i.badge() > 0),
    })),
  );

</script>

{#if backendOk === null}
  <!-- Écran de démarrage : on attend que le sidecar Python soit prêt -->
  <div class="flex h-screen items-center justify-center bg-stone-50">
    <div class="flex flex-col items-center gap-4 text-center">
      <div class="h-12 w-12 animate-spin rounded-full border-4 border-stone-200 border-t-emerald-700"></div>
      <div>
        <p class="text-lg font-semibold text-stone-900">Appli Rentrée</p>
        <p class="mt-1 text-sm text-stone-500">{messageDemarrage}</p>
      </div>
    </div>
  </div>
{:else if backendOk === false}
  <!-- Backend injoignable : on explique au lieu d'un écran blanc -->
  <div class="flex h-screen items-center justify-center bg-stone-50 px-8">
    <div class="card max-w-xl space-y-4 p-6">
      <h2 class="text-xl font-semibold text-red-700">Backend injoignable</h2>
      <p class="text-sm text-stone-700">
        Le sidecar Python n'a pas répondu après plusieurs tentatives. Cela peut venir d'un
        antivirus qui bloque <code>backend.exe</code>, du port 8020 déjà utilisé, ou d'un
        plantage interne du backend.
      </p>
      {#if erreurDemarrage}
        <pre class="overflow-x-auto rounded-lg bg-stone-100 p-3 text-xs text-stone-700 whitespace-pre-wrap">{erreurDemarrage}</pre>
      {/if}
      <p class="text-sm text-stone-700">
        Vérifie qu'aucun autre programme n'utilise le port 8020, et relance l'application.
      </p>
      <button class="btn-primary" onclick={() => location.reload()}>Réessayer</button>
    </div>
  </div>
{:else}
<div class="flex h-screen flex-col overflow-hidden">
  {#if majDisponible && !majEnCours}
    <!-- Bannière nouvelle version dispo -->
    <div class="flex items-center justify-between gap-3 border-b border-emerald-200 bg-emerald-50 px-4 py-2">
      <div class="flex items-center gap-2 text-sm text-emerald-900">
        <Sparkles class="h-4 w-4 text-emerald-700" />
        <span>
          Une nouvelle version <strong>v{majDisponible.version}</strong> est disponible.
        </span>
      </div>
      <button class="btn-primary !py-1 !px-3 text-xs" onclick={lancerMaj}>
        <Download class="h-3.5 w-3.5" />
        Mettre à jour
      </button>
    </div>
  {/if}
  {#if majErreur && !majEnCours}
    <!-- Échec de vérification : rendu visible plutôt qu'avalé en console,
         inaccessible dans l'app packagée. -->
    <div class="flex items-center justify-between gap-3 border-b border-amber-200 bg-amber-50 px-4 py-2 dark:border-amber-800 dark:bg-amber-900/20">
      <div class="flex items-start gap-2 text-sm text-amber-900 dark:text-amber-200">
        <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          Impossible de vérifier les mises à jour :
          <span class="font-mono text-xs">{majErreur}</span>
        </span>
      </div>
      <button
        class="btn-secondary !py-1 !px-3 text-xs shrink-0"
        onclick={() => verifierMiseAJour({ manuelle: true })}
        disabled={majVerificationEnCours}
      >
        Réessayer
      </button>
    </div>
  {/if}
  {#if majEnCours}
    <div class="flex items-center gap-3 border-b border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-900">
      <span>
        Mise à jour vers <strong>v{majProgression.version}</strong> —
        {majProgression.phase === "telechargement"
          ? `téléchargement ${majProgression.pourcentage}%`
          : majProgression.phase === "installation"
            ? "installation…"
            : majProgression.phase === "termine"
              ? "redémarrage…"
              : "préparation…"}
      </span>
      <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-emerald-200">
        <div
          class="h-full bg-emerald-600 transition-all"
          style="width: {majProgression.pourcentage}%"
        ></div>
      </div>
    </div>
  {/if}

<div class="flex flex-1 overflow-hidden">
  <!-- Barre latérale -->
  <aside class="flex w-64 shrink-0 flex-col border-r border-stone-200 bg-white dark:border-stone-700 dark:bg-stone-800">
    <div class="flex items-center gap-2 border-b border-stone-200 px-5 py-4 dark:border-stone-700">
      <GraduationCap class="h-7 w-7 text-emerald-700 dark:text-emerald-400" />
      <div class="flex flex-1 flex-col leading-tight">
        <span class="text-sm font-semibold text-stone-900 dark:text-stone-100">Appli Rentrée</span>
        <span class="text-xs text-stone-500 dark:text-stone-400">Ensemble Scolaire du Kreisker</span>
      </div>
      <button
        class="rounded-md p-1.5 text-stone-500 transition hover:bg-stone-100 hover:text-stone-800 dark:text-stone-400 dark:hover:bg-stone-700 dark:hover:text-stone-200"
        title={$theme === "clair" ? "Passer en mode sombre" : "Passer en mode clair"}
        onclick={basculerTheme}
      >
        {#if $theme === "clair"}
          <Moon class="h-4 w-4" />
        {:else}
          <Sun class="h-4 w-4" />
        {/if}
      </button>
    </div>

    <div class="px-3 pt-3">
      <button
        class="flex w-full items-center gap-2 rounded-lg border border-stone-200 bg-stone-50 px-3 py-1.5 text-sm text-stone-600 transition hover:border-emerald-300 hover:bg-emerald-50 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-emerald-600 dark:hover:bg-stone-700"
        onclick={() => (paletteOuverte = true)}
      >
        <Search class="h-4 w-4" />
        <span class="flex-1 text-left">Rechercher…</span>
        <kbd class="rounded border border-stone-300 bg-white px-1 py-0 text-[10px] font-medium text-stone-500">
          Ctrl K
        </kbd>
      </button>
    </div>

    <nav class="flex-1 overflow-y-auto px-3 py-2">
      {#each sectionsAffichees as section, iSection (iSection)}
        <div class={section.titre ? "mt-4 first:mt-0" : "mt-2 first:mt-0"}>
          {#if section.titre && section.repliable}
            <!-- Un groupe replié s'ouvre d'un clic : rien n'a été retiré du
                 menu, seulement mis à distance de la main. -->
            <button
              class="mb-1 flex w-full items-center gap-1.5 px-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400 transition hover:text-stone-600 dark:text-stone-500 dark:hover:text-stone-300"
              onclick={() => (groupesOuverts[section.id] = !section.ouvert)}
            >
              <ChevronRight
                class="h-3 w-3 shrink-0 transition-transform duration-150 {section.ouvert ? 'rotate-90' : ''}"
              />
              <span class="flex-1 text-left">{section.titre}</span>
              {#if !section.ouvert}
                <span class="font-normal normal-case tracking-normal text-stone-400 dark:text-stone-500">
                  {section.items.length}
                </span>
              {/if}
              {#if section.alerte && !section.ouvert}
                <span class="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500"></span>
              {/if}
            </button>
          {:else if section.titre}
            <p
              class="mb-1 px-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400 dark:text-stone-500"
            >
              {section.titre}
            </p>
          {/if}
          <div class="space-y-0.5" class:hidden={!section.ouvert}>
            {#each section.items as item (item.id)}
              {@const actif = page === item.id}
              <button
                class="group relative flex w-full items-center gap-3 rounded-lg py-2 pl-4 pr-3 text-left text-sm transition-all duration-150
                       {actif
                         ? 'bg-emerald-50 font-semibold text-emerald-800 shadow-sm dark:bg-emerald-900/30 dark:text-emerald-300'
                         : 'font-medium text-stone-700 hover:bg-stone-100 hover:pl-5 dark:text-stone-300 dark:hover:bg-stone-700/50'}"
                onclick={() => (page = item.id)}
              >
                <!-- Barre latérale : repère plus lisible qu'un simple fond coloré -->
                <span
                  class="absolute left-0 top-1/2 w-1 -translate-y-1/2 rounded-r-full bg-emerald-600 transition-all duration-200 dark:bg-emerald-400
                         {actif ? 'h-5 opacity-100' : 'h-0 opacity-0'}"
                ></span>
                <item.icon
                  class="h-4 w-4 shrink-0 transition-transform duration-150 {actif
                    ? ''
                    : 'group-hover:scale-110'}"
                />
                <span class="flex-1 truncate">{item.label}</span>
                {#if item.badge && item.badge() > 0}
                  <span
                    class="animate-[pulsation-douce_2s_ease-in-out_infinite] rounded-full bg-amber-500 px-1.5 py-0 text-[10px] font-semibold text-white shadow-sm"
                  >
                    {item.badge()}
                  </span>
                {/if}
              </button>
            {/each}
          </div>
        </div>
      {/each}
    </nav>

    <div class="border-t border-stone-200 p-3 text-xs text-stone-500 dark:border-stone-700 dark:text-stone-400">
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <span
            class="inline-block h-2 w-2 rounded-full {backendOk === true ? 'bg-emerald-500' : backendOk === false ? 'bg-red-500' : 'bg-stone-300'}"
          ></span>
          Backend{backendOk === true ? ` v${versionBackend}` : backendOk === false ? " hors-ligne" : "…"}
        </div>
        <button
          class="rounded-md p-1 text-stone-400 transition hover:bg-stone-100 hover:text-stone-700 disabled:opacity-40 dark:hover:bg-stone-700 dark:hover:text-stone-200"
          title="Vérifier les mises à jour maintenant"
          onclick={() => verifierMiseAJour({ manuelle: true })}
          disabled={majVerificationEnCours}
        >
          <RefreshCw class="h-3.5 w-3.5 {majVerificationEnCours ? 'animate-spin' : ''}" />
        </button>
      </div>
    </div>
  </aside>

  <!-- Zone principale -->
  <main class="flex-1 overflow-auto bg-stone-50 dark:bg-stone-900">
    <!-- La frise reste hors du bloc `{#key}` : la rejouer à chaque
         navigation la ferait clignoter, alors qu'elle est justement le
         repère fixe pendant qu'on avance. -->
    <FriseRentree {page} faites={etapesFaites} etats={etapesEtats}
                  onNaviguer={(p) => (page = p)} />

    <!-- `{#key}` reconstruit le bloc à chaque navigation, ce qui relance
         l'animation d'apparition — sinon Svelte réutilise le nœud et rien
         ne bouge visuellement. -->
    {#key page}
      <!-- Apparition sans `transform` : ce conteneur englobe les modales des
           écrans, et un transform ferait d'elles des enfants de cette div
           plutôt que de la fenêtre — elles se retrouveraient rognées. -->
      <div class="anim-apparition-sans-transform mx-auto max-w-7xl p-6">
        {#if page === "accueil"}
          <TableauDeBord onNaviguer={(p) => (page = p)} />
        {:else if page === "personnes"}
          <Personnes />
        {:else if page === "coffre"}
          <Coffre />
        {:else if page === "arrivees"}
          <Arrivees />
        {:else if page === "concordance"}
          <Concordance />
        {:else if page === "bilan"}
          <Bilan />
        {:else if page === "mouvements"}
          <Mouvements />
        {:else if page === "sites"}
          <Sites />
        {:else if page === "table_correspondance"}
          <TableCorrespondance rotationInitiale={rotationDemandee} />
        {:else if page === "amorcage"}
          <Amorcage />
        {:else if page === "controle_koxo"}
          <ControleKoxo />
        {:else if page === "snapshots"}
          <Snapshots onNaviguer={(p) => (page = p)} />
        {:else if page === "reconciliation"}
          <Reconciliation />
        {:else if page === "nouveaux"}
          <Nouveaux />
        {:else if page === "bascule"}
          <Bascule />
        {:else if page === "sortants"}
          <Sortants />
        {:else if page === "chromebooks"}
          <Chromebooks />
        {:else if page === "conformite_google"}
          <ConformiteGoogle
            onRotationTable={(a) => {
              rotationDemandee = a;
              page = "table_correspondance";
            }}
          />
        {:else if page === "arbitrage"}
          <Arbitrage />
        {:else if page === "simulation"}
          <Simulation />
        {:else if page === "exports"}
          <Exports />
        {:else if page === "suivi"}
          <Suivi />
        {:else if page === "statistiques"}
          <Statistiques />
        {:else if page === "parametres"}
          <Parametres />
        {:else if page === "aide"}
          <Aide />
        {/if}
      </div>
    {/key}
  </main>
</div>
</div>

<CommandPalette
  bind:ouvert={paletteOuverte}
  onFermer={() => (paletteOuverte = false)}
  ecrans={sections.flatMap((s) => s.items)}
  onAller={(id) => (page = id)}
/>
<ToasterContainer />
{/if}
