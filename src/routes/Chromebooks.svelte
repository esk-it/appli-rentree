<script>
  import { onMount } from "svelte";
  import Laptop from "@lucide/svelte/icons/laptop";
  import Upload from "@lucide/svelte/icons/upload";
  import Undo2 from "@lucide/svelte/icons/undo-2";
  import UserPlus from "@lucide/svelte/icons/user-plus";
  import PackageOpen from "@lucide/svelte/icons/package-open";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Download from "@lucide/svelte/icons/download";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Chromebook from "$lib/components/Chromebook.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import { enregistrerFichierBase64, googleApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let statutApi = $state(/** @type {any} */ (null));
  let fichier = $state(/** @type {File|null} */ (null));
  let flotte = $state(/** @type {any} */ (null));
  let chargement = $state(false);
  let vue = $state("a_recuperer");
  let enCours = $state(/** @type {string|null} */ (null));
  let attribution = $state(/** @type {any} */ (null));
  let recherche = $state("");
  let filtreOu = $state("");
  let filtreModele = $state("");
  let filtreEtat = $state("");

  /** Ce qu'on voit du parc une fois les filtres posés. */
  let parcFiltre = $derived.by(() => {
    if (!flotte) return [];
    return flotte.tous.filter((a) => {
      if (filtreOu && a.ou !== filtreOu) return false;
      if (filtreModele && a.modele !== filtreModele) return false;
      if (filtreEtat === "dormant" && !(a.dort && a.statut === "ACTIVE")) return false;
      if (filtreEtat === "desactive" && a.statut === "ACTIVE") return false;
      if (filtreEtat === "service" && (a.dort || a.statut !== "ACTIVE")) return false;
      return true;
    });
  });

  /**
   * Ce qu'il y a à faire d'un appareil, en un mot.
   *
   * C'est l'action attendue qui colore la ligne, non la santé technique :
   * regarder un parc, c'est chercher ce qui réclame un geste. Une machine
   * en service chez quelqu'un qui reste n'a rien à signaler, et c'est très
   * bien ainsi — elle reste neutre.
   */
  function etatDe(a) {
    if (a.recupere_le) return "rendu";
    if (a.statut !== "ACTIVE") return "hs";
    if (a.a_recuperer) return "attendu";
    // `libre` vient du service, qui sait que le parc de prêt se limite aux
    // machines du personnel. Une machine élève porte un code d'emplacement
    // et non une adresse : sans porteur, mais pas disponible pour autant.
    if (a.libre) return "libre";
    if (a.dort) return "dormant";
    return "actif";
  }

  const ETATS = {
    attendu: {
      texte: "à récupérer",
      ligne: "bg-red-50/70 dark:bg-red-900/15",
      pastille: "bg-red-500",
      mot: "text-red-700 dark:text-red-400",
      dessin: "hs",
    },
    libre: {
      texte: "libre",
      ligne: "bg-emerald-50/70 dark:bg-emerald-900/15",
      pastille: "bg-emerald-500",
      mot: "text-emerald-700 dark:text-emerald-400",
      dessin: "libre",
    },
    rendu: {
      texte: "rendue",
      ligne: "bg-emerald-50/40 dark:bg-emerald-900/10",
      pastille: "bg-emerald-400",
      mot: "text-emerald-700 dark:text-emerald-400",
      dessin: "rendu",
    },
    dormant: {
      texte: "en sommeil",
      ligne: "",
      pastille: "bg-amber-400",
      mot: "text-amber-700 dark:text-amber-400",
      dessin: "dormant",
    },
    hs: {
      texte: "désactivée",
      ligne: "opacity-60",
      pastille: "bg-stone-300 dark:bg-stone-600",
      mot: "text-stone-500 dark:text-stone-400",
      dessin: "hs",
    },
    actif: {
      texte: "en service",
      ligne: "",
      pastille: "bg-stone-300 dark:bg-stone-600",
      mot: "text-stone-500 dark:text-stone-400",
      dessin: "actif",
    },
  };

  let ousDispo = $derived(
    [...new Set((flotte?.tous ?? []).map((a) => a.ou).filter(Boolean))].sort(),
  );
  let modelesDispo = $derived(
    [...new Set((flotte?.tous ?? []).map((a) => a.modele).filter(Boolean))].sort(),
  );

  /**
   * Rendre un Chromebook, c'est en avoir un dans les mains et lire le
   * numéro inscrit dessous. Partir du nom du porteur supposé demande que
   * l'étiquette soit juste — c'est-à-dire ce qui manque quand on en a
   * besoin. La recherche porte aussi sur les derniers utilisateurs, qui
   * ne mentent pas sur qui s'en est servi.
   */
  let resultats = $derived.by(() => {
    const q = recherche.trim().toLowerCase();
    if (q.length < 3 || !flotte) return [];
    return flotte.tous
      .filter((a) =>
        [a.serie, a.etiquette, a.porteur ?? "", a.emplacement, a.modele]
          .concat(a.derniers_utilisateurs)
          .some((c) => (c ?? "").toLowerCase().includes(q)),
      )
      .sort((x, y) => (y.derniere_synchro ?? "").localeCompare(x.derniere_synchro ?? ""))
      .slice(0, 40);
  });

  /** Note un geste, puis relit la flotte : le suivi change les listes. */
  async function noter(params, message) {
    enCours = params.serie;
    try {
      await googleApi.noterSuiviAppareil(params);
      notify.succes(message);
      await analyser();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      enCours = null;
    }
  }

  /**
   * La note d'une machine, écrite au clavier puis enregistrée à la sortie
   * du champ. Le programme ne peut pas déduire ce qu'on décide d'un
   * appareil désactivé ou d'une étiquette douteuse ; il offre de l'écrire.
   */
  let noteEnEdition = $state(/** @type {string|null} */ (null));
  let texteNote = $state("");

  /** Le statut Google, en français. */
  const STATUTS = {
    ACTIVE: "en service",
    DEPROVISIONED: "désactivée dans Google",
    DISABLED: "suspendue",
  };

  /** « il y a deux mois » se juge mieux qu'une date brute. */
  function depuis(iso) {
    if (!iso) return "jamais synchronisée";
    const jours = Math.floor((Date.now() - new Date(iso)) / 86400000);
    if (jours <= 1) return "aujourd'hui";
    if (jours < 31) return `il y a ${jours} jours`;
    const mois = Math.round(jours / 30.4);
    if (mois < 24) return `il y a ${mois} mois`;
    return `il y a ${Math.round(mois / 12)} ans`;
  }

  let detail = $state(/** @type {string|null} */ (null));

  function ouvrirNote(a) {
    noteEnEdition = a.serie;
    texteNote = a.note ?? "";
  }

  async function enregistrerNote(serie) {
    const valeur = texteNote;
    noteEnEdition = null;
    await noter({ serie, note: valeur }, "Note enregistrée");
  }

  function confirmerAttribution(serie) {
    if (!attribution) return;
    const a = attribution;
    noter({ serie, attribueA: a }, serie + " confiée à " + a).then(
      () => (attribution = null),
    );
  }

  let apiUtilisable = $derived(
    statutApi?.bibliotheques_disponibles && statutApi?.configuration_complete,
  );

  async function analyser() {
    if (!fichier) return;
    chargement = true;
    try {
      flotte = await googleApi.analyserChromebooks({ fichier });
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      chargement = false;
    }
  }

  let onglets = $derived([
    { id: "a_recuperer", label: "À récupérer", badge: flotte?.nb_a_recuperer ?? 0 },
    { id: "a_attribuer", label: "À équiper", badge: flotte?.a_attribuer?.length ?? 0 },
    { id: "disponibles", label: "Libres", badge: flotte?.disponibles?.length ?? 0 },
    { id: "discordances", label: "À vérifier", badge: flotte?.discordances?.length ?? 0 },
    { id: "sans_compte", label: "Sans compte", badge: flotte?.sans_compte?.length ?? 0 },
    { id: "rapproches", label: "Rapprochés", badge: flotte?.rapproches?.length ?? 0 },
    { id: "recherche", label: "Retrouver une machine", badge: 0 },
    { id: "parc", label: "Le parc", badge: flotte?.parc?.total ?? 0 },
    { id: "journal", label: "Journal", badge: flotte?.historique?.length ?? 0 },
  ]);

  /** Comment le compte a été retrouvé, en français. */
  const RAISONS = {
    arrivant: "arrivant",
    remplace: "remplacement",
    revenu: "a rendu sa machine en juin, et revient",
  };

  const METHODES = {
    exact: "nom identique",
    nom_compose: "nom composé tronqué",
    prenom_compose: "prénom composé réduit",
    prenom_abrege: "prénom abrégé",
    orthographe: "une lettre d'écart",
    adresse: "retrouvé par l'adresse",
    nom_et_prenom_composes: "nom et prénom composés",
  };

  function exporter() {
    if (!flotte) return;
    const lignes = [];
    for (const p of flotte.a_recuperer) {
      for (const a of p.appareils) {
        lignes.push(["À récupérer", p.nom, p.prenom, p.discipline, p.email ?? "",
                     a.modele, a.serie, a.etiquette]);
      }
    }
    for (const p of flotte.a_attribuer) {
      lignes.push(["À équiper", p.nom, p.prenom, p.discipline, p.email ?? "", "", "", ""]);
    }
    for (const a of flotte.disponibles) {
      lignes.push(["Libre", "", "", "", "", a.modele, a.serie, a.etiquette]);
    }
    const entetes = ["Situation", "Nom", "Prénom", "Discipline", "Adresse",
                     "Modèle", "N° de série", "Étiquette"];
    const csv = [entetes, ...lignes]
      .map((l) => l.map((c) => (String(c).includes(";") ? `"${c}"` : c)).join(";"))
      .join("\r\n");
    const b64 = btoa(String.fromCharCode(...new TextEncoder().encode("﻿" + csv)));
    enregistrerFichierBase64("Chromebooks.csv", b64, "text/csv").then(
      ({ chemin, annule }) => {
        if (!annule) {
          notify.succes(`${lignes.length} ligne(s) — ${chemin ?? "Téléchargements"}`,
            { duree: 8000 });
        }
      },
    );
  }

  function jour(iso) {
    return iso ? iso.slice(0, 10).split("-").reverse().join("/") : "—";
  }

  onMount(async () => {
    try {
      statutApi = await googleApi.statut();
    } catch {
      statutApi = null;
      return;
    }
    // Le tableau des professeurs a été conservé lors du dernier import :
    // l'écran s'ouvre garni, sans réclamer à nouveau le classeur.
    try {
      flotte = await googleApi.flotteEnregistree();
    } catch {
      flotte = null;
    }
  });
</script>

<section class="space-y-4">
  <EnTetePage
    icon={Laptop}
    titre="Chromebooks"
    description="Qui détient quelle machine, ce qu'il faut réclamer aux partants et attribuer aux arrivants. Lecture seule : le programme constate, il ne déplace rien."
  />

  {#if !apiUtilisable}
    <div class="card p-4">
      <EtatVide
        icon={Laptop}
        titre="Mode API non configuré"
        message="Cet écran lit les appareils dans Google. Renseigne le compte de service dans Paramètres, et vérifie que le droit de lecture des Chromebooks lui a été accordé."
      />
    </div>
  {:else}
    <div class="card p-4 space-y-3">
      <p class="text-xs text-stone-600 dark:text-stone-400">
        Google prévoit un champ « utilisateur annoté » pour désigner le porteur
        d'un appareil ; il contient ici partout le même compte technique. C'est
        l'<strong>étiquette</strong> qui porte l'adresse du titulaire, et les
        dernières connexions servent de contre-épreuve. Le mouvement de chaque
        enseignant — entrant, sortant — vient du tableau que tu tiens, où il est
        porté par la couleur.
      </p>

      <div class="flex flex-wrap items-center gap-3">
        <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
          <Upload class="h-4 w-4" />
          {fichier?.name ?? (flotte ? "Charger un tableau à jour (.xlsx)" : "Choisir le tableau des professeurs (.xlsx)")}
          <input
            type="file"
            accept=".xlsx"
            class="hidden"
            onchange={(e) => (fichier = e.target.files?.[0] ?? null)}
          />
        </label>
        <Bouton variante="primary" occupe={chargement} disabled={!fichier} onclick={analyser}>
          {flotte ? "Remplacer le tableau" : "Analyser la flotte"}
        </Bouton>
        {#if flotte}
          <Bouton icon={Download} classe="ml-auto" onclick={exporter}>Export Excel</Bouton>
        {/if}
      </div>

      {#if flotte}
        <div class="flex flex-wrap gap-x-6 gap-y-1 border-t border-stone-200 pt-3 text-sm dark:border-stone-700">
          <span><strong class="tabular-nums">{flotte.nb_profs}</strong> enseignants</span>
          {#if flotte.tableau_importe_le}
            <span class="text-stone-500 dark:text-stone-400">
              tableau chargé le {jour(flotte.tableau_importe_le)}
            </span>
          {/if}
          {#each Object.entries(flotte.nb_par_code) as [code, n]}
            <span class="text-stone-500 dark:text-stone-400">{code} : {n}</span>
          {/each}
        </div>
        {#each flotte.avertissements as a}
          <p class="rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">
            {a}
          </p>
        {/each}
      {/if}
    </div>

    {#if flotte?.parc}
      <!-- Ce que le parc **est**, avant ce qu'il y a à y faire. Cinq cents
           appareils qu'on ne voit qu'à travers quatre listes d'actions
           restent invisibles le reste de l'année. -->
      <div class="card flex flex-wrap items-center gap-x-8 gap-y-4 p-4">
        <div class="flex items-center gap-3">
          <Chromebook taille={44} etat="actif" />
          <div>
            <p class="text-2xl font-semibold tabular-nums leading-none text-stone-900 dark:text-stone-100">
              {flotte.parc.total}
            </p>
            <p class="text-xs text-stone-500 dark:text-stone-400">appareils</p>
          </div>
        </div>

        <div class="flex items-center gap-6">
          <div>
            <p class="text-lg font-semibold tabular-nums leading-none text-emerald-700 dark:text-emerald-400">
              {flotte.parc.actifs - flotte.parc.dormants}
            </p>
            <p class="text-xs text-stone-500 dark:text-stone-400">en service</p>
          </div>
          <button
            class="text-left transition hover:opacity-80"
            title="Voir les appareils en sommeil"
            onclick={() => {
              vue = "parc";
              filtreEtat = "dormant";
            }}
          >
            <p class="text-lg font-semibold tabular-nums leading-none text-amber-700 dark:text-amber-400">
              {flotte.parc.dormants}
            </p>
            <p class="text-xs text-stone-500 underline-offset-2 hover:underline dark:text-stone-400">
              en sommeil
            </p>
          </button>
          <div>
            <p class="text-lg font-semibold tabular-nums leading-none text-stone-400 dark:text-stone-500">
              {flotte.parc.desactives}
            </p>
            <p class="text-xs text-stone-500 dark:text-stone-400">désactivés</p>
          </div>
        </div>

        <!-- Répartition par modèle : une barre proportionnelle en dit plus
             qu'une liste de nombres, et tient sur une ligne. -->
        <div class="min-w-56 flex-1">
          <div class="flex h-2 overflow-hidden rounded-full bg-stone-100 dark:bg-stone-700">
            {#each flotte.parc.par_modele.slice(0, 6) as [modele, n], i (modele)}
              <div
                class="h-full {['bg-emerald-500/80','bg-sky-500/70','bg-indigo-400/70','bg-amber-400/70','bg-stone-400/70','bg-stone-300/70'][i]}"
                style="width: {(n / flotte.parc.total) * 100}%"
                title="{modele} — {n}"
              ></div>
            {/each}
          </div>
          <p class="mt-1.5 truncate text-xs text-stone-500 dark:text-stone-400">
            {flotte.parc.par_modele.length} modèle(s) ·
            {flotte.parc.par_modele[0]?.[0]} en tête ({flotte.parc.par_modele[0]?.[1]})
          </p>
        </div>
      </div>
    {/if}

    {#if flotte}
      <div class="card p-3">
        <Segments bind:valeur={vue} options={onglets} />
      </div>

      <div class="card overflow-hidden">
        {#if vue === "a_recuperer"}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            <Undo2 class="mr-1 inline h-3.5 w-3.5" />
            Enseignants marqués sortants qui détiennent encore une machine.
          </div>
          <div class="max-h-[28rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Enseignant</th>
                  <th class="text-left">Discipline</th>
                  <th class="text-left">Modèle</th>
                  <th class="text-left">N° de série</th>
                  <th class="text-left">Dernière synchro</th>
                  <th class="text-left">Rendue</th>
                </tr>
              </thead>
              <tbody>
                {#each flotte.a_recuperer as p (p.email ?? p.nom)}
                  {#each p.appareils as a (a.serie)}
                    <tr>
                      <td class="whitespace-nowrap font-medium">{p.prenom} {p.nom}</td>
                      <td class="whitespace-nowrap text-stone-600 dark:text-stone-400">{p.discipline}</td>
                      <td class="whitespace-nowrap text-xs">{a.modele}</td>
                      <td class="whitespace-nowrap font-mono text-xs">{a.serie}</td>
                      <td class="whitespace-nowrap text-xs {a.dort ? 'text-amber-700 dark:text-amber-400' : 'text-stone-500'}">
                        {jour(a.derniere_synchro)}
                        {#if a.dort}<span class="ml-1">· en sommeil</span>{/if}
                      </td>
                      <td class="whitespace-nowrap">
                        <label class="inline-flex cursor-pointer items-center gap-2 text-xs">
                          <input
                            type="checkbox"
                            class="rounded"
                            disabled={enCours === a.serie}
                            onchange={() =>
                              noter(
                                { serie: a.serie, recupere: true, recupereDe: p.email },
                                a.serie + " notée rendue",
                              )}
                          />
                          je l'ai récupérée
                        </label>
                      </td>
                    </tr>
                  {/each}
                {/each}
              </tbody>
            </table>
          </div>

        {:else if vue === "a_attribuer"}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            <UserPlus class="mr-1 inline h-3.5 w-3.5" />
            Enseignants sans machine : arrivants, remplaçants, et ceux qui ont
            rendu la leur avant l'été par précaution puis sont revenus. Un
            titulaire qui n'en a jamais eu n'y figure pas.
          </div>
          <div class="max-h-[28rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Enseignant</th>
                  <th class="text-left">Discipline</th>
                  <th class="text-left">Adresse</th>
                  <th class="text-left">Pourquoi</th>
                  <th class="text-left">Machine confiée</th>
                </tr>
              </thead>
              <tbody>
                {#each flotte.a_attribuer as p (p.nom + p.prenom)}
                  <tr class:ligne-douteuse={!p.email}>
                    <td class="whitespace-nowrap font-medium">{p.prenom} {p.nom}</td>
                    <td class="whitespace-nowrap text-stone-600 dark:text-stone-400">{p.discipline}</td>
                    <td class="whitespace-nowrap font-mono text-xs">
                      {#if p.email}
                        {p.email}
                      {:else}
                        <span class="font-sans text-amber-700 dark:text-amber-400">
                          aucun compte Google — à créer d'abord
                        </span>
                      {/if}
                    </td>
                    <td class="whitespace-nowrap text-xs {p.raison === 'revenu' ? 'text-amber-700 dark:text-amber-400' : 'text-stone-600 dark:text-stone-400'}">
                      {RAISONS[p.raison] ?? p.raison}
                    </td>
                    <td class="whitespace-nowrap">
                      {#if !p.email}
                        <span class="text-xs text-stone-400">—</span>
                      {:else if attribution === p.email}
                        <select
                          class="champ w-56 font-mono text-xs"
                          onchange={(e) => e.target.value && confirmerAttribution(e.target.value)}
                        >
                          <option value="">— choisir une machine —</option>
                          {#each flotte.disponibles as d (d.serie)}
                            <option value={d.serie}>{d.etiquette} · {d.serie.slice(-8)}</option>
                          {/each}
                        </select>
                        <button
                          class="ml-2 text-xs text-stone-500 hover:text-red-600"
                          onclick={() => (attribution = null)}
                        >
                          annuler
                        </button>
                      {:else}
                        <Bouton
                          taille="sm"
                          icon={UserPlus}
                          disabled={!flotte.disponibles.length}
                          onclick={() => (attribution = p.email)}
                        >
                          Lui attribuer
                        </Bouton>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

        {:else if vue === "disponibles"}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            <PackageOpen class="mr-1 inline h-3.5 w-3.5" />
            Parc de prêt, et machines étiquetées au nom de comptes qui n'existent plus.
          </div>
          <div class="max-h-[28rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Étiquette</th>
                  <th class="text-left">Modèle</th>
                  <th class="text-left">N° de série</th>
                  <th class="text-left">Dernière synchro</th>
                </tr>
              </thead>
              <tbody>
                {#each flotte.disponibles as a (a.serie)}
                  <tr>
                    <td class="whitespace-nowrap font-mono text-xs">{a.etiquette}</td>
                    <td class="whitespace-nowrap text-xs">{a.modele}</td>
                    <td class="whitespace-nowrap font-mono text-xs">{a.serie}</td>
                    <td class="whitespace-nowrap text-xs text-stone-500">{jour(a.derniere_synchro)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

        {:else if vue === "journal"}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            Ce que tu as noté : machines reprises, machines confiées. Une
            machine attribuée quitte les listes d'actions — c'est le but — mais
            elle quittait aussi le champ de vision. C'est ici qu'on retrouve à
            qui elle est allée, et de qui elle venait.
          </div>

          {#if !flotte.historique.length}
            <p class="px-4 pb-4 text-sm text-stone-500 dark:text-stone-400">
              Aucun mouvement noté pour l'instant. Coche « je l'ai récupérée »
              ou attribue une machine, et le geste s'inscrira ici.
            </p>
          {:else}
            <div class="max-h-[30rem] overflow-auto">
              <ol class="divide-y divide-stone-100 dark:divide-stone-700/60">
                {#each flotte.historique as m (m.serie)}
                  <li class="flex items-start gap-4 px-4 py-3">
                    <Chromebook
                      taille={34}
                      etat={m.confie_a ? "actif" : "rendu"}
                      classe="mt-0.5 shrink-0"
                    />
                    <div class="min-w-0 flex-1">
                      <!-- Le trajet en une ligne : d'où elle vient, où elle
                           va. C'est la phrase qu'on se dit à voix haute. -->
                      <p class="flex flex-wrap items-baseline gap-x-2 text-sm">
                        {#if m.rendu_par}
                          <span class="text-stone-500 dark:text-stone-400">reprise à</span>
                          <span class="font-medium text-stone-800 dark:text-stone-200">
                            {m.rendu_par_nom ?? m.rendu_par}
                          </span>
                        {/if}
                        {#if m.rendu_par && m.confie_a}
                          <ArrowRight class="h-3.5 w-3.5 shrink-0 text-stone-400" />
                        {/if}
                        {#if m.confie_a}
                          <span class="text-stone-500 dark:text-stone-400">confiée à</span>
                          <span class="font-medium text-emerald-700 dark:text-emerald-400">
                            {m.confie_a_nom ?? m.confie_a}
                          </span>
                        {:else if m.rendu_par}
                          <span class="text-stone-400 dark:text-stone-500">
                            · en attente d'attribution
                          </span>
                        {/if}
                      </p>
                      <p class="mt-0.5 flex flex-wrap gap-x-3 text-xs text-stone-500 dark:text-stone-400">
                        <span class="font-mono">{m.serie}</span>
                        <span>{m.modele}</span>
                        {#if m.etiquette}
                          <span class="font-mono">étiquette {m.etiquette}</span>
                        {/if}
                      </p>
                      {#if m.motif_indisponible}
                        <p class="mt-1 text-xs text-amber-700 dark:text-amber-400">
                          {m.motif_indisponible}
                        </p>
                      {/if}
                      {#if noteEnEdition === m.serie}
                        <input
                          class="champ mt-1 w-full text-xs"
                          placeholder="Ce que tu décides de cette machine…"
                          bind:value={texteNote}
                          onblur={() => enregistrerNote(m.serie)}
                          onkeydown={(e) => {
                            if (e.key === "Enter") e.target.blur();
                            if (e.key === "Escape") noteEnEdition = null;
                          }}
                        />
                      {:else}
                        <button
                          class="mt-1 text-left text-xs text-stone-500 underline-offset-2
                                 hover:underline dark:text-stone-400"
                          onclick={() => ouvrirNote(m)}
                        >
                          {m.note ?? "+ ajouter une note"}
                        </button>
                      {/if}
                    </div>

                    <div class="shrink-0 text-right text-xs tabular-nums text-stone-500 dark:text-stone-400">
                      {#if m.rendu_le}<p>reprise le {jour(m.rendu_le)}</p>{/if}
                      {#if m.confie_le}<p>remise le {jour(m.confie_le)}</p>{/if}
                    </div>

                    <div class="flex shrink-0 flex-col gap-1">
                      {#if m.confie_a}
                        <button
                          class="rounded-md px-2 py-1 text-xs text-stone-500 transition
                                 hover:bg-stone-100 hover:text-red-700 dark:hover:bg-stone-700"
                          disabled={enCours === m.serie}
                          onclick={() =>
                            noter({ serie: m.serie, attribueA: "" },
                                  m.serie + " : attribution annulée")}
                        >
                          Annuler la remise
                        </button>
                      {/if}
                      {#if m.rendu_le}
                        <button
                          class="rounded-md px-2 py-1 text-xs text-stone-500 transition
                                 hover:bg-stone-100 hover:text-red-700 dark:hover:bg-stone-700"
                          disabled={enCours === m.serie}
                          onclick={() =>
                            noter({ serie: m.serie, recupere: false },
                                  m.serie + " : reprise annulée")}
                        >
                          Annuler la reprise
                        </button>
                      {/if}
                    </div>
                  </li>
                {/each}
              </ol>
            </div>
          {/if}

        {:else if vue === "parc"}
          <div class="flex flex-wrap items-center gap-2 px-4 py-3">
            <select class="champ text-xs" bind:value={filtreEtat} aria-label="Filtrer par état">
              <option value="">Tous les états</option>
              <option value="service">En service</option>
              <option value="dormant">En sommeil</option>
              <option value="desactive">Désactivées</option>
            </select>
            <select class="champ max-w-64 text-xs" bind:value={filtreOu} aria-label="Filtrer par emplacement">
              <option value="">Tous les emplacements</option>
              {#each ousDispo as o (o)}<option value={o}>{o}</option>{/each}
            </select>
            <select class="champ max-w-64 text-xs" bind:value={filtreModele} aria-label="Filtrer par modèle">
              <option value="">Tous les modèles</option>
              {#each modelesDispo as m (m)}<option value={m}>{m}</option>{/each}
            </select>
            {#if filtreEtat || filtreOu || filtreModele}
              <button
                class="rounded-md px-2 py-1 text-xs text-stone-500 transition hover:bg-stone-100
                       hover:text-stone-800 dark:hover:bg-stone-700 dark:hover:text-stone-200"
                onclick={() => { filtreEtat = ""; filtreOu = ""; filtreModele = ""; }}
              >
                Tout afficher
              </button>
            {/if}
            <span class="ml-auto text-xs tabular-nums text-stone-500 dark:text-stone-400">
              {parcFiltre.length} / {flotte.parc.total}
            </span>
          </div>

          <!-- La légende dit le code couleur une fois pour toutes, plutôt
               que de le faire deviner ligne par ligne. -->
          <div class="flex flex-wrap gap-x-5 gap-y-1 border-y border-stone-100 px-4 py-2 text-xs dark:border-stone-700/60">
            {#each ["attendu", "libre", "dormant", "actif", "hs"] as cle (cle)}
              <span class="flex items-center gap-1.5 text-stone-500 dark:text-stone-400">
                <span class="h-2 w-2 rounded-full {ETATS[cle].pastille}"></span>
                {ETATS[cle].texte}
              </span>
            {/each}
          </div>

          <div class="max-h-[30rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left"></th>
                  <th class="text-left">Étiquette</th>
                  <th class="text-left">Modèle</th>
                  <th class="text-left">N° de série</th>
                  <th class="text-left">Emplacement</th>
                  <th class="text-left">Dernière synchro</th>
                  <th class="text-left">État</th>
                </tr>
              </thead>
              <tbody>
                {#each parcFiltre.slice(0, 400) as a (a.serie)}
                  {@const e = ETATS[etatDe(a)]}
                  <tr class={e.ligne} title={a.lecture.join(" ")}>
                    <td class="py-1 pl-3 pr-0">
                      <Chromebook taille={30} etat={e.dessin} />
                    </td>
                    <td class="whitespace-nowrap font-mono text-xs">{a.etiquette || "—"}</td>
                    <td class="whitespace-nowrap text-xs text-stone-600 dark:text-stone-400">
                      {a.modele}
                    </td>
                    <td class="whitespace-nowrap font-mono text-xs">{a.serie}</td>
                    <td class="whitespace-nowrap text-xs text-stone-500 dark:text-stone-400">
                      {a.ou.replace("/1. Chromebooks/", "")}
                    </td>
                    <td class="whitespace-nowrap text-xs text-stone-500 dark:text-stone-400">
                      {jour(a.derniere_synchro)}
                    </td>
                    <td class="whitespace-nowrap text-xs {e.mot}">{e.texte}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
            {#if parcFiltre.length > 400}
              <p class="px-4 py-3 text-xs text-stone-500 dark:text-stone-400">
                400 premiers appareils affichés — affine les filtres pour voir
                les {parcFiltre.length - 400} autres.
              </p>
            {/if}
          </div>

        {:else if vue === "recherche"}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            Tu as la machine en main : tape son numéro de série, son étiquette,
            ou le nom de quelqu'un qui s'en est servi. Tu peux la marquer rendue
            même si son étiquette désigne quelqu'un d'autre — c'est justement le
            cas où elle ne sert à rien.
          </div>
          <div class="px-4 pb-3">
            <input
              class="champ w-full font-mono text-sm"
              placeholder="numéro de série, étiquette, adresse…"
              bind:value={recherche}
            />
          </div>
          {#if recherche.trim().length >= 3}
            <div class="max-h-[24rem] overflow-auto">
              <table class="tableau w-full text-sm">
                <thead>
                  <tr>
                    <th class="text-left">N° de série</th>
                    <th class="text-left">Étiquette</th>
                    <th class="text-left">Qui s'en sert</th>
                    <th class="text-left">Dernière synchro</th>
                    <th class="text-left">État</th>
                  </tr>
                </thead>
                <tbody>
                  {#each resultats as a (a.serie)}
                    <tr
                      class="cursor-pointer {a.dort ? 'ligne-douteuse' : ''}"
                      onclick={() => (detail = detail === a.serie ? null : a.serie)}
                    >
                      <td class="whitespace-nowrap font-mono text-xs">{a.serie}</td>
                      <td class="whitespace-nowrap font-mono text-xs">{a.etiquette}</td>
                      <td class="whitespace-nowrap font-mono text-xs">
                        {a.derniers_utilisateurs[0] ?? "—"}
                      </td>
                      <td class="whitespace-nowrap text-xs {a.dort ? 'text-amber-700 dark:text-amber-400' : 'text-stone-500'}">
                        {jour(a.derniere_synchro)}
                      </td>
                      <td class="whitespace-nowrap">
                        {#if a.statut !== "ACTIVE"}
                          <span class="text-xs text-stone-500 dark:text-stone-400">
                            désactivée
                          </span>
                        {/if}
                        {#if a.recupere_le}
                          <span class="text-xs text-emerald-700 dark:text-emerald-400">
                            rendue le {jour(a.recupere_le)}
                          </span>
                          <button
                            class="ml-2 text-xs text-stone-500 hover:text-red-600"
                            onclick={() =>
                              noter({ serie: a.serie, recupere: false },
                                    a.serie + " : restitution annulée")}
                          >
                            annuler
                          </button>
                        {:else if a.attribue_a}
                          <span class="text-xs text-stone-500">
                            confiée à {a.attribue_a}
                          </span>
                        {:else}
                          <Bouton
                            taille="sm"
                            occupe={enCours === a.serie}
                            onclick={(e) => {
                              e.stopPropagation();
                              noter({ serie: a.serie, recupere: true,
                                      recupereDe: a.porteur },
                                    a.serie + " notée rendue");
                            }}
                          >
                            Je l'ai récupérée
                          </Bouton>
                        {/if}
                      </td>
                    </tr>
                    {#if detail === a.serie}
                      <tr class="bg-stone-50/80 dark:bg-stone-800/50">
                        <td colspan="5" class="px-4 py-4">
                          <!-- La lecture d'abord : les champs sont dessous
                               pour la vérifier, pas pour la remplacer. -->
                          {#if a.lecture.length}
                            <div class="mb-4 space-y-1.5 border-l-2 border-emerald-400 pl-3
                                        dark:border-emerald-600">
                              {#each a.lecture as phrase}
                                <p class="max-w-3xl text-sm text-stone-700 dark:text-stone-300">
                                  {phrase}
                                </p>
                              {/each}
                            </div>
                          {/if}
                          <div class="flex items-start gap-5">
                            <Chromebook taille={64} etat={ETATS[etatDe(a)].dessin} classe="shrink-0" />

                            <div class="grid min-w-0 flex-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
                              <div>
                                <p class="libelle-champ">L'appareil</p>
                                <dl class="space-y-0.5 text-xs">
                                  <div class="flex gap-2">
                                    <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Statut</dt>
                                    <dd class={a.statut === "ACTIVE"
                                      ? "text-emerald-700 dark:text-emerald-400"
                                      : "text-red-700 dark:text-red-400"}>
                                      {STATUTS[a.statut] ?? a.statut}
                                    </dd>
                                  </div>
                                  <div class="flex gap-2">
                                    <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Modèle</dt>
                                    <dd>{a.modele}</dd>
                                  </div>
                                  <div class="flex gap-2">
                                    <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Vue</dt>
                                    <dd class={a.dort ? "text-amber-700 dark:text-amber-400" : ""}>
                                      {depuis(a.derniere_synchro)}
                                      {#if a.derniere_synchro}
                                        <span class="text-stone-400">({jour(a.derniere_synchro)})</span>
                                      {/if}
                                    </dd>
                                  </div>
                                  <div class="flex gap-2">
                                    <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Emplacement</dt>
                                    <dd class="min-w-0 break-all font-mono">{a.ou}</dd>
                                  </div>
                                </dl>
                              </div>

                              <div>
                                <p class="libelle-champ">Qui, selon qui</p>
                                <dl class="space-y-0.5 text-xs">
                                  <div class="flex gap-2">
                                    <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">Étiquette</dt>
                                    <dd class="min-w-0 break-all font-mono">
                                      {a.etiquette || "—"}
                                    </dd>
                                  </div>
                                  {#if a.porteur_code}
                                    <div class="flex gap-2">
                                      <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400"></dt>
                                      <dd class={a.porteur_en_poste
                                        ? "text-stone-500 dark:text-stone-400"
                                        : "text-red-700 dark:text-red-400"}>
                                        {a.porteur_en_poste
                                          ? "cette personne est toujours au tableau"
                                          : "cette personne est marquée sortante"}
                                      </dd>
                                    </div>
                                  {/if}
                                  {#if a.homonymes_etiquette > 0}
                                    <div class="flex gap-2">
                                      <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400"></dt>
                                      <dd class="text-amber-700 dark:text-amber-400">
                                        {a.homonymes_etiquette} autre(s) machine(s) portent
                                        la même étiquette
                                      </dd>
                                    </div>
                                  {/if}
                                  <div class="mt-1 flex gap-2">
                                    <dt class="w-24 shrink-0 text-stone-500 dark:text-stone-400">S'y connectent</dt>
                                    <dd class="min-w-0">
                                      {#if a.derniers_utilisateurs.length}
                                        <ul class="space-y-0.5">
                                          {#each a.derniers_utilisateurs.slice(0, 4) as u, i (u)}
                                            <li class="break-all font-mono {i === 0
                                              ? 'text-stone-800 dark:text-stone-200'
                                              : 'text-stone-400 dark:text-stone-500'}">
                                              {u}
                                            </li>
                                          {/each}
                                        </ul>
                                      {:else}
                                        <span class="text-stone-400">aucune connexion enregistrée</span>
                                      {/if}
                                    </dd>
                                  </div>
                                  {#if a.porteur && a.derniers_utilisateurs.length
                                       && !a.derniers_utilisateurs.includes(a.porteur)}
                                    <p class="mt-1 text-amber-700 dark:text-amber-400">
                                      L'étiquette et les connexions se contredisent : la
                                      machine a sans doute changé de mains sans qu'on la
                                      réétiquette.
                                    </p>
                                  {/if}
                                </dl>
                              </div>

                              <div>
                                <p class="libelle-champ">Ce que tu en as fait</p>
                                {#if a.recupere_le}
                                  <p class="text-xs text-emerald-700 dark:text-emerald-400">
                                    reprise le {jour(a.recupere_le)}
                                    {#if a.derniers_utilisateurs.length === 0}{/if}
                                  </p>
                                {/if}
                                {#if a.attribue_a}
                                  <p class="text-xs">
                                    confiée à <span class="font-mono">{a.attribue_a}</span>
                                  </p>
                                {/if}
                                {#if !a.recupere_le && !a.attribue_a}
                                  <p class="text-xs text-stone-400 dark:text-stone-500">
                                    Aucun mouvement noté. Si tu l'as en main, coche
                                    « je l'ai récupérée » pour en garder la trace.
                                  </p>
                                {/if}
                                {#if a.motif_indisponible}
                                  <p class="mt-1.5 text-xs text-amber-700 dark:text-amber-400">
                                    {a.motif_indisponible}
                                  </p>
                                {/if}
                                {#if a.libre}
                                  <p class="mt-1.5 text-xs text-emerald-700 dark:text-emerald-400">
                                    Disponible : tu peux l'attribuer depuis l'onglet
                                    « À équiper ».
                                  </p>
                                {/if}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    {/if}

                    {#if a.motif_indisponible || a.note || noteEnEdition === a.serie}
                      <tr>
                        <td colspan="5" class="px-3 pb-2 pt-0">
                          {#if a.motif_indisponible}
                            <p class="text-xs text-amber-700 dark:text-amber-400">
                              {a.motif_indisponible}
                            </p>
                          {/if}
                          {#if noteEnEdition === a.serie}
                            <input
                              class="champ mt-1 w-full text-xs"
                              placeholder="Ce que tu décides de cette machine…"
                              bind:value={texteNote}
                              onblur={() => enregistrerNote(a.serie)}
                              onkeydown={(e) => {
                                if (e.key === "Enter") e.target.blur();
                                if (e.key === "Escape") noteEnEdition = null;
                              }}
                            />
                          {:else}
                            <button
                              class="mt-0.5 text-left text-xs text-stone-500 underline-offset-2
                                     hover:underline dark:text-stone-400"
                              onclick={() => ouvrirNote(a)}
                            >
                              {a.note ?? "+ ajouter une note"}
                            </button>
                          {/if}
                        </td>
                      </tr>
                    {/if}
                  {/each}
                </tbody>
              </table>
            </div>
            {#if !resultats.length}
              <p class="px-4 pb-4 text-sm text-stone-500 dark:text-stone-400">
                Aucun appareil ne correspond. Le numéro de série est inscrit
                sous la machine, souvent précédé de « S/N ».
              </p>
            {/if}
          {/if}

        {:else if vue === "rapproches"}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            Ces enseignants ont été reliés à leur compte par une règle plus
            souple que l'égalité stricte : leur nom ne s'écrit pas pareil dans
            ton tableau et dans Google. Le rapprochement est appliqué, mais il
            s'affiche — un coup d'œil suffit à le démentir.
          </div>
          <div class="max-h-[28rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Dans ton tableau</th>
                  <th class="text-left">Compte retrouvé</th>
                  <th class="text-left">Par quelle règle</th>
                  <th class="text-right">Machines</th>
                </tr>
              </thead>
              <tbody>
                {#each flotte.rapproches as p (p.nom + p.prenom)}
                  <tr>
                    <td class="whitespace-nowrap font-medium">{p.prenom} {p.nom}</td>
                    <td class="whitespace-nowrap font-mono text-xs">{p.email}</td>
                    <td class="whitespace-nowrap text-xs text-stone-600 dark:text-stone-400">
                      {METHODES[p.methode] ?? p.methode}
                    </td>
                    <td class="text-right tabular-nums">{p.appareils.length || ""}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

        {:else if vue === "sans_compte"}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            Enseignants du tableau qu'aucun compte Google ne porte. Un arrivant
            attend sans doute la création du sien ; un enseignant en poste dans
            ce cas signale plutôt un écart à regarder — nom orthographié
            différemment d'un côté ou de l'autre, ou compte jamais créé.
          </div>
          <div class="max-h-[28rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Enseignant</th>
                  <th class="text-left">Discipline</th>
                  <th class="text-left">Situation</th>
                </tr>
              </thead>
              <tbody>
                {#each flotte.sans_compte as p (p.nom + p.prenom)}
                  <tr class:ligne-douteuse={p.code === "en_poste"}>
                    <td class="whitespace-nowrap font-medium">{p.prenom} {p.nom}</td>
                    <td class="whitespace-nowrap text-stone-600 dark:text-stone-400">{p.discipline}</td>
                    <td class="whitespace-nowrap text-xs">
                      {#if p.code === "arrivant"}
                        <span class="text-emerald-700 dark:text-emerald-400">
                          arrivant — compte à créer
                        </span>
                      {:else if p.code === "sortant"}
                        <span class="text-stone-500">sortant — compte sans doute déjà retiré</span>
                      {:else if p.code === "remplace"}
                        <span class="text-stone-500">remplacement — deux personnes sur la ligne</span>
                      {:else if p.homonymes.length}
                        <span class="text-amber-700 dark:text-amber-400">
                          plusieurs comptes possibles : {p.homonymes.join(", ")}
                        </span>
                      {:else}
                        <span class="text-amber-700 dark:text-amber-400">
                          en poste sans compte — à regarder
                        </span>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

        {:else}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            <TriangleAlert class="mr-1 inline h-3.5 w-3.5" />
            L'étiquette dit une chose, les connexions en disent une autre. Deux
            machines échangées se voient ici. Le programme ne tranche pas.
          </div>
          <div class="max-h-[28rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Étiquette</th>
                  <th class="text-left">Qui s'y connecte</th>
                  <th class="text-left">N° de série</th>
                </tr>
              </thead>
              <tbody>
                {#each flotte.discordances as d (d.appareil.serie)}
                  <tr class="ligne-douteuse">
                    <td class="whitespace-nowrap font-mono text-xs">{d.attendu}</td>
                    <td class="whitespace-nowrap font-mono text-xs">{d.constates.join(", ")}</td>
                    <td class="whitespace-nowrap font-mono text-xs">{d.appareil.serie}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</section>
