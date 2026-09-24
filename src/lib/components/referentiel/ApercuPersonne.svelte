<script>
  import { untrack } from "svelte";
  import Copy from "@lucide/svelte/icons/copy";
  import AtSign from "@lucide/svelte/icons/at-sign";
  import KeyRound from "@lucide/svelte/icons/key-round";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import FolderTree from "@lucide/svelte/icons/folder-tree";
  import Radar from "@lucide/svelte/icons/radar";
  import Pencil from "@lucide/svelte/icons/pencil";
  import Lock from "@lucide/svelte/icons/lock";
  import GitMerge from "@lucide/svelte/icons/git-merge";
  import Avatar from "$lib/components/Avatar.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import Touche from "$lib/components/Touche.svelte";
  import { coffreApi, personnes } from "$lib/api.js";
  import { jour, NOM_SYSTEME } from "$lib/referentiel.js";
  import { notify } from "$lib/toasts.js";
  import logoCharlemagne from "$lib/assets/systemes/charlemagne.png";
  import logoGoogle from "$lib/assets/systemes/google.svg";
  import logoKoxo from "$lib/assets/systemes/koxo.png";

  /**
   * La fiche d'une personne, à côté de la liste — sans quitter la liste.
   *
   * Le geste le plus fréquent sur le Référentiel est de retrouver quelqu'un
   * et d'agir sur lui : copier son identifiant, retrouver son mot de passe,
   * vérifier son compte. La fiche dépliée dans le tableau repoussait les
   * lignes, et la page de la fiche faisait perdre la liste. Ici les deux
   * restent en vue, et les flèches du clavier passent d'une personne à
   * l'autre.
   *
   * La page complète de la fiche reste à un clic : c'est là qu'on corrige
   * un écart en plusieurs étapes.
   *
   * @typedef {Object} Props
   * @property {any} personne
   * @property {any} [verdict]
   * @property {number|null} [anneeId]
   * @property {(id: number) => void} [onOuvrirFiche]
   * @property {(p: any) => void} [onDeplacer]
   * @property {(p: any) => void} [onRenommer]
   * @property {(p: any) => void} [onFigerAdresse]
   */
  /** @type {Props} */
  let {
    personne,
    verdict = null,
    anneeId = null,
    onOuvrirFiche,
    onDeplacer,
    onRenommer,
    onFigerAdresse,
  } = $props();

  const libelle = (e) => String(e).replace(/^Error:\s*/, "");

  let fiche = $state(/** @type {any} */ (null));
  let ficheEnCours = $state(false);
  let enquete = $state(/** @type {any} */ (null));
  let enqueteEnCours = $state(false);

  /** `null` tant qu'on n'a rien demandé ; une liste, même vide, ensuite. */
  let secrets = $state(/** @type {any[]|null} */ (null));
  let coffreFerme = $state(false);
  let motMaitre = $state("");
  let secretEnCours = $state(false);

  // La fiche se charge après une courte pause : maintenir la flèche fait
  // défiler vingt personnes, et vingt fiches demandées pour n'en lire
  // qu'une seraient du bruit.
  //
  // Suivie par son identifiant, pas par l'objet : la liste se recalcule
  // (un verdict arrive, une adresse est figée) et rend un objet neuf pour
  // la même personne — la fiche n'a pas à se recharger pour autant.
  let idSuivi = $derived(personne?.id ?? null);
  let sansCompteSuivi = $derived(!!personne?.sans_compte);

  $effect(() => {
    const id = idSuivi;
    const sansCompte = sansCompteSuivi;
    untrack(() => {
      fiche = null;
      enquete = null;
      secrets = null;
      coffreFerme = false;
      motMaitre = "";
      ficheEnCours = false;
    });
    if (!id || sansCompte) return;
    const minuteur = setTimeout(async () => {
      ficheEnCours = true;
      try {
        const f = await personnes.fiche(id);
        if (personne?.id === id) fiche = f;
      } catch (e) {
        if (personne?.id === id) notify.erreur(libelle(e));
      } finally {
        if (personne?.id === id) ficheEnCours = false;
      }
    }, 140);
    return () => clearTimeout(minuteur);
  });

  async function copier(texte, message) {
    if (!texte) return;
    try {
      await navigator.clipboard.writeText(texte);
      notify.succes(message);
    } catch {
      notify.erreur("Le système a refusé la copie.");
    }
  }

  let identifiant = $derived(personne?.login_constate ?? personne?.login ?? "");

  /** Pour le raccourci `C` de la liste. */
  export function copierAdresse() {
    copier(personne?.email, `Adresse copiée : ${personne?.email}`);
  }

  /** Pour le raccourci `M` de la liste. */
  export function montrerMotDePasse() {
    chercherSecrets();
  }

  async function chercherSecrets() {
    if (!personne || personne.sans_compte) return;
    secretEnCours = true;
    try {
      const etat = await coffreApi.etat();
      if (!etat.initialise) {
        notify.info("Le coffre n'est pas encore créé : l'écran Coffre le prépare.");
        return;
      }
      if (!etat.ouvert) {
        coffreFerme = true;
        secrets = null;
        return;
      }
      coffreFerme = false;
      const trouves = await coffreApi.chercher(identifiant || personne.nom);
      secrets = trouves.filter((s) => s.personne_id === personne.id);
    } catch (e) {
      notify.erreur(libelle(e));
    } finally {
      secretEnCours = false;
    }
  }

  async function ouvrirCoffre() {
    if (!motMaitre) return;
    secretEnCours = true;
    try {
      await coffreApi.ouvrir(motMaitre);
      motMaitre = "";
    } catch (e) {
      notify.erreur(libelle(e));
      secretEnCours = false;
      return;
    }
    await chercherSecrets();
  }

  async function enqueter() {
    if (!personne || personne.sans_compte) return;
    enqueteEnCours = true;
    enquete = null;
    try {
      enquete = await personnes.enquete(personne.id, { anneeId });
    } catch (e) {
      notify.erreur(libelle(e), { duree: 12000 });
    } finally {
      enqueteEnCours = false;
    }
  }

  const LOGOS = { charlemagne: logoCharlemagne, google: logoGoogle, koxo: logoKoxo };

  let systemes = $derived(
    ["charlemagne", "google", "koxo"].map((s) => ({
      systeme: s,
      nom: NOM_SYSTEME[s],
      logo: LOGOS[s],
      v: verdict?.systemes?.find((x) => x.systeme === s) ?? null,
    })),
  );

  /** @returns {{etat: "pret"|"ecart"|"attente"|"inconnu", texte: string}} */
  function pastille(v) {
    if (!v) return { etat: "inconnu", texte: "Pas vérifié" };
    if (v.etat === "accord") return { etat: "pret", texte: "Cohérent" };
    if (v.etat === "absent") return { etat: "attente", texte: "Absent" };
    return { etat: "ecart", texte: "Écart" };
  }

  /** Depuis quand le constat date, en clair. */
  let dateVerdict = $derived.by(() => {
    if (!verdict?.verifie_le) return "";
    const h = Math.round((Date.now() - new Date(verdict.verifie_le + "Z").getTime()) / 3600000);
    if (h < 1) return "vérifié il y a moins d'une heure";
    if (h < 24) return `vérifié il y a ${h} h`;
    const j = Math.round(h / 24);
    return j === 1 ? "vérifié hier" : `vérifié il y a ${j} jours`;
  });

  let parcours = $derived((fiche?.parcours ?? []).slice(0, 4).reverse());
  let compteGoogle = $derived(fiche?.comptes?.find((c) => c.cible === "google") ?? null);

  const LIBELLE_SOURCE = {
    referentiel: "Référentiel",
    google: "Google",
    coffre: "Coffre",
    charlemagne: "Charlemagne",
    koxo: "KoXo",
    ts1000: "TS1000",
  };

  const NOM_CIBLE = { koxo: "KoXo", google: "Google", charlemagne: "Charlemagne" };
  const REGIMES = { D: "Demi-pension", E: "Externe", P: "Interne" };
</script>

{#snippet titre(texte, couleur, droite = "")}
  <div class="flex items-center gap-2.5">
    <span class="h-2.5 w-2.5 shrink-0 rounded-full" style="background: {couleur};"></span>
    <h3 class="titre-affiche text-base whitespace-nowrap text-stone-900 dark:text-stone-100">{texte}</h3>
    <span class="h-px flex-1 bg-stone-200 dark:bg-stone-800"></span>
    {#if droite}
      <span class="text-xs whitespace-nowrap text-stone-500 dark:text-stone-400">{droite}</span>
    {/if}
  </div>
{/snippet}

{#snippet puce(icone, texte, onclick, mono = false, occupe = false)}
  {@const Icone = icone}
  <button
    type="button"
    class="inline-flex max-w-full items-center gap-2 rounded-full border border-stone-300 px-3.5 py-1.5 text-[13px]
           font-semibold text-stone-800 transition hover:border-stone-400 hover:bg-stone-100 disabled:opacity-50
           dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
    disabled={occupe}
    {onclick}
  >
    <Icone class="h-3.5 w-3.5 shrink-0" />
    <span class="truncate {mono ? 'font-mono font-medium' : ''}">{texte}</span>
  </button>
{/snippet}

<div class="flex h-full min-h-0 flex-col">
  <div class="min-h-0 flex-1 space-y-7 overflow-y-auto px-8 pt-6 pb-8">
    <!-- L'identité, en tête : la photo en portrait, parce que c'est là
         qu'on reconnaît quelqu'un, et le nom en grand. -->
    <div class="flex items-start gap-5">
      <div class="w-24 shrink-0">
        <Avatar
          personneId={personne.sans_compte ? null : personne.id}
          nom={personne.nom}
          prenom={personne.prenom}
          forme="portrait"
        />
      </div>
      <div class="min-w-0 flex-1">
        <h2 class="titre-affiche text-[28px] leading-tight text-stone-900 dark:text-stone-100">
          {personne.prenom} <span class="uppercase">{personne.nom}</span>
        </h2>
        <p class="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-stone-600 dark:text-stone-400">
          {#if personne.cle_pivot}<span class="font-mono">{personne.cle_pivot}</span><span>·</span>{/if}
          <span>{personne.type === "adulte" ? "Adulte" : "Élève"}</span>
          {#if personne.classe}
            <span>·</span><span class="font-semibold text-emerald-700 dark:text-emerald-400">{personne.classe}</span>
          {/if}
          <span>·</span><span>{personne.site ? `Site ${personne.site}` : "Sans site"}</span>
          {#if personne.mouvement === "entrant"}
            <Pastille etat="reference" texte="nouveau" />
          {:else if personne.mouvement === "sortant"}
            <Pastille etat="attente" texte="parti" />
          {/if}
        </p>
        {#if personne.detail}
          <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">{personne.detail}</p>
        {/if}
        {#if fiche?.anciennes_fiches?.length}
          <p class="mt-1 flex items-center gap-1.5 text-xs text-stone-500 dark:text-stone-400">
            <GitMerge class="h-3.5 w-3.5" />
            Ancienne fiche <span class="font-mono">{fiche.anciennes_fiches.join(", ")}</span>, réunie à celle-ci
          </p>
        {/if}
      </div>
      {#if !personne.sans_compte}
        <Bouton variante="primary" icon={ArrowRight} onclick={() => onOuvrirFiche?.(personne.id)}>
          Ouvrir la fiche
        </Bouton>
      {/if}
    </div>

    {#if personne.sans_compte}
      <p class="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:bg-amber-400/10 dark:text-amber-200">
        Cette personne vient du tableau des professeurs et n'est pas encore au
        référentiel : aucun compte, aucune fiche à ouvrir. Elle y entrera à
        l'ingestion de l'export des adultes.
      </p>
    {:else}
      <!-- Ce qu'on vient chercher le plus souvent, à un clic. -->
      <div class="space-y-3">
        <div class="flex flex-wrap items-center gap-2">
          {#if identifiant}
            {@render puce(Copy, identifiant, () => copier(identifiant, `Identifiant copié : ${identifiant}`), true)}
          {/if}
          {#if personne.email}
            {@render puce(AtSign, personne.email, copierAdresse, true)}
          {/if}
          {@render puce(KeyRound, "Mot de passe", chercherSecrets, false, secretEnCours)}
        </div>
        <div class="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[13px] font-semibold text-stone-600 dark:text-stone-400">
          <button type="button" class="inline-flex items-center gap-1.5 hover:text-stone-900 dark:hover:text-stone-100" onclick={() => onDeplacer?.(personne)}>
            <FolderTree class="h-3.5 w-3.5" /> Déplacer dans Google
          </button>
          <button type="button" class="inline-flex items-center gap-1.5 hover:text-stone-900 disabled:opacity-50 dark:hover:text-stone-100" disabled={enqueteEnCours} onclick={enqueter}>
            <Radar class="h-3.5 w-3.5" /> {enqueteEnCours ? "Interrogation…" : "Interroger les sources"}
          </button>
          <button type="button" class="inline-flex items-center gap-1.5 hover:text-stone-900 dark:hover:text-stone-100" onclick={() => onRenommer?.(personne)}>
            <Pencil class="h-3.5 w-3.5" /> Corriger le nom
          </button>
          <button type="button" class="inline-flex items-center gap-1.5 hover:text-stone-900 dark:hover:text-stone-100" onclick={() => onFigerAdresse?.(personne)}>
            <Lock class="h-3.5 w-3.5" /> Figer l'adresse
          </button>
        </div>

        {#if coffreFerme}
          <div class="flex flex-wrap items-center gap-2 rounded-xl bg-stone-50 px-4 py-3 dark:bg-stone-900">
            <KeyRound class="h-4 w-4 text-stone-500" />
            <span class="text-sm text-stone-700 dark:text-stone-300">Le coffre est fermé.</span>
            <input
              type="password"
              class="champ !w-56 !py-1.5"
              placeholder="Mot de passe maître"
              autocomplete="current-password"
              aria-label="Mot de passe maître du coffre"
              bind:value={motMaitre}
              onkeydown={(e) => e.key === "Enter" && ouvrirCoffre()}
            />
            <Bouton taille="sm" variante="primary" occupe={secretEnCours} disabled={!motMaitre} onclick={ouvrirCoffre}>
              Ouvrir
            </Bouton>
          </div>
        {:else if secrets}
          <div class="rounded-xl bg-stone-50 px-4 py-3 dark:bg-stone-900">
            {#if secrets.length === 0}
              <p class="text-sm text-stone-600 dark:text-stone-400">
                Aucun mot de passe au coffre pour {personne.prenom} {personne.nom}.
              </p>
            {:else}
              <ul class="space-y-1.5">
                {#each secrets as s (s.cible + (s.site ?? ""))}
                  <li class="flex flex-wrap items-center gap-3 text-sm">
                    <span class="w-40 shrink-0 text-stone-500 dark:text-stone-400">
                      {NOM_CIBLE[s.cible] ?? s.cible}{s.site ? ` ${s.site}` : ""}{s.origine === "genere" ? " · généré" : ""}
                    </span>
                    {#if s.identifiant && s.identifiant !== identifiant}
                      <span class="font-mono text-xs text-stone-500">{s.identifiant}</span>
                    {/if}
                    <button
                      type="button"
                      class="rounded-md px-1.5 py-0.5 font-mono font-semibold hover:bg-stone-200 dark:hover:bg-stone-800"
                      title="Copier"
                      onclick={() => copier(s.mot_de_passe, "Mot de passe copié")}
                    >
                      {s.mot_de_passe}
                    </button>
                  </li>
                {/each}
              </ul>
            {/if}
          </div>
        {/if}
      </div>

      <section class="space-y-2">
        {@render titre("Dans les systèmes", "var(--color-emerald-600)", dateVerdict)}
        <div>
          {#each systemes as s (s.systeme)}
            {@const pa = pastille(s.v)}
            <div class="grid grid-cols-[170px_minmax(0,1fr)_auto] items-center gap-4 border-b border-stone-200 py-2.5 dark:border-stone-800">
              <span class="flex items-center gap-3 text-sm font-semibold">
                <img src={s.logo} alt="" class="h-6 w-6 object-contain" />
                {s.nom}
              </span>
              <span class="min-w-0 truncate text-sm text-stone-600 dark:text-stone-400">
                {#if s.v?.etat === "ecart"}
                  <b class="text-red-700 dark:text-red-400">{s.v.constate ?? "—"}</b>
                  <span class="text-stone-500">— le référentiel dit</span> <b class="text-stone-800 dark:text-stone-200">{s.v.attendu ?? "—"}</b>
                {:else if s.v}
                  {s.v.constate ?? s.v.attendu ?? ""}
                {:else}
                  <span class="text-stone-400 dark:text-stone-500">jamais croisé — la Concordance le dira</span>
                {/if}
              </span>
              <Pastille etat={pa.etat} texte={pa.texte} />
            </div>
          {/each}
        </div>
      </section>

      <section class="space-y-3">
        {@render titre("Parcours", "#FF7A59")}
        {#if ficheEnCours && !fiche}
          <p class="text-sm text-stone-500 dark:text-stone-400">Lecture…</p>
        {:else if parcours.length}
          <ol class="flex">
            {#each parcours as a, i (a.annee)}
              {@const courant = i === parcours.length - 1}
              <li class="min-w-0 flex-1">
                <div class="flex items-center">
                  <span
                    class="h-4 w-4 shrink-0 rounded-full {courant
                      ? 'border-[3px] border-emerald-100 bg-emerald-600 dark:border-emerald-900'
                      : 'border-2 border-stone-300 bg-white dark:border-stone-600 dark:bg-stone-900'}"
                  ></span>
                  <span class="h-0.5 flex-1 {courant ? '' : 'bg-stone-300 dark:bg-stone-700'}"></span>
                </div>
                <p class="mt-2 text-xs tabular-nums text-stone-500 dark:text-stone-400">{a.annee}</p>
                <p class="mt-0.5 text-sm font-bold {courant ? 'text-emerald-700 dark:text-emerald-400' : 'text-stone-800 dark:text-stone-200'}">
                  {a.classe ?? "—"}
                </p>
                {#if a.regime}
                  <p class="text-xs text-stone-500 dark:text-stone-400">régime {a.regime}</p>
                {/if}
              </li>
            {/each}
          </ol>
        {:else if fiche}
          <p class="text-sm text-stone-500 dark:text-stone-400">Aucune année ingérée pour cette personne.</p>
        {/if}
      </section>

      <section class="space-y-3">
        {@render titre("Identité", "#2BC4D8")}
        <dl class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm lg:grid-cols-3">
          <div>
            <dt class="text-xs text-stone-500 dark:text-stone-400">Identifiant</dt>
            <dd class="mt-0.5 font-mono font-semibold">
              {identifiant || "—"}
              {#if personne.login_constate && personne.login_constate !== personne.login}
                <span class="ml-1 font-sans text-[11px] font-medium text-amber-700 dark:text-amber-400" title="Le référentiel avait calculé « {personne.login} », déjà pris chez lui.">constaté dans KoXo</span>
              {/if}
            </dd>
          </div>
          <div class="col-span-2 min-w-0">
            <dt class="text-xs text-stone-500 dark:text-stone-400">Adresse</dt>
            <dd class="mt-0.5 flex items-center gap-1.5 font-semibold">
              {#if personne.email_est_constate}<Lock class="h-3 w-3 shrink-0 text-emerald-600 dark:text-emerald-400" />{/if}
              <span class="truncate font-mono {personne.email_est_constate ? '' : 'italic text-stone-500 dark:text-stone-400'}">{personne.email ?? "—"}</span>
              <span class="shrink-0 text-[11px] font-medium text-stone-500 dark:text-stone-400">
                {personne.email_est_constate ? "constatée" : "calculée, pas encore relevée dans Google"}
              </span>
            </dd>
          </div>
          <div>
            <dt class="text-xs text-stone-500 dark:text-stone-400">Badge</dt>
            <dd class="mt-0.5 font-semibold tabular-nums">{personne.badge ?? "—"}</dd>
          </div>
          <div>
            <dt class="text-xs text-stone-500 dark:text-stone-400">INE</dt>
            <dd class="mt-0.5 font-semibold {personne.ine ? 'font-mono' : 'text-amber-700 dark:text-amber-400'}">
              {personne.ine ?? "pas encore relevé"}
            </dd>
          </div>
          <div>
            <dt class="text-xs text-stone-500 dark:text-stone-400">Naissance</dt>
            <dd class="mt-0.5 font-semibold tabular-nums {personne.date_naissance ? '' : 'text-amber-700 dark:text-amber-400'}">
              {personne.date_naissance ? jour(personne.date_naissance) : "pas encore relevée"}
            </dd>
          </div>
          {#if personne.regime}
            <div>
              <dt class="text-xs text-stone-500 dark:text-stone-400">Régime</dt>
              <dd class="mt-0.5 font-semibold">{REGIMES[personne.regime] ?? personne.regime}</dd>
            </div>
          {/if}
          {#if personne.date_entree}
            <div>
              <dt class="text-xs text-stone-500 dark:text-stone-400">Entrée</dt>
              <dd class="mt-0.5 font-semibold tabular-nums">{jour(personne.date_entree)}</dd>
            </div>
          {/if}
          {#if personne.poste_occupe}
            <div>
              <dt class="text-xs text-stone-500 dark:text-stone-400">Poste</dt>
              <dd class="mt-0.5 font-semibold">{personne.poste_occupe}</dd>
            </div>
          {/if}
          {#if personne.matieres}
            <div class="col-span-2">
              <dt class="text-xs text-stone-500 dark:text-stone-400">Matières</dt>
              <dd class="mt-0.5 font-semibold">{personne.matieres.split(";").join(" · ")}</dd>
            </div>
          {/if}
          {#if personne.classes_prof_principal}
            <div>
              <dt class="text-xs text-stone-500 dark:text-stone-400">Prof. principal</dt>
              <dd class="mt-0.5 font-semibold">{personne.classes_prof_principal.split(";").join(" · ")}</dd>
            </div>
          {/if}
        </dl>
      </section>

      {#if compteGoogle}
        <section class="space-y-3">
          {@render titre("Compte Google", "#2F6CE0")}
          <dl class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm lg:grid-cols-3">
            <div>
              <dt class="text-xs text-stone-500 dark:text-stone-400">Suivi</dt>
              <dd class="mt-0.5 font-semibold">{compteGoogle.etat}</dd>
            </div>
            {#if compteGoogle.ou_appliquee}
              <div class="col-span-2 min-w-0">
                <dt class="text-xs text-stone-500 dark:text-stone-400">OU</dt>
                <dd class="mt-0.5 truncate font-mono text-[13px] font-semibold">{compteGoogle.ou_appliquee}</dd>
              </div>
            {/if}
            {#if compteGoogle.ou_constatee && compteGoogle.ou_constatee !== compteGoogle.ou_appliquee}
              <div class="col-span-2 min-w-0">
                <dt class="text-xs text-stone-500 dark:text-stone-400">Dans Google</dt>
                <dd class="mt-0.5 truncate font-mono text-[13px] font-semibold text-amber-700 dark:text-amber-400">{compteGoogle.ou_constatee}</dd>
              </div>
            {/if}
            {#if compteGoogle.date_prevue_purge}
              <div>
                <dt class="text-xs text-stone-500 dark:text-stone-400">Suppression</dt>
                <dd class="mt-0.5 font-semibold tabular-nums">{jour(compteGoogle.date_prevue_purge)}</dd>
              </div>
            {/if}
          </dl>
        </section>
      {/if}

      {#if enquete && enquete.personne_id === personne.id}
        <section class="space-y-3">
          {@render titre("Ce que disent les sources", "#FFB938", enquete.tout_concorde ? "tout concorde" : "")}
          {#each enquete.divergences as d (d.quoi)}
            <p class="rounded-lg px-3 py-2 text-sm {d.gravite === 'bloquant'
              ? 'bg-red-50 text-red-800 dark:bg-red-500/10 dark:text-red-200'
              : 'bg-amber-50 text-amber-900 dark:bg-amber-400/10 dark:text-amber-200'}">
              <b>{d.quoi}</b> — <span class="font-mono">{d.valeurs[0] ?? "—"}</span> contre
              <span class="font-mono">{d.valeurs[1] ?? "—"}</span>
            </p>
          {/each}
          <div class="grid gap-3 sm:grid-cols-2">
            {#each enquete.dires as d (d.source)}
              <div class="text-xs">
                <p class="flex items-center gap-1.5 font-semibold text-stone-800 dark:text-stone-200">
                  {LIBELLE_SOURCE[d.source] ?? d.source}
                  {#if !d.consultee}<span class="font-normal text-stone-500">· pas consultée</span>{/if}
                </p>
                {#if d.motif}<p class="text-stone-500 dark:text-stone-400">{d.motif}</p>{/if}
                {#each Object.entries(d.valeurs).filter(([, v]) => v) as [cle, valeur] (cle)}
                  <p class="flex gap-2">
                    <span class="w-28 shrink-0 text-stone-500 dark:text-stone-400">{cle.replace(/_/g, " ")}</span>
                    <span class="min-w-0 break-all font-mono">{valeur}</span>
                  </p>
                {/each}
              </div>
            {/each}
          </div>
        </section>
      {/if}
    {/if}
  </div>

  <div class="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-stone-200 px-8 py-2.5 text-xs text-stone-500 dark:border-stone-800 dark:text-stone-400">
    <span class="flex items-center gap-1.5"><Touche texte="↑" /><Touche texte="↓" /> changer de personne</span>
    <span class="flex items-center gap-1.5"><Touche texte="Entrée" /> ouvrir la fiche</span>
    <span class="flex items-center gap-1.5"><Touche texte="C" /> copier l'adresse</span>
    <span class="flex items-center gap-1.5"><Touche texte="M" /> mot de passe</span>
    <span class="flex items-center gap-1.5"><Touche texte="/" /> chercher</span>
  </div>
</div>
