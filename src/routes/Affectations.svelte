<script>
  import { onMount } from "svelte";
  import Search from "@lucide/svelte/icons/search";
  import Laptop from "@lucide/svelte/icons/laptop";
  import Plus from "@lucide/svelte/icons/plus";
  import Check from "@lucide/svelte/icons/check";
  import X from "@lucide/svelte/icons/x";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import { parc, personnes as personnesApi } from "$lib/api.js";
  import { TEINTES } from "$lib/familles.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Quel prof a quel Chromebook.
   *
   * ## La liste part des personnes, pas des machines
   *
   * Un inventaire de machines répond à « où est le CB-0210 ». La question
   * posée en salle des profs est l'inverse : « qui n'a rien ». Elle ne se
   * lit que si la liste part des adultes du référentiel — une machine
   * manquante ne se voit pas dans une liste de machines.
   *
   * ## Le porteur est un texte libre, et ce sont des adresses mail
   *
   * `attribue_a` est une chaîne. Sur le parc réel, elle contient
   * l'**adresse mail** du prof — `eric.senabre@lekreisker.fr` — parce que
   * c'est ce que la console Google donnait au moment de l'import. Un nom y
   * aurait aussi bien tenu, et rien n'empêche qu'un jour on y écrive
   * « Mme Martin ».
   *
   * Le rapprochement accepte donc les deux : l'adresse de la personne, ou
   * son « NOM Prénom ». Et pour que ce qu'on saisit demain tombe juste, le
   * champ **propose** les adultes du référentiel — c'est l'entrée qu'on
   * fiabilise, pas la comparaison qu'on assouplit indéfiniment.
   *
   * Les machines dont le porteur ne correspond à personne ne disparaissent
   * pas pour autant : elles sont listées à part. Une machine attribuée à un
   * nom inconnu est précisément ce qu'on veut voir.
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  const libelleErreur = (e) => String(e).replace(/^Error:\s*/, "");

  let machines = $state(/** @type {any[]} */ ([]));
  let adultes = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let erreur = $state("");
  let occupe = $state("");

  let recherche = $state("");
  let vue = $state(lire("affectations.vue", "tous"));
  $effect(() => ecrire("affectations.vue", vue));

  /** Le formulaire du haut : une machine, et à qui on la confie. */
  let nouvelle = $state(/** @type {null | {serie: string, porteur: string}} */ (null));

  /** La saisie dans une ligne : à ce prof, quelle machine. */
  let enLigne = $state(/** @type {null | {id: number, nom: string, serie: string}} */ (null));

  onMount(charger);

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      const [p, a] = await Promise.all([
        parc.machines(),
        personnesApi.lister({ type: "adulte" }),
      ]);
      machines = p.machines ?? [];
      adultes = a ?? [];
    } catch (e) {
      erreur = libelleErreur(e);
    } finally {
      chargement = false;
    }
  }

  const nomDe = (p) => `${p.nom ?? ""} ${p.prenom ?? ""}`.trim();
  const plier = (s) => String(s ?? "").trim().toLowerCase();

  /** Les écritures sous lesquelles une personne peut être désignée. */
  const clesDe = (p) => [plier(p.email), plier(nomDe(p))].filter(Boolean);

  /** Série(s) portée(s) par chaque écriture rencontrée. */
  let parPorteur = $derived.by(() => {
    const par = new Map();
    for (const m of machines) {
      if (!m.attribue_a) continue;
      const cle = plier(m.attribue_a);
      par.set(cle, [...(par.get(cle) ?? []), m]);
    }
    return par;
  });

  /** Ce qu'une personne porte, quelle que soit l'écriture employée. */
  function machinesDe(p) {
    const vues = new Map();
    for (const cle of clesDe(p)) {
      for (const m of parPorteur.get(cle) ?? []) vues.set(m.serie, m);
    }
    return [...vues.values()];
  }

  let lignes = $derived.by(() => {
    const q = plier(recherche);
    return adultes
      .map((p) => ({ personne: p, nom: nomDe(p), machines: machinesDe(p) }))
      .filter((l) => {
        if (vue === "affectes" && !l.machines.length) return false;
        if (vue === "sans" && l.machines.length) return false;
        if (q) {
          const foin = `${l.nom} ${l.personne.email ?? ""} ${l.machines
            .map((m) => m.serie)
            .join(" ")}`.toLowerCase();
          if (!foin.includes(q)) return false;
        }
        return true;
      })
      .sort((a, b) => a.nom.localeCompare(b.nom));
  });

  let disponibles = $derived(
    machines.filter((m) => m.etat === "en_stock").sort((a, b) => a.serie.localeCompare(b.serie)),
  );

  /** Les machines confiées à quelqu'un que le référentiel ne connaît pas. */
  let porteursInconnus = $derived.by(() => {
    const connus = new Set(adultes.flatMap(clesDe));
    return machines.filter((m) => m.attribue_a && !connus.has(plier(m.attribue_a)));
  });

  let nbSans = $derived(adultes.filter((p) => !machinesDe(p).length).length);

  async function affecter(serie, porteur) {
    occupe = serie;
    try {
      await parc.affecter(serie, { attribueA: porteur || null });
      await charger();
      notify.succes(
        porteur ? `${serie} confié à ${porteur}.` : `${serie} repris, retour au stock.`,
      );
      nouvelle = null;
      enLigne = null;
    } catch (e) {
      notify.erreur(libelleErreur(e), { duree: 10000 });
    } finally {
      occupe = "";
    }
  }
</script>

<section class="space-y-6">
  <EnTetePage
    icon={Laptop}
    titre="Affectations"
    description="Quel prof a quel Chromebook. La liste part des adultes du référentiel : c'est la seule façon de voir qui n'a rien."
  >
    {#snippet actions()}
      <Bouton
        variante="primary"
        icon={Plus}
        onclick={() => (nouvelle = { serie: "", porteur: "" })}
      >
        Affecter un Chromebook
      </Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  <!-- Saisie libre : une machine neuve n'existe nulle part avant qu'on la
       confie, et exiger de la créer d'abord ferait saisir deux fois. -->
  {#if nouvelle}
    <div class="card flex flex-wrap items-end gap-3 p-4">
      <div class="min-w-48 flex-1">
        <label class="libelle-champ" for="aff-serie">Numéro de série</label>
        <input
          id="aff-serie"
          class="champ mt-1 font-mono"
          placeholder="5CD1234ABC"
          bind:value={nouvelle.serie}
        />
      </div>
      <div class="min-w-56 flex-1">
        <label class="libelle-champ" for="aff-porteur">À qui</label>
        <input
          id="aff-porteur"
          class="champ mt-1"
          list="adultes-connus"
          placeholder="Adresse mail ou nom…"
          bind:value={nouvelle.porteur}
        />
      </div>
      <Bouton
        variante="primary"
        icon={Check}
        disabled={!nouvelle.serie.trim()}
        occupe={occupe === nouvelle.serie}
        onclick={() => affecter(nouvelle.serie.trim(), nouvelle.porteur.trim())}
      >
        Confier
      </Bouton>
      <Bouton icon={X} onclick={() => (nouvelle = null)}>Annuler</Bouton>
    </div>
  {/if}

  <!-- Les deux listes qui guident la saisie : les noms connus d'un côté,
       les machines libres de l'autre. Une frappe libre les contourne, et
       c'est voulu : une machine neuve n'est encore dans aucune liste. -->
  <datalist id="adultes-connus">
    {#each adultes as p (p.id)}
      <option value={p.email ?? nomDe(p)}>{nomDe(p)}</option>
    {/each}
  </datalist>
  <datalist id="series-libres">
    {#each disponibles as m (m.serie)}<option value={m.serie}></option>{/each}
  </datalist>

  {#if chargement}
    <Squelette variante="ligne-tableau" nb={6} colonnes={5} />
  {:else}
    <div class="grid gap-12 lg:grid-cols-[minmax(0,1fr)_280px]">
      <div>
        <!-- Filtres -->
        <div class="flex flex-wrap items-center gap-4 border-b border-stone-200 pb-4 dark:border-stone-800">
          <div class="relative min-w-56 flex-1 sm:max-w-xs">
            <Search class="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-stone-400" />
            <input
              class="champ !rounded-full !py-1.5 pl-9 text-sm"
              placeholder="Prof ou Chromebook"
              bind:value={recherche}
            />
          </div>
          <Segments
            bind:valeur={vue}
            taille="sm"
            options={[
              { id: "tous", label: "Tous", badge: adultes.length },
              { id: "affectes", label: "Affectés", badge: adultes.length - nbSans },
              { id: "sans", label: "Sans Chromebook", badge: nbSans },
            ]}
          />
        </div>

        <!-- Le tableau -->
        <div class="mt-1 grid grid-cols-[minmax(0,1fr)_170px_150px_120px_110px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
          <span class="libelle-champ">Prof</span>
          <span class="libelle-champ">Chromebook</span>
          <span class="libelle-champ">Depuis</span>
          <span class="libelle-champ">État</span>
          <span></span>
        </div>

        <div class="max-h-[calc(100vh-24rem)] min-h-40 overflow-y-auto">
          {#each lignes as l (l.personne.id)}
            {@const m = l.machines[0]}
            {@const sans = !m}
            <div
              class="grid grid-cols-[minmax(0,1fr)_170px_150px_120px_110px] items-center gap-3 border-b border-stone-100 py-2.5 text-sm dark:border-stone-800/70 {sans
                ? 'bg-amber-50/70 dark:bg-amber-400/5'
                : ''}"
            >
              <span class="truncate font-semibold">{l.nom}</span>

              <span class="truncate font-mono text-[13px]">
                {#if m}{m.serie}{:else}<span class="text-stone-400">—</span>{/if}
                {#if l.machines.length > 1}
                  <span class="text-xs text-stone-500">+{l.machines.length - 1}</span>
                {/if}
              </span>

              <span class="text-[13px] text-stone-600 dark:text-stone-400">
                {m?.attribue_le ?? (sans ? "Sans Chromebook" : "—")}
              </span>

              <span>
                {#if !m}
                  <Pastille etat="attente" texte="À affecter" />
                {:else if m.etat === "hs"}
                  <Pastille etat="ecart" texte="HS" />
                {:else}
                  <Pastille etat="pret" texte="Affecté" />
                {/if}
              </span>

              {#if enLigne?.id === l.personne.id}
                <span class="flex items-center gap-1">
                  <input
                    class="champ !px-2 !py-1 font-mono text-xs"
                    list="series-libres"
                    placeholder="série"
                    bind:value={enLigne.serie}
                    onkeydown={(e) =>
                      e.key === "Enter" &&
                      affecter(enLigne.serie.trim(), l.personne.email ?? l.nom)}
                  />
                  <button
                    class="shrink-0 rounded-full p-1.5 text-white disabled:opacity-40"
                    style="background: {TEINTES.materiel};"
                    aria-label="Confirmer l'affectation"
                    disabled={!enLigne.serie.trim()}
                    onclick={() => affecter(enLigne.serie.trim(), l.personne.email ?? l.nom)}
                  >
                    <Check class="h-3.5 w-3.5" />
                  </button>
                </span>
              {:else}
                <button
                  class="justify-self-start text-sm font-semibold hover:underline"
                  style="color: {TEINTES.materiel};"
                  onclick={() => (enLigne = { id: l.personne.id, nom: l.nom, serie: "" })}
                >
                  {m ? "Changer" : "Affecter"}
                </button>
              {/if}
            </div>
          {/each}

          {#if !lignes.length}
            <p class="py-8 text-center text-sm text-stone-500 dark:text-stone-400">
              Aucun adulte ne correspond à ces filtres.
            </p>
          {/if}
        </div>

        <!-- Les porteurs que le référentiel ne connaît pas : une machine
             attribuée à un nom inconnu est justement ce qu'on veut voir. -->
        {#if porteursInconnus.length}
          <div class="mt-5 rounded-xl bg-amber-50 p-4 dark:bg-amber-400/10">
            <p class="text-sm font-semibold text-amber-900 dark:text-amber-200">
              {porteursInconnus.length} machine{porteursInconnus.length > 1 ? "s" : ""}
              confiée{porteursInconnus.length > 1 ? "s" : ""} à un nom que le référentiel ne connaît pas
            </p>
            <p class="mt-1 text-[13px] text-amber-900/80 dark:text-amber-200/80">
              Le porteur est un texte libre. Réaffecte depuis la liste pour que
              le nom tombe juste — ces machines n'apparaissent dans aucune ligne
              ci-dessus.
            </p>
            <div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-amber-900 dark:text-amber-200">
              {#each porteursInconnus as m (m.serie)}
                <span>{m.serie} → {m.attribue_a}</span>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      <!-- Les machines libres, à portée de clic. -->
      <aside>
        <p class="libelle-champ">Disponibles · {disponibles.length}</p>
        <div class="mt-2.5 border-t border-stone-200 dark:border-stone-800">
          {#each disponibles.slice(0, 20) as m (m.serie)}
            <div class="flex items-center justify-between gap-2 border-b border-stone-100 py-3 dark:border-stone-800/70">
              <span class="truncate font-mono text-[13px] font-semibold">{m.serie}</span>
              <button
                class="shrink-0 text-sm font-semibold hover:underline"
                style="color: {TEINTES.materiel};"
                onclick={() => (nouvelle = { serie: m.serie, porteur: "" })}
              >
                Affecter →
              </button>
            </div>
          {/each}
          {#if !disponibles.length}
            <p class="py-4 text-[13px] text-stone-500 dark:text-stone-400">
              Aucune machine au stock. Elles y reviennent quand on les reprend.
            </p>
          {/if}
          {#if disponibles.length > 20}
            <p class="py-3 text-[13px] text-stone-500 dark:text-stone-400">
              … {disponibles.length - 20} autres
            </p>
          {/if}
        </div>

        <button
          class="mt-5 flex items-center gap-2 text-sm font-semibold hover:underline"
          style="color: {TEINTES.materiel};"
          onclick={() => onNaviguer?.("chromebooks")}
        >
          <Laptop class="h-4 w-4" /> Tout le parc
        </button>
      </aside>
    </div>
  {/if}
</section>
