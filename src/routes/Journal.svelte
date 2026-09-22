<script>
  import { onMount } from "svelte";
  import History from "@lucide/svelte/icons/history";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Search from "@lucide/svelte/icons/search";
  import Download from "@lucide/svelte/icons/download";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import BarreAction from "$lib/components/BarreAction.svelte";
  import { enregistrerFichierBase64, journal } from "$lib/api.js";
  import { TEINTES } from "$lib/familles.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Ce qui a été fait, et quand.
   *
   * ## Pourquoi il fallait le montrer
   *
   * Le programme journalise depuis toujours : chaque ingestion, chaque
   * export, chaque déplacement laisse une trace avec ses paramètres et son
   * résultat. Aucun écran ne les montrait — la table existait pour personne.
   *
   * Or la question revient : *« pourquoi ce compte est-il là ? »*,
   * *« quand ai-je synchronisé KoXo pour la dernière fois ? »*, *« qu'est-ce
   * que j'ai importé le 15 septembre ? »*. En août prochain, quand le
   * référentiel ne collera pas à Charlemagne, c'est ici qu'on saura si
   * c'était un accident ou une décision.
   *
   * ## Ce qu'une ligne montre, et ce qu'elle cache
   *
   * Le résumé d'abord — quoi, quand, sur quelle année, avec quel résultat.
   * Le détail complet se déplie : paramètres et résultat tels qu'ils ont été
   * enregistrés. Les mots de passe n'y sont jamais : le journal les écarte à
   * l'écriture, et il vaut mieux perdre une information de mise au point que
   * consigner un secret.
   */

  /** Séparateurs du CSV — nommés pour rester lisibles à la relecture. */
  const SAUT = "\r\n";
  /** Sans lui, Excel lit les accents de travers. */
  const BOM = "﻿";

  let lignes = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let erreur = $state("");
  let depliee = $state(/** @type {number | null} */ (null));
  let filtreType = $state("");
  let recherche = $state("");

  const LIBELLES = {
    ingestion: "Ingestion",
    amorcage: "Amorçage",
    import_table: "Import de table",
    export: "Export",
    cycle_vie: "Cycle de vie",
    identifiant: "Identifiant",
    mouvement: "Mouvement",
    desinscription: "Désinscription",
  };

  /**
   * La pastille prend la couleur du domaine touché, pas une palette à
   * elle : on relit le journal après être passé par les écrans, et la
   * teinte est ce qui fait retrouver « la ligne verte de KoXo » sans lire.
   */
  const COULEURS = {
    ingestion: TEINTES.rentree,
    import_table: TEINTES.rentree,
    amorcage: TEINTES.koxo,
    export: TEINTES.fichiers,
    cycle_vie: TEINTES.google,
    mouvement: TEINTES.google,
    identifiant: TEINTES.annee,
    desinscription: "var(--color-red-600)",
  };

  const couleur = (t) => COULEURS[t] ?? TEINTES.fichiers;

  onMount(charger);

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      lignes = await journal.lister({ limite: 300 });
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
      notify.erreur(erreur);
    } finally {
      chargement = false;
    }
  }

  const heure = (iso) =>
    new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

  /**
   * Le journal se lit par journées, pas par horodatages.
   *
   * « 22/09/2026 14:32 » sur chaque ligne oblige à comparer des dates pour
   * savoir ce qui s'est passé le même jour. Un intertitre par journée et
   * l'heure seule sur la ligne : la question qu'on se pose est « qu'est-ce
   * que j'ai fait mardi », et elle se lit alors d'un coup d'œil.
   */
  function jourDe(iso) {
    const d = new Date(iso);
    const auj = new Date();
    const memeJour = (a, b) => a.toDateString() === b.toDateString();
    if (memeJour(d, auj)) return "Aujourd'hui";
    const hier = new Date(auj);
    hier.setDate(auj.getDate() - 1);
    if (memeJour(d, hier)) return "Hier";
    return d.toLocaleDateString("fr-FR", {
      weekday: "long", day: "numeric", month: "long", year: "numeric",
    });
  }

  /** Le chiffre qui résume l'opération, quand elle en porte un. */
  function resume(l) {
    const r = l.resultat ?? {};
    const parts = [];
    for (const [cle, valeur] of Object.entries(r)) {
      if (typeof valeur === "number" && valeur !== 0) {
        parts.push(`${valeur} ${cle.replace(/^nb_/, "").replace(/_/g, " ")}`);
      }
    }
    return parts.slice(0, 4).join(" · ");
  }

  let types = $derived([...new Set(lignes.map((l) => l.type_operation))].sort());

  /** Les lignes regroupées par journée, dans l'ordre où elles arrivent. */
  let journees = $derived.by(() => {
    const par = [];
    for (const l of listeFiltree) {
      const jour = jourDe(l.date_creation);
      const dernier = par.at(-1);
      if (dernier?.jour === jour) dernier.lignes.push(l);
      else par.push({ jour, lignes: [l] });
    }
    return par;
  });

  /** Le journal sur papier, pour le joindre à un ticket ou l'archiver. */
  function exporter() {
    const rangs = [
      ["Date", "Operation", "Mode", "Cible", "Annee", "Resultat"],
      ...listeFiltree.map((l) => [
        new Date(l.date_creation).toLocaleString("fr-FR"),
        LIBELLES[l.type_operation] ?? l.type_operation,
        l.mode ?? "",
        l.cible ?? "",
        l.annee_libelle ?? "",
        l.notes || resume(l) || "",
      ]),
    ];
    const csv = rangs
      .map((r) => r.map((c) => `"${String(c).replaceAll('"', '""')}"`).join(";"))
      .join(SAUT);
    const octets = new TextEncoder().encode(BOM + csv);
    let binaire = "";
    for (const o of octets) binaire += String.fromCharCode(o);
    enregistrerFichierBase64("Journal.csv", btoa(binaire), "text/csv");
  }

  let listeFiltree = $derived.by(() => {
    let r = lignes;
    if (filtreType) r = r.filter((l) => l.type_operation === filtreType);
    const q = recherche.trim().toLowerCase();
    if (q) {
      r = r.filter((l) =>
        `${l.type_operation} ${l.cible ?? ""} ${l.notes ?? ""} ${l.annee_libelle ?? ""}`
          .toLowerCase()
          .includes(q),
      );
    }
    return r;
  });
</script>

<section class="flex min-h-[calc(100vh-10rem)] flex-col space-y-6">
  <EnTetePage
    icon={History}
    titre="Ce qui a été fait"
    description="Le journal des actions réalisées, de la plus récente à la plus ancienne. C'est ici qu'on répond à « pourquoi ce compte est-il là ? », des mois plus tard."
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

  {#if chargement && !lignes.length}
    <Squelette variante="ligne-tableau" nb={6} colonnes={4} />
  {:else if !lignes.length}
    <EtatVide
      icon={History}
      titre="Aucune opération enregistrée"
      message="Le journal se remplit au fil des ingestions, des exports et des déplacements."
    />
  {:else}
    <!-- Chercher et filtrer, sur une seule ligne. -->
    <div class="flex flex-wrap items-center gap-4">
      <div class="relative min-w-56 flex-1 sm:max-w-xs">
        <Search class="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-stone-400" />
        <input
          class="champ !rounded-full !py-1.5 pl-9 text-sm"
          placeholder="Chercher dans le journal"
          bind:value={recherche}
        />
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          class="rounded-full px-4 py-1.5 text-[13px] font-semibold transition-colors {filtreType === ''
            ? 'bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900'
            : 'bg-stone-100 text-stone-600 hover:bg-stone-200 dark:bg-stone-900 dark:text-stone-400 dark:hover:bg-stone-800'}"
          onclick={() => (filtreType = "")}
        >
          Tout
        </button>
        {#each types as t (t)}
          <button
            class="rounded-full px-4 py-1.5 text-[13px] font-semibold transition-colors {filtreType === t
              ? 'bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900'
              : 'bg-stone-100 text-stone-600 hover:bg-stone-200 dark:bg-stone-900 dark:text-stone-400 dark:hover:bg-stone-800'}"
            onclick={() => (filtreType = t)}
          >
            {LIBELLES[t] ?? t}
            <span class="tabular-nums opacity-60">
              {lignes.filter((l) => l.type_operation === t).length}
            </span>
          </button>
        {/each}
      </div>
    </div>

    <!-- Le journal, par journées. -->
    <div class="min-h-0 flex-1 overflow-y-auto">
      {#each journees as j (j.jour)}
        <p class="mt-6 mb-1 text-xs font-bold tracking-[0.08em] text-stone-600 uppercase first:mt-0 dark:text-stone-400">
          {j.jour}
        </p>
        {#each j.lignes as l (l.id)}
          <div class="border-b border-stone-100 dark:border-stone-800/70">
            <div class="grid grid-cols-[62px_18px_minmax(0,1fr)_minmax(0,1.1fr)_80px] items-center gap-3 py-3 text-sm">
              <span class="font-mono text-[13px] text-stone-600 tabular-nums dark:text-stone-400">
                {heure(l.date_creation)}
              </span>
              <span
                class="h-2.5 w-2.5 rounded-full"
                style="background: {couleur(l.type_operation)};"
                aria-hidden="true"
              ></span>
              <span class="min-w-0 truncate font-bold">
                {LIBELLES[l.type_operation] ?? l.type_operation}
                {#if l.mode}
                  <span class="font-normal text-stone-500 dark:text-stone-400">· {l.mode}</span>
                {/if}
              </span>
              <span class="min-w-0 truncate text-stone-600 dark:text-stone-400">
                {[l.cible, l.annee_libelle, l.notes || resume(l)].filter(Boolean).join(" · ") || "—"}
              </span>
              <button
                class="justify-self-end text-sm font-semibold hover:underline"
                style="color: {TEINTES.annee};"
                onclick={() => (depliee = depliee === l.id ? null : l.id)}
              >
                {depliee === l.id ? "Replier" : "Détails"}
              </button>
            </div>

            {#if depliee === l.id}
              <div class="anim-apparition-douce grid gap-6 rounded-xl bg-stone-100/70 px-5 py-4 lg:grid-cols-2 dark:bg-stone-900">
                {#each [["Ce qui a été demandé", l.parametres], ["Ce qui en est sorti", l.resultat]] as [titre, bloc] (titre)}
                  <div>
                    <p class="libelle-champ mb-1.5">{titre}</p>
                    {#if bloc && Object.keys(bloc).length}
                      <dl class="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs">
                        {#each Object.entries(bloc) as [cle, valeur] (cle)}
                          <dt class="text-stone-500 dark:text-stone-400">{cle}</dt>
                          <dd class="min-w-0 font-mono break-words">
                            {Array.isArray(valeur)
                              ? valeur.slice(0, 12).join(", ") +
                                (valeur.length > 12 ? ` … (${valeur.length})` : "")
                              : String(valeur)}
                          </dd>
                        {/each}
                      </dl>
                    {:else}
                      <p class="text-xs text-stone-400">rien d'enregistré</p>
                    {/if}
                  </div>
                {/each}
                <p class="text-[11px] text-stone-500 lg:col-span-2 dark:text-stone-400">
                  Les mots de passe ne figurent jamais ici : le journal les écarte
                  à l'écriture. Mieux vaut perdre une information de mise au point
                  que consigner un secret.
                </p>
              </div>
            {/if}
          </div>
        {/each}
      {/each}

      {#if !listeFiltree.length}
        <p class="py-10 text-center text-sm text-stone-500 dark:text-stone-400">
          Aucune opération ne correspond à cette recherche.
        </p>
      {/if}
    </div>

    <BarreAction message="Les {listeFiltree.length} dernières actions, la plus récente en haut.">
      <Bouton icon={Download} onclick={exporter}>Exporter le journal</Bouton>
    </BarreAction>
  {/if}
</section>
