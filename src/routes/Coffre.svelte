<script>
  /**
   * Le coffre à mots de passe.
   *
   * Retrouver le mot de passe d'un élève obligeait à ouvrir KoXo. Et pour
   * NDE, qui n'a pas de serveur KoXo, le mot de passe n'existe nulle part.
   *
   * Trois états, et l'écran n'en montre qu'un à la fois : pas encore de
   * mot de passe maître, coffre fermé, coffre ouvert. Mélanger les trois
   * ferait un formulaire qui demande tout et n'explique rien.
   */
  import { onMount, onDestroy } from "svelte";
  import KeyRound from "@lucide/svelte/icons/key-round";
  import Lock from "@lucide/svelte/icons/lock";
  import LockOpen from "@lucide/svelte/icons/lock-open";
  import Search from "@lucide/svelte/icons/search";
  import Upload from "@lucide/svelte/icons/upload";
  import Copy from "@lucide/svelte/icons/copy";
  import ShieldAlert from "@lucide/svelte/icons/shield-alert";
  import GitCompare from "@lucide/svelte/icons/git-compare";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import MotsDePasseGoogle from "$lib/components/MotsDePasseGoogle.svelte";
  import { coffreApi, sites as sitesApi } from "$lib/api.js";
  import { jour } from "$lib/referentiel.js";
  import { notify } from "$lib/toasts.js";

  let etat = $state(/** @type {any} */ (null));
  let motDePasse = $state("");
  let confirmation = $state("");
  let occupe = $state(false);

  let requete = $state("");
  let resultats = $state(/** @type {any[]} */ ([]));
  let recherche = $state(false);
  let cherchee = $state("");

  let listeSites = $state(/** @type {any[]} */ ([]));
  let fichierKoxo = $state(/** @type {File|null} */ (null));
  let siteVersement = $state(/** @type {string|null} */ (null));

  let minuteur = /** @type {any} */ (null);

  /**
   * Les écarts entre sources, et le dernier versement.
   *
   * Le coffre ne garde que des relevés datés. Le 13 octobre 2026, celui de
   * KoXo NDK datait du 31 août : les 140 montants de SU y avaient retrouvé
   * leur mot de passe du collège le 15 septembre, et le coffre gardait
   * celui de la rentrée. Rien ne le montrait — l'étiquette d'Eléanor BRETON
   * l'a imprimé. L'écran dit désormais qui diffère, et de quand date chaque
   * source.
   */
  let ecarts = $state(/** @type {any} */ (null));
  let comparaison = $state(false);
  let dernierVersement = $state(/** @type {any} */ (null));

  /** Les noms de source, tels qu'on les lit dans KoXo et Charlemagne. */
  const nomSource = (s) =>
    s.cible === "koxo" ? `KoXo ${s.site ?? ""}`.trim()
      : s.cible === "charlemagne" ? "Charlemagne"
        : "Google (fabriqué)";

  async function comparer() {
    comparaison = true;
    try {
      ecarts = await coffreApi.ecarts();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      comparaison = false;
    }
  }

  // Coffre ouvert : les écarts se comparent d'eux-mêmes — un dixième de
  // seconde, et c'est la première chose à savoir avant d'imprimer.
  $effect(() => {
    if (etat?.ouvert && ecarts === null && !comparaison) comparer();
  });


  onMount(async () => {
    await relire();
    try {
      listeSites = await sitesApi.lister();
    } catch {
      // Le coffre marche sans : le site n'est qu'une étiquette.
    }
    // Le compte à rebours de refermeture n'a d'intérêt que s'il descend.
    minuteur = setInterval(() => {
      if (etat?.ouvert && etat.expire_dans > 0) etat.expire_dans -= 1;
      else if (etat?.ouvert && etat.expire_dans <= 0) relire();
    }, 1000);
  });

  onDestroy(() => clearInterval(minuteur));

  async function relire() {
    try {
      etat = await coffreApi.etat();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    }
  }

  async function creer() {
    if (motDePasse !== confirmation) {
      notify.avertissement("Les deux saisies diffèrent.");
      return;
    }
    occupe = true;
    try {
      etat = await coffreApi.initialiser(motDePasse);
      motDePasse = confirmation = "";
      notify.succes("Coffre créé. Note ce mot de passe : il ne se retrouve pas.");
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      occupe = false;
    }
  }

  async function ouvrir() {
    occupe = true;
    try {
      etat = await coffreApi.ouvrir(motDePasse);
      motDePasse = "";
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      occupe = false;
    }
  }

  async function fermer() {
    ecarts = null;
    dernierVersement = null;
    resultats = [];
    cherchee = "";
    requete = "";
    etat = await coffreApi.verrouiller();
  }

  async function chercher() {
    const q = requete.trim();
    if (!q) {
      resultats = [];
      cherchee = "";
      return;
    }
    recherche = true;
    try {
      resultats = await coffreApi.chercher(q);
      cherchee = q;
      if (!resultats.length) notify.info(`Aucun mot de passe pour « ${q} ».`);
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
      await relire();
    } finally {
      recherche = false;
    }
  }

  async function verser() {
    if (!fichierKoxo) return;
    occupe = true;
    try {
      const r = await coffreApi.verser({ fichier: fichierKoxo, site: siteVersement });
      dernierVersement = r;
      notify.succes(r.resume);
      if (r.nb_sans_correspondance) {
        notify.avertissement(
          `${r.nb_sans_correspondance} identifiant(s) du fichier sont inconnus du référentiel.`,
        );
      }
      fichierKoxo = null;
      await relire();
      await comparer();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      occupe = false;
    }
  }

  async function copier(texte) {
    try {
      await navigator.clipboard.writeText(texte);
      notify.succes("Copié.");
    } catch {
      notify.avertissement("Le presse-papiers a refusé la copie.");
    }
  }

  let minutes = $derived(Math.floor((etat?.expire_dans ?? 0) / 60));
  let secondes = $derived((etat?.expire_dans ?? 0) % 60);
</script>

<section class="space-y-5">
  <EnTetePage
    icon={KeyRound}
    titre="Coffre"
    description="Retrouver le mot de passe d'une personne sans ouvrir KoXo. Ceux de KoXo, ceux que Charlemagne garde — rangés à chaque ingestion coffre ouvert —, ceux fabriqués pour NDE. Chiffrés : sans le mot de passe maître, le fichier de base ne vaut rien."
  />

  {#if !etat}
    <p class="text-sm text-stone-500 dark:text-stone-400">Lecture de l'état…</p>

  {:else if !etat.initialise}
    <!-- Premier usage : on crée le mot de passe maître, et on dit ce qu'il
         engage avant qu'il soit choisi, pas après. -->
    <div class="card space-y-4 p-4">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
        Créer le coffre
      </h2>

      <div class="rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-900/20">
        <div class="flex items-start gap-2.5">
          <ShieldAlert class="mt-0.5 h-4 w-4 shrink-0 text-amber-700 dark:text-amber-400" />
          <div class="text-sm text-amber-900 dark:text-amber-200">
            <p class="font-medium">Ce mot de passe ne se retrouve pas.</p>
            <p class="mt-1 text-xs leading-relaxed">
              Il n'est enregistré nulle part — c'est ce qui rend le coffre
              inutilisable pour qui copierait le fichier de base. La
              contrepartie est absolue : oublié, tout ce qu'il protège
              devient définitivement illisible. Note-le ailleurs, dès
              maintenant.
            </p>
          </div>
        </div>
      </div>

      <label class="block">
        <span class="libelle-champ">Mot de passe maître</span>
        <input class="champ w-full max-w-md" type="password" bind:value={motDePasse}
               placeholder="Une phrase, plutôt qu'un mot" autocomplete="new-password" />
      </label>
      <label class="block">
        <span class="libelle-champ">Répéter</span>
        <input class="champ w-full max-w-md" type="password" bind:value={confirmation}
               autocomplete="new-password" />
      </label>

      <Bouton variante="primary" icon={Lock} {occupe}
              disabled={motDePasse.length < 10 || !confirmation}
              onclick={creer}>
        Créer le coffre
      </Bouton>
      <p class="text-xs text-stone-500 dark:text-stone-400">
        Dix caractères au minimum. Une phrase se retient mieux qu'un mot
        compliqué, et résiste davantage.
      </p>
    </div>

  {:else if !etat.ouvert}
    <div class="card space-y-3 p-4">
      <h2 class="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
        <Lock class="h-4 w-4" />
        Coffre fermé
      </h2>
      <p class="text-sm text-stone-600 dark:text-stone-400">
        {etat.nb_secrets} mot(s) de passe conservé(s).
      </p>
      <form class="flex flex-wrap items-end gap-2" onsubmit={(e) => { e.preventDefault(); ouvrir(); }}>
        <label class="block">
          <span class="libelle-champ">Mot de passe maître</span>
          <input class="champ w-72" type="password" bind:value={motDePasse}
                 autocomplete="current-password" />
        </label>
        <Bouton variante="primary" icon={LockOpen} {occupe}
                disabled={!motDePasse} onclick={ouvrir}>
          Ouvrir
        </Bouton>
      </form>
    </div>

  {:else}
    <!-- Coffre ouvert -->
    <div class="card space-y-3 p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
          <LockOpen class="h-4 w-4" />
          Coffre ouvert
        </h2>
        <div class="flex items-center gap-3">
          <span class="font-mono text-xs text-stone-500 dark:text-stone-400"
                title="Refermeture automatique après inactivité">
            {minutes}:{String(secondes).padStart(2, "0")}
          </span>
          <Bouton taille="sm" icon={Lock} onclick={fermer}>Fermer</Bouton>
        </div>
      </div>

      <form class="flex flex-wrap items-end gap-2" onsubmit={(e) => { e.preventDefault(); chercher(); }}>
        <label class="block flex-1" style="min-width: 16rem;">
          <span class="libelle-champ">Nom, prénom ou identifiant</span>
          <input class="champ w-full" bind:value={requete}
                 placeholder="Un champ vide ne rend rien" />
        </label>
        <Bouton variante="primary" icon={Search} occupe={recherche}
                disabled={!requete.trim()} onclick={chercher}>
          Chercher
        </Bouton>
      </form>

      {#if cherchee}
        <p class="text-xs text-stone-500 dark:text-stone-400">
          {resultats.length} résultat(s) pour « {cherchee} »
        </p>
      {/if}

      {#if resultats.length}
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead class="text-xs uppercase text-stone-500 dark:text-stone-400">
              <tr>
                <th class="py-1 pr-3">Personne</th>
                <th class="py-1 pr-3">Identifiant</th>
                <th class="py-1 pr-3">Base</th>
                <th class="py-1 pr-3">Relu le</th>
                <th class="py-1">Mot de passe</th>
              </tr>
            </thead>
            <tbody>
              {#each resultats as s (s.personne_id + "/" + s.cible + "/" + (s.site ?? ""))}
                <tr class="border-t border-stone-200 dark:border-stone-700">
                  <td class="py-1.5 pr-3">
                    {s.nom} {s.prenom}
                    {#if s.classe}
                      <span class="ml-1 text-xs text-stone-500 dark:text-stone-400">{s.classe}</span>
                    {/if}
                  </td>
                  <td class="py-1.5 pr-3 font-mono text-xs">
                    {s.identifiant ?? s.login ?? "—"}
                    {#if s.identifiant && s.login && s.identifiant !== s.login}
                      <!-- Saisi à la main dans Charlemagne : il peut différer
                           du référentiel, et c'est avec lui que ce mot de
                           passe va. -->
                      <span class="ml-1 font-sans text-stone-400" title="L'identifiant du référentiel">
                        (référentiel : {s.login})
                      </span>
                    {/if}
                  </td>
                  <td class="py-1.5 pr-3 text-xs text-stone-500 dark:text-stone-400">
                    {#if s.cible === "charlemagne"}
                      <span title="Tel que Charlemagne le garde. S'il diffère de KoXo, le relevé le plus récent passe devant — et l'écart se règle à la source.">
                        Charlemagne
                      </span>
                    {:else}
                      {s.site ?? "—"}
                    {/if}
                    {#if s.origine === "genere"}
                      <span class="ml-1" title="Fabriqué par le programme : il n'existe nulle part ailleurs">·&nbsp;généré</span>
                    {/if}
                  </td>
                  <td class="py-1.5 pr-3 text-xs tabular-nums text-stone-500 dark:text-stone-400">
                    {jour(s.releve_le)}
                  </td>
                  <td class="py-1.5">
                    <span class="inline-flex flex-wrap items-center gap-2">
                      <button
                        class="group inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 font-mono hover:bg-stone-100 dark:hover:bg-stone-700/50
                               {s.ecart && !s.retenu && !s.autre_base && !s.a_relire ? 'text-stone-400 line-through dark:text-stone-500' : ''}"
                        onclick={() => copier(s.mot_de_passe)}
                        title="Copier"
                      >
                        {s.mot_de_passe}
                        <Copy class="h-3 w-3 text-stone-400 opacity-0 transition group-hover:opacity-100" />
                      </button>
                      <!-- KoXo fait foi. Contredit par une source lue après
                           lui, son relevé est peut-être dépassé : à relire. -->
                      {#if s.autre_base}
                        <Pastille etat="inconnu" texte="autre base" />
                      {:else if s.a_relire && s.cible === "koxo"}
                        <Pastille etat="ecart" texte="à relire dans KoXo" />
                      {:else if s.a_relire}
                        <Pastille etat="attente" texte="lu après KoXo" />
                      {:else if s.ecart && s.retenu}
                        <Pastille etat="pret" texte="KoXo fait foi" />
                      {:else if s.ecart}
                        <Pastille etat="ecart" texte="diffère de KoXo" />
                      {/if}
                    </span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>

    <!-- Les écarts entre sources -->
    <div class="card space-y-3 p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Mots de passe qui ne concordent pas
        </h2>
        <Bouton taille="sm" icon={GitCompare} occupe={comparaison} onclick={comparer}>Comparer</Bouton>
      </div>
      <p class="text-sm text-stone-600 dark:text-stone-400">
        KoXo est <strong>le</strong> mot de passe ; Charlemagne en garde une
        copie. Mais le coffre ne garde que ce que chacun disait le jour où on
        l'a lu. Quand Charlemagne a été lu <em>après</em> KoXo et dit autre
        chose, KoXo a peut-être changé : rien ne s'imprime pour cet élève
        tant qu'on n'a pas reversé un export KoXo récent ci-dessous. Lu le
        même jour ou après, KoXo l'emporte — et c'est Charlemagne qu'il faut
        corriger (la Cohérence en fabrique le fichier).
      </p>
      {#if ecarts}
        <p class="text-xs tabular-nums text-stone-500 dark:text-stone-400">
          {#each Object.entries(ecarts.releves_koxo) as [base, quand], i (base)}
            {i ? " · " : ""}KoXo {base} relu le <b class="text-stone-700 dark:text-stone-300">{jour(quand)}</b>
          {/each}
        </p>
        {#if ecarts.ecarts.length}
          <p class="text-sm font-medium text-red-800 dark:text-red-300">
            {ecarts.ecarts.length} personne(s) avec deux mots de passe différents
          </p>
          <div class="max-h-80 overflow-auto">
            <table class="w-full text-left text-sm">
              <thead class="text-xs uppercase text-stone-500 dark:text-stone-400">
                <tr>
                  <th class="py-1 pr-3">Personne</th>
                  <th class="py-1 pr-3">KoXo</th>
                  <th class="py-1">Ce qui diffère</th>
                </tr>
              </thead>
              <tbody>
                {#each ecarts.ecarts as e (e.personne_id)}
                  <tr class="border-t border-stone-200 dark:border-stone-700">
                    <td class="py-1.5 pr-3">
                      {e.nom} {e.prenom}
                      <span class="ml-1 text-xs text-stone-500 dark:text-stone-400">{[e.site, e.classe].filter(Boolean).join(" · ")}</span>
                    </td>
                    {#each [e.sources.filter((s) => s.retenu), e.sources.filter((s) => !s.retenu)] as groupe, i (i)}
                      <td class="py-1.5 pr-3 text-xs {i ? 'text-red-700 dark:text-red-400' : 'text-stone-600 dark:text-stone-300'}">
                        {groupe.map((s) => `${nomSource(s)}, relu le ${jour(s.releve_le)}`).join(" · ")}
                        {#if !i}
                          <span class="block font-semibold {e.a_relire ? 'text-red-700 dark:text-red-400' : 'text-vert-700 dark:text-vert-300'}">
                            {e.a_relire ? "à relire dans KoXo — rien ne s'imprime" : "fait foi — corriger Charlemagne"}
                          </span>
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <p class="text-sm text-vert-800 dark:text-vert-300">
            Toutes les sources concordent : un seul mot de passe par personne.
          </p>
        {/if}
      {/if}
    </div>

    <!-- Google : on lit qui a changé son mot de passe, on impose sur clic. -->
    <MotsDePasseGoogle />

    <!-- Verser un export KoXo -->
    <div class="card space-y-3 p-4">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
        Verser un export KoXo
      </h2>
      <p class="text-sm text-stone-600 dark:text-stone-400">
        Range dans le coffre les mots de passe d'un export KoXo, rapprochés
        par identifiant. Désigne la base d'où vient le fichier : un
        professeur peut avoir un mot de passe différent dans chacune.
      </p>
      <div class="flex flex-wrap items-end gap-2">
        <label class="block">
          <span class="libelle-champ">Base</span>
          <select class="champ w-40" bind:value={siteVersement}>
            <option value={null}>Non précisée</option>
            {#each listeSites as s (s.id)}<option value={s.nom}>{s.nom}</option>{/each}
          </select>
        </label>
        <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
          <Upload class="h-4 w-4" />
          {fichierKoxo?.name ?? "Choisir le CSV KoXo"}
          <input type="file" accept=".csv,.CSV" class="hidden"
                 onchange={(e) => (fichierKoxo = e.target.files?.[0] ?? null)} />
        </label>
        <Bouton variante="primary" {occupe} disabled={!fichierKoxo} onclick={verser}>
          Verser
        </Bouton>
      </div>
      <p class="text-xs text-stone-500 dark:text-stone-400">
        Le fichier ne quitte pas la machine et n'est pas conservé : seuls
        les mots de passe sont rangés, chiffrés. À refaire après tout
        changement de mot de passe dans KoXo — la Cohérence le fait aussi
        quand on lui dépose un export avec les mots de passe.
      </p>
      {#if dernierVersement?.changes?.length}
        <details class="rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-sm dark:border-amber-800 dark:bg-amber-950/40">
          <summary class="cursor-pointer font-medium text-amber-900 dark:text-amber-200">
            {dernierVersement.changes.length} mot(s) de passe avaient changé dans KoXo
            {dernierVersement.precedent_releve ? `depuis le relevé du ${jour(dernierVersement.precedent_releve)}` : ""}
          </summary>
          <p class="mt-1.5 text-xs text-amber-900 dark:text-amber-200">
            Le coffre est maintenant à jour pour eux. Une étiquette imprimée
            avant ce versement peut porter l'ancien.
          </p>
          <p class="mt-1.5 text-xs text-stone-600 dark:text-stone-400">{dernierVersement.changes.join(" · ")}</p>
        </details>
      {/if}
    </div>
  {/if}
</section>
