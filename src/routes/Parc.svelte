<script>
  import { onMount } from "svelte";
  import Laptop from "@lucide/svelte/icons/laptop";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import CloudUpload from "@lucide/svelte/icons/cloud-upload";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Onglets from "$lib/components/Onglets.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import ListeParc from "$lib/components/parc/ListeParc.svelte";
  import Echanger from "$lib/components/parc/Echanger.svelte";
  import Stock from "$lib/components/parc/Stock.svelte";
  import Journal from "$lib/components/parc/Journal.svelte";
  import FicheMachine from "$lib/components/parc/FicheMachine.svelte";
  import Pointage from "$lib/components/parc/Pointage.svelte";
  import Atelier from "./Atelier.svelte";
  import { parc } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";
  import { ilYA, messageErreur } from "$lib/parc.js";

  /**
   * Le parc : toutes les machines, le stock, l'atelier, et ce qui a été fait.
   *
   * ## Pourquoi un seul écran (Johann, 16/11/2026)
   *
   * « Parc et pannes » ne connaissait que les numéros tapés à la main, et
   * « Les accessoires » vivait à côté. Or échanger la machine d'un prof
   * touche les trois à la fois : on prend au stock, l'ancienne part à
   * l'atelier, et on donne un chargeur avec. Un geste, un écran.
   *
   * « La flotte Google » reste à part : elle sert la rentrée — à réclamer
   * aux partants, à équiper les arrivants.
   *
   * ## D'où viennent les machines
   *
   * Du dernier relevé de la console Google, gardé en base : l'écran s'ouvre
   * tout de suite, et dit de quand date ce qu'il montre. « Relire Google »
   * le rafraîchit.
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  let inv = $state(/** @type {any} */ (null));
  let accessoires = $state(/** @type {any} */ (null));
  let personnes = $state(/** @type {any[]} */ ([]));
  let vocabulaire = $state(/** @type {any} */ (null));
  let chargement = $state(true);
  let releve = $state(false);
  let ecriture = $state(false);
  let erreur = $state("");
  let vue = $state(lire("parc.vue", "parc"));
  $effect(() => ecrire("parc.vue", vue));

  let ouverte = $state(/** @type {string|null} */ (null));
  let depart = $state(/** @type {any} */ (null));
  let version = $state(0);

  async function charger() {
    erreur = "";
    try {
      const [i, a, p, v] = await Promise.all([
        parc.inventaire(),
        parc.accessoires(),
        parc.personnes(),
        parc.vocabulaire(),
      ]);
      inv = i;
      accessoires = a;
      personnes = p;
      vocabulaire = v;
    } catch (e) {
      erreur = messageErreur(e);
    } finally {
      chargement = false;
    }
  }

  /** Après un geste : l'inventaire et les accessoires ont bougé. */
  async function relireApresGeste() {
    version++;
    try {
      const [i, a] = await Promise.all([parc.inventaire(), parc.accessoires()]);
      inv = i;
      accessoires = a;
    } catch (e) {
      notify.erreur(messageErreur(e));
    }
  }

  onMount(async () => {
    await charger();
    // Jamais relevé : la liste serait vide, et c'est Google qui la remplit.
    if (inv && !inv.releve_le) await relever();
  });

  async function relever() {
    releve = true;
    try {
      const r = await parc.releve();
      inv = r.inventaire;
      const morceaux = [`${r.nb} machines lues`];
      if (r.nouveaux && r.nouveaux !== r.nb) morceaux.push(`${r.nouveaux} nouvelles`);
      if (r.disparus) morceaux.push(`${r.disparus} disparues de la console`);
      if (r.reconcilies) morceaux.push(`${r.reconcilies} étiquettes désormais à jour`);
      notify.succes(morceaux.join(" · "), { duree: 8000 });
    } catch (e) {
      notify.erreur(messageErreur(e), { duree: 15000 });
    } finally {
      releve = false;
    }
  }

  async function reporterTout() {
    ecriture = true;
    try {
      const r = await parc.reporterGoogle(null);
      inv = r.inventaire;
      version++;
      const ok = r.google.filter((g) => g.ok).length;
      const ko = r.google.filter((g) => !g.ok);
      if (ok) notify.succes(`${ok} étiquette${ok > 1 ? "s" : ""} écrite${ok > 1 ? "s" : ""} dans Google.`);
      if (ko.length) notify.erreur(`${ko.length} refusée${ko.length > 1 ? "s" : ""} : ${ko[0].message}`, { duree: 20000 });
    } catch (e) {
      notify.erreur(messageErreur(e), { duree: 15000 });
    } finally {
      ecriture = false;
    }
  }

  function versEchange(p) {
    ouverte = null;
    depart = p.etat === "en_stock" ? { nouvelle: p.serie } : { ancienne: p.serie };
    vue = "echanger";
  }

  let postes = $derived(inv?.postes ?? []);
  let chargeursAuStock = $derived(
    (accessoires?.accessoires ?? []).filter((a) => a.type === "chargeur" && a.etat === "en_stock"),
  );
  let nbHs = $derived(inv?.par_etat?.hs ?? 0);
  let nbStock = $derived(inv?.par_etat?.en_stock ?? 0);
  let nbService = $derived(inv?.par_etat?.en_service ?? 0);

  let onglets = $derived([
    { id: "parc", label: "Tout le parc", compte: postes.length },
    { id: "echanger", label: "Échanger" },
    { id: "stock", label: "Le stock", compte: nbStock },
    { id: "atelier", label: "L'atelier", compte: nbHs },
    {
      id: "inventorier",
      label: inv?.pointage_depuis ? `Inventorier (${inv.pointees}/${inv.pointees + inv.a_pointer})` : "Inventorier",
    },
    { id: "journal", label: "Journal" },
  ]);
</script>

<section class="space-y-5">
  <EnTetePage
    icon={Laptop}
    titre="Le parc"
    description="Chaque Chromebook, chez qui ou dans quelle salle. Échanger la machine d'un prof en piochant dans le stock, suivre les chargeurs de rechange et les machines en panne."
  >
    {#snippet actions()}
      {#if inv?.nb_a_reporter}
        <Bouton icon={CloudUpload} occupe={ecriture} onclick={reporterTout}>
          Écrire {inv.nb_a_reporter} étiquette{inv.nb_a_reporter > 1 ? "s" : ""} dans Google
        </Bouton>
      {/if}
      <Bouton icon={RefreshCw} occupe={releve} onclick={relever}>Relire Google</Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">{erreur}</p>
  {/if}

  {#if chargement && !inv}
    <Squelette variante="ligne-tableau" nb={6} colonnes={4} />
  {:else if inv}
    <!-- Les grands nombres : ce qui tourne, ce qui reste, ce qui est mort. -->
    <div class="flex flex-wrap items-end gap-x-12 gap-y-4 border-b border-stone-200 pb-5 dark:border-stone-800">
      <div>
        <p class="titre-affiche text-[32px] leading-none tabular-nums">{nbService}</p>
        <p class="mt-1 text-[13px] text-stone-600 dark:text-stone-400">en service</p>
      </div>
      <button class="text-left" onclick={() => (vue = "stock")}>
        <p class="titre-affiche text-[32px] leading-none tabular-nums {nbStock < inv.seuils.machines ? 'text-amber-700 dark:text-amber-400' : 'text-sky-700 dark:text-sky-400'}">
          {nbStock}
        </p>
        <p class="mt-1 text-[13px] text-stone-600 dark:text-stone-400">au stock</p>
      </button>
      <button class="text-left" onclick={() => (vue = "stock")}>
        <p class="titre-affiche text-[32px] leading-none tabular-nums {inv.chargeurs_en_stock < inv.seuils.chargeurs ? 'text-amber-700 dark:text-amber-400' : ''}">
          {inv.chargeurs_en_stock}
        </p>
        <p class="mt-1 text-[13px] text-stone-600 dark:text-stone-400">chargeurs de rechange</p>
      </button>
      <button class="text-left" onclick={() => (vue = "atelier")}>
        <p class="titre-affiche text-[32px] leading-none tabular-nums {nbHs ? 'text-red-700 dark:text-red-400' : 'text-stone-400'}">{nbHs}</p>
        <p class="mt-1 text-[13px] text-stone-600 dark:text-stone-400">hors service</p>
      </button>
      <div>
        <p class="titre-affiche text-[32px] leading-none tabular-nums {inv.fin_maj.depassee ? 'text-red-700 dark:text-red-400' : 'text-stone-400'}">
          {inv.fin_maj.depassee}
        </p>
        <p class="mt-1 text-[13px] text-stone-600 dark:text-stone-400">
          sans mises à jour{#if inv.fin_maj.cette_annee} · {inv.fin_maj.cette_annee} d'ici l'été{/if}
        </p>
      </div>
      <p class="ml-auto text-xs text-stone-500 dark:text-stone-400">
        {inv.releve_le ? `Relevé Google ${ilYA(inv.releve_le)}` : "Jamais relevé"}
      </p>
    </div>

    {#if inv.alertes.length}
      <ul class="space-y-1">
        {#each inv.alertes as a (a)}
          <li class="flex items-start gap-2 text-sm text-amber-800 dark:text-amber-300">
            <TriangleAlert class="mt-0.5 h-4 w-4 shrink-0" /> {a}
          </li>
        {/each}
      </ul>
    {/if}

    <Onglets {onglets} bind:valeur={vue} onChange={(id) => id !== "echanger" && relireApresGeste()} />

    {#if vue === "parc"}
      {#if postes.length}
        <ListeParc {postes} onOuvrir={(s) => (ouverte = s)} />
      {:else}
        <p class="py-8 text-center text-sm text-stone-500">
          Aucune machine : relis la flotte chez Google pour remplir l'inventaire.
        </p>
      {/if}
    {:else if vue === "echanger"}
      <Echanger
        {postes}
        {personnes}
        {vocabulaire}
        chargeurs={chargeursAuStock}
        {depart}
        onFait={(r) => {
          inv = r.inventaire;
          relireApresGeste();
        }}
      />
    {:else if vue === "stock"}
      <Stock
        {postes}
        stockAccessoires={accessoires}
        {personnes}
        seuils={inv.seuils}
        onOuvrir={(s) => (ouverte = s)}
        onModifie={relireApresGeste}
      />
    {:else if vue === "atelier"}
      <Atelier sansEntete />
    {:else if vue === "inventorier"}
      <Pointage
        {inv}
        {personnes}
        {vocabulaire}
        onInventaire={(i) => {
          inv = i;
          version++;
        }}
        onOuvrir={(s) => (ouverte = s)}
      />
    {:else if vue === "journal"}
      <Journal raisons={vocabulaire?.raisons ?? {}} {personnes} {version} onOuvrir={(s) => (ouverte = s)} />
    {/if}
  {/if}
</section>

{#if ouverte}
  {#key ouverte}
    <FicheMachine
      serie={ouverte}
      raisons={vocabulaire?.raisons ?? {}}
      onFermer={() => (ouverte = null)}
      onEchanger={versEchange}
      onModifie={relireApresGeste}
    />
  {/key}
{/if}
