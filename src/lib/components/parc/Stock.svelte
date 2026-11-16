<script>
  import PackagePlus from "@lucide/svelte/icons/package-plus";
  import Send from "@lucide/svelte/icons/send";
  import Undo2 from "@lucide/svelte/icons/undo-2";
  import Settings2 from "@lucide/svelte/icons/settings-2";
  import Bouton from "$lib/components/Bouton.svelte";
  import Modale from "$lib/components/Modale.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import ChoixPersonne from "./ChoixPersonne.svelte";
  import { parc } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { enUneLigne, finMaj, jour, messageErreur, TYPES_ACCESSOIRE } from "$lib/parc.js";

  /**
   * Ce qu'il reste : les machines disponibles et les accessoires de rechange.
   *
   * ## Un chargeur se donne, ou se prête
   *
   * Un chargeur de rechange remis à un prof ne revient pas : il est
   * **donné**, quitte le stock, et n'est jamais en retard. Un chargeur
   * dépanné pour la journée est **prêté** et attendu. Les deux se notent,
   * parce que la question « à qui ai-je passé mes chargeurs » vaut pour
   * les deux.
   *
   * @typedef {Object} Props
   * @property {any[]} postes
   * @property {any} stockAccessoires - réponse de `parc.accessoires()`
   * @property {any[]} personnes
   * @property {{machines: number, chargeurs: number}} seuils
   * @property {(serie: string) => void} onOuvrir
   * @property {() => void} onModifie
   */
  /** @type {Props} */
  let { postes = [], stockAccessoires, personnes = [], seuils, onOuvrir, onModifie } = $props();

  let machines = $derived(
    postes
      .filter((p) => p.etat === "en_stock")
      .sort((a, b) => (b.fin_maj ?? "").localeCompare(a.fin_maj ?? "")),
  );
  let accessoires = $derived(stockAccessoires?.accessoires ?? []);

  /** Combien de chaque type sont encore au stock — la question la plus fréquente. */
  let parType = $derived.by(() => {
    const r = {};
    for (const a of accessoires) {
      r[a.type] ??= { en_stock: 0, dehors: 0 };
      if (a.etat === "en_stock") r[a.type].en_stock++;
      else if (a.etat === "prete" || a.etat === "donne") r[a.type].dehors++;
    }
    return r;
  });

  let filtreAcc = $state("en_stock");
  let listeAcc = $derived(
    accessoires
      .filter((a) => !filtreAcc || (filtreAcc === "dehors" ? ["prete", "donne"].includes(a.etat) : a.etat === filtreAcc))
      .sort((a, b) => Number(b.en_retard) - Number(a.en_retard) || a.serie.localeCompare(b.serie, "fr", { numeric: true })),
  );

  const nomDe = (adresse) => {
    const p = personnes.find((x) => x.adresse === adresse);
    return p ? `${p.prenom} ${p.nom}` : adresse;
  };

  // --- Entrer une machine au stock -------------------------------------
  let serieMachine = $state("");
  let occupe = $state("");

  async function machineAuStock() {
    const serie = serieMachine.trim();
    if (!serie) return;
    occupe = "machine";
    try {
      await parc.mettreAuStock(serie, { precision: "entrée au stock" });
      notify.succes(`${serie} entrée au stock.`);
      serieMachine = "";
      onModifie();
    } catch (e) {
      notify.erreur(messageErreur(e), { duree: 10000 });
    } finally {
      occupe = "";
    }
  }

  // --- Entrer des accessoires -------------------------------------------
  let entree = $state(/** @type {null | {type: string, mode: string, nombre: number, serie: string, note: string}} */ (null));

  async function entrerAccessoires() {
    if (!entree) return;
    occupe = "acc";
    try {
      if (entree.mode === "lot") {
        await parc.ajouterLot({ type: entree.type, nombre: Number(entree.nombre), note: entree.note.trim() || null });
        notify.succes(`${entree.nombre} ${TYPES_ACCESSOIRE[entree.type]?.toLowerCase() ?? entree.type}(s) entrés au stock — note leur numéro au feutre.`, { duree: 8000 });
        entree = null;
      } else {
        await parc.ajouterAccessoire({ serie: entree.serie.trim() || null, type: entree.type, note: entree.note.trim() || null });
        notify.succes(`${entree.serie.trim() || "Accessoire"} entré au stock.`);
        // On garde la fenêtre ouverte : un carton s'inventorie à la chaîne.
        entree = { ...entree, serie: "", note: "" };
      }
      onModifie();
    } catch (e) {
      notify.erreur(messageErreur(e), { duree: 9000 });
    } finally {
      occupe = "";
    }
  }

  // --- Prêter ou donner ------------------------------------------------
  let sortie = $state(/** @type {null | {serie: string, aQui: string, definitif: boolean, retour: string, note: string}} */ (null));

  async function sortir() {
    if (!sortie?.aQui.trim()) return;
    occupe = "sortie";
    try {
      await parc.preter(sortie.serie, {
        aQui: sortie.aQui.trim(),
        definitif: sortie.definitif,
        retourPrevuLe: sortie.definitif ? null : sortie.retour || null,
        note: sortie.note.trim() || null,
      });
      notify.succes(`${sortie.serie} ${sortie.definitif ? "donné" : "prêté"} à ${nomDe(sortie.aQui.trim())}.`);
      sortie = null;
      onModifie();
    } catch (e) {
      notify.erreur(messageErreur(e), { duree: 9000 });
    } finally {
      occupe = "";
    }
  }

  async function rentrer(serie, etat) {
    try {
      await parc.rendre(serie, { etat });
      notify.succes(etat === "hs" ? `${serie} revenu, noté hors service.` : `${serie} revenu au stock.`);
      onModifie();
    } catch (e) {
      notify.erreur(messageErreur(e), { duree: 9000 });
    }
  }

  // --- Seuils -------------------------------------------------------------
  let reglage = $state(/** @type {null | {machines: number, chargeurs: number}} */ (null));

  async function enregistrerSeuils() {
    if (!reglage) return;
    try {
      await parc.reglerSeuils({ machines: Number(reglage.machines), chargeurs: Number(reglage.chargeurs) });
      notify.succes("Seuils enregistrés.");
      reglage = null;
      onModifie();
    } catch (e) {
      notify.erreur(messageErreur(e));
    }
  }

  const ETATS_ACC = {
    en_stock: ["reference", "Au stock"],
    prete: ["attente", "Prêté"],
    donne: ["pret", "Donné"],
    hs: ["ecart", "Hors service"],
    reforme: ["inconnu", "Réformé"],
  };
</script>

<div class="space-y-8">
  <!-- Les machines disponibles -->
  <section class="space-y-3">
    <div class="flex flex-wrap items-baseline gap-3">
      <h3 class="titre-section">Les machines disponibles</h3>
      <span class="text-sm tabular-nums {machines.length < (seuils?.machines ?? 0) ? 'font-semibold text-amber-700 dark:text-amber-400' : 'text-stone-500'}">
        {machines.length} au stock · seuil {seuils?.machines ?? "—"}
      </span>
      <button
        class="ml-auto inline-flex items-center gap-1 text-xs text-stone-500 hover:text-stone-800 dark:hover:text-stone-200"
        onclick={() => (reglage = { machines: seuils?.machines ?? 3, chargeurs: seuils?.chargeurs ?? 3 })}
      >
        <Settings2 class="h-3.5 w-3.5" /> Seuils d'alerte
      </button>
    </div>
    {#if machines.length}
      <div class="overflow-x-auto">
        <table class="tableau min-w-[40rem]">
          <thead class="entete-tableau">
            <tr>
              <th class="px-3 py-2 text-left">Machine</th>
              <th class="px-3 py-2 text-left">Mises à jour</th>
              <th class="px-3 py-2 text-left">Au stock depuis</th>
              <th class="px-3 py-2 text-left">À savoir</th>
            </tr>
          </thead>
          <tbody class="corps-tableau">
            {#each machines as p (p.serie)}
              {@const maj = finMaj(p.fin_maj)}
              <tr class="cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50" onclick={() => onOuvrir(p.serie)}>
                <td class="px-3 py-1.5">{enUneLigne(p)}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-xs {maj.ton}">{maj.texte}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-xs text-stone-500">{p.depuis ? jour(p.depuis) : "—"}</td>
                <td class="px-3 py-1.5 text-xs text-amber-800 dark:text-amber-300">{p.a_verifier ?? ""}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      <p class="text-sm text-stone-500">Aucune machine au stock.</p>
    {/if}
    <div class="flex flex-wrap items-end gap-2">
      <div class="min-w-64">
        <label class="libelle-champ" for="stock-serie">Entrer une machine au stock</label>
        <input
          id="stock-serie"
          class="champ font-mono"
          placeholder="numéro de série (douchette)"
          bind:value={serieMachine}
          onkeydown={(e) => e.key === "Enter" && machineAuStock()}
        />
      </div>
      <Bouton icon={PackagePlus} occupe={occupe === "machine"} disabled={!serieMachine.trim()} onclick={machineAuStock}>
        Au stock
      </Bouton>
      <p class="basis-full text-xs text-stone-500 dark:text-stone-400">
        Pour une machine neuve, ou réparée hors du programme. Pense à lui donner une étiquette de
        stock dans la console (<span class="font-mono">Prof_10</span>…) si elle n'en a pas.
      </p>
    </div>
  </section>

  <!-- Les accessoires -->
  <section class="space-y-3">
    <div class="flex flex-wrap items-center gap-3">
      <h3 class="titre-section">Chargeurs et accessoires de rechange</h3>
      <Bouton
        taille="sm"
        icon={PackagePlus}
        onclick={() => (entree = { type: "chargeur", mode: "lot", nombre: 1, serie: "", note: "" })}
      >
        Entrer au stock
      </Bouton>
    </div>

    {#if Object.keys(parType).length}
      <div class="flex flex-wrap gap-x-12 gap-y-3">
        {#each Object.entries(parType) as [type, n] (type)}
          <div>
            <p class="titre-affiche text-[28px] leading-none tabular-nums {type === 'chargeur' && n.en_stock < (seuils?.chargeurs ?? 0) ? 'text-amber-700 dark:text-amber-400' : ''}">
              {n.en_stock}
            </p>
            <p class="mt-1 text-[13px] text-stone-600 dark:text-stone-400">
              {TYPES_ACCESSOIRE[type] ?? type}{n.en_stock > 1 ? "s" : ""} au stock · {n.dehors} remis
            </p>
          </div>
        {/each}
      </div>

      <div class="flex flex-wrap gap-1">
        {#each [["en_stock", "Au stock"], ["dehors", "Remis (prêtés ou donnés)"], ["hs", "Hors service"], ["", "Tous"]] as [id, label] (id)}
          <button
            class="rounded-full border px-2.5 py-1 text-xs transition {filtreAcc === id
              ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
              : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
            onclick={() => (filtreAcc = id)}
          >
            {label}
          </button>
        {/each}
      </div>

      <div class="overflow-x-auto">
        <table class="tableau min-w-[44rem]">
          <thead class="entete-tableau">
            <tr>
              <th class="px-3 py-2 text-left">Numéro</th>
              <th class="px-3 py-2 text-left">Type</th>
              <th class="px-3 py-2 text-left">État</th>
              <th class="px-3 py-2 text-left">Chez qui</th>
              <th class="px-3 py-2 text-left">Depuis</th>
              <th class="px-3 py-2 text-right">Geste</th>
            </tr>
          </thead>
          <tbody class="corps-tableau">
            {#each listeAcc as a (a.serie)}
              <tr class={a.en_retard ? "bg-amber-50/70 dark:bg-amber-900/20" : ""}>
                <td class="whitespace-nowrap px-3 py-1.5 font-mono text-xs">{a.serie}</td>
                <td class="px-3 py-1.5 text-xs">{TYPES_ACCESSOIRE[a.type] ?? a.type}</td>
                <td class="px-3 py-1.5">
                  <Pastille etat={ETATS_ACC[a.etat]?.[0] ?? "inconnu"} texte={ETATS_ACC[a.etat]?.[1] ?? a.etat} />
                  {#if a.en_retard}<span class="ml-1 text-xs font-semibold text-amber-700">en retard</span>{/if}
                </td>
                <td class="px-3 py-1.5 text-sm">{a.prete_a ? nomDe(a.prete_a) : "—"}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-xs tabular-nums text-stone-500">
                  {jour(a.prete_le)}{#if a.retour_prevu_le} → {jour(a.retour_prevu_le)}{/if}
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 text-right">
                  {#if a.etat === "prete" || a.etat === "donne"}
                    <Bouton taille="sm" icon={Undo2} onclick={() => rentrer(a.serie, "en_stock")}>Revenu</Bouton>
                    <button
                      class="ml-1 text-xs text-stone-500 underline decoration-dotted hover:text-red-600"
                      onclick={() => rentrer(a.serie, "hs")}
                    >
                      revenu cassé
                    </button>
                  {:else if a.etat === "en_stock"}
                    <Bouton
                      taille="sm"
                      icon={Send}
                      onclick={() => (sortie = { serie: a.serie, aQui: "", definitif: a.type === "chargeur", retour: "", note: "" })}
                    >
                      Remettre
                    </Bouton>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      <p class="text-sm text-stone-500">
        Aucun accessoire enregistré. Entre tes chargeurs de rechange : avec leur numéro s'ils en
        portent un, sinon par lot — le programme les numérote <span class="font-mono">CH-001</span>,
        <span class="font-mono">CH-002</span>…
      </p>
    {/if}
  </section>
</div>

{#if entree}
  <Modale titre="Entrer au stock" onFermer={() => (entree = null)}>
    <div>
      <label class="libelle-champ" for="acc-type">Type</label>
      <select id="acc-type" class="champ" bind:value={entree.type}>
        {#each Object.entries(TYPES_ACCESSOIRE) as [id, label] (id)}
          <option value={id}>{label}</option>
        {/each}
      </select>
    </div>
    <div class="flex gap-4 text-sm">
      <label class="flex items-center gap-1.5">
        <input type="radio" class="accent-emerald-600" bind:group={entree.mode} value="lot" />
        Plusieurs, sans numéro
      </label>
      <label class="flex items-center gap-1.5">
        <input type="radio" class="accent-emerald-600" bind:group={entree.mode} value="serie" />
        Un par un, avec son numéro
      </label>
    </div>
    {#if entree.mode === "lot"}
      <div>
        <label class="libelle-champ" for="acc-nombre">Combien</label>
        <input id="acc-nombre" type="number" min="1" max="200" class="champ max-w-32" bind:value={entree.nombre} />
        <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
          Le programme leur donne un numéro (CH-001…) : écris-le au feutre sur chacun.
        </p>
      </div>
    {:else}
      <div>
        <label class="libelle-champ" for="acc-serie">Numéro de série</label>
        <input
          id="acc-serie"
          class="champ font-mono"
          placeholder="vide : le programme en donne un"
          bind:value={entree.serie}
          onkeydown={(e) => e.key === "Enter" && entrerAccessoires()}
        />
      </div>
    {/if}
    <div>
      <label class="libelle-champ" for="acc-note">Note</label>
      <input id="acc-note" class="champ" placeholder="45 W USB-C, carton de septembre…" bind:value={entree.note} />
    </div>
    {#snippet actions()}
      <Bouton onclick={() => (entree = null)}>Fermer</Bouton>
      <Bouton variante="primary" occupe={occupe === "acc"} onclick={entrerAccessoires}>Enregistrer</Bouton>
    {/snippet}
  </Modale>
{/if}

{#if sortie}
  <Modale titre="Remettre {sortie.serie}" onFermer={() => (sortie = null)}>
    <div>
      <label class="libelle-champ" for="sortie-qui">À qui</label>
      <ChoixPersonne id="sortie-qui" {personnes} elevesAussi bind:valeur={sortie.aQui} />
    </div>
    <div class="flex gap-4 text-sm">
      <label class="flex items-center gap-1.5">
        <input type="radio" class="accent-emerald-600" bind:group={sortie.definitif} value={true} />
        Donné, il ne revient pas
      </label>
      <label class="flex items-center gap-1.5">
        <input type="radio" class="accent-emerald-600" bind:group={sortie.definitif} value={false} />
        Prêté, il doit revenir
      </label>
    </div>
    {#if !sortie.definitif}
      <div>
        <label class="libelle-champ" for="sortie-retour">Retour prévu</label>
        <input id="sortie-retour" type="date" class="champ max-w-48" bind:value={sortie.retour} />
      </div>
    {/if}
    <div>
      <label class="libelle-champ" for="sortie-note">Note</label>
      <input id="sortie-note" class="champ" bind:value={sortie.note} />
    </div>
    {#snippet actions()}
      <Bouton onclick={() => (sortie = null)}>Annuler</Bouton>
      <Bouton variante="primary" occupe={occupe === "sortie"} disabled={!sortie.aQui.trim()} onclick={sortir}>
        {sortie.definitif ? "Donner" : "Prêter"}
      </Bouton>
    {/snippet}
  </Modale>
{/if}

{#if reglage}
  <Modale titre="Seuils d'alerte" onFermer={() => (reglage = null)}>
    <p class="text-sm text-stone-600 dark:text-stone-300">
      En dessous, l'écran le signale : il est temps de commander ou de réparer.
    </p>
    <div class="flex gap-4">
      <div>
        <label class="libelle-champ" for="seuil-m">Machines au stock</label>
        <input id="seuil-m" type="number" min="0" class="champ max-w-28" bind:value={reglage.machines} />
      </div>
      <div>
        <label class="libelle-champ" for="seuil-c">Chargeurs au stock</label>
        <input id="seuil-c" type="number" min="0" class="champ max-w-28" bind:value={reglage.chargeurs} />
      </div>
    </div>
    {#snippet actions()}
      <Bouton onclick={() => (reglage = null)}>Annuler</Bouton>
      <Bouton variante="primary" onclick={enregistrerSeuils}>Enregistrer</Bouton>
    {/snippet}
  </Modale>
{/if}
