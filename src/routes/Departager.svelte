<script>
  import { onMount } from "svelte";
  import AtSign from "@lucide/svelte/icons/at-sign";
  import Check from "@lucide/svelte/icons/check";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import Progression from "$lib/components/Progression.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import BarreAction from "$lib/components/BarreAction.svelte";
  import { personnes } from "$lib/api.js";
  import { TEINTES } from "$lib/familles.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Départager les adresses que plusieurs personnes visent.
   *
   * ## Pourquoi un écran, et pas un bouton
   *
   * L'accueil comptait « 29 adresses visées par plusieurs personnes » et
   * renvoyait au Référentiel — c'est-à-dire à deux mille cinq cents lignes
   * parmi lesquelles retrouver les cinquante-huit concernées. Le constat
   * était juste, le geste manquait.
   *
   * ## Ce que le programme refuse de faire seul
   *
   * Les adresses existantes portent tantôt un suffixe `1`, tantôt `2`, sans
   * règle déductible : le second Hugo GUILLOU s'est vu attribuer
   * `hugo.guillou1@` par calcul, puis créer dans Google sous
   * `hugo.guillou2@`. Le programme **propose** donc un suffixe et n'écrit
   * rien tant qu'on n'a pas validé. Créer un compte sous une adresse que
   * personne n'a regardée est exactement l'erreur que cet écran évite.
   *
   * ## Qui garde l'adresse nue
   *
   * Celui qui **détient déjà le compte** : la lui retirer casserait une
   * adresse en service — courriers, partages, comptes tiers. C'est donc à
   * l'arrivant de prendre le suffixe, et la ligne le dit.
   *
   * Sauf quand **plusieurs** la détiennent. Le cas existe : trois groupes
   * sur vingt-neuf, deux fiches portant le même `email_constate`, héritées
   * d'un amorçage. Personne ne peut alors être présumé la garder, et la
   * saisie s'ouvre sur toutes — désigner un titulaire au hasard reviendrait
   * à retirer à quelqu'un une adresse dont il se sert.
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  const libelleErreur = (e) => String(e).replace(/^Error:\s*/, "");

  let groupes = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let erreur = $state("");
  let enCours = $state(/** @type {number|null} */ (null));

  /** Ce qui est saisi, par personne, avant validation. */
  let saisies = $state(/** @type {Record<number, string>} */ ({}));

  onMount(charger);

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      groupes = await personnes.collisions();
      // La suggestion pré-remplit le champ : on la relit, on la corrige si
      // besoin, on valide. Un champ vide obligerait à retaper une adresse
      // que le programme sait déjà écrire.
      const prets = {};
      for (const g of groupes) {
        for (const v of g.visants) {
          if (v.a_trancher)
            prets[v.personne_id] = saisies[v.personne_id] ?? v.adresse_proposee;
        }
      }
      saisies = prets;
    } catch (e) {
      erreur = libelleErreur(e);
    } finally {
      chargement = false;
    }
  }

  let aDepartager = $derived(
    groupes.flatMap((g) => g.visants.filter((v) => v.a_trancher)),
  );
  let nbDoubles = $derived(groupes.filter((g) => g.plusieurs_comptes).length);

  async function valider(visant) {
    const adresse = (saisies[visant.personne_id] ?? "").trim();
    if (!adresse) return;
    enCours = visant.personne_id;
    try {
      await personnes.definirEmail(visant.personne_id, adresse);
      notify.succes(`${visant.prenom} ${visant.nom} prend ${adresse}.`);
      await charger();
    } catch (e) {
      notify.erreur(libelleErreur(e), { duree: 12000 });
    } finally {
      enCours = null;
    }
  }

  /** Tout valider d'un coup, en s'arrêtant sur la première qui résiste. */
  async function validerTout() {
    for (const v of [...aDepartager]) {
      const adresse = (saisies[v.personne_id] ?? "").trim();
      if (!adresse) continue;
      enCours = v.personne_id;
      try {
        await personnes.definirEmail(v.personne_id, adresse);
      } catch (e) {
        notify.erreur(
          `${v.prenom} ${v.nom} : ${libelleErreur(e)} — la suite n'a pas été appliquée.`,
          { duree: 14000 },
        );
        enCours = null;
        await charger();
        return;
      }
    }
    enCours = null;
    notify.succes("Toutes les adresses saisies ont été enregistrées.");
    await charger();
  }
</script>

<section class="flex min-h-[calc(100vh-10rem)] flex-col space-y-6">
  <EnTetePage
    icon={AtSign}
    chemin={["Départager"]}
    titre="{groupes.length} adresse{groupes.length > 1 ? 's' : ''} mail visée{groupes.length > 1 ? 's' : ''} par plusieurs personnes"
    description="Google refusera la création du doublon. Saisis une adresse distincte pour chaque personne « à créer » — les homonymes existants portent un suffixe numérique : prenom.nom2@…"
  >
    {#snippet actions()}
      <Bouton taille="sm" icon={RefreshCw} occupe={chargement} onclick={charger}>
        Relire
      </Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if chargement && !groupes.length}
    <Squelette variante="ligne-tableau" nb={6} colonnes={4} />
  {:else if !groupes.length}
    <EtatVide
      icon={CheckCircle2}
      ton="succes"
      titre="Aucune adresse disputée"
      message="Chaque personne vise une adresse qui n'appartient qu'à elle. L'export Google ne butera pas sur un doublon."
    />
  {:else}
    {#if nbDoubles}
      <div class="flex flex-wrap items-center gap-3 rounded-xl bg-red-50 px-4 py-3 text-sm dark:bg-red-500/10">
        <span class="h-2.5 w-2.5 shrink-0 rounded-full bg-red-500"></span>
        <span class="text-stone-800 dark:text-stone-200">
          <b>{nbDoubles} adresse{nbDoubles > 1 ? "s" : ""}</b>
          {nbDoubles > 1 ? "sont détenues" : "est détenue"} par
          <b>plusieurs fiches à la fois</b> — deux comptes constatés sur la
          même adresse. Personne ne peut être présumé la garder : les deux
          lignes s'ouvrent, et c'est à toi de dire laquelle bouge.
        </span>
      </div>
    {/if}

    <div class="max-w-md">
      <Progression
        valeur={0}
        total={aDepartager.length}
        libelle="{aDepartager.length} adresse{aDepartager.length > 1 ? 's' : ''} restent à trancher"
        teinte={TEINTES.annee}
      />
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <div class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_140px_300px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
        <span class="libelle-champ">Adresse visée</span>
        <span class="libelle-champ">Personne</span>
        <span class="libelle-champ">Statut</span>
        <span class="libelle-champ">Adresse distincte</span>
      </div>

      {#each groupes as g (g.adresse)}
        {#each g.visants as v, i (v.personne_id)}
          <div
            class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_140px_300px] items-center gap-3 py-2.5 text-sm
                   {i === g.visants.length - 1
              ? 'border-b border-stone-200 pb-3 dark:border-stone-800'
              : ''}"
          >
            <span class="truncate font-mono text-[13px]">
              {#if i === 0}{g.adresse}{/if}
            </span>

            <span class="min-w-0 truncate">
              <span class="font-mono text-xs text-stone-500 dark:text-stone-400">
                {v.cle_pivot}
              </span>
              <strong class="ml-1.5 font-semibold">{v.nom}</strong>
              <span class="text-stone-600 dark:text-stone-300">{v.prenom}</span>
              {#if v.classe}
                <span class="ml-1 text-xs text-stone-500">· {v.classe}</span>
              {/if}
            </span>

            <span>
              {#if v.a_un_compte && !v.a_trancher}
                <Pastille etat="inconnu" texte="compte existant" />
              {:else if v.a_un_compte}
                <Pastille etat="ecart" texte="compte en double" />
              {:else}
                <Pastille etat="reference" texte="à créer" />
              {/if}
            </span>

            {#if !v.a_trancher}
              <!-- Celui qui détient le compte garde son adresse : la
                   déplacer casserait une adresse en service. -->
              <span class="text-stone-500 dark:text-stone-400">la garde</span>
            {:else}
              <span class="flex items-center gap-1.5">
                <input
                  class="champ !py-1.5 font-mono text-[13px]"
                  aria-label="Adresse distincte pour {v.prenom} {v.nom}"
                  bind:value={saisies[v.personne_id]}
                  onkeydown={(e) => e.key === "Enter" && valider(v)}
                />
                <Bouton
                  taille="sm"
                  icon={Check}
                  occupe={enCours === v.personne_id}
                  disabled={!(saisies[v.personne_id] ?? "").trim()}
                  onclick={() => valider(v)}
                >
                  Valider
                </Bouton>
              </span>
            {/if}
          </div>
        {/each}
      {/each}
    </div>

    <BarreAction
      message="Rien n'est écrit tant que tu n'as pas validé. L'adresse saisie devient l'adresse constatée, et fait autorité comme si elle avait été relevée dans un export."
    >
      <Bouton onclick={() => onNaviguer?.("ou_ca_coince")}>Retour aux constats</Bouton>
      <Bouton
        variante="primary"
        icon={Check}
        disabled={!aDepartager.length}
        occupe={enCours !== null}
        onclick={validerTout}
      >
        Valider les {aDepartager.length} adresses
      </Bouton>
    </BarreAction>
  {/if}
</section>
