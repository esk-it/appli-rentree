<script>
  import { onMount } from "svelte";
  import UtensilsCrossed from "@lucide/svelte/icons/utensils-crossed";
  import ExternalLink from "@lucide/svelte/icons/external-link";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import KeyRound from "@lucide/svelte/icons/key-round";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import FileDown from "@lucide/svelte/icons/file-down";
  import Link2 from "@lucide/svelte/icons/link-2";
  import Pencil from "@lucide/svelte/icons/pencil";
  import Check from "@lucide/svelte/icons/check";
  import Bouton from "$lib/components/Bouton.svelte";
  import CopiableTexte from "$lib/components/CopiableTexte.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import Touche from "$lib/components/Touche.svelte";
  import { parametres } from "$lib/api.js";
  import { ouvrirLien } from "$lib/liens.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";
  import { notify } from "$lib/toasts.js";
  import {
    ICONES,
    IDENTIFIANT_SODEXO,
    LIEUX,
    PORTAIL_SODEXO,
    PROCEDURES,
    REGLAGE_CLASSEUR_ELEVES,
  } from "$lib/sodexo.js";

  /**
   * La procédure Sodexo, portée par le programme.
   *
   * ## Ce que cet écran montre, et pourquoi en images
   *
   * La procédure d'origine est illustrée : le logo de l'application où l'on
   * se trouve, les touches à frapper, l'icône exacte à cliquer. Lue en
   * texte seul, elle devient un mur de phrases où l'on perd sa ligne ;
   * illustrée, elle se parcourt.
   *
   * Les pictogrammes sont donc repris tels quels du document — un
   * engrenage reconnu se trouve à l'écran plus vite que « l'icône engrenage
   * du libellé Import comptes par badge » ne se lit.
   *
   * ## La chaîne d'abord
   *
   * Avant les gestes, le trajet : Charlemagne sort la liste, le classeur la
   * transforme, le portail l'avale. Trois logos et deux flèches portant
   * chacune le fichier qui passe. C'est ce qu'on oublie entre deux
   * rentrées, et ce qu'aucune liste à puces ne dit.
   */

  let idProcedure = $state(lire("sodexo.procedure", PROCEDURES[0].id));
  $effect(() => ecrire("sodexo.procedure", idProcedure));

  /** Adresse du classeur, telle qu'elle est enregistrée. */
  let urlClasseur = $state("");
  /** Saisie en cours — distincte, pour pouvoir annuler. */
  let saisie = $state("");
  let enEdition = $state(false);
  let enregistre = $state(false);

  let procedure = $derived(
    PROCEDURES.find((p) => p.id === idProcedure) ?? PROCEDURES[0],
  );

  /** Le trajet du fichier : un lieu par étape, le produit sur la flèche. */
  let chaine = $derived(
    procedure.etapes.map((e) => ({
      lieu: LIEUX[e.lieu],
      produit: e.produit ?? "",
    })),
  );

  onMount(async () => {
    try {
      const tous = await parametres.lister();
      const trouve = (tous ?? []).find((p) => p.cle === REGLAGE_CLASSEUR_ELEVES);
      urlClasseur = typeof trouve?.valeur === "string" ? trouve.valeur.trim() : "";
      saisie = urlClasseur;
    } catch {
      // Sans le réglage, il manque un bouton — la procédure reste lisible,
      // c'est l'essentiel.
    }
  });

  /**
   * L'adresse d'un lien : fixe pour le portail, réglable pour le classeur.
   */
  function adresse(l) {
    if (l.url) return l.url;
    if (l.reglage === REGLAGE_CLASSEUR_ELEVES) return urlClasseur || null;
    return null;
  }

  async function enregistrerClasseur() {
    const valeur = saisie.trim();
    if (valeur && !/^https?:\/\//i.test(valeur)) {
      notify.erreur("L'adresse doit commencer par https:// — colle celle de la barre du navigateur.");
      return;
    }
    enregistre = true;
    try {
      await parametres.mettreAJour(REGLAGE_CLASSEUR_ELEVES, valeur);
      urlClasseur = valeur;
      enEdition = false;
      notify.succes(valeur ? "Adresse du classeur enregistrée." : "Adresse effacée.");
    } catch (e) {
      notify.erreur(e instanceof Error ? e.message : String(e));
    } finally {
      enregistre = false;
    }
  }

  /**
   * Un lien qui ne s'ouvre pas doit dire pourquoi : « ça n'a pas marché »
   * oblige à tout rouvrir pour savoir ce qui a été refusé.
   */
  async function ouvrir(url) {
    const erreur = await ouvrirLien(url);
    if (erreur) notify.erreur(erreur, { duree: 12000 });
  }
</script>

<section class="space-y-5">
  <EnTetePage
    icon={UtensilsCrossed}
    titre="Sodexo"
    description="La procédure d'import, dans l'ordre, avec ses pièges. Le fichier se fabrique dans le classeur Google — le programme ne le refait pas, il t'y mène."
  />

  <Segments
    bind:valeur={idProcedure}
    options={PROCEDURES.map((p) => ({ id: p.id, label: p.titre }))}
  />

  <!-- ------------------------------------------------------------------
       Le trajet du fichier, avant les gestes.
       ------------------------------------------------------------------ -->
  <div class="card p-4">
    <p class="mb-3 text-sm text-stone-600 dark:text-stone-300">{procedure.resume}</p>
    <div class="flex flex-wrap items-center gap-x-1 gap-y-3">
      {#each chaine as maillon, i (maillon.lieu.nom)}
        <div class="flex items-center gap-2.5 rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 dark:border-stone-700 dark:bg-stone-900/50">
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white p-1 ring-1 ring-stone-200 dark:ring-stone-600">
            <img src={maillon.lieu.image} alt="" class="max-h-full max-w-full object-contain" />
          </span>
          <span class="text-sm font-medium whitespace-nowrap">{maillon.lieu.nom}</span>
        </div>

        {#if i < chaine.length - 1}
          <!-- La flèche porte le fichier qui passe d'un lieu à l'autre. -->
          <div class="flex items-center gap-1.5 px-1 text-stone-400">
            <ArrowRight class="h-4 w-4 shrink-0" />
            {#if maillon.produit}
              <span class="flex items-center gap-1 text-xs whitespace-nowrap text-stone-500 dark:text-stone-400">
                <FileDown class="h-3 w-3" />{maillon.produit}
              </span>
              <ArrowRight class="h-4 w-4 shrink-0" />
            {/if}
          </div>
        {/if}
      {/each}
    </div>
  </div>

  <!-- ------------------------------------------------------------------
       Les accès — sans le mot de passe, et c'est délibéré.
       ------------------------------------------------------------------ -->
  <div class="card flex flex-wrap items-center gap-x-6 gap-y-3 p-4">
    <div class="flex items-center gap-3">
      <span class="flex h-10 w-16 shrink-0 items-center justify-center rounded-lg bg-white p-1.5 ring-1 ring-stone-200 dark:ring-stone-600">
        <img src={LIEUX.portail.image} alt="Sodexo" class="max-h-full max-w-full object-contain" />
      </span>
      <Bouton taille="sm" icon={ExternalLink} onclick={() => ouvrir(PORTAIL_SODEXO)}>
        Ouvrir le portail
      </Bouton>
    </div>
    <div>
      <p class="libelle-champ">Identifiant</p>
      <CopiableTexte valeur={IDENTIFIANT_SODEXO} />
    </div>
    <div class="flex max-w-lg items-start gap-2 text-xs text-stone-500 dark:text-stone-400">
      <KeyRound class="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <p>
        Le mot de passe n'est pas écrit ici, et c'est délibéré : il partirait
        dans le dépôt et y resterait. Surtout, il deviendrait
        <strong>faux</strong> — la note d'origine de cette procédure en portait
        deux, dont un périmé depuis un changement.
      </p>
    </div>
  </div>

  <!-- ------------------------------------------------------------------
       Les étapes.
       ------------------------------------------------------------------ -->
  <div class="flex flex-col gap-3">
    {#each procedure.etapes as etape, i (etape.titre)}
      {@const lieu = LIEUX[etape.lieu]}
      <div class="card overflow-hidden p-4">
        <header class="flex items-center gap-3">
          <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white p-1.5 ring-1 ring-stone-200 dark:ring-stone-600">
            <img src={lieu.image} alt={lieu.nom} class="max-h-full max-w-full object-contain" />
          </span>
          <div class="min-w-0">
            <p class="text-[11px] font-medium tracking-wide text-stone-500 uppercase dark:text-stone-400">
              Étape {i + 1} · {lieu.nom}
            </p>
            <h2 class="text-lg font-semibold">{etape.titre}</h2>
          </div>
        </header>

        <!-- Les gestes, dans l'ordre. -->
        <ol class="mt-3 flex flex-col">
          {#each etape.gestes as geste, g (g)}
            <li class="flex gap-3 border-t border-stone-100 py-2 first:border-t-0 first:pt-0 dark:border-stone-700/60">
              <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-stone-100 font-mono text-[11px] text-stone-500 dark:bg-stone-700 dark:text-stone-400">
                {g + 1}
              </span>
              <div class="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1.5 text-sm">
                {#if geste.texte}
                  <span class="text-stone-700 dark:text-stone-200">{geste.texte}</span>
                {/if}

                {#if geste.icone}
                  <!-- L'icône exacte, telle qu'elle apparaît à l'écran. -->
                  {@const icone = ICONES[geste.icone]}
                  <span class="inline-flex items-center rounded-md bg-white px-1.5 py-1 ring-1 ring-stone-200 dark:ring-stone-600">
                    <img
                      src={icone.image}
                      alt={icone.alt}
                      class="{icone.hauteur} w-auto object-contain"
                    />
                  </span>
                {/if}

                {#if geste.chemin}
                  <!-- Un chemin de menus se clique, il ne se lit pas : on le
                       dessine comme la barre qu'il est. -->
                  <span class="inline-flex flex-wrap items-center gap-0.5 rounded-lg bg-stone-100 px-2 py-1 dark:bg-stone-900/60">
                    {#if geste.depuis}
                      <span class="pr-0.5 text-xs font-medium text-stone-500 dark:text-stone-400">
                        {geste.depuis}
                      </span>
                      <ChevronRight class="h-3 w-3 shrink-0 text-stone-400" />
                    {/if}
                    {#each geste.chemin as cran, c (cran)}
                      {#if c > 0}
                        <ChevronRight class="h-3 w-3 shrink-0 text-stone-400" />
                      {/if}
                      <span class="text-xs font-medium text-stone-700 dark:text-stone-200">{cran}</span>
                    {/each}
                  </span>
                {/if}

                {#if geste.cible}
                  <!-- L'intitulé exact : c'est ce qu'on compare à l'écran. -->
                  <span class="rounded-md border border-stone-300 bg-white px-2 py-0.5 text-xs font-medium text-stone-800 dark:border-stone-600 dark:bg-stone-900 dark:text-stone-100">
                    {geste.cible}
                  </span>
                {/if}

                {#if geste.touches}
                  <span class="inline-flex items-center gap-1.5">
                    {#each geste.touches as accord, a (a)}
                      {#if a > 0}
                        <span class="text-xs text-stone-400">puis</span>
                      {/if}
                      {#each accord as touche, t (touche)}
                        {#if t > 0}<span class="text-xs text-stone-400">+</span>{/if}
                        <Touche texte={touche} />
                      {/each}
                    {/each}
                  </span>
                {/if}
              </div>
            </li>
          {/each}
        </ol>

        {#if etape.produit}
          <p class="mt-2 flex items-center gap-1.5 text-xs text-emerald-800 dark:text-emerald-400">
            <FileDown class="h-3.5 w-3.5 shrink-0" />
            Il en sort <strong class="font-semibold">{etape.produit}</strong>
          </p>
        {/if}

        <!-- Les liens : le classeur se déclare ici, pas dans les réglages. -->
        {#if etape.liens?.length}
          <div class="mt-3 flex flex-wrap items-center gap-2">
            {#each etape.liens as l (l.libelle)}
              {@const url = adresse(l)}
              {#if url && !(enEdition && l.reglage)}
                <Bouton taille="sm" icon={ExternalLink} onclick={() => ouvrir(url)}>
                  {l.libelle}
                </Bouton>
                {#if l.reglage}
                  <button
                    class="flex items-center gap-1 text-xs text-stone-500 hover:text-emerald-700 dark:text-stone-400 dark:hover:text-emerald-400"
                    onclick={() => {
                      saisie = urlClasseur;
                      enEdition = true;
                    }}
                  >
                    <Pencil class="h-3 w-3" /> changer l'adresse
                  </button>
                {/if}
              {:else if l.reglage}
                <!-- Pas d'adresse connue : on la demande sur place. Renvoyer
                     vers les Paramètres obligerait à quitter la procédure au
                     milieu, puis à la retrouver. -->
                <div class="flex w-full flex-wrap items-end gap-2 rounded-lg border border-dashed border-stone-300 p-3 dark:border-stone-600">
                  <div class="min-w-64 flex-1">
                    <label class="libelle-champ" for="url-classeur">
                      Adresse du classeur « {l.libelle} »
                    </label>
                    <input
                      id="url-classeur"
                      class="champ mt-1"
                      placeholder="https://docs.google.com/spreadsheets/d/…"
                      bind:value={saisie}
                      onkeydown={(e) => e.key === "Enter" && enregistrerClasseur()}
                    />
                    <p class="mt-1 flex items-center gap-1 text-[11px] text-stone-500 dark:text-stone-400">
                      <Link2 class="h-3 w-3 shrink-0" />
                      Ouvre le classeur dans le navigateur et copie l'adresse de la barre. Elle est retenue.
                    </p>
                  </div>
                  <Bouton
                    taille="sm"
                    icon={Check}
                    onclick={enregistrerClasseur}
                    disabled={enregistre}
                  >
                    Enregistrer
                  </Bouton>
                  {#if urlClasseur}
                    <button
                      class="px-1 pb-2 text-xs text-stone-500 hover:underline dark:text-stone-400"
                      onclick={() => {
                        saisie = urlClasseur;
                        enEdition = false;
                      }}
                    >
                      annuler
                    </button>
                  {/if}
                </div>
              {/if}
            {/each}
          </div>
        {/if}

        {#if etape.pieges?.length}
          <div class="mt-3 rounded-lg border-l-4 border-l-amber-500 bg-amber-50 p-3 dark:bg-amber-900/25">
            <p class="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-amber-800 uppercase dark:text-amber-300">
              <AlertTriangle class="h-3.5 w-3.5" /> Ce qui peut mal tourner
            </p>
            <ul class="mt-1.5 flex flex-col gap-1.5">
              {#each etape.pieges as piege (piege)}
                <li class="text-sm leading-relaxed text-amber-900 dark:text-amber-200">
                  {piege}
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>
    {/each}
  </div>

  <!-- ------------------------------------------------------------------
       Le format attendu : à relire quand le portail refuse.
       ------------------------------------------------------------------ -->
  <div class="card p-4">
    <h2 class="titre-section">Le format que le portail attend</h2>
    <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
      À relire d'abord quand un import est refusé : neuf fois sur dix, c'est une
      colonne ou un séparateur.
    </p>

    <p class="mt-3 flex flex-wrap items-baseline gap-2 text-sm">
      <span class="text-xs font-medium tracking-wide text-stone-600 uppercase dark:text-stone-400">
        Fichier
      </span>
      <span class="font-mono">{procedure.memo.format}</span>
    </p>

    <p class="libelle-champ mt-3">Attributs, dans cet ordre</p>
    <div class="mt-1.5 flex flex-wrap items-center gap-1">
      {#each procedure.memo.attributs as attribut, a (attribut)}
        {#if a > 0}<span class="text-stone-300 dark:text-stone-600">·</span>{/if}
        <span class="badge-neutre">{attribut}</span>
      {/each}
    </div>

    {#if procedure.memo.regimes}
      <p class="libelle-champ mt-4">Valeurs du Code régime</p>
      <div class="mt-1.5 flex flex-wrap items-center gap-1.5">
        {#each procedure.memo.regimes.defaut as regime (regime)}
          <span class="badge-nouveau font-mono">{regime}</span>
        {/each}
        <span class="text-xs text-stone-500 dark:text-stone-400">par défaut — sinon</span>
        {#each procedure.memo.regimes.autres as regime (regime)}
          <span class="badge-neutre font-mono">{regime}</span>
        {/each}
      </div>
    {/if}
  </div>
</section>
