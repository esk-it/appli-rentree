<script>
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Bouton from "$lib/components/Bouton.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import { personnes as personnesApi } from "$lib/api.js";
  import { comparerNaturel } from "$lib/referentiel.js";

  /**
   * Ce que le référentiel sait des inscrits, et ce qui lui manque.
   *
   * Chaque écran voyait son morceau — les cartes leurs codes, les photos
   * leurs visages, le coffre ses mots de passe. Personne ne voyait
   * l'ensemble, et c'est la question qu'on se pose juste après une
   * ingestion : qu'est-ce qui manque encore, et où ? D'abord les taux,
   * puis le détail classe par classe — c'est à ce grain qu'on corrige.
   *
   * Une case ouvre la liste des personnes concernées dans l'onglet
   * Personnes, déjà filtrée.
   *
   * @typedef {Object} Props
   * @property {number|null} anneeId
   * @property {(f: {classe: string, facette: string, valeur: string}) => void} [onFiltrer]
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { anneeId = null, onFiltrer, onNaviguer } = $props();

  let releve = $state(/** @type {any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");
  let site = $state("");
  let tri = $state(/** @type {"classe"|"manque"} */ ("classe"));

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      releve = await personnesApi.completude(anneeId);
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
    } finally {
      chargement = false;
    }
  }

  $effect(() => {
    anneeId;
    charger();
  });

  const pct = (n, total) => (n == null ? null : total ? Math.round((100 * n) / total) : 0);

  let mesures = $derived.by(() => {
    if (!releve) return [];
    const r = releve;
    const aAjouter = "colonne à ajouter à l'export Charlemagne";
    return [
      {
        // « Constatée » : relevée dans Google ou dans un export. Une adresse
        // qui ne l'est pas n'est pas un compte absent — elle est calculée,
        // et le compte peut exister sans avoir encore été relevé.
        titre: "Adresse constatée",
        valeur: pct(r.avec_adresse, r.effectif),
        chiffre: `${pct(r.avec_adresse, r.effectif)} %`,
        detail: `${r.avec_adresse.toLocaleString("fr-FR")} sur ${r.effectif.toLocaleString("fr-FR")} — les autres sont calculées, pas encore relevées dans Google`,
      },
      {
        titre: "Mot de passe au coffre",
        valeur: pct(r.au_coffre, r.effectif),
        chiffre: `${pct(r.au_coffre, r.effectif)} %`,
        detail: `${r.au_coffre.toLocaleString("fr-FR")} personnes`,
      },
      {
        titre: "Photo (élèves)",
        valeur: pct(r.avec_photo, r.eleves),
        chiffre: r.avec_photo == null ? "—" : `${pct(r.avec_photo, r.eleves)} %`,
        detail: r.avec_photo == null ? "partage des photos injoignable" : `${r.avec_photo.toLocaleString("fr-FR")} sur ${r.eleves.toLocaleString("fr-FR")}`,
      },
      {
        titre: "INE (élèves)",
        valeur: pct(r.avec_ine, r.eleves),
        chiffre: `${pct(r.avec_ine, r.eleves)} %`,
        detail: r.avec_ine ? `${r.avec_ine.toLocaleString("fr-FR")} relevés` : aAjouter,
      },
      {
        titre: "Date de naissance",
        valeur: pct(r.avec_naissance, r.effectif),
        chiffre: `${pct(r.avec_naissance, r.effectif)} %`,
        detail: r.avec_naissance ? `${r.avec_naissance.toLocaleString("fr-FR")} relevées` : aAjouter,
      },
      {
        titre: "Codes CardStudio",
        valeur: pct(r.classes_avec_codes, r.classes),
        chiffre: `${r.classes_avec_codes} / ${r.classes}`,
        detail: r.classes_avec_codes ? "classes qui les ont" : "« Code niveau » et « Code établissement » à ajouter",
      },
    ];
  });

  function couleurBarre(v) {
    if (v == null) return "bg-stone-300 dark:bg-stone-600";
    if (v >= 90) return "bg-vert-500";
    if (v >= 50) return "bg-amber-500";
    return "bg-red-500";
  }

  /** La teinte d'une case : la clarté change avec la couleur, pas la seule teinte. */
  function teinte(v) {
    if (v == null) return "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400";
    if (v >= 99) return "bg-vert-200 text-vert-900 dark:bg-vert-500/30 dark:text-vert-100";
    if (v >= 90) return "bg-vert-100 text-vert-800 dark:bg-vert-500/15 dark:text-vert-200";
    if (v >= 50) return "bg-amber-100 text-amber-900 dark:bg-amber-400/20 dark:text-amber-100";
    return "bg-red-100 text-red-800 dark:bg-red-400/20 dark:text-red-100";
  }

  let sites = $derived([...new Set((releve?.par_classe ?? []).map((c) => c.site).filter(Boolean))].sort());

  let classes = $derived.by(() => {
    const lignes = (releve?.par_classe ?? []).filter((c) => !site || c.site === site);
    const manque = (c) =>
      (c.effectif - c.avec_adresse) + (c.effectif - c.au_coffre) + (c.effectif - c.avec_ine) +
      (c.effectif - c.avec_naissance) + (c.avec_photo == null ? 0 : c.effectif - c.avec_photo);
    return lignes.slice().sort((a, b) =>
      tri === "manque"
        ? manque(b) / b.effectif - manque(a) / a.effectif
        : (a.site ?? "").localeCompare(b.site ?? "") || comparerNaturel(a.classe, b.classe),
    );
  });

  const COLONNES = "grid-cols-[110px_64px_76px_repeat(7,minmax(0,1fr))]";
</script>

{#snippet caseChiffre(v, texte, action, titre)}
  <button
    type="button"
    class="flex h-9 items-center justify-center rounded-lg text-[13px] font-bold tabular-nums transition hover:ring-2 hover:ring-stone-400/60 focus-visible:ring-2 {teinte(v)}"
    title={titre}
    onclick={action}
  >
    {texte}
  </button>
{/snippet}

<div class="flex h-full min-h-0 flex-col">
  {#if chargement && !releve}
    <Squelette variante="ligne-tableau" nb={8} colonnes={8} />
  {:else if erreur}
    <p class="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">{erreur}</p>
  {:else if releve && !releve.effectif}
    <EtatVide icon={CheckCircle2} titre="Personne d'inscrit cette année" message="Ingère l'export Charlemagne de l'année : le relevé portera sur ses inscrits." />
  {:else if releve}
    <div class="grid grid-cols-2 gap-6 border-b border-stone-200 pb-5 md:grid-cols-3 xl:grid-cols-6 dark:border-stone-800">
      {#each mesures as m, i (m.titre)}
        <div class="min-w-0 {i ? 'xl:border-l xl:border-stone-200 xl:pl-6 xl:dark:border-stone-800' : ''}">
          <p class="text-[13px] font-semibold text-stone-500 dark:text-stone-400">{m.titre}</p>
          <p class="titre-affiche mt-1 text-3xl tabular-nums {m.valeur === 0 ? 'text-amber-700 dark:text-amber-400' : 'text-stone-900 dark:text-stone-100'}">{m.chiffre}</p>
          <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800">
            <div class="h-1.5 rounded-full {couleurBarre(m.valeur)}" style="width: {Math.max(m.valeur ?? 0, 2)}%;"></div>
          </div>
          <p class="mt-2 text-xs leading-snug text-stone-500 dark:text-stone-400">{m.detail}</p>
        </div>
      {/each}
    </div>

    <div class="mt-5 flex flex-wrap items-center gap-3">
      <span class="h-2.5 w-2.5 rounded-full bg-emerald-600"></span>
      <h3 class="titre-affiche text-base text-stone-900 dark:text-stone-100">Classe par classe</h3>
      <span class="text-sm text-stone-500 dark:text-stone-400">{releve.eleves.toLocaleString("fr-FR")} élèves · {releve.classes} classes · {releve.annee}</span>
      <span class="flex-1"></span>
      {#if sites.length > 1}
        <Segments
          bind:valeur={site}
          taille="sm"
          options={[{ id: "", label: "Tous" }, ...sites.map((s) => ({ id: s, label: s }))]}
        />
      {/if}
      <Segments
        bind:valeur={tri}
        taille="sm"
        options={[{ id: "classe", label: "Par classe" }, { id: "manque", label: "Le plus incomplet" }]}
      />
      <Bouton taille="sm" icon={RefreshCw} occupe={chargement} onclick={charger}>Relire</Bouton>
    </div>

    <div class="mt-3 min-h-0 flex-1 overflow-y-auto pb-4">
      <div class="sticky top-0 z-10 grid {COLONNES} items-center gap-2 border-b border-stone-200 bg-stone-50 py-2 dark:border-stone-800 dark:bg-stone-950">
        {#each ["Classe", "Site", "Effectif", "Adresse", "Coffre", "Photo", "INE", "Naissance", "Codes carte", "Cohérence"] as t (t)}
          <span class="libelle-champ">{t}</span>
        {/each}
      </div>
      {#each classes as c (c.classe)}
        <div class="grid {COLONNES} items-center gap-2 border-b border-stone-200 py-1.5 text-sm dark:border-stone-800">
          <b class="font-mono text-[13px]">{c.classe}</b>
          <span class="text-stone-500 dark:text-stone-400">{c.site ?? "—"}</span>
          <span class="tabular-nums">{c.effectif}</span>
          {@render caseChiffre(pct(c.avec_adresse, c.effectif), `${pct(c.avec_adresse, c.effectif)} %`,
            () => onFiltrer?.({ classe: c.classe, facette: "manque", valeur: "adresse" }),
            `${c.effectif - c.avec_adresse} dont l'adresse n'est pas constatée — les voir`)}
          {@render caseChiffre(pct(c.au_coffre, c.effectif), `${pct(c.au_coffre, c.effectif)} %`,
            () => onFiltrer?.({ classe: c.classe, facette: "manque", valeur: "coffre" }),
            `${c.effectif - c.au_coffre} sans mot de passe au coffre — les voir`)}
          {@render caseChiffre(pct(c.avec_photo, c.effectif), c.avec_photo == null ? "non lu" : `${pct(c.avec_photo, c.effectif)} %`,
            () => onNaviguer?.("photos"),
            "Ouvrir l'écran des photos")}
          {@render caseChiffre(pct(c.avec_ine, c.effectif), `${pct(c.avec_ine, c.effectif)} %`,
            () => onFiltrer?.({ classe: c.classe, facette: "manque", valeur: "ine" }),
            `${c.effectif - c.avec_ine} sans INE — les voir`)}
          {@render caseChiffre(pct(c.avec_naissance, c.effectif), `${pct(c.avec_naissance, c.effectif)} %`,
            () => onFiltrer?.({ classe: c.classe, facette: "manque", valeur: "naissance" }),
            `${c.effectif - c.avec_naissance} sans date de naissance — les voir`)}
          {@render caseChiffre(c.codes_carte ? 100 : null, c.codes_carte ? "connus" : "à apprendre",
            () => onNaviguer?.("cartes"),
            "Les codes s'apprennent de l'export Charlemagne, ou d'un export CardStudio")}
          {@render caseChiffre(c.verifies ? pct(c.coherents, c.effectif) : null, c.verifies ? `${c.coherents} / ${c.effectif}` : "pas vérifiée",
            () => onFiltrer?.({ classe: c.classe, facette: "etat", valeur: "ecart" }),
            "Les personnes en écart — les voir")}
        </div>
      {/each}
      <p class="mt-3 flex items-center gap-2 text-xs text-stone-500 dark:text-stone-400">
        <ArrowRight class="h-3.5 w-3.5" />
        Une case ouvre les personnes concernées, déjà filtrées dans l'onglet Personnes.
        {#if releve.photos_injoignables}
          Photos : {releve.photos_injoignables}
        {/if}
      </p>
    </div>
  {/if}
</div>
