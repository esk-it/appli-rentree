<script>
  import { onMount } from "svelte";
  import Activity from "@lucide/svelte/icons/activity";
  import Clock from "@lucide/svelte/icons/clock";
  import Trash2 from "@lucide/svelte/icons/trash-2";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import LogOut from "@lucide/svelte/icons/log-out";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Nombre from "$lib/components/Nombre.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import { annees, suivi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let stats = $state(/** @type {null | any} */ (null));
  let purges = $state([]);
  let etatChoisi = $state("actif");
  let liste = $state([]);
  let chargement = $state(false);
  let erreur = $state("");

  // Actions de cycle de vie
  let listeAnnees = $state([]);
  let cibleAction = $state("koxo_ndk");
  let anneeSourceId = $state(/** @type {null | number} */ (null));
  let anneeCibleId = $state(/** @type {null | number} */ (null));
  let actionEnCours = $state(false);

  const ETATS = ["prevu", "cree", "actif", "quarantaine", "purge"];
  const CIBLES = [
    "google", "koxo_ndk", "koxo_su", "pmb_ndk", "pmb_su", "jpm", "cardstudio",
  ];

  onMount(async () => {
    await charger();
    try {
      listeAnnees = await annees.lister();
      if (listeAnnees.length >= 2) {
        anneeCibleId = listeAnnees[0].id;
        anneeSourceId = listeAnnees[1].id;
      }
    } catch (e) {
      erreur = String(e);
    }
  });

  async function confirmerCreation() {
    actionEnCours = true;
    try {
      const r = await suivi.confirmerCreation({ cible: cibleAction });
      notify.succes(`${r.nb_transitions} compte(s) passé(s) en « créé »`);
      await charger();
    } catch (e) {
      notify.erreur(String(e));
    } finally {
      actionEnCours = false;
    }
  }

  async function activerComptes() {
    actionEnCours = true;
    try {
      const r = await suivi.activer({ cible: cibleAction });
      notify.succes(`${r.nb_transitions} compte(s) passé(s) en « actif »`);
      await charger();
    } catch (e) {
      notify.erreur(String(e));
    } finally {
      actionEnCours = false;
    }
  }

  // Purge en deux temps : la confirmation est un écran à part entière,
  // pas une case cochée d'avance.
  let confirmationPurge = $state(false);

  async function confirmerPurge() {
    actionEnCours = true;
    try {
      const r = await suivi.purger({});
      notify.succes(`${r.nb_transitions} compte(s) marqué(s) comme purgé(s)`);
      if (r.erreurs.length > 0) {
        notify.avertissement(`${r.erreurs.length} compte(s) refusé(s)`);
      }
      confirmationPurge = false;
      await charger();
    } catch (e) {
      notify.erreur(String(e));
    } finally {
      actionEnCours = false;
    }
  }

  async function traiterSortants() {
    if (!anneeSourceId || !anneeCibleId) return;
    if (anneeSourceId === anneeCibleId) {
      notify.avertissement("Sélectionne deux années différentes");
      return;
    }
    actionEnCours = true;
    try {
      const r = await suivi.traiterSortants({ anneeSourceId, anneeCibleId });
      notify.succes(
        `${r.nb_transitions} compte(s) sortis — Google en quarantaine, autres purgés`,
      );
      await charger();
    } catch (e) {
      notify.erreur(String(e));
    } finally {
      actionEnCours = false;
    }
  }

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      [stats, purges, liste] = await Promise.all([
        suivi.stats(),
        suivi.purgesEchues(),
        suivi.lister({ etat: etatChoisi }),
      ]);
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  async function rafraichirListe() {
    try {
      liste = await suivi.lister({ etat: etatChoisi });
    } catch (err) {
      notify.erreur(String(err));
    }
  }

  function formaterDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("fr-FR");
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Suivi des comptes
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Cycle de vie de chaque compte cible : <code>prévu → créé → actif → quarantaine → purge</code>.
      Google passe par une quarantaine de 18 mois avant purge ; les autres cibles sont
      supprimées immédiatement à la sortie.
    </p>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if stats}
    <!-- Cards totaux par état -->
    <div class="grid grid-cols-2 gap-3 md:grid-cols-5">
      {#each ETATS as e}
        <div class="card anim-apparition p-3">
          <p class="text-xs uppercase tracking-wide text-stone-500">{e}</p>
          <p class="text-2xl font-semibold">
            <Nombre valeur={stats.total_par_etat[e] ?? 0} />
          </p>
        </div>
      {/each}
    </div>

    <!-- Purges échues -->
    {#if stats.nb_purges_echues > 0}
      <div class="card border-red-200 bg-red-50/50 p-4 dark:border-red-800 dark:bg-red-900/20">
        <div class="flex items-start gap-3">
          <Trash2 class="mt-0.5 h-5 w-5 text-red-700 dark:text-red-400" />
          <div class="flex-1">
            <p class="font-medium text-red-900 dark:text-red-200">
              {stats.nb_purges_echues} compte(s) en quarantaine avec date de purge échue
            </p>
            <p class="mt-1 text-sm text-stone-700 dark:text-stone-300">
              Leur quarantaine est terminée : tu peux les supprimer dans la
              console de chaque cible. Une fois que c'est fait, enregistre-le
              ici pour que le référentiel reflète la réalité.
            </p>

            {#if !confirmationPurge}
              <button
                class="btn-secondary mt-2 text-xs"
                onclick={() => (confirmationPurge = true)}
                disabled={actionEnCours}
              >
                <Trash2 class="h-3.5 w-3.5" />
                Enregistrer la purge
              </button>
            {:else}
              <div class="mt-2 rounded-lg border border-red-300 bg-white p-3 dark:border-red-700 dark:bg-stone-900">
                <p class="text-sm font-medium text-red-900 dark:text-red-200">
                  Confirmer la purge de {purges.length} compte(s) ?
                </p>
                <p class="mt-1 text-xs text-stone-600 dark:text-stone-400">
                  Cette action <strong>ne supprime rien</strong> dans Google, KoXo
                  ou les autres cibles — le programme n'y touche jamais. Elle
                  enregistre que tu as effectué la suppression de ton côté. Les
                  <code>Personne</code> du référentiel sont conservées, seul l'état
                  du compte cible passe à <code>purge</code>.
                </p>
                <div class="mt-2 flex gap-2">
                  <button class="btn-primary text-xs" onclick={confirmerPurge} disabled={actionEnCours}>
                    Oui, c'est fait côté cible
                  </button>
                  <button
                    class="btn-secondary text-xs"
                    onclick={() => (confirmationPurge = false)}
                    disabled={actionEnCours}
                  >
                    Annuler
                  </button>
                </div>
              </div>
            {/if}

            <details class="mt-2">
              <summary class="cursor-pointer text-xs text-red-700 dark:text-red-400">
                Voir la liste ({purges.length})
              </summary>
              <ul class="mt-2 space-y-1 text-xs">
                {#each purges.slice(0, 20) as l}
                  <li>
                    <code>{l.login}</code> — {l.prenom} {l.nom} · {l.cible} · purge prévue {formaterDate(l.date_prevue_purge)}
                  </li>
                {/each}
              </ul>
            </details>
          </div>
        </div>
      </div>
    {/if}

    <!-- Actions de cycle de vie -->
    <div class="card p-4 space-y-4">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
        Faire avancer les comptes
      </h2>

      <div class="rounded-lg border border-stone-200 bg-stone-50 p-3 dark:border-stone-700 dark:bg-stone-800">
        <p class="text-xs text-stone-600 dark:text-stone-400 mb-3">
          Après avoir importé un fichier dans une cible, confirme-le ici pour
          faire avancer l'état des comptes. Aucune action n'est envoyée au
          système tiers — seul l'état du référentiel change.
        </p>
        <div class="flex flex-wrap items-end gap-2">
          <label class="block">
            <span class="text-xs font-medium uppercase tracking-wide text-stone-500">Cible</span>
            <select
              bind:value={cibleAction}
              class="mt-1 rounded-lg border border-stone-300 px-3 py-1.5 text-sm dark:border-stone-600 dark:bg-stone-800"
            >
              {#each CIBLES as c (c)}
                <option value={c}>{c}</option>
              {/each}
            </select>
          </label>
          <button class="btn-secondary" onclick={confirmerCreation} disabled={actionEnCours}>
            <CheckCircle2 class="h-4 w-4" />
            prévu → créé
          </button>
          <button class="btn-secondary" onclick={activerComptes} disabled={actionEnCours}>
            <Activity class="h-4 w-4" />
            créé → actif
          </button>
        </div>
      </div>

      <div class="rounded-lg border border-amber-200 bg-amber-50/50 p-3 dark:border-amber-800 dark:bg-amber-900/20">
        <p class="text-xs text-stone-700 dark:text-stone-300 mb-3">
          <strong>Traiter les sortants</strong> — applique la politique de sortie à
          toutes les personnes présentes à l'année source mais absentes de la cible.
          Google part en <strong>quarantaine 18 mois</strong>, les autres cibles en
          purge immédiate.
        </p>
        <div class="flex flex-wrap items-end gap-2">
          <label class="block">
            <span class="text-xs font-medium uppercase tracking-wide text-stone-500">Année source</span>
            <select
              bind:value={anneeSourceId}
              class="mt-1 rounded-lg border border-stone-300 px-3 py-1.5 text-sm dark:border-stone-600 dark:bg-stone-800"
            >
              <option value={null}>—</option>
              {#each listeAnnees as a (a.id)}
                <option value={a.id}>{a.libelle}</option>
              {/each}
            </select>
          </label>
          <label class="block">
            <span class="text-xs font-medium uppercase tracking-wide text-stone-500">Année cible</span>
            <select
              bind:value={anneeCibleId}
              class="mt-1 rounded-lg border border-stone-300 px-3 py-1.5 text-sm dark:border-stone-600 dark:bg-stone-800"
            >
              <option value={null}>—</option>
              {#each listeAnnees as a (a.id)}
                <option value={a.id}>{a.libelle}</option>
              {/each}
            </select>
          </label>
          <button
            class="btn-secondary"
            onclick={traiterSortants}
            disabled={actionEnCours || !anneeSourceId || !anneeCibleId}
          >
            <LogOut class="h-4 w-4" />
            Traiter les sortants
          </button>
        </div>
      </div>
    </div>

    <!-- Détail par cible × état -->
    <div class="card p-4">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400 mb-3">
        Répartition par cible × état
      </h2>
      <div class="overflow-hidden rounded-lg border border-stone-200 dark:border-stone-700">
        <table class="min-w-full divide-y divide-stone-200 text-sm dark:divide-stone-700">
          <thead class="bg-stone-50 text-xs uppercase tracking-wide text-stone-500 dark:bg-stone-800">
            <tr>
              <th class="px-3 py-2 text-left">Cible</th>
              {#each ETATS as e}
                <th class="px-3 py-2 text-right">{e}</th>
              {/each}
            </tr>
          </thead>
          <tbody class="divide-y divide-stone-100 dark:divide-stone-800">
            {#each Object.entries(stats.par_cible) as [cible, valeurs]}
              <tr class="hover:bg-stone-50 dark:hover:bg-stone-800/50">
                <td class="px-3 py-1.5 font-mono text-xs">{cible}</td>
                {#each ETATS as e}
                  <td class="px-3 py-1.5 text-right tabular-nums {valeurs[e] > 0 ? '' : 'text-stone-300'}">
                    {valeurs[e] ?? 0}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Liste filtrée par état -->
    <div class="card p-4">
      <div class="flex items-center gap-2 mb-3">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Comptes en état
        </h2>
        <Segments
          bind:valeur={etatChoisi}
          taille="sm"
          onChange={rafraichirListe}
          options={ETATS.map((e) => ({
            id: e,
            label: e,
            badge: stats?.total_par_etat?.[e] ?? 0,
          }))}
        />
      </div>

      {#if liste.length === 0}
        <EtatVide
          titre="Aucun compte dans cet état"
          message="Rien n'est actuellement en « {etatChoisi} ». Les comptes apparaissent ici dès qu'un export « Nouveaux » est généré avec le suivi activé."
        />
      {:else}
        <div class="overflow-hidden rounded-lg border border-stone-200 dark:border-stone-700">
          <table class="min-w-full divide-y divide-stone-200 text-sm dark:divide-stone-700">
            <thead class="bg-stone-50 text-xs uppercase tracking-wide text-stone-500 dark:bg-stone-800">
              <tr>
                <th class="px-3 py-2 text-left">Personne</th>
                <th class="px-3 py-2 text-left">Login</th>
                <th class="px-3 py-2 text-left">Site</th>
                <th class="px-3 py-2 text-left">Cible</th>
                <th class="px-3 py-2 text-left">Purge prévue</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-stone-100 dark:divide-stone-800">
              {#each liste as l (l.id)}
                <tr class="hover:bg-stone-50 dark:hover:bg-stone-800/50">
                  <td class="px-3 py-1.5">
                    <div>{l.nom} {l.prenom}</div>
                    <div class="text-xs text-stone-500 font-mono">{l.cle_pivot}</div>
                  </td>
                  <td class="px-3 py-1.5 font-mono text-xs">{l.login}</td>
                  <td class="px-3 py-1.5 text-stone-600 dark:text-stone-400">{l.site_nom ?? "—"}</td>
                  <td class="px-3 py-1.5 font-mono text-xs">{l.cible}</td>
                  <td class="px-3 py-1.5 text-xs text-stone-500">{formaterDate(l.date_prevue_purge)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</section>
