<script>
  import { onMount } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import Download from "@lucide/svelte/icons/download";
  import FileDown from "@lucide/svelte/icons/file-down";
  import Upload from "@lucide/svelte/icons/upload";
  import Info from "@lucide/svelte/icons/info";
  import KeyRound from "@lucide/svelte/icons/key-round";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import Cloud from "@lucide/svelte/icons/cloud";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Bouton from "$lib/components/Bouton.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import {
    annees,
    exportsCible,
    googleApi,
    coffreApi,
    sites as sitesApi,
    enregistrerFichierBase64,
  } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let listeSites = $state([]);
  let listeAnnees = $state([]);

  let cible = $state(
    /** @type {"koxo"|"google"|"groupes"|"pmb"|"charlemagne"|"listes"|"jpm"|"cardstudio"} */ ("koxo"),
  );

  /**
   * Les deux cibles qui partent d'un fichier de Charlemagne au lieu d'en
   * produire un : la répartition PMB et le retour des adresses. Elles
   * n'ont ni site ni catégorie à choisir — tout est dans le fichier.
   *
   * « Listes & étiquettes » part aussi d'un fichier, mais garde les
   * sélecteurs : l'export KoXo ne dit ni de quel site il parle ni contre
   * quelle année comparer les entrants.
   */
  let partDunFichier = $derived(cible === "pmb" || cible === "charlemagne");

  // Groupes Google : quelles familles inclure
  let inclureEleves = $state(true);
  let inclureProfs = $state(true);
  let siteId = $state(/** @type {null | number} */ (null));
  let typePersonne = $state(/** @type {"eleve"|"adulte"} */ ("eleve"));
  let categorie = $state(/** @type {"tous"|"nouveaux"|"anciens"} */ ("tous"));
  /**
   * La base KoXo qui recevra le fichier, quand ce n'est pas celle du site.
   *
   * Les professeurs vivent dans les deux serveurs, et chacun nomme ses
   * groupes secondaires à sa façon — `DIRECTEUR` ici, `PHYSIQUE-CHIMIE`
   * là. Le référentiel ne rattache un adulte qu'à un seul site : sans ce
   * choix, le même fichier servi au second serveur y déplaçait
   * vingt-quatre comptes qui n'avaient aucune raison de bouger.
   */
  let baseKoxo = $state(/** @type {string | null} */ (null));

  /**
   * Le site choisi a-t-il un serveur KoXo ?
   *
   * S'il n'en a pas, personne ne fabrique les mots de passe de ses élèves
   * et personne ne les imprime. Le programme doit s'en charger — et c'est
   * un autre geste que l'export ordinaire, puisqu'il écrit au coffre.
   */
  let siteChoisi = $derived(listeSites.find((s) => s.id === siteId) ?? null);
  let siteSansKoxo = $derived(
    Boolean(siteChoisi) && !(siteChoisi.base_koxo ?? "").trim(),
  );
  let generationEnCours = $state(false);

  /**
   * Les comptes que la synchronisation désactiverait.
   *
   * KoXo n'annonce qu'un nombre au moment de lancer l'opération —
   * « Désactiver 7 » — et il faut exporter la base puis comparer les
   * fichiers à la main pour savoir lesquels. Sur l'instance réelle, la
   * liste contenait un remplaçant attendu pour la rentrée.
   */
  let menaces = $state(/** @type {null | any} */ (null));
  let menacesEnCours = $state(false);
  let menacesErreur = $state("");

  async function chargerMenaces() {
    if (!siteId || !anneeCibleId || cible !== "koxo" || categorie !== "tous") {
      menaces = null;
      return;
    }
    menacesEnCours = true;
    menacesErreur = "";
    try {
      menaces = await exportsCible.desactivationsKoxo({
        siteId,
        typePersonne,
        anneeCibleId,
        baseKoxo: typePersonne === "adulte" ? baseKoxo : null,
      });
    } catch (e) {
      menaces = null;
      menacesErreur = e?.message ?? String(e);
    } finally {
      menacesEnCours = false;
    }
  }

  async function basculerConservation(compte) {
    if (!menaces) return;
    try {
      await exportsCible.conserverKoxo({
        badges: [compte.badge],
        base: menaces.base,
        conserver: !compte.conserver,
      });
      await chargerMenaces();
      notify.succes(
        compte.conserver
          ? `${compte.prenom} ${compte.nom} sera désactivé`
          : `${compte.prenom} ${compte.nom} sera reconduit dans l'export`,
      );
    } catch (e) {
      notify.erreur(e?.message ?? String(e));
    }
  }

  // La liste dépend de tout ce qui définit le fichier : la recharger à
  // chaque changement évite de décider sur un état périmé.
  $effect(() => {
    void [cible, siteId, typePersonne, categorie, anneeCibleId, baseKoxo];
    chargerMenaces();
  });

  /**
   * Groupe secondaire imposé aux sortants KoXo.
   *
   * Sans lui, la ligne d'un sortant porte sa dernière classe — le seul
   * groupe que le référentiel lui connaisse. Synchronisée telle quelle,
   * elle le remettrait dans cette classe, au milieu de la promotion
   * suivante. Les rassembler dans un groupe dédié est ce que recommande la
   * documentation KoXo : les comptes restent, identifiables, et la
   * suppression devient un geste distinct et daté.
   */
  let groupeSortants = $state("");
  // Phase visée par le plan API — même découpage que l'onglet Bascule des OU.
  let phaseApi = $state(/** @type {"pre_rentree"|"definitive"} */ ("pre_rentree"));
  let anneeCibleId = $state(/** @type {null | number} */ (null));
  let anneeSourceId = $state(/** @type {null | number} */ (null));

  let dernierRapport = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  // Boucle KoXo → Google (Lot 8b) — MDP transportés en mémoire uniquement
  let fichierKoxoEnrichi = $state(/** @type {File|null} */ (null));

  // Enregistrement du cycle de vie : inscrit les personnes du fichier en
  // CompteCible(etat="prevu") — c'est ce qui alimente l'écran Suivi.
  let enregistrerPrevus = $state(true);

  // Mode API Google (optionnel — le mode fichier reste le mode nominal)
  let statutApi = $state(/** @type {null | any} */ (null));
  let planApi = $state(/** @type {null | any} */ (null));
  let apiEnCours = $state(false);

  async function chargerStatutApi() {
    try {
      statutApi = await googleApi.statut();
    } catch (e) {
      statutApi = null;
    }
  }

  async function csvKoxoEnBase64() {
    if (!fichierKoxoEnrichi) return null;
    const buffer = await fichierKoxoEnrichi.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, /** @type {any} */ (bytes.subarray(i, i + chunk)));
    }
    return btoa(binary);
  }

  let testEnCours = $state(false);

  async function testerConnexion() {
    testEnCours = true;
    try {
      const r = await googleApi.testerConnexion();
      notify.succes(
        `Connexion Google établie — ${r.nb_utilisateurs_visibles} utilisateur(s) lu(s). ` +
          "Aucune modification n'a été faite.",
        { duree: 8000 },
      );
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      testEnCours = false;
    }
  }

  /**
   * Fabrique les comptes d'un site sans KoXo, et les étiquettes qui vont
   * avec.
   *
   * Deux fichiers, demandés l'un après l'autre : le CSV pour la console,
   * les étiquettes pour la classe. Les mots de passe sont rangés au coffre
   * dans le même geste — sans quoi ils seraient perdus.
   */
  async function genererComptesSansKoxo() {
    if (!siteId || !anneeCibleId) return;
    generationEnCours = true;
    try {
      const r = await coffreApi.comptesSansKoxo({
        siteId,
        anneeCibleId,
        anneeSourceId: anneeSourceId ?? null,
        categorie: anneeSourceId ? "nouveaux" : "tous",
      });
      dernierRapport = { ...r, cible: "google (comptes fabriqués)" };

      const csv = await enregistrerFichierBase64(
        r.nom_fichier_csv, r.csv_base64, "text/csv",
      );
      if (csv.annule) return;
      const fiches = await enregistrerFichierBase64(
        r.nom_fichier_fiches, r.etiquettes_base64, "text/html",
      );

      notify.succes(
        `${r.nb_lignes} compte(s) — ${r.nb_generes} mot(s) de passe fabriqué(s), `
          + `${r.nb_deja_au_coffre} repris du coffre`,
        { duree: 9000 },
      );
      if (!fiches.annule) {
        notify.info(
          "Imprime les étiquettes avant d'importer : c'est le seul endroit "
            + "où l'élève lira son mot de passe.",
          { duree: 12000 },
        );
      }
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
      notify.erreur(erreur, { duree: 12000 });
    } finally {
      generationEnCours = false;
    }
  }

  async function calculerPlanApi() {
    if (!siteId || !anneeCibleId || !anneeSourceId) {
      notify.avertissement("Site et deux années requis pour le plan API");
      return;
    }
    apiEnCours = true;
    try {
      planApi = await googleApi.plan({
        siteId, typePersonne,
        anneeCibleId, anneeSourceId,
        csvKoxoBase64: await csvKoxoEnBase64(),
        phase: phaseApi,
      });
      if (!planApi.est_executable) {
        notify.avertissement(
          `${planApi.nb_bloques} élève(s) sans OU calculable — complète la Table de correspondance`,
        );
      } else {
        notify.info(`${planApi.nb_total} opération(s) planifiée(s) — rien n'a été envoyé`);
      }
    } catch (e) {
      notify.erreur(String(e));
    } finally {
      apiEnCours = false;
    }
  }

  async function executerPlanApi() {
    if (!planApi) return;
    apiEnCours = true;
    try {
      const r = await googleApi.executer({
        siteId, typePersonne,
        anneeCibleId, anneeSourceId,
        csvKoxoBase64: await csvKoxoEnBase64(),
        phase: phaseApi,
      });
      if (r.tout_reussi) {
        notify.succes(`${r.nb_reussies} opération(s) appliquée(s) sur Google`);
      } else {
        notify.erreur(`${r.nb_echecs} échec(s) sur ${r.nb_reussies + r.nb_echecs}`);
      }
      planApi = null;
    } catch (e) {
      notify.erreur(String(e));
    } finally {
      apiEnCours = false;
    }
  }

  onMount(async () => {
    try {
      listeSites = await sitesApi.lister();
      listeAnnees = await annees.lister();
      // Par libellé, pas par date de création : « 2025-2026 » a été créée
      // après « 2026-2027 », et l'ordre de l'API mettait donc l'année
      // révolue en cible et l'année en cours en source. La liste des
      // entrants comparait alors 2026-2027 à elle-même, et ne rendait
      // aucun élève sans rien signaler.
      const parLibelle = [...listeAnnees].sort((a, b) =>
        String(b.libelle).localeCompare(String(a.libelle)),
      );
      if (parLibelle.length >= 1) anneeCibleId = parLibelle[0].id;
      if (parLibelle.length >= 2) anneeSourceId = parLibelle[1].id;
    } catch (e) {
      erreur = String(e);
    }
    try {
      modeles = await exportsCible.modelesEtiquettes();
    } catch {
      // Le catalogue n'est pas vital : sans lui, le modèle par défaut
      // s'applique et l'écran reste utilisable.
      modeles = [];
    }
    await chargerStatutApi();
  });

  /** L'année source est ce qui définit « nouveau » : sans elle, la liste
   *  des entrants et leurs étiquettes n'ont pas de sens. L'onglet des
   *  listes en dépend donc autant que les catégories de KoXo — et ne pas
   *  l'y montrer laissait l'utilisateur devant trois documents vides sans
   *  moyen de comprendre pourquoi. */
  let anneeSourceRequise = $derived(
    categorie === "nouveaux" || categorie === "anciens" || cible === "listes",
  );

  /**
   * PMB : le fichier de Charlemagne, coupé par instance.
   *
   * Le programme ne fabrique pas cet export. PMB veut treize colonnes,
   * dont sept — adresse, complément, code postal, ville, téléphone, année
   * de naissance, sexe — ne sont nulle part dans le référentiel ni dans
   * l'export que le programme ingère. La version qui essayait rendait un
   * fichier de six colonnes que PMB refusait.
   *
   * Ce que le programme apporte, et que Charlemagne ignore : quel code
   * classe appartient à quel établissement. Importé entier dans l'instance
   * du lycée, le fichier y fait entrer les classes du collège — c'est
   * arrivé, et la documentaliste a vu ses effectifs doubler.
   */
  let fichierCharlemagne = $state(/** @type {File|null} */ (null));
  let rapportPmb = $state(/** @type {any} */ (null));

  /**
   * L'année qui nommera les fichiers, montrée avant de lancer.
   *
   * La liste des années arrive triée par date de création, pas par
   * millésime : la plus récemment ingérée n'est pas forcément l'année
   * courante, et le choix par défaut peut donc tomber sur la précédente.
   * Un fichier mal daté envoyé au CDI est long à rattraper — autant que le
   * nom se lise avant le clic.
   */
  let anneeLibelleChoisie = $derived(
    listeAnnees.find((a) => a.id === anneeCibleId)?.libelle ?? "",
  );

  async function repartirPmb() {
    if (!fichierCharlemagne || !anneeCibleId) return;
    chargement = true;
    erreur = "";
    rapportPmb = null;
    try {
      const anneeLibelle =
        listeAnnees.find((a) => a.id === anneeCibleId)?.libelle ?? "";
      rapportPmb = await exportsCible.pmb({ fichier: fichierCharlemagne, anneeLibelle });
      notify.succes(
        `${rapportPmb.nb_reparties} ligne(s) réparties en ` +
          `${rapportPmb.paquets.length} fichier(s) — à enregistrer ci-dessous`,
        { duree: 8000 },
      );
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
      notify.erreur(erreur, { duree: 12000 });
    } finally {
      chargement = false;
    }
  }

  /**
   * Les adresses à renvoyer dans Charlemagne.
   *
   * Charlemagne est la source pour l'état civil et la classe ; il ne l'est
   * pas pour l'adresse, qui se crée ici après son export de rentrée. Sa
   * colonne reste donc vide pour toute la promotion entrante — et c'est
   * elle qu'il réexporte ensuite vers PMB et SoHappy.
   *
   * L'annuaire Google est lu avant que quoi que ce soit soit proposé : la
   * plupart des adresses du référentiel sont **calculées**, et pousser un
   * calcul dans Charlemagne y propagerait l'erreur.
   */
  let rapportAdresses = $state(/** @type {any} */ (null));

  async function confronterAdresses() {
    if (!fichierCharlemagne) return;
    chargement = true;
    erreur = "";
    rapportAdresses = null;
    try {
      const anneeLibelle =
        listeAnnees.find((a) => a.id === anneeCibleId)?.libelle ?? "";
      rapportAdresses = await exportsCible.charlemagneAdresses({
        fichier: fichierCharlemagne, anneeLibelle,
      });
      const n = rapportAdresses.nb_a_importer;
      if (n === 0) {
        notify.succes(
          "Rien à renvoyer : Charlemagne connaît déjà toutes les adresses.",
          { duree: 8000 },
        );
      } else {
        notify.succes(
          `${n} adresse(s) à renvoyer, toutes vérifiées dans Google.`,
          { duree: 8000 },
        );
      }
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
      notify.erreur(erreur, { duree: 12000 });
    } finally {
      chargement = false;
    }
  }

  /**
   * Les trois documents de rentrée d'un site, depuis son export KoXo.
   *
   * Le référentiel ne connaît pas les mots de passe : là où KoXo existe,
   * c'est lui l'autorité, et le programme n'en invente aucun. Les trois
   * documents en ont pourtant besoin — la liste que le professeur principal
   * garde, celle des entrants pour la vie scolaire, les étiquettes que
   * l'élève emporte.
   */
  let fichierListes = $state(/** @type {File|null} */ (null));
  let rapportListes = $state(/** @type {any} */ (null));

  /** Le catalogue des présentations, et celle qu'on a retenue. */
  let modeles = $state(/** @type {any[]} */ ([]));
  let modeleChoisi = $state("filigrane");
  /** Les classes cochées. Vide = tout le site, pas « aucune ». */
  let classesRetenues = $state(new SvelteSet());
  /** Les élèves cochés nommément — le cas du mot de passe perdu. */
  let elevesRetenus = $state(new SvelteSet());
  /** Le site entier, chargé dès qu'on choisit un site : on doit pouvoir
   *  filtrer **avant** de générer, pas après. */
  let elevesDuSite = $state(/** @type {any[]} */ ([]));
  let filtreEleve = $state("");
  let parPage = $state(18);
  /** Les documents à produire. Vide = les quatre. */
  let documentsVoulus = $state(new SvelteSet());

  const DOCUMENTS = [
    { id: "liste_tous", libelle: "Liste de tous les élèves" },
    { id: "liste_nouveaux", libelle: "Liste des entrants" },
    { id: "etiquettes_tous", libelle: "Étiquettes de tous" },
    { id: "etiquettes_nouveaux", libelle: "Étiquettes des entrants" },
  ];

  $effect(() => {
    const s = siteId;
    const a = anneeCibleId;
    if (cible !== "listes" || !s || !a) return;
    exportsCible
      .elevesDuSite({ siteId: s, anneeId: a })
      .then((r) => {
        elevesDuSite = r;
        classesRetenues.clear();
        elevesRetenus.clear();
      })
      .catch(() => (elevesDuSite = []));
  });

  let classesDuSite = $derived([
    ...new Set(elevesDuSite.map((e) => e.classe).filter(Boolean)),
  ].sort());

  let elevesAffiches = $derived.by(() => {
    const q = filtreEleve.trim().toLowerCase();
    const base = classesRetenues.size
      ? elevesDuSite.filter((e) => classesRetenues.has(e.classe))
      : elevesDuSite;
    if (!q) return base;
    return base.filter((e) =>
      `${e.prenom} ${e.nom} ${e.classe}`.toLowerCase().includes(q),
    );
  });

  async function genererListes() {
    if (!fichierListes || !siteId || !anneeCibleId) return;
    chargement = true;
    erreur = "";
    rapportListes = null;
    try {
      rapportListes = await exportsCible.listesKoxo({
        fichierKoxo: fichierListes,
        siteId,
        anneeCibleId,
        anneeSourceId: anneeSourceId ?? null,
        classes: [...classesRetenues],
        personneIds: [...elevesRetenus],
        documents: [...documentsVoulus],
        modele: modeleChoisi,
        parPage,
      });
      notify.succes(
        `${rapportListes.nb_tous} élève(s), dont ${rapportListes.nb_nouveaux} entrants`,
        { duree: 8000 },
      );
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
      notify.erreur(erreur, { duree: 14000 });
    } finally {
      chargement = false;
    }
  }

  /**
   * @param {any} paquet
   * @param {string} [mime] - le type importe pour le classeur et le HTML :
   *   sans lui, Windows ouvrirait un `.xlsx` dans un éditeur de texte.
   */
  async function enregistrerPaquet(paquet, mime = "text/csv") {
    const { chemin, annule } = await enregistrerFichierBase64(
      paquet.nom_fichier, paquet.contenu_base64, mime,
    );
    if (annule) return;
    notify.succes(
      `${paquet.nom_fichier} — ${chemin ?? "dans ton dossier Téléchargements"}`,
    );
  }

  async function generer() {
    if (!siteId || !anneeCibleId) return;
    if (anneeSourceRequise && !anneeSourceId) {
      notify.avertissement("Année source requise pour cette catégorie");
      return;
    }
    chargement = true;
    erreur = "";
    try {
      const params = {
        siteId,
        typePersonne,
        categorie,
        anneeCibleId,
        anneeSourceId: anneeSourceRequise ? anneeSourceId : null,
        enregistrerPrevus,
      };
      if (cible === "koxo" && categorie === "anciens") {
        params.groupeSecondaireForce = groupeSortants.trim() || null;
      }
      if (cible === "koxo" && typePersonne === "adulte") {
        params.baseKoxo = baseKoxo;
      }
      let r;
      if (cible === "koxo") {
        r = await exportsCible.koxo(params);
      } else if (cible === "google") {
        r = fichierKoxoEnrichi
          ? await exportsCible.googleAvecMdp({ fichierKoxo: fichierKoxoEnrichi, ...params })
          : await exportsCible.google(params);
      } else if (cible === "groupes") {
        r = await exportsCible.googleGroupes({
          siteId, anneeId: anneeCibleId, inclureEleves, inclureProfs,
        });
      } else if (cible === "jpm") {
        r = await exportsCible.jpm({
          siteId, anneeCibleId, anneeSourceId, enregistrerPrevus,
        });
      } else if (cible === "cardstudio") {
        r = await exportsCible.cardstudio({
          siteId, categorie, anneeCibleId, anneeSourceId, enregistrerPrevus,
        });
      }
      const labelCible = cible === "google" && fichierKoxoEnrichi ? "google (avec MDP)" : cible;
      dernierRapport = { ...r, cible: labelCible };
      const { chemin, annule } = await enregistrerFichierBase64(
        r.nom_fichier, r.contenu_base64, "text/csv",
      );
      if (annule) return;
      const parts = [];
      if (r.nb_sans_ou > 0) parts.push(`${r.nb_sans_ou} sans OU — classe hors table`);
      if (r.nb_prevus_enregistres > 0) parts.push(`${r.nb_prevus_enregistres} compte(s) suivi(s)`);
      const suffixe = parts.length ? ` (${parts.join(" ; ")})` : "";
      const nb = r.nb_lignes ?? r.nb_total ?? 0;
      notify.succes(
        `${nb} ligne(s) — ${chemin ?? `${r.nom_fichier} dans ton dossier Téléchargements`}${suffixe}`,
        { duree: 8000 },
      );
    } catch (e) {
      erreur = String(e);
      notify.erreur(erreur);
    } finally {
      chargement = false;
    }
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Exports vers les cibles
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Génère les fichiers à importer dans les systèmes tiers. KoXo, PMB, JPM
      et CardStudio n'ont pas d'API : ces exports restent le seul canal. Côté
      Google, le CSV reste disponible, mais l'écran <strong>Conformité
      Google</strong> fait le même travail directement.
    </p>
  </header>

  {#if listeSites.length === 0 || listeAnnees.length === 0}
    <div class="card border-amber-200 bg-amber-50/50 p-4 text-sm dark:border-amber-800 dark:bg-amber-900/20">
      <div class="flex items-start gap-3">
        <AlertTriangle class="mt-0.5 h-5 w-5 text-amber-700 dark:text-amber-400" />
        <div>
          <p class="font-medium text-amber-900 dark:text-amber-200">Données manquantes</p>
          <p class="mt-1 text-stone-700 dark:text-stone-300">
            Il faut au moins un <strong>Site</strong> et une <strong>année scolaire</strong>
            {#if listeAnnees.length === 0}(via un amorçage ou une ingestion){/if} pour
            générer un export.
          </p>
        </div>
      </div>
    </div>
  {/if}

  <div class="card p-5 space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold">Génération d'un CSV</h2>
      <Segments
        bind:valeur={cible}
        taille="sm"
        options={[
          { id: "koxo", label: "KoXo" },
          { id: "google", label: "Google" },
          { id: "groupes", label: "Groupes" },
          { id: "pmb", label: "PMB" },
          { id: "charlemagne", label: "Charlemagne" },
          { id: "listes", label: "Listes & étiquettes" },
          { id: "jpm", label: "JPM" },
          { id: "cardstudio", label: "CardStudio" },
        ]}
      />
    </div>

    {#if !partDunFichier}
    <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Site cible
        </span>
        <select
          bind:value={siteId}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value={null}>— Choisir —</option>
          {#each listeSites as s (s.id)}
            <option value={s.id}>{s.nom}</option>
          {/each}
        </select>
      </label>
      <label class="block {cible === 'groupes' ? 'opacity-40 pointer-events-none' : ''}">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Type de population
        </span>
        <select
          bind:value={typePersonne}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value="eleve">Élèves</option>
          <option value="adulte">Adultes / Profs</option>
        </select>
      </label>
      <label class="block {cible === 'groupes' ? 'opacity-40 pointer-events-none' : ''}">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Catégorie
        </span>
        <select
          bind:value={categorie}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value="tous">Tous (état complet visé)</option>
          <option value="nouveaux">Nouveaux (à créer)</option>
          <option value="anciens">Anciens (sortants)</option>
        </select>
      </label>
    </div>
    {/if}

    {#if cible === "listes"}
      <div class="rounded-lg border-2 border-dashed border-sky-300 bg-sky-50/40 p-3 dark:border-sky-700 dark:bg-sky-900/10">
        <p class="mb-2 text-xs font-medium text-sky-900 dark:text-sky-200">
          Trois documents, depuis l'export KoXo du site
        </p>
        <p class="mb-2 text-xs text-stone-700 dark:text-stone-300">
          Le référentiel ne connaît pas les <strong>mots de passe</strong> : là
          où KoXo existe, c'est lui l'autorité, et le programme n'en invente
          aucun. Les trois documents en ont pourtant besoin. Exporte donc la
          base KoXo <strong>en cochant l'inclusion des mots de passe</strong>,
          puis dépose le fichier ici.
        </p>
        <ul class="mb-2 ml-4 list-disc text-xs text-stone-700 dark:text-stone-300">
          <li>la liste de <strong>tous</strong> les élèves — classeur trié et filtrable</li>
          <li>celle des <strong>entrants</strong> seuls</li>
          <li>les <strong>étiquettes</strong> des entrants, une planche par classe</li>
        </ul>
        <div class="flex flex-wrap items-center gap-2">
          <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-xs text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
            <Upload class="h-3.5 w-3.5" />
            {fichierListes?.name ?? "Choisir l'export KoXo (avec mots de passe)"}
            <input
              type="file"
              accept=".csv,.xlsx"
              onchange={(e) => {
                const champ = /** @type {HTMLInputElement} */ (e.target);
                fichierListes = champ.files?.[0] ?? null;
                rapportListes = null;
              }}
              class="hidden"
            />
          </label>
          {#if fichierListes}
            <button
              class="text-xs text-stone-500 hover:text-red-600"
              onclick={() => { fichierListes = null; rapportListes = null; }}
            >
              × retirer
            </button>
          {/if}
        </div>
        <p class="mt-1.5 text-xs text-stone-500 dark:text-stone-400">
          <strong>KoXo a une base par établissement</strong> : dépose celle du
          site choisi ci-dessus. Sans <strong>année source</strong>, les
          entrants ne peuvent pas être distingués — ni leur liste ni leurs
          étiquettes ne sont alors produites.
        </p>
      </div>

      <!-- Quoi produire. Tout décoché vaut « les quatre » : c'est le cas
           courant, et obliger à cocher pour obtenir le comportement normal
           serait une friction sans contrepartie. -->
      <div class="mt-3 rounded-lg border border-stone-200 p-3 dark:border-stone-700">
        <p class="mb-2 text-xs font-medium uppercase tracking-wide text-stone-500 dark:text-stone-400">
          Documents à produire
        </p>
        <div class="flex flex-wrap gap-x-5 gap-y-1.5">
          {#each DOCUMENTS as d (d.id)}
            <label class="inline-flex cursor-pointer items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={documentsVoulus.has(d.id)}
                onchange={() => {
                  if (documentsVoulus.has(d.id)) documentsVoulus.delete(d.id);
                  else documentsVoulus.add(d.id);
                  rapportListes = null;
                }}
              />
              {d.libelle}
            </label>
          {/each}
        </div>
        <p class="mt-1.5 text-xs text-stone-500 dark:text-stone-400">
          {documentsVoulus.size === 0
            ? "Rien de coché : les quatre seront produits."
            : `${documentsVoulus.size} document(s) retenu(s).`}
        </p>
      </div>

      <!-- Le modèle d'étiquette, avec son aperçu. Un aperçu sur « Jean
           DUPONT » ne montrerait jamais ce qui déborde : l'exemple porte
           un nom composé et l'adresse la plus longue de l'établissement. -->
      {#if modeles.length}
        <div class="mt-3 rounded-lg border border-stone-200 p-3 dark:border-stone-700">
          <p class="mb-2 text-xs font-medium uppercase tracking-wide text-stone-500 dark:text-stone-400">
            Présentation des étiquettes
          </p>
          <div class="flex flex-wrap items-start gap-4">
            <div class="min-w-56 flex-1 space-y-1">
              {#each modeles as m (m.id)}
                <label class="flex cursor-pointer items-start gap-2 rounded-md p-1.5 text-sm hover:bg-stone-100 dark:hover:bg-stone-800">
                  <input
                    type="radio"
                    class="mt-1"
                    checked={modeleChoisi === m.id}
                    onchange={() => { modeleChoisi = m.id; rapportListes = null; }}
                  />
                  <span class="min-w-0">
                    <span class="font-medium">{m.libelle}</span>
                    <span class="block text-xs text-stone-500 dark:text-stone-400">
                      {m.description}
                    </span>
                  </span>
                </label>
              {/each}
            </div>
            <div class="shrink-0">
              <div class="mb-1 flex items-baseline gap-3">
                <p class="text-xs text-stone-500 dark:text-stone-400">
                  Aperçu {siteId ? "" : "— choisis un site pour voir son logo"}
                </p>
                <label class="ml-auto inline-flex items-center gap-1.5 text-xs text-stone-600 dark:text-stone-300">
                  par feuille
                  <select
                    class="champ py-0.5 text-xs"
                    value={parPage}
                    onchange={(e) => {
                      parPage = Number(e.currentTarget.value);
                      rapportListes = null;
                    }}
                  >
                    <option value={18}>18</option>
                    <option value={15}>15</option>
                  </select>
                </label>
              </div>
              <iframe
                title="Aperçu de l'étiquette"
                src={exportsCible.urlApercuModele(modeleChoisi, siteId, parPage)}
                class="h-52 w-[420px] rounded-lg border border-stone-300 bg-white dark:border-stone-600"
              ></iframe>
            </div>
          </div>
        </div>
      {/if}

      <!-- Le filtre agit AVANT la génération : la première version ne
           proposait les classes qu'une fois les documents produits, si
           bien qu'il fallait tout sortir pour découvrir la liste, cocher,
           puis tout refaire. -->
      {#if elevesDuSite.length}
        <div class="mt-3 rounded-lg border border-stone-200 p-3 dark:border-stone-700">
          <div class="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <p class="text-xs font-medium uppercase tracking-wide text-stone-500 dark:text-stone-400">
              Qui exporter — {elevesDuSite.length} élève(s) au site
            </p>
            {#if classesRetenues.size || elevesRetenus.size}
              <button
                class="text-xs text-stone-500 hover:text-emerald-600"
                onclick={() => {
                  classesRetenues.clear();
                  elevesRetenus.clear();
                  rapportListes = null;
                }}
              >
                × tout le site
              </button>
            {/if}
          </div>

          <div class="flex flex-wrap gap-1.5">
            {#each classesDuSite as c (c)}
              <button
                class="rounded-full border px-2.5 py-1 text-xs {classesRetenues.has(c)
                  ? 'border-emerald-400 bg-emerald-50 text-emerald-900 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-200'
                  : 'border-stone-300 text-stone-600 hover:border-emerald-400 dark:border-stone-600 dark:text-stone-300'}"
                onclick={() => {
                  if (classesRetenues.has(c)) classesRetenues.delete(c);
                  else classesRetenues.add(c);
                  rapportListes = null;
                }}
              >
                {c}
              </button>
            {/each}
          </div>

          <!-- Le choix à l'unité : le cas courant du mot de passe perdu,
               où l'on ne veut qu'une étiquette. -->
          <details class="mt-2.5">
            <summary class="cursor-pointer text-xs text-stone-600 hover:text-emerald-600 dark:text-stone-300">
              Choisir des élèves un par un
              {#if elevesRetenus.size}({elevesRetenus.size} retenu(s)){/if}
            </summary>
            <input
              class="champ mt-2 w-full text-xs"
              placeholder="Chercher un nom, un prénom, une classe…"
              bind:value={filtreEleve}
            />
            <div class="mt-2 max-h-56 overflow-y-auto rounded-md border border-stone-200 dark:border-stone-700">
              {#each elevesAffiches.slice(0, 400) as e (e.personne_id)}
                <label class="flex cursor-pointer items-center gap-2 border-b border-stone-100 px-2 py-1 text-xs last:border-0 hover:bg-stone-50 dark:border-stone-800 dark:hover:bg-stone-800">
                  <input
                    type="checkbox"
                    checked={elevesRetenus.has(e.personne_id)}
                    onchange={() => {
                      if (elevesRetenus.has(e.personne_id))
                        elevesRetenus.delete(e.personne_id);
                      else elevesRetenus.add(e.personne_id);
                      rapportListes = null;
                    }}
                  />
                  <span class="w-14 shrink-0 text-stone-500">{e.classe}</span>
                  <span class="truncate">{e.prenom} {e.nom}</span>
                </label>
              {/each}
              {#if elevesAffiches.length > 400}
                <p class="px-2 py-1 text-xs text-stone-500">
                  … {elevesAffiches.length - 400} de plus — affine la recherche.
                </p>
              {/if}
            </div>
          </details>

          <p class="mt-1.5 text-xs text-stone-500 dark:text-stone-400">
            {#if elevesRetenus.size}
              {elevesRetenus.size} élève(s) nommément retenu(s).
            {:else if classesRetenues.size}
              {classesRetenues.size} classe(s) retenue(s).
            {:else}
              Rien de coché : tout le site.
            {/if}
          </p>
        </div>
      {/if}

    {/if}

    {#if cible === "charlemagne"}
      <div class="rounded-lg border-2 border-dashed border-sky-300 bg-sky-50/40 p-3 dark:border-sky-700 dark:bg-sky-900/10">
        <p class="mb-2 text-xs font-medium text-sky-900 dark:text-sky-200">
          Renvoyer à Charlemagne les adresses qu'il ne connaît pas
        </p>
        <p class="mb-2 text-xs text-stone-700 dark:text-stone-300">
          Charlemagne fait autorité sur l'état civil, la classe et le badge.
          Pas sur l'adresse : les comptes se créent <strong>ici</strong>, après
          son export de rentrée. Sa colonne <code>Email</code> reste donc vide
          pour toute la promotion entrante — et c'est cette colonne qu'il
          réexporte ensuite vers PMB et SoHappy.
        </p>
        <p class="mb-2 text-xs text-stone-700 dark:text-stone-300">
          Dépose le même fichier que pour PMB. L'annuaire <strong>Google est
          lu</strong> avant que la moindre adresse soit proposée : la plupart
          de celles du référentiel sont <em>calculées</em>, et pousser un
          calcul dans Charlemagne y propagerait l'erreur au lieu de la
          corriger.
        </p>
        <div class="flex flex-wrap items-center gap-2">
          <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-xs text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
            <Upload class="h-3.5 w-3.5" />
            {fichierCharlemagne?.name ?? "Choisir l'export de Charlemagne (.csv)"}
            <input
              type="file"
              accept=".csv"
              onchange={(e) => {
                const champ = /** @type {HTMLInputElement} */ (e.target);
                fichierCharlemagne = champ.files?.[0] ?? null;
                rapportAdresses = null;
              }}
              class="hidden"
            />
          </label>
          {#if fichierCharlemagne}
            <button
              class="text-xs text-stone-500 hover:text-red-600"
              onclick={() => { fichierCharlemagne = null; rapportAdresses = null; }}
            >
              × retirer
            </button>
          {/if}
        </div>
        <p class="mt-1.5 text-xs text-stone-500 dark:text-stone-400">
          Il suffit que le fichier porte <code>Num Badge</code> et
          <code>Email</code> : l'export PMB convient tel quel. La lecture de
          l'annuaire prend une minute et ne modifie rien. Le fichier rendu
          s'appellera
          <strong class="font-mono text-stone-700 dark:text-stone-300">
            Charlemagne_adresses_{anneeLibelleChoisie || "…"}.csv
          </strong>
        </p>
      </div>
    {/if}

    {#if cible === "pmb"}
      <div class="rounded-lg border-2 border-dashed border-sky-300 bg-sky-50/40 p-3 dark:border-sky-700 dark:bg-sky-900/10">
        <p class="mb-2 text-xs font-medium text-sky-900 dark:text-sky-200">
          Ce fichier vient de Charlemagne, pas du programme
        </p>
        <p class="mb-2 text-xs text-stone-700 dark:text-stone-300">
          PMB veut treize colonnes, dont l'<strong>adresse postale</strong>, le
          <strong>téléphone</strong>, l'<strong>année de naissance</strong> et le
          <strong>sexe</strong>. Aucune n'existe dans le référentiel : le
          programme ne peut pas les inventer. Sors l'export PMB depuis
          Charlemagne, puis dépose-le ici.
        </p>
        <p class="mb-2 text-xs text-stone-700 dark:text-stone-300">
          Ce que le programme fait, et que Charlemagne ne sait pas faire :
          <strong>le couper par établissement</strong>. Son export porte les
          trois sites en vrac, et PMB a une instance par établissement.
        </p>
        <div class="flex flex-wrap items-center gap-2">
          <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-xs text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
            <Upload class="h-3.5 w-3.5" />
            {fichierCharlemagne?.name ?? "Choisir l'export PMB de Charlemagne (.csv)"}
            <input
              type="file"
              accept=".csv"
              onchange={(e) => {
                const champ = /** @type {HTMLInputElement} */ (e.target);
                fichierCharlemagne = champ.files?.[0] ?? null;
                rapportPmb = null;
              }}
              class="hidden"
            />
          </label>
          {#if fichierCharlemagne}
            <button
              class="text-xs text-stone-500 hover:text-red-600"
              onclick={() => { fichierCharlemagne = null; rapportPmb = null; }}
            >
              × retirer
            </button>
          {/if}
        </div>
        <p class="mt-1.5 text-xs text-stone-500 dark:text-stone-400">
          Le contenu n'est pas touché — chaque ligne ressort telle quelle,
          colonne <code>Prof. Princ.</code> comprise. L'année choisie
          ci-dessous ne sert qu'à nommer les fichiers :
          <strong class="font-mono text-stone-700 dark:text-stone-300">
            PMB_&lt;SITE&gt;_{anneeLibelleChoisie || "…"}.csv
          </strong>
        </p>
      </div>
    {/if}

    <!-- Sans destination, la ligne d'un sortant porte sa dernière classe :
         synchronisée, elle le remettrait au milieu de la promotion
         suivante. Un groupe dédié le range ailleurs, sans le supprimer. -->
    <!-- Un prof existe dans les deux serveurs KoXo, et chacun range ses
         groupes à sa manière. Le fichier doit porter les groupes de la base
         qui va le recevoir, sinon la synchronisation déplace des comptes
         qui n'ont pas changé de matière. -->
    <!-- Un site sans serveur KoXo n'a personne pour fabriquer les mots de
         passe de ses élèves, ni pour les imprimer. Le programme s'en charge,
         et range au coffre dans le même geste. -->
    {#if cible === "google" && typePersonne === "eleve" && siteSansKoxo}
      <div class="rounded-lg border-2 border-dashed border-sky-300 bg-sky-50/40 p-3 dark:border-sky-700 dark:bg-sky-900/10">
        <p class="mb-2 text-xs font-medium text-sky-900 dark:text-sky-200">
          {siteChoisi.nom} n'a pas de serveur KoXo
        </p>
        <p class="mb-2 text-xs text-stone-700 dark:text-stone-300">
          Personne n'y fabrique les mots de passe de ses élèves, ni ne les
          imprime. Le programme le fait — à la forme de ceux de KoXo — et
          les range au <strong>coffre</strong> dans le même geste : un mot
          de passe fabriqué et non rangé serait perdu, et il faudrait
          réinitialiser chaque compte.
        </p>
        <p class="mb-2 text-xs text-stone-700 dark:text-stone-300">
          Deux fichiers en sortent : le CSV pour la console, et les
          <strong>étiquettes par classe</strong> à imprimer — le seul
          endroit où l'élève lira son mot de passe.
        </p>
        <Bouton
          variante="primary"
          icon={KeyRound}
          occupe={generationEnCours}
          disabled={!anneeCibleId}
          onclick={genererComptesSansKoxo}
        >
          Fabriquer les comptes et les étiquettes
        </Bouton>
        <p class="mt-1.5 text-xs text-stone-500 dark:text-stone-400">
          Le coffre doit être ouvert. Relancer ne change aucun mot de passe
          déjà distribué.
        </p>
      </div>
    {/if}

    {#if cible === "koxo" && typePersonne === "adulte"}
      <label class="block rounded-lg border border-stone-200 bg-stone-50 p-3 dark:border-stone-700 dark:bg-stone-800">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Base KoXo qui recevra ce fichier
        </span>
        <select
          bind:value={baseKoxo}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value={null}>Celle du site choisi</option>
          {#each listeSites as s (s.id)}<option value={s.nom}>{s.nom}</option>{/each}
        </select>
        <span class="mt-1 block text-xs text-stone-500 dark:text-stone-400">
          Les professeurs existent dans les deux serveurs, qui ne nomment pas
          leurs groupes secondaires pareil. Le fichier reprend les groupes que
          <strong>cette base</strong> détient, pour ne déplacer personne. Il
          faut d'abord avoir passé l'export de cette base au
          <strong>Contrôle KoXo</strong>, site désigné.
        </span>
      </label>
    {/if}

    {#if cible === "koxo" && categorie === "tous" && menaces && (menaces.comptes.length > 0 || menaces.avertissements.length > 0)}
      <div class="rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/40">
        <div class="flex items-baseline justify-between gap-2">
          <span class="text-xs font-medium uppercase tracking-wide text-amber-800 dark:text-amber-300">
            Comptes que la synchronisation désactivera
          </span>
          {#if menaces.comptes.length > 0}
            <span class="text-xs text-amber-700 dark:text-amber-400">
              base {menaces.base} · {menaces.nb_menaces} désactivé{menaces.nb_menaces > 1 ? "s" : ""}{#if menaces.nb_conserves > 0}, {menaces.nb_conserves} gardé{menaces.nb_conserves > 1 ? "s" : ""}{/if}
            </span>
          {/if}
        </div>

        {#each menaces.avertissements as a}
          <p class="mt-2 text-xs text-amber-800 dark:text-amber-300">{a}</p>
        {/each}

        {#if menaces.comptes.length > 0}
          <p class="mt-1 text-xs text-amber-700 dark:text-amber-400">
            Un export « tous » vaut état complet : KoXo désactive tout compte
            qui n'y figure pas. Coche ceux à garder — ils seront reconduits
            tels que la base les détient.
          </p>
          <ul class="mt-2 space-y-1">
            {#each menaces.comptes as c (c.badge)}
              <li
                class="flex items-start gap-2 rounded-md border px-2 py-1.5 text-sm {c.conserver
                  ? 'border-emerald-300 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/40'
                  : 'border-amber-200 bg-white dark:border-amber-900 dark:bg-stone-900'}"
              >
                <input
                  type="checkbox"
                  class="mt-1 shrink-0"
                  checked={c.conserver}
                  onchange={() => basculerConservation(c)}
                  aria-label="Garder {c.prenom} {c.nom}"
                />
                <span class="min-w-0 flex-1">
                  <span class="font-medium">{c.prenom} {c.nom}</span>
                  <span class="text-stone-500 dark:text-stone-400"> · {c.login}</span>
                  {#if c.groupe_secondaire}
                    <span class="text-stone-500 dark:text-stone-400"> · {c.groupe_secondaire}</span>
                  {/if}
                  <span class="block text-xs text-stone-500 dark:text-stone-400">{c.motif}</span>
                </span>
                <span class="shrink-0 text-xs {c.conserver ? 'text-emerald-700 dark:text-emerald-400' : 'text-amber-700 dark:text-amber-400'}">
                  {c.conserver ? "gardé" : "désactivé"}
                </span>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    {:else if cible === "koxo" && categorie === "tous" && menacesErreur}
      <p class="rounded-lg border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-300">
        Impossible de lire ce que la base détient : {menacesErreur}. Sans cette
        liste, tu ne sauras pas qui la synchronisation désactivera.
      </p>
    {:else if cible === "koxo" && categorie === "tous" && menacesEnCours}
      <p class="text-xs text-stone-500 dark:text-stone-400">
        Lecture de ce que la base détient…
      </p>
    {/if}

    {#if cible === "koxo" && categorie === "anciens"}
      <label class="block rounded-lg border border-stone-200 bg-stone-50 p-3 dark:border-stone-700 dark:bg-stone-800">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Groupe secondaire de destination
        </span>
        <input
          type="text"
          bind:value={groupeSortants}
          placeholder="Anciens élèves — laisse vide pour garder la dernière classe"
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        />
        <span class="mt-1 block text-xs text-stone-500 dark:text-stone-400">
          Renseigné, toutes les lignes porteront ce groupe au lieu de la
          dernière classe de l'élève. Le groupe doit exister dans KoXo, et
          cette synchronisation-là se fait en mode
          <strong>non destructif</strong> : le mode destructif supprimerait
          tout ce qui ne figure pas dans le fichier.
        </span>
      </label>
    {/if}

    {#if cible === "groupes"}
      <div class="flex flex-wrap gap-4 rounded-lg border border-stone-200 bg-stone-50 p-3 dark:border-stone-700 dark:bg-stone-800">
        <label class="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            bind:checked={inclureEleves}
            class="h-4 w-4 rounded border-stone-300 text-emerald-700 focus:ring-emerald-500"
          />
          Mailing lists de classe (élèves)
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            bind:checked={inclureProfs}
            class="h-4 w-4 rounded border-stone-300 text-emerald-700 focus:ring-emerald-500"
          />
          Groupes d'enseignants
        </label>
      </div>
    {/if}

    <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Année cible (à traiter)
        </span>
        <select
          bind:value={anneeCibleId}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value={null}>— Choisir —</option>
          {#each listeAnnees as a (a.id)}
            <option value={a.id}>{a.libelle}</option>
          {/each}
        </select>
      </label>
      {#if anneeSourceRequise}
        <label class="block">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
            Année source (référentiel)
          </span>
          <select
            bind:value={anneeSourceId}
            class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
          >
            <option value={null}>— Choisir —</option>
            {#each listeAnnees as a (a.id)}
              <option value={a.id}>{a.libelle}</option>
            {/each}
          </select>
        </label>
      {/if}
    </div>

    <!-- Rien ici pour les deux onglets qui partent d'un fichier : le
         programme n'y fabrique pas de CSV, et l'encadré du haut dit déjà
         d'où le fichier doit venir. -->
    {#if !partDunFichier}
    <div class="rounded-lg border border-stone-200 bg-stone-50 p-3 text-xs dark:border-stone-700 dark:bg-stone-800">
      <div class="flex items-start gap-2 text-stone-700 dark:text-stone-300">
        <Info class="mt-0.5 h-4 w-4 shrink-0" />
        <div class="space-y-1">
          {#if cible === "groupes"}
            <p>
              Appartenances aux groupes Google — un fichier à charger dans
              <strong>Admin Google → Groupes → Importer des membres</strong>.
            </p>
            <p>
              Les adresses viennent de la <strong>Table de correspondance</strong> :
              colonne <em>groupe Google</em> pour les élèves de la classe, colonne
              <em>groupe profs</em> pour les enseignants.
            </p>
            <p class="text-stone-500">
              Les enseignants sont déduits du champ Charlemagne « Liste des classes
              (prof principal) » — un intervenant qui n'est pas professeur principal
              n'y figure pas. Le rapport signale les groupes restés vides.
            </p>
          {:else if cible === "koxo"}
            {#if categorie === "tous"}
              <p>Toutes les personnes du site+type ayant un snapshot dans l'année cible. Utile pour un import massif initial ou une resynchronisation.</p>
            {:else if categorie === "nouveaux"}
              <p>Uniquement les entrants (présents cible, absents source). KoXo <strong>générera les mots de passe à l'import</strong>.</p>
            {:else}
              <p>Uniquement les sortants (présents source, absents cible). À utiliser pour supprimer les comptes obsolètes côté KoXo.</p>
            {/if}
          {:else}
            {#if categorie === "tous"}
              <p>État complet visé — chaque personne est placée dans son OU définitive (via Table de correspondance).</p>
            {:else if categorie === "nouveaux"}
              <p>Nouveaux comptes Google — placés dans l'<strong>OU pré-rentrée</strong>, avec le mot de passe repris du fichier KoXo déposé ci-dessus. <strong>Aucun changement forcé à la première connexion</strong> : l'élève n'a qu'un mot de passe, celui de sa fiche KoXo, et Google doit garder le même.</p>
            {:else}
              <p>Sortants — à déplacer manuellement vers <code>/7. Sortis/…</code> (l'automatisation viendra plus tard).</p>
            {/if}
            <p class="text-stone-500">Format Google Admin bulk-import : 40 colonnes, UTF-8 avec BOM. Ce CSV se charge dans Admin Google → Utilisateurs → Importer utilisateurs.</p>
          {/if}
        </div>
      </div>
    </div>
    {/if}

    {#if cible === "google" && categorie === "nouveaux"}
      <div class="rounded-lg border-2 border-dashed border-emerald-300 bg-emerald-50/40 p-3 dark:border-emerald-700 dark:bg-emerald-900/10">
        <p class="text-xs font-medium text-emerald-900 dark:text-emerald-200 mb-2">
          KoXo d'abord, Google ensuite
        </p>
        <p class="text-xs text-stone-700 dark:text-stone-300 mb-2">
          Créer un compte Google suppose un mot de passe, et c'est
          <strong>KoXo qui les génère</strong> — jamais le programme. L'ordre est
          donc : exporter les nouveaux vers KoXo, les y importer, puis
          re-exporter depuis KoXo <em>avec</em> les mots de passe et déposer ce
          fichier ici. Les mots de passe ne font que transiter en mémoire :
          <strong>rien n'est stocké côté serveur.</strong>
        </p>
        {#if !fichierKoxoEnrichi}
          <p class="mb-2 rounded bg-amber-100 px-2 py-1.5 text-xs text-amber-900 dark:bg-amber-900/30 dark:text-amber-200">
            Sans ce fichier, la colonne « Password » restera vide et Google
            refusera les créations. Le CSV n'en aura pas l'air.
          </p>
        {/if}
        <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-xs text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
          <Upload class="h-3.5 w-3.5" />
          {fichierKoxoEnrichi?.name ?? "Choisir le CSV KoXo (avec MDP)"}
          <input
            type="file"
            accept=".csv"
            onchange={(e) => (fichierKoxoEnrichi = e.target.files?.[0] ?? null)}
            class="hidden"
          />
        </label>
        {#if fichierKoxoEnrichi}
          <button
            class="ml-2 text-xs text-stone-500 hover:text-red-600"
            onclick={() => (fichierKoxoEnrichi = null)}
          >
            × retirer
          </button>
        {/if}
      </div>
    {/if}

    {#if categorie === "nouveaux"}
      <label class="flex items-start gap-2 text-xs text-stone-700 dark:text-stone-300">
        <input
          type="checkbox"
          bind:checked={enregistrerPrevus}
          class="mt-0.5 h-4 w-4 rounded border-stone-300 text-emerald-700 focus:ring-emerald-500"
        />
        <span>
          <strong>Enregistrer le suivi</strong> — inscrit les personnes du fichier
          comme comptes <em>prévus</em> sur cette cible. C'est ce qui alimente
          l'onglet <strong>Suivi</strong> ; tu confirmeras la création réelle
          après l'import.
        </span>
      </label>
    {/if}

    <div class="flex gap-2">
      {#if cible === "pmb"}
        <Bouton
          variante="primary"
          icon={FileDown}
          occupe={chargement}
          disabled={!fichierCharlemagne || !anneeCibleId}
          onclick={repartirPmb}
        >
          Répartir par établissement
        </Bouton>
      {:else if cible === "listes"}
        <Bouton
          variante="primary"
          icon={FileDown}
          occupe={chargement}
          disabled={!fichierListes || !siteId || !anneeCibleId}
          onclick={genererListes}
        >
          Produire les listes et les étiquettes
        </Bouton>
      {:else if cible === "charlemagne"}
        <Bouton
          variante="primary"
          icon={FileDown}
          occupe={chargement}
          disabled={!fichierCharlemagne}
          onclick={confronterAdresses}
        >
          Confronter à Google
        </Bouton>
      {:else}
        <Bouton
          variante="primary"
          icon={FileDown}
          occupe={chargement}
          disabled={!siteId || !anneeCibleId || (anneeSourceRequise && !anneeSourceId)}
          onclick={generer}
        >
          {cible === "google" && fichierKoxoEnrichi
            ? "Générer Google avec MDP"
            : "Générer et télécharger"}
        </Bouton>
      {/if}
    </div>

    {#if rapportListes}
      {@const r = rapportListes}
      <div class="space-y-3 rounded-lg border border-stone-200 bg-stone-50 p-3 dark:border-stone-700 dark:bg-stone-800">
        <p class="text-xs text-stone-600 dark:text-stone-400">
          {r.site_nom} · {r.annee_libelle} —
          <strong class="tabular-nums">{r.nb_tous}</strong> élève(s), dont
          <strong class="tabular-nums">{r.nb_nouveaux}</strong> entrants.
        </p>

        {#each [
          { nom: r.nom_xlsx_tous, b64: r.xlsx_tous_base64, mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            titre: "Tous les élèves", detail: `${r.nb_tous} lignes · classe, identifiant, mot de passe, adresse` },
          { nom: r.nom_xlsx_nouveaux, b64: r.xlsx_nouveaux_base64, mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            titre: "Les entrants seuls", detail: `${r.nb_nouveaux} lignes` },
          { nom: r.nom_etiquettes_tous, b64: r.etiquettes_tous_base64, mime: "text/html",
            titre: "Étiquettes de tous les élèves", detail: `${r.nb_tous} étiquettes · pour une réimpression ou un mot de passe perdu` },
          { nom: r.nom_etiquettes, b64: r.etiquettes_base64, mime: "text/html",
            titre: "Étiquettes des entrants", detail: "une planche par classe, à imprimer depuis le navigateur" },
        ] as doc (doc.titre)}
          {#if doc.b64}
            <div class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-stone-200 bg-white p-2.5 dark:border-stone-700 dark:bg-stone-900">
              <div class="min-w-0">
                <p class="text-sm font-medium">{doc.titre}</p>
                <p class="text-xs text-stone-500 dark:text-stone-400">{doc.detail}</p>
              </div>
              <Bouton
                icon={Download}
                taille="sm"
                onclick={() =>
                  enregistrerPaquet({ nom_fichier: doc.nom, contenu_base64: doc.b64 }, doc.mime)}
              >
                {doc.nom}
              </Bouton>
            </div>
          {/if}
        {/each}

        {#if !r.xlsx_nouveaux_base64}
          <p class="rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
            Sans <strong>année source</strong>, les entrants ne peuvent pas être
            distingués : seule la liste complète est produite.
          </p>
        {/if}

        {#if r.sans_ligne_koxo.length}
          <details class="rounded-lg border border-amber-300 bg-amber-50 p-2.5 dark:border-amber-800 dark:bg-amber-950/40">
            <summary class="cursor-pointer text-xs font-medium text-amber-900 dark:text-amber-200">
              {r.sans_ligne_koxo.length} élève(s) absents de l'export KoXo
            </summary>
            <p class="mt-1 text-xs text-amber-800 dark:text-amber-300">
              Ils n'ont pas de mot de passe à distribuer, et ne figurent dans
              aucun des trois documents. Synchronise KoXo, puis reprends
              l'export.
            </p>
            <p class="mt-1 text-xs text-stone-600 dark:text-stone-400">
              {r.sans_ligne_koxo.join(" · ")}
            </p>
          </details>
        {/if}

        {#if r.sans_mot_de_passe.length}
          <p class="rounded-lg border border-rose-300 bg-rose-50 p-2.5 text-xs text-rose-900 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
            {r.sans_mot_de_passe.length} élève(s) sans mot de passe dans
            l'export — leur étiquette sortirait vide. Reprends l'export KoXo en
            cochant l'inclusion des mots de passe.
          </p>
        {/if}
      </div>
    {/if}

    {#if rapportAdresses}
      {@const r = rapportAdresses}
      <div class="space-y-3 rounded-lg border border-stone-200 bg-stone-50 p-3 dark:border-stone-700 dark:bg-stone-800">
        <p class="text-xs text-stone-600 dark:text-stone-400">
          {r.nb_lignes_lues} ligne(s) lues · {r.nb_deja_bonnes} déjà justes ·
          <strong class="tabular-nums">{r.nb_a_importer}</strong> à renvoyer.
        </p>

        {#if r.nb_a_importer > 0}
          <div class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-emerald-300 bg-white p-2.5 dark:border-emerald-800 dark:bg-stone-900">
            <div class="min-w-0">
              <p class="text-sm font-medium">
                {r.a_remplir.length} adresse(s) à remplir
                {#if r.a_corriger.length}
                  · {r.a_corriger.length} à corriger
                {/if}
              </p>
              <p class="text-xs text-stone-500 dark:text-stone-400">
                Toutes vues dans l'annuaire Google — aucune supposition.
              </p>
            </div>
            <Bouton
              icon={Download}
              taille="sm"
              onclick={() =>
                enregistrerPaquet({
                  nom_fichier: r.nom_fichier,
                  contenu_base64: r.contenu_base64,
                })}
            >
              {r.nom_fichier}
            </Bouton>
          </div>
        {:else}
          <p class="rounded-lg border border-emerald-300 bg-white p-2.5 text-sm dark:border-emerald-800 dark:bg-stone-900">
            Rien à renvoyer : Charlemagne connaît déjà toutes les adresses
            que le programme peut confirmer.
          </p>
        {/if}

        {#each [
          { cle: "a_corriger", titre: "Adresses fausses dans Charlemagne", ton: "danger",
            mot: "Elles n'existent pas dans Google. Elles sont dans le fichier ci-dessus." },
          { cle: "a_verifier", titre: "Non vérifiables", ton: "attention",
            mot: "L'adresse du référentiel n'a pas été trouvée dans Google : rien n'est proposé." },
          { cle: "conflit", titre: "Deux comptes distincts", ton: "danger",
            mot: "Charlemagne et le référentiel désignent des comptes différents — à trancher à la main." },
          { cle: "adresse_personnelle", titre: "Adresse de famille dans le champ", ton: "attention",
            mot: "Écraser est peut-être ce qu'il faut, mais c'est une décision sans retour : ces lignes ne sont pas dans le fichier." },
          { cle: "referentiel_a_tort", titre: "À corriger ici, pas dans Charlemagne", ton: "attention",
            mot: "Google donne raison à Charlemagne." },
          { cle: "alias_dans_charlemagne", titre: "Alias du bon compte", ton: "neutre",
            mot: "Le courrier arrive : rien à faire." },
          { cle: "sans_adresse_nulle_part", titre: "Aucune adresse nulle part", ton: "attention",
            mot: "Ni Charlemagne ni le référentiel n'en connaissent." },
          { cle: "hors_referentiel", titre: "Inconnus du programme", ton: "neutre",
            mot: "Dans Charlemagne, jamais ingérés ici — une ingestion les prendra." },
        ] as bloc (bloc.cle)}
          {#if r[bloc.cle].length}
            <details
              class="rounded-lg border p-2.5 {bloc.ton === 'danger'
                ? 'border-rose-300 bg-rose-50 dark:border-rose-800 dark:bg-rose-950/30'
                : bloc.ton === 'attention'
                  ? 'border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30'
                  : 'border-stone-300 bg-white dark:border-stone-600 dark:bg-stone-900'}"
              open={bloc.ton === "danger"}
            >
              <summary class="cursor-pointer text-xs font-medium">
                {bloc.titre}
                <span class="text-stone-500 dark:text-stone-400">
                  — {r[bloc.cle].length}
                </span>
              </summary>
              <p class="mt-1 text-xs text-stone-600 dark:text-stone-400">{bloc.mot}</p>
              <ul class="mt-1.5 space-y-0.5">
                {#each r[bloc.cle] as c (c.badge + bloc.cle)}
                  <li class="text-xs">
                    <span class="font-medium">{c.prenom} {c.nom}</span>
                    <span class="text-stone-500 dark:text-stone-400">
                      · badge {c.badge}{c.classe ? ` · ${c.classe}` : ""}
                    </span>
                    {#if c.detail}
                      <span class="block text-stone-500 dark:text-stone-400">{c.detail}</span>
                    {/if}
                  </li>
                {/each}
              </ul>
            </details>
          {/if}
        {/each}
      </div>
    {/if}

    {#if rapportPmb}
      <div class="space-y-3 rounded-lg border border-stone-200 bg-stone-50 p-3 dark:border-stone-700 dark:bg-stone-800">
        <p class="text-xs text-stone-600 dark:text-stone-400">
          {rapportPmb.nb_lignes_lues} ligne(s) lues,
          <strong class="tabular-nums">{rapportPmb.nb_reparties}</strong> réparties.
          La somme des fichiers vaut le fichier d'origine, aux écartées près.
        </p>

        {#each rapportPmb.paquets as p (p.site_nom)}
          <div class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-stone-200 bg-white p-2.5 dark:border-stone-700 dark:bg-stone-900">
            <div class="min-w-0">
              <p class="text-sm font-medium">
                {p.site_nom}
                <span class="text-stone-500 dark:text-stone-400">
                  — {p.nb_eleves} élèves, {p.classes.length} classes
                </span>
              </p>
              <p class="truncate font-mono text-xs text-stone-500 dark:text-stone-400">
                {p.classes.join(" ")}
              </p>
            </div>
            <Bouton icon={Download} taille="sm" onclick={() => enregistrerPaquet(p)}>
              {p.nom_fichier}
            </Bouton>
          </div>
        {/each}

        {#if rapportPmb.ecartees.length}
          <div class="rounded-lg border border-amber-300 bg-amber-50 p-2.5 dark:border-amber-800 dark:bg-amber-950/40">
            <p class="text-xs font-medium text-amber-900 dark:text-amber-200">
              {rapportPmb.ecartees.length} ligne(s) dans aucun fichier
            </p>
            <p class="mt-0.5 text-xs text-amber-800 dark:text-amber-300">
              Leur classe n'est dans aucune table de correspondance. Sans cette
              liste, l'élève disparaîtrait sans bruit.
            </p>
            <ul class="mt-1.5 space-y-0.5">
              {#each rapportPmb.ecartees as e (e.badge + e.code_classe)}
                <li class="text-xs">
                  <span class="font-medium">{e.prenom} {e.nom}</span>
                  <span class="text-stone-500 dark:text-stone-400">
                    · badge {e.badge} · {e.motif}
                  </span>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if rapportPmb.inconnus_du_referentiel.length}
          <div class="rounded-lg border border-stone-300 bg-white p-2.5 dark:border-stone-600 dark:bg-stone-900">
            <p class="text-xs font-medium">
              {rapportPmb.inconnus_du_referentiel.length} élève(s) que le
              programme ne connaît pas
            </p>
            <p class="mt-0.5 text-xs text-stone-600 dark:text-stone-400">
              Ils sont bien dans les fichiers ci-dessus, et entreront dans PMB.
              Mais ils n'ont jamais été ingérés ici : ni compte Google, ni
              compte KoXo, et le <strong>Bilan</strong> ne les voit pas. Une
              ingestion Charlemagne les prendra tous d'un coup.
            </p>
            <ul class="mt-1.5 space-y-0.5">
              {#each rapportPmb.inconnus_du_referentiel as i (i.badge)}
                <li class="text-xs">
                  <span class="font-medium">{i.prenom} {i.nom}</span>
                  <span class="text-stone-500 dark:text-stone-400">
                    · badge {i.badge} · classe {i.code_classe}
                  </span>
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>
    {/if}

    {#if erreur}
      <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
        {erreur}
      </p>
    {/if}
  </div>

  <!-- Mode API Google — canal alternatif au CSV -->
  {#if cible === "google" && statutApi}
    <div class="card p-4 space-y-3">
      <div class="flex items-center justify-between gap-2">
        <h2 class="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
          <Cloud class="h-4 w-4" />
          Mode API (optionnel)
        </h2>
        {#if statutApi.configuration_complete}
          <span class="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
            <CheckCircle2 class="h-3.5 w-3.5" />
            Configuré
          </span>
        {:else}
          <span class="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-600 dark:bg-stone-800 dark:text-stone-400">
            Non configuré
          </span>
        {/if}
      </div>

      {#if statutApi.bibliotheques_disponibles}
        <div class="mb-3">
          <Bouton icon={Cloud} occupe={testEnCours} onclick={testerConnexion}>
            Tester la connexion
          </Bouton>
          <span class="ml-2 text-xs text-stone-500 dark:text-stone-400">
            Lit un seul utilisateur, ne modifie rien.
          </span>
        </div>
      {/if}

      {#if !statutApi.configuration_complete}
        <div class="rounded-lg border border-stone-200 bg-stone-50 p-3 text-xs dark:border-stone-700 dark:bg-stone-800">
          <p class="text-stone-700 dark:text-stone-300">
            Le mode API applique les changements directement dans Google, sans
            passer par l'import manuel du CSV. <strong>Le mode fichier
            ci-dessus reste le mode nominal</strong> et fonctionne sans cette
            configuration.
          </p>
          {#if statutApi.problemes.length > 0}
            <ul class="mt-2 space-y-0.5 text-stone-600 dark:text-stone-400">
              {#each statutApi.problemes as p}
                <li>• {p}</li>
              {/each}
            </ul>
          {/if}
          {#if !statutApi.bibliotheques_disponibles}
            <p class="mt-2 text-stone-500">{statutApi.message_bibliotheques}</p>
          {/if}
        </div>
      {:else}
        <!--
          Deux écrans savaient appliquer un déplacement d'OU, sans que rien
          ne dise lequel choisir. Celui-ci reste utile pour les créations et
          les suspensions ; pour les OU, la Bascule montre l'avancement.
        -->
        <p class="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-900 dark:bg-emerald-900/20 dark:text-emerald-200">
          Pour <strong>déplacer les élèves d'OU</strong>, préfère l'onglet
          <strong>Bascule des OU</strong> : même traitement, mais avec
          l'avancement élève par élève et la reprise des échecs. Cette
          section-ci sert aux créations de comptes et aux suspensions.
        </p>

        <div class="mb-3">
          <span class="libelle-champ">Phase de rentrée</span>
          <Segments
            bind:valeur={phaseApi}
            taille="sm"
            options={[
              { id: "pre_rentree", label: "1. Pré-rentrée" },
              { id: "definitive", label: "2. Rentrée" },
            ]}
            onChange={() => (planApi = null)}
          />
          <p class="mt-1.5 text-xs text-stone-500 dark:text-stone-400">
            Même découpage que l'onglet <strong>Bascule des OU</strong> : les
            déplacements sont calculés par le même service, les deux canaux ne
            peuvent pas diverger.
          </p>
        </div>

        <div class="flex flex-wrap gap-2">
          <button class="btn-secondary" onclick={calculerPlanApi} disabled={apiEnCours}>
            <Cloud class="h-4 w-4" />
            Calculer le plan
          </button>
          {#if planApi && planApi.nb_total > 0 && planApi.est_executable}
            <button class="btn-primary" onclick={executerPlanApi} disabled={apiEnCours}>
              Appliquer les {planApi.nb_total} opération(s)
            </button>
          {/if}
        </div>

        {#if planApi}
          <div class="rounded-lg border border-stone-200 p-3 text-sm dark:border-stone-700">
            <p class="font-medium">
              {planApi.nb_creations} création(s) · {planApi.nb_deplacements} déplacement(s)
              · {planApi.nb_suspensions} suspension(s)
            </p>
            <p class="mt-1 text-xs text-stone-500">
              Aucun compte n'est jamais supprimé — un sortant est suspendu et
              déplacé en OU d'archivage.
            </p>
            {#if !planApi.est_executable}
              <p class="mt-2 rounded bg-red-50 px-2 py-1.5 text-xs text-red-700 dark:bg-red-900/30 dark:text-red-300">
                {planApi.nb_bloques} élève(s) sans OU calculable — exécution
                refusée. Complète la Table de correspondance : le programme
                n'attribue jamais d'OU par défaut.
              </p>
            {/if}
            {#if planApi.avertissements.length > 0}
              <ul class="mt-2 space-y-0.5 text-xs text-amber-700 dark:text-amber-400">
                {#each planApi.avertissements.slice(0, 10) as a}
                  <li>⚠ {a}</li>
                {/each}
              </ul>
            {/if}
            {#if planApi.operations.length > 0}
              <details class="mt-2">
                <summary class="cursor-pointer text-xs text-sky-700 dark:text-sky-400">
                  Voir les opérations
                </summary>
                <ul class="mt-1 space-y-0.5 text-xs text-stone-600 dark:text-stone-400">
                  {#each planApi.operations.slice(0, 50) as o}
                    <li>{o.libelle}</li>
                  {/each}
                </ul>
              </details>
            {/if}
          </div>
        {/if}
      {/if}
    </div>
  {/if}

  {#if dernierRapport}
    <div class="card p-4">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm font-semibold text-stone-900 dark:text-stone-100">
            Dernier export : <code>{dernierRapport.nom_fichier}</code>
          </p>
          <p class="text-xs text-stone-500 dark:text-stone-400">
            {dernierRapport.nb_lignes} ligne(s) — {dernierRapport.cible}, site {dernierRapport.site_nom},
            {dernierRapport.type_personne}s, catégorie {dernierRapport.categorie}
          </p>
          {#each dernierRapport.avertissements ?? [] as a}
            <p class="mt-1 text-xs text-amber-700 dark:text-amber-400">⚠ {a}</p>
          {/each}
          {#if dernierRapport.nb_sans_ou > 0 && !(dernierRapport.avertissements ?? []).length}
            <p class="text-xs text-amber-700 dark:text-amber-400">
              ⚠ {dernierRapport.nb_sans_ou} ligne(s) sans OU — leur classe n'est pas dans la Table de correspondance.
            </p>
          {/if}
          {#if dernierRapport.nb_lignes_avec_mdp !== undefined}
            <p class="mt-1 text-xs text-emerald-700 dark:text-emerald-400">
              {dernierRapport.nb_lignes_avec_mdp} ligne(s) sur {dernierRapport.nb_lignes}
              ont reçu leur mot de passe
              {#if dernierRapport.nb_mdp_orphelins > 0}
                · {dernierRapport.nb_mdp_orphelins} entrée(s) KoXo sans correspondance
              {/if}
            </p>
          {/if}
          {#if dernierRapport.classes_sans_groupe?.length > 0}
            <p class="text-xs text-amber-700 dark:text-amber-400">
              ⚠ {dernierRapport.classes_sans_groupe.length} classe(s) sans adresse de groupe :
              <span class="font-mono">{dernierRapport.classes_sans_groupe.join(", ")}</span>
            </p>
          {/if}
          {#if dernierRapport.groupes_profs_vides?.length > 0}
            <p class="text-xs text-stone-500">
              {dernierRapport.groupes_profs_vides.length} groupe(s) profs sans aucun
              enseignant rattaché — le champ « prof principal » ne couvre pas tous
              les intervenants.
            </p>
          {/if}
        </div>
        <button
          class="btn-secondary text-xs"
          onclick={() => enregistrerFichierBase64(dernierRapport.nom_fichier, dernierRapport.contenu_base64, "text/csv")}
        >
          <Download class="h-3.5 w-3.5" />
          Ré-enregistrer
        </button>
      </div>
    </div>
  {/if}
</section>
