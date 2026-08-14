<script>
  import { onMount } from "svelte";
  import GraduationCap from "@lucide/svelte/icons/graduation-cap";
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
  import Scale from "@lucide/svelte/icons/scale";
  import Rocket from "@lucide/svelte/icons/rocket";
  import FileDown from "@lucide/svelte/icons/file-down";
  import Zap from "@lucide/svelte/icons/zap";
  import Activity from "@lucide/svelte/icons/activity";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import TableauDeBord from "./routes/TableauDeBord.svelte";
  import Personnes from "./routes/Personnes.svelte";
  import Sites from "./routes/Sites.svelte";
  import TableCorrespondance from "./routes/TableCorrespondance.svelte";
  import Amorcage from "./routes/Amorcage.svelte";
  import Snapshots from "./routes/Snapshots.svelte";
  import Reconciliation from "./routes/Reconciliation.svelte";
  import Arbitrage from "./routes/Arbitrage.svelte";
  import Simulation from "./routes/Simulation.svelte";
  import Exports from "./routes/Exports.svelte";
  import Suivi from "./routes/Suivi.svelte";
  import Statistiques from "./routes/Statistiques.svelte";
  import { arbitrages } from "$lib/api.js";
  import Parametres from "./routes/Parametres.svelte";
  import Aide from "./routes/Aide.svelte";
  import CommandPalette from "$lib/components/CommandPalette.svelte";
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
      versionBackend = h.version;
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
  const sections = [
    {
      titre: null, // le tableau de bord n'appartient à aucun groupe
      items: [{ id: "accueil", label: "Tableau de bord", icon: Home }],
    },
    {
      titre: "Configuration",
      items: [
        { id: "sites", label: "Sites", icon: Building2 },
        { id: "table_correspondance", label: "Table de correspondance", icon: TableIcon },
        { id: "amorcage", label: "Amorçage KoXo", icon: Rocket },
      ],
    },
    {
      titre: "Traitement",
      items: [
        { id: "snapshots", label: "Snapshots d'années", icon: Database },
        { id: "reconciliation", label: "Réconciliation", icon: GitCompareArrows },
        {
          id: "arbitrage",
          label: "Arbitrage",
          icon: Scale,
          badge: () => nbArbitragesEnAttente,
        },
        { id: "simulation", label: "Simulation", icon: Zap },
        { id: "exports", label: "Exports", icon: FileDown },
      ],
    },
    {
      titre: "Consultation",
      items: [
        { id: "personnes", label: "Référentiel", icon: Users2 },
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
      {#each sections as section, iSection (iSection)}
        <div class={section.titre ? "mt-4 first:mt-0" : "mt-2 first:mt-0"}>
          {#if section.titre}
            <p
              class="mb-1 px-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400 dark:text-stone-500"
            >
              {section.titre}
            </p>
          {/if}
          <div class="space-y-0.5">
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
    <!-- `{#key}` reconstruit le bloc à chaque navigation, ce qui relance
         l'animation d'apparition — sinon Svelte réutilise le nœud et rien
         ne bouge visuellement. -->
    {#key page}
      <div class="anim-apparition mx-auto max-w-7xl p-6">
        {#if page === "accueil"}
          <TableauDeBord onNaviguer={(p) => (page = p)} />
        {:else if page === "personnes"}
          <Personnes />
        {:else if page === "sites"}
          <Sites />
        {:else if page === "table_correspondance"}
          <TableCorrespondance />
        {:else if page === "amorcage"}
          <Amorcage />
        {:else if page === "snapshots"}
          <Snapshots />
        {:else if page === "reconciliation"}
          <Reconciliation />
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

<CommandPalette bind:ouvert={paletteOuverte} onFermer={() => (paletteOuverte = false)} />
<ToasterContainer />
{/if}
