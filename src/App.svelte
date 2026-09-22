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
  import Compass from "@lucide/svelte/icons/compass";
  import Wrench from "@lucide/svelte/icons/wrench";
  import Cable from "@lucide/svelte/icons/cable";
  import Nfc from "@lucide/svelte/icons/nfc";
  import Camera from "@lucide/svelte/icons/camera";
  import History from "@lucide/svelte/icons/history";
  import Shuffle from "@lucide/svelte/icons/shuffle";
  import UtensilsCrossed from "@lucide/svelte/icons/utensils-crossed";
  import CreditCard from "@lucide/svelte/icons/credit-card";
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
  import OuCaCoince from "./routes/OuCaCoince.svelte";
  import Parcours from "./routes/Parcours.svelte";
  import Atelier from "./routes/Atelier.svelte";
  import Ts1000 from "./routes/Ts1000.svelte";
  import Photos from "./routes/Photos.svelte";
  import Journal from "./routes/Journal.svelte";
  import QuelquunBouge from "./routes/QuelquunBouge.svelte";
  import Sodexo from "./routes/Sodexo.svelte";
  import Cartes from "./routes/Cartes.svelte";
  import SelecteurAnnee from "$lib/components/SelecteurAnnee.svelte";
  import Accessoires from "./routes/Accessoires.svelte";
  import Affectations from "./routes/Affectations.svelte";
  import Departager from "./routes/Departager.svelte";
  import FichePersonne from "./routes/FichePersonne.svelte";
  import { annees as anneesApi, arbitrages, parcoursApi } from "$lib/api.js";
  import Parametres from "./routes/Parametres.svelte";
  import Aide from "./routes/Aide.svelte";
  import CommandPalette from "$lib/components/CommandPalette.svelte";
  import ToasterContainer from "$lib/components/ToasterContainer.svelte";
  import { notify } from "$lib/toasts.js";
  import { theme, basculerTheme } from "$lib/theme.js";
  import { TEINTES, teinte } from "$lib/familles.js";
  import { charger as chargerAnnees } from "$lib/annee.svelte.js";
  import { declarer as declarerEcran } from "$lib/ecran.svelte.js";
  import Sun from "@lucide/svelte/icons/sun";
  import Moon from "@lucide/svelte/icons/moon";
  import { attendreBackend } from "$lib/api.js";
  import { verifierMaj, installerMaj } from "$lib/updater.js";

  let backendOk = $state(/** @type {null | boolean} */ (null));
  let versionBackend = $state("");

  // Command Palette (Ctrl+K / Cmd+K)
  let paletteOuverte = $state(false);

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

    // 2. L'année de travail, avant tout le reste : c'est elle qui donne
    //    son sens à ce que les écrans afficheront.
    chargerAnnees();

    // 3. Vérification de mise à jour (en parallèle de l'app qui démarre)
    await verifierMiseAJour();

    // 4. Compteur arbitrages en attente (badge sidebar)
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
   * Trois parties, parce que le programme sert à trois moments distincts.
   *
   * La barre latérale rangeait les écrans par ce qu'ils **font** :
   * « parcours », « outils », « consulter ». Il fallait connaître
   * l'architecture pour deviner où aller, et vingt-cinq entrées ouvertes en
   * permanence ne laissaient de place ni au regard ni au tableau.
   *
   * Ces trois-là rangent par **quand on s'en sert** — et ça, on le sait
   * avant même d'ouvrir le programme :
   *
   * - **La rentrée** : la campagne d'août, qui a un début et une fin ;
   * - **L'année** : le cas ponctuel, la vérification, la réédition ;
   * - **Le matériel** : les machines et les accessoires, un domaine à part.
   *
   * Aucun écran n'a été retiré ni réécrit : ils sont rangés ailleurs. Les
   * deux qui ne relèvent d'aucune des trois — Paramètres et Aide — vivent
   * dans le coin de la barre, là où l'on va une fois par an.
   */
  const PARTIES = [
    {
      id: "rentree",
      label: "La rentrée",
      icon: Rocket,
      resume: "La campagne conduite étape par étape",
      ecrans: [{ id: "parcours", label: "Le parcours", icon: Rocket }],
    },
    {
      id: "annee",
      label: "L'année",
      icon: Users2,
      resume: "Chercher quelqu'un, corriger, vérifier, rééditer",
      ecrans: [
        // Ouvrir sur les constats plutôt que sur le référentiel : la
        // première question n'est pas « qui est là » mais « qu'est-ce qui
        // ne colle pas ». Viennent ensuite les deux écrans que l'usage
        // réclame vraiment — chercher quelqu'un, et tout recouper.
        { id: "ou_ca_coince", label: "Où ça coince", icon: Compass },
        { id: "personnes", label: "Référentiel", icon: Users2 },
        // Un mouvement en cours d'année déclenche sept ou huit gestes
        // dans autant de systèmes. L'onglet mène à l'écran qui les montre
        // *et* les applique ; la liste des conséquences reste accessible
        // depuis lui, pour les arrivées et les départs.
        { id: "mouvements", label: "Mouvements", icon: Shuffle },
        { id: "concordance", label: "Concordance", icon: GitCompare },
        // « Qui n'a pas de photo » est demandé toutes les semaines : la
        // réponse mérite une porte, pas une case à cocher dans un contrôle.
        { id: "photos", label: "Les photos", icon: Camera },
        // Faire des cartes est une tâche à part entière, et récurrente :
        // elle avait sa place dans un onglet d'un écran d'export, où
        // personne n'allait la chercher.
        { id: "cartes", label: "Les cartes", icon: CreditCard },
        { id: "exports", label: "Produire un fichier", icon: FileDown },
        // « Pourquoi ce compte est-il là ? » se pose des mois après :
        // le journal existait, il n'avait simplement pas de porte.
        { id: "sodexo", label: "Sodexo", icon: UtensilsCrossed },
        { id: "journal", label: "Ce qui a été fait", icon: History },
      ],
    },
    {
      id: "materiel",
      label: "Chromebooks",
      icon: Laptop,
      resume: "Le parc, le stock, les pannes, les prêts",
      ecrans: [
        // « Qui a quoi » avant « où est quoi » : c'est la question qu'on
        // pose en salle des profs, et elle demande la liste des gens.
        { id: "affectations", label: "Affectations", icon: UserPlus },
        // Le suivi local d'abord : c'est lui qui répond à la question
        // qu'on se pose devant un carton de machines mortes, et c'est sur
        // lui qu'on agit.
        { id: "atelier", label: "Parc et pannes", icon: Wrench },
        // « La flotte » et non « le parc » : cet écran lit l'inventaire
        // Google, là où « Parc et pannes » tient le suivi local. Deux
        // écrans nommés « parc » se confondaient.
        { id: "chromebooks", label: "La flotte Google", icon: Laptop },
        { id: "accessoires", label: "Les accessoires", icon: Cable },
        // Les badges tiennent au matériel autant qu'aux comptes : la
        // carte est un objet qu'on encode, qu'on perd et qu'on refait.
        { id: "ts1000", label: "Badges et accès", icon: Nfc },
      ],
    },
  ];

  /**
   * Les modules bruts, atteignables sans passer par une étape.
   *
   * Le parcours et les constats couvrent l'usage courant, mais il arrive
   * qu'on veuille lancer une bascule ou une conformité seule, hors de toute
   * campagne. Rien n'a été retiré : ces écrans restent ici et dans la
   * recherche, simplement hors du chemin.
   */
  const OUTILS = [
    { id: "sites", label: "Sites", icon: Building2 },
    { id: "table_correspondance", label: "Table de correspondance", icon: TableIcon },
    { id: "amorcage", label: "Amorçage KoXo", icon: Rocket },
    { id: "snapshots", label: "Snapshots d'années", icon: Database },
    { id: "arbitrage", label: "Arbitrage", icon: Scale },
    { id: "simulation", label: "Simulation", icon: Zap },
    { id: "bascule", label: "Bascule des OU", icon: FolderTree },
    { id: "conformite_google", label: "Conformité Google", icon: ShieldCheck },
    { id: "controle_koxo", label: "Contrôle KoXo", icon: ShieldCheck },
    { id: "reconciliation", label: "Réconciliation", icon: GitCompareArrows },
    { id: "sortants", label: "Sortants", icon: LogOut },
    { id: "nouveaux", label: "Nouveaux arrivants", icon: UserPlus },
    { id: "arrivees", label: "Arrivée", icon: UserPlus },
    { id: "bilan", label: "Bilan de rentrée", icon: ClipboardCheck },
    { id: "coffre", label: "Coffre", icon: KeyRound },
    { id: "statistiques", label: "Statistiques", icon: BarChart3 },
    { id: "suivi", label: "Suivi", icon: Activity },
  ];

  /** Hors des trois parties : on y va une fois par an. */
  const A_PART = [
    { id: "parametres", label: "Paramètres", icon: Settings },
    { id: "aide", label: "Aide", icon: HelpCircle },
  ];

  const TOUS_LES_ECRANS = [
    ...PARTIES.flatMap((p) => p.ecrans),
    ...OUTILS,
    ...A_PART,
  ].filter((e, i, tous) => tous.findIndex((x) => x.id === e.id) === i);

  /**
   * La partie ouverte suit l'écran, et non l'inverse.
   *
   * On arrive sur un écran par bien d'autres chemins que la barre : la
   * recherche, la frise, un bouton d'un autre écran. Déduire la partie de
   * l'écran courant garantit que l'onglet souligné est toujours celui où
   * l'on se trouve — au lieu d'un état parallèle qui se désynchronise.
   */
  /**
   * Les écrans qu'on atteint depuis un autre, et qui ne sont dans aucune
   * barre.
   *
   * « Départager » se rejoint depuis « Où ça coince » ou l'accueil ; lui
   * donner un onglet permanent mettrait au même rang qu'un module un écran
   * qu'on ouvre trois fois l'an. Mais il doit garder sa partie : sinon la
   * barre se vide en y entrant, et l'on ne sait plus d'où l'on vient.
   */
  const RATTACHEMENTS = {
    departager: { partie: "annee", depuis: "ou_ca_coince" },
    fiche: { partie: "annee", depuis: "personnes" },
    bouge: { partie: "annee", depuis: "mouvements" },
  };

  /**
   * La personne dont la page est ouverte.
   *
   * Elle vit ici plutôt que dans l'écran : on y arrive depuis le
   * Référentiel, depuis une liste de photos, depuis un constat — et
   * l'écran de destination ne doit pas dépendre de celui d'où l'on vient.
   */
  let personneOuverte = $state(/** @type {number|null} */ (null));

  function ouvrirFiche(id) {
    personneOuverte = id;
    page = "fiche";
  }

  let partieActive = $derived(
    PARTIES.find((p) => p.ecrans.some((e) => e.id === page))?.id ??
      RATTACHEMENTS[page]?.partie ??
      null,
  );
  let ecransDeLaPartie = $derived(
    PARTIES.find((p) => p.id === partieActive)?.ecrans ?? [],
  );

  /** Changer de partie ouvre son premier écran, qui en est l'entrée. */
  function allerDansLaPartie(partie) {
    if (partie.id === partieActive) return;
    page = partie.ecrans[0].id;
  }

  /**
   * Raccourcis de navigation.
   *
   * `Ctrl+1` à `Ctrl+9` suivent l'ordre visuel de la rangée d'écrans de la
   * partie ouverte, et non un ordre global. Les neuf premiers changent donc
   * avec la partie — c'est ce qu'on veut : le raccourci porte sur ce qu'on
   * a sous les yeux, pas sur une liste qu'il faudrait mémoriser.
   */
  let ordreRaccourcis = $derived(ecransDeLaPartie.map((e) => e.id));

  // La couleur d'un écran est celle de sa famille, et c'est la
  // navigation qui la connaît : elle la dépose, l'en-tête la lit.
  $effect(() => {
    const partie = PARTIES.find((p) => p.id === partieActive);
    const rattache = RATTACHEMENTS[page];
    const ecranCourant =
      partie?.ecrans.find((e) => e.id === page) ??
      [...OUTILS, ...A_PART].find((e) => e.id === page) ??
      (rattache
        ? partie?.ecrans.find((e) => e.id === rattache.depuis)
        : undefined);
    declarerEcran(page, partieActive ?? "annee", {
      label: ecranCourant?.label ?? "",
      partieLabel: partie?.label ?? "",
      aller: (p) => (page = p),
    });
  });

  /**
   * Le trait qui souligne l'onglet ouvert, mesuré sur le bouton réel.
   *
   * Un calcul en pourcentage casserait dès qu'un libellé change de
   * longueur, et ils n'ont pas tous la même. On lit la géométrie du DOM,
   * qui est la seule source exacte — et on la relit quand la fenêtre
   * change de largeur, sinon le trait reste au dernier endroit mesuré.
   */
  let traitEcran = $state({ gauche: 0, largeur: 0, pret: false });

  /**
   * Mesure le bouton ouvert pour y poser le trait.
   *
   * Une **action** plutôt qu'un effet : `use:` reçoit le nœud déjà monté,
   * et son `update` se déclenche après que Svelte a repeint la rangée. Un
   * `$effect` lisant une référence `bind:this` peut tourner avant que
   * cette référence existe, et rien ne le rappelle ensuite — c'est ce qui
   * laissait le trait à zéro.
   *
   * La largeur est lue sur le bouton réel : un calcul en pourcentage
   * casserait dès qu'un libellé change de longueur, et ils n'ont pas tous
   * la même.
   *
   * @param {HTMLElement} rail
   */
  function suivreLOnglet(rail, ouvert) {
    const mesurer = (id) => {
      const actif = rail.querySelector(`[data-ecran="${id}"]`);
      if (!(actif instanceof HTMLElement)) {
        traitEcran = { gauche: 0, largeur: 0, pret: false };
        return;
      }
      traitEcran = {
        gauche: actif.offsetLeft + 6,
        largeur: Math.max(0, actif.offsetWidth - 12),
        pret: true,
      };
    };

    let courant = ouvert;
    // La rangée défile : une largeur de fenêtre qui change déplace les
    // boutons sans qu'aucune page ne change.
    const observateur = new ResizeObserver(() => mesurer(courant));
    observateur.observe(rail);
    mesurer(courant);

    return {
      update(suivant) {
        courant = suivant;
        mesurer(courant);
      },
      destroy() {
        observateur.disconnect();
      },
    };
  }

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

<div class="flex flex-1 flex-col overflow-hidden">
  <!-- Barre du haut : les trois parties, puis les écrans de celle qu'on
       ouvre. Deux niveaux, et à chaque niveau le choix est évident — au
       lieu de vingt-cinq entrées présentées d'un bloc. -->
  <header class="shrink-0 border-b border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900">
    <div class="flex items-center gap-6 px-5 py-2.5">
      <!-- Le logo ramène à l'accueil.
           Il n'y menait pas : une fois entré dans une partie, plus aucun
           chemin ne revenait à la page d'accueil, qui devenait un écran
           qu'on ne voyait qu'au lancement. Cliquer le nom du programme pour
           revenir à son entrée est la convention la plus répandue qui soit ;
           elle manquait, simplement. -->
      <button
        type="button"
        class="flex items-center gap-2.5 rounded-xl px-1.5 py-1 transition-colors hover:bg-stone-100 dark:hover:bg-stone-800"
        title="Revenir à l'accueil"
        aria-current={page === "accueil" ? "page" : undefined}
        onclick={() => (page = "accueil")}
      >
        <!-- Les quatre pastilles ne décorent pas : ce sont les couleurs des
             familles, et donc la clé du code employé partout ailleurs. -->
        <span
          class="grid h-9 w-9 shrink-0 grid-cols-2 grid-rows-2 gap-1 rounded-xl bg-stone-900 p-1.5 dark:bg-stone-800"
          aria-hidden="true"
        >
          <span class="rounded-full" style="background: {TEINTES.rentree}"></span>
          <span class="rounded-full" style="background: {TEINTES.annee}"></span>
          <span class="rounded-full" style="background: {TEINTES.materiel}"></span>
          <span class="rounded-full" style="background: {TEINTES.repas}"></span>
        </span>
        <span class="flex flex-col text-left leading-tight whitespace-nowrap">
          <span class="titre-affiche text-[17px] text-stone-900 dark:text-stone-100">
            Appli Rentrée
          </span>
          <span class="text-[11px] text-stone-500 dark:text-stone-400">Ensemble Scolaire du Kreisker</span>
        </span>
      </button>

      <nav class="flex items-center gap-1" aria-label="Parties">
        {#each PARTIES as partie (partie.id)}
          {@const actif = partieActive === partie.id}
          {@const teintePartie = TEINTES[partie.id] ?? TEINTES.annee}
          <button
            class="flex items-center gap-2 rounded-full px-4 py-2 text-sm transition-colors duration-150
                   {actif
                     ? 'font-semibold'
                     : 'font-medium text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800'}"
            style={actif
              ? `color: ${teintePartie}; background: color-mix(in oklab, ${teintePartie} 12%, transparent);`
              : ""}
            title={partie.resume}
            aria-label={partie.label}
            aria-current={actif ? "page" : undefined}
            onclick={() => allerDansLaPartie(partie)}
          >
            <partie.icon class="h-4 w-4 shrink-0" />
            {partie.label}
            {#if partie.id === "rentree" && nbArbitragesEnAttente > 0}
              <span class="rounded-full bg-red-500 px-1.5 py-0 text-[10px] font-bold text-white">
                {nbArbitragesEnAttente}
              </span>
            {/if}
          </button>
        {/each}
      </nav>

      <div class="ml-auto flex items-center gap-2">
        <button
          class="flex items-center gap-2 rounded-full border border-stone-300 px-3.5 py-1.5 text-sm text-stone-600 transition hover:border-stone-400 hover:bg-stone-100 dark:border-stone-700 dark:text-stone-400 dark:hover:border-stone-600 dark:hover:bg-stone-800"
          onclick={() => (paletteOuverte = true)}
        >
          <Search class="h-4 w-4" />
          <span>Rechercher…</span>
          <kbd class="rounded border border-stone-300 px-1 py-0 text-[10px] font-medium text-stone-500 dark:border-stone-700">
            Ctrl K
          </kbd>
        </button>

        <!-- L'année de travail, visible en permanence : un écran de
             concordance ne dit pas de lui-même quelle année il compare. -->
        <SelecteurAnnee />

        {#each A_PART as ecran (ecran.id)}
          <button
            class="rounded-md p-2 transition {page === ecran.id
              ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/35 dark:text-emerald-300'
              : 'text-stone-500 hover:bg-stone-100 hover:text-stone-800 dark:text-stone-400 dark:hover:bg-stone-700 dark:hover:text-stone-200'}"
            title={ecran.label}
            aria-label={ecran.label}
            onclick={() => (page = ecran.id)}
          >
            <ecran.icon class="h-4 w-4" />
          </button>
        {/each}

        <button
          class="rounded-md p-2 text-stone-500 transition hover:bg-stone-100 hover:text-stone-800 dark:text-stone-400 dark:hover:bg-stone-700 dark:hover:text-stone-200"
          title={$theme === "clair" ? "Passer en mode sombre" : "Passer en mode clair"}
          onclick={basculerTheme}
        >
          {#if $theme === "clair"}<Moon class="h-4 w-4" />{:else}<Sun class="h-4 w-4" />{/if}
        </button>

        <div class="flex items-center gap-1.5 border-l border-stone-200 pl-3 text-xs text-stone-500 dark:border-stone-700 dark:text-stone-400">
          <span
            class="inline-block h-2 w-2 rounded-full {backendOk === true
              ? 'bg-emerald-500'
              : backendOk === false
                ? 'bg-red-500'
                : 'bg-stone-300'}"
          ></span>
          <span class="tabular-nums">
            {backendOk === true ? `v${versionBackend}` : backendOk === false ? "hors-ligne" : "…"}
          </span>
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
    </div>

    <!-- Les écrans de la partie ouverte. Ils défilent plutôt que de passer
         à la ligne : la hauteur de la barre doit rester constante, sinon le
         contenu saute d'une partie à l'autre. -->
    {#if ecransDeLaPartie.length > 1}
      <!-- Le trait glisse d'un onglet à l'autre plutôt que de s'éteindre
           ici pour se rallumer là : on voit d'où l'on vient, et le
           déplacement fait comprendre que c'est la même barre. -->
      <nav
        class="relative flex gap-0.5 overflow-x-auto px-5"
        aria-label="Écrans"
        use:suivreLOnglet={page}
      >
        {#each ecransDeLaPartie as ecran (ecran.id)}
          {@const actif = page === ecran.id}
          {@const teinteEcran = teinte(ecran.id, partieActive ?? "annee")}
          <button
            class="relative flex shrink-0 items-center gap-2 px-3 py-2 text-[13px] transition-colors duration-150
                   {actif
                     ? 'font-semibold'
                     : 'font-medium text-stone-500 hover:text-stone-800 dark:text-stone-400 dark:hover:text-stone-200'}"
            style={actif ? `color: ${teinteEcran};` : ""}
            aria-current={actif ? "page" : undefined}
            data-ecran={ecran.id}
            onclick={() => (page = ecran.id)}
          >
            <ecran.icon class="h-3.5 w-3.5 shrink-0" />
            {ecran.label}
            {#if ecran.badge && ecran.badge() > 0}
              <span class="rounded-full bg-red-500 px-1.5 py-0 text-[10px] font-bold text-white">
                {ecran.badge()}
              </span>
            {/if}
          </button>
        {/each}
        <span
          class="pointer-events-none absolute bottom-0 h-0.5 rounded-t-full transition-[left,width,background-color] duration-300 ease-out"
          style="left: {traitEcran.gauche}px; width: {traitEcran.largeur}px;
                 background: {teinte(page, partieActive ?? 'annee')};
                 opacity: {traitEcran.pret ? 1 : 0};"
          aria-hidden="true"
        ></span>
      </nav>
    {/if}
  </header>

  <!-- Zone principale -->
  <main class="flex-1 overflow-auto bg-stone-50 dark:bg-stone-950">
    <!-- La frise a disparu : le parcours porte désormais son propre rail,
         qui dit la même chose en mieux — l'étape ouverte y est en entier,
         pas seulement pointée. Deux rails empilés diraient deux fois la
         même chose et repousseraient l'outil hors de l'écran. -->

    <!-- `{#key}` reconstruit le bloc à chaque navigation, ce qui relance
         l'animation d'apparition — sinon Svelte réutilise le nœud et rien
         ne bouge visuellement. -->
    {#key page}
      <!-- Apparition sans `transform` : ce conteneur englobe les modales des
           écrans, et un transform ferait d'elles des enfants de cette div
           plutôt que de la fenêtre — elles se retrouveraient rognées. -->
      <!-- La largeur suit l'écran plutôt qu'un gabarit de lecture : ces
           pages portent surtout des tableaux, où chaque colonne gagnée
           évite une troncature. Ce qui se lit en prose — la description
           d'en-tête — garde son propre plafond, sinon les lignes de texte
           deviendraient interminables. -->
      <div class="anim-apparition-sans-transform mx-auto max-w-[1800px] p-6">
        {#if page === "accueil"}
          <TableauDeBord
            onNaviguer={(p) => (page = p)}
            parties={PARTIES}
            onRechercher={() => (paletteOuverte = true)}
          />
        {:else if page === "personnes"}
          <Personnes onOuvrirFiche={ouvrirFiche} />
        {:else if page === "coffre"}
          <Coffre />
        {:else if page === "arrivees"}
          <Arrivees />
        {:else if page === "concordance"}
          <Concordance />
        {:else if page === "bilan"}
          <Bilan />
        {:else if page === "mouvements"}
          <Mouvements onNaviguer={(p) => (page = p)} />
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
        {:else if page === "ou_ca_coince"}
          <OuCaCoince onNaviguer={(p) => (page = p)} />
        {:else if page === "parcours"}
          <Parcours etats={etapesEtats} onRelireAvancement={relireAvancement} />
        {:else if page === "bouge"}
          <QuelquunBouge onNaviguer={(p) => (page = p)} />
        {:else if page === "sodexo"}
          <Sodexo />
        {:else if page === "cartes"}
          <Cartes />
        {:else if page === "affectations"}
          <Affectations onNaviguer={(p) => (page = p)} />
        {:else if page === "departager"}
          <Departager onNaviguer={(p) => (page = p)} />
        {:else if page === "fiche" && personneOuverte !== null}
          <FichePersonne
            personneId={personneOuverte}
            onNaviguer={(p) => (page = p)}
            onRetour={() => (page = "personnes")}
          />
        {:else if page === "journal"}
          <Journal />
        {:else if page === "photos"}
          <Photos />
        {:else if page === "ts1000"}
          <Ts1000 />
        {:else if page === "atelier"}
          <Atelier />
        {:else if page === "accessoires"}
          <Accessoires />
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
  ecrans={TOUS_LES_ECRANS}
  onAller={(id) => (page = id)}
/>
<ToasterContainer />
{/if}
