<script>
  import ChevronLeft from "@lucide/svelte/icons/chevron-left";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import Camera from "@lucide/svelte/icons/camera";
  import Radar from "@lucide/svelte/icons/radar";
  import Shuffle from "@lucide/svelte/icons/shuffle";
  import Avatar from "$lib/components/Avatar.svelte";
  import FilAriane from "$lib/components/FilAriane.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import CopiableTexte from "$lib/components/CopiableTexte.svelte";
  import Onglets from "$lib/components/Onglets.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { personnes } from "$lib/api.js";
  import { TEINTES } from "$lib/familles.js";
  import { notify } from "$lib/toasts.js";

  /**
   * La page d'une personne : où elle est, dans chaque système.
   *
   * ## Pourquoi une page, et non la ligne dépliée
   *
   * La fiche existait, repliée dans le tableau du Référentiel. Elle y tient
   * la largeur d'une ligne et se referme dès qu'on clique ailleurs — bon
   * pour jeter un œil, insuffisant pour travailler. Un écart entre KoXo et
   * le référentiel se corrige en plusieurs gestes, et chacun d'eux fermait
   * la fiche.
   *
   * ## Six systèmes, et trois façons de ne rien savoir
   *
   * Le tableau montre **six lignes**, et chacune dit *comment* elle sait,
   * ou pourquoi elle ne sait pas :
   *
   * - **Le référentiel** fait référence : c'est lui qu'on compare.
   * - **Google** s'interroge ici même, en direct, sur demande.
   * - **Charlemagne et KoXo** se comparent depuis la Concordance, qui
   *   demande un export frais. Ils ont une source ; elle n'est simplement
   *   pas branchée sur cette page.
   * - **PMB et Sodexo** n'ont aucune source : le programme leur écrit des
   *   fichiers, rien n'en revient.
   *
   * C'est le point de tout l'écran : **une absence de regard n'est pas une
   * absence d'écart**. Une ligne verte qu'on n'a pas vérifiée est pire
   * qu'une ligne grise, parce qu'elle rassure.
   *
   * @typedef {Object} Props
   * @property {number} personneId
   * @property {(page: string) => void} [onNaviguer]
   * @property {() => void} [onRetour]
   */
  /** @type {Props} */
  let { personneId, onNaviguer, onRetour } = $props();

  const libelleErreur = (e) => String(e).replace(/^Error:\s*/, "");

  let fiche = $state(/** @type {any} */ (null));
  let enquete = $state(/** @type {any} */ (null));
  let chargement = $state(true);
  let enqueteEnCours = $state(false);
  let erreur = $state("");
  let vue = $state("ensemble");

  /**
   * Les six systèmes, et d'où viendrait leur réponse.
   *
   * `lecture` vaut `ici` quand cette page sait interroger, `concordance`
   * quand la comparaison existe mais demande un export frais, `aucune`
   * quand rien ne revient du système. Confondre les deux derniers dirait
   * que Charlemagne n'a pas de source — alors que tout le référentiel en
   * vient.
   */
  const SYSTEMES = [
    { id: "referentiel", nom: "Référentiel", sigle: "Ré", teinte: TEINTES.annee, lecture: "reference" },
    { id: "charlemagne", nom: "Charlemagne", sigle: "Ch", teinte: TEINTES.rentree, lecture: "concordance" },
    { id: "google", nom: "Google", sigle: "G", teinte: TEINTES.google, lecture: "ici" },
    { id: "koxo", nom: "KoXo", sigle: "Ko", teinte: TEINTES.koxo, lecture: "concordance" },
    { id: "pmb", nom: "PMB", sigle: "PM", teinte: TEINTES.materiel, lecture: "aucune" },
    { id: "sodexo", nom: "Sodexo", sigle: "So", teinte: TEINTES.repas, lecture: "aucune" },
  ];

  $effect(() => {
    const id = personneId;
    if (!id) return;
    chargement = true;
    erreur = "";
    enquete = null;
    personnes
      .fiche(id)
      .then((f) => (fiche = f))
      .catch((e) => (erreur = libelleErreur(e)))
      .finally(() => (chargement = false));
  });

  /**
   * L'enquête part sur demande.
   *
   * Elle interroge l'annuaire en direct : deux appels pour une personne.
   * C'est peu, mais c'est un appel réseau — et un écran qui part sur le
   * réseau dès qu'on l'ouvre devient un écran qu'on n'ose plus ouvrir.
   */
  async function interroger() {
    enqueteEnCours = true;
    try {
      enquete = await personnes.enquete(personneId, { interrogerGoogle: true });
    } catch (e) {
      notify.erreur(libelleErreur(e), { duree: 12000 });
    } finally {
      enqueteEnCours = false;
    }
  }

  let p = $derived(fiche?.personne ?? null);
  let dires = $derived(
    Object.fromEntries((enquete?.dires ?? []).map((d) => [d.source, d])),
  );
  let nbEcarts = $derived(enquete?.divergences?.length ?? 0);

  /** Ce que chaque ligne du tableau affiche. */
  function ligne(s) {
    if (s.id === "referentiel") {
      const bouts = [];
      if (p?.classe) bouts.push(`Classe ${p.classe}`);
      if (p?.site) bouts.push(`Site ${p.site}`);
      return { valeur: bouts.join(" · ") || "—", etat: "reference", texte: "Référence" };
    }

    if (s.lecture === "aucune") {
      return {
        valeur: "Aucun export de ce système n'entre dans le programme",
        etat: "inconnu",
        texte: "Pas de source",
      };
    }

    if (s.lecture === "concordance") {
      return {
        valeur: "Se compare dans la Concordance, qui demande un export frais",
        etat: "inconnu",
        texte: "Pas vérifié",
        vers: "concordance",
      };
    }

    const d = dires[s.id];
    if (!d) {
      return { valeur: "—", etat: "inconnu", texte: "Pas vérifié" };
    }
    if (!d.consultee) {
      return { valeur: d.motif ?? "Non interrogé", etat: "inconnu", texte: "Pas vérifié" };
    }

    const ecart = (enquete?.divergences ?? []).find((x) => x.entre?.includes(s.id));
    const valeurs = Object.entries(d.valeurs ?? {})
      .filter(([, v]) => v)
      .map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`)
      .join(" · ");

    return ecart
      ? { valeur: `${ecart.quoi} : ${ecart.valeurs?.join(" ≠ ") ?? ""}`, etat: "ecart", texte: "Écart" }
      : { valeur: valeurs || "Rien à signaler", etat: "pret", texte: "Cohérent" };
  }
</script>

<section class="space-y-6">
  <FilAriane chemin={p ? [`${p.prenom} ${p.nom}`] : []} />

  <button
    class="flex items-center gap-1.5 text-sm text-stone-600 transition-colors hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-100"
    onclick={() => onRetour?.()}
  >
    <ChevronLeft class="h-4 w-4" /> Retour au référentiel
  </button>

  {#if erreur}
    <p class="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if chargement && !fiche}
    <Squelette variante="ligne-tableau" nb={6} colonnes={3} />
  {:else if p}
    <!-- L'identité, en tête. -->
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div class="flex min-w-0 items-center gap-5">
        <Avatar personneId={p.id} nom={p.nom} prenom={p.prenom} taille={76} />
        <div class="min-w-0">
          <h1 class="titre-affiche text-[32px] leading-tight">
            {p.prenom} <span class="uppercase">{p.nom}</span>
          </h1>
          <p class="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-stone-600 dark:text-stone-400">
            <span class="font-mono">{p.cle_pivot}</span>
            <span>·</span>
            <span>{p.type === "adulte" ? "Adulte" : "Élève"}</span>
            {#if p.classe}
              <span>·</span>
              <span class="font-semibold" style="color: {TEINTES.rentree};">{p.classe}</span>
            {/if}
            <span>·</span>
            <span>{p.site ? `Site ${p.site}` : "Sans site"}</span>
          </p>
        </div>
      </div>
      <div class="flex shrink-0 flex-wrap items-center gap-3">
        <Bouton icon={Radar} occupe={enqueteEnCours} onclick={interroger}>
          {enquete ? "Réinterroger" : "Interroger les systèmes"}
        </Bouton>
        <Bouton variante="primary" icon={Shuffle} onclick={() => onNaviguer?.("bouge")}>
          Changer de classe
        </Bouton>
      </div>
    </div>

    <Onglets
      bind:valeur={vue}
      onglets={[
        { id: "ensemble", label: "Vue d'ensemble" },
        { id: "historique", label: "Historique", compte: fiche.parcours.length },
        { id: "comptes", label: "Comptes", compte: fiche.comptes.length },
      ]}
    />

    {#if vue === "ensemble"}
      <div class="grid gap-16 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section>
          <div class="flex flex-wrap items-baseline justify-between gap-3">
            <h2 class="titre-affiche text-[22px]">Où est cette personne</h2>
            {#if enquete}
              <span
                class="text-[13px] font-semibold"
                style="color: {nbEcarts ? 'var(--color-red-700)' : TEINTES.koxo};"
              >
                {nbEcarts
                  ? `${nbEcarts} écart${nbEcarts > 1 ? "s" : ""} à corriger`
                  : "Aucun écart sur les sources lues"}
              </span>
            {:else}
              <span class="text-[13px] text-stone-500 dark:text-stone-400">
                Rien n'a encore été interrogé
              </span>
            {/if}
          </div>

          <div class="mt-4 grid grid-cols-[200px_minmax(0,1fr)_130px] items-center gap-4 border-b border-stone-200 py-2 dark:border-stone-800">
            <span class="libelle-champ">Système</span>
            <span class="libelle-champ">Valeur</span>
            <span class="libelle-champ">État</span>
          </div>

          {#each SYSTEMES as s (s.id)}
            {@const l = ligne(s)}
            <div
              class="grid grid-cols-[200px_minmax(0,1fr)_130px] items-center gap-4 border-b border-stone-100 py-3.5 dark:border-stone-800/70
                     {l.etat === 'ecart' ? 'bg-red-50/70 dark:bg-red-400/5' : ''}"
            >
              <span class="flex items-center gap-3 font-semibold">
                <span
                  class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                  style="background: {s.teinte};"
                  aria-hidden="true"
                >
                  {s.sigle}
                </span>
                {s.nom}
              </span>
              <span class="min-w-0 truncate text-sm text-stone-600 dark:text-stone-400">
                {l.valeur}
                {#if l.vers}
                  <button
                    class="ml-1 font-semibold hover:underline"
                    style="color: {TEINTES.koxo};"
                    onclick={() => onNaviguer?.(l.vers)}
                  >
                    Y aller →
                  </button>
                {/if}
              </span>
              <Pastille etat={l.etat} texte={l.texte} />
            </div>
          {/each}

          <p class="mt-3 max-w-3xl text-[13px] leading-relaxed text-stone-500 dark:text-stone-400">
            Charlemagne et KoXo <strong>ont</strong> une source : la Concordance
            les compare, avec un export frais. PMB et Sodexo n'en ont aucune —
            le programme leur écrit des fichiers, rien n'en revient. Ces deux
            lignes resteront grises tant qu'un export n'entrera pas ici, et
            c'est plus honnête qu'un vert qui rassurerait à tort.
          </p>
        </section>

        <aside class="space-y-8">
          <div>
            <p class="libelle-champ">Identifiants</p>
            <dl class="mt-2 space-y-2 text-sm">
              <div class="flex items-center justify-between gap-3">
                <dt class="text-stone-500 dark:text-stone-400">Login</dt>
                <dd><CopiableTexte valeur={p.login_constate ?? p.login} classe="font-mono text-xs" /></dd>
              </div>
              <div class="flex items-center justify-between gap-3">
                <dt class="text-stone-500 dark:text-stone-400">Badge</dt>
                <dd class="font-mono text-xs tabular-nums">{p.badge}</dd>
              </div>
              <div class="flex flex-col gap-1">
                <dt class="text-stone-500 dark:text-stone-400">Adresse</dt>
                <dd class="flex items-center gap-2">
                  <CopiableTexte valeur={p.email ?? "—"} classe="font-mono text-xs" />
                  {#if !p.email_est_constate}
                    <Pastille etat="attente" texte="calculée" />
                  {/if}
                </dd>
              </div>
            </dl>
            {#if !p.email_est_constate}
              <p class="mt-2 text-[11px] leading-relaxed text-stone-500 dark:text-stone-400">
                Calculée, non constatée : la formule tombe juste neuf fois sur
                dix. N'écris jamais sur cette adresse sans l'avoir vérifiée.
              </p>
            {/if}
          </div>

          <div>
            <p class="libelle-champ">Photo</p>
            <div class="mt-2.5 flex items-center gap-3.5">
              <span class="plaque-icone h-14 w-14" style="--teinte: {TEINTES.photos};">
                <Camera class="h-7 w-7" style="stroke-width: 1.6;" />
              </span>
              <div>
                <Pastille etat="inconnu" texte="Non relevée" />
                <p class="mt-1.5 text-[13px] text-stone-500 dark:text-stone-400">
                  Le partage se lit depuis l'écran Photos.
                </p>
              </div>
            </div>
          </div>

          <div>
            <p class="libelle-champ">Actions</p>
            {#each [["Voir les photos", "photos"], ["Refaire sa carte", "cartes"], ["Ce qui a été fait", "journal"]] as [texte, cible] (cible)}
              <button
                class="flex w-full items-center justify-between border-b border-stone-200 py-3 text-sm font-semibold transition-colors hover:text-stone-900 dark:border-stone-800 dark:hover:text-white"
                onclick={() => onNaviguer?.(cible)}
              >
                {texte}
                <ChevronRight class="h-4 w-4 text-stone-400" />
              </button>
            {/each}
          </div>
        </aside>
      </div>
    {:else if vue === "historique"}
      <div>
        <div class="grid grid-cols-[140px_minmax(0,1fr)_120px_120px] items-center gap-4 border-b border-stone-200 py-2 dark:border-stone-800">
          <span class="libelle-champ">Année</span>
          <span class="libelle-champ">Classe</span>
          <span class="libelle-champ">Niveau</span>
          <span class="libelle-champ">Régime</span>
        </div>
        {#each fiche.parcours as a (a.annee)}
          <div class="grid grid-cols-[140px_minmax(0,1fr)_120px_120px] items-center gap-4 border-b border-stone-100 py-2.5 text-sm dark:border-stone-800/70">
            <span class="font-semibold">{a.annee}</span>
            <span class="font-mono text-[13px]">{a.classe ?? "—"}</span>
            <span class="text-stone-600 dark:text-stone-400">{a.niveau ?? "—"}</span>
            <span class="text-stone-600 dark:text-stone-400">{a.regime ?? "—"}</span>
          </div>
        {/each}
        {#if !fiche.parcours.length}
          <p class="py-8 text-sm text-stone-500 dark:text-stone-400">
            Aucune année ingérée pour cette personne.
          </p>
        {/if}
      </div>
    {:else}
      <div>
        <div class="grid grid-cols-[140px_minmax(0,1fr)_140px] items-center gap-4 border-b border-stone-200 py-2 dark:border-stone-800">
          <span class="libelle-champ">Cible</span>
          <span class="libelle-champ">Unité appliquée</span>
          <span class="libelle-champ">État</span>
        </div>
        {#each fiche.comptes as c (c.cible)}
          <div class="grid grid-cols-[140px_minmax(0,1fr)_140px] items-center gap-4 border-b border-stone-100 py-2.5 text-sm dark:border-stone-800/70">
            <span class="font-semibold">{c.cible}</span>
            <span class="min-w-0 truncate font-mono text-[13px] text-stone-600 dark:text-stone-400">
              {c.ou_appliquee ?? c.ou_constatee ?? "—"}
            </span>
            <Pastille
              etat={c.etat === "actif" ? "pret" : c.etat === "suspendu" ? "attente" : "inconnu"}
              texte={c.etat}
            />
          </div>
        {/each}
        {#if !fiche.comptes.length}
          <p class="py-8 text-sm text-stone-500 dark:text-stone-400">
            Aucun compte suivi pour cette personne.
          </p>
        {/if}
      </div>
    {/if}
  {/if}
</section>
