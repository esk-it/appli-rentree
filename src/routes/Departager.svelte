<script>
  import { onMount } from "svelte";
  import AtSign from "@lucide/svelte/icons/at-sign";
  import Check from "@lucide/svelte/icons/check";
  import GitMerge from "@lucide/svelte/icons/git-merge";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Modale from "$lib/components/Modale.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import Progression from "$lib/components/Progression.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import BarreAction from "$lib/components/BarreAction.svelte";
  import { personnes } from "$lib/api.js";
  import { TEINTES } from "$lib/familles.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Départager les adresses que plusieurs fiches visent.
   *
   * ## Pourquoi un écran, et pas un bouton
   *
   * L'accueil comptait « 29 adresses visées par plusieurs personnes » et
   * renvoyait au Référentiel — c'est-à-dire à deux mille cinq cents lignes
   * parmi lesquelles retrouver les cinquante-huit concernées. Le constat
   * était juste, le geste manquait.
   *
   * ## Deux fiches ne font pas toujours deux personnes
   *
   * L'écran n'offrait d'abord qu'une issue : une adresse suffixée pour la
   * seconde. Or les vingt-neuf adresses de septembre 2026 étaient toutes
   * **une seule personne inscrite deux fois** — vingt-huit élèves passés
   * de NDE à NDK ou SU, que la seconde base Charlemagne a renumérotés, et
   * une réinscription. Aaron SAILLOUR, en 4J à NDE puis en 3e prépa-métiers
   * à NDK, se voyait proposer `aaron.saillour2@` : un second compte pour un
   * élève qui a déjà le sien.
   *
   * Quand tout l'indique — même INE, ou même nom et même date de
   * naissance, ou même nom et une seule des deux fiches inscrite cette
   * année — la réunion est donc proposée en premier. L'autre issue reste à
   * un clic : c'est à toi de dire que ce sont deux personnes. Deux INE ou
   * deux dates différentes le disent à ta place.
   *
   * ## Les doublons qui ne se disputent rien
   *
   * Un élève passé de NDE à NDK sous une adresse neuve n'a pas d'adresse
   * disputée : ses deux fiches cohabitaient sans bruit. L'INE et la date de
   * naissance les retrouvent, et ils ont leur section, sous les adresses.
   *
   * ## Ce que le programme refuse de faire seul
   *
   * Les adresses existantes portent tantôt un suffixe `1`, tantôt `2`, sans
   * règle déductible : le second Hugo GUILLOU s'est vu attribuer
   * `hugo.guillou1@` par calcul, puis créer dans Google sous
   * `hugo.guillou2@`. Le programme **propose** donc un suffixe et n'écrit
   * rien tant qu'on n'a pas validé.
   *
   * ## Qui garde l'adresse nue
   *
   * Celui qui **détient déjà le compte** : la lui retirer casserait une
   * adresse en service. Quand plusieurs la détiennent, personne ne peut
   * être présumé la garder, et la saisie s'ouvre sur toutes.
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  const libelleErreur = (e) => String(e).replace(/^Error:\s*/, "");

  let groupes = $state(/** @type {any[]} */ ([]));
  /** Les personnes en deux fiches, prouvées sans adresse disputée. */
  let doublons = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let erreur = $state("");
  /** La ligne ou la paire en cours : un id de personne, ou une adresse. */
  let enCours = $state(/** @type {number|string|null} */ (null));

  /** Ce qui est saisi, par personne, avant validation. */
  let saisies = $state(/** @type {Record<number, string>} */ ({}));

  /** Les paires que tu as déclarées « deux personnes », par adresse. */
  let distinctes = $state(/** @type {Record<string, boolean>} */ ({}));

  /** Ce qui a été tranché depuis l'ouverture de l'écran. */
  let faits = $state(/** @type {{ qui: string, texte: string, notes: string[] }[]} */ ([]));

  /** L'aperçu d'une réunion que rien n'a suggérée, avant confirmation. */
  let apercu = $state(/** @type {any} */ (null));
  let demandeTout = $state(false);

  onMount(charger);

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      [groupes, doublons] = await Promise.all([
        personnes.collisions(),
        personnes.doublons(),
      ]);
      // La suggestion pré-remplit le champ : on la relit, on la corrige si
      // besoin, on valide. Un champ vide obligerait à retaper une adresse
      // que le programme sait déjà écrire.
      const prets = /** @type {Record<number, string>} */ ({});
      for (const g of groupes) {
        for (const v of g.visants) {
          if (v.a_trancher)
            prets[v.personne_id] = saisies[v.personne_id] ?? v.adresse_proposee;
        }
      }
      saisies = prets;
    } catch (e) {
      erreur = libelleErreur(e);
    } finally {
      chargement = false;
    }
  }

  /** La paire se présente comme une réunion : suggérée, et pas récusée. */
  const enFusion = (g) => g.meme_personne_probable && !distinctes[g.adresse];

  let aReunir = $derived(groupes.filter(enFusion));

  /** Tout ce qu'un seul geste peut réunir : adresses et doublons prouvés. */
  let lot = $derived([...aReunir, ...doublons]);

  /** Une paire se désigne par l'adresse qu'elle dispute, ou par sa clé. */
  const cleDeGroupe = (g) => g.adresse ?? g.cle;

  /** « 12/03/2012 », depuis « 2012-03-12 ». */
  const jour = (iso) => (iso ? iso.split("-").reverse().join("/") : "");
  let aDepartager = $derived(
    groupes
      .filter((g) => !enFusion(g))
      .flatMap((g) => g.visants.filter((v) => v.a_trancher)),
  );
  let nbDoubles = $derived(
    groupes.filter((g) => g.plusieurs_comptes && !enFusion(g)).length,
  );

  /** « 3_PM à NDK en 2026-2027 · naissance 12/03/2012 » */
  function parcours(v) {
    return [
      ...(v.annees ?? [])
        .slice(0, 2)
        .map(
          (a) =>
            `${a.classe ?? "sans classe"}${a.site ? ` à ${a.site}` : ""} en ${a.annee}`,
        ),
      ...(v.date_naissance ? [`naissance ${jour(v.date_naissance)}`] : []),
    ].join(" · ");
  }

  const cleDe = (g, id) => g.visants.find((v) => v.personne_id === id)?.cle_pivot;

  /** Ce qu'une réunion a écarté ou abandonné, et qui mérite d'être lu. */
  const notesDe = (r) => [...r.annees_ecartees, ...r.abandonnes, ...r.avertissements];

  function retenir(r) {
    faits = [
      ...faits,
      {
        qui: `${r.garde.prenom} ${r.garde.nom}`,
        texte: `${r.absorbee.cle_pivot} rejoint ${r.garde.cle_pivot}`,
        notes: notesDe(r),
      },
    ];
  }

  async function reunir(g) {
    enCours = cleDeGroupe(g);
    try {
      const r = await personnes.fusionner(
        g.visants.map((v) => v.personne_id),
        "reel",
      );
      retenir(r);
      const notes = notesDe(r);
      notify.succes(
        `${r.garde.prenom} ${r.garde.nom} : ${r.absorbee.cle_pivot} rejoint ${r.garde.cle_pivot}.` +
          (notes.length ? ` ${notes.join(" ")}` : ""),
        notes.length ? { duree: 12000 } : undefined,
      );
      await charger();
    } catch (e) {
      notify.erreur(libelleErreur(e), { duree: 12000 });
    } finally {
      enCours = null;
    }
  }

  /** Une réunion que rien n'a suggérée : on regarde avant d'écrire. */
  async function examiner(g) {
    enCours = cleDeGroupe(g);
    try {
      apercu = {
        groupe: g,
        rapport: await personnes.fusionner(g.visants.map((v) => v.personne_id)),
      };
    } catch (e) {
      notify.erreur(libelleErreur(e), { duree: 12000 });
    } finally {
      enCours = null;
    }
  }

  async function confirmerApercu() {
    const g = apercu.groupe;
    apercu = null;
    await reunir(g);
  }

  /** Toutes les paires suggérées, en s'arrêtant sur la première qui résiste. */
  async function reunirTout() {
    demandeTout = false;
    let n = 0;
    for (const g of [...lot]) {
      enCours = cleDeGroupe(g);
      try {
        retenir(await personnes.fusionner(g.visants.map((v) => v.personne_id), "reel"));
        n++;
      } catch (e) {
        const qui = g.visants.find((v) => v.personne_id === g.garde_id) ?? g.visants[0];
        notify.erreur(
          `${qui.prenom} ${qui.nom} : ${libelleErreur(e)} — la suite n'a pas été réunie.`,
          { duree: 14000 },
        );
        break;
      }
    }
    enCours = null;
    if (n) notify.succes(`${n} paire${n > 1 ? "s" : ""} de fiches réunie${n > 1 ? "s" : ""}.`);
    await charger();
  }

  async function valider(visant) {
    const adresse = (saisies[visant.personne_id] ?? "").trim();
    if (!adresse) return;
    enCours = visant.personne_id;
    try {
      await personnes.definirEmail(visant.personne_id, adresse);
      faits = [
        ...faits,
        { qui: `${visant.prenom} ${visant.nom}`, texte: `prend ${adresse}`, notes: [] },
      ];
      notify.succes(`${visant.prenom} ${visant.nom} prend ${adresse}.`);
      await charger();
    } catch (e) {
      notify.erreur(libelleErreur(e), { duree: 12000 });
    } finally {
      enCours = null;
    }
  }

  /** Tout valider d'un coup, en s'arrêtant sur la première qui résiste. */
  async function validerTout() {
    for (const v of [...aDepartager]) {
      const adresse = (saisies[v.personne_id] ?? "").trim();
      if (!adresse) continue;
      enCours = v.personne_id;
      try {
        await personnes.definirEmail(v.personne_id, adresse);
        faits = [
          ...faits,
          { qui: `${v.prenom} ${v.nom}`, texte: `prend ${adresse}`, notes: [] },
        ];
      } catch (e) {
        notify.erreur(
          `${v.prenom} ${v.nom} : ${libelleErreur(e)} — la suite n'a pas été appliquée.`,
          { duree: 14000 },
        );
        enCours = null;
        await charger();
        return;
      }
    }
    enCours = null;
    notify.succes("Toutes les adresses saisies ont été enregistrées.");
    await charger();
  }

  let notables = $derived(faits.filter((f) => f.notes.length));
</script>

<section class="flex min-h-[calc(100vh-10rem)] flex-col space-y-6">
  <EnTetePage
    icon={AtSign}
    chemin={["Départager"]}
    titre={groupes.length
      ? `${groupes.length} adresse${groupes.length > 1 ? "s" : ""} mail visée${groupes.length > 1 ? "s" : ""} par plusieurs fiches`
      : doublons.length
        ? `${doublons.length} personne${doublons.length > 1 ? "s" : ""} en deux fiches`
        : "Adresses mail disputées"}
    description="Souvent, c'est une seule personne inscrite deux fois — un passage de NDE à NDK ou SU, une réinscription : on réunit ses fiches, et son compte reste le sien. Sinon, ce sont deux homonymes, et celui qui n'a pas de compte prend une adresse suffixée : prenom.nom2@…"
  >
    {#snippet actions()}
      <Bouton taille="sm" icon={RefreshCw} occupe={chargement} onclick={charger}>
        Relire
      </Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if faits.length}
    <div class="rounded-xl bg-stone-50 px-4 py-3 text-sm dark:bg-stone-900">
      <p class="text-stone-800 dark:text-stone-200">
        <b>{faits.length}</b> cas tranché{faits.length > 1 ? "s" : ""} depuis l'ouverture de l'écran.
        {#if !notables.length}Rien n'a été écarté.{/if}
      </p>
      {#if notables.length}
        <ul class="mt-2 space-y-1 text-xs text-stone-600 dark:text-stone-400">
          {#each notables as f}
            <li>
              <b class="text-stone-800 dark:text-stone-200">{f.qui}</b> ({f.texte}) —
              {f.notes.join(" ")}
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}

  {#if chargement && !groupes.length && !doublons.length}
    <Squelette variante="ligne-tableau" nb={6} colonnes={4} />
  {:else if !groupes.length && !doublons.length}
    <EtatVide
      icon={CheckCircle2}
      ton="succes"
      titre="Aucune adresse disputée"
      message="Chaque fiche vise une adresse qui n'appartient qu'à elle. L'export Google ne butera pas sur un doublon."
    />
  {:else}
    {#if lot.length}
      <div class="flex flex-wrap items-center gap-3 rounded-xl bg-emerald-50 px-4 py-3 text-sm dark:bg-emerald-500/10">
        <GitMerge class="h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-300" />
        <span class="min-w-0 flex-1 text-stone-800 dark:text-stone-200">
          <b>{lot.length} paire{lot.length > 1 ? "s" : ""}</b>
          {lot.length > 1 ? "ont" : "a"} tout d'une seule personne inscrite
          deux fois : même INE, même date de naissance, ou même nom et une
          seule des deux fiches inscrite cette année. Réunir garde la fiche
          la plus récente et y rattache l'ancienne — son année rejoint le
          parcours, son numéro reste reconnu. Aucune adresse à créer, rien ne
          change dans Google ni dans KoXo.
        </span>
      </div>
    {/if}

    {#if nbDoubles}
      <div class="flex flex-wrap items-center gap-3 rounded-xl bg-red-50 px-4 py-3 text-sm dark:bg-red-500/10">
        <span class="h-2.5 w-2.5 shrink-0 rounded-full bg-red-500"></span>
        <span class="text-stone-800 dark:text-stone-200">
          <b>{nbDoubles} adresse{nbDoubles > 1 ? "s" : ""}</b>
          {nbDoubles > 1 ? "sont détenues" : "est détenue"} par
          <b>plusieurs fiches à la fois</b> — deux comptes constatés sur la
          même adresse. Personne ne peut être présumé la garder : les deux
          lignes s'ouvrent, et c'est à toi de dire laquelle bouge.
        </span>
      </div>
    {/if}

    <div class="max-w-md">
      <Progression
        valeur={faits.length}
        total={faits.length + groupes.length + doublons.length}
        libelle="{groupes.length + doublons.length} cas reste{groupes.length + doublons.length > 1 ? 'nt' : ''} à trancher"
        teinte={TEINTES.annee}
      />
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto">
      {#if groupes.length}
      <div class="grid grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_140px_300px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
        <span class="libelle-champ">Adresse visée</span>
        <span class="libelle-champ">Fiche</span>
        <span class="libelle-champ">Compte</span>
        <span class="libelle-champ">Décision</span>
      </div>
      {/if}

      {#each groupes as g (g.adresse)}
        {@const fusion = enFusion(g)}
        <div class="border-b border-stone-200 py-2.5 dark:border-stone-800">
          {#each g.visants as v, i (v.personne_id)}
            <div class="grid grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_140px_300px] items-center gap-3 py-1.5 text-sm">
              <span class="truncate font-mono text-[13px]">
                {#if i === 0}{g.adresse}{/if}
              </span>

              <span class="min-w-0">
                <span class="block truncate">
                  <span class="font-mono text-xs text-stone-500 dark:text-stone-400">
                    {v.cle_pivot}
                  </span>
                  <strong class="ml-1.5 font-semibold">{v.nom}</strong>
                  <span class="text-stone-600 dark:text-stone-300">{v.prenom}</span>
                </span>
                {#if v.annees?.length}
                  <span class="block truncate text-xs text-stone-500 dark:text-stone-400">
                    {parcours(v)}
                  </span>
                {/if}
              </span>

              <span>
                {#if fusion}
                  <!-- Une seule personne : un seul compte, ou aucun. Ni
                       « à créer », ni « en double ». -->
                  <Pastille
                    etat="inconnu"
                    texte={v.a_un_compte ? "compte existant" : "sans compte"}
                  />
                {:else if v.a_un_compte && !v.a_trancher}
                  <Pastille etat="inconnu" texte="compte existant" />
                {:else if v.a_un_compte}
                  <Pastille etat="ecart" texte="compte en double" />
                {:else}
                  <Pastille etat="reference" texte="à créer" />
                {/if}
              </span>

              {#if fusion}
                {#if v.personne_id === g.garde_id}
                  <span class="text-xs font-semibold text-stone-800 dark:text-stone-200">
                    reste — {v.inscrit ? "inscrite cette année" : "la plus récente"}
                  </span>
                {:else}
                  <span class="text-xs text-stone-500 dark:text-stone-400">
                    rejoint {cleDe(g, g.garde_id)}
                  </span>
                {/if}
              {:else if !v.a_trancher}
                <!-- Celui qui détient le compte garde son adresse : la
                     déplacer casserait une adresse en service. -->
                <span class="text-stone-500 dark:text-stone-400">la garde</span>
              {:else}
                <span class="flex items-center gap-1.5">
                  <input
                    class="champ !py-1.5 font-mono text-[13px]"
                    aria-label="Adresse distincte pour {v.prenom} {v.nom}"
                    bind:value={saisies[v.personne_id]}
                    onkeydown={(e) => e.key === "Enter" && valider(v)}
                  />
                  <Bouton
                    taille="sm"
                    icon={Check}
                    occupe={enCours === v.personne_id}
                    disabled={!(saisies[v.personne_id] ?? "").trim()}
                    onclick={() => valider(v)}
                  >
                    Valider
                  </Bouton>
                </span>
              {/if}
            </div>
          {/each}

          {#if g.meme_personne_probable}
            <div class="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg px-3 py-2
                        {fusion ? 'bg-emerald-50/70 dark:bg-emerald-500/10' : 'bg-stone-50 dark:bg-stone-900'}">
              <GitMerge class="h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-300" />
              <p class="min-w-0 flex-1 text-xs text-stone-700 dark:text-stone-300">{g.motif}</p>
              {#if fusion}
                <button
                  class="text-xs font-semibold text-stone-500 underline-offset-2 hover:text-stone-800 hover:underline dark:text-stone-400 dark:hover:text-stone-200"
                  onclick={() => (distinctes[g.adresse] = true)}
                >
                  Ce sont deux personnes
                </button>
                <Bouton
                  taille="sm"
                  variante="primary"
                  icon={GitMerge}
                  occupe={enCours === g.adresse}
                  disabled={enCours !== null && enCours !== g.adresse}
                  onclick={() => reunir(g)}
                >
                  Réunir les fiches
                </Bouton>
              {:else}
                <button
                  class="text-xs font-semibold text-emerald-700 underline-offset-2 hover:underline dark:text-emerald-300"
                  onclick={() => (distinctes[g.adresse] = false)}
                >
                  Finalement, c'est la même personne
                </button>
              {/if}
            </div>
          {:else if g.contradiction}
            <!-- Deux INE, deux dates de naissance : deux personnes, et
                 l'export le dit. Proposer de les réunir serait inviter à
                 l'erreur que l'écran existe pour éviter. -->
            <p class="mt-1 text-right text-xs text-stone-500 dark:text-stone-400">
              {g.contradiction}
            </p>
          {:else if g.visants.length === 2}
            <div class="mt-1 flex justify-end">
              <button
                class="text-xs font-semibold text-stone-500 underline-offset-2 hover:text-stone-800 hover:underline disabled:opacity-50 dark:text-stone-400 dark:hover:text-stone-200"
                disabled={enCours !== null}
                onclick={() => examiner(g)}
              >
                {enCours === g.adresse ? "Lecture…" : "C'est la même personne ?"}
              </button>
            </div>
          {/if}
        </div>
      {/each}

      {#if doublons.length}
        <div class="{groupes.length ? 'mt-8' : ''} border-b border-stone-200 pb-2 dark:border-stone-800">
          <p class="libelle-champ">Même personne, deux fiches — sans adresse disputée</p>
          <p class="mt-1 max-w-3xl text-xs text-stone-500 dark:text-stone-400">
            Retrouvées par l'INE, ou par le nom et la date de naissance.
            Elles ne se disputent aucune adresse, mais le parcours est coupé
            en deux, et la personne compte parmi les sortants d'un site et
            les entrants de l'autre.
          </p>
        </div>
        {#each doublons as d (d.cle)}
          <div class="border-b border-stone-200 py-2.5 dark:border-stone-800">
            {#each d.visants as v, i (v.personne_id)}
              <div class="grid grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_140px_300px] items-center gap-3 py-1.5 text-sm">
                <span>
                  {#if i === 0}
                    <Pastille
                      etat="reference"
                      texte={d.preuve === "ine" ? "même INE" : "même naissance"}
                    />
                  {/if}
                </span>
                <span class="min-w-0">
                  <span class="block truncate">
                    <span class="font-mono text-xs text-stone-500 dark:text-stone-400">
                      {v.cle_pivot}
                    </span>
                    <strong class="ml-1.5 font-semibold">{v.nom}</strong>
                    <span class="text-stone-600 dark:text-stone-300">{v.prenom}</span>
                  </span>
                  <span class="block truncate text-xs text-stone-500 dark:text-stone-400">
                    {parcours(v)}
                  </span>
                </span>
                <span>
                  <Pastille
                    etat="inconnu"
                    texte={v.a_un_compte ? "compte existant" : "sans compte"}
                  />
                </span>
                {#if v.personne_id === d.garde_id}
                  <span class="text-xs font-semibold text-stone-800 dark:text-stone-200">
                    reste — {v.inscrit ? "inscrite cette année" : "la plus récente"}
                  </span>
                {:else}
                  <span class="text-xs text-stone-500 dark:text-stone-400">
                    rejoint {cleDe(d, d.garde_id)}
                  </span>
                {/if}
              </div>
            {/each}
            <div class="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg bg-emerald-50/70 px-3 py-2 dark:bg-emerald-500/10">
              <GitMerge class="h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-300" />
              <p class="min-w-0 flex-1 text-xs text-stone-700 dark:text-stone-300">{d.motif}</p>
              <Bouton
                taille="sm"
                variante="primary"
                icon={GitMerge}
                occupe={enCours === d.cle}
                disabled={enCours !== null && enCours !== d.cle}
                onclick={() => reunir(d)}
              >
                Réunir les fiches
              </Bouton>
            </div>
          </div>
        {/each}
      {/if}
    </div>

    <BarreAction
      message="Rien n'est écrit tant que tu n'as pas tranché. Une adresse saisie devient l'adresse constatée ; une réunion garde la fiche de cette année et reconnaît l'ancien numéro à chaque ingestion."
    >
      <Bouton onclick={() => onNaviguer?.("ou_ca_coince")}>Retour aux constats</Bouton>
      {#if aDepartager.length}
        <Bouton
          variante={lot.length ? "secondary" : "primary"}
          icon={Check}
          occupe={typeof enCours === "number"}
          disabled={enCours !== null && typeof enCours !== "number"}
          onclick={validerTout}
        >
          {aDepartager.length > 1 ? `Valider les ${aDepartager.length} adresses` : "Valider l'adresse"}
        </Bouton>
      {/if}
      {#if lot.length}
        <Bouton
          variante="primary"
          icon={GitMerge}
          occupe={typeof enCours === "string"}
          disabled={enCours !== null}
          onclick={() => (demandeTout = true)}
        >
          {lot.length > 1 ? `Réunir les ${lot.length} paires` : "Réunir la paire"}
        </Bouton>
      {/if}
    </BarreAction>
  {/if}
</section>

{#if demandeTout}
  <Modale
    titre="Réunir {lot.length} paire{lot.length > 1 ? 's' : ''} de fiches"
    largeur="lg"
    onFermer={() => (demandeTout = false)}
  >
    <div class="space-y-3 text-sm text-stone-600 dark:text-stone-300">
      <p>
        Pour chaque paire, la fiche inscrite cette année reste. L'ancienne
        lui est rattachée : son année rejoint le parcours, son numéro et son
        identifiant restent reconnus, et rien n'est créé ni déplacé dans
        Google ou KoXo.
      </p>
      <p>
        Une année que la fiche gardée décrit déjà n'est pas reprise, et une
        sortie prévue pour l'ancienne fiche est abandonnée : la personne est
        toujours là. Le récapitulatif le dira, paire par paire.
      </p>
      <ul class="max-h-56 space-y-0.5 overflow-y-auto rounded-lg bg-stone-50 px-3 py-2 text-xs dark:bg-stone-900">
        {#each lot as g (cleDeGroupe(g))}
          {@const garde = g.visants.find((v) => v.personne_id === g.garde_id)}
          <li class="truncate">
            <b class="text-stone-800 dark:text-stone-200">{garde?.nom} {garde?.prenom}</b>
            — {g.motif}
          </li>
        {/each}
      </ul>
    </div>

    {#snippet actions()}
      <Bouton onclick={() => (demandeTout = false)}>Annuler</Bouton>
      <Bouton variante="primary" icon={GitMerge} onclick={reunirTout}>
        {lot.length > 1 ? `Réunir les ${lot.length}` : "Réunir"}
      </Bouton>
    {/snippet}
  </Modale>
{/if}

{#if apercu}
  {@const r = apercu.rapport}
  <Modale titre="Réunir {r.garde.prenom} {r.garde.nom} ?" largeur="lg" onFermer={() => (apercu = null)}>
    <div class="space-y-3 text-sm text-stone-600 dark:text-stone-300">
      {#if r.avertissements.length}
        <div class="space-y-1.5 rounded-lg bg-amber-50 px-3 py-2 text-amber-900 dark:bg-amber-400/10 dark:text-amber-200">
          {#each r.avertissements as a}
            <p class="flex gap-2">
              <TriangleAlert class="mt-0.5 h-4 w-4 shrink-0" />
              <span>{a}</span>
            </p>
          {/each}
        </div>
      {/if}
      <p>
        <b class="text-stone-800 dark:text-stone-200">{r.garde.cle_pivot} reste.</b>
        {r.motif_du_choix}
      </p>
      <dl class="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-xs">
        <dt class="libelle-champ">Rejoint le parcours</dt>
        <dd>{r.annees_rattachees.join(" · ") || "aucune année"}</dd>
        {#if r.annees_ecartees.length}
          <dt class="libelle-champ">Non reprises</dt>
          <dd>{r.annees_ecartees.join(" · ")}</dd>
        {/if}
        {#if r.repris.length}
          <dt class="libelle-champ">Repris</dt>
          <dd>{r.repris.join(" · ")}</dd>
        {/if}
        {#if r.abandonnes.length}
          <dt class="libelle-champ">Abandonné</dt>
          <dd>{r.abandonnes.join(" · ")}</dd>
        {/if}
        <dt class="libelle-champ">Ancien numéro</dt>
        <dd>
          {r.absorbee.cle_pivot} (badge {r.absorbee.badge}, identifiant
          {r.absorbee.login}) — reconnu à chaque ingestion, jamais recyclé
        </dd>
      </dl>
    </div>

    {#snippet actions()}
      <Bouton onclick={() => (apercu = null)}>Annuler</Bouton>
      <Bouton variante="primary" icon={GitMerge} onclick={confirmerApercu}>
        Réunir les deux fiches
      </Bouton>
    {/snippet}
  </Modale>
{/if}
