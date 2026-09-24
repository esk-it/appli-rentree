<script>
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import ChevronDown from "@lucide/svelte/icons/chevron-down";
  import Printer from "@lucide/svelte/icons/printer";
  import IdCard from "@lucide/svelte/icons/id-card";
  import Download from "@lucide/svelte/icons/download";
  import LayoutGrid from "@lucide/svelte/icons/layout-grid";
  import Rows3 from "@lucide/svelte/icons/rows-3";
  import Search from "@lucide/svelte/icons/search";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Avatar from "$lib/components/Avatar.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import { enregistrerFichierBase64, personnes as personnesApi } from "$lib/api.js";
  import { ecrire } from "$lib/memoire.svelte.js";
  import {
    comparerNaturel,
    csvDeClasse,
    etatDe,
    niveauDe,
    ordreNiveau,
    texteEnBase64,
  } from "$lib/referentiel.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Le Référentiel rangé comme l'établissement se pense : par classe.
   *
   * La liste répond à « où est cette personne » ; ici on répond à
   * « qui est dans cette classe, et est-ce qu'il ne lui manque rien ». Le
   * trombinoscope sert à reconnaître — à quarante pixels dans une liste, un
   * visage n'est qu'une tache — et les trois gestes de rentrée se font
   * depuis la classe : l'imprimer pour le professeur principal, faire ses
   * cartes, sortir sa liste.
   *
   * @typedef {Object} Props
   * @property {any[]} lignes  - les personnes de l'année, mouvement compris
   * @property {Record<number, any>} verdicts
   * @property {number|null} anneeId
   * @property {string} libelleAnnee
   * @property {string} classe  - bindable
   * @property {(id: number) => void} [onChoisir]
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let {
    lignes = [],
    verdicts = {},
    anneeId = null,
    libelleAnnee = "",
    classe = $bindable(""),
    onChoisir,
    onNaviguer,
  } = $props();

  const PERSONNEL = "__personnel";
  const libelle = (e) => String(e).replace(/^Error:\s*/, "");

  let filtreArbre = $state("");
  let vue = $state(/** @type {"trombinoscope"|"liste"} */ ("trombinoscope"));
  let ouverts = $state(/** @type {Set<string>} */ (new Set()));
  let impression = $state(false);

  /** Les présents : un parti n'est plus dans sa classe. */
  let presents = $derived(lignes.filter((p) => p.mouvement !== "sortant"));
  let eleves = $derived(presents.filter((p) => p.type === "eleve" && p.classe));
  let adultes = $derived(presents.filter((p) => p.type === "adulte"));

  /** Site → niveau → classe, avec les effectifs. */
  let arbre = $derived.by(() => {
    /** @type {Map<string, Map<string, Map<string, number>>>} */
    const sites = new Map();
    for (const p of eleves) {
      const site = p.site ?? "Sans site";
      const niveau = niveauDe(p.classe);
      if (!sites.has(site)) sites.set(site, new Map());
      const niveaux = sites.get(site);
      if (!niveaux.has(niveau)) niveaux.set(niveau, new Map());
      const classes = niveaux.get(niveau);
      classes.set(p.classe, (classes.get(p.classe) ?? 0) + 1);
    }
    const q = filtreArbre.trim().toLowerCase();
    return [...sites.entries()]
      .sort(([a], [b]) => Number(a === "Sans site") - Number(b === "Sans site") || a.localeCompare(b))
      .map(([site, niveaux]) => ({
        site,
        total: [...niveaux.values()].reduce((s, c) => s + [...c.values()].reduce((x, y) => x + y, 0), 0),
        niveaux: [...niveaux.entries()]
          .sort(([a], [b]) => ordreNiveau(a) - ordreNiveau(b))
          .map(([niveau, classes]) => ({
            niveau,
            total: [...classes.values()].reduce((x, y) => x + y, 0),
            classes: [...classes.entries()]
              .filter(([c]) => !q || c.toLowerCase().includes(q))
              .sort(([a], [b]) => comparerNaturel(a, b))
              .map(([c, n]) => ({ classe: c, n })),
          }))
          .filter((n) => n.classes.length),
      }))
      .filter((s) => s.niveaux.length);
  });

  // Une classe choisie ouvre sa branche ; aucune choisie, la première l'est.
  $effect(() => {
    if (!classe && arbre.length) classe = arbre[0].niveaux[0].classes[0].classe;
  });
  $effect(() => {
    if (!classe || classe === PERSONNEL) return;
    const p = eleves.find((x) => x.classe === classe);
    if (!p) return;
    const s = p.site ?? "Sans site";
    const n = `${s}/${niveauDe(classe)}`;
    if (!ouverts.has(s) || !ouverts.has(n)) ouverts = new Set([...ouverts, s, n]);
  });

  function basculer(cle) {
    const s = new Set(ouverts);
    if (s.has(cle)) s.delete(cle);
    else s.add(cle);
    ouverts = s;
  }

  let membres = $derived(
    (classe === PERSONNEL ? adultes : eleves.filter((p) => p.classe === classe))
      .slice()
      .sort((a, b) => (a.nom ?? "").localeCompare(b.nom ?? "", "fr") || (a.prenom ?? "").localeCompare(b.prenom ?? "", "fr")),
  );
  let site = $derived(membres[0]?.site ?? null);

  /** Les professeurs principaux, lus sur les fiches des adultes. */
  let profsPrincipaux = $derived(
    classe === PERSONNEL
      ? []
      : adultes.filter((a) => (a.classes_prof_principal ?? "").split(";").map((x) => x.trim()).includes(classe)),
  );

  let sante = $derived.by(() => {
    const r = { pret: 0, ecart: 0, inconnu: 0, aCreer: 0, sansIne: 0 };
    for (const p of membres) {
      r[etatDe(p, verdicts).etat] += 1;
      if (!p.email_est_constate) r.aCreer += 1;
      if (p.type === "eleve" && !p.ine) r.sansIne += 1;
    }
    return r;
  });

  async function imprimer() {
    impression = true;
    try {
      const r = await personnesApi.trombinoscope(classe, anneeId);
      const { annule } = await enregistrerFichierBase64(r.nom_fichier, r.pdf_base64, "application/pdf");
      if (!annule) {
        notify.succes(
          `Trombinoscope de ${classe} : ${r.nb_eleves} élèves` +
            (r.nb_sans_photo ? `, ${r.nb_sans_photo} sans photo (initiales à la place).` : "."),
        );
      }
    } catch (e) {
      notify.erreur(libelle(e), { duree: 12000 });
    } finally {
      impression = false;
    }
  }

  function cartes() {
    // L'écran des cartes retient sa sélection : on la lui prépare, et il
    // s'ouvre sur la classe, ses élèves cochés.
    ecrire("cartes.site", site ?? "");
    ecrire("cartes.classes", [classe]);
    ecrire("cartes.coches", membres.map((p) => p.id).filter((id) => id > 0));
    onNaviguer?.("cartes");
  }

  async function liste() {
    const nom = `Liste_${classe === PERSONNEL ? "Personnel" : classe}_${libelleAnnee || "annee"}.csv`;
    await enregistrerFichierBase64(nom, texteEnBase64(csvDeClasse(membres)), "text/csv");
  }
</script>

<div class="grid h-full min-h-0 grid-cols-[250px_minmax(0,1fr)]">
  <!-- L'arbre : le site, le niveau, la classe. -->
  <aside class="min-h-0 overflow-y-auto border-r border-stone-200 pr-5 dark:border-stone-800">
    <div class="relative">
      <Search class="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-stone-400" />
      <input
        type="search"
        class="champ !rounded-full !py-1.5 !pl-9"
        placeholder="Une classe"
        aria-label="Chercher une classe"
        bind:value={filtreArbre}
      />
    </div>
    <p class="libelle-champ mt-5 mb-1.5">Établissements</p>
    {#each arbre as s (s.site)}
      {@const ouvertS = ouverts.has(s.site) || !!filtreArbre}
      <button
        type="button"
        class="flex h-8 w-full items-center gap-1.5 rounded-lg px-2 text-left text-sm font-bold hover:bg-stone-100 dark:hover:bg-stone-800"
        onclick={() => basculer(s.site)}
      >
        {#if ouvertS}<ChevronDown class="h-3.5 w-3.5 text-stone-400" />{:else}<ChevronRight class="h-3.5 w-3.5 text-stone-400" />{/if}
        <span class="flex-1">{s.site}</span>
        <span class="text-xs font-medium tabular-nums text-stone-500">{s.total}</span>
      </button>
      {#if ouvertS}
        {#each s.niveaux as n (n.niveau)}
          {@const cleN = `${s.site}/${n.niveau}`}
          {@const ouvertN = ouverts.has(cleN) || !!filtreArbre}
          <button
            type="button"
            class="flex h-8 w-full items-center gap-1.5 rounded-lg pr-2 pl-6 text-left text-sm font-semibold text-stone-700 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800"
            onclick={() => basculer(cleN)}
          >
            {#if ouvertN}<ChevronDown class="h-3.5 w-3.5 text-stone-400" />{:else}<ChevronRight class="h-3.5 w-3.5 text-stone-400" />{/if}
            <span class="flex-1">{n.niveau}</span>
            <span class="text-xs font-medium tabular-nums text-stone-500">{n.total}</span>
          </button>
          {#if ouvertN}
            {#each n.classes as c (c.classe)}
              {@const choisie = c.classe === classe}
              <button
                type="button"
                class="flex h-8 w-full items-center rounded-lg pr-2 pl-12 text-left text-sm transition
                       {choisie
                  ? 'bg-emerald-100 font-bold text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-200'
                  : 'text-stone-700 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800'}"
                onclick={() => (classe = c.classe)}
              >
                <span class="flex-1 font-mono text-[13px]">{c.classe}</span>
                <span class="text-xs tabular-nums {choisie ? '' : 'text-stone-500'}">{c.n}</span>
              </button>
            {/each}
          {/if}
        {/each}
      {/if}
    {/each}
    {#if adultes.length}
      <button
        type="button"
        class="mt-1 flex h-8 w-full items-center gap-1.5 rounded-lg px-2 text-left text-sm font-bold transition
               {classe === PERSONNEL
          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-200'
          : 'hover:bg-stone-100 dark:hover:bg-stone-800'}"
        onclick={() => (classe = PERSONNEL)}
      >
        <Users2 class="h-3.5 w-3.5 text-stone-400" />
        <span class="flex-1">Personnel</span>
        <span class="text-xs font-medium tabular-nums text-stone-500">{adultes.length}</span>
      </button>
    {/if}
  </aside>

  <!-- La classe ouverte. -->
  <section class="flex min-h-0 min-w-0 flex-col pl-8">
    {#if !membres.length}
      <EtatVide
        icon={Users2}
        titre="Aucune classe à montrer"
        message="Choisis une classe dans l'arbre. S'il est vide, l'année choisie n'a encore aucun élève ingéré."
      />
    {:else}
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="min-w-0">
          <div class="flex items-center gap-3">
            <h2 class="titre-affiche text-4xl text-stone-900 dark:text-stone-100">
              {classe === PERSONNEL ? "Personnel" : classe}
            </h2>
            {#if classe !== PERSONNEL}
              <Pastille etat="reference" texte={niveauDe(classe)} />
            {/if}
          </div>
          <p class="mt-1.5 flex flex-wrap gap-x-2 text-sm text-stone-600 dark:text-stone-400">
            {#if site}<span>{site}</span><span>·</span>{/if}
            <span><b class="text-stone-900 dark:text-stone-100">{membres.length}</b> {classe === PERSONNEL ? "adultes" : "élèves"}</span>
            {#if libelleAnnee}<span>·</span><span>{libelleAnnee}</span>{/if}
            {#if profsPrincipaux.length}
              <span>·</span>
              <span>Prof. principal : {profsPrincipaux.map((a) => `${a.prenom} ${a.nom}`).join(", ")}</span>
            {/if}
          </p>
        </div>
        <Segments
          bind:valeur={vue}
          taille="sm"
          options={[
            { id: "trombinoscope", label: "Trombinoscope", icon: LayoutGrid },
            { id: "liste", label: "Liste", icon: Rows3 },
          ]}
        />
      </div>

      <div class="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-y border-stone-200 py-3 text-sm dark:border-stone-800">
        <span class="flex items-center gap-2"><span class="h-2.5 w-2.5 rounded-full bg-vert-500"></span><b>{sante.pret}</b> cohérents</span>
        {#if sante.ecart}
          <span class="flex items-center gap-2"><span class="h-2.5 w-2.5 rounded-full bg-red-500"></span><b>{sante.ecart}</b> en écart</span>
        {/if}
        {#if sante.inconnu}
          <span class="flex items-center gap-2"><span class="h-2.5 w-2.5 rounded-full bg-stone-300 dark:bg-stone-600"></span><b>{sante.inconnu}</b> pas vérifiés</span>
        {/if}
        {#if sante.aCreer}
          <span class="flex items-center gap-2"><span class="h-2.5 w-2.5 rounded-full bg-amber-500"></span><b>{sante.aCreer}</b> adresses pas encore constatées</span>
        {/if}
        <span class="flex-1"></span>
        <div class="flex flex-wrap items-center gap-2">
          {#if classe !== PERSONNEL}
            <Bouton taille="sm" icon={Printer} occupe={impression} onclick={imprimer}>Imprimer le trombinoscope</Bouton>
            <Bouton taille="sm" icon={IdCard} onclick={cartes}>Cartes de la classe</Bouton>
          {/if}
          <Bouton taille="sm" variante="primary" icon={Download} onclick={liste}>
            {classe === PERSONNEL ? "Liste du personnel" : "Liste pour l'enseignant"}
          </Bouton>
        </div>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto pt-5 pb-4">
        {#if vue === "trombinoscope"}
          <div class="grid gap-x-5 gap-y-6 [grid-template-columns:repeat(auto-fill,minmax(112px,1fr))]">
            {#each membres as p (p.id)}
              {@const e = etatDe(p, verdicts)}
              <button
                type="button"
                class="group text-left"
                title="Ouvrir {p.prenom} {p.nom} dans la liste"
                onclick={() => onChoisir?.(p.id)}
              >
                <div class="overflow-hidden rounded-xl ring-emerald-500 transition group-hover:ring-2 group-focus-visible:ring-2">
                  <Avatar personneId={p.sans_compte ? null : p.id} nom={p.nom} prenom={p.prenom} forme="portrait" />
                </div>
                <p class="mt-2 truncate text-sm leading-tight">{p.prenom}</p>
                <p class="truncate text-sm leading-tight font-bold uppercase">{p.nom}</p>
                {#if e.etat === "ecart"}
                  <span class="mt-1 inline-block"><Pastille etat="ecart" texte={e.texte} /></span>
                {/if}
              </button>
            {/each}
          </div>
        {:else}
          {#each membres as p (p.id)}
            {@const e = etatDe(p, verdicts)}
            <button
              type="button"
              class="grid w-full grid-cols-[36px_minmax(0,1fr)_140px_minmax(0,1.2fr)_140px] items-center gap-4 border-b border-stone-200 py-2 text-left text-sm hover:bg-stone-50 dark:border-stone-800 dark:hover:bg-stone-900"
              onclick={() => onChoisir?.(p.id)}
            >
              <Avatar personneId={p.sans_compte ? null : p.id} nom={p.nom} prenom={p.prenom} taille={32} />
              <span class="truncate"><b class="uppercase">{p.nom}</b> {p.prenom}</span>
              <span class="truncate font-mono text-xs text-stone-600 dark:text-stone-400">{p.login_constate ?? p.login ?? "—"}</span>
              <span class="truncate font-mono text-xs text-stone-600 dark:text-stone-400">{p.email ?? "—"}</span>
              <Pastille etat={e.etat} texte={e.texte} />
            </button>
          {/each}
        {/if}
      </div>
    {/if}
  </section>
</div>
