<script>
  import { onMount } from "svelte";
  import CreditCard from "@lucide/svelte/icons/credit-card";
  import Camera from "@lucide/svelte/icons/camera";
  import CameraOff from "@lucide/svelte/icons/camera-off";
  import Search from "@lucide/svelte/icons/search";
  import Download from "@lucide/svelte/icons/download";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import BedDouble from "@lucide/svelte/icons/bed-double";
  import GraduationCap from "@lucide/svelte/icons/graduation-cap";
  import Upload from "@lucide/svelte/icons/upload";
  import CheckSquare from "@lucide/svelte/icons/check-square";
  import Square from "@lucide/svelte/icons/square";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { cartes, enregistrerFichierBase64 } from "$lib/api.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";
  import { notify } from "$lib/toasts.js";

  /**
   * L'atelier des cartes — choisir qui, puis produire le fichier.
   *
   * ## Ce que cet écran remplace
   *
   * La version précédente réclamait un export de Charlemagne à chaque
   * utilisation, puis faisait **saisir des numéros de badge à la main** pour
   * désigner des élèves. Personne ne connaît par cœur le badge de Léa
   * Abalain, et le programme, lui, le connaît.
   *
   * Ici : on filtre par site et par classe, on coche dans une liste, on
   * produit. Le fichier sort du référentiel.
   *
   * ## Filtrer n'est pas cocher
   *
   * Les filtres décident de **ce qui est affiché**, les cases de **qui entre
   * dans le fichier**. Jamais l'un pour l'autre : un filtre qui décocherait
   * en douce ferait disparaître du fichier des élèves qu'on croyait dedans,
   * et cela ne se verrait qu'à l'impression. Le compteur affiche donc
   * toujours la sélection entière, y compris ce qu'on ne voit plus.
   *
   * ## La photo avant l'impression
   *
   * Une carte sans visage est une carte à refaire. L'état de la photo est
   * donc sur chaque ligne, **avant** de cocher, et non dans un rapport après
   * coup.
   */

  /** Le message d'une erreur remontée par l'API, sans le « Error: ». */
  const libelleErreur = (e) => String(e).replace(/^Error:\s*/, "");

  // Le relevé coûte une lecture du partage réseau — deux mille fichiers,
  // quelques secondes. On le garde donc entre deux passages sur l'écran, en
  // disant de quand il date : un état de photos vieux d'une heure reste vrai
  // pour choisir, et le redemander à chaque retour rendrait l'écran pénible.
  let candidats = $state(lire("cartes.candidats", /** @type {any[]} */ ([])));
  let releveA = $state(lire("cartes.releve", ""));
  let nbChambres = $state(lire("cartes.nbChambres", 77));
  let chargement = $state(false);
  let erreur = $state("");

  $effect(() => ecrire("cartes.candidats", candidats));
  $effect(() => ecrire("cartes.releve", releveA));
  $effect(() => ecrire("cartes.nbChambres", nbChambres));

  // La sélection survit à la navigation : on prépare une fournée de cartes en
  // plusieurs fois, et aller vérifier une photo ne doit pas tout défaire.
  let coches = $state(lire("cartes.coches", /** @type {number[]} */ ([])));
  let siteChoisi = $state(lire("cartes.site", ""));
  let classesChoisies = $state(lire("cartes.classes", /** @type {string[]} */ ([])));
  let recherche = $state("");
  let avecChambres = $state(lire("cartes.chambres", false));
  let intitule = $state("");
  let occupe = $state(false);

  $effect(() => ecrire("cartes.coches", coches));
  $effect(() => ecrire("cartes.site", siteChoisi));
  $effect(() => ecrire("cartes.classes", classesChoisies));
  $effect(() => ecrire("cartes.chambres", avecChambres));

  let ensembleCoche = $derived(new Set(coches));

  let sites = $derived(
    [...new Set(candidats.map((c) => c.site).filter(Boolean))].sort(),
  );

  /** Les classes du site choisi — sinon toutes. */
  let classesDuSite = $derived(
    [
      ...new Set(
        candidats
          .filter((c) => !siteChoisi || c.site === siteChoisi)
          .map((c) => c.classe),
      ),
    ].sort(),
  );

  let affiches = $derived.by(() => {
    const q = recherche.trim().toLowerCase();
    return candidats.filter((c) => {
      if (siteChoisi && c.site !== siteChoisi) return false;
      if (classesChoisies.length && !classesChoisies.includes(c.classe)) return false;
      if (q) {
        const foin = `${c.nom} ${c.prenom} ${c.classe} ${c.badge ?? ""}`.toLowerCase();
        if (!foin.includes(q)) return false;
      }
      return true;
    });
  });

  let nbAffichesCoches = $derived(
    affiches.filter((c) => ensembleCoche.has(c.personne_id)).length,
  );
  let selection = $derived(candidats.filter((c) => ensembleCoche.has(c.personne_id)));
  let selectionSansPhoto = $derived(selection.filter((c) => !c.a_une_photo));
  let selectionSansCodes = $derived(
    [...new Set(selection.filter((c) => !c.codes_connus).map((c) => c.classe))].sort(),
  );

  onMount(() => {
    if (!candidats.length) charger();
  });

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      const r = await cartes.candidats();
      candidats = r.candidats ?? [];
      nbChambres = r.nb_chambres ?? 77;
      releveA = new Date().toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
      });
      // Un élève parti entre deux visites ne doit pas rester coché dans
      // l'ombre : la sélection se rabat sur ce qui existe encore.
      const vivants = new Set(candidats.map((c) => c.personne_id));
      coches = coches.filter((id) => vivants.has(id));
    } catch (e) {
      erreur = libelleErreur(e);
    } finally {
      chargement = false;
    }
  }

  function basculer(id) {
    coches = ensembleCoche.has(id)
      ? coches.filter((x) => x !== id)
      : [...coches, id];
  }

  function cocherAffiches() {
    const ajout = affiches.map((c) => c.personne_id);
    coches = [...new Set([...coches, ...ajout])];
  }

  function decocherAffiches() {
    const retrait = new Set(affiches.map((c) => c.personne_id));
    coches = coches.filter((id) => !retrait.has(id));
  }

  /** Retirer de la sélection ceux dont la carte sortirait sans visage. */
  function retirerLesSansPhoto() {
    const sans = new Set(selectionSansPhoto.map((c) => c.personne_id));
    coches = coches.filter((id) => !sans.has(id));
  }

  function basculerClasse(classe) {
    classesChoisies = classesChoisies.includes(classe)
      ? classesChoisies.filter((c) => c !== classe)
      : [...classesChoisies, classe];
  }

  async function produire() {
    if (!coches.length) return;
    occupe = true;
    try {
      const r = await cartes.fichier({
        personneIds: coches,
        avecChambres,
        intitule,
      });
      const { chemin, annule } = await enregistrerFichierBase64(
        r.nom_fichier,
        r.contenu_base64,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      );
      if (annule) return;
      const details = [];
      if (r.nb_chambres) details.push(`${r.nb_chambres} chambres`);
      if (r.sans_photo?.length) details.push(`${r.sans_photo.length} sans photo`);
      notify.succes(
        `${r.nb_cartes} carte(s)${details.length ? ` — ${details.join(", ")}` : ""} — ` +
          (chemin ?? r.nom_fichier),
        { duree: 9000 },
      );
      if (r.classes_sans_codes?.length) {
        notify.avertissement(
          `Codes inconnus pour ${r.classes_sans_codes.join(", ")} — ces cartes ` +
            "sortent sans code niveau ni établissement.",
          { duree: 12000 },
        );
      }
    } catch (e) {
      notify.erreur(libelleErreur(e), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  async function apprendre(fichier) {
    if (!fichier) return;
    occupe = true;
    try {
      const r = await cartes.apprendre(fichier);
      notify.succes(
        `${r.classes_apprises.length} classe(s) renseignée(s), ` +
          `${r.nb_dates_apprises} date(s) d'entrée apprise(s).`,
        { duree: 9000 },
      );
      if (r.classes_inconnues?.length) {
        notify.avertissement(
          `Classes absentes de la table de correspondance : ${r.classes_inconnues.join(", ")}`,
          { duree: 12000 },
        );
      }
      await charger();
    } catch (e) {
      notify.erreur(libelleErreur(e), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }
</script>

<section class="space-y-4">
  <EnTetePage
    icon={CreditCard}
    titre="Les cartes"
    description="Coche les élèves dont tu veux les cartes, et le fichier d'import CardStudio sort du référentiel — photos comprises."
  />

  {#if erreur}
    <div class="card border-l-4 border-l-red-500 p-4 text-sm text-red-800 dark:text-red-300">
      {erreur}
    </div>
  {/if}

  {#if chargement && !candidats.length}
    <div class="card space-y-3 p-4">
      <p class="text-sm text-stone-600 dark:text-stone-300">
        Lecture du partage des photos — deux mille fichiers sur le réseau,
        quelques secondes. C'est ce qui permet de voir qui n'a pas de visage
        avant d'imprimer.
      </p>
      <Squelette nb={6} />
    </div>
  {:else if !candidats.length}
    <EtatVide
      icon={GraduationCap}
      titre="Aucun élève dans l'année en cours"
      message="Le référentiel doit d'abord recevoir un export Charlemagne."
    />
  {:else}
    <!-- ----------------------------------------------------------------
         Choisir : les filtres montrent, les cases décident.
         ---------------------------------------------------------------- -->
    <div class="card space-y-3 p-4">
      <div class="flex flex-wrap items-center gap-2">
        <span class="libelle-champ">Site</span>
        <button
          class="rounded-full border px-3 py-1 text-xs transition-colors {siteChoisi === ''
            ? 'border-emerald-500 bg-emerald-500 text-white'
            : 'border-stone-300 text-stone-600 hover:border-emerald-400 dark:border-stone-600 dark:text-stone-300'}"
          onclick={() => { siteChoisi = ""; classesChoisies = []; }}
        >
          Tous
        </button>
        {#each sites as s (s)}
          <button
            class="rounded-full border px-3 py-1 text-xs transition-colors {siteChoisi === s
              ? 'border-emerald-500 bg-emerald-500 text-white'
              : 'border-stone-300 text-stone-600 hover:border-emerald-400 dark:border-stone-600 dark:text-stone-300'}"
            onclick={() => { siteChoisi = s; classesChoisies = []; }}
          >
            {s}
          </button>
        {/each}

        <div class="relative ml-auto min-w-56">
          <Search class="pointer-events-none absolute top-2.5 left-2.5 h-3.5 w-3.5 text-stone-400" />
          <input
            class="champ !py-1.5 !pl-8 text-xs"
            placeholder="Un nom, une classe, un badge…"
            bind:value={recherche}
          />
        </div>
      </div>

      <div>
        <span class="libelle-champ">Classes</span>
        <div class="mt-1 flex max-h-28 flex-wrap gap-1.5 overflow-y-auto">
          {#each classesDuSite as c (c)}
            {@const dedans = classesChoisies.includes(c)}
            <button
              class="rounded-full border px-2 py-0.5 font-mono text-xs transition-colors {dedans
                ? 'border-emerald-500 bg-emerald-500 text-white'
                : 'border-stone-300 text-stone-600 hover:border-emerald-400 dark:border-stone-600 dark:text-stone-300'}"
              onclick={() => basculerClasse(c)}
            >
              {c}
            </button>
          {/each}
          {#if classesChoisies.length}
            <button
              class="text-xs text-stone-500 hover:text-red-600"
              onclick={() => (classesChoisies = [])}
            >
              × toutes
            </button>
          {/if}
        </div>
      </div>
    </div>

    <!-- ----------------------------------------------------------------
         La liste : c'est elle qui manquait.
         ---------------------------------------------------------------- -->
    <div class="card overflow-hidden">
      <div class="flex flex-wrap items-center gap-2 border-b border-stone-200 p-3 dark:border-stone-700">
        <p class="text-sm">
          <strong class="tabular-nums">{affiches.length}</strong>
          <span class="text-stone-500 dark:text-stone-400">
            affiché{affiches.length > 1 ? "s" : ""} · {nbAffichesCoches} coché{nbAffichesCoches > 1 ? "s" : ""}
          </span>
        </p>
        <Bouton taille="sm" icon={CheckSquare} onclick={cocherAffiches}>
          Tout cocher
        </Bouton>
        <Bouton taille="sm" icon={Square} onclick={decocherAffiches}>
          Tout décocher
        </Bouton>
        <div class="ml-auto flex items-center gap-2 text-xs text-stone-500 dark:text-stone-400">
          {#if releveA}<span>photos relevées à {releveA}</span>{/if}
          <Bouton taille="sm" icon={RefreshCw} occupe={chargement} onclick={charger}>
            Relire le partage
          </Bouton>
        </div>
      </div>

      <div class="max-h-[26rem] overflow-y-auto">
        {#if !affiches.length}
          <p class="p-6 text-center text-sm text-stone-500 dark:text-stone-400">
            Aucun élève ne correspond à ces filtres.
          </p>
        {:else}
          {#each affiches as c (c.personne_id)}
            {@const coche = ensembleCoche.has(c.personne_id)}
            <label
              class="flex cursor-pointer items-center gap-3 border-b border-stone-100 px-3 py-1.5 text-sm transition-colors last:border-b-0 hover:bg-emerald-50/50 dark:border-stone-800 dark:hover:bg-emerald-900/10"
            >
              <input
                type="checkbox"
                class="h-4 w-4 shrink-0 accent-emerald-600"
                checked={coche}
                onchange={() => basculer(c.personne_id)}
              />
              <span class="w-24 shrink-0 font-mono text-xs text-stone-500 dark:text-stone-400">
                {c.classe}
              </span>
              <span class="min-w-0 flex-1 truncate">
                <strong class="font-medium">{c.nom}</strong>
                {c.prenom}
              </span>
              <span class="w-16 shrink-0 text-right font-mono text-xs text-stone-500 tabular-nums dark:text-stone-400">
                {c.badge ?? ""}
              </span>
              {#if c.a_une_photo}
                <Camera class="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
              {:else}
                <span
                  class="flex shrink-0 items-center gap-1 text-xs text-amber-700 dark:text-amber-400"
                  title="Aucune photo sur le partage — la carte sortirait sans visage"
                >
                  <CameraOff class="h-4 w-4" /> sans photo
                </span>
              {/if}
            </label>
          {/each}
        {/if}
      </div>
    </div>

    <!-- ----------------------------------------------------------------
         Produire.
         ---------------------------------------------------------------- -->
    <div class="card space-y-3 p-4">
      <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
        <p class="text-sm">
          <strong class="tabular-nums text-emerald-700 dark:text-emerald-400">
            {selection.length}
          </strong>
          <span class="text-stone-600 dark:text-stone-300">
            carte{selection.length > 1 ? "s" : ""} au total
          </span>
          {#if selection.length !== affiches.length}
            <span class="text-xs text-stone-500 dark:text-stone-400">
              — filtres compris
            </span>
          {/if}
        </p>
        {#if coches.length}
          <button
            class="text-xs text-stone-500 hover:text-red-600 dark:text-stone-400"
            onclick={() => (coches = [])}
          >
            × vider la sélection
          </button>
        {/if}
      </div>

      {#if selectionSansPhoto.length}
        <div class="rounded-lg border-l-4 border-l-amber-500 bg-amber-50 p-3 dark:bg-amber-900/25">
          <p class="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-amber-800 uppercase dark:text-amber-300">
            <AlertTriangle class="h-3.5 w-3.5" />
            {selectionSansPhoto.length} carte{selectionSansPhoto.length > 1 ? "s" : ""} sans visage
          </p>
          <p class="mt-1 text-sm text-amber-900 dark:text-amber-200">
            {selectionSansPhoto.slice(0, 6).map((c) => `${c.nom} ${c.prenom}`).join(", ")}{selectionSansPhoto.length > 6 ? `, et ${selectionSansPhoto.length - 6} autres` : ""}.
            Le fichier sort quand même — c'est une carte à refaire, pas une erreur du programme.
          </p>
          <button
            class="mt-1.5 text-xs font-medium text-amber-800 underline dark:text-amber-300"
            onclick={retirerLesSansPhoto}
          >
            Les retirer de la sélection
          </button>
        </div>
      {/if}

      {#if selectionSansCodes.length}
        <div class="rounded-lg border-l-4 border-l-amber-500 bg-amber-50 p-3 dark:bg-amber-900/25">
          <p class="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-amber-800 uppercase dark:text-amber-300">
            <AlertTriangle class="h-3.5 w-3.5" /> Classes sans code niveau
          </p>
          <p class="mt-1 text-sm text-amber-900 dark:text-amber-200">
            <span class="font-mono">{selectionSansCodes.join(", ")}</span> — le code
            niveau et le code établissement sont des attributs de la classe, que
            seul Charlemagne connaît. Ils se renseignent dans le Référentiel, ou
            s'apprennent d'un export ci-dessous.
          </p>
        </div>
      {/if}

      <label class="flex cursor-pointer items-start gap-2 text-sm">
        <input type="checkbox" class="mt-0.5 accent-emerald-600" bind:checked={avecChambres} />
        <span class="text-stone-700 dark:text-stone-200">
          <BedDouble class="mr-1 inline h-4 w-4" />
          Ajouter les <strong class="tabular-nums">{nbChambres}</strong> lignes de chambre
          <span class="block text-xs text-stone-500 dark:text-stone-400">
            Les chambres de l'internat, en fin de fichier, comme Charlemagne les
            écrit. Elles ne portent pas d'élève — rien ne dit qui dort où — mais
            la liste, elle, ne change pas.
          </span>
        </span>
      </label>

      <div class="flex flex-wrap items-end gap-3">
        <div class="min-w-56 flex-1">
          <label class="libelle-champ" for="cartes-intitule">
            Intitulé du fichier (facultatif)
          </label>
          <input
            id="cartes-intitule"
            class="champ mt-1"
            placeholder="cartes oubliées, montée SU vers NDK…"
            bind:value={intitule}
          />
        </div>
        <Bouton
          variante="primary"
          icon={Download}
          occupe={occupe}
          disabled={!coches.length}
          onclick={produire}
        >
          Produire le fichier
        </Bouton>
      </div>
    </div>

    <!-- ----------------------------------------------------------------
         L'installation : une fois, puis plus jamais.
         ---------------------------------------------------------------- -->
    <details class="card p-4 text-sm">
      <summary class="cursor-pointer font-medium">
        Apprendre les codes de classe depuis un export Charlemagne
      </summary>
      <p class="mt-2 text-stone-600 dark:text-stone-300">
        Trois choses ne viennent pas du référentiel : le <strong>code niveau</strong>
        et le <strong>code établissement</strong> de chaque classe, et la
        <strong>date d'entrée</strong> de chaque élève — parfois sept ans en
        arrière. Un export CardStudio de Charlemagne passé <strong>une fois</strong>
        les enseigne au programme, qui n'en a plus besoin ensuite. À refaire
        seulement quand des classes apparaissent.
      </p>
      <label class="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-xs text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
        <Upload class="h-3.5 w-3.5" />
        Choisir l'export (.htm, .xls, .xlsx)
        <input
          type="file"
          accept=".htm,.html,.xlsx,.xls"
          class="hidden"
          onchange={(e) => {
            const champ = /** @type {HTMLInputElement} */ (e.target);
            apprendre(champ.files?.[0] ?? null);
            champ.value = "";
          }}
        />
      </label>
    </details>
  {/if}
</section>
