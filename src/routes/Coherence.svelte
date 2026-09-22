<script>
  /**
   * Les six systèmes, et l'état du lien qui les rattache au référentiel.
   *
   * ## Pourquoi un schéma plutôt qu'un tableau
   *
   * La question posée ici n'est pas « combien d'écarts » mais « qu'est-ce
   * que je n'ai pas vérifié ». Un tableau range les lignes par nom et
   * laisse la réponse à l'addition ; un schéma la donne d'un regard — les
   * traits en pointillé sont ceux qu'on n'a pas regardés.
   *
   * Le référentiel est au centre parce qu'il est la référence : chaque
   * autre système se compare à lui, jamais deux satellites entre eux.
   *
   * ## Trois liens qu'on ne saura pas vérifier
   *
   * PMB, Sodexo et CardStudio reçoivent des fichiers du programme et n'en
   * rendent aucun. Leur trait reste gris — pas « pas encore fait », mais
   * « pas de source ». Les confondre ferait croire qu'il suffit de
   * relancer un croisement, alors qu'il faudrait d'abord obtenir un
   * export de ces trois-là.
   *
   * Ils sont montrés quand même : les cacher ferait croire que l'école
   * tient en quatre systèmes, et c'est faux.
   *
   * ## L'écran ne croise rien
   *
   * Croiser demande un export Charlemagne frais, l'annuaire Google, et
   * une bonne minute. Le faire à l'ouverture rendrait insupportable le
   * seul geste qu'on fait le plus souvent ici — regarder. L'écran lit ce
   * que le dernier croisement a laissé, avec sa date, et mène à la
   * Concordance quand il faut recommencer.
   */
  import { onMount } from "svelte";
  import Network from "@lucide/svelte/icons/network";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Upload from "@lucide/svelte/icons/upload";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { TEINTES } from "$lib/familles.js";
  import { concordance as concordanceApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let { onNaviguer } = $props();

  let donnees = $state(/** @type {any} */ (null));
  let chargement = $state(true);
  let choisi = $state("charlemagne");

  /**
   * Le tour du schéma, dans le sens des aiguilles depuis le haut.
   *
   * L'ordre n'est pas décoratif : Charlemagne en haut parce que tout
   * part de lui, puis les deux systèmes qu'on sait lire (Google, KoXo),
   * puis les trois qu'on ne sait qu'alimenter. Le regard descend des
   * liens vivants vers les liens muets.
   */
  const SYSTEMES = [
    { id: "charlemagne", nom: "Charlemagne", sigle: "Ch", angle: -90, teinte: TEINTES.rentree },
    // « Google », pas « Google Workspace » : le nom complet déborde sur la
    // pastille voisine, et le schéma n'a pas à répéter ce que l'encadré dit.
    { id: "google", nom: "Google", sigle: "G", angle: -30, teinte: TEINTES.google },
    { id: "koxo", nom: "KoXo", sigle: "Ko", angle: 30, teinte: TEINTES.koxo },
    { id: "pmb", nom: "PMB", sigle: "PM", angle: 90, teinte: TEINTES.materiel },
    { id: "sodexo", nom: "Sodexo", sigle: "So", angle: 150, teinte: TEINTES.repas },
    { id: "cardstudio", nom: "CardStudio", sigle: "Ca", angle: 210, teinte: TEINTES.photos },
  ];

  /** Le schéma, en coordonnées. Calculées, pour qu'un angle suffise. */
  const CX = 310;
  const CY = 300;
  const R_CENTRE = 88;
  const R_SATELLITE = 32;
  const R_ORBITE = 196;
  const R_LEGENDE = R_ORBITE + R_SATELLITE + 22;

  /**
   * Vert, ambre, gris — et le vert n'est pas `emerald`.
   *
   * L'échelle `emerald` a été reteintée en violet, qui est l'accent du
   * programme : un schéma qui code l'état par la couleur montrerait du
   * violet là où il dit « cohérent », et la légende mentirait. Le vert
   * est une échelle à lui — `vert`, dans la feuille de style — et non la
   * teinte de KoXo, qu'on lirait comme le nom d'un système.
   */
  const VERT = "var(--color-vert-500)";
  const COULEURS = {
    coherent: VERT,
    ecarts: "var(--color-amber-500)",
    non_verifie: "var(--color-stone-400)",
    sans_source: "var(--color-stone-400)",
  };

  const MOTS = {
    coherent: "Cohérent",
    ecarts: "Écarts",
    non_verifie: "Pas encore vérifié",
    sans_source: "Pas de source",
  };

  /** Les genres d'écart, dits en français plutôt qu'en clé. */
  const LIBELLES = {
    referentiel: "Classe différente du référentiel",
    google: "Unité d'une autre classe",
    groupe: "Groupe d'une autre classe",
    hors_arbre_de_classe: "Compte pas encore basculé",
    sans_compte: "Sans compte Google",
    koxo: "Classe différente dans KoXo",
    absent_koxo: "Absent de la base KoXo",
  };

  function position(angle, rayon) {
    const rad = (angle * Math.PI) / 180;
    return { x: CX + rayon * Math.cos(rad), y: CY + rayon * Math.sin(rad) };
  }

  let liens = $derived(
    SYSTEMES.map((s) => {
      const d = (donnees?.liens ?? []).find((l) => l.systeme === s.id);
      const etat = d?.etat ?? "non_verifie";
      const rad = (s.angle * Math.PI) / 180;
      const centre = position(s.angle, R_ORBITE);
      return {
        ...s,
        ...(d ?? { libelle: s.id, nb_ecarts: 0, nb_absents: 0, details: [] }),
        etat,
        centre,
        // Le rayon place le texte du bon côté ; il ne dit pas de combien
        // un bloc de deux lignes déborde. Sur les diagonales, sans ce
        // décalage vertical, « Google » passait sur sa propre pastille.
        legende: (() => {
          const pt = position(s.angle, R_LEGENDE);
          return { x: pt.x, y: pt.y + (Math.sin(rad) < 0 ? -22 : 22) };
        })(),
        // Le trait s'arrête au bord de chaque cercle, jamais dessous :
        // un trait qui passe sous une pastille se lit comme une flèche.
        depart: {
          x: CX + R_CENTRE * Math.cos(rad),
          y: CY + R_CENTRE * Math.sin(rad),
        },
        arrivee: {
          x: centre.x - R_SATELLITE * Math.cos(rad),
          y: centre.y - R_SATELLITE * Math.sin(rad),
        },
      };
    }),
  );

  let ouvert = $derived(liens.find((l) => l.systeme === choisi) ?? liens[0]);

  let nbAVerifier = $derived(
    liens.filter((l) => l.etat === "non_verifie").length,
  );
  let nbEnEcart = $derived(liens.filter((l) => l.etat === "ecarts").length);

  onMount(charger);

  async function charger() {
    chargement = true;
    try {
      donnees = await concordanceApi.liens();
      // S'ouvrir sur ce qui cloche : un écran qui s'ouvre sur un lien
      // vert laisserait le seul lien rouge à découvrir.
      const enEcart = donnees.liens.find((l) => l.etat === "ecarts");
      choisi = enEcart?.systeme ?? "charlemagne";
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      chargement = false;
    }
  }

  /** « il y a deux heures », plutôt qu'un horodatage à déchiffrer. */
  function age(iso) {
    if (!iso) return "";
    const s = Math.round((Date.now() - new Date(iso + "Z").getTime()) / 1000);
    if (s < 90) return "à l'instant";
    const m = Math.round(s / 60);
    if (m < 60) return `il y a ${m} min`;
    const h = Math.round(m / 60);
    if (h < 24) return `il y a ${h} h`;
    const j = Math.round(h / 24);
    return j === 1 ? "hier" : `il y a ${j} jours`;
  }

  const nombre = (n) => (n ?? 0).toLocaleString("fr-FR");
</script>

<section class="space-y-6">
  <EnTetePage
    icon={Network}
    titre="Cohérence entre les systèmes"
    description="Le référentiel est la référence. Chaque lien dit où il diverge."
  >
    {#snippet actions()}
      <Bouton icon={RefreshCw} onclick={charger} occupe={chargement}>
        Relire
      </Bouton>
      <Bouton variante="primary" icon={Upload} onclick={() => onNaviguer?.("concordance")}>
        Croiser les sources
      </Bouton>
    {/snippet}
  </EnTetePage>

  {#if chargement && !donnees}
    <Squelette variante="carte" nb={2} />
  {:else if donnees}
    <!-- ------------------------------------------------------------------
         La légende. Trois traits, trois mots — et jamais la couleur seule.
         ------------------------------------------------------------------ -->
    <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
      {#each ["coherent", "ecarts", "non_verifie"] as e (e)}
        <span class="flex items-center gap-2 text-xs text-stone-600 dark:text-stone-400">
          <svg width="26" height="8" aria-hidden="true">
            <line
              x1="1" y1="4" x2="25" y2="4"
              stroke={COULEURS[e]}
              stroke-width="2.5"
              stroke-linecap="round"
              stroke-dasharray={e === "non_verifie" ? "4 4" : undefined}
            />
          </svg>
          {MOTS[e]}
        </span>
      {/each}
      {#if nbAVerifier}
        <span class="ml-auto text-xs text-stone-500 dark:text-stone-400">
          <strong class="text-stone-800 dark:text-stone-200">{nbAVerifier}</strong>
          lien{nbAVerifier > 1 ? "s" : ""} sur {liens.length} sans comparaison
        </span>
      {/if}
    </div>

    <div class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
      <!-- ----------------------------------------------------------------
           Le schéma.
           ---------------------------------------------------------------- -->
      <div class="card p-2">
        <svg
          viewBox="0 0 620 620"
          class="mx-auto block w-full max-w-[620px]"
          role="img"
          aria-label="Le référentiel au centre, six systèmes autour, chaque trait coloré selon l'état de la comparaison"
        >
          <!-- Les traits d'abord : ils passent sous les pastilles. -->
          {#each liens as l (l.id)}
            <line
              x1={l.depart.x} y1={l.depart.y}
              x2={l.arrivee.x} y2={l.arrivee.y}
              stroke={COULEURS[l.etat]}
              stroke-width={l.systeme === ouvert?.systeme ? 5 : 2.5}
              stroke-linecap="round"
              stroke-dasharray={l.etat === "non_verifie" || l.etat === "sans_source"
                ? "5 6"
                : undefined}
              opacity={l.systeme === ouvert?.systeme ? 1 : 0.75}
            />
          {/each}

          <!-- Le centre : le référentiel, et ce qu'il contient. -->
          <circle cx={CX} cy={CY} r={R_CENTRE} fill={TEINTES.annee} />
          <text
            x={CX} y={CY - 22}
            text-anchor="middle"
            class="fill-white text-[11px] font-bold tracking-[0.08em] uppercase"
          >
            Référentiel
          </text>
          <text
            x={CX} y={CY + 14}
            text-anchor="middle"
            class="fill-white text-[34px] font-bold tabular-nums"
            style="font-family: var(--font-display);"
          >
            {nombre(donnees.nb_personnes)}
          </text>
          <text x={CX} y={CY + 36} text-anchor="middle" class="fill-white/80 text-[11px]">
            {nombre(donnees.nb_eleves)} élèves · {nombre(donnees.nb_adultes)} adultes
          </text>

          <!-- Les satellites. Cliquables : c'est le seul geste de l'écran. -->
          {#each liens as l (l.id)}
            <g
              role="button"
              tabindex="0"
              class="cursor-pointer outline-none"
              onclick={() => (choisi = l.systeme)}
              onkeydown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  choisi = l.systeme;
                }
              }}
            >
              <circle
                cx={l.centre.x} cy={l.centre.y}
                r={R_SATELLITE + (l.systeme === ouvert?.systeme ? 5 : 0)}
                fill={l.etat === "sans_source" || l.etat === "non_verifie"
                  ? "transparent"
                  : l.teinte}
                stroke={l.teinte}
                stroke-width="2.5"
                stroke-dasharray={l.etat === "sans_source" || l.etat === "non_verifie"
                  ? "5 5"
                  : undefined}
                opacity={l.etat === "sans_source" ? 0.5 : 1}
                class="transition-all"
              />
              <text
                x={l.centre.x} y={l.centre.y + 5}
                text-anchor="middle"
                class="pointer-events-none text-[15px] font-bold"
                fill={l.etat === "sans_source" || l.etat === "non_verifie"
                  ? l.teinte
                  : "#fff"}
                opacity={l.etat === "sans_source" ? 0.6 : 1}
              >
                {l.sigle}
              </text>

              <text
                x={l.legende.x} y={l.legende.y}
                text-anchor="middle"
                class="fill-stone-800 text-[13px] font-semibold dark:fill-stone-100"
              >
                {l.nom}
              </text>
              <text
                x={l.legende.x} y={l.legende.y + 15}
                text-anchor="middle"
                class="fill-stone-500 text-[11px] dark:fill-stone-400"
              >
                {#if l.etat === "ecarts"}
                  {nombre(l.nb_ecarts + l.nb_absents)} écart{l.nb_ecarts + l.nb_absents > 1 ? "s" : ""}
                {:else}
                  {MOTS[l.etat]}
                {/if}
              </text>
            </g>
          {/each}
        </svg>
      </div>

      <!-- ----------------------------------------------------------------
           Le lien ouvert, en détail.
           ---------------------------------------------------------------- -->
      {#if ouvert}
        <aside class="space-y-4">
          <div>
            <p class="libelle-champ">Référentiel ↔ {ouvert.libelle}</p>
            {#if ouvert.etat === "ecarts"}
              <p
                class="titre-affiche mt-1 text-2xl leading-tight"
                style="color: var(--color-amber-600);"
              >
                {nombre(ouvert.nb_ecarts + ouvert.nb_absents)} écart{ouvert.nb_ecarts + ouvert.nb_absents > 1 ? "s" : ""} à regarder
              </p>
            {:else if ouvert.etat === "coherent"}
              <p
                class="titre-affiche mt-1 text-2xl leading-tight"
                style="color: {VERT};"
              >
                Tout concorde
              </p>
            {:else}
              <p class="titre-affiche mt-1 text-2xl leading-tight text-stone-500">
                {MOTS[ouvert.etat]}
              </p>
            {/if}
            {#if ouvert.verifie_le}
              <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
                Comparé {age(ouvert.verifie_le)} sur
                <strong class="tabular-nums">{nombre(ouvert.nb_verifies)}</strong>
                personnes.
              </p>
            {/if}
          </div>

          {#if ouvert.details?.length}
            <div class="filet"></div>
            <div class="space-y-1">
              {#each ouvert.details as d (d.genre)}
                <button
                  type="button"
                  class="flex w-full items-center gap-3 rounded-xl px-2 py-2.5 text-left transition-colors hover:bg-stone-100 dark:hover:bg-stone-800"
                  onclick={() => onNaviguer?.("concordance")}
                >
                  <span
                    class="titre-affiche w-14 shrink-0 text-right text-2xl leading-none tabular-nums"
                    style="color: {ouvert.teinte};"
                  >
                    {nombre(d.nb)}
                  </span>
                  <span class="min-w-0 flex-1 text-sm text-stone-700 dark:text-stone-300">
                    {LIBELLES[d.genre] ?? d.genre}
                  </span>
                  <ArrowRight class="h-4 w-4 shrink-0 text-stone-400" />
                </button>
              {/each}
            </div>
          {/if}

          {#if ouvert.pourquoi}
            <p class="rounded-xl bg-stone-100 p-3 text-[13px] leading-relaxed text-stone-600 dark:bg-stone-800/60 dark:text-stone-300">
              {ouvert.pourquoi}
            </p>
          {/if}

          {#if ouvert.etat !== "sans_source"}
            <div class="space-y-3">
              <p class="text-[13px] leading-relaxed text-stone-600 dark:text-stone-400">
                Cette comparaison demande un export Charlemagne frais : elle ne
                peut pas tourner toute seule.
              </p>
              <Bouton
                variante="primary"
                icon={Upload}
                onclick={() => onNaviguer?.("concordance")}
              >
                Charger un export Charlemagne
              </Bouton>
            </div>
          {/if}
        </aside>
      {/if}
    </div>

    {#if nbEnEcart === 0 && nbAVerifier === 0}
      <p class="text-sm text-stone-600 dark:text-stone-400">
        Les trois systèmes qu'on sait lire disent la même chose que le
        référentiel. Les trois autres attendent un export.
      </p>
    {/if}
  {/if}
</section>
