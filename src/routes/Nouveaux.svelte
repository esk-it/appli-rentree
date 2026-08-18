<script>
  import { onMount } from "svelte";
  import UserPlus from "@lucide/svelte/icons/user-plus";
  import Printer from "@lucide/svelte/icons/printer";
  import Download from "@lucide/svelte/icons/download";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Nombre from "$lib/components/Nombre.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { annees, nouveaux, sites, telechargerFichierBase64 } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let listeSites = $state(/** @type {any[]} */ ([]));

  let anneeId = $state(/** @type {number | null} */ (null));
  let anneeSourceId = $state(/** @type {number | null} */ (null));
  let filtreSite = $state("");
  let filtreType = $state("");
  let filtreStatut = $state("");

  let rapport = $state(/** @type {any} */ (null));
  let chargement = $state(true);
  let erreur = $state("");
  let telechargement = $state(false);

  let arrivantsAffiches = $derived.by(() => {
    if (!rapport) return [];
    let r = rapport.arrivants;
    if (filtreStatut) r = r.filter((a) => a.statut === filtreStatut);
    return r;
  });

  // Regroupement par classe : c'est ainsi qu'un collègue relit une liste —
  // classe par classe, pas dans un tableau de 400 lignes d'affilée.
  let parClasse = $derived.by(() => {
    /** @type {Map<string, any[]>} */
    const m = new Map();
    for (const a of arrivantsAffiches) {
      const cle = `${a.site ?? "sans site"} · ${a.classe ?? "sans classe"}`;
      if (!m.has(cle)) m.set(cle, []);
      m.get(cle).push(a);
    }
    return [...m.entries()];
  });

  let optionsStatut = $derived([
    { id: "", label: "Tous", badge: rapport?.nb_total ?? 0 },
    { id: "nouveau", label: "Nouveaux", badge: rapport?.nb_nouveaux ?? 0 },
    { id: "a_verifier", label: "À vérifier", badge: rapport?.nb_a_verifier ?? 0 },
  ]);

  onMount(async () => {
    try {
      [listeAnnees, listeSites] = await Promise.all([annees.lister(), sites.lister()]);
      // L'année la plus récente est celle qu'on prépare.
      const triees = [...listeAnnees].sort((a, b) => b.libelle.localeCompare(a.libelle));
      anneeId = triees[0]?.id ?? null;
      if (triees.length > 1) anneeSourceId = triees[1].id;
    } catch (e) {
      erreur = String(e);
    }
    await rafraichir();
  });

  async function rafraichir() {
    if (!anneeId) {
      chargement = false;
      return;
    }
    chargement = true;
    erreur = "";
    try {
      rapport = await nouveaux.lister({
        anneeId,
        siteId: filtreSite || null,
        type: filtreType || null,
        anneeSourceId: anneeSourceId || null,
      });
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
      rapport = null;
    } finally {
      chargement = false;
    }
  }

  async function telechargerCsv() {
    telechargement = true;
    try {
      const r = await nouveaux.csv({
        anneeId,
        siteId: filtreSite || null,
        type: filtreType || null,
        anneeSourceId: anneeSourceId || null,
      });
      telechargerFichierBase64(r.nom_fichier, r.contenu_base64, "text/csv");
      notify.succes(`${r.nb_lignes} ligne(s) exportée(s)`);
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      telechargement = false;
    }
  }

  let libelleAnnee = $derived(
    listeAnnees.find((a) => a.id === anneeId)?.libelle ?? "",
  );
</script>

<section class="space-y-4">
  <div class="sans-impression">
    <EnTetePage
      icon={UserPlus}
      titre="Nouveaux arrivants"
      description="Les personnes pour lesquelles un compte reste à créer. Liste faite pour être imprimée et relue par un collègue avant de générer quoi que ce soit."
    />
  </div>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  <div class="card p-3 sans-impression">
    <div class="flex flex-wrap items-end gap-3">
      <div>
        <label class="libelle-champ" for="an-cible">Année préparée</label>
        <select id="an-cible" class="champ w-44" bind:value={anneeId} onchange={rafraichir}>
          {#each listeAnnees as a (a.id)}
            <option value={a.id}>{a.libelle}</option>
          {/each}
        </select>
      </div>

      <div>
        <label class="libelle-champ" for="an-source">Comparée à</label>
        <select id="an-source" class="champ w-44" bind:value={anneeSourceId} onchange={rafraichir}>
          <option value={null}>— aucune —</option>
          {#each listeAnnees.filter((a) => a.id !== anneeId) as a (a.id)}
            <option value={a.id}>{a.libelle}</option>
          {/each}
        </select>
      </div>

      <div>
        <label class="libelle-champ" for="f-site">Site</label>
        <select id="f-site" class="champ w-36" bind:value={filtreSite} onchange={rafraichir}>
          <option value="">Tous</option>
          {#each listeSites as s (s.id)}
            <option value={s.id}>{s.nom}</option>
          {/each}
        </select>
      </div>

      <div>
        <label class="libelle-champ" for="f-type">Population</label>
        <select id="f-type" class="champ w-36" bind:value={filtreType} onchange={rafraichir}>
          <option value="">Toutes</option>
          <option value="eleve">Élèves</option>
          <option value="adulte">Adultes</option>
        </select>
      </div>

      <div class="ml-auto flex gap-2">
        <Bouton icon={Printer} onclick={() => window.print()}>Imprimer</Bouton>
        <Bouton
          variante="primary"
          icon={Download}
          occupe={telechargement}
          disabled={!rapport || rapport.nb_total === 0}
          onclick={telechargerCsv}
        >
          Export Excel
        </Bouton>
      </div>
    </div>

    {#if !anneeSourceId}
      <p class="mt-3 border-t border-stone-100 pt-2 text-xs text-stone-500 dark:border-stone-800 dark:text-stone-400">
        Sans année de référence, un arrivant est reconnu au croisement de deux
        signaux : aucun compte existant, et aucune classe l'an dernier selon
        Charlemagne. Quand ces deux signaux se contredisent, la personne est
        listée « à vérifier » plutôt que tranchée d'office.
      </p>
    {/if}
  </div>

  {#if rapport && rapport.nb_total > 0}
    <div class="card p-3 sans-impression">
      <Segments bind:valeur={filtreStatut} taille="sm" options={optionsStatut} />
    </div>
  {/if}

  <!-- En-tête d'impression : à l'écran la barre de filtres suffit, sur papier
       il faut savoir de quelle année et de quel périmètre parle la feuille. -->
  <div class="impression-seule mb-3">
    <h1 class="text-lg font-bold">Nouveaux arrivants — {libelleAnnee}</h1>
    <p class="text-xs">
      {rapport?.nb_total ?? 0} personne(s) · {rapport?.nb_nouveaux ?? 0} nouveaux ·
      {rapport?.nb_a_verifier ?? 0} à vérifier
      {#if rapport?.annee_source_libelle}
        · comparé à {rapport.annee_source_libelle}
      {/if}
    </p>
  </div>

  {#if chargement}
    <div class="card p-4">
      <Squelette variante="ligne-tableau" nb={8} colonnes={7} />
    </div>
  {:else if !anneeId}
    <div class="card p-4">
      <EtatVide
        icon={UserPlus}
        titre="Aucune année ingérée"
        message="Dépose d'abord un export Charlemagne dans l'onglet Snapshots d'années."
      />
    </div>
  {:else if !rapport || rapport.nb_total === 0}
    <div class="card p-4">
      <EtatVide
        icon={UserPlus}
        titre="Aucun nouvel arrivant"
        message="Toutes les personnes de cette année ont déjà un compte et une scolarité l'an dernier."
      />
    </div>
  {:else}
    <div class="space-y-4">
      {#each parClasse as [groupe, membres] (groupe)}
        <div class="card overflow-hidden groupe-impression">
          <div class="flex items-baseline justify-between bg-stone-100 px-3 py-1.5 dark:bg-stone-800">
            <h2 class="text-sm font-semibold">{groupe}</h2>
            <span class="text-xs tabular-nums text-stone-500 dark:text-stone-400">
              {membres.length}
            </span>
          </div>
          <table class="tableau w-full text-sm">
            <thead>
              <tr>
                <th class="text-left">Nom</th>
                <th class="text-left">Prénom</th>
                <th class="text-left">Identifiant</th>
                <th class="text-left">Adresse mail</th>
                <th class="text-right">Badge</th>
                <th class="text-left">Régime</th>
                <th class="text-left">Constat</th>
              </tr>
            </thead>
            <tbody>
              {#each membres as a (a.personne_id)}
                <tr class:ligne-douteuse={a.statut === "a_verifier"}>
                  <td class="whitespace-nowrap font-medium">{a.nom}</td>
                  <td class="whitespace-nowrap">{a.prenom}</td>
                  <td class="whitespace-nowrap font-mono text-xs">{a.login}</td>
                  <td class="whitespace-nowrap font-mono text-xs">{a.email ?? "—"}</td>
                  <td class="text-right tabular-nums">{a.badge}</td>
                  <td>{a.regime ?? "—"}</td>
                  <td class="text-xs">
                    {#if a.statut === "a_verifier"}
                      <span class="inline-flex items-center gap-1 text-amber-700 dark:text-amber-400">
                        <TriangleAlert class="h-3 w-3 shrink-0" />
                        {a.motif}
                      </span>
                    {:else}
                      <span class="text-stone-400 dark:text-stone-500">{a.motif}</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/each}

      <p class="impression-seule mt-4 text-xs">
        Vérifié par ……………………………………  le ……… / ……… / ………
      </p>
    </div>
  {/if}
</section>
