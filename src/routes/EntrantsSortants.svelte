<script>
  /**
   * Qui arrive, qui part, et qui vient de nos propres collèges.
   *
   * ## Pourquoi trois listes et pas deux
   *
   * Un élève qui entre en seconde après avoir fait son collège chez nous
   * n'est pas un entrant : il a déjà un compte, un login, une adresse et
   * un badge. Lui en créer un second le dédoublerait dans tous les
   * systèmes, et c'est l'erreur la plus coûteuse de la rentrée — deux
   * identités pour une personne ne se recollent plus jamais.
   *
   * Le programme les distingue à la classe que Charlemagne lui connaissait
   * l'an dernier. Ils ont donc leur onglet, et leur liste ne propose pas
   * de créer quoi que ce soit : elle propose de **vérifier**.
   *
   * ## Ce que « sortant » veut dire ici
   *
   * Le compte Google n'est pas supprimé : il est déplacé dans l'unité des
   * sortants, sans suspension, et y reste dix-huit mois. Une lettre de
   * prévenance part, puis quatre mois passent. KoXo et PMB, eux, se
   * nettoient en fin d'année.
   *
   * C'est pour ça que cette liste se lit et ne s'applique pas : le seul
   * geste qu'on fait ici est de **vérifier** que Google est bien dans
   * l'état annoncé.
   */
  import { onMount } from "svelte";
  import LogIn from "@lucide/svelte/icons/log-in";
  import LogOut from "@lucide/svelte/icons/log-out";
  import GraduationCap from "@lucide/svelte/icons/graduation-cap";
  import Download from "@lucide/svelte/icons/download";
  import UserPlus from "@lucide/svelte/icons/user-plus";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Onglets from "$lib/components/Onglets.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import BarreAction from "$lib/components/BarreAction.svelte";
  import {
    annees as anneesApi,
    nouveaux as nouveauxApi,
    sortants as sortantsApi,
    enregistrerFichierBase64,
  } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { TEINTES } from "$lib/familles.js";

  let { onNaviguer } = $props();

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));
  let arrivants = $state(/** @type {any} */ (null));
  let partants = $state(/** @type {any} */ (null));
  let chargement = $state(true);
  let occupe = $state(false);
  let onglet = $state("entrants");

  /**
   * Les trois listes, tirées d'une seule lecture.
   *
   * Un entrant n'a ni compte ni classe l'an dernier : tout est à créer.
   * Un élève de nos collèges en a une — c'est ce que `classe_precedente`
   * dit, et c'est la seule chose qui les sépare.
   */
  let entrants = $derived(
    (arrivants?.arrivants ?? []).filter(
      (a) => a.statut === "nouveau" && !a.classe_precedente,
    ),
  );
  let desCollegois = $derived(
    (arrivants?.arrivants ?? []).filter((a) => a.classe_precedente),
  );
  /** Ni l'un ni l'autre : un compte existe, mais rien l'an dernier. */
  let aVerifier = $derived(
    (arrivants?.arrivants ?? []).filter(
      (a) => a.statut !== "nouveau" && !a.classe_precedente,
    ),
  );
  let sortantsListe = $derived(partants?.sortants ?? []);

  /**
   * Les rattachables d'abord, les autres à la fin.
   *
   * Sans site, aucune cible n'est calculable : la ligne ne peut rien
   * produire. Or ce sont justement elles qui remontaient en tête — seize
   * « RPP A » à « RPP P », un CNED, deux vies scolaires — et les deux
   * cent entrants réels commençaient sous la ligne de flottaison.
   *
   * Elles restent listées, en rouge : les cacher ferait croire que la
   * rentrée est complète. Elles passent simplement après ce qu'on peut
   * traiter.
   */
  let lignes = $derived.by(() => {
    const brut =
      onglet === "entrants"
        ? entrants
        : onglet === "collegois"
          ? desCollegois
          : onglet === "a_verifier"
            ? aVerifier
            : sortantsListe;
    if (onglet === "sortants") return brut;
    return [...brut].sort((a, b) => {
      if (!a.site !== !b.site) return a.site ? -1 : 1;
      return (
        (a.site ?? "").localeCompare(b.site ?? "") ||
        (a.classe ?? "").localeCompare(b.classe ?? "") ||
        a.nom.localeCompare(b.nom)
      );
    });
  });

  /** Combien de la liste affichée ne mènent nulle part faute de site. */
  let nbSansSite = $derived(lignes.filter((l) => !l.site).length);

  /**
   * Les systèmes où un compte se crée, pour ce site.
   *
   * NDE n'a ni KoXo ni contrôle d'accès : y annoncer un compte KoXo
   * ferait chercher une console qui n'existe pas.
   */
  function cibles(site) {
    if (!site) return null;
    return site === "NDE"
      ? ["Google", "PMB"]
      : ["Google", "KoXo", "PMB", "Badge"];
  }

  onMount(async () => {
    try {
      listeAnnees = await anneesApi.lister();
      const triees = [...listeAnnees].sort((a, b) =>
        b.libelle.localeCompare(a.libelle),
      );
      anneeId = triees[0]?.id ?? null;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      chargement = false;
    }
    await charger();
  });

  async function charger() {
    if (!anneeId) return;
    occupe = true;
    try {
      [arrivants, partants] = await Promise.all([
        nouveauxApi.lister({ anneeId }),
        sortantsApi.lister().catch(() => null),
      ]);
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  async function exporter() {
    if (!anneeId) return;
    occupe = true;
    try {
      const f = await nouveauxApi.csv({ anneeId });
      await enregistrerFichierBase64(f.nom_fichier, f.contenu_base64);
      notify.succes(`${f.nom_fichier} enregistré`);
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      occupe = false;
    }
  }

  async function verifierSortants() {
    occupe = true;
    try {
      const r = await sortantsApi.verifier();
      notify.info(
        `${r.nb_a_verifier} compte(s) confrontés à Google — voir le Suivi.`,
        { duree: 9000 },
      );
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      occupe = false;
    }
  }

  const nombre = (n) => (n ?? 0).toLocaleString("fr-FR");
</script>

<section class="flex min-h-[calc(100vh-10rem)] flex-col space-y-5">
  <EnTetePage
    icon={LogIn}
    titre="Entrants, sortants et collèges"
    description="Faire le point avant de créer ou de supprimer des comptes. Un élève venu de nos propres collèges a déjà un compte — lui en créer un second le dédoublerait partout."
  >
    {#snippet actions()}
      <select class="champ w-40" bind:value={anneeId} onchange={charger}>
        {#each listeAnnees as a (a.id)}<option value={a.id}>{a.libelle}</option>{/each}
      </select>
      <Bouton icon={RefreshCw} occupe={occupe} onclick={charger}>Relire</Bouton>
    {/snippet}
  </EnTetePage>

  {#if chargement}
    <Squelette variante="ligne-tableau" nb={5} colonnes={5} />
  {:else}
    <Onglets
      bind:valeur={onglet}
      onglets={[
        { id: "entrants", label: "Entrants", compte: entrants.length },
        { id: "sortants", label: "Sortants", compte: sortantsListe.length },
        { id: "collegois", label: "Venant de nos collèges", compte: desCollegois.length },
        { id: "a_verifier", label: "À vérifier", compte: aVerifier.length },
      ]}
    />

    <!-- ----------------------------------------------------------------
         Les trois chiffres, avant la liste.
         ---------------------------------------------------------------- -->
    <div class="flex flex-wrap gap-12 border-b border-stone-200 pb-5 dark:border-stone-800">
      <div>
        <p class="titre-affiche text-3xl leading-none" style="color: {TEINTES.rentree};">
          {nombre(entrants.length)}
        </p>
        <p class="mt-1 text-xs text-stone-600 dark:text-stone-400">
          entrant{entrants.length > 1 ? "s" : ""} — tout est à créer
        </p>
      </div>
      <div>
        <p class="titre-affiche text-3xl leading-none" style="color: {TEINTES.fichiers};">
          {nombre(sortantsListe.length)}
        </p>
        <p class="mt-1 text-xs text-stone-600 dark:text-stone-400">
          sortant{sortantsListe.length > 1 ? "s" : ""}
          {#if partants?.nb_echeance_depassee}
            · <span class="font-semibold text-amber-700 dark:text-amber-400">
              {partants.nb_echeance_depassee} échu(s)
            </span>
          {/if}
        </p>
      </div>
      <div>
        <p class="titre-affiche text-3xl leading-none" style="color: {TEINTES.google};">
          {nombre(desCollegois.length)}
        </p>
        <p class="mt-1 text-xs text-stone-600 dark:text-stone-400">
          venant de nos collèges — à ne pas recréer
        </p>
      </div>
    </div>

    {#if !lignes.length}
      <EtatVide
        icon={onglet === "sortants" ? LogOut : LogIn}
        titre="Rien dans cette liste"
        message={onglet === "sortants"
          ? "Aucun compte en attente de purge pour l'instant."
          : "Aucune personne de ce genre dans l'année choisie."}
      />
    {:else if onglet === "sortants"}
      <!-- ----------------------------------------------------------------
           Les sortants : une lecture, pas une action.
           ---------------------------------------------------------------- -->
      <div class="min-h-0 flex-1 overflow-y-auto">
        <div class="grid grid-cols-[minmax(0,1fr)_70px_100px_minmax(0,1fr)_110px_120px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
          <span class="libelle-champ">Personne</span>
          <span class="libelle-champ">Site</span>
          <span class="libelle-champ">Dernière classe</span>
          <span class="libelle-champ">Unité attendue</span>
          <span class="libelle-champ">Purge prévue</span>
          <span class="libelle-champ">État</span>
        </div>

        {#each sortantsListe as s (s.personne_id)}
          <div class="grid grid-cols-[minmax(0,1fr)_70px_100px_minmax(0,1fr)_110px_120px] items-center gap-3 border-b border-stone-100 py-3 text-sm dark:border-stone-800/70">
            <span class="min-w-0 truncate">
              <strong>{s.nom}</strong> {s.prenom}
              <span class="ml-1 font-mono text-xs text-stone-500">{s.email ?? "—"}</span>
            </span>
            <span class="text-stone-600 dark:text-stone-400">{s.site ?? "—"}</span>
            <span class="text-stone-600 dark:text-stone-400">{s.derniere_classe ?? "—"}</span>
            <span class="min-w-0 truncate font-mono text-xs text-stone-500 dark:text-stone-400">
              {s.ou_attendue ?? "—"}
            </span>
            <span class="tabular-nums text-stone-600 dark:text-stone-400">
              {s.date_prevue_purge ?? "—"}
            </span>
            {#if s.verification === "conforme"}
              <Pastille etat="pret" texte="Là où il faut" />
            {:else if s.verification === "ecart"}
              <Pastille etat="ecart" texte={s.detail_verification ?? "Écart"} />
            {:else if s.echeance_depassee}
              <Pastille etat="attente" texte="Échéance passée" />
            {:else}
              <Pastille etat="inconnu" texte="Pas vérifié" />
            {/if}
          </div>
        {/each}
      </div>

      <BarreAction
        message="Le compte Google est déplacé sans suspension et conservé dix-huit mois. KoXo et PMB se nettoient en fin d'année. Rien n'est supprimé ici."
      >
        <Bouton icon={RefreshCw} occupe={occupe} onclick={verifierSortants}>
          Confronter à Google
        </Bouton>
      </BarreAction>
    {:else}
      <!-- ----------------------------------------------------------------
           Entrants, collégiens, à vérifier : la même forme de tableau.
           ---------------------------------------------------------------- -->
      <div class="min-h-0 flex-1 overflow-y-auto">
        <div class="grid grid-cols-[minmax(0,1fr)_70px_100px_140px_minmax(0,1fr)_130px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
          <span class="libelle-champ">Personne</span>
          <span class="libelle-champ">Site</span>
          <span class="libelle-champ">Classe cible</span>
          <span class="libelle-champ">Origine</span>
          <span class="libelle-champ">
            {onglet === "entrants" ? "À créer" : "Pourquoi cette ligne"}
          </span>
          <span class="libelle-champ">État</span>
        </div>

        {#each lignes as a (a.personne_id)}
          <div class="grid grid-cols-[minmax(0,1fr)_70px_100px_140px_minmax(0,1fr)_130px] items-center gap-3 border-b border-stone-100 py-3 text-sm dark:border-stone-800/70">
            <button
              class="min-w-0 truncate text-left hover:underline"
              onclick={() => onNaviguer?.("personnes")}
            >
              <strong>{a.nom}</strong> {a.prenom}
              <span class="ml-1 font-mono text-xs text-stone-500">{a.login}</span>
            </button>
            <span class="text-stone-600 dark:text-stone-400">{a.site ?? "—"}</span>
            <span class="font-semibold">{a.classe ?? "—"}</span>
            <span class="text-stone-600 dark:text-stone-400">
              {a.classe_precedente ? `Chez nous en ${a.classe_precedente}` : "Extérieur"}
            </span>
            <span class="min-w-0 truncate text-stone-600 dark:text-stone-400">
              {#if onglet === "entrants"}
                {#if cibles(a.site)}
                  {cibles(a.site).join(" · ")}
                {:else}
                  <span class="text-red-600 dark:text-red-400">Aucune cible</span>
                {/if}
              {:else}
                {a.motif}
              {/if}
            </span>
            {#if !a.site}
              <Pastille etat="ecart" texte="Sans site" />
            {:else if a.classe_precedente}
              <Pastille etat="attente" texte="A déjà un compte" />
            {:else if a.statut === "nouveau"}
              <Pastille etat="pret" texte="Prêt" />
            {:else}
              <Pastille etat="attente" texte="À vérifier" />
            {/if}
          </div>
        {/each}
      </div>

      <BarreAction
        message={nbSansSite
          ? `${nbSansSite} ligne(s) sans site en fin de liste : aucune cible n'est calculable tant qu'elles n'y sont pas rattachées.`
          : onglet === "entrants"
            ? "La création se fait depuis « Arrivée », qui écrit le référentiel, l'adresse, le login et le badge en un geste."
            : "Ces lignes ne se créent pas : un compte existe déjà. Les ouvrir depuis le référentiel avant toute décision."}
      >
        <Bouton icon={Download} occupe={occupe} onclick={exporter}>
          Exporter la liste
        </Bouton>
        {#if onglet === "entrants"}
          <Bouton
            variante="primary"
            icon={UserPlus}
            onclick={() => onNaviguer?.("arrivees")}
          >
            Créer les comptes
          </Bouton>
        {/if}
      </BarreAction>
    {/if}
  {/if}
</section>
