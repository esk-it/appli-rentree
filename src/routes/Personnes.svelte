<script>
  import { onMount } from "svelte";
  import Search from "@lucide/svelte/icons/search";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Pencil from "@lucide/svelte/icons/pencil";
  import Lock from "@lucide/svelte/icons/lock";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import X from "@lucide/svelte/icons/x";
  import Avatar from "$lib/components/Avatar.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import CopiableTexte from "$lib/components/CopiableTexte.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Modale from "$lib/components/Modale.svelte";
  import Nombre from "$lib/components/Nombre.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { personnes } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let liste = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let erreur = $state("");

  let recherche = $state("");
  let filtreType = $state(/** @type {"" | "eleve" | "adulte"} */ (""));
  let filtreSite = $state("");
  let filtreClasse = $state("");

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

  async function basculer(p) {
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
    let r = liste;
    if (filtreType) r = r.filter((p) => p.type === filtreType);
    if (filtreSite) r = r.filter((p) => p.site === filtreSite);
    if (filtreClasse) r = r.filter((p) => p.classe === filtreClasse);
    const q = recherche.trim().toLowerCase();
    if (q) {
      r = r.filter((p) =>
        `${p.nom} ${p.prenom} ${p.login} ${p.cle_pivot} ${p.badge}`
          .toLowerCase()
          .includes(q),
      );
    }
    return r;
  });

  let sitesDispo = $derived([
    ...new Set(liste.map((p) => p.site).filter(Boolean)),
  ].sort());

  // Les classes proposées suivent les filtres déjà posés : chercher une
  // classe de NDK dans une liste filtrée sur SU n'aurait pas de sens.
  let classesDispo = $derived(
    [
      ...new Set(
        liste
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
    { id: "", label: "Tous", badge: liste.length },
    { id: "eleve", label: "Élèves", badge: liste.filter((p) => p.type === "eleve").length },
    { id: "adulte", label: "Adultes", badge: liste.filter((p) => p.type === "adulte").length },
  ]);

  let optionsSite = $derived([
    { id: "", label: "Tous sites" },
    ...sitesDispo.map((s) => ({
      id: s,
      label: s,
      badge: liste.filter((p) => p.site === s).length,
    })),
  ]);

  onMount(rafraichir);

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
<section
  class="space-y-4"
  onclickcapture={(e) => {
    if (ouverte !== null && !e.target.closest("tr")) fermerFiche();
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
      <Segments bind:valeur={filtreType} taille="sm" options={optionsType} />

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

      {#if filtreType || filtreSite || filtreClasse || recherche}
        <button
          class="rounded-md px-2 py-1 text-xs text-stone-500 transition hover:bg-stone-100
                 hover:text-stone-800 dark:hover:bg-stone-700 dark:hover:text-stone-200"
          onclick={() => {
            filtreType = "";
            filtreSite = "";
            filtreClasse = "";
            recherche = "";
          }}
        >
          Tout afficher
        </button>
      {/if}

      <span class="ml-auto text-xs tabular-nums text-stone-500 dark:text-stone-400">
        <Nombre valeur={listeFiltree.length} duree={300} /> / {liste.length}
      </span>
    </div>
  </div>

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
    {:else if listeFiltree.length === 0}
      <div class="p-4">
        <EtatVide
          icon={Search}
          titre="Aucun résultat"
          message="Aucune personne ne correspond à ces filtres. Élargis la recherche ou retire un filtre."
        />
      </div>
    {:else}
      <div class="max-h-[640px] overflow-auto">
        <table class="w-full text-sm">
          <thead class="sticky top-0 z-10 bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300">
            <tr>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700"></th>
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
                class="cursor-pointer border-b border-stone-100 transition-colors dark:border-stone-800
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
                    <Avatar personneId={p.id} nom={p.nom} prenom={p.prenom} taille={40} />
                  </div>
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 font-mono text-xs text-stone-600 dark:text-stone-400">
                  {p.cle_pivot}
                </td>
                <td class="px-3 py-1.5 text-xs">
                  <span class="rounded-full px-2 py-0.5 {p.type === 'eleve' ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' : 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300'}">
                    {p.type}
                  </span>
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 font-medium">{p.nom}</td>
                <td class="whitespace-nowrap px-3 py-1.5">{p.prenom}</td>
                <td class="whitespace-nowrap px-3 py-1.5">
                  <CopiableTexte valeur={p.login} classe="font-mono text-xs" />
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
                      {#if ficheEnCours}
                        <p class="text-sm text-stone-500 dark:text-stone-400">
                          Lecture de la fiche…
                        </p>
                      {:else if fiche}
                        <div class="flex items-start gap-6">
                          <!-- La photo prend enfin la place qu'elle mérite :
                               à 40 pixels dans la liste, on ne reconnaît
                               personne. -->
                          <Avatar
                            personneId={p.id}
                            nom={p.nom}
                            prenom={p.prenom}
                            taille={112}
                          />

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
                                    {fiche.personne.login}
                                    <span class="ml-1 text-stone-400" title="Fixé pour toute la scolarité">
                                      figé
                                    </span>
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
