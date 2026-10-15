<script>
  import { untrack } from "svelte";
  import Check from "@lucide/svelte/icons/check";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import Eye from "@lucide/svelte/icons/eye";
  import FlaskConical from "@lucide/svelte/icons/flask-conical";
  import { repetition } from "$lib/repetition.svelte.js";
  import Bouton from "$lib/components/Bouton.svelte";
  import BandeChapitres from "./BandeChapitres.svelte";
  import KoxoImport from "./schemas/KoxoImport.svelte";
  import KoxoExport from "./schemas/KoxoExport.svelte";
  import CaptureAttendue from "./schemas/CaptureAttendue.svelte";
  import Repere from "./schemas/Repere.svelte";
  import { CONTENU, gesteCourant } from "$lib/rentree/etapes.js";
  import { rentreeApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Une étape de la rentrée, geste par geste (maquettes 7B, 7C, 7F).
   *
   * À gauche, les gestes : celui en cours est ouvert, les autres se
   * taisent. À droite, ce qui sert à le faire — l'outil du programme,
   * embarqué, ou le schéma du logiciel où cliquer — et, au-dessus, ce qui
   * se constate : avant, maintenant. En bas, un seul bouton qui dit
   * exactement ce qu'il fait : « C'est importé dans KoXo NDK », puis
   * « Valider ».
   *
   * La validation relit les mesures et refuse tant qu'un écart bloque —
   * à moins d'en dire la raison, gardée avec l'étape.
   *
   * En visite (avant le 1er juillet), rien n'est lu ni enregistré, et aucun
   * outil n'est lancé : on lit le chemin.
   *
   * @typedef {Object} Props
   * @property {any} etat               - la campagne
   * @property {string} etapeId
   * @property {boolean} [visite]
   * @property {Record<string, {composant: any, label: string, props?: Record<string, any>}>} outils
   * @property {(etat: any) => void} onEtat
   * @property {(vue: any) => void} onAller
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { etat, etapeId, visite = false, outils, onEtat, onAller, onNaviguer } = $props();

  const SCHEMAS = { koxo_import: KoxoImport, koxo_export: KoxoExport };
  const libelle = (e) => String(e).replace(/^Error:\s*/, "");

  let etape = $derived(etat.etapes.find((e) => e.id === etapeId));
  let contenu = $derived(CONTENU[etapeId]);
  let chapitre = $derived(etat.chapitres.find((c) => c.id === etape?.chapitre));
  let rangChapitre = $derived(etat.chapitres.findIndex((c) => c.id === etape?.chapitre) + 1);
  let suivante = $derived(etat.etapes[etape?.rang ?? 99] ?? null);
  let precedente = $derived(etat.etapes[(etape?.rang ?? 1) - 2] ?? null);

  let mesures = $state(/** @type {any[]|null} */ (null));
  let lecture = $state(false);
  let lectureGoogle = $state(false);
  let action = $state(/** @type {string|null} */ (null));
  let faits = $state(/** @type {string[]} */ ([]));
  let gesteVu = $state(/** @type {string|null} */ (null));
  let refus = $state(/** @type {string|null} */ (null));
  let forcer = $state(false);
  let note = $state("");

  let courant = $derived(gesteCourant(contenu, faits));
  let tousFaits = $derived(courant === null);
  let affiche = $derived(
    contenu?.gestes.find((g) => g.id === gesteVu) ?? courant ?? contenu?.gestes.at(-1),
  );
  let iAffiche = $derived(contenu?.gestes.indexOf(affiche) ?? 0);
  let finie = $derived(etape?.statut === "validee" || etape?.statut === "reportee");
  let googleALire = $derived((mesures ?? []).some((m) => m.source === "google" && m.valeur === null));
  let ecartBloquant = $derived((mesures ?? []).some((m) => m.bloquante && m.bonne !== true));

  // Une autre étape : on repart de zéro, et on relève ses mesures.
  $effect(() => {
    const id = etapeId;
    untrack(() => {
      faits = [...(etape?.gestes ?? [])];
      gesteVu = null;
      refus = null;
      forcer = false;
      note = "";
      mesures = null;
      if (!visite && etape && etape.statut !== "fermee") relever(id, false);
    });
  });

  function remplacerEtape(e) {
    onEtat({ ...etat, etapes: etat.etapes.map((x) => (x.id === e.id ? e : x)) });
  }

  async function relever(id, google) {
    if (google) lectureGoogle = true;
    else lecture = true;
    try {
      const r = await rentreeApi.ouvrir(id, { annee: etat.annee, google });
      if (id !== etapeId) return;
      mesures = r.mesures;
      remplacerEtape(r.etape);
    } catch (e) {
      notify.erreur(libelle(e), { duree: 10000 });
    } finally {
      lecture = false;
      lectureGoogle = false;
    }
  }

  async function declarer(geste, fait = true) {
    action = "declarer";
    try {
      faits = await rentreeApi.declarer(etapeId, { annee: etat.annee, geste: geste.id, fait });
      remplacerEtape({ ...etape, gestes: faits });
      gesteVu = null;
      relever(etapeId, false);
    } catch (e) {
      notify.erreur(libelle(e));
    } finally {
      action = null;
    }
  }

  function apres(nouvel) {
    onEtat(nouvel);
    const fini = (id) => {
      const e = nouvel.etapes.find((x) => x.id === id);
      return e && (e.statut === "validee" || e.statut === "reportee");
    };
    const duChapitre = nouvel.etapes.filter((x) => x.chapitre === etape.chapitre);
    if (duChapitre.every((x) => fini(x.id))) onAller({ type: "fin", chapitre: etape.chapitre });
    else if (suivante) onAller({ type: "etape", id: suivante.id });
  }

  async function valider() {
    action = "valider";
    refus = null;
    try {
      const nouvel = await rentreeApi.valider(etapeId, {
        annee: etat.annee,
        forcer,
        note: forcer ? note : null,
      });
      notify.succes(`« ${etape.titre} » est validée.`);
      apres(nouvel);
    } catch (e) {
      refus = libelle(e).replace(/^Pas encore : /, "");
    } finally {
      action = null;
    }
  }

  async function reporter() {
    action = "reporter";
    try {
      const nouvel = await rentreeApi.reporter(etapeId, {
        annee: etat.annee,
        note: etape.pas_avant ? "À faire à partir du 1er septembre." : null,
      });
      apres(nouvel);
    } catch (e) {
      notify.erreur(libelle(e));
    } finally {
      action = null;
    }
  }

  async function rouvrir() {
    action = "rouvrir";
    try {
      onEtat(await rentreeApi.rouvrir(etapeId, { annee: etat.annee }));
      relever(etapeId, false);
    } catch (e) {
      notify.erreur(libelle(e));
    } finally {
      action = null;
    }
  }

  /** « Utilisateurs › Importer ①, … » : les chiffres cerclés deviennent des repères. */
  const CERCLES = "①②③④⑤⑥";
  const morceaux = (texte) =>
    texte.split(new RegExp(`([${CERCLES}])`)).map((m) =>
      CERCLES.includes(m) && m ? { repere: CERCLES.indexOf(m) + 1 } : { texte: m },
    );

  const logicielDe = (g) =>
    g.schema?.startsWith("koxo") ? "KoXo" : (g.capture ?? "").split(" :")[0] || "ce logiciel";

  const heure = (iso) => (iso ? iso.slice(11, 16).replace(":", " h ") : "");
  const jour = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "");

  const valeurDe = (photo) => (photo && photo.valeur !== undefined && photo.valeur !== null ? photo.valeur : null);
  const nombre = (n) => (n === null || n === undefined ? "—" : new Intl.NumberFormat("fr-FR").format(n));
</script>

{#if etape && contenu && chapitre}
  <div
    class="flex min-h-[calc(100vh-9rem)] flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-950"
    style="--chap: {chapitre.couleur};"
  >
    <!-- Où l'on est -->
    <header class="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-stone-200 px-6 py-3 lg:px-10 dark:border-stone-800">
      <nav aria-label="Fil d'Ariane" class="flex min-w-0 items-center gap-2 text-sm text-stone-500 dark:text-stone-400">
        <button type="button" class="hover:text-stone-900 hover:underline dark:hover:text-stone-100" onclick={() => onAller({ type: "fil" })}>
          La rentrée {etat.annee}
        </button>
        <span aria-hidden="true">›</span>
        <span class="chap-texte truncate font-bold">{rangChapitre} · {chapitre.titre}</span>
      </nav>
      <div class="flex items-center gap-4">
        <div class="w-44"><BandeChapitres chapitres={etat.chapitres} etapes={etat.etapes} actif={chapitre.id} libelles={false} /></div>
        <span class="text-sm whitespace-nowrap text-stone-500 dark:text-stone-400">Étape <b class="text-stone-900 dark:text-stone-100">{etape.rang}</b> sur {etat.etapes.length}</span>
      </div>
    </header>

    {#if visite}
      <p class="flex items-center gap-2 border-b border-stone-200 bg-stone-50 px-6 py-2.5 text-sm text-stone-600 lg:px-10 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-300">
        <Eye class="h-4 w-4 shrink-0" />
        Visite : rien n'est lu ni enregistré, aucun outil n'est lancé. La rentrée {etat.annee} s'ouvre le {jour(etat.s_ouvre_le)}/{etat.s_ouvre_le.slice(0, 4)}.
      </p>
    {/if}

    <div class="grid flex-1 2xl:grid-cols-[440px_minmax(0,1fr)]">
      <!-- Les gestes, un par un : celui en cours est ouvert, les autres se taisent -->
      <section class="flex flex-col px-6 py-7 lg:px-10 2xl:border-r 2xl:border-stone-200 2xl:dark:border-stone-800">
        <div class="flex flex-wrap items-center gap-3">
          <span class="chap-fond chap-texte rounded-full px-3 py-1 text-xs font-bold">{contenu.duree}</span>
          {#if etape.statut === "validee"}
            <span class="inline-flex items-center gap-1 rounded-full bg-vert-100 px-3 py-1 text-xs font-bold text-vert-700 dark:bg-vert-900/50 dark:text-vert-300">
              <Check class="h-3.5 w-3.5" /> Validée le {jour(etape.validee_le)} à {heure(etape.validee_le)}
            </span>
          {:else if etape.statut === "reportee"}
            <span class="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">Reportée</span>
          {/if}
        </div>
        <h1 class="titre-affiche mt-3 text-[32px] leading-tight text-balance text-stone-900 dark:text-stone-100">{etape.titre}</h1>
        <p class="mt-2 text-[15px] leading-relaxed text-stone-600 dark:text-stone-300">{contenu.but}</p>
        {#if etape.note}
          <p class="mt-3 text-sm text-stone-500 dark:text-stone-400"><b>Note :</b> {etape.note}</p>
        {/if}

        <ol class="mt-6">
          {#each contenu.gestes as g, i (g.id)}
            {@const fait = faits.includes(g.id)}
            {@const ouvert = g.id === affiche.id}
            <li class="grid grid-cols-[30px_minmax(0,1fr)] gap-3.5">
              <div class="flex flex-col items-center">
                <button
                  type="button"
                  aria-label="Geste {i + 1} : {g.titre}{fait ? ' (fait)' : ''}"
                  class="grid h-[30px] w-[30px] shrink-0 place-items-center rounded-full text-[13px] font-extrabold transition-transform hover:scale-105
                    {fait ? 'chap-plein text-white' : ouvert ? 'chap-anneau chap-texte border-[3px] bg-white dark:bg-stone-950' : 'border-2 border-stone-300 bg-white text-stone-400 dark:border-stone-700 dark:bg-stone-950'}"
                  onclick={() => (gesteVu = g.id)}
                >
                  {#if fait}<Check class="h-4 w-4" strokeWidth={3} />{:else}{i + 1}{/if}
                </button>
                {#if i < contenu.gestes.length - 1}
                  <span class="mt-1 w-0.5 flex-1 {fait ? 'chap-plein' : 'bg-stone-200 dark:bg-stone-800'}"></span>
                {/if}
              </div>
              <div class="min-w-0 pb-5">
                {#if ouvert}
                  <div class="chap-fond rounded-2xl px-4 py-3.5">
                    <p class="chap-texte text-base font-extrabold">{g.titre}</p>
                    <ol class="mt-2.5 flex list-decimal flex-col gap-1.5 pl-5 text-sm leading-normal text-stone-700 dark:text-stone-200">
                      {#each g.consignes as c, j (j)}
                        <li>
                          {#each morceaux(c) as m, k (k)}{#if m.repere}<Repere n={m.repere} petit />{:else}{m.texte}{/if}{/each}
                        </li>
                      {/each}
                    </ol>
                    {#if repetition.active && (g.ecrit || g.google || g.enRepetition)}
                      <p class="mt-3 flex gap-2 rounded-lg bg-amber-100 px-3 py-2 text-[13px] leading-snug text-amber-950 dark:bg-amber-900/40 dark:text-amber-100">
                        <FlaskConical class="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        {#if g.ecrit}
                          Répétition : ne le fais pas dans {logicielDe(g)}, ce serait pour de vrai. Dis seulement que c'est fait.
                        {:else if g.google}
                          Répétition : l'outil lit Google et montre ce qu'il ferait ; appliquer est refusé. Valide ensuite l'étape en disant pourquoi.
                        {:else}
                          {g.enRepetition}
                        {/if}
                      </p>
                    {/if}
                    {#if fait && etape.gestes_le?.[g.id]}
                      <p class="mt-2.5 text-xs text-stone-500 dark:text-stone-400">Fait le {jour(etape.gestes_le[g.id])} à {heure(etape.gestes_le[g.id])}.</p>
                    {/if}
                  </div>
                {:else}
                  <button type="button" class="block text-left" onclick={() => (gesteVu = g.id)}>
                    <span class="text-[15px] font-bold {fait ? 'text-stone-900 dark:text-stone-100' : 'text-stone-400 dark:text-stone-500'}">{g.titre}</span>
                    {#if fait && etape.gestes_le?.[g.id]}
                      <span class="mt-0.5 block text-[13px] text-stone-500 dark:text-stone-400">Fait le {jour(etape.gestes_le[g.id])} à {heure(etape.gestes_le[g.id])}</span>
                    {:else if g.type === "externe"}
                      <span class="mt-0.5 block text-[13px] text-stone-400 dark:text-stone-500">Dans {logicielDe(g)}</span>
                    {/if}
                  </button>
                {/if}
              </div>
            </li>
          {/each}
        </ol>

        {#if contenu.pieges?.length}
          <div class="mt-auto rounded-2xl bg-amber-50 px-4 py-3.5 dark:bg-amber-950/30">
            <p class="flex items-center gap-2 text-[11px] font-bold tracking-[0.08em] text-amber-800 uppercase dark:text-amber-300">
              <AlertTriangle class="h-3.5 w-3.5" /> {contenu.pieges.length > 1 ? "Les pièges" : "Le piège"}
            </p>
            <ul class="mt-1.5 flex flex-col gap-1.5 text-sm leading-normal text-amber-950 dark:text-amber-100">
              {#each contenu.pieges as p, i (i)}<li>{p}</li>{/each}
            </ul>
          </div>
        {/if}
      </section>

      <!-- Ce qui se constate, et ce qui sert à faire le geste -->
      <section class="flex min-w-0 flex-col gap-7 border-t border-stone-200 bg-stone-50/70 px-6 py-7 lg:px-10 2xl:border-t-0 dark:border-stone-800 dark:bg-stone-900/40">
        {#if !visite && (mesures?.length || lecture)}
          <div>
            <div class="flex flex-wrap items-center justify-between gap-3">
              <h2 class="libelle-champ">{finie ? "Avant / après" : "Avant / maintenant"}</h2>
              <div class="flex items-center gap-2">
                {#if googleALire}
                  <Bouton taille="sm" variante="primary" icon={RefreshCw} occupe={lectureGoogle} onclick={() => relever(etapeId, true)}>Relire dans Google</Bouton>
                {/if}
                <Bouton taille="sm" icon={RefreshCw} occupe={lecture} onclick={() => relever(etapeId, false)}>Relire</Bouton>
              </div>
            </div>
            {#if mesures}
              <div class="mt-2 overflow-x-auto">
                <table class="w-full text-sm tabular-nums">
                  <thead>
                    <tr class="text-left text-xs text-stone-500 dark:text-stone-400">
                      <th class="py-2 pr-4 font-semibold">Ce qu'on regarde</th>
                      <th class="w-24 py-2 pr-4 text-right font-semibold">Avant</th>
                      {#if finie}<th class="w-24 py-2 pr-4 text-right font-semibold">Après</th>{/if}
                      <th class="w-28 py-2 pr-4 text-right font-semibold">Maintenant</th>
                      <th class="w-32 py-2 font-semibold"><span class="sr-only">État</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each mesures as m (m.id)}
                      <tr class="border-t border-stone-200 align-top dark:border-stone-800">
                        <td class="py-2.5 pr-4">
                          <span class="font-semibold text-stone-900 dark:text-stone-100">{m.libelle}</span>
                          <span class="mt-0.5 block text-[13px] text-stone-500 dark:text-stone-400">{m.detail}</span>
                        </td>
                        <td class="py-2.5 pr-4 text-right text-stone-500 dark:text-stone-400">{nombre(valeurDe(etape.avant?.[m.id]))}</td>
                        {#if finie}<td class="py-2.5 pr-4 text-right text-stone-700 dark:text-stone-300">{nombre(valeurDe(etape.apres?.[m.id]))}</td>{/if}
                        <td class="py-2.5 pr-4 text-right text-base font-extrabold text-stone-900 dark:text-stone-100">{m.valeur === null ? "?" : nombre(m.valeur)}</td>
                        <td class="py-2.5 text-xs font-bold">
                          {#if m.bonne === true}
                            <span class="inline-flex items-center gap-1 text-vert-700 dark:text-vert-300"><Check class="h-3.5 w-3.5" /> bon</span>
                          {:else if m.bonne === null}
                            <span class="text-stone-500 dark:text-stone-400">à lire</span>
                          {:else if m.bloquante}
                            <span class="text-red-700 dark:text-red-400">bloque</span>
                          {:else}
                            <span class="text-amber-700 dark:text-amber-400">à surveiller</span>
                          {/if}
                        </td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Un geste peut passer par un autre logiciel puis par le programme :
             exporter de KoXo, puis déposer l'export ici. -->
        <div class="flex min-w-0 flex-col gap-4">
          {#if (affiche.schema && SCHEMAS[affiche.schema]) || (affiche.type === "externe" && affiche.capture)}
            <h2 class="libelle-champ">Où cliquer dans {logicielDe(affiche)}</h2>
            {#if affiche.schema && SCHEMAS[affiche.schema]}
              {@const Schema = SCHEMAS[affiche.schema]}
              {#key affiche.id}<Schema {...affiche.schemaProps ?? {}} />{/key}
            {:else}
              <CaptureAttendue capture={affiche.capture} />
            {/if}
            {#if affiche.attendu}
              <div class="grid gap-3 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-baseline">
                <span class="text-xs text-stone-500 dark:text-stone-400">Le programme attend</span>
                <p class="titre-affiche text-xl text-stone-900 dark:text-stone-100">{affiche.attendu}</p>
              </div>
            {/if}
          {/if}
          {#if affiche.outil}
            {@const entree = outils[affiche.outil.page]}
            <h2 class="libelle-champ {affiche.schema ? 'mt-4' : ''}">{affiche.schema ? "Puis dans le programme" : "Dans le programme"}{entree ? ` · ${entree.label}` : ""}</h2>
            {#if visite || !entree}
              <div class="grid min-h-[160px] place-items-center rounded-xl border-2 border-dashed border-stone-300 px-6 text-center text-sm text-stone-500 dark:border-stone-700 dark:text-stone-400">
                {visite ? `Ici s'ouvrira « ${entree?.label ?? affiche.outil.page} », le jour venu.` : "Cet outil n'est pas disponible ici."}
              </div>
            {:else if etape.statut === "fermee"}
              <p class="text-sm text-stone-500">L'outil s'ouvrira avec l'étape.</p>
            {:else}
              {@const Outil = entree.composant}
              {#key affiche.id}
                <div class="min-w-0">
                  <Outil {...entree.props ?? {}} {...affiche.outil.props ?? {}} {onNaviguer} />
                </div>
              {/key}
            {/if}
          {/if}
        </div>
      </section>
    </div>

    {#if refus}
      <div class="border-t border-amber-300 bg-amber-50 px-6 py-4 lg:px-10 dark:border-amber-800 dark:bg-amber-950/30" role="alert">
        <p class="font-bold text-amber-900 dark:text-amber-200">Pas encore validée</p>
        <p class="mt-1 text-sm text-amber-900 dark:text-amber-100">{refus}</p>
        {#if !forcer}
          <button type="button" class="mt-2 text-sm font-semibold text-amber-900 underline dark:text-amber-200" onclick={() => (forcer = true)}>
            Valider quand même, en disant pourquoi
          </button>
        {:else}
          <div class="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
            <label class="min-w-0 flex-1">
              <span class="libelle-champ">Pourquoi valider malgré l'écart ? (gardé avec l'étape)</span>
              <input class="champ mt-1" bind:value={note} placeholder="Les 2 élèves partis restent à ranger lundi" />
            </label>
            <Bouton variante="danger" occupe={action === "valider"} disabled={!note.trim()} onclick={valider}>Valider malgré l'écart</Bouton>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Un seul bouton, qui dit ce qu'il fait -->
    <footer class="sticky bottom-0 flex flex-wrap items-center justify-between gap-4 border-t border-stone-200 bg-white/95 px-6 py-4 backdrop-blur lg:px-10 dark:border-stone-800 dark:bg-stone-950/95">
      <p class="text-sm text-stone-500 dark:text-stone-400">
        {#if visite}
          Étape <b class="text-stone-900 dark:text-stone-100">{etape.rang}</b> sur {etat.etapes.length} · geste {iAffiche + 1} sur {contenu.gestes.length}
        {:else if finie}
          {etape.statut === "validee" ? "Validée" : "Reportée"} — tu peux la rouvrir si quelque chose est à refaire.
        {:else if etape.statut === "fermee"}
          Cette étape s'ouvrira quand la précédente sera validée.
        {:else if !tousFaits}
          Geste <b class="text-stone-900 dark:text-stone-100">{iAffiche + 1}</b> sur {contenu.gestes.length} ·
          {affiche.type === "externe" ? `le programme ne voit pas ${logicielDe(affiche)} : dis-lui quand c'est fait` : "fais-le dans l'outil, puis dis-le"}
        {:else if mesures && !ecartBloquant}
          Tout est constaté : tu peux valider.
        {:else}
          Valider relit ce qui se constate, et dit ce qui manque s'il manque quelque chose.
        {/if}
      </p>
      <div class="flex flex-wrap items-center gap-4">
        {#if visite}
          {#if iAffiche > 0}
            <button type="button" class="text-sm font-semibold text-stone-700 hover:underline dark:text-stone-200" onclick={() => (gesteVu = contenu.gestes[iAffiche - 1].id)}>← Geste précédent</button>
          {:else if precedente}
            <button type="button" class="text-sm font-semibold text-stone-700 hover:underline dark:text-stone-200" onclick={() => onAller({ type: "etape", id: precedente.id })}>← Étape {precedente.rang}</button>
          {/if}
          {#if iAffiche < contenu.gestes.length - 1}
            <button type="button" class="chap-bouton" onclick={() => (gesteVu = contenu.gestes[iAffiche + 1].id)}>Geste suivant →</button>
          {:else if suivante}
            <button type="button" class="chap-bouton" onclick={() => onAller({ type: "etape", id: suivante.id })}>Étape {suivante.rang} : {suivante.titre} →</button>
          {:else}
            <button type="button" class="chap-bouton" onclick={() => onAller({ type: "fil" })}>Revenir au fil →</button>
          {/if}
        {:else if finie}
          <Bouton occupe={action === "rouvrir"} onclick={rouvrir}>{etape.statut === "validee" ? "Rouvrir l'étape" : "La reprendre maintenant"}</Bouton>
          {#if suivante}
            <button type="button" class="chap-bouton" onclick={() => onAller({ type: "etape", id: suivante.id })}>Étape {suivante.rang} →</button>
          {:else}
            <button type="button" class="chap-bouton" onclick={() => onAller({ type: "fin", chapitre: etape.chapitre })}>Le bilan →</button>
          {/if}
        {:else if etape.statut !== "fermee"}
          {#if iAffiche > 0}
            <button type="button" class="text-sm font-semibold text-stone-700 hover:underline dark:text-stone-200" onclick={() => (gesteVu = contenu.gestes[iAffiche - 1].id)}>← Geste précédent</button>
          {/if}
          {#if faits.includes(affiche.id)}
            <button type="button" class="text-sm text-stone-500 hover:underline dark:text-stone-400" onclick={() => declarer(affiche, false)}>Pas fait, en fait</button>
          {/if}
          {#if etape.reportable}
            <Bouton occupe={action === "reporter"} onclick={reporter}>La faire plus tard</Bouton>
          {/if}
          {#if !tousFaits && !faits.includes(affiche.id)}
            <button type="button" class="chap-bouton" disabled={action !== null} onclick={() => declarer(affiche)}>{affiche.fait} →</button>
          {:else if !tousFaits}
            <button type="button" class="chap-bouton" onclick={() => (gesteVu = courant?.id ?? null)}>Geste suivant →</button>
          {:else}
            <button type="button" class="chap-bouton" disabled={action !== null} onclick={valider}>
              {action === "valider" ? "Je relis…" : suivante && suivante.chapitre === etape.chapitre ? `Valider et passer à l'étape ${suivante.rang} →` : "Valider et finir le chapitre →"}
            </button>
          {/if}
        {:else}
          <button type="button" class="chap-bouton" onclick={() => onAller({ type: "etape", id: etat.courante })}>Aller à l'étape en cours →</button>
        {/if}
      </div>
    </footer>
  </div>
{/if}

<style>
  /* La couleur du chapitre, partout où l'étape parle d'elle-même. */
  .chap-fond {
    background: color-mix(in srgb, var(--chap) 11%, transparent);
  }
  .chap-texte {
    color: color-mix(in srgb, var(--chap) 62%, black);
  }
  :global(.dark) .chap-texte {
    color: color-mix(in srgb, var(--chap) 55%, white);
  }
  .chap-plein {
    background: color-mix(in srgb, var(--chap) 80%, black);
  }
  .chap-anneau {
    border-color: color-mix(in srgb, var(--chap) 80%, black);
  }
  .chap-bouton {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.8rem 1.6rem;
    font-size: 15px;
    font-weight: 700;
    color: white;
    background: color-mix(in srgb, var(--chap) 58%, black);
    transition: transform 150ms, filter 150ms;
  }
  .chap-bouton:hover {
    filter: brightness(1.12);
  }
  .chap-bouton:active {
    transform: scale(0.97);
  }
  .chap-bouton:focus-visible {
    outline: 2px solid var(--chap);
    outline-offset: 3px;
  }
  .chap-bouton:disabled {
    opacity: 0.5;
    pointer-events: none;
  }
</style>
