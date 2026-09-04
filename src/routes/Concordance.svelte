<script>
  /**
   * Ce que chaque source dit de la classe d'un élève, côte à côte.
   *
   * ## Pourquoi cet écran existe
   *
   * Quatre systèmes portent la classe d'un élève, et chacun l'apprend à un
   * moment différent : Charlemagne quand la vie scolaire l'y saisit, le
   * référentiel à l'ingestion, Google à la bascule, KoXo à la
   * synchronisation. Rien ne les montrait ensemble — le bilan comparait le
   * référentiel à Google, le contrôle KoXo comparait KoXo au référentiel,
   * et Charlemagne n'entrait que par l'ingestion.
   *
   * Résultat à la rentrée 2026 : quarante-quatre élèves avaient changé de
   * classe dans Charlemagne après le premier import, et personne ne l'a vu
   * pendant deux semaines.
   *
   * ## Charlemagne fait foi, mais ne décide pas
   *
   * C'est la source administrative : l'écran propose de tout aligner
   * dessus. Mais chaque ligne se décoche, parce que l'utilisateur sait des
   * choses que Charlemagne ignore encore — une élève y était donnée en 2_4
   * alors qu'elle suivait en 2_5.
   *
   * ## La correction ne s'écrit pas ici
   *
   * Elle passe par le changement de classe, qui sait déjà déplacer l'unité
   * et échanger les groupes en un geste, et qui journalise. Avec
   * `reprise`, il accepte que le référentiel soit déjà à jour et ne
   * corrige que Google — c'est exactement le cas qu'on traite.
   */
  import { onMount } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import GitCompare from "@lucide/svelte/icons/git-compare";
  import Upload from "@lucide/svelte/icons/upload";
  import Search from "@lucide/svelte/icons/search";
  import Wand2 from "@lucide/svelte/icons/wand-2";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import StatCard from "$lib/components/StatCard.svelte";
  import {
    annees as anneesApi,
    concordance as concordanceApi,
    mouvementsApi,
  } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));
  let fichier = $state(/** @type {File | null} */ (null));
  /** Un export par base : KoXo a un serveur par établissement. */
  let fichiersKoxo = $state(/** @type {File[]} */ ([]));
  let rapport = $state(/** @type {any} */ (null));
  let occupe = $state(false);
  let chargement = $state(true);

  /** Les lignes qu'on va aligner. Cochées par défaut — Charlemagne fait foi. */
  let retenues = $state(new SvelteSet());
  let application = $state(/** @type {null | any} */ (null));

  const LIBELLES = {
    referentiel: "Référentiel en retard",
    google: "Google en retard",
    groupe: "Groupe d'une autre classe",
    koxo: "KoXo en retard",
    sans_compte: "Sans compte Google",
    hors_arbre_de_classe: "Compte pas encore basculé",
    absent_referentiel: "Inconnu du référentiel",
    absent_koxo: "Absent de la base KoXo",
  };

  /** Ce qu'un changement de classe ne peut pas réparer. */
  const HORS_PORTEE = new Set(["sans_compte", "absent_referentiel", "absent_koxo"]);

  onMount(async () => {
    try {
      const a = await anneesApi.lister();
      listeAnnees = a;
      const triees = [...a].sort((x, y) => y.libelle.localeCompare(x.libelle));
      anneeId = triees[0]?.id ?? null;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      chargement = false;
    }
  });

  let corrigeables = $derived(
    (rapport?.lignes ?? []).filter(
      (l) => l.personne_id && !l.genres.every((g) => HORS_PORTEE.has(g)),
    ),
  );

  async function croiser() {
    if (!fichier || !anneeId) return;
    occupe = true;
    rapport = null;
    application = null;
    try {
      rapport = await concordanceApi.croiser({ fichier, anneeId, fichiersKoxo });
      retenues.clear();
      for (const l of rapport.lignes) {
        if (l.personne_id && !l.genres.every((g) => HORS_PORTEE.has(g))) {
          retenues.add(l.personne_id);
        }
      }
      for (const a of rapport.avertissements ?? []) notify.avertissement(a, { duree: 9000 });
      notify.succes(
        `${rapport.nb_accord} d'accord, ${rapport.nb_a_corriger} à corriger`,
        { duree: 8000 },
      );
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  function basculer(id) {
    if (retenues.has(id)) retenues.delete(id);
    else retenues.add(id);
  }

  function toutCocher() {
    if (retenues.size === corrigeables.length) retenues.clear();
    else for (const l of corrigeables) retenues.add(l.personne_id);
  }

  /**
   * Aligne les lignes retenues : référentiel, unité, groupes.
   *
   * `reprise` est vrai parce que le référentiel est souvent déjà à jour —
   * c'est Google qui est en retard. Sans lui, le changement serait refusé
   * pour la raison même qui prouve que la moitié du travail est faite.
   */
  async function aligner() {
    if (!retenues.size || !anneeId) return;
    const lignes = (rapport?.lignes ?? []).filter((l) => retenues.has(l.personne_id));
    if (
      !confirm(
        `Aligner ${lignes.length} élève(s) sur Charlemagne ?\n\n` +
          "Le référentiel, l'unité d'organisation et les groupes Google " +
          "seront mis à jour. KoXo n'est pas touché : il se synchronise " +
          "depuis un fichier, que tu généreras ensuite.",
      )
    ) {
      return;
    }
    occupe = true;
    application = { total: lignes.length, faits: 0, echecs: [] };
    try {
      for (const l of lignes) {
        try {
          const r = await mouvementsApi.changerClasse({
            personneId: l.personne_id,
            nouvelleClasse: l.propose,
            anneeId,
            mode: "reel",
            reprise: true,
            appliquerGoogle: true,
          });
          const rates = (r.operations ?? []).filter((o) => !o.reussie);
          if (rates.length) {
            application.echecs.push({
              nom: `${l.prenom} ${l.nom}`,
              message: rates.map((o) => o.message).join(" · "),
            });
          } else {
            retenues.delete(l.personne_id);
          }
        } catch (e) {
          application.echecs.push({
            nom: `${l.prenom} ${l.nom}`,
            message: String(e).replace(/^Error:\s*/, "").slice(0, 160),
          });
        }
        application.faits += 1;
      }
      const ok = application.total - application.echecs.length;
      if (application.echecs.length) {
        notify.avertissement(
          `${ok} aligné(s), ${application.echecs.length} en échec — voir le détail`,
          { duree: 12000 },
        );
      } else {
        notify.succes(`${ok} élève(s) alignés. Relance le croisement pour vérifier.`,
                      { duree: 9000 });
      }
    } finally {
      occupe = false;
    }
  }
</script>

<section class="space-y-5">
  <EnTetePage
    icon={GitCompare}
    titre="Concordance des sources"
    description="Charlemagne, le référentiel, Google et KoXo côte à côte. Charlemagne fait foi par défaut — décoche ce que tu sais faux. La correction aligne le référentiel, l'unité et les groupes en un geste ; le fichier KoXo se génère ensuite depuis Exports."
  />

  {#if chargement}
    <p class="text-sm text-stone-500 dark:text-stone-400">Chargement…</p>
  {:else}
    <div class="card space-y-3 p-4">
      <div class="flex flex-wrap items-end gap-3">
        <label class="block">
          <span class="libelle-champ">Année</span>
          <select class="champ w-40" bind:value={anneeId} onchange={() => (rapport = null)}>
            {#each listeAnnees as a (a.id)}<option value={a.id}>{a.libelle}</option>{/each}
          </select>
        </label>

        <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 text-xs text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
          <Upload class="h-3.5 w-3.5" />
          {fichier?.name ?? "Export Charlemagne (obligatoire)"}
          <input
            type="file"
            accept=".csv,.htm,.html,.xlsx"
            onchange={(e) => {
              const champ = /** @type {HTMLInputElement} */ (e.target);
              fichier = champ.files?.[0] ?? null;
              rapport = null;
            }}
            class="hidden"
          />
        </label>

        <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 text-xs text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
          <Upload class="h-3.5 w-3.5" />
          {fichiersKoxo.length === 0
            ? "Exports KoXo (une base par fichier)"
            : fichiersKoxo.map((f) => f.name).join(" + ")}
          <input
            type="file"
            accept=".csv,.xlsx"
            multiple
            onchange={(e) => {
              const champ = /** @type {HTMLInputElement} */ (e.target);
              fichiersKoxo = [...(champ.files ?? [])];
              rapport = null;
            }}
            class="hidden"
          />
        </label>

        <Bouton
          icon={Search}
          variante="primary"
          occupe={occupe}
          disabled={!fichier || !anneeId}
          onclick={croiser}
        >
          Croiser les sources
        </Bouton>
      </div>
      <p class="text-xs text-stone-500 dark:text-stone-400">
        L'annuaire Google est lu à chaque croisement — comptes et membres de
        chaque groupe de classe : compte une minute. Sans export KoXo, sa
        colonne reste vide plutôt que fausse.
        <strong>KoXo a une base par établissement</strong> : un export ne
        couvre que la sienne. Dépose-les <strong>tous en même temps</strong>
        (NDK <em>et</em> SU) pour juger toute l'école en une passe — les
        élèves d'une base absente restent « hors base » plutôt qu'accusés.
      </p>
    </div>

    {#if rapport}
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Lignes lues" value={rapport.nb_lignes_lues} />
        <StatCard
          label="Toutes sources d'accord"
          value={rapport.nb_accord}
          variante="success"
        />
        <StatCard
          label="À corriger"
          value={rapport.nb_a_corriger}
          variante={rapport.nb_a_corriger ? "danger" : "success"}
        />
        <StatCard
          label="Classes concernées"
          value={rapport.classes_concernees.length}
          hint={rapport.koxo_fourni
            ? (rapport.koxo_sites.length
                ? `KoXo : ${rapport.koxo_sites.join(", ")}`
                : "export KoXo non reconnu")
            : "sans KoXo"}
        />
      </div>

      {#if rapport.nb_a_corriger === 0}
        <div class="card flex items-center gap-3 border-emerald-300 p-4 dark:border-emerald-800">
          <CheckCircle2 class="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <p class="text-sm">
            Les quatre sources disent la même chose pour chaque élève.
          </p>
        </div>
      {:else}
        <div class="card space-y-3 p-4">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="text-xs text-stone-600 dark:text-stone-400">
              {Object.entries(rapport.par_genre)
                .map(([g, n]) => `${n} ${LIBELLES[g] ?? g}`)
                .join(" · ")}
            </p>
            <div class="flex items-center gap-2">
              <button class="btn-secondary text-xs" onclick={toutCocher}>
                {retenues.size === corrigeables.length ? "Tout décocher" : "Tout cocher"}
              </button>
              <Bouton
                variante="primary"
                icon={Wand2}
                occupe={occupe}
                disabled={retenues.size === 0}
                onclick={aligner}
              >
                Aligner {retenues.size} élève(s) sur Charlemagne
              </Bouton>
            </div>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="text-xs uppercase text-stone-500 dark:text-stone-400">
                <tr>
                  <th class="px-2 py-1"></th>
                  <th class="px-2 py-1 text-left">Élève</th>
                  <th class="px-2 py-1 text-left">Charlemagne</th>
                  <th class="px-2 py-1 text-left">Référentiel</th>
                  <th class="px-2 py-1 text-left">Google</th>
                  {#if rapport.koxo_fourni}
                    <th class="px-2 py-1 text-left">KoXo</th>
                  {/if}
                  <th class="px-2 py-1 text-left">Écart</th>
                </tr>
              </thead>
              <tbody>
                {#each rapport.lignes as l (l.badge)}
                  {@const horsPortee = !l.personne_id
                    || l.genres.every((g) => HORS_PORTEE.has(g))}
                  <tr class="border-t border-stone-100 dark:border-stone-800">
                    <td class="px-2 py-1">
                      {#if !horsPortee}
                        <input
                          type="checkbox"
                          checked={retenues.has(l.personne_id)}
                          onchange={() => basculer(l.personne_id)}
                        />
                      {/if}
                    </td>
                    <td class="px-2 py-1">
                      <span class="font-medium">{l.prenom} {l.nom}</span>
                      <span class="text-xs text-stone-500 dark:text-stone-400">
                        · {l.site ?? "—"} · {l.badge}
                      </span>
                    </td>
                    <td class="px-2 py-1 font-medium text-emerald-700 dark:text-emerald-400">
                      {l.charlemagne ?? "—"}
                    </td>
                    <td class="px-2 py-1 {l.referentiel !== l.charlemagne ? 'text-rose-600 dark:text-rose-400' : 'text-stone-500'}">
                      {l.referentiel ?? "—"}
                    </td>
                    <td class="px-2 py-1 {l.google_classe !== l.charlemagne ? 'text-rose-600 dark:text-rose-400' : 'text-stone-500'}">
                      {l.google_classe ?? (l.google_ou ? "hors classe" : "—")}
                    </td>
                    {#if rapport.koxo_fourni}
                      <td class="px-2 py-1 {l.koxo_consulte && l.koxo !== l.charlemagne ? 'text-rose-600 dark:text-rose-400' : 'text-stone-500'}">
                        {#if !l.koxo_consulte}
                          <span title="Cet export KoXo ne parle pas de son établissement">
                            hors base
                          </span>
                        {:else}
                          {l.koxo ?? "—"}
                        {/if}
                      </td>
                    {/if}
                    <td class="px-2 py-1 text-xs text-stone-600 dark:text-stone-400">
                      {l.genres.map((g) => LIBELLES[g] ?? g).join(", ")}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <p class="text-xs text-stone-500 dark:text-stone-400">
            Les lignes sans case à cocher ne se règlent pas par un changement
            de classe : un élève sans compte se crée depuis
            <strong>Arrivée</strong>, un inconnu du référentiel entre par une
            <strong>ingestion</strong>.
          </p>
        </div>
      {/if}

      {#if application}
        <div class="card space-y-2 p-4">
          <p class="text-sm">
            <strong class="tabular-nums">{application.faits}</strong> /
            {application.total} traités
            {#if application.echecs.length}
              · <span class="text-rose-600 dark:text-rose-400">
                {application.echecs.length} en échec
              </span>
            {/if}
          </p>
          {#each application.echecs as e (e.nom)}
            <p class="text-xs text-rose-700 dark:text-rose-300">
              <strong>{e.nom}</strong> — {e.message}
            </p>
          {/each}
          {#if !application.echecs.length && application.faits === application.total}
            <p class="text-xs text-stone-600 dark:text-stone-400">
              Reste KoXo : va dans <strong>Exports</strong>, onglet KoXo, et
              génère le fichier pour les classes concernées —
              <span class="font-mono">{rapport.classes_concernees.join(" ")}</span>
            </p>
          {/if}
        </div>
      {/if}
    {/if}
  {/if}
</section>
