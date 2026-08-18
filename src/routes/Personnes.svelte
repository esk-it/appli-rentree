<script>
  import { onMount } from "svelte";
  import Search from "@lucide/svelte/icons/search";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Pencil from "@lucide/svelte/icons/pencil";
  import Lock from "@lucide/svelte/icons/lock";
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

  let listeFiltree = $derived.by(() => {
    let r = liste;
    if (filtreType) r = r.filter((p) => p.type === filtreType);
    if (filtreSite) r = r.filter((p) => p.site === filtreSite);
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

<section class="space-y-4">
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
              <tr class="border-b border-stone-100 dark:border-stone-800 hover:bg-emerald-50/40 dark:hover:bg-emerald-900/20">
                <td class="px-3 py-1">
                  <Avatar personneId={p.id} nom={p.nom} prenom={p.prenom} taille={32} />
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
                      onclick={() => ouvrirEdition(p)}
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
