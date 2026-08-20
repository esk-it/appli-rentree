<script>
  import { onMount } from "svelte";
  import LogOut from "@lucide/svelte/icons/log-out";
  import ShieldCheck from "@lucide/svelte/icons/shield-check";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Check from "@lucide/svelte/icons/check";
  import Download from "@lucide/svelte/icons/download";
  import Printer from "@lucide/svelte/icons/printer";
  import HelpCircle from "@lucide/svelte/icons/help-circle";
  import Eraser from "@lucide/svelte/icons/eraser";
  import Search from "@lucide/svelte/icons/search";
  import Users from "@lucide/svelte/icons/users";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import Modale from "$lib/components/Modale.svelte";
  import {
    enregistrerFichierBase64,
    googleApi,
    sites,
    sortants as apiSortants,
  } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let liste = $state(/** @type {any} */ (null));
  let listeSites = $state(/** @type {any[]} */ ([]));
  let statutApi = $state(/** @type {any} */ (null));

  let filtreSite = $state("");
  let filtreVue = $state("");
  let chargement = $state(true);
  let erreur = $state("");
  let verification = $state(false);
  let job = $state(/** @type {any} */ (null));
  let sondage = /** @type {any} */ (null);

  let apiUtilisable = $derived(
    statutApi?.bibliotheques_disponibles && statutApi?.configuration_complete,
  );

  // --- Vidange d'une branche d'OU -----------------------------------------
  // Une arborescence d'année garde la promotion qui l'a occupée. Tant que
  // personne ne la vide, ses comptes restent actifs — et l'arbre ne peut pas
  // être recyclé pour la rentrée suivante.
  let ouAVider = $state("");
  // La destination est nommée, pas calculée : l'établissement range ses
  // sortants dans des OU qui existent déjà et qu'il a datées lui-même.
  let ouArchivage = $state("");
  // Un compte de sortie reste consultable. Couper l'accès est une décision
  // à part, qui ne doit jamais être le comportement par défaut.
  let suspendreAussi = $state(false);

  // La liste des personnes à prévenir se lit dans Google, pas ici : la
  // plupart sont parties avant les exports chargés, le référentiel ne les
  // connaît pas. L'OU, elle, sait exactement qui elle contient.
  let occupants = $state(/** @type {any} */ (null));

  async function listerOccupants() {
    const cible = (ouArchivage.trim() || planVidange?.ou_archivage || "").trim();
    if (!cible) {
      notify.info("Renseigne d'abord la destination à inspecter.");
      return;
    }
    vidangeEnCours = true;
    try {
      occupants = await googleApi.occupantsSortie({ ou: cible });
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      vidangeEnCours = false;
    }
  }

  function exporterOccupants() {
    if (!occupants?.occupants?.length) return;
    const entetes = ["Nom", "Prénom", "Adresse mail", "OU", "Prévenance", "Suppression"];
    const lignes = occupants.occupants.map((o) => [
      o.nom, o.prenom, o.email, o.ou,
      formaterIso(occupants.date_prevenance),
      formaterIso(occupants.date_suppression),
    ]);
    const csv = [entetes, ...lignes]
      .map((l) => l.map((c) => (String(c).includes(";") ? `"${c}"` : c)).join(";"))
      .join("\r\n");
    const b64 = btoa(String.fromCharCode(...new TextEncoder().encode("﻿" + csv)));
    enregistrerFichierBase64("Destinataires_prevenance.csv", b64, "text/csv").then(
      ({ chemin, annule }) => {
        if (!annule) {
          notify.succes(`${lignes.length} destinataire(s) — ${chemin ?? "Téléchargements"}`,
            { duree: 8000 });
        }
      },
    );
  }
  let planVidange = $state(/** @type {any} */ (null));
  let vidangeEnCours = $state(false);
  let confirmationVidange = $state(false);

  async function previsualiserVidange() {
    if (!ouAVider.trim()) return;
    vidangeEnCours = true;
    planVidange = null;
    try {
      planVidange = await googleApi.planVidange({
        ou: ouAVider.trim(),
        ouArchivage: ouArchivage.trim() || null,
        suspendre: suspendreAussi,
      });
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      vidangeEnCours = false;
    }
  }

  async function appliquerVidange() {
    vidangeEnCours = true;
    try {
      job = await googleApi.lancerVidange({
        ou: ouAVider.trim(),
        ouArchivage: ouArchivage.trim() || null,
        suspendre: suspendreAussi,
      });
      confirmationVidange = false;
      planVidange = null;
      demarrerSondage();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      vidangeEnCours = false;
    }
  }

  function formaterIso(iso) {
    return iso ? iso.split("-").reverse().join("/") : "\u2014";
  }

  let affiches = $derived.by(() => {
    if (!liste) return [];
    if (filtreVue === "echus") return liste.sortants.filter((s) => s.echeance_depassee);
    if (filtreVue === "ecarts")
      return liste.sortants.filter((s) => ["ecart", "introuvable"].includes(s.verification));
    return liste.sortants;
  });

  let optionsVue = $derived([
    { id: "", label: "Tous", badge: liste?.nb_total ?? 0 },
    { id: "echus", label: "Purge due", badge: liste?.nb_echeance_depassee ?? 0 },
    { id: "ecarts", label: "Écarts", badge: liste?.nb_ecarts ?? 0 },
  ]);

  onMount(async () => {
    try {
      listeSites = await sites.lister();
      try {
        statutApi = await googleApi.statut();
      } catch {
        statutApi = null;
      }
    } catch (e) {
      erreur = String(e);
    }
    await rafraichir();
  });

  async function rafraichir() {
    chargement = true;
    erreur = "";
    try {
      liste = await apiSortants.lister({ siteId: filtreSite || null });
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
      liste = null;
    } finally {
      chargement = false;
    }
  }

  async function verifier() {
    verification = true;
    try {
      const r = await apiSortants.verifier({ siteId: filtreSite || null });
      job = await googleApi.suivreJob(r.job_id);
      demarrerSondage();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      verification = false;
    }
  }

  function demarrerSondage() {
    arreterSondage();
    sondage = setInterval(async () => {
      if (!job) return arreterSondage();
      try {
        job = await googleApi.suivreJob(job.id);
        if (job.est_termine) {
          arreterSondage();
          await rafraichir();
          notify.info(
            `${job.nb_reussies} conforme(s), ${job.nb_echecs} écart(s) sur ${job.total}`,
            { duree: 8000 },
          );
        }
      } catch (e) {
        arreterSondage();
        notify.erreur(String(e).replace(/^Error:\s*/, ""));
      }
    }, 700);
  }

  function arreterSondage() {
    if (sondage) clearInterval(sondage);
    sondage = null;
  }

  $effect(() => () => arreterSondage());

  function exporter() {
    if (!affiches.length) return;
    const entetes = [
      "Clé pivot", "Nom", "Prénom", "Dernière classe", "Site", "Adresse mail",
      "État", "Suppression prévue", "Vérification", "OU réelle", "Détail",
    ];
    const lignes = affiches.map((s) => [
      s.cle_pivot, s.nom, s.prenom, s.derniere_classe ?? "", s.site ?? "",
      s.email ?? "", s.etat,
      s.date_prevue_purge ? s.date_prevue_purge.split("-").reverse().join("/") : "",
      libelleVerification(s.verification), s.ou_reelle ?? "", s.detail_verification ?? "",
    ]);
    const csv = [entetes, ...lignes]
      .map((l) => l.map((c) => (String(c).includes(";") ? `"${c}"` : c)).join(";"))
      .join("\r\n");
    // BOM UTF-8 : sans lui Excel FR massacre les accents
    const b64 = btoa(
      String.fromCharCode(...new TextEncoder().encode("﻿" + csv)),
    );
    enregistrerFichierBase64("Sortants.csv", b64, "text/csv").then(({ chemin, annule }) => {
      if (!annule) {
        notify.succes(
          `${lignes.length} ligne(s) — ${chemin ?? "dans ton dossier Téléchargements"}`,
          { duree: 8000 },
        );
      }
    });
  }

  function libelleVerification(v) {
    return { conforme: "Conforme", ecart: "Écart", introuvable: "Absent de Google" }[v]
      ?? "Non vérifié";
  }

  function formaterDate(iso) {
    return iso ? iso.split("-").reverse().join("/") : "—";
  }
</script>

<section class="space-y-4">
  <div class="sans-impression">
    <EnTetePage
      icon={LogOut}
      titre="Sortants"
      description="Les comptes en quarantaine avant suppression : où ils devraient être, et — si l'API est configurée — où ils sont réellement dans Google."
    />
  </div>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  <div class="card p-3 sans-impression">
    <div class="flex flex-wrap items-end gap-3">
      <div>
        <label class="libelle-champ" for="s-site">Site</label>
        <select id="s-site" class="champ w-40" bind:value={filtreSite} onchange={rafraichir}>
          <option value="">Tous</option>
          {#each listeSites as s (s.id)}
            <option value={s.id}>{s.nom}</option>
          {/each}
        </select>
      </div>

      {#if liste && liste.nb_total > 0}
        <div>
          <span class="libelle-champ">Vue</span>
          <Segments bind:valeur={filtreVue} taille="sm" options={optionsVue} />
        </div>
      {/if}

      <div class="ml-auto flex gap-2">
        <Bouton icon={Printer} onclick={() => window.print()}>Imprimer</Bouton>
        <Bouton icon={Download} disabled={!affiches.length} onclick={exporter}>
          Export Excel
        </Bouton>
        {#if apiUtilisable}
          <Bouton
            variante="primary"
            icon={ShieldCheck}
            occupe={verification}
            disabled={!liste || liste.nb_total === 0 || (job && !job.est_termine)}
            onclick={verifier}
          >
            Vérifier dans Google
          </Bouton>
        {/if}
      </div>
    </div>

    <p class="mt-3 text-xs text-stone-500 dark:text-stone-400">
      {#if apiUtilisable}
        La vérification lit l'état réel de chaque compte — son unité
        d'organisation et sa suspension — sans rien modifier. Elle relève les
        écarts ; les corriger reste une action délibérée.
      {:else}
        Le mode API n'est pas configuré : la liste montre ce que le programme
        a mémorisé, sans pouvoir le confronter à Google. Vois l'aide, section
        « Compte de service Google ».
      {/if}
    </p>
  </div>

  {#if apiUtilisable}
    <div class="card p-3 sans-impression">
      <h2 class="titre-section mb-2 flex items-center gap-2">
        <Eraser class="h-4 w-4" />
        Vider une arborescence d'année
      </h2>
      <p class="mb-3 text-xs text-stone-600 dark:text-stone-400">
        Une branche d'année conserve la promotion qui l'a occupée, et l'arbre ne
        peut pas être recyclé tant qu'elle s'y trouve. Les comptes sont
        <strong>déplacés, pas suspendus</strong> : leur titulaire garde sa
        messagerie le temps qu'on l'ait prévenu. L'échéance de suppression court
        depuis le <strong>départ réel</strong>, déduit du nom de la branche —
        pas depuis aujourd'hui.
      </p>

      <div class="flex flex-wrap items-end gap-3">
        <div>
          <label class="libelle-champ" for="ou-vider">Branche à vider</label>
          <input
            id="ou-vider"
            class="champ w-72 font-mono"
            placeholder="/3. NDK/NDK2025"
            bind:value={ouAVider}
            onkeydown={(e) => e.key === "Enter" && previsualiserVidange()}
          />
        </div>
        <div>
          <label class="libelle-champ" for="ou-archivage">Destination</label>
          <input
            id="ou-archivage"
            class="champ w-80 font-mono"
            placeholder="déduite du site si vide"
            bind:value={ouArchivage}
            onkeydown={(e) => e.key === "Enter" && previsualiserVidange()}
          />
        </div>
        <Bouton icon={Search} occupe={vidangeEnCours} onclick={previsualiserVidange}>
          Prévisualiser
        </Bouton>
        <label class="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" bind:checked={suspendreAussi} class="rounded" />
          Suspendre aussi
        </label>
        <Bouton icon={Users} occupe={vidangeEnCours} onclick={listerOccupants}>
          Qui est dans la destination ?
        </Bouton>
        {#if planVidange && planVidange.nb_a_archiver > 0}
          <Bouton
            variante="danger"
            icon={Eraser}
            disabled={job && !job.est_termine}
            onclick={() => (confirmationVidange = true)}
          >
            Déplacer {planVidange.nb_a_archiver} compte(s)
          </Bouton>
        {/if}
      </div>

      {#if occupants}
        <div class="mt-3 rounded-lg border border-stone-200 p-3 text-sm dark:border-stone-700">
          <div class="flex flex-wrap items-center gap-3">
            <span>
              <strong class="tabular-nums">{occupants.nb}</strong> compte(s) dans
              <span class="font-mono text-xs">{occupants.ou}</span>
            </span>
            {#if occupants.nb_suspendus > 0}
              <span class="text-amber-700 dark:text-amber-400">
                {occupants.nb_suspendus} suspendu(s)
              </span>
            {/if}
            <Bouton
              taille="sm"
              icon={Download}
              classe="ml-auto"
              disabled={!occupants.nb}
              onclick={exporterOccupants}
            >
              Liste des destinataires
            </Bouton>
            <Bouton taille="sm" onclick={() => (occupants = null)}>Fermer</Bouton>
          </div>

          {#if occupants.date_prevenance}
            <p class="mt-2 text-xs text-stone-600 dark:text-stone-400">
              Lettre à envoyer le
              <strong>{formaterIso(occupants.date_prevenance)}</strong>, annonçant
              quatre mois : suppression le
              <strong>{formaterIso(occupants.date_suppression)}</strong>.
            </p>
          {:else}
            <p class="mt-2 text-xs text-amber-700 dark:text-amber-400">
              Le nom de cette OU ne porte pas de date : aucune échéance ne peut
              en être déduite.
            </p>
          {/if}

          <div class="mt-3 max-h-64 overflow-auto">
            <table class="tableau w-full text-xs">
              <thead>
                <tr>
                  <th class="text-left">Nom</th>
                  <th class="text-left">Adresse</th>
                  <th class="text-left">Dernière connexion</th>
                </tr>
              </thead>
              <tbody>
                {#each occupants.occupants.slice(0, 300) as o (o.email)}
                  <tr class:ligne-douteuse={o.suspendu}>
                    <td class="whitespace-nowrap">{o.prenom} {o.nom}</td>
                    <td class="whitespace-nowrap font-mono">{o.email}</td>
                    <td class="whitespace-nowrap text-stone-500 dark:text-stone-400">
                      {o.derniere_connexion ? o.derniere_connexion.slice(0, 10).split("-").reverse().join("/") : "—"}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}

      {#if planVidange}
        <div class="mt-3 rounded-lg border border-stone-200 p-3 text-sm dark:border-stone-700">
          <div class="flex flex-wrap gap-x-6 gap-y-1">
            <span><strong>{planVidange.nb_trouves}</strong> compte(s) trouvés</span>
            <span class="text-red-700 dark:text-red-400">
              <strong>{planVidange.nb_a_archiver}</strong> à archiver
            </span>
            {#if planVidange.nb_deja_suspendus > 0}
              <span class="text-stone-500">{planVidange.nb_deja_suspendus} déjà suspendus</span>
            {/if}
            {#if planVidange.nb_epargnes > 0}
              <span class="text-emerald-700 dark:text-emerald-400">
                {planVidange.nb_epargnes} épargnés
              </span>
            {/if}
          </div>
          <p class="mt-2 text-xs text-stone-600 dark:text-stone-400">
            {#if planVidange.date_prevenance}
              Lettre de prévenance le
              <strong>{formaterIso(planVidange.date_prevenance)}</strong>, puis
              quatre mois : suppression le
              <strong>{formaterIso(planVidange.date_echeance)}</strong>.
            {:else}
              Départ constaté au <strong>{formaterIso(planVidange.date_depart)}</strong>,
              suppression prévue le <strong>{formaterIso(planVidange.date_echeance)}</strong>.
            {/if}
            Destination : <span class="font-mono">{planVidange.ou_archivage}</span>
          </p>

          {#each planVidange.avertissements as a}
            <p class="mt-2 rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">
              {a}
            </p>
          {/each}

          {#if planVidange.epargnes.length}
            <p class="mt-2 text-xs font-medium">Laissés en place :</p>
            <ul class="text-xs text-stone-600 dark:text-stone-400">
              {#each planVidange.epargnes.slice(0, 10) as e (e.email)}
                <li>{e.prenom ?? ""} {e.nom ?? ""} — <span class="font-mono">{e.email}</span></li>
              {/each}
            </ul>
          {/if}

          <div class="mt-3 max-h-64 overflow-auto">
            <table class="tableau w-full text-xs">
              <thead>
                <tr>
                  <th class="text-left">Nom</th>
                  <th class="text-left">Adresse</th>
                  <th class="text-left">OU actuelle</th>
                  <th class="text-left">Purge</th>
                </tr>
              </thead>
              <tbody>
                {#each planVidange.mouvements.slice(0, 200) as m (m.email)}
                  <tr>
                    <td class="whitespace-nowrap">{m.prenom} {m.nom}</td>
                    <td class="whitespace-nowrap font-mono">{m.email}</td>
                    <td class="whitespace-nowrap font-mono text-stone-500 dark:text-stone-400">
                      {m.ou_actuelle}
                    </td>
                    <td class="whitespace-nowrap">
                      {#if m.date_echeance && m.date_echeance !== planVidange.date_echeance}
                        <span class="text-amber-700 dark:text-amber-400">
                          {formaterIso(m.date_echeance)}
                        </span>
                      {:else}
                        <span class="text-stone-400">—</span>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}
    </div>
  {/if}

  <div class="impression-seule mb-3">
    <h1 class="text-lg font-bold">Comptes sortants</h1>
    <p class="text-xs">
      {liste?.nb_total ?? 0} compte(s) · {liste?.nb_echeance_depassee ?? 0} dont la
      suppression est due
    </p>
  </div>

  {#if job}
    <div class="card overflow-hidden sans-impression">
      <div class="flex items-center gap-3 px-3 py-2 text-sm">
        <span class="font-semibold">{job.libelle}</span>
        <span class="tabular-nums text-stone-500 dark:text-stone-400">
          {job.nb_traitees} / {job.total}
        </span>
        <span class="text-emerald-700 dark:text-emerald-400">{job.nb_reussies} conforme(s)</span>
        {#if job.nb_echecs > 0}
          <span class="font-medium text-amber-700 dark:text-amber-400">
            {job.nb_echecs} écart(s)
          </span>
        {/if}
        {#if job.est_termine}
          <Bouton taille="sm" classe="ml-auto" onclick={() => (job = null)}>Fermer</Bouton>
        {/if}
      </div>
      <div class="h-1.5 w-full bg-stone-200 dark:bg-stone-700">
        <div
          class="h-full bg-emerald-600 transition-all duration-300"
          style="width: {Math.round(job.progression * 100)}%"
        ></div>
      </div>
    </div>
  {/if}

  {#if chargement}
    <div class="card p-4">
      <Squelette variante="ligne-tableau" nb={6} colonnes={6} />
    </div>
  {:else if !liste || liste.nb_total === 0}
    <div class="card p-4">
      <EtatVide
        icon={LogOut}
        titre="Aucun compte en sortie enregistré"
        message="Ce tableau ne liste que les comptes déjà mis en quarantaine. Deux chemins y mènent, et ils ne se ressemblent pas."
      />
      <!--
        Un état vide qui ne dit pas quoi faire laisse croire à une panne.
        Ici le piège est autre : la vidange ci-dessus alimente ce tableau,
        et l'utilisateur qui vient de s'en servir ne doit pas lire des
        prérequis qui ne le concernent pas.
      -->
      <div class="mx-auto mt-4 grid max-w-3xl gap-3 text-sm sm:grid-cols-2">
        <div class="rounded-lg border border-stone-200 p-3 text-left dark:border-stone-700">
          <p class="font-medium text-stone-800 dark:text-stone-200">
            Par l'arborescence — le bloc ci-dessus
          </p>
          <p class="mt-1 text-stone-600 dark:text-stone-400">
            Les comptes logés dans l'arbre d'une année révolue, quelle que soit
            la raison de leur présence. C'est le chemin habituel à la rentrée :
            prévisualise <span class="font-mono text-xs">/3. NDK/NDK2025</span>,
            puis archive. Ce tableau se remplit ensuite.
          </p>
        </div>
        <div class="rounded-lg border border-stone-200 p-3 text-left dark:border-stone-700">
          <p class="font-medium text-stone-800 dark:text-stone-200">
            Par le référentiel — écran Suivi
          </p>
          <p class="mt-1 text-stone-600 dark:text-stone-400">
            Les élèves présents l'an dernier et absents cette année. Suppose un
            export Charlemagne <strong>incluant les sortants</strong>, une
            réconciliation qui en trouve, puis le bouton
            <strong>Traiter les sortants</strong> dans l'écran Suivi.
          </p>
          <p class="mt-2 text-xs text-stone-500 dark:text-stone-400">
            Ce chemin ne donne rien quand l'année précédente est entièrement
            contenue dans la nouvelle — aucun départ ne s'y lit.
          </p>
        </div>
      </div>
    </div>
  {:else}
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-3 sans-impression">
      <div class="card p-3">
        <p class="text-xs uppercase tracking-wide text-stone-500 dark:text-stone-400">En sortie</p>
        <p class="mt-1 text-2xl font-semibold tabular-nums">{liste.nb_total}</p>
      </div>
      <div class="card p-3 {liste.nb_echeance_depassee ? 'ring-1 ring-amber-300 dark:ring-amber-700' : ''}">
        <p class="text-xs uppercase tracking-wide text-stone-500 dark:text-stone-400">
          Suppression due
        </p>
        <p class="mt-1 text-2xl font-semibold tabular-nums {liste.nb_echeance_depassee ? 'text-amber-700 dark:text-amber-400' : ''}">
          {liste.nb_echeance_depassee}
        </p>
      </div>
      <div class="card p-3 {liste.nb_ecarts ? 'ring-1 ring-red-300 dark:ring-red-800' : ''}">
        <p class="text-xs uppercase tracking-wide text-stone-500 dark:text-stone-400">Écarts</p>
        <p class="mt-1 text-2xl font-semibold tabular-nums {liste.nb_ecarts ? 'text-red-700 dark:text-red-400' : ''}">
          {liste.nb_ecarts}
        </p>
      </div>
    </div>

    <div class="card overflow-hidden">
      <div class="max-h-[640px] overflow-auto">
        <table class="tableau w-full text-sm">
          <thead class="sticky top-0 z-10">
            <tr>
              <th class="px-3 py-2 text-left">Nom</th>
              <th class="px-3 py-2 text-left">Prénom</th>
              <th class="px-3 py-2 text-left">Dernière classe</th>
              <th class="px-3 py-2 text-left">Adresse mail</th>
              <th class="px-3 py-2 text-left">Suppression prévue</th>
              <th class="px-3 py-2 text-left">Dans Google</th>
            </tr>
          </thead>
          <tbody>
            {#each affiches as s (s.personne_id)}
              <tr class:ligne-douteuse={s.verification === "ecart" || s.verification === "introuvable"}>
                <td class="whitespace-nowrap px-3 py-1.5 font-medium">{s.nom}</td>
                <td class="whitespace-nowrap px-3 py-1.5">{s.prenom}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-stone-600 dark:text-stone-400">
                  {s.derniere_classe ?? "—"}
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 font-mono text-xs">{s.email ?? "—"}</td>
                <td class="whitespace-nowrap px-3 py-1.5 tabular-nums {s.echeance_depassee ? 'font-medium text-amber-700 dark:text-amber-400' : ''}">
                  {formaterDate(s.date_prevue_purge)}
                </td>
                <td class="px-3 py-1.5 text-xs">
                  {#if s.verification === "conforme"}
                    <span class="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400">
                      <Check class="h-3 w-3 shrink-0" /> archivé et suspendu
                    </span>
                  {:else if s.verification === "non_verifie"}
                    <span class="inline-flex items-center gap-1 text-stone-400 dark:text-stone-500">
                      <HelpCircle class="h-3 w-3 shrink-0" /> non vérifié
                    </span>
                  {:else}
                    <span class="inline-flex items-center gap-1 text-red-700 dark:text-red-400">
                      <TriangleAlert class="h-3 w-3 shrink-0" />
                      {s.detail_verification}
                    </span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <p class="impression-seule mt-4 text-xs">
      Vérifié par ……………………………………  le ……… / ……… / ………
    </p>
  {/if}
</section>

{#if confirmationVidange && planVidange}
  <Modale
    titre="Déplacer {planVidange.nb_a_archiver} compte(s) ?"
    largeur="lg"
    onFermer={() => (confirmationVidange = false)}
  >
    <div class="space-y-3 text-sm text-stone-600 dark:text-stone-300">
      <p>
        Ces comptes vont être déplacés vers
        <span class="font-mono">{planVidange.ou_archivage}</span>.
        {#if suspendreAussi}
          Ils seront <strong>aussi suspendus</strong> : leurs titulaires ne
          pourront plus se connecter.
        {:else}
          Ils <strong>restent actifs</strong> — sortir de l'arbre des classes
          suffit à les mettre en quarantaine.
        {/if}
      </p>
      <p>
        Rien n'est supprimé : les données restent en place jusqu'au
        <strong>{formaterIso(planVidange.date_echeance)}</strong>, et la
        suppression définitive reste un geste manuel dans la console Google.
      </p>
      {#if planVidange.nb_epargnes > 0}
        <p class="rounded bg-emerald-50 px-2 py-1.5 text-xs text-emerald-900 dark:bg-emerald-900/20 dark:text-emerald-200">
          {planVidange.nb_epargnes} compte(s) ne seront pas touchés : leur
          titulaire est encore inscrit cette année.
        </p>
      {/if}
    </div>

    {#snippet actions()}
      <Bouton onclick={() => (confirmationVidange = false)}>Annuler</Bouton>
      <Bouton variante="danger" occupe={vidangeEnCours} onclick={appliquerVidange}>
        {suspendreAussi ? "Suspendre et déplacer" : "Déplacer"}
      </Bouton>
    {/snippet}
  </Modale>
{/if}
