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
  import {
    annees as anneesApi,
    arrivees as arriveesApi,
    sites as sitesApi,
    tableCorrespondance,
    telechargerFichierBase64,
  } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

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
</script>

<section class="space-y-5">
  <EnTetePage
    icon={UserPlus}
    titre="Arrivée"
    description="Faire entrer un élève ou un adulte en cours d'année : le référentiel, puis le compte Google, puis le groupe. Le référentiel d'abord — sans lui, la composition des groupes et la prochaine ingestion ignoreraient l'arrivant."
  />

  {#if chargement}
    <p class="text-sm text-stone-500 dark:text-stone-400">Chargement…</p>
  {:else}
    <!-- 1. Qui arrive -->
    <div class="card space-y-3 p-4">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
        1 — Qui arrive
      </h2>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label class="block">
          <span class="libelle-champ">Population</span>
          <select class="champ w-full" bind:value={typePersonne}
                  onchange={() => { proposition = null; enregistree = null; }}>
            <option value="eleve">Élève</option>
            <option value="adulte">Adulte (AESH, personnel…)</option>
          </select>
        </label>
        <label class="block">
          <span class="libelle-champ">Site</span>
          <select class="champ w-full" bind:value={siteId}
                  onchange={() => (proposition = null)}>
            <option value={null}>— Choisir —</option>
            {#each listeSites as s (s.id)}<option value={s.id}>{s.nom}</option>{/each}
          </select>
        </label>
        <label class="block">
          <span class="libelle-champ">Année</span>
          <select class="champ w-full" bind:value={anneeId}>
            {#each listeAnnees as a (a.id)}<option value={a.id}>{a.libelle}</option>{/each}
          </select>
        </label>
        <label class="block">
          <span class="libelle-champ">Nom</span>
          <input class="champ w-full" bind:value={nom} placeholder="MARTIN" />
        </label>
        <label class="block">
          <span class="libelle-champ">Prénom</span>
          <input class="champ w-full" bind:value={prenom} placeholder="Louise" />
        </label>
        {#if typePersonne === "eleve"}
          <label class="block">
            <span class="libelle-champ">Classe</span>
            <select class="champ w-full" bind:value={classe}
                    onchange={() => (proposition = null)}>
              <option value="">— Choisir —</option>
              {#each codesClasses as c (c)}<option value={c}>{c}</option>{/each}
            </select>
          </label>
        {:else}
          <label class="block">
            <span class="libelle-champ">Fonction (pour les Chromebooks)</span>
            <input class="champ w-full" bind:value={discipline} placeholder="AESH" />
          </label>
        {/if}
        <label class="block">
          <span class="libelle-champ">Identifiant Charlemagne</span>
          <input class="champ w-full" bind:value={idCharlemagne}
                 inputmode="numeric" placeholder="facultatif" />
          <span class="mt-1 block text-xs text-stone-500 dark:text-stone-400">
            Sans lui, pas d'ID unique : la synchronisation KoXo ne saura pas
            reconnaître ce compte.
          </span>
        </label>
      </div>
      <Bouton icon={UserPlus} occupe={occupe} disabled={!peutProposer}
              onclick={proposer}>
        Proposer
      </Bouton>
    </div>

    <!-- 2. Ce que ça donnerait -->
    {#if proposition}
      <div class="card space-y-3 p-4">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
          2 — Ce que le programme propose
        </h2>
        <dl class="grid gap-2 text-sm sm:grid-cols-2">
          <div><dt class="text-xs uppercase text-stone-500">Identifiant</dt>
            <dd class="font-mono">{proposition.login_propose}</dd></div>
          <div><dt class="text-xs uppercase text-stone-500">Adresse</dt>
            <dd class="font-mono">{proposition.email_propose}</dd></div>
          <div><dt class="text-xs uppercase text-stone-500">ID unique</dt>
            <dd class="font-mono">{proposition.badge ?? "—"}</dd></div>
          {#if proposition.groupe_google}
            <div><dt class="text-xs uppercase text-stone-500">Groupe de classe</dt>
              <dd class="font-mono">{proposition.groupe_google}</dd></div>
          {/if}
        </dl>

        {#each proposition.avertissements as a}
          <p class="rounded-lg border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
            {a}
          </p>
        {/each}

        {#if !enregistree}
          <Bouton variante="primary" occupe={occupe} onclick={enregistrer}>
            Enregistrer au référentiel
          </Bouton>
        {:else}
          <p class="text-sm text-emerald-700 dark:text-emerald-400">
            Enregistré — {enregistree.login} · {enregistree.email}
          </p>
        {/if}
      </div>
    {/if}

    <!-- 3. Le compte Google -->
    {#if enregistree}
      <div class="card space-y-3 p-4">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
          3 — Le compte Google
        </h2>
        <p class="text-xs text-stone-500 dark:text-stone-400">
          La console crée les comptes depuis un CSV. Le fichier porte l'unité
          d'organisation visée, pour que le compte y naisse plutôt que d'y
          être déplacé ensuite. Le mot de passe est fabriqué et rangé au
          coffre dans le même geste — <strong>le coffre doit être ouvert</strong>.
        </p>

        {#if typePersonne === "eleve"}
          <fieldset class="space-y-1">
            <legend class="libelle-champ">Où le ranger</legend>
            <label class="flex items-center gap-2 text-sm">
              <input type="radio" bind:group={ouChoisie} value="definitive" />
              <span>Unité définitive — <span class="font-mono text-xs">{proposition.ou_definitive}</span></span>
            </label>
            <label class="flex items-center gap-2 text-sm">
              <input type="radio" bind:group={ouChoisie} value="pre" />
              <span>Pré-rentrée — <span class="font-mono text-xs">{proposition.ou_pre_rentree}</span></span>
            </label>
          </fieldset>
        {:else}
          <label class="block">
            <span class="libelle-champ">Unité d'organisation</span>
            <input class="champ w-full font-mono text-sm" bind:value={ouPersonnel} />
            <span class="mt-1 block text-xs text-stone-500 dark:text-stone-400">
              C'est elle qui dit à quel titre la personne est là, et l'écran
              Chromebooks s'en sert.
            </span>
          </label>
        {/if}

        <Bouton icon={Download} occupe={occupe} onclick={fabriquerCompte}>
          Fabriquer le compte et télécharger le CSV
        </Bouton>
      </div>
    {/if}

    <!-- 4. Le placer -->
    {#if compteFait}
      <div class="card space-y-3 p-4">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
          4 — Une fois le CSV importé dans la console
        </h2>
        <p class="text-xs text-stone-500 dark:text-stone-400">
          Ces gestes touchent un compte qui doit exister : fais-les après
          l'import, pas avant.
        </p>

        {#if typePersonne === "eleve" && proposition.groupe_google}
          <div>
            <Bouton icon={Users} occupe={occupe} onclick={rejoindreGroupe}>
              Ajouter à {proposition.groupe_google}
            </Bouton>
            <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
              Un groupe de classe est une liste de diffusion : y entrer, c'est
              apparaître aux yeux des autres. Rien ne le fait d'office.
            </p>
          </div>
        {/if}

        {#if typePersonne === "adulte"}
          <div>
            <Bouton icon={Laptop} occupe={occupe} onclick={ajouterAuxChromebooks}>
              Inscrire au tableau des Chromebooks
            </Bouton>
            <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
              L'écran Chromebooks lit le tableau des enseignants, importé une
              fois l'an. Sans cette inscription, la personne n'y apparaît pas
              et aucune machine ne peut lui être attribuée.
            </p>
          </div>
        {/if}

        {#if proposition.badge}
          <p class="rounded-lg border border-stone-200 bg-stone-50 p-2 text-xs text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-400">
            Reste KoXo, qui n'a pas d'API : crée le compte
            <strong class="font-mono">{proposition.login_propose}</strong>
            avec l'ID unique <strong class="font-mono">{proposition.badge}</strong
            >{#if proposition.classe} dans le groupe secondaire
              <strong class="font-mono">{proposition.classe}</strong>{/if}, et
            donne-lui le mot de passe du coffre.
          </p>
        {/if}

        <button class="text-xs text-stone-500 hover:text-stone-800 dark:hover:text-stone-200"
                onclick={recommencer}>
          Enregistrer une autre arrivée
        </button>
      </div>
    {/if}
  {/if}
</section>
