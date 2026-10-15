<script>
  import { onMount, setContext } from "svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import Accueil from "$lib/components/rentree/Accueil.svelte";
  import Fil from "$lib/components/rentree/Fil.svelte";
  import Etape from "$lib/components/rentree/Etape.svelte";
  import FinChapitre from "$lib/components/rentree/FinChapitre.svelte";
  import ComptesGoogleNouveaux from "$lib/components/ComptesGoogleNouveaux.svelte";
  import { rentreeApi } from "$lib/api.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";
  import { notify } from "$lib/toasts.js";

  import Parametres from "./Parametres.svelte";
  import Coffre from "./Coffre.svelte";
  import Sites from "./Sites.svelte";
  import TableCorrespondance from "./TableCorrespondance.svelte";
  import Snapshots from "./Snapshots.svelte";
  import Arbitrage from "./Arbitrage.svelte";
  import Departager from "./Departager.svelte";
  import Exports from "./Exports.svelte";
  import ControleKoxo from "./ControleKoxo.svelte";
  import Concordance from "./Concordance.svelte";
  import Sortants from "./Sortants.svelte";
  import RenommerOu from "./RenommerOu.svelte";
  import Bascule from "./Bascule.svelte";
  import GroupesGoogle from "./GroupesGoogle.svelte";
  import Cartes from "./Cartes.svelte";
  import Ts1000 from "./Ts1000.svelte";
  import Sodexo from "./Sodexo.svelte";
  import Chromebooks from "./Chromebooks.svelte";
  import Bilan from "./Bilan.svelte";

  /**
   * La rentrée, conduite comme un long tutoriel.
   *
   * Demandé par Johann le 15 octobre 2026 : « qu'une personne qui n'a
   * jamais géré la rentrée voie le programme, et juste en suivant les
   * étapes, puisse le faire ultra facilement ». Maquettes : tours 7 et
   * 7 bis du canvas.
   *
   * Quatre vues, une seule à la fois :
   *
   * - **l'accueil**, avant la toute première étape : ce qui attend, ce
   *   qu'il faut avoir sous la main ;
   * - **le fil** : où l'on en est, la prochaine étape, le calendrier ;
   * - **une étape**, geste par geste, avec son avant / après ;
   * - **la fin d'un chapitre** : ce qui a changé, ce qui reste à surveiller.
   *
   * L'ordre et les validations sont tenus par le serveur
   * (`backend/services/rentree.py`) ; les textes qui guident, par
   * `$lib/rentree/etapes.js`. Les outils sont ceux du programme, embarqués
   * dans l'étape : le contexte `parcours.embarque` efface leur en-tête.
   *
   * Avant le 1er juillet, la rentrée suivante ne se commence pas — ses
   * étapes viseraient l'année qui tourne encore. Elle se **visite** : tout
   * le chemin, rien de lu, rien d'enregistré, aucun outil lancé.
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  setContext("parcours.embarque", true);

  /** L'outil de chaque geste « programme », par la page qu'il désigne. */
  const OUTILS = {
    parametres: { composant: Parametres, label: "Paramètres" },
    coffre: { composant: Coffre, label: "Coffre" },
    sites: { composant: Sites, label: "Établissements" },
    table_correspondance: { composant: TableCorrespondance, label: "Table de correspondance" },
    snapshots: { composant: Snapshots, label: "Ingestion de l'export" },
    arbitrage: { composant: Arbitrage, label: "Arbitrage" },
    departager: { composant: Departager, label: "Départager les adresses" },
    exports: { composant: Exports, label: "Les exports" },
    controle_koxo: { composant: ControleKoxo, label: "Contrôle KoXo" },
    concordance: { composant: Concordance, label: "Concordance" },
    comptes_google_nouveaux: { composant: ComptesGoogleNouveaux, label: "Comptes Google des nouveaux" },
    sortants: { composant: Sortants, label: "Sortants" },
    renommer_ou: { composant: RenommerOu, label: "Unités de l'année" },
    bascule: { composant: Bascule, label: "Bascule des unités" },
    groupes_google: { composant: GroupesGoogle, label: "Groupes Google" },
    cartes: { composant: Cartes, label: "Les cartes" },
    ts1000: { composant: Ts1000, label: "Badges et accès" },
    sodexo: { composant: Sodexo, label: "Sodexo" },
    chromebooks: { composant: Chromebooks, label: "La flotte Google" },
    bilan: { composant: Bilan, label: "Bilan de rentrée" },
  };

  let etat = $state(/** @type {any} */ (null));
  let erreur = $state(/** @type {string|null} */ (null));
  let commencement = $state(false);

  /** La vue survit à la navigation : une rentrée dure des jours. */
  let vue = $state(lire("rentree.vue", /** @type {any} */ ({ type: "fil" })));
  let visite = $state(lire("rentree.visite", false));
  $effect(() => ecrire("rentree.vue", vue));
  $effect(() => ecrire("rentree.visite", visite));

  const libelle = (e) => String(e).replace(/^Error:\s*/, "");

  async function charger() {
    erreur = null;
    try {
      etat = await rentreeApi.etat();
      if (etat.commencee) visite = false;
    } catch (e) {
      erreur = libelle(e);
    }
  }
  onMount(charger);

  async function commencer() {
    commencement = true;
    try {
      etat = await rentreeApi.commencer(etat.annee);
      visite = false;
      vue = { type: "etape", id: etat.etapes[0].id };
    } catch (e) {
      notify.erreur(libelle(e), { duree: 10000 });
    } finally {
      commencement = false;
    }
  }

  let racine = $state(/** @type {HTMLElement|null} */ (null));

  /** Change de vue, et remonte : le défilement est celui de l'application. */
  function aller(v) {
    vue = v;
    racine?.closest("main")?.scrollTo({ top: 0 });
  }

  let accueil = $derived(etat && !etat.commencee && !visite);
  let vueValide = $derived(
    etat &&
      ((vue.type === "etape" && etat.etapes.some((e) => e.id === vue.id)) ||
        (vue.type === "fin" && etat.chapitres.some((c) => c.id === vue.chapitre)) ||
        vue.type === "fil"),
  );
</script>

<div bind:this={racine}>
{#if erreur}
  <div class="card px-6 py-5">
    <p class="font-semibold text-stone-900 dark:text-stone-100">La rentrée ne se lit pas</p>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-300">{erreur}</p>
    <div class="mt-3"><Bouton onclick={charger}>Réessayer</Bouton></div>
  </div>
{:else if !etat}
  <Squelette variante="carte" nb={2} />
{:else if accueil}
  <Accueil
    annee={etat.annee}
    chapitres={etat.chapitres}
    occupe={commencement}
    tropTot={etat.trop_tot}
    ouvreLe={etat.s_ouvre_le}
    onCommencer={commencer}
    onVisiter={() => {
      visite = true;
      aller({ type: "fil" });
    }}
  />
{:else}
  {#if visite}
    <div class="mb-3 flex justify-end">
      <button type="button" class="text-sm font-semibold text-stone-600 hover:underline dark:text-stone-300" onclick={() => (visite = false)}>
        Quitter la visite
      </button>
    </div>
  {/if}
  {#if vueValide && vue.type === "etape"}
    <Etape
      {etat}
      etapeId={vue.id}
      {visite}
      outils={OUTILS}
      onEtat={(e) => (etat = e)}
      onAller={aller}
      {onNaviguer}
    />
  {:else if vueValide && vue.type === "fin"}
    <FinChapitre {etat} chapitreId={vue.chapitre} onAller={aller} />
  {:else}
    <Fil {etat} {visite} onAller={aller} />
  {/if}
{/if}
</div>
