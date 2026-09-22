<script>
  /**
   * Faire entrer quelqu'un en cours d'année.
   *
   * Tout venait de l'ingestion Charlemagne, qui arrive une fois l'an. Un
   * élève inscrit un mardi de novembre, une AESH qui prend son poste le
   * jour même, n'avaient aucune porte d'entrée.
   *
   * L'écran suit les quatre gestes du service, et les montre comme quatre
   * gestes : entre le compte et le groupe, il y a l'import du CSV dans la
   * console Google, que personne d'autre que l'utilisateur ne peut faire.
   */
  import { onMount } from "svelte";
  import UserPlus from "@lucide/svelte/icons/user-plus";
  import Download from "@lucide/svelte/icons/download";
  import Users from "@lucide/svelte/icons/users";
  import Laptop from "@lucide/svelte/icons/laptop";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import BarreAction from "$lib/components/BarreAction.svelte";
  import Check from "@lucide/svelte/icons/check";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import {
    annees as anneesApi,
    arrivees as arriveesApi,
    sites as sitesApi,
    tableCorrespondance,
    telechargerFichierBase64,
  } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";
  import { TEINTES } from "$lib/familles.js";

  let listeSites = $state(/** @type {any[]} */ ([]));
  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let classes = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let occupe = $state(false);

  let typePersonne = $state(/** @type {"eleve"|"adulte"} */ ("eleve"));
  let siteId = $state(/** @type {number | null} */ (null));
  let anneeId = $state(/** @type {number | null} */ (null));
  let nom = $state("");
  let prenom = $state("");
  let classe = $state("");
  let idCharlemagne = $state("");
  let discipline = $state("");

  let proposition = $state(/** @type {any} */ (null));
  let enregistree = $state(/** @type {any} */ (null));

  /**
   * Pré-rentrée ou définitive.
   *
   * Avant la rentrée, un élève attend dans l'unité de pré-rentrée, où la
   * classe ne transparaît pas. Après, il va dans celle de sa classe. Le
   * programme n'a pas à deviner où en est la campagne.
   */
  let ouChoisie = $state(/** @type {"pre"|"definitive"} */ ("definitive"));
  let compteFait = $state(false);

  onMount(async () => {
    try {
      const [s, a, tc] = await Promise.all([
        sitesApi.lister(),
        anneesApi.lister(),
        tableCorrespondance.lister(),
      ]);
      listeSites = s;
      listeAnnees = a;
      classes = tc;
      anneeId =
        [...a].sort((x, y) => x.libelle.localeCompare(y.libelle)).at(-1)?.id ?? null;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      chargement = false;
    }
  });

  let codesClasses = $derived(
    [
      ...new Set(
        classes
          .filter((c) => !siteId || c.site_id === siteId)
          .map((c) => c.classe_code_court),
      ),
    ].sort(),
  );

  function corps() {
    return {
      site_id: siteId,
      type_personne: typePersonne,
      nom,
      prenom,
      annee_id: anneeId,
      classe: typePersonne === "eleve" ? classe : null,
      id_charlemagne: idCharlemagne.trim() ? Number(idCharlemagne) : null,
    };
  }

  let peutProposer = $derived(
    Boolean(
      siteId && anneeId && nom.trim() && prenom.trim() &&
        (typePersonne === "adulte" || classe),
    ),
  );

  async function proposer() {
    occupe = true;
    proposition = null;
    enregistree = null;
    compteFait = false;
    try {
      proposition = await arriveesApi.proposer(corps());
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      occupe = false;
    }
  }

  async function enregistrer() {
    occupe = true;
    try {
      enregistree = await arriveesApi.enregistrer({ ...corps(), mode: "reel" });
      notify.succes(
        `${prenom} ${nom} est au référentiel — ${enregistree.login}`,
      );
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      occupe = false;
    }
  }

  async function fabriquerCompte() {
    if (!enregistree || !proposition) return;
    const ou =
      typePersonne === "adulte"
        ? ouPersonnel
        : ouChoisie === "pre"
          ? proposition.ou_pre_rentree
          : proposition.ou_definitive;
    if (!ou) {
      notify.avertissement("Aucune unité d'organisation à viser.");
      return;
    }
    occupe = true;
    try {
      const r = await arriveesApi.compteGoogle({
        personneId: enregistree.personne_id,
        ou,
        mode: "reel",
      });
      telechargerFichierBase64(r.nom_fichier, r.csv_base64, "text/csv");
      compteFait = true;
      for (const a of r.avertissements) notify.avertissement(a, { duree: 9000 });
      notify.succes(
        `${r.email} — mot de passe fabriqué et rangé au coffre. Importe le fichier dans la console.`,
      );
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  /** Pour un adulte, aucune table ne dit où le ranger : on le saisit. */
  let ouPersonnel = $state("/6. Personnel/AESH");

  async function rejoindreGroupe() {
    if (!enregistree || !proposition?.groupe_google) return;
    occupe = true;
    try {
      const r = await arriveesApi.rejoindreGroupe({
        personneId: enregistree.personne_id,
        groupe: proposition.groupe_google,
      });
      notify.succes(r.message);
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  async function ajouterAuxChromebooks() {
    if (!enregistree || !anneeId) return;
    occupe = true;
    try {
      const r = await arriveesApi.tableauChromebooks({
        personneId: enregistree.personne_id,
        anneeId,
        discipline: discipline.trim() || null,
      });
      notify.succes(r.message);
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      occupe = false;
    }
  }

  function recommencer() {
    proposition = null;
    enregistree = null;
    compteFait = false;
    nom = "";
    prenom = "";
    idCharlemagne = "";
  }

  /**
   * Les six systèmes, et lequel le programme sait vraiment servir.
   *
   * La maquette coche six cases et annonce « Créer sur les 6 systèmes ».
   * Le programme n'en touche que deux : le référentiel, qu'il écrit, et
   * Google, dont il fabrique le compte et le groupe. KoXo, PMB, Sodexo et
   * CardStudio se nourrissent de fichiers, produits ailleurs et déposés à
   * la main.
   *
   * Les afficher pareil laisserait croire que le bouton les traite. Un
   * écran qui fait un tiers du travail sans nommer les deux autres est
   * plus dangereux qu'un écran inerte — c'est en confiance qu'on oublie.
   *
   * Les lignes automatisables portent donc une case qui **commande**, les
   * autres une case qui **constate** : on la coche une fois le geste fait
   * de son côté.
   */
  let systemes = $derived.by(() => {
    if (!proposition) return [];
    const eleve = typePersonne === "eleve";
    const ou =
      typePersonne === "adulte"
        ? ouPersonnel
        : ouChoisie === "pre"
          ? proposition.ou_pre_rentree
          : proposition.ou_definitive;
    const sansKoxo = proposition.site_nom === "NDE";
    return [
      {
        cle: "referentiel",
        nom: "Référentiel",
        teinte: TEINTES.annee,
        quoi: "Créer la personne",
        valeur: [
          proposition.login_propose,
          proposition.badge ? `badge ${proposition.badge}` : null,
          proposition.classe ? `classe ${proposition.classe}` : null,
          `site ${proposition.site_nom}`,
        ]
          .filter(Boolean)
          .join(" · "),
        automatique: true,
        force: true,
        fait: Boolean(enregistree),
      },
      {
        cle: "google",
        nom: "Google",
        teinte: TEINTES.google,
        quoi: eleve ? "Compte, unité et groupe" : "Compte et unité",
        valeur: [proposition.email_propose, ou].filter(Boolean).join(" · "),
        automatique: true,
        fait: compteFait,
      },
      {
        cle: "koxo",
        nom: "KoXo",
        teinte: TEINTES.koxo,
        quoi: sansKoxo ? "Aucun — NDE n'a pas de KoXo" : "Compte réseau",
        valeur: sansKoxo
          ? "—"
          : `ID unique ${proposition.badge ?? "—"} · mot de passe à générer`,
        automatique: false,
        sansObjet: sansKoxo,
      },
      {
        cle: "pmb",
        nom: "PMB",
        teinte: TEINTES.materiel,
        quoi: "Lecteur du CDI",
        valeur: proposition.classe ? `Classe ${proposition.classe}` : "Adulte",
        automatique: false,
      },
      {
        cle: "sodexo",
        nom: "Sodexo",
        teinte: TEINTES.repas,
        quoi: eleve ? "Élève dans sa classe" : "Convive",
        valeur: proposition.classe ? `Classe ${proposition.classe}` : "Adulte",
        automatique: false,
      },
      {
        cle: "cardstudio",
        nom: "CardStudio",
        teinte: TEINTES.photos,
        quoi: "Carte à imprimer",
        valeur: proposition.badge
          ? `Badge ${proposition.badge}`
          : "Sans identifiant Charlemagne, pas de badge",
        automatique: false,
        sansObjet: !proposition.badge,
      },
    ];
  });

  /**
   * Ce qui a été fait à la main, coché par l'utilisateur.
   *
   * Le cochage survit à la navigation : une arrivée se traite sur
   * plusieurs jours — le compte le lundi, la carte le jeudi.
   */
  let faits = $state(lire("arrivees.faits", /** @type {Record<string, boolean>} */ ({})));
  $effect(() => ecrire("arrivees.faits", faits));

  let nbAutomatiques = $derived(
    systemes.filter((s) => s.automatique && !s.fait).length,
  );
</script>

<section class="flex min-h-[calc(100vh-10rem)] flex-col space-y-5">
  <EnTetePage
    icon={UserPlus}
    titre="Un élève arrive"
    description="Créer la personne et tout ce qui en découle, système par système. Le référentiel d'abord — sans lui, la composition des groupes et la prochaine ingestion ignoreraient l'arrivant."
  />

  {#if chargement}
    <p class="text-sm text-stone-500 dark:text-stone-400">Chargement…</p>
  {:else}
    <!-- ----------------------------------------------------------------
         Qui arrive. Une seule ligne : c'est une phrase, pas un dossier.
         ---------------------------------------------------------------- -->
    <div class="flex flex-wrap items-end gap-4 border-b border-stone-200 pb-5 dark:border-stone-800">
      <div>
        <label class="libelle-champ" for="a-pop">Population</label>
        <select
          id="a-pop"
          class="champ mt-1 w-36"
          bind:value={typePersonne}
          onchange={() => { proposition = null; enregistree = null; }}
        >
          <option value="eleve">Élève</option>
          <option value="adulte">Adulte</option>
        </select>
      </div>
      <div>
        <label class="libelle-champ" for="a-nom">Nom</label>
        <input id="a-nom" class="champ mt-1 w-44" bind:value={nom} placeholder="MARTIN" />
      </div>
      <div>
        <label class="libelle-champ" for="a-prenom">Prénom</label>
        <input id="a-prenom" class="champ mt-1 w-44" bind:value={prenom} placeholder="Louise" />
      </div>
      <div>
        <label class="libelle-champ" for="a-site">Site</label>
        <select
          id="a-site"
          class="champ mt-1 w-32"
          bind:value={siteId}
          onchange={() => (proposition = null)}
        >
          <option value={null}>—</option>
          {#each listeSites as s (s.id)}<option value={s.id}>{s.nom}</option>{/each}
        </select>
      </div>
      {#if typePersonne === "eleve"}
        <div>
          <label class="libelle-champ" for="a-classe">Classe</label>
          <select
            id="a-classe"
            class="champ mt-1 w-36 !border-2 font-mono font-bold"
            style="border-color: {TEINTES.google};"
            bind:value={classe}
            onchange={() => (proposition = null)}
          >
            <option value="">—</option>
            {#each codesClasses as c (c)}<option value={c}>{c}</option>{/each}
          </select>
        </div>
      {:else}
        <div>
          <label class="libelle-champ" for="a-fonction">Fonction</label>
          <input id="a-fonction" class="champ mt-1 w-40" bind:value={discipline} placeholder="AESH" />
        </div>
      {/if}
      <div>
        <label class="libelle-champ" for="a-id">Identifiant Charlemagne</label>
        <input
          id="a-id"
          class="champ mt-1 w-36"
          bind:value={idCharlemagne}
          inputmode="numeric"
          placeholder="facultatif"
        />
      </div>
      <div>
        <label class="libelle-champ" for="a-annee">Année</label>
        <select id="a-annee" class="champ mt-1 w-36" bind:value={anneeId}>
          {#each listeAnnees as a (a.id)}<option value={a.id}>{a.libelle}</option>{/each}
        </select>
      </div>

      {#if !proposition}
        <Bouton
          variante="primary"
          icon={ArrowRight}
          occupe={occupe}
          disabled={!peutProposer}
          onclick={proposer}
        >
          Calculer
        </Bouton>
      {:else}
        <!-- Ce que le programme en déduit, et s'il connaît déjà quelqu'un. -->
        <div class="flex items-center gap-3 pb-1.5 text-sm">
          <span class="font-mono text-xs text-stone-600 dark:text-stone-400">
            {proposition.email_propose}
          </span>
          {#if proposition.personne_existante_id}
            <Pastille etat="ecart" texte="Existe déjà au référentiel" />
          {:else}
            <Pastille etat="pret" texte="Aucun homonyme" />
          {/if}
        </div>
        <button
          class="pb-2 text-sm text-stone-500 underline hover:text-stone-800 dark:hover:text-stone-200"
          onclick={recommencer}
        >
          Recommencer
        </button>
      {/if}
    </div>

    {#if !proposition}
      <p class="py-10 text-center text-sm text-stone-500 dark:text-stone-400">
        Remplis le nom, le prénom, le site{typePersonne === "eleve" ? " et la classe" : ""} :
        le programme calculera le login, l'adresse, le badge et l'unité avant
        d'écrire quoi que ce soit.
      </p>
    {:else}
      <div class="min-h-0 flex-1 overflow-y-auto">
        <div class="mb-2 flex flex-wrap items-baseline justify-between gap-4">
          <h2 class="titre-affiche text-xl">Ce qui va être créé</h2>
          <div class="flex items-center gap-4">
            {#if typePersonne === "eleve"}
              <!-- Avant la rentrée, la classe ne transparaît pas encore :
                   l'élève attend dans l'unité de pré-rentrée. -->
              <label class="flex items-center gap-2 text-sm">
                <span class="libelle-champ">Unité visée</span>
                <select class="champ !py-1 text-xs" bind:value={ouChoisie}>
                  <option value="definitive">Celle de sa classe</option>
                  <option value="pre">Pré-rentrée</option>
                </select>
              </label>
            {:else}
              <label class="flex items-center gap-2 text-sm">
                <span class="libelle-champ">Unité</span>
                <input class="champ !py-1 w-56 font-mono text-xs" bind:value={ouPersonnel} />
              </label>
            {/if}
            <span class="text-[13px] text-stone-500 dark:text-stone-400">
              6 systèmes
            </span>
          </div>
        </div>

        <div class="grid grid-cols-[36px_150px_minmax(0,1fr)_minmax(0,1.4fr)_120px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
          <span></span>
          <span class="libelle-champ">Système</span>
          <span class="libelle-champ">Ce qui est créé</span>
          <span class="libelle-champ">Valeur</span>
          <span class="libelle-champ">État</span>
        </div>

        {#each systemes as s (s.cle)}
          <div class="grid grid-cols-[36px_150px_minmax(0,1fr)_minmax(0,1.4fr)_120px] items-center gap-3 border-b border-stone-100 py-3 text-sm dark:border-stone-800/70">
            <span>
              {#if s.sansObjet}
                <!-- Rien à faire ici : pas de case, pour qu'on ne la coche
                     pas en croyant avoir fait quelque chose. -->
              {:else if s.force}
                <input
                  type="checkbox"
                  checked
                  disabled
                  class="h-4 w-4 accent-emerald-600"
                  aria-label="Référentiel, toujours écrit"
                />
              {:else if s.automatique}
                <input
                  type="checkbox"
                  checked
                  disabled
                  class="h-4 w-4 accent-emerald-600"
                  aria-label="{s.nom}, le programme s'en charge"
                />
              {:else}
                <input
                  type="checkbox"
                  class="h-4 w-4 accent-emerald-600"
                  aria-label="Marquer « {s.nom} » comme fait"
                  checked={faits[s.cle] ?? false}
                  onchange={(e) => (faits = { ...faits, [s.cle]: e.currentTarget.checked })}
                />
              {/if}
            </span>

            <span class="flex items-center gap-2.5 font-semibold">
              <span class="h-2.5 w-2.5 shrink-0 rounded-full" style="background: {s.teinte};"></span>
              {s.nom}
            </span>

            <span class="min-w-0 truncate text-stone-600 dark:text-stone-400">{s.quoi}</span>

            <span
              class="min-w-0 truncate font-mono text-xs"
              class:text-stone-400={s.sansObjet}
              style={s.sansObjet ? "" : `color: ${s.teinte};`}
            >
              {s.valeur}
            </span>

            {#if s.sansObjet}
              <Pastille etat="inconnu" texte="Sans objet" />
            {:else if s.fait}
              <Pastille etat="pret" texte="Fait" />
            {:else if s.automatique}
              <Pastille etat="pret" texte="Prêt" />
            {:else}
              <Pastille etat="attente" texte="À la main" />
            {/if}
          </div>
        {/each}

        {#if proposition.avertissements?.length}
          <div class="mt-4 rounded-xl bg-amber-50 p-4 dark:bg-amber-400/10">
            <p class="text-[11px] font-bold tracking-[0.08em] text-amber-800 uppercase dark:text-amber-300">
              À savoir
            </p>
            <ul class="mt-1.5 space-y-1 text-sm text-amber-900 dark:text-amber-200">
              {#each proposition.avertissements as a (a)}<li>{a}</li>{/each}
            </ul>
          </div>
        {/if}

        {#if enregistree}
          <!-- Les gestes qui suivent l'écriture au référentiel : ils ne
               peuvent pas se faire avant qu'elle existe. -->
          <div class="mt-5 flex flex-wrap items-center gap-3 rounded-xl bg-stone-100 p-4 dark:bg-stone-800/60">
            <span class="text-sm">
              <strong>{prenom} {nom}</strong> est au référentiel —
              <span class="font-mono text-xs">{enregistree.login}</span>
            </span>
            <div class="ml-auto flex flex-wrap gap-2">
              <Bouton icon={Download} occupe={occupe} onclick={fabriquerCompte}>
                Fabriquer le compte Google
              </Bouton>
              {#if typePersonne === "eleve" && proposition.groupe_google}
                <Bouton icon={Users} occupe={occupe} onclick={rejoindreGroupe}>
                  Ajouter à {proposition.groupe_google}
                </Bouton>
              {/if}
              <Bouton icon={Laptop} occupe={occupe} onclick={ajouterAuxChromebooks}>
                Au tableau Chromebooks
              </Bouton>
            </div>
          </div>
        {/if}
      </div>

      <BarreAction
        message="Rien n'est modifié tant que tu n'as pas validé. Les systèmes sans API se cochent à la main, une fois le geste fait de leur côté — le fichier se produit depuis « Produire un fichier »."
      >
        <Bouton onclick={recommencer}>Annuler</Bouton>
        <Bouton
          variante="primary"
          icon={Check}
          occupe={occupe}
          disabled={Boolean(enregistree)}
          onclick={enregistrer}
        >
          {#if enregistree}
            Créé sur le référentiel
          {:else}
            Créer sur {nbAutomatiques} système{nbAutomatiques > 1 ? "s" : ""}
          {/if}
        </Bouton>
      </BarreAction>
    {/if}
  {/if}
</section>
