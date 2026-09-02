<script>
  import { onMount } from "svelte";
  import Search from "@lucide/svelte/icons/search";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Pencil from "@lucide/svelte/icons/pencil";
  import Lock from "@lucide/svelte/icons/lock";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import X from "@lucide/svelte/icons/x";
  import LayoutGrid from "@lucide/svelte/icons/layout-grid";
  import Rows3 from "@lucide/svelte/icons/rows-3";
  import Avatar from "$lib/components/Avatar.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import CopiableTexte from "$lib/components/CopiableTexte.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Modale from "$lib/components/Modale.svelte";
  import Nombre from "$lib/components/Nombre.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import Info from "@lucide/svelte/icons/info";
  import { annees as anneesApi, personnes } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let liste = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let erreur = $state("");

  let recherche = $state("");
  let filtreType = $state(/** @type {"" | "eleve" | "adulte"} */ (""));
  let filtreSite = $state("");
  let filtreClasse = $state("");

  /**
   * L'année observée, et le mouvement qu'on veut y voir.
   *
   * Sans année, l'écran montre le référentiel entier — l'état des lieux,
   * hors du temps. Avec une année, il montre ce qui s'y passe : qui entre,
   * qui sort, qui reste. Ce sont deux questions différentes, et la seconde
   * ne se répond pas en filtrant la première : elle demande de comparer
   * deux photographies annuelles, ce que seul le serveur peut faire.
   */
  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {null | number} */ (null));
  let filtreMouvement = $state("");
  let mouvements = $state(/** @type {any} */ (null));

  /**
   * Le mouvement demande une population : entrants et sortants ne se
   * lisent pas dans la même source selon qu'il s'agit d'élèves ou
   * d'adultes. « Tous » n'a donc pas de sens ici, et bascule sur les
   * élèves.
   */
  let typePourAnnee = $derived(filtreType === "adulte" ? "adulte" : "eleve");

  $effect(() => {
    if (anneeId === null) {
      mouvements = null;
      return;
    }
    const demande = { anneeId, type: typePourAnnee };
    let annule = false;
    chargement = true;
    personnes
      .mouvements(demande)
      .then((r) => {
        if (!annule) mouvements = r;
      })
      .catch((e) => {
        if (!annule) {
          erreur = String(e).replace(/^Error:\s*/, "");
          mouvements = null;
        }
      })
      .finally(() => {
        if (!annule) chargement = false;
      });
    return () => (annule = true);
  });

  const LIBELLES_MOUVEMENT = {
    entrant: "Nouveaux",
    sortant: "Sortants",
    present: "En poste",
  };

  const TEINTES_MOUVEMENT = {
    entrant: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
    sortant: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    present: "bg-stone-100 text-stone-600 dark:bg-stone-700/60 dark:text-stone-300",
  };

  /** Les lignes d'une année, mises à la forme du tableau du référentiel. */
  let lignesAnnee = $derived.by(() => {
    if (!mouvements) return [];
    return mouvements.lignes.map((l, i) => ({
      ...l,
      // Un arrivant sans compte n'a pas d'identifiant référentiel : on lui
      // donne une clé négative pour la boucle, et la ligne ne se déplie pas.
      id: l.personne_id ?? -(i + 1),
      sans_compte: l.personne_id === null,
    }));
  });

  let optionsMouvement = $derived.by(() => {
    if (!mouvements) return [];
    const n = mouvements.nb_par_mouvement;
    return [
      { id: "", label: "Tous", badge: mouvements.lignes.length },
      { id: "entrant", label: "Nouveaux", badge: n.entrant ?? 0 },
      { id: "sortant", label: "Sortants", badge: n.sortant ?? 0 },
      { id: "present", label: "En poste", badge: n.present ?? 0 },
    ];
  });

  /** Les années voisines effectivement disponibles, dites d'un trait. */
  let voisines = $derived.by(() => {
    if (!mouvements) return "";
    const v = [mouvements.annee_precedente, mouvements.annee_suivante].filter(Boolean);
    return v.join(" et à ");
  });

  /** La raison pour laquelle le mouvement demandé n'est pas établissable. */
  let raisonAbsente = $derived(
    mouvements && filtreMouvement ? (mouvements.raisons[filtreMouvement] ?? "") : "",
  );

  /**
   * La fiche dépliée, s'il y en a une.
   *
   * Une seule à la fois : ouvrir la suivante referme la précédente. Deux
   * fiches ouvertes obligeraient à chercher laquelle on regarde, et la
   * comparaison qu'on croit gagner se fait mieux en fermant l'une.
   */
  let ouverte = $state(/** @type {number|null} */ (null));
  let fiche = $state(/** @type {any} */ (null));
  let ficheEnCours = $state(false);

  /**
   * Deux façons de regarder les mêmes personnes.
   *
   * Le tableau sert à **comparer** : login, adresse, badge et mouvement
   * alignés, on lit une colonne d'un bout à l'autre. Il ne sert à rien pour
   * reconnaître quelqu'un — à quarante pixels, un visage n'est qu'une
   * tache.
   *
   * Le trombinoscope sert à **reconnaître** : c'est la vue qu'on veut
   * devant une classe, pour retrouver un élève dont on a le visage et pas
   * le nom, ou vérifier qu'une photo est bien la bonne. Les deux ont leur
   * moment, aucune ne remplace l'autre.
   */
  let vue = $state(/** @type {"tableau"|"trombinoscope"} */ ("tableau"));

  async function basculer(p) {
    if (p.sans_compte) {
      notify.info(
        `${p.prenom} ${p.nom} ne figure pas encore au référentiel : ` +
          "cette ligne vient du tableau des professeurs.",
      );
      return;
    }
    if (ouverte === p.id) {
      fermerFiche();
      return;
    }
    ouverte = p.id;
    fiche = null;
    ficheEnCours = true;
    try {
      fiche = await personnes.fiche(p.id);
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
      ouverte = null;
    } finally {
      ficheEnCours = false;
    }
  }

  function jour(iso) {
    return iso ? String(iso).slice(0, 10).split("-").reverse().join("/") : "—";
  }

  function fermerFiche() {
    ouverte = null;
    fiche = null;
  }

  // Échap ferme la fiche, comme une fenêtre — c'est le geste attendu, et
  // il évite d'avoir à viser une croix.
  function surTouche(e) {
    if (e.key === "Escape" && ouverte !== null) fermerFiche();
  }

  let listeFiltree = $derived.by(() => {
    let r = anneeId === null ? liste : lignesAnnee;
    if (filtreMouvement && anneeId !== null) {
      r = r.filter((p) => p.mouvement === filtreMouvement);
    }
    if (filtreType) r = r.filter((p) => p.type === filtreType);
    if (filtreSite) r = r.filter((p) => p.site === filtreSite);
    if (filtreClasse) r = r.filter((p) => p.classe === filtreClasse);
    const q = recherche.trim().toLowerCase();
    if (q) {
      r = r.filter((p) =>
        `${p.nom} ${p.prenom} ${p.login} ${p.login_constate ?? ""} ${p.cle_pivot} ${p.badge}`
          .toLowerCase()
          .includes(q),
      );
    }
    return r;
  });

  /** La source affichée : le référentiel entier, ou une année. */
  let source = $derived(anneeId === null ? liste : lignesAnnee);

  let sitesDispo = $derived([
    ...new Set(source.map((p) => p.site).filter(Boolean)),
  ].sort());

  // Les classes proposées suivent les filtres déjà posés : chercher une
  // classe de NDK dans une liste filtrée sur SU n'aurait pas de sens.
  let classesDispo = $derived(
    [
      ...new Set(
        source
          .filter((p) => (!filtreType || p.type === filtreType))
          .filter((p) => (!filtreSite || p.site === filtreSite))
          .map((p) => p.classe)
          .filter(Boolean),
      ),
    ].sort(),
  );

  // Les compteurs affichés dans les segments donnent la répartition sans
  // avoir à cliquer sur chaque filtre pour la découvrir.
  let optionsType = $derived([
    { id: "", label: "Tous", badge: source.length },
    { id: "eleve", label: "Élèves", badge: source.filter((p) => p.type === "eleve").length },
    { id: "adulte", label: "Adultes", badge: source.filter((p) => p.type === "adulte").length },
  ]);

  let optionsSite = $derived([
    { id: "", label: "Tous sites" },
    ...sitesDispo.map((s) => ({
      id: s,
      label: s,
      badge: source.filter((p) => p.site === s).length,
    })),
  ]);

  onMount(async () => {
    try {
      listeAnnees = (await anneesApi.lister()).slice().sort((a, b) =>
        a.libelle.localeCompare(b.libelle),
      );
    } catch {
      listeAnnees = [];
    }
    await rafraichir();
  });

  async function rafraichir() {
    chargement = true;
    erreur = "";
    try {
      liste = await personnes.lister();
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  // --- Adresse mail : saisie manuelle -------------------------------------
  // Nécessaire pour les cas que le programme refuse de trancher seul : deux
  // homonymes qui viseraient la même adresse, ou une adresse historique hors
  // convention qu'aucun export n'a fait remonter.
  let enEdition = $state(/** @type {any} */ (null));
  let saisie = $state("");
  let enregistrement = $state(false);

  function ouvrirEdition(p) {
    enEdition = p;
    saisie = p.email_est_constate ? (p.email ?? "") : "";
  }

  /**
   * Corriger le nom ou le prénom.
   *
   * Charlemagne se trompe, ou il est en retard, et rien ne permettait de
   * le contredire. La simulation montre d'abord ce que ça entraîne —
   * l'adresse calculée suit le prénom, et c'est souvent le but.
   */
  let enRenommage = $state(/** @type {any} */ (null));
  let nomSaisi = $state("");
  let prenomSaisi = $state("");
  let apercu = $state(/** @type {any} */ (null));

  function ouvrirRenommage(p) {
    enRenommage = p;
    nomSaisi = p.nom ?? "";
    prenomSaisi = p.prenom ?? "";
    apercu = null;
  }

  async function simulerRenommage() {
    if (!enRenommage) return;
    enregistrement = true;
    try {
      apercu = await personnes.corrigerIdentite(enRenommage.id, {
        nom: nomSaisi.trim(), prenom: prenomSaisi.trim(), mode: "simulation",
      });
    } catch (e) {
      apercu = null;
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 9000 });
    } finally {
      enregistrement = false;
    }
  }

  async function enregistrerRenommage() {
    if (!enRenommage) return;
    enregistrement = true;
    try {
      const r = await personnes.corrigerIdentite(enRenommage.id, {
        nom: nomSaisi.trim(), prenom: prenomSaisi.trim(), mode: "reel",
      });
      liste = await personnes.lister();
      notify.succes(
        r.changements.length
          ? `${r.prenom_apres} ${r.nom_apres} — ${r.changements.length} changement(s)`
          : "Rien à changer.",
      );
      for (const x of r.reste_a_faire) notify.info(x, { duree: 11000 });
      enRenommage = null;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 9000 });
    } finally {
      enregistrement = false;
    }
  }

  async function enregistrerEmail() {
    if (!enEdition) return;
    enregistrement = true;
    try {
      const maj = await personnes.definirEmail(enEdition.id, saisie.trim());
      liste = liste.map((x) => (x.id === maj.id ? maj : x));
      notify.succes(
        saisie.trim()
          ? `Adresse figée : ${maj.email}`
          : `Adresse recalculée : ${maj.email}`,
      );
      enEdition = null;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      enregistrement = false;
    }
  }
</script>

<svelte:window onkeydown={surTouche} />

<!--
  Le clic « à l'extérieur » se prend sur la section entière plutôt que sur
  la fenêtre : viser le document attraperait aussi les clics des modales
  et de la palette, qui vivent ailleurs dans l'arbre.
-->
{#snippet fichePersonne(p)}
          {#if ficheEnCours}
            <p class="text-sm text-stone-500 dark:text-stone-400">
              Lecture de la fiche…
            </p>
          {:else if fiche}
            <div class="flex items-start gap-6">
              <!-- La photo prend enfin la place qu'elle mérite : à 40 pixels
                   dans la liste, on ne reconnaît personne. En portrait plutôt
                   qu'en pastille — le rond coupe le menton et les oreilles,
                   et c'est là qu'on cherche à reconnaître quelqu'un. -->
              <div class="w-40 shrink-0">
                <Avatar
                  personneId={p.id}
                  nom={p.nom}
                  prenom={p.prenom}
                  forme="portrait"
                />
              </div>

              <div class="grid min-w-0 flex-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
                <div>
                  <p class="libelle-champ">Identité</p>
                  <p class="text-base font-semibold text-stone-900 dark:text-stone-100">
                    {fiche.personne.prenom} {fiche.personne.nom}
                  </p>
                  {#if fiche.personne.nom_usage}
                    <p class="text-xs text-stone-500 dark:text-stone-400">
                      nom d'usage : {fiche.personne.nom_usage}
                    </p>
                  {/if}
                  <dl class="mt-2 space-y-0.5 text-xs">
                    <div class="flex gap-2">
                      <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Clé pivot</dt>
                      <dd class="font-mono">{fiche.personne.cle_pivot}</dd>
                    </div>
                    <div class="flex gap-2">
                      <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Badge</dt>
                      <dd class="font-mono tabular-nums">{fiche.personne.badge}</dd>
                    </div>
                    <div class="flex gap-2">
                      <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Login</dt>
                      <dd class="font-mono">
                        {fiche.personne.login_constate ?? fiche.personne.login}
                        {#if fiche.personne.login_constate && fiche.personne.login_constate !== fiche.personne.login}
                          <span class="ml-1 text-amber-600 dark:text-amber-400">
                            constaté dans KoXo
                          </span>
                          <span class="ml-1 text-stone-400">
                            (le référentiel avait calculé « {fiche.personne.login} »,
                            déjà pris par quelqu'un d'autre chez lui)
                          </span>
                        {:else}
                          <span class="ml-1 text-stone-400" title="Fixé pour toute la scolarité">
                            figé
                          </span>
                        {/if}
                      </dd>
                    </div>
                    {#if fiche.personne.date_entree}
                      <div class="flex gap-2">
                        <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Entrée</dt>
                        <dd class="tabular-nums">{jour(fiche.personne.date_entree)}</dd>
                      </div>
                    {/if}
                    {#if fiche.personne.poste_occupe}
                      <div class="flex gap-2">
                        <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Poste</dt>
                        <dd>{fiche.personne.poste_occupe}</dd>
                      </div>
                    {/if}
                    {#if fiche.personne.matieres}
                      <div class="flex gap-2">
                        <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Matières</dt>
                        <dd>{fiche.personne.matieres}</dd>
                      </div>
                    {/if}
                  </dl>
                </div>

                <div>
                  <p class="libelle-champ">Parcours</p>
                  {#if fiche.parcours.length}
                    <ol class="space-y-1.5">
                      {#each fiche.parcours as a, i (a.annee)}
                        <li class="flex items-baseline gap-2 text-xs">
                          <span
                            class="font-mono tabular-nums {i === 0
                              ? 'text-stone-900 dark:text-stone-100'
                              : 'text-stone-400 dark:text-stone-500'}"
                          >
                            {a.annee}
                          </span>
                          <span
                            class="font-medium {i === 0
                              ? 'text-emerald-700 dark:text-emerald-400'
                              : 'text-stone-600 dark:text-stone-400'}"
                          >
                            {a.classe ?? "—"}
                          </span>
                          {#if a.regime}
                            <span class="text-stone-400 dark:text-stone-500">
                              régime {a.regime}
                            </span>
                          {/if}
                        </li>
                      {/each}
                    </ol>
                    {#if fiche.parcours.length === 1}
                      <p class="mt-1.5 text-xs text-stone-400 dark:text-stone-500">
                        Une seule année connue — arrivé cette année, ou
                        ingestion d'une seule campagne.
                      </p>
                    {/if}
                  {:else}
                    <p class="text-xs text-stone-400 dark:text-stone-500">
                      Aucune année ingérée pour cette personne.
                    </p>
                  {/if}
                </div>

                <div>
                  <p class="libelle-champ">Compte Google</p>
                  {#if fiche.comptes.length}
                    {#each fiche.comptes as c (c.cible)}
                      <dl class="space-y-0.5 text-xs">
                        <div class="flex gap-2">
                          <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">État</dt>
                          <dd>
                            <span
                              class="rounded-full px-2 py-0.5 {c.etat === 'quarantaine'
                                ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
                                : c.etat === 'purge'
                                  ? 'bg-stone-200 text-stone-700 dark:bg-stone-700 dark:text-stone-300'
                                  : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'}"
                            >
                              {c.etat}
                            </span>
                          </dd>
                        </div>
                        {#if c.ou_appliquee}
                          <div class="flex gap-2">
                            <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">OU appliquée</dt>
                            <dd class="min-w-0 break-all font-mono">{c.ou_appliquee}</dd>
                          </div>
                        {/if}
                        {#if c.ou_constatee && c.ou_constatee !== c.ou_appliquee}
                          <div class="flex gap-2">
                            <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Dans Google</dt>
                            <dd class="min-w-0 break-all font-mono text-amber-700 dark:text-amber-400">
                              {c.ou_constatee}
                            </dd>
                          </div>
                        {/if}
                        {#if c.date_prevue_purge}
                          <div class="flex gap-2">
                            <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Suppression</dt>
                            <dd class="tabular-nums">{jour(c.date_prevue_purge)}</dd>
                          </div>
                        {/if}
                        {#if c.note}
                          <p class="mt-1 text-stone-500 dark:text-stone-400">{c.note}</p>
                        {/if}
                      </dl>
                    {/each}
                  {:else}
                    <p class="text-xs text-stone-400 dark:text-stone-500">
                      Aucun compte enregistré — il sera créé à l'export
                      des nouveaux.
                    </p>
                  {/if}
                </div>
              </div>

              <button
                type="button"
                class="shrink-0 rounded-md p-1 text-stone-400 transition hover:bg-stone-200
                       hover:text-stone-700 dark:hover:bg-stone-700 dark:hover:text-stone-200"
                aria-label="Fermer la fiche"
                onclick={(e) => {
                  e.stopPropagation();
                  fermerFiche();
                }}
              >
                <X class="h-4 w-4" />
              </button>
            </div>
          {/if}
{/snippet}

<section
  class="space-y-4"
  onclickcapture={(e) => {
    // Ce qui garde la fiche ouverte diffère selon la vue : une rangée dans
    // le tableau, une vignette ou la fiche elle-même dans le trombinoscope.
    // Sans les trois, cliquer une vignette refermerait ce qu'on vient
    // d'ouvrir, et le bouton « Fermer » de la fiche serait hors de portée.
    const dedans = e.target.closest("tr, [data-fiche], [data-vignette]");
    if (ouverte !== null && !dedans) fermerFiche();
  }}
>
  <EnTetePage
    icon={Users2}
    titre="Référentiel des personnes"
    description="Identité persistante des élèves et adultes. Créée à la première apparition, jamais supprimée — le login reste figé, y compris après un départ."
  />

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  <div class="card p-3">
    <div class="flex flex-wrap items-center gap-3">
      <div class="relative">
        <Search class="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
        <input
          type="search"
          placeholder="Nom, prénom, login, clé pivot, badge…"
          bind:value={recherche}
          class="w-80 rounded-lg border border-stone-300 py-1.5 pl-8 pr-3 text-sm dark:border-stone-600 dark:bg-stone-800 dark:text-stone-200"
        />
      </div>
      <!-- L'année d'abord : c'est elle qui décide si l'écran montre un état
           des lieux ou un mouvement, et donc ce que les autres filtres
           signifient. -->
      <select
        class="rounded-lg border border-stone-300 px-2 py-1.5 text-sm dark:border-stone-600
               dark:bg-stone-800 dark:text-stone-200"
        bind:value={anneeId}
        aria-label="Année observée"
      >
        <option value={null}>Tout le référentiel</option>
        {#each listeAnnees as a (a.id)}
          <option value={a.id}>{a.libelle}</option>
        {/each}
      </select>

      <Segments bind:valeur={filtreType} taille="sm" options={optionsType} />

      {#if anneeId !== null && optionsMouvement.length}
        <Segments bind:valeur={filtreMouvement} taille="sm" options={optionsMouvement} />
      {/if}

      {#if sitesDispo.length}
        <Segments bind:valeur={filtreSite} taille="sm" options={optionsSite} />
      {/if}

      <!-- Une soixantaine de classes : un menu plutôt que des segments,
           qui déborderaient de la barre. -->
      {#if classesDispo.length > 1}
        <select
          class="rounded-lg border border-stone-300 px-2 py-1.5 text-sm dark:border-stone-600
                 dark:bg-stone-800 dark:text-stone-200"
          bind:value={filtreClasse}
          aria-label="Filtrer par classe"
        >
          <option value="">Toutes les classes</option>
          {#each classesDispo as c (c)}
            <option value={c}>{c}</option>
          {/each}
        </select>
      {/if}

      {#if filtreType || filtreSite || filtreClasse || recherche || anneeId !== null}
        <button
          class="rounded-md px-2 py-1 text-xs text-stone-500 transition hover:bg-stone-100
                 hover:text-stone-800 dark:hover:bg-stone-700 dark:hover:text-stone-200"
          onclick={() => {
            filtreType = "";
            filtreSite = "";
            filtreClasse = "";
            recherche = "";
            anneeId = null;
            filtreMouvement = "";
          }}
        >
          Tout afficher
        </button>
      {/if}

      <div class="ml-auto flex items-center gap-3">
        <Segments
          bind:valeur={vue}
          taille="sm"
          options={[
            { id: "tableau", label: "Tableau", icon: Rows3 },
            { id: "trombinoscope", label: "Trombinoscope", icon: LayoutGrid },
          ]}
        />
        <span class="text-xs tabular-nums text-stone-500 dark:text-stone-400">
          <Nombre valeur={listeFiltree.length} duree={300} /> / {source.length}
        </span>
      </div>
    </div>
  </div>

  <!-- Une liste vide parce que la question n'a pas de réponse ne ressemble
       en rien à une liste vide parce qu'il n'y a personne. -->
  {#if mouvements}
    <p class="text-xs text-stone-500 dark:text-stone-400">
      {mouvements.annee} · {mouvements.type_personne === "eleve" ? "élèves" : "adultes"}
      · source : {mouvements.source}{#if voisines}{" · comparée à " + voisines}{/if}
    </p>
  {/if}

  <div class="card overflow-hidden">
    {#if chargement}
      <div class="p-4">
        <Squelette variante="ligne-tableau" nb={6} colonnes={6} />
      </div>
    {:else if liste.length === 0}
      <div class="p-4">
        <EtatVide
          icon={Users2}
          titre="Référentiel vide"
          message="Charge d'abord tes comptes existants depuis l'onglet Amorçage KoXo, puis dépose un export Charlemagne dans Snapshots d'années."
        />
      </div>
    {:else if listeFiltree.length === 0 && raisonAbsente}
      <!-- Retirer un filtre ne donnerait rien : ce n'est pas le filtre qui
           vide la liste, c'est la question qui n'a pas de réponse. -->
      <div class="p-4">
        <EtatVide
          icon={Info}
          titre="Cette liste ne peut pas être établie"
          message={raisonAbsente}
        />
      </div>
    {:else if listeFiltree.length === 0}
      <div class="p-4">
        <EtatVide
          icon={Search}
          titre="Aucun résultat"
          message="Aucune personne ne correspond à ces filtres. Élargis la recherche ou retire un filtre."
        />
      </div>
    {:else if vue === "trombinoscope"}
      <div class="max-h-[640px] overflow-auto p-3">
        <div class="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
          {#each listeFiltree as p (p.id)}
            <button
              type="button"
              data-vignette
              class="card-interactive overflow-hidden p-2 text-center
                     {ouverte === p.id ? 'ring-2 ring-emerald-500' : ''}"
              onclick={() => basculer(p)}
              title="{p.prenom} {p.nom}{p.classe ? ' · ' + p.classe : ''}"
            >
              <Avatar
                personneId={p.sans_compte ? null : p.id}
                nom={p.nom}
                prenom={p.prenom}
                forme="portrait"
              />
              <span class="mt-2 block truncate text-xs font-semibold leading-tight">
                {p.prenom}
              </span>
              <span class="block truncate text-xs uppercase leading-tight text-stone-600 dark:text-stone-400">
                {p.nom}
              </span>
              <span class="mt-1 block text-[11px] text-stone-500 dark:text-stone-400">
                {p.classe ?? (p.type === "adulte" ? "adulte" : "—")}
              </span>
              {#if anneeId !== null}
                <span class="mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] {TEINTES_MOUVEMENT[p.mouvement]}">
                  {LIBELLES_MOUVEMENT[p.mouvement]}
                </span>
              {/if}
            </button>
          {/each}
        </div>
      </div>
    {:else}
      <div class="max-h-[640px] overflow-auto">
        <table class="w-full text-sm">
          <thead class="sticky top-0 z-10 bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300">
            <tr>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700"></th>
              {#if anneeId !== null}
                <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Mouvement</th>
              {/if}
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Clé pivot</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Type</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Nom</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Prénom</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Login</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Email</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Site</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Classe</th>
              <th class="border-b border-stone-200 px-3 py-2 text-right font-semibold dark:border-stone-700">Badge</th>
            </tr>
          </thead>
          <tbody>
            {#each listeFiltree as p (p.id)}
              <tr
                class="border-b border-stone-100 transition-colors dark:border-stone-800
                       {p.sans_compte ? 'cursor-default' : 'cursor-pointer'}
                       {ouverte === p.id
                  ? 'bg-emerald-50/70 dark:bg-emerald-900/25'
                  : 'hover:bg-emerald-50/40 dark:hover:bg-emerald-900/20'}"
                onclick={() => basculer(p)}
              >
                <td class="py-1 pl-1 pr-2">
                  <div class="flex items-center gap-1">
                    <ChevronRight
                      class="h-3.5 w-3.5 shrink-0 text-stone-300 transition-transform duration-150
                             dark:text-stone-600 {ouverte === p.id ? 'rotate-90' : ''}"
                    />
                    <Avatar
                      personneId={p.sans_compte ? null : p.id}
                      nom={p.nom}
                      prenom={p.prenom}
                      taille={40}
                    />
                  </div>
                </td>
                {#if anneeId !== null}
                  <td class="whitespace-nowrap px-3 py-1.5 text-xs">
                    <span class="rounded-full px-2 py-0.5 {TEINTES_MOUVEMENT[p.mouvement]}">
                      {LIBELLES_MOUVEMENT[p.mouvement]}
                    </span>
                    {#if p.detail}
                      <span class="ml-2 text-stone-500 dark:text-stone-400">{p.detail}</span>
                    {/if}
                  </td>
                {/if}
                <td class="whitespace-nowrap px-3 py-1.5 font-mono text-xs text-stone-600 dark:text-stone-400">
                  {p.cle_pivot ?? "—"}
                </td>
                <td class="px-3 py-1.5 text-xs">
                  <span class="rounded-full px-2 py-0.5 {p.type === 'eleve' ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' : 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300'}">
                    {p.type}
                  </span>
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 font-medium">{p.nom}</td>
                <td class="whitespace-nowrap px-3 py-1.5">
                  <div class="group/nom flex items-center gap-1.5">
                    <span>{p.prenom}</span>
                    <!-- Charlemagne se trompe, ou il est en retard. Jusqu'ici
                         rien ne permettait de le contredire. -->
                    <button
                      type="button"
                      title="Corriger le nom ou le prénom"
                      aria-label="Corriger l'identité de {p.prenom} {p.nom}"
                      onclick={(e) => {
                        e.stopPropagation();
                        ouvrirRenommage(p);
                      }}
                      class="rounded p-0.5 text-stone-300 opacity-60 transition hover:bg-stone-200 hover:text-stone-700 focus:opacity-100 group-hover/nom:opacity-100 dark:text-stone-600 dark:hover:bg-stone-700 dark:hover:text-stone-200"
                    >
                      <Pencil class="h-3 w-3" />
                    </button>
                  </div>
                </td>
                <!-- L'identifiant détenu prime sur celui que le référentiel
                     a calculé : `login` est unique ici alors que les
                     identifiants vivent dans une base KoXo par population.
                     Afficher le calculé faisait douter — à raison — de ce
                     que le référentiel raconte. -->
                <td class="whitespace-nowrap px-3 py-1.5">
                  <CopiableTexte
                    valeur={p.login_constate ?? p.login}
                    classe="font-mono text-xs"
                  />
                  {#if p.login_constate && p.login_constate !== p.login}
                    <span
                      class="ml-1 cursor-help text-[10px] text-amber-600 dark:text-amber-400"
                      title={`Le référentiel avait calculé « ${p.login} », déjà pris chez lui. KoXo détient « ${p.login_constate} ».`}
                    >
                      constaté
                    </span>
                  {/if}
                </td>
                <td class="whitespace-nowrap px-3 py-1.5">
                  <div class="group/mail flex items-center gap-1.5">
                    {#if p.email_est_constate}
                      <!-- Adresse d'un compte en place : ne sera jamais recalculée -->
                      <Lock
                        class="h-3 w-3 shrink-0 text-emerald-600 dark:text-emerald-400"
                      />
                    {/if}
                    <CopiableTexte
                      valeur={p.email ?? ""}
                      classe="font-mono text-xs {p.email_est_constate
                        ? 'text-stone-800 dark:text-stone-200'
                        : 'text-stone-500 italic dark:text-stone-400'}"
                    />
                    <!--
                      Discret mais toujours visible : caché jusqu'au survol,
                      l'action serait introuvable pour qui ne pense pas à
                      promener la souris sur la colonne.
                    -->
                    <button
                      type="button"
                      title="Figer ou corriger l'adresse"
                      aria-label="Modifier l'adresse de {p.prenom} {p.nom}"
                      onclick={(e) => {
                        e.stopPropagation();
                        ouvrirEdition(p);
                      }}
                      class="rounded p-0.5 text-stone-300 opacity-60 transition hover:bg-stone-200 hover:text-stone-700 focus:opacity-100 group-hover/mail:opacity-100 dark:text-stone-600 dark:hover:bg-stone-700 dark:hover:text-stone-200"
                    >
                      <Pencil class="h-3 w-3" />
                    </button>
                  </div>
                </td>
                <td class="px-3 py-1.5 text-stone-600 dark:text-stone-400">{p.site ?? "—"}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-stone-600 dark:text-stone-400">{p.classe ?? "—"}</td>
                <td class="px-3 py-1.5 text-right tabular-nums text-stone-600 dark:text-stone-400">{p.badge}</td>
              </tr>

              {#if ouverte === p.id}
                <tr class="border-b border-stone-200 bg-stone-50/80 dark:border-stone-700 dark:bg-stone-800/50">
                  <td colspan="10" class="p-0">
                    <div class="anim-apparition-douce px-5 py-4">
                      {@render fichePersonne(p)}
                    </div>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>

      <p class="border-t border-stone-100 px-3 py-2 text-xs text-stone-500 dark:border-stone-800 dark:text-stone-400">
        <Lock class="inline h-3 w-3 text-emerald-600 dark:text-emerald-400" />
        adresse d'un compte existant, jamais recalculée —
        <span class="italic">en gris clair</span>, adresse calculée pour un compte
        à créer.
      </p>
    {/if}
  </div>
</section>

<!-- Le trombinoscope ouvre la fiche en fenêtre, pas au-dessus de la grille :
     une bande insérée dans le flux repousse les vignettes, et celle qu'on
     vient de cliquer se retrouve ailleurs qu'où on l'a laissée. -->
{#if vue === "trombinoscope" && ouverte !== null}
  {@const p = listeFiltree.find((x) => x.id === ouverte)}
  {#if p}
    <Modale
      titre="{p.prenom} {p.nom}"
      largeur="xl"
      onFermer={fermerFiche}
    >
      {@render fichePersonne(p)}
    </Modale>
  {/if}
{/if}

{#if enRenommage}
  <Modale titre="Nom et prénom — {enRenommage.prenom} {enRenommage.nom}"
          onFermer={() => (enRenommage = null)}>
    <div class="space-y-3">
      <p class="text-sm text-stone-600 dark:text-stone-300">
        Le référentiel se remplit par ingestion, et Charlemagne fait foi. Il
        se trompe parfois, ou il est en retard. Corriger ici fait suivre les
        exports — et l'adresse calculée, si elle n'a pas été figée.
      </p>

      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="libelle-champ" for="champ-nom">Nom</label>
          <input id="champ-nom" class="champ" bind:value={nomSaisi}
                 oninput={() => (apercu = null)} />
        </div>
        <div>
          <label class="libelle-champ" for="champ-prenom">Prénom</label>
          <input id="champ-prenom" class="champ" bind:value={prenomSaisi}
                 oninput={() => (apercu = null)} />
        </div>
      </div>

      {#if apercu}
        {#if apercu.changements.length === 0}
          <p class="text-sm text-stone-500 dark:text-stone-400">
            Rien ne change.
          </p>
        {:else}
          <ul class="space-y-1 rounded-lg border border-stone-200 bg-stone-50 p-2 text-sm dark:border-stone-700 dark:bg-stone-800">
            {#each apercu.changements as c}<li>{c}</li>{/each}
          </ul>
        {/if}
        {#each apercu.reste_a_faire as x}
          <p class="rounded-lg border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
            {x}
          </p>
        {/each}
      {/if}

      <p class="text-xs text-stone-500 dark:text-stone-400">
        L'identifiant <span class="font-mono">{enRenommage.login_constate ?? enRenommage.login}</span>
        ne bouge pas : c'est celui que KoXo détient, et le changer ferait
        renommer le compte de l'annuaire.
      </p>
    </div>

    {#snippet actions()}
      <Bouton onclick={() => (enRenommage = null)}>Annuler</Bouton>
      <Bouton occupe={enregistrement} onclick={simulerRenommage}>
        Voir ce que ça change
      </Bouton>
      <Bouton variante="primary" occupe={enregistrement}
              disabled={!apercu || apercu.changements.length === 0}
              onclick={enregistrerRenommage}>
        Corriger
      </Bouton>
    {/snippet}
  </Modale>
{/if}

{#if enEdition}
  <Modale titre="Adresse mail — {enEdition.prenom} {enEdition.nom}" onFermer={() => (enEdition = null)}>
    <div class="space-y-3">
      <p class="text-sm text-stone-600 dark:text-stone-300">
        Laisse vide pour utiliser l'adresse calculée à partir du nom et du
        prénom. Saisis une adresse pour la figer — c'est ce qu'il faut faire
        quand un homonyme possède déjà l'adresse calculée.
      </p>

      <div>
        <label class="libelle-champ" for="champ-email">Adresse</label>
        <input
          id="champ-email"
          type="email"
          class="champ font-mono"
          placeholder={enEdition.email ?? "prenom.nom@domaine"}
          bind:value={saisie}
          onkeydown={(e) => e.key === "Enter" && enregistrerEmail()}
        />
      </div>

      <p class="text-xs text-stone-500 dark:text-stone-400">
        Login réseau : <span class="font-mono">{enEdition.login}</span> — il
        reste figé et n'a pas à correspondre à l'adresse.
      </p>
    </div>

    {#snippet actions()}
      <Bouton onclick={() => (enEdition = null)}>Annuler</Bouton>
      <Bouton variante="primary" occupe={enregistrement} onclick={enregistrerEmail}>
        Enregistrer
      </Bouton>
    {/snippet}
  </Modale>
{/if}
