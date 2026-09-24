<script>
  /**
   * Le référentiel, et les trois systèmes qui doivent dire comme lui.
   *
   * ## Trois systèmes, pas six
   *
   * La première version dessinait une étoile à six branches, dont trois en
   * pointillé permanent : PMB, Sodexo et CardStudio reçoivent des fichiers
   * et n'en rendent aucun, il n'y a rien à comparer. Trois traits gris au
   * milieu d'un écran qu'on ouvre pour savoir ce qui cloche ne disaient
   * rien. La cohérence se juge là où elle se vérifie : Charlemagne, Google,
   * KoXo. Sodexo se suit par ses envois, CardStudio par ses cartes.
   *
   * ## Un arbre, pas une étoile
   *
   * Avec trois branches, le cercle n'apportait plus rien — il occupait la
   * place et reléguait le détail dans un encadré à côté, qu'il fallait
   * ouvrir satellite par satellite. Ici le référentiel est en haut, parce
   * qu'il est la référence ; chaque système pend de lui, et sous chacun
   * son détail tient en entier. Tout se lit d'un coup, sans clic.
   *
   * Le trait qui relie chaque système au référentiel porte l'état de la
   * dernière comparaison : vert, ambre, ou pointillé quand elle n'a jamais
   * tourné. Le cadre du logo reprend la même couleur — c'est ce qu'on voit
   * en premier.
   *
   * ## Les vrais logos
   *
   * Le « C » rouge de Charlemagne, le « G » de Google, le « K » bleu de
   * KoXo : on les reconnaît avant de les lire. Celui de Charlemagne vient
   * de la procédure Sodexo, celui de KoXo de son propre installateur.
   *
   * ## L'écran ne croise rien
   *
   * Croiser demande des exports et une bonne minute. L'écran lit ce que
   * les derniers croisements ont laissé, avec leur date, et chaque colonne
   * dit ce que coûte sa vérification — un export frais pour Charlemagne,
   * rien pour Google, un export par serveur pour KoXo.
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
  import logoCharlemagne from "$lib/assets/systemes/charlemagne.png";
  import logoGoogle from "$lib/assets/systemes/google.svg";
  import logoKoxo from "$lib/assets/systemes/koxo.png";

  let { onNaviguer } = $props();

  let donnees = $state(/** @type {any} */ (null));
  let chargement = $state(true);

  /**
   * Les trois, dans l'ordre où l'information circule : Charlemagne la
   * saisit, Google et KoXo la reçoivent.
   */
  const SYSTEMES = [
    {
      id: "charlemagne",
      nom: "Charlemagne",
      logo: logoCharlemagne,
      verifier: {
        texte:
          "Demande un export Charlemagne frais : cette comparaison ne peut " +
          "pas tourner toute seule.",
        bouton: "Charger un export Charlemagne",
        icone: Upload,
        vers: "concordance",
      },
    },
    {
      id: "google",
      nom: "Google Workspace",
      logo: logoGoogle,
      verifier: {
        texte:
          "Ne demande aucun fichier : le référentiel et l'annuaire sont déjà " +
          "là. Compter une minute de lecture.",
        bouton: "Confronter à Google",
        icone: RefreshCw,
        vers: "bilan",
      },
    },
    {
      id: "koxo",
      nom: "KoXo",
      logo: logoKoxo,
      verifier: {
        texte:
          "Un export par serveur — NDK et SU — avec un export Charlemagne pour " +
          "les croiser. NDE n'a pas de KoXo : ses élèves ne comptent pas ici.",
        bouton: "Déposer les exports KoXo",
        icone: Upload,
        vers: "concordance",
      },
    },
  ];

  /** Vert, ambre, gris — le vert du programme, pas `emerald` qui est violet. */
  const COULEURS = {
    coherent: "var(--color-vert-500)",
    ecarts: "var(--color-amber-500)",
    non_verifie: "var(--color-stone-400)",
  };

  const MOTS = {
    coherent: "Cohérent",
    ecarts: "Écarts",
    non_verifie: "Pas encore vérifié",
  };

  /** Les genres d'écart, dits en français plutôt qu'en clé. */
  const LIBELLES = {
    // Ceux que la Concordance nomme
    referentiel: "Classe différente du référentiel",
    google: "Unité d'une autre classe",
    groupe: "Groupe d'une autre classe",
    hors_arbre_de_classe: "Compte pas encore basculé",
    sans_compte: "Sans compte Google",
    koxo: "Classe différente dans KoXo",
    absent_koxo: "Absent de la base KoXo",
    // Ceux que le bilan nomme
    compte_absent: "Sans compte Google",
    compte_suspendu: "Compte suspendu",
    ou_inattendue: "Unité d'une autre classe",
    groupe_manquant: "Absent du groupe de sa classe",
    groupe_en_trop: "Membre du groupe d'une autre classe",
    identifiant_discordant: "Identifiant Charlemagne discordant",
    sortant_dans_arbre_actif: "Parti, mais rangé avec les inscrits",
  };

  /**
   * Où mène une ligne d'écart : l'écran qui l'a constatée.
   *
   * Les genres du bilan se règlent depuis le bilan, ceux de la
   * Concordance depuis la Concordance — un même lien, Google, peut avoir
   * été vérifié par l'un ou par l'autre.
   */
  const GENRES_DU_BILAN = new Set([
    "compte_absent", "compte_suspendu", "ou_inattendue", "groupe_manquant",
    "groupe_en_trop", "identifiant_discordant", "sortant_dans_arbre_actif",
  ]);

  let liens = $derived(
    SYSTEMES.map((s) => {
      const d = (donnees?.liens ?? []).find((l) => l.systeme === s.id);
      return {
        ...s,
        etat: d?.etat ?? "non_verifie",
        nb: (d?.nb_ecarts ?? 0) + (d?.nb_absents ?? 0),
        nb_verifies: d?.nb_verifies ?? 0,
        verifie_le: d?.verifie_le ?? null,
        details: d?.details ?? [],
      };
    }),
  );

  let nbNonVerifies = $derived(liens.filter((l) => l.etat === "non_verifie").length);
  let toutConcorde = $derived(liens.every((l) => l.etat === "coherent"));

  onMount(charger);

  async function charger() {
    chargement = true;
    try {
      donnees = await concordanceApi.liens();
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
    description="Le référentiel est la référence. Charlemagne, Google et KoXo se comparent à lui, et chaque trait dit où en est la dernière comparaison."
  >
    {#snippet actions()}
      <Bouton icon={RefreshCw} onclick={charger} occupe={chargement}>Relire</Bouton>
    {/snippet}
  </EnTetePage>

  {#if chargement && !donnees}
    <Squelette variante="carte" nb={2} />
  {:else if donnees}
    <!-- La légende : trois traits, trois mots — jamais la couleur seule. -->
    <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
      {#each ["coherent", "ecarts", "non_verifie"] as e (e)}
        <span class="flex items-center gap-2 text-xs text-stone-600 dark:text-stone-400">
          <span
            class="w-6"
            style="border-top: 2.5px {e === 'non_verifie' ? 'dashed' : 'solid'} {COULEURS[e]};"
            aria-hidden="true"
          ></span>
          {MOTS[e]}
        </span>
      {/each}
      {#if nbNonVerifies}
        <span class="ml-auto text-xs text-stone-500 dark:text-stone-400">
          <strong class="text-stone-800 dark:text-stone-200">{nbNonVerifies}</strong>
          lien{nbNonVerifies > 1 ? "s" : ""} sur 3 jamais comparé{nbNonVerifies > 1 ? "s" : ""}
        </span>
      {/if}
    </div>

    <!-- ----------------------------------------------------------------
         L'arbre : le référentiel en haut, les trois systèmes en dessous.
         ---------------------------------------------------------------- -->
    <div class="arbre">
      <div class="racine">
        <p class="text-[11px] font-bold tracking-[0.08em] text-white/80 uppercase">
          Référentiel
        </p>
        <p class="titre-affiche text-4xl leading-none tabular-nums text-white">
          {nombre(donnees.nb_personnes)}
        </p>
        <p class="text-xs text-white/85">
          {nombre(donnees.nb_eleves)} élèves · {nombre(donnees.nb_adultes)} adultes
        </p>
        {#if donnees.nb_verifiees}
          <p class="mt-1 text-[11px] text-white/70">
            {nombre(donnees.nb_verifiees)} déjà passées par un croisement
          </p>
        {/if}
      </div>

      <!-- La tige et le rail : neutres. Seules les descentes portent un
           état, parce que c'est chaque lien qui a le sien. -->
      <div class="tige" aria-hidden="true"></div>
      <div class="colonnes">
        <div class="rail" aria-hidden="true"></div>

        {#each liens as l (l.id)}
          <article class="colonne">
            <div
              class="descente"
              style="border-left: 2.5px {l.etat === 'non_verifie' ? 'dashed' : 'solid'} {COULEURS[l.etat]};"
              aria-hidden="true"
            ></div>

            <!-- Le cadre reprend l'état du trait : c'est ce qu'on voit en
                 premier. `outline` plutôt qu'une ombre : lui sait être en
                 pointillé, et suit l'arrondi. -->
            <div
              class="tuile"
              style="outline: 2.5px {l.etat === 'non_verifie' ? 'dashed' : 'solid'} {COULEURS[l.etat]};"
              class:tuile-grise={l.etat === "non_verifie"}
            >
              <img src={l.logo} alt="" class="h-9 w-9 object-contain" />
            </div>

            <h2 class="titre-affiche mt-3 text-lg">{l.nom}</h2>

            {#if l.etat === "ecarts"}
              <p class="titre-affiche text-2xl leading-tight" style="color: var(--color-amber-600);">
                {nombre(l.nb)} écart{l.nb > 1 ? "s" : ""}
              </p>
            {:else if l.etat === "coherent"}
              <p class="titre-affiche text-2xl leading-tight" style="color: var(--color-vert-600);">
                Tout concorde
              </p>
            {:else}
              <p class="titre-affiche text-2xl leading-tight text-stone-500 dark:text-stone-400">
                Pas encore vérifié
              </p>
            {/if}

            {#if l.verifie_le}
              <p class="text-xs text-stone-500 dark:text-stone-400">
                Comparé {age(l.verifie_le)} sur
                <strong class="tabular-nums">{nombre(l.nb_verifies)}</strong> personnes
              </p>
            {/if}

            {#if l.details.length}
              <div class="mt-3 w-full space-y-0.5 text-left">
                {#each l.details as d (d.genre)}
                  <button
                    type="button"
                    class="flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-stone-100 dark:hover:bg-stone-800"
                    onclick={() =>
                      onNaviguer?.(GENRES_DU_BILAN.has(d.genre) ? "bilan" : "concordance")}
                  >
                    <span
                      class="titre-affiche w-10 shrink-0 text-right text-lg leading-none tabular-nums"
                      style="color: var(--color-amber-600);"
                    >
                      {nombre(d.nb)}
                    </span>
                    <span class="min-w-0 flex-1 text-[13px] text-stone-700 dark:text-stone-300">
                      {LIBELLES[d.genre] ?? d.genre}
                    </span>
                    <ArrowRight class="h-3.5 w-3.5 shrink-0 text-stone-400" />
                  </button>
                {/each}
              </div>
            {/if}

            <div class="mt-auto w-full space-y-2.5 border-t border-stone-200 pt-3 text-left dark:border-stone-800">
              <p class="text-[12.5px] leading-relaxed text-stone-600 dark:text-stone-400">
                {l.verifier.texte}
              </p>
              <Bouton
                variante={l.etat === "coherent" ? "secondary" : "primary"}
                icon={l.verifier.icone}
                onclick={() => onNaviguer?.(l.verifier.vers)}
              >
                {l.verifier.bouton}
              </Bouton>
            </div>
          </article>
        {/each}
      </div>
    </div>

    {#if toutConcorde}
      <p class="text-sm text-stone-600 dark:text-stone-400">
        Les trois systèmes disent la même chose que le référentiel.
      </p>
    {/if}

    <p class="text-[13px] leading-relaxed text-stone-500 dark:text-stone-400">
      PMB, Sodexo et CardStudio n'y figurent pas : ils reçoivent des fichiers
      et n'en rendent aucun, il n'y a rien à comparer. Sodexo se suit par ses
      envois, dans son écran ; CardStudio par les cartes déjà faites.
    </p>
  {/if}
</section>

<style>
  /* L'arbre se lit de haut en bas : la référence, puis ce qui en dépend. */
  .arbre {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .racine {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
    padding: 1.1rem 2.25rem;
    border-radius: 1.25rem;
    background: var(--color-emerald-600); /* l'accent — violet ici */
    text-align: center;
  }

  .tige {
    width: 2px;
    height: 1.5rem;
    background: var(--color-stone-300);
  }
  :global(.dark) .tige {
    background: var(--color-stone-700);
  }

  .colonnes {
    --ecart: 2rem;
    position: relative;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--ecart);
    width: 100%;
  }

  /* Du centre de la première colonne au centre de la dernière. */
  .rail {
    position: absolute;
    top: 0;
    left: calc((100% - 2 * var(--ecart)) / 6);
    right: calc((100% - 2 * var(--ecart)) / 6);
    height: 2px;
    background: var(--color-stone-300);
  }
  :global(.dark) .rail {
    background: var(--color-stone-700);
  }

  .colonne {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding-bottom: 0.25rem;
  }

  .descente {
    width: 0;
    height: 1.75rem;
  }

  /* Une tuile blanche dans les deux thèmes : les logos sont dessinés pour
     un fond clair, comme une icône d'application. */
  .tuile {
    display: grid;
    place-items: center;
    width: 4rem;
    height: 4rem;
    border-radius: 1rem;
    background: #fff;
  }
  .tuile-grise img {
    opacity: 0.55;
    filter: grayscale(0.4);
  }

  /* Étroit : les colonnes s'empilent, et les traits n'ont plus de sens. */
  @media (max-width: 767px) {
    .colonnes {
      grid-template-columns: minmax(0, 1fr);
    }
    .rail,
    .tige,
    .descente {
      display: none;
    }
    .colonne {
      padding-top: 1rem;
    }
  }
</style>
