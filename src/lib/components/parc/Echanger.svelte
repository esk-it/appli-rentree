<script>
  import ArrowLeftRight from "@lucide/svelte/icons/arrow-left-right";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import CloudAlert from "@lucide/svelte/icons/cloud-alert";
  import Bouton from "$lib/components/Bouton.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import ChoixPersonne from "./ChoixPersonne.svelte";
  import { parc } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { enUneLigne, finMaj, LIBELLES_ORGANE, messageErreur, ouEst } from "$lib/parc.js";

  /**
   * Échanger, remettre ou reprendre une machine — un seul formulaire.
   *
   * ## La nouvelle prend la place de l'ancienne
   *
   * Remplacer la machine d'un prof et la n°8 d'un chariot sont le même
   * geste : la machine du stock reçoit l'étiquette (et l'emplacement, et
   * l'unité Google) de celle qui part, et celle qui part reprend
   * l'étiquette de stock libérée — ou part à l'atelier.
   *
   * ## Seul le stock fournit
   *
   * La machine qui arrive se choisit dans une liste, et la liste ne
   * contient que le stock. C'est ce qui tient l'inventaire juste : une
   * machine remise sort du stock au moment où on la remet.
   *
   * @typedef {Object} Props
   * @property {any[]} postes
   * @property {any[]} personnes
   * @property {any} vocabulaire
   * @property {any[]} chargeurs - accessoires au stock, type chargeur
   * @property {{ancienne?: string, nouvelle?: string, porteur?: string} | null} [depart]
   * @property {(r: any) => void} onFait
   */
  /** @type {Props} */
  let { postes = [], personnes = [], vocabulaire, chargeurs = [], depart = null, onFait } = $props();

  let mode = $state("personne");
  let porteur = $state("");
  let rechercheMachine = $state("");
  let ancienne = $state("");
  let action = $state("remplacer");
  let nouvelle = $state("");
  let raison = $state("panne");
  let precision = $state("");
  let devenir = $state("stock");
  let organes = $state(/** @type {string[]} */ ([]));
  let etiquetteAncienne = $state("");
  let etiquetteTouchee = $state(false);
  let chargeur = $state("");
  let ecrireGoogle = $state(true);
  let envoi = $state(false);
  let resultat = $state(/** @type {any} */ (null));

  // Arriver depuis la fiche d'une machine : le formulaire se pré-remplit.
  let departApplique = $state(/** @type {any} */ (null));
  $effect(() => {
    if (!depart || depart === departApplique) return;
    departApplique = depart;
    resultat = null;
    if (depart.nouvelle) {
      mode = "personne";
      nouvelle = depart.nouvelle;
      ancienne = "";
      porteur = "";
    } else if (depart.ancienne) {
      const p = postes.find((x) => x.serie === depart.ancienne);
      if (p?.porteur) {
        mode = "personne";
        porteur = p.porteur;
      } else {
        mode = "machine";
        rechercheMachine = p?.etiquette || depart.ancienne;
      }
      ancienne = depart.ancienne;
      action = "remplacer";
    }
  });

  const parSerie = $derived(new Map(postes.map((p) => [p.serie, p])));
  let pa = $derived(ancienne ? parSerie.get(ancienne) : null);
  let pn = $derived(nouvelle ? parSerie.get(nouvelle) : null);

  /** Les machines que tient la personne choisie. */
  let siennes = $derived(
    porteur ? postes.filter((p) => p.porteur === porteur.toLowerCase() && p.etat === "en_service") : [],
  );
  $effect(() => {
    if (mode !== "personne") return;
    // La personne change : on propose sa machine si elle n'en a qu'une.
    if (ancienne && !siennes.some((p) => p.serie === ancienne)) ancienne = "";
    if (!ancienne && siennes.length === 1 && !depart?.nouvelle) ancienne = siennes[0].serie;
  });

  let machinesTrouvees = $derived.by(() => {
    const q = rechercheMachine.trim().toLowerCase();
    if (q.length < 2) return [];
    return postes
      .filter((p) => p.etat === "en_service")
      .filter((p) =>
        [p.serie, p.etiquette, p.lieu, p.porteur_nom, p.tenue_par].some((c) => (c ?? "").toLowerCase().includes(q)),
      )
      .slice(0, 12);
  });

  /** Le stock, les machines aux mises à jour les plus lointaines d'abord. */
  let stock = $derived(
    postes
      .filter((p) => p.etat === "en_stock")
      .sort((a, b) => (b.fin_maj ?? "").localeCompare(a.fin_maj ?? "") || a.serie.localeCompare(b.serie)),
  );

  let remplace = $derived(!!ancienne && action === "remplacer");
  let reprendSeulement = $derived(!!ancienne && action === "reprendre");

  // L'étiquette que gardera l'ancienne : celle que la nouvelle libère.
  let etiquetteParDefaut = $derived.by(() => {
    if (remplace && pn?.etiquette && !pn.etiquette.includes("@")) return pn.etiquette;
    return { stock: "Stock", hs: "HS", reforme: "Réformé" }[devenir];
  });
  $effect(() => {
    if (!etiquetteTouchee) etiquetteAncienne = etiquetteParDefaut;
  });

  let raisonsProposees = $derived(Object.entries(vocabulaire?.raisons ?? {}));

  let pret = $derived.by(() => {
    if (!raison) return false;
    if (reprendSeulement) return true;
    if (!nouvelle) return false;
    return !!ancienne || !!porteur.trim();
  });

  function basculerOrgane(o) {
    organes = organes.includes(o) ? organes.filter((x) => x !== o) : [...organes, o];
  }

  async function valider() {
    envoi = true;
    try {
      const r = await parc.echanger({
        ancienne: ancienne || null,
        nouvelle: reprendSeulement ? null : nouvelle || null,
        porteur: mode === "personne" ? porteur.trim() || null : null,
        raison,
        precision: precision.trim() || null,
        devenir,
        organes: devenir === "hs" ? organes : [],
        etiquetteAncienne: ancienne ? etiquetteAncienne.trim() || null : null,
        chargeur: chargeur || null,
        ecrireGoogle,
      });
      resultat = r;
      notify.succes(r.message, { duree: 8000 });
      onFait(r);
      // Le formulaire se vide : l'échange suivant ne doit rien hériter.
      ancienne = "";
      nouvelle = "";
      porteur = "";
      rechercheMachine = "";
      precision = "";
      organes = [];
      chargeur = "";
      etiquetteTouchee = false;
    } catch (e) {
      notify.erreur(messageErreur(e), { duree: 12000 });
    } finally {
      envoi = false;
    }
  }
</script>

<div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
  <div class="space-y-6">
    <!-- 1. De qui, ou de quoi, part-on -->
    <section class="space-y-3">
      <h3 class="titre-section">Pour qui ?</h3>
      <Segments
        taille="sm"
        bind:valeur={mode}
        options={[
          { id: "personne", label: "Un membre du personnel" },
          { id: "machine", label: "Une machine (chariot, salle…)" },
        ]}
        onChange={() => {
          ancienne = "";
          porteur = "";
          rechercheMachine = "";
        }}
      />

      {#if mode === "personne"}
        <div class="max-w-md">
          <label class="libelle-champ" for="ech-porteur">La personne</label>
          <ChoixPersonne id="ech-porteur" {personnes} bind:valeur={porteur} />
        </div>
        {#if porteur}
          <div class="space-y-1.5">
            <p class="libelle-champ">Sa machine aujourd'hui</p>
            {#each siennes as p (p.serie)}
              <label class="flex items-center gap-2 text-sm">
                <input type="radio" class="accent-emerald-600" bind:group={ancienne} value={p.serie} />
                <span class="font-medium">{p.etiquette || p.serie}</span>
                <span class="font-mono text-xs text-stone-500">{p.serie}</span>
                <span class="text-xs {finMaj(p.fin_maj).ton}">màj {finMaj(p.fin_maj).texte}</span>
              </label>
            {/each}
            <label class="flex items-center gap-2 text-sm">
              <input type="radio" class="accent-emerald-600" bind:group={ancienne} value="" />
              <span>{siennes.length ? "Aucune de celles-ci" : "Elle n'en a pas"} — lui en confier une</span>
            </label>
          </div>
        {/if}
      {:else}
        <div class="max-w-md">
          <label class="libelle-champ" for="ech-machine">La machine</label>
          <input
            id="ech-machine"
            class="champ"
            placeholder="K-B5-13-08, numéro de série, salle…"
            bind:value={rechercheMachine}
          />
        </div>
        {#if machinesTrouvees.length}
          <div class="space-y-1">
            {#each machinesTrouvees as p (p.serie)}
              <label class="flex items-center gap-2 text-sm">
                <input type="radio" class="accent-emerald-600" bind:group={ancienne} value={p.serie} />
                <span class="font-medium">{p.etiquette || p.serie}</span>
                <span class="text-xs text-stone-500">{ouEst(p)} · <span class="font-mono">{p.serie}</span></span>
              </label>
            {/each}
          </div>
        {/if}
      {/if}
    </section>

    <!-- 2. Ce qui se passe -->
    {#if ancienne}
      <section class="space-y-3">
        <h3 class="titre-section">Que fait-on de {pa?.etiquette || ancienne} ?</h3>
        <Segments
          taille="sm"
          bind:valeur={action}
          options={[
            { id: "remplacer", label: "La remplacer par une machine du stock" },
            { id: "reprendre", label: "La reprendre sans la remplacer" },
          ]}
        />
      </section>
    {/if}

    {#if !reprendSeulement}
      <section class="space-y-2">
        <h3 class="titre-section">La machine qui arrive, prise au stock</h3>
        {#if stock.length}
          <select class="champ max-w-xl" bind:value={nouvelle}>
            <option value="">Choisir dans le stock ({stock.length})…</option>
            {#each stock as p (p.serie)}
              <option value={p.serie}>{enUneLigne(p)} — màj {finMaj(p.fin_maj).texte}</option>
            {/each}
          </select>
          <p class="text-xs text-stone-500 dark:text-stone-400">
            Celles dont les mises à jour durent le plus longtemps sont en tête.
          </p>
        {:else}
          <p class="text-sm text-amber-800 dark:text-amber-300">
            Le stock est vide. Remets-y une machine depuis l'onglet « Le stock », ou reprends
            celle-ci sans la remplacer.
          </p>
        {/if}
      </section>
    {/if}

    <!-- 3. Pourquoi -->
    <section class="grid gap-3 sm:grid-cols-[16rem_minmax(0,1fr)]">
      <div>
        <label class="libelle-champ" for="ech-raison">Raison</label>
        <select id="ech-raison" class="champ" bind:value={raison}>
          {#each raisonsProposees as [code, libelle] (code)}
            <option value={code}>{libelle}</option>
          {/each}
        </select>
      </div>
      <div>
        <label class="libelle-champ" for="ech-precision">Précision</label>
        <input
          id="ech-precision"
          class="champ"
          placeholder="ne charge plus, tombée en cours, remplaçant de Mme…"
          bind:value={precision}
        />
      </div>
    </section>

    <!-- 4. Ce que devient l'ancienne -->
    {#if ancienne}
      <section class="space-y-3">
        <h3 class="titre-section">Où va {pa?.etiquette || ancienne} ?</h3>
        <Segments
          taille="sm"
          bind:valeur={devenir}
          options={[
            { id: "stock", label: "Au stock, elle marche" },
            { id: "hs", label: "À l'atelier, elle est en panne" },
            { id: "reforme", label: "À la réforme" },
          ]}
        />
        {#if devenir === "hs"}
          <div>
            <p class="libelle-champ">Ce qui est mort</p>
            <div class="mt-1 flex flex-wrap gap-1.5">
              {#each vocabulaire?.organes ?? [] as o (o)}
                <button
                  type="button"
                  class="rounded-full border px-2.5 py-1 text-xs transition {organes.includes(o)
                    ? 'border-red-400 bg-red-50 font-medium text-red-800 dark:bg-red-900/40 dark:text-red-300'
                    : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
                  onclick={() => basculerOrgane(o)}
                >
                  {LIBELLES_ORGANE[o] ?? o}
                </button>
              {/each}
            </div>
            <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
              C'est ce qui permet à l'atelier de dire si on peut en refaire une avec les autres.
            </p>
          </div>
        {/if}
        <div class="max-w-sm">
          <label class="libelle-champ" for="ech-etiquette">Son étiquette Google</label>
          <input
            id="ech-etiquette"
            class="champ"
            bind:value={etiquetteAncienne}
            oninput={() => (etiquetteTouchee = true)}
          />
        </div>
      </section>
    {/if}

    <!-- 5. Un chargeur avec -->
    {#if !reprendSeulement}
      <section class="max-w-md">
        <label class="libelle-champ" for="ech-chargeur">Donner aussi un chargeur de rechange</label>
        <select id="ech-chargeur" class="champ" bind:value={chargeur}>
          <option value="">Non</option>
          {#each chargeurs as c (c.serie)}
            <option value={c.serie}>{c.serie}{c.note ? ` — ${c.note}` : ""}</option>
          {/each}
        </select>
        {#if !chargeurs.length}
          <p class="mt-1 text-xs text-stone-500">Aucun chargeur au stock.</p>
        {/if}
      </section>
    {/if}
  </div>

  <!-- Le résumé : avant → après, puis le geste. -->
  <aside class="space-y-3 lg:sticky lg:top-4 lg:self-start">
    <div class="card space-y-3 p-4 text-sm">
      <p class="libelle-champ">Ce qui va se passer</p>
      {#if remplace && pn}
        <p>
          <span class="font-medium">{pn.etiquette || pn.serie}</span>
          <ArrowRight class="inline h-3.5 w-3.5" />
          prend la place de <span class="font-medium">{pa?.etiquette || ancienne}</span>
          {#if pa}<span class="text-stone-500">({ouEst(pa)})</span>{/if}
        </p>
      {:else if !ancienne && pn && porteur}
        <p>
          <span class="font-medium">{pn.etiquette || pn.serie}</span>
          <ArrowRight class="inline h-3.5 w-3.5" />
          {personnes.find((x) => x.adresse === porteur)?.prenom ?? ""}
          {personnes.find((x) => x.adresse === porteur)?.nom ?? porteur}
        </p>
      {/if}
      {#if ancienne}
        <p>
          <span class="font-medium">{pa?.etiquette || ancienne}</span>
          <ArrowRight class="inline h-3.5 w-3.5" />
          {{ stock: "au stock", hs: "à l'atelier", reforme: "à la réforme" }[devenir]},
          étiquette « {etiquetteAncienne || "—"} »
        </p>
      {/if}
      {#if chargeur}<p>Chargeur {chargeur} donné.</p>{/if}
      {#if !pret}
        <p class="text-stone-500">
          {#if !ancienne && !porteur}Choisis une personne ou une machine.
          {:else if !reprendSeulement && !nouvelle}Choisis la machine du stock.
          {/if}
        </p>
      {/if}
      <label class="flex items-start gap-2 text-xs text-stone-600 dark:text-stone-300">
        <input type="checkbox" class="mt-0.5 accent-emerald-600" bind:checked={ecrireGoogle} />
        <span>
          Écrire les étiquettes dans Google tout de suite
          <span class="block text-stone-500">Sinon, elles attendront dans « À reporter ».</span>
        </span>
      </label>
      <Bouton variante="primary" icon={ArrowLeftRight} occupe={envoi} disabled={!pret} onclick={valider}>
        {remplace ? "Échanger" : reprendSeulement ? "Reprendre" : "Confier"}
      </Bouton>
    </div>

    {#if resultat}
      <div class="card space-y-1.5 p-4 text-sm">
        <p class="flex items-center gap-1.5 font-semibold text-emerald-700 dark:text-emerald-400">
          <CheckCircle2 class="h-4 w-4" /> {resultat.message}
        </p>
        {#each resultat.google as g (g.serie)}
          <p class="text-xs {g.ok ? 'text-stone-600 dark:text-stone-300' : 'text-amber-800 dark:text-amber-300'}">
            {#if !g.ok}<CloudAlert class="inline h-3.5 w-3.5" />{/if}
            <span class="font-mono">{g.serie}</span> — Google {g.ok ? "" : "n'a pas suivi : "}{g.message}
          </p>
        {/each}
      </div>
    {/if}
  </aside>
</div>
