<script>
  /**
   * Les mouvements d'un élève en cours d'année.
   *
   * Toute la chaîne de rentrée suppose une campagne, traitée en bloc. La
   * vie scolaire se fait à l'unité : un changement de classe en octobre,
   * une inscription en janvier.
   *
   * L'écran montre le plan avant de l'appliquer, et surtout **ce qui
   * restera à faire ailleurs** — KoXo n'a pas d'API. Un écran qui ferait
   * 60 % du travail sans nommer les 40 % restants serait plus dangereux
   * qu'un écran inerte.
   */
  import { onMount } from "svelte";
  import ArrowRightLeft from "@lucide/svelte/icons/arrow-right-left";
  import Search from "@lucide/svelte/icons/search";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Check from "@lucide/svelte/icons/check";
  import X from "@lucide/svelte/icons/x";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Bouton from "$lib/components/Bouton.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import BarreAction from "$lib/components/BarreAction.svelte";
  import { TEINTES } from "$lib/familles.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import {
    annees as anneesApi,
    mouvementsApi,
    personnes as personnesApi,
    tableCorrespondance,
  } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  /**
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));
  let classes = $state(/** @type {any[]} */ ([]));
  let toutes = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);

  let requete = $state("");
  let choisi = $state(/** @type {any} */ (null));
  let nouvelleClasse = $state("");
  let plan = $state(/** @type {any} */ (null));
  let occupe = $state(false);

  /**
   * Google reste à l'écart tant que la rentrée n'est pas faite.
   *
   * Avant le jour J, les élèves attendent tous dans la même OU — la classe
   * n'y change rien — et leurs groupes sont volontairement vides. Ajouter
   * l'élève à sa nouvelle liste le remettrait dans un groupe qu'on a vidé,
   * et lui révélerait sa classe avant l'heure.
   */
  let appliquerGoogle = $state(false);

  /**
   * Ce qui a été fait à la main, et qui survit à la navigation.
   *
   * Un mouvement se traite sur plusieurs jours : KoXo le lundi, la carte le
   * jeudi. Les cases cochées doivent tenir entre-temps, sinon on recoche au
   * jugé — ou on refait deux fois le même geste.
   */
  let faits = $state(lire("mouvement.faits", /** @type {Record<string, boolean>} */ ({})));
  $effect(() => ecrire("mouvement.faits", faits));

  /**
   * Les lignes du tableau, dans l'ordre où les systèmes se servent.
   *
   * Le référentiel d'abord — il conditionne tout le reste. Google ensuite,
   * la seule cible que le programme sait toucher. Puis ce qui reste à faire
   * ailleurs : KoXo n'a pas d'API, PMB et Sodexo se nourrissent de fichiers.
   *
   * Ces derniers ne sont pas « prêts » : ils sont **à faire**. Les afficher
   * comme les autres laisserait croire que le bouton les traite, et un écran
   * qui fait soixante pour cent du travail sans nommer les quarante restants
   * est plus dangereux qu'un écran inerte.
   */
  const TEINTE_SYSTEME = {
    Google: TEINTES.google,
    KoXo: TEINTES.koxo,
    PMB: TEINTES.materiel,
    Sodexo: TEINTES.repas,
    CardStudio: TEINTES.photos,
  };

  let rangs = $derived.by(() => {
    if (!plan) return [];
    const r = [
      {
        cle: "referentiel",
        systeme: "Référentiel",
        champ: "Classe",
        avant: plan.classe_avant,
        apres: plan.classe_apres,
        teinte: TEINTES.annee,
        force: true,
        automatisable: true,
        etat: "pret",
        texte: "Toujours",
      },
    ];

    if (plan.ou_avant !== plan.ou_apres) {
      r.push({
        cle: "google-ou",
        systeme: "Google",
        champ: "Unité",
        avant: plan.ou_avant,
        apres: plan.ou_apres,
        teinte: TEINTES.google,
        automatisable: true,
        etat: plan.deplacement_utile ? "pret" : "attente",
        texte: plan.deplacement_utile ? "Prêt" : "Sans effet",
      });
    }
    if (plan.groupe_quitte || plan.groupe_rejoint) {
      r.push({
        cle: "google-groupe",
        systeme: "Google",
        champ: "Groupe",
        avant: plan.groupe_quitte,
        apres: plan.groupe_rejoint,
        teinte: TEINTES.google,
        automatisable: true,
        etat: "pret",
        texte: "Prêt",
      });
    }

    for (const reste of plan.reste_a_faire ?? []) {
      r.push({
        cle: `main-${reste.systeme}`,
        systeme: reste.systeme,
        champ: "Classe",
        avant: plan.classe_avant,
        apres: plan.classe_apres,
        teinte: TEINTE_SYSTEME[reste.systeme] ?? TEINTES.fichiers,
        automatisable: false,
        etat: "attente",
        texte: "À la main",
      });
    }
    return r;
  });

  let nbSystemes = $derived(
    new Set(rangs.map((r) => r.systeme)).size,
  );
  let nbAutomatiques = $derived(
    new Set(rangs.filter((r) => r.automatisable).map((r) => r.systeme)).size,
  );

  onMount(async () => {
    try {
      const [a, tc, p] = await Promise.all([
        anneesApi.lister(),
        tableCorrespondance.lister(),
        personnesApi.lister({ type: "eleve" }),
      ]);
      listeAnnees = a;
      anneeId = [...a].sort((x, y) => x.libelle.localeCompare(y.libelle)).at(-1)?.id ?? null;
      classes = tc;
      toutes = p;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      chargement = false;
    }
  });

  // Sans accents ni casse : « guegan » doit trouver « Guégan ».
  function aplatir(t) {
    return (t ?? "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase();
  }

  let resultats = $derived.by(() => {
    const q = aplatir(requete.trim());
    if (q.length < 2) return [];
    return toutes
      .filter((p) => aplatir(`${p.nom} ${p.prenom} ${p.login} ${p.badge}`).includes(q))
      .slice(0, 12);
  });

  // Les classes déclarées, sans doublon, dans l'ordre.
  let codesClasses = $derived(
    [...new Set(classes.map((c) => c.classe_code_court))].sort(),
  );

  function choisir(p) {
    choisi = p;
    plan = null;
    nouvelleClasse = "";
    requete = "";
  }

  async function calculer() {
    if (!choisi || !nouvelleClasse || !anneeId) return;
    occupe = true;
    try {
      plan = await mouvementsApi.changerClasse({
        personneId: choisi.id,
        nouvelleClasse,
        anneeId,
        appliquerGoogle,
      });
    } catch (e) {
      plan = null;
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      occupe = false;
    }
  }

  async function appliquer() {
    if (!plan) return;
    occupe = true;
    try {
      const r = await mouvementsApi.changerClasse({
        personneId: choisi.id,
        nouvelleClasse,
        anneeId,
        mode: "reel",
        appliquerGoogle,
      });
      const echecs = (r.operations ?? []).filter((o) => !o.reussie).length;
      if (echecs) {
        notify.avertissement(
          `${r.prenom} ${r.nom} est passé en ${r.classe_apres}, mais ${echecs} opération(s) Google ont échoué.`,
        );
      } else {
        notify.succes(`${r.prenom} ${r.nom} est passé en ${r.classe_apres}.`);
      }
      plan = r;
      // Le référentiel a changé : la liste en mémoire doit suivre, sinon
      // un second mouvement partirait de l'ancienne classe.
      toutes = await personnesApi.lister({ type: "eleve" });
      choisi = toutes.find((p) => p.id === choisi.id) ?? choisi;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      occupe = false;
    }
  }
</script>

<section class="flex min-h-[calc(100vh-10rem)] flex-col space-y-6">
  <EnTetePage
    icon={ArrowRightLeft}
    titre="Un élève change de classe"
    description="Le référentiel bouge d'abord — sans lui, la bascule du jour J et la composition des groupes ramèneraient l'élève dans son ancienne classe."
  />

  {#if chargement}
    <Squelette variante="ligne-tableau" nb={4} colonnes={4} />
  {:else}
    <!-- ----------------------------------------------------------------
         Qui, et vers quoi. Tout sur une ligne : c'est une phrase.
         ---------------------------------------------------------------- -->
    <div class="flex flex-wrap items-end gap-6 border-b border-stone-200 pb-5 dark:border-stone-800">
      <div class="min-w-64 flex-1">
        <span class="libelle-champ">Élève</span>
        {#if choisi}
          <div class="mt-1.5 flex items-center gap-2">
            <span class="font-semibold">{choisi.nom} {choisi.prenom}</span>
            <span class="font-mono text-xs text-stone-500 dark:text-stone-400">
              {choisi.cle_pivot ?? choisi.badge}
            </span>
            <button
              class="text-stone-400 transition hover:text-red-600"
              aria-label="Changer d'élève"
              onclick={() => { choisi = null; plan = null; nouvelleClasse = ""; }}
            >
              <X class="h-4 w-4" />
            </button>
          </div>
        {:else}
          <div class="relative mt-1.5">
            <Search class="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-stone-400" />
            <input
              class="champ !py-2 pl-9"
              placeholder="Nom, prénom, login ou badge…"
              bind:value={requete}
            />
            {#if resultats.length}
              <div class="card card-relief absolute z-20 mt-1 max-h-64 w-full overflow-y-auto p-1">
                {#each resultats as p (p.id)}
                  <button
                    class="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-stone-100 dark:hover:bg-stone-800"
                    onclick={() => choisir(p)}
                  >
                    <span class="truncate">
                      <strong>{p.nom}</strong> {p.prenom}
                    </span>
                    <span class="shrink-0 font-mono text-xs text-stone-500">
                      {p.classe ?? "—"}
                    </span>
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      </div>

      <div>
        <span class="libelle-champ">Classe actuelle</span>
        <p
          class="titre-affiche mt-1 text-xl leading-none"
          style="color: {TEINTES.rentree};"
        >
          {choisi?.classe ?? "—"}
        </p>
      </div>

      <ArrowRight class="mb-1 h-5 w-5 shrink-0 text-stone-400" />

      <div>
        <label class="libelle-champ" for="nouvelle-classe">Nouvelle classe</label>
        <select
          id="nouvelle-classe"
          class="champ mt-1 !border-2 !py-1.5 font-mono font-bold"
          style="border-color: {TEINTES.annee};"
          bind:value={nouvelleClasse}
          disabled={!choisi}
          onchange={calculer}
        >
          <option value="">Choisir…</option>
          {#each codesClasses.filter((c) => c !== choisi?.classe) as c (c)}
            <option value={c}>{c}</option>
          {/each}
        </select>
      </div>

      {#if plan}
        <div class="ml-auto text-right">
          <p class="titre-affiche text-3xl leading-none" style="color: {TEINTES.annee};">
            {nbSystemes}
          </p>
          <p class="text-xs text-stone-600 dark:text-stone-400">
            système{nbSystemes > 1 ? "s" : ""} touché{nbSystemes > 1 ? "s" : ""}
          </p>
        </div>
      {/if}
    </div>

    {#if !choisi}
      <EtatVide
        icon={ArrowRightLeft}
        titre="Choisis d'abord un élève"
        message="Un changement de classe touche sept systèmes. L'écran les montre tous avant d'en modifier un seul."
      >
        <Bouton onclick={() => onNaviguer?.("bouge")}>
          Une arrivée ou un départ ?
        </Bouton>
      </EtatVide>
    {:else if !plan}
      <p class="py-10 text-center text-sm text-stone-500 dark:text-stone-400">
        Choisis la nouvelle classe : le plan s'affichera avant toute modification.
      </p>
    {:else}
      <!-- ----------------------------------------------------------------
           Ce qui va changer, ligne par ligne.
           ---------------------------------------------------------------- -->
      <div class="min-h-0 flex-1 overflow-y-auto">
        <h2 class="titre-affiche mb-2 text-xl">Ce qui va changer</h2>

        <div class="grid grid-cols-[36px_190px_110px_minmax(0,1fr)_24px_minmax(0,1fr)_130px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
          <span></span>
          <span class="libelle-champ">Système</span>
          <span class="libelle-champ">Champ</span>
          <span class="libelle-champ">Avant</span>
          <span></span>
          <span class="libelle-champ">Après</span>
          <span class="libelle-champ">État</span>
        </div>

        {#each rangs as r (r.cle)}
          <div class="grid grid-cols-[36px_190px_110px_minmax(0,1fr)_24px_minmax(0,1fr)_130px] items-center gap-3 border-b border-stone-100 py-3 text-sm dark:border-stone-800/70">
            <span>
              {#if r.force}
                <!-- Le référentiel bouge toujours : sans lui, la bascule
                     ramènerait l'élève dans son ancienne classe. -->
                <input
                  type="checkbox"
                  checked
                  disabled
                  class="h-4 w-4 accent-emerald-600"
                  aria-label="Référentiel, toujours appliqué"
                />
              {:else if r.automatisable}
                <input
                  type="checkbox"
                  class="h-4 w-4 accent-emerald-600"
                  aria-label="Appliquer sur {r.systeme}"
                  bind:checked={appliquerGoogle}
                />
              {:else}
                <input
                  type="checkbox"
                  class="h-4 w-4 accent-emerald-600"
                  aria-label="Marquer « {r.systeme} » comme fait"
                  checked={faits[r.cle] ?? false}
                  onchange={(e) => (faits = { ...faits, [r.cle]: e.currentTarget.checked })}
                />
              {/if}
            </span>

            <span class="flex items-center gap-2.5 font-semibold">
              <span class="h-2.5 w-2.5 shrink-0 rounded-full" style="background: {r.teinte};"></span>
              {r.systeme}
            </span>

            <span class="text-stone-600 dark:text-stone-400">{r.champ}</span>

            <span class="min-w-0 truncate text-stone-500 line-through dark:text-stone-400">
              {r.avant ?? "—"}
            </span>
            <ArrowRight class="h-4 w-4 shrink-0 text-stone-400" />
            <span class="min-w-0 truncate font-bold" style="color: {r.teinte};">
              {r.apres ?? "—"}
            </span>

            <Pastille etat={r.etat} texte={r.texte} />
          </div>
        {/each}

        <p class="mt-3 text-[13px] text-stone-500 dark:text-stone-400">
          Ne change pas : site <b>{choisi.site ?? "—"}</b> · adresse mail ·
          année <b>{listeAnnees.find((a) => a.id === anneeId)?.libelle ?? "—"}</b>
        </p>

        {#if plan.avertissements?.length}
          <div class="mt-4 rounded-xl bg-amber-50 p-4 dark:bg-amber-400/10">
            <p class="flex items-center gap-1.5 text-[11px] font-bold tracking-[0.08em] text-amber-800 uppercase dark:text-amber-300">
              <TriangleAlert class="h-3.5 w-3.5" /> À savoir
            </p>
            <ul class="mt-1.5 space-y-1 text-sm text-amber-900 dark:text-amber-200">
              {#each plan.avertissements as a (a)}<li>{a}</li>{/each}
            </ul>
          </div>
        {/if}
      </div>

      <BarreAction
        message="Rien n'est modifié tant que tu n'as pas validé. Les systèmes sans API se cochent à la main, une fois le geste fait de leur côté."
      >
        <Bouton onclick={() => { plan = null; nouvelleClasse = ""; }}>Annuler</Bouton>
        <Bouton variante="primary" icon={Check} occupe={occupe} onclick={appliquer}>
          Appliquer sur {nbAutomatiques} système{nbAutomatiques > 1 ? "s" : ""}
        </Bouton>
      </BarreAction>
    {/if}
  {/if}
</section>
