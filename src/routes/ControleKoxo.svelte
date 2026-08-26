<script>
  /**
   * Contrôle d'un export KoXo avant la synchronisation annuelle.
   *
   * La synchronisation reconnaît un compte par son **ID unique**, et ne
   * retombe sur `Nom + Prénom + Date de naissance` que si ce champ est
   * vide. L'établissement ne renseignant pas la date de naissance, ce
   * repli ne distingue rien : un compte non reconnu est un compte recréé
   * sous un autre login — ou supprimé, si la synchronisation est
   * destructive.
   *
   * Cet écran n'écrit rien, ni dans le référentiel ni dans KoXo. Il lit un
   * export et dit ce qui empêchera la reconnaissance. Corriger reste un
   * geste humain, fait dans KoXo, parce que le programme n'a aucun moyen
   * de savoir laquelle des deux valeurs fait foi.
   */
  import { onMount } from "svelte";
  import ShieldCheck from "@lucide/svelte/icons/shield-check";
  import Upload from "@lucide/svelte/icons/upload";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import Info from "@lucide/svelte/icons/info";
  import Download from "@lucide/svelte/icons/download";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import { annees as anneesApi, koxo, sites as sitesApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Les genres d'écart, rangés du plus bloquant au plus anodin.
   *
   * L'ordre n'est pas décoratif : il dit dans quel ordre les traiter. Un
   * rapprochement ambigu se règle avant un login divergent, parce qu'on ne
   * sait pas encore de qui le compte est celui.
   */
  const GENRES = {
    rapprochement_ambigu: {
      titre: "Rapprochement ambigu",
      quoi: "Le badge désigne une personne, l'identifiant une autre.",
      ton: "rouge",
    },
    id_en_double: {
      titre: "ID unique en double",
      quoi: "Plusieurs comptes KoXo portent le même ID unique.",
      ton: "rouge",
    },
    login_en_double: {
      titre: "Identifiant en double",
      quoi: "Deux comptes portent le même identifiant.",
      ton: "rouge",
    },
    id_non_numerique: {
      titre: "ID unique qui n'est pas un badge",
      quoi: "Le champ contient autre chose qu'un numéro.",
      ton: "rouge",
    },
    id_absent: {
      titre: "ID unique absent",
      quoi: "Rien ne permet de reconnaître ce compte.",
      ton: "rouge",
    },
    login_divergent: {
      titre: "Identifiant divergent",
      quoi: "KoXo et le référentiel ne connaissent pas ce badge sous le même identifiant.",
      ton: "ambre",
    },
    badge_inconnu: {
      titre: "Badge inconnu du référentiel",
      quoi: "Aucune ligne de l'export ne s'adressera à ce compte.",
      ton: "ambre",
    },
    absent_de_koxo: {
      titre: "À créer dans KoXo",
      quoi: "Le déroulement normal d'une rentrée : la synchronisation créera le compte.",
      ton: "neutre",
    },
  };

  const TONS = {
    rouge: {
      carte: "border-red-200 bg-red-50/60 dark:border-red-900/50 dark:bg-red-900/15",
      titre: "text-red-900 dark:text-red-200",
      pastille: "bg-red-500",
    },
    ambre: {
      carte: "border-amber-200 bg-amber-50/60 dark:border-amber-900/50 dark:bg-amber-900/15",
      titre: "text-amber-900 dark:text-amber-200",
      pastille: "bg-amber-500",
    },
    neutre: {
      carte: "border-stone-200 bg-stone-50/60 dark:border-stone-700 dark:bg-stone-800/40",
      titre: "text-stone-700 dark:text-stone-300",
      pastille: "bg-stone-400",
    },
  };

  let listeSites = $state([]);
  let listeAnnees = $state([]);
  let siteId = $state(/** @type {null | number} */ (null));
  let anneeId = $state(/** @type {null | number} */ (null));
  let typePersonne = $state(/** @type {"eleve"|"adulte"} */ ("eleve"));
  let fichier = $state(/** @type {File|null} */ (null));
  let rapport = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");
  let deplie = $state(/** @type {string|null} */ (null));

  onMount(async () => {
    try {
      listeSites = await sitesApi.lister();
    } catch {
      listeSites = [];
    }
    try {
      listeAnnees = await anneesApi.lister();
      // L'année la plus récente est celle qu'on prépare : c'est sa
      // population qui doit exister dans KoXo à la fin. Elle se trouve par
      // son libellé, et non par le premier rang : la liste est rendue par
      // date de création, et une année réingérée passe devant.
      const derniere = [...listeAnnees].sort((a, b) =>
        a.libelle.localeCompare(b.libelle),
      ).at(-1);
      if (derniere) anneeId = derniere.id;
    } catch {
      listeAnnees = [];
    }
  });

  /** Les écarts d'un genre donné, dans l'ordre de GENRES. */
  let parGenre = $derived.by(() => {
    if (!rapport) return [];
    return Object.keys(GENRES)
      .map((genre) => ({
        genre,
        ...GENRES[genre],
        lignes: rapport.ecarts.filter((e) => e.genre === genre),
      }))
      .filter((g) => g.lignes.length);
  });

  /** Ce qui empêchera une reconnaissance — les créations n'en sont pas. */
  let nbBloquants = $derived(
    rapport ? rapport.ecarts.filter((e) => e.genre !== "absent_de_koxo").length : 0,
  );

  async function lancer() {
    if (!fichier) return;
    chargement = true;
    erreur = "";
    rapport = null;
    try {
      rapport = await koxo.controle({ fichier, typePersonne, siteId, anneeId });
      if (rapport.est_sain) {
        notify.succes("Aucun écart : la synchronisation reconnaîtra tous les comptes");
      } else {
        notify.info(`${nbBloquants} écart(s) à regarder avant la synchronisation`);
      }
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
      notify.erreur(erreur, { duree: 12000 });
    } finally {
      chargement = false;
    }
  }

  /** Le rapport en CSV, pour le corriger dans KoXo une ligne après l'autre. */
  function exporter() {
    if (!rapport) return;
    const colonnes = [
      "genre", "qui", "identifiant_koxo", "id_unique_koxo",
      "badge_referentiel", "identifiant_referentiel", "lignes", "explication",
      "consequence",
    ];
    const echapper = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lignes = rapport.ecarts.map((e) =>
      [
        e.genre, e.qui, e.login, e.id_unique, e.badge_referentiel,
        e.login_referentiel, (e.lignes ?? []).join(" "), e.explication,
        e.consequence,
      ]
        .map(echapper)
        .join(";"),
    );
    const contenu = "﻿" + [colonnes.join(";"), ...lignes].join("\r\n");
    const url = URL.createObjectURL(
      new Blob([contenu], { type: "text/csv;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `controle_koxo_${typePersonne}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<section class="space-y-4">
  <EnTetePage
    icon={ShieldCheck}
    titre="Contrôle avant synchronisation KoXo"
    description="Confronte un export KoXo au référentiel et signale ce qui empêchera la reconnaissance des comptes. Lecture seule : rien n'est écrit, ni ici ni dans KoXo."
  />

  <div class="card space-y-3 p-4">
    <p class="text-xs text-stone-600 dark:text-stone-400">
      La synchronisation reconnaît un compte par son <strong>ID unique</strong>,
      et ne retombe sur <em>Nom + Prénom + Date de naissance</em> que si ce champ
      est vide. Comme la date de naissance n'est pas renseignée, ce repli ne
      distingue rien : un compte non reconnu est recréé sous un autre identifiant
      — ou supprimé, si la synchronisation est en mode destructif.
    </p>

    <div class="flex flex-wrap items-end gap-3">
      <label class="flex flex-col gap-1">
        <span class="text-xs text-stone-500 dark:text-stone-400">Population</span>
        <select class="champ text-sm" bind:value={typePersonne}>
          <option value="eleve">Élèves</option>
          <option value="adulte">Adultes</option>
        </select>
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-xs text-stone-500 dark:text-stone-400">Site</span>
        <select class="champ text-sm" bind:value={siteId}>
          <option value={null}>Tous</option>
          {#each listeSites as s (s.id)}<option value={s.id}>{s.nom}</option>{/each}
        </select>
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-xs text-stone-500 dark:text-stone-400">Année visée</span>
        <select class="champ text-sm" bind:value={anneeId}>
          <option value={null}>Toutes</option>
          {#each listeAnnees as a (a.id)}<option value={a.id}>{a.libelle}</option>{/each}
        </select>
      </label>

      <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
        <Upload class="h-4 w-4" />
        {fichier?.name ?? "Choisir l'export KoXo (.csv)"}
        <input
          type="file"
          accept=".csv,.txt"
          class="hidden"
          onchange={(e) => {
            fichier = e.target.files?.[0] ?? null;
            rapport = null;
          }}
        />
      </label>

      <Bouton variante="primary" occupe={chargement} disabled={!fichier} onclick={lancer}>
        Contrôler
      </Bouton>
      {#if rapport}
        <Bouton icon={Download} classe="ml-auto" onclick={exporter}>Export CSV</Bouton>
      {/if}
    </div>

    {#if erreur}
      <p class="rounded bg-red-50 px-3 py-2 text-sm text-red-800 dark:bg-red-900/20 dark:text-red-200">
        {erreur}
      </p>
    {/if}
  </div>

  {#if rapport}
    <!-- Comment le fichier a été compris. Un séparateur mal deviné donne un
         rapport vide qui ressemble à un rapport sain. -->
    <div class="card flex flex-wrap items-center gap-x-8 gap-y-3 p-4">
      <div class="flex items-center gap-3">
        {#if rapport.est_sain}
          <CheckCircle2 class="h-8 w-8 text-emerald-600 dark:text-emerald-400" />
        {:else}
          <AlertTriangle class="h-8 w-8 text-amber-600 dark:text-amber-400" />
        {/if}
        <div>
          <p class="text-2xl font-semibold tabular-nums leading-none text-stone-900 dark:text-stone-100">
            {rapport.nb_concordants}<span class="text-base font-normal text-stone-400">/{rapport.nb_lignes}</span>
          </p>
          <p class="text-xs text-stone-500 dark:text-stone-400">comptes reconnus</p>
        </div>
      </div>

      <div>
        <p class="text-lg font-semibold tabular-nums leading-none {nbBloquants ? 'text-red-700 dark:text-red-400' : 'text-emerald-700 dark:text-emerald-400'}">
          {nbBloquants}
        </p>
        <p class="text-xs text-stone-500 dark:text-stone-400">à corriger dans KoXo</p>
      </div>

      <div>
        <p class="text-lg font-semibold tabular-nums leading-none text-stone-600 dark:text-stone-300">
          {rapport.nb_par_genre.absent_de_koxo ?? 0}
        </p>
        <p class="text-xs text-stone-500 dark:text-stone-400">comptes à créer</p>
      </div>

      <p class="ml-auto text-xs text-stone-400 dark:text-stone-500">
        {rapport.fichier} · séparateur « {rapport.separateur} » · {rapport.encodage}
        · {rapport.colonnes_lues.length} colonnes lues
      </p>
    </div>

    {#each rapport.avertissements as a}
      <p class="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">
        <Info class="mt-0.5 h-3.5 w-3.5 shrink-0" />
        {a}
      </p>
    {/each}

    {#if rapport.est_sain}
      <div class="card p-4">
        <EtatVide
          icon={CheckCircle2}
          titre="Aucun écart"
          message="Chaque compte de cet export est reconnu par son ID unique, et le référentiel lui donne le même identifiant. La synchronisation déplacera les comptes existants sans en recréer."
        />
      </div>
    {/if}

    {#each parGenre as g (g.genre)}
      {@const t = TONS[g.ton]}
      <div class="card overflow-hidden">
        <button
          class="flex w-full items-center gap-3 border-b px-4 py-3 text-left transition
                 hover:bg-stone-50 dark:hover:bg-stone-800/50 {t.carte}"
          onclick={() => (deplie = deplie === g.genre ? null : g.genre)}
        >
          <span class="h-2 w-2 shrink-0 rounded-full {t.pastille}"></span>
          <span class="font-medium {t.titre}">{g.titre}</span>
          <span class="text-xs text-stone-500 dark:text-stone-400">{g.quoi}</span>
          <span class="ml-auto text-sm font-semibold tabular-nums {t.titre}">
            {g.lignes.length}
          </span>
        </button>

        {#if deplie === g.genre || g.lignes.length <= 10}
          <div class="max-h-[26rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Qui</th>
                  <th class="text-left">Identifiant KoXo</th>
                  <th class="text-left">ID unique</th>
                  <th class="text-left">Référentiel</th>
                  <th class="text-left">Ligne</th>
                </tr>
              </thead>
              <tbody>
                {#each g.lignes.slice(0, 300) as e (e.qui + e.login + e.id_unique)}
                  <tr>
                    <td class="whitespace-nowrap">{e.qui}</td>
                    <td class="whitespace-nowrap font-mono text-xs">{e.login || "—"}</td>
                    <td class="whitespace-nowrap font-mono text-xs">{e.id_unique || "—"}</td>
                    <td class="whitespace-nowrap font-mono text-xs text-stone-500">
                      {e.login_referentiel || e.badge_referentiel || "—"}
                    </td>
                    <td class="whitespace-nowrap text-xs text-stone-400">
                      {(e.lignes ?? []).join(", ") || "—"}
                    </td>
                  </tr>
                  {#if e.explication}
                    <tr>
                      <td colspan="5" class="px-4 pb-2 pt-0">
                        <p class="text-xs text-stone-600 dark:text-stone-400">
                          {e.explication}
                        </p>
                        {#if e.consequence}
                          <p class="mt-0.5 text-xs {t.titre}">→ {e.consequence}</p>
                        {/if}
                      </td>
                    </tr>
                  {/if}
                {/each}
              </tbody>
            </table>
            {#if g.lignes.length > 300}
              <p class="px-4 py-2 text-xs text-stone-500 dark:text-stone-400">
                300 premières lignes affichées — l'export CSV les contient toutes.
              </p>
            {/if}
          </div>
        {/if}
      </div>
    {/each}
  {/if}
</section>
