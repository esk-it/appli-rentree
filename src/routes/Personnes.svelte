<script>
  import { onMount, tick, untrack } from "svelte";
  import Search from "@lucide/svelte/icons/search";
  import Users2 from "@lucide/svelte/icons/users-2";
  import FolderTree from "@lucide/svelte/icons/folder-tree";
  import Download from "@lucide/svelte/icons/download";
  import RotateCcw from "@lucide/svelte/icons/rotate-ccw";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Info from "@lucide/svelte/icons/info";
  import Avatar from "$lib/components/Avatar.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import DeplacementGoogle from "$lib/components/DeplacementGoogle.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Modale from "$lib/components/Modale.svelte";
  import Onglets from "$lib/components/Onglets.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import Touche from "$lib/components/Touche.svelte";
  import ApercuPersonne from "$lib/components/referentiel/ApercuPersonne.svelte";
  import CeQuiManque from "$lib/components/referentiel/CeQuiManque.svelte";
  import Facettes from "$lib/components/referentiel/Facettes.svelte";
  import ParClasse from "$lib/components/referentiel/ParClasse.svelte";
  import {
    annees as anneesApi,
    concordance as concordanceApi,
    enregistrerFichierBase64,
    personnes,
  } from "$lib/api.js";
  import { ecrire, lire } from "$lib/memoire.svelte.js";
  import { comparerNaturel, csvDeClasse, etatDe, texteEnBase64 } from "$lib/referentiel.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Le Référentiel : retrouver quelqu'un, et agir sur lui.
   *
   * ## Trois vues, trois questions
   *
   * - **Personnes** — « où est cette personne, et qu'est-ce qu'il lui
   *   faut ? ». La liste à gauche, regroupée par classe ; sa fiche à côté,
   *   sans quitter la liste. Les flèches passent d'une personne à l'autre.
   * - **Par classe** — « qui est dans cette classe ? ». L'arbre des
   *   classes, le trombinoscope, et les gestes de rentrée : l'imprimer,
   *   faire les cartes, sortir la liste.
   * - **Ce qui manque** — « qu'est-ce qui manque encore, et où ? ». Les
   *   taux de remplissage, puis classe par classe.
   *
   * ## Une année par défaut
   *
   * Le référentiel ne supprime jamais personne : sans année, un élève parti
   * il y a trois ans resterait rangé dans sa dernière classe. L'écran
   * s'ouvre donc sur l'année la plus récente — les nouveaux, ceux qui
   * restent, ceux qui sont partis. « Tout le référentiel » reste au menu.
   *
   * ## Les filtres disent ce qu'ils ramèneraient
   *
   * Chaque valeur porte son nombre, compte tenu des autres filtres : on lit
   * qu'il y a vingt-quatre personnes sans site avant de les chercher.
   *
   * @typedef {Object} Props
   * @property {(id: number) => void} [onOuvrirFiche]
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onOuvrirFiche, onNaviguer } = $props();

  const libelle = (e) => String(e).replace(/^Error:\s*/, "");

  // --- Les données -------------------------------------------------------
  // Gardées d'une visite à l'autre. On revient ici dix fois par jour, et
  // relire deux mille fiches à chaque retour faisait attendre une seconde
  // un écran qu'on venait de quitter. Ce qui a été gardé s'affiche tout de
  // suite et se relit derrière ; « mise à jour » le dit le temps que ça
  // arrive. Rien n'est gardé d'un lancement à l'autre (voir memoire.svelte.js).
  //
  // `$state.raw` : ces données ne se modifient jamais en place, on les
  // remplace. Un proxy profond sur deux mille fiches se payait à chaque
  // lecture de champ, pour rien.
  const VIDE = { eleve: null, adulte: null };
  let liste = $state.raw(lire("referentiel.donnees.liste", /** @type {any[]} */ ([])));
  let verdicts = $state.raw(lire("referentiel.donnees.verdicts", /** @type {Record<number, any>} */ ({})));
  let listeAnnees = $state.raw(lire("referentiel.donnees.annees", /** @type {any[]} */ ([])));
  let chargement = $state(true);
  let chargementAnnee = $state(false);
  let actualisation = $state(false);
  let actualisationAnnee = $state(false);
  let erreur = $state("");
  $effect(() => ecrire("referentiel.donnees.liste", liste));
  $effect(() => ecrire("referentiel.donnees.verdicts", verdicts));
  $effect(() => ecrire("referentiel.donnees.annees", listeAnnees));

  // --- Ce qui survit à la navigation : aller voir une fiche et revenir ne
  // doit pas défaire les filtres ni perdre la personne choisie. ------------
  let onglet = $state(lire("referentiel.onglet", "personnes"));
  // Lue à part : un `<select>` lié à une valeur indéfinie prend d'office sa
  // première option — « Tout le référentiel » — avant que l'année la plus
  // récente ait pu être choisie.
  const anneeRetenue = lire("referentiel.annee", /** @type {number|null|undefined} */ (undefined));
  let anneeId = $state(/** @type {number|null} */ (anneeRetenue ?? null));
  let mouvements = $state.raw(
    /** @type {{eleve: any, adulte: any}} */ (lire(`referentiel.donnees.mouvements.${anneeRetenue}`, VIDE)),
  );
  let recherche = $state(lire("referentiel.recherche", ""));
  let choix = $state(lire("referentiel.choix", /** @type {Record<string, string[]>} */ ({})));
  let filtreClasse = $state(lire("referentiel.classe", ""));
  let selectionne = $state(lire("referentiel.selectionne", /** @type {number|null} */ (null)));
  let classeOuverte = $state(lire("referentiel.classeOuverte", ""));
  $effect(() => ecrire("referentiel.onglet", onglet));
  $effect(() => ecrire("referentiel.annee", anneeId));
  $effect(() => ecrire("referentiel.recherche", recherche));
  $effect(() => ecrire("referentiel.choix", choix));
  $effect(() => ecrire("referentiel.classe", filtreClasse));
  $effect(() => ecrire("referentiel.selectionne", selectionne));
  $effect(() => ecrire("referentiel.classeOuverte", classeOuverte));

  let coches = $state(/** @type {Set<number>} */ (new Set()));
  let deplacement = $state(/** @type {any[]|null} */ (null));
  let champRecherche = $state(/** @type {HTMLInputElement|null} */ (null));
  let apercu = $state(/** @type {any} */ (null));

  // Tout part en même temps : les années, les fiches, les verdicts. Seuls
  // les mouvements attendent — il leur faut l'année, et l'année par défaut
  // est la plus récente de la liste.
  onMount(() => {
    anneesApi
      .lister()
      .then((a) => (listeAnnees = a.slice().sort((x, y) => x.libelle.localeCompare(y.libelle))))
      .catch(() => {})
      .finally(() => {
        if (anneeRetenue === undefined) anneeId = listeAnnees.at(-1)?.id ?? null;
      });
    rafraichir();
  });

  async function rafraichir() {
    const deja = liste.length > 0;
    chargement = !deja;
    actualisation = deja;
    erreur = "";
    const [p, v] = await Promise.allSettled([personnes.lister(), concordanceApi.verdicts()]);
    if (p.status === "fulfilled") liste = p.value;
    else erreur = libelle(p.reason);
    // Pas de verdicts, ce n'est pas une panne : la Concordance n'a peut-être
    // jamais été lancée. On garde alors ce qu'on avait.
    if (v.status === "fulfilled") verdicts = v.value;
    chargement = false;
    actualisation = false;
  }

  // Les mouvements de l'année se lisent dans deux sources : les photographies
  // annuelles pour les élèves, le tableau des professeurs pour les adultes.
  // Gardés par année : revenir sur une année déjà vue la montre aussitôt.
  $effect(() => {
    const id = anneeId;
    if (id === null || id === undefined) {
      mouvements = VIDE;
      return;
    }
    const cle = `referentiel.donnees.mouvements.${id}`;
    const garde = untrack(() => lire(cle, null));
    // Une année qu'on n'a pas encore vue ne montre pas la précédente sous
    // son nom : la liste attend, « Lecture de l'année… ».
    mouvements = garde ?? VIDE;
    let annule = false;
    chargementAnnee = !garde;
    actualisationAnnee = !!garde;
    Promise.allSettled([
      personnes.mouvements({ anneeId: id, type: "eleve" }),
      personnes.mouvements({ anneeId: id, type: "adulte" }),
    ])
      .then(([e, a]) => {
        if (annule) return;
        const m = {
          eleve: e.status === "fulfilled" ? e.value : (garde?.eleve ?? null),
          adulte: a.status === "fulfilled" ? a.value : (garde?.adulte ?? null),
        };
        mouvements = m;
        ecrire(cle, m);
        if (e.status === "rejected") notify.erreur(libelle(e.reason));
      })
      .finally(() => {
        if (annule) return;
        chargementAnnee = false;
        actualisationAnnee = false;
      });
    return () => (annule = true);
  });

  let parId = $derived(new Map(liste.map((p) => [p.id, p])));
  let libelleAnnee = $derived(listeAnnees.find((a) => a.id === anneeId)?.libelle ?? "");
  let parAnnee = $derived(anneeId !== null && anneeId !== undefined);

  /**
   * Les personnes montrées : le référentiel entier, ou les lignes de
   * l'année — nouveaux, présents et partis — complétées par leur fiche.
   */
  let lignes = $derived.by(() => {
    if (!parAnnee) return liste;
    const r = [];
    let n = 0;
    for (const type of ["eleve", "adulte"]) {
      const m = mouvements[type];
      if (!m) continue;
      for (const l of m.lignes) {
        n += 1;
        const p = l.personne_id != null ? parId.get(l.personne_id) : null;
        r.push({
          ...(p ?? {}),
          id: l.personne_id ?? -n,
          sans_compte: l.personne_id == null,
          type: l.type || type,
          nom: l.nom ?? p?.nom ?? "",
          prenom: l.prenom ?? p?.prenom ?? "",
          site: l.site ?? p?.site ?? null,
          classe:
            l.mouvement === "sortant"
              ? (l.classe_precedente ?? l.classe ?? p?.classe ?? null)
              : (l.classe ?? p?.classe ?? null),
          cle_pivot: l.cle_pivot ?? p?.cle_pivot ?? null,
          badge: l.badge ?? p?.badge ?? null,
          login: p?.login ?? l.login ?? null,
          email: p?.email ?? l.email ?? null,
          mouvement: l.mouvement,
          detail: l.detail,
          discipline: l.discipline,
        });
      }
    }
    return r;
  });

  let inscrites = $derived(parAnnee ? lignes.filter((p) => p.mouvement !== "sortant").length : 0);

  // --- Les filtres -----------------------------------------------------------
  const sansAccents = (s) =>
    String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  // Un seul comparateur pour tout le tri : `localeCompare(…, "fr")` en
  // refabrique un à chaque appel, et trier deux mille noms en fait vingt mille.
  const ORDRE = new Intl.Collator("fr");

  const aDeja = {
    adresse: (p) => !!p.email_est_constate,
    coffre: (p) => !!p.au_coffre,
    ine: (p) => !!p.ine,
    naissance: (p) => !!p.date_naissance,
  };

  let sites = $derived([...new Set(lignes.map((p) => p.site).filter(Boolean))].sort());

  let definitions = $derived([
    {
      cle: "type", titre: "Population",
      valeurs: [["eleve", "Élèves"], ["adulte", "Adultes"]],
      teste: (p, v) => p.type === v,
    },
    ...(parAnnee
      ? [{
          cle: "mouvement", titre: `Mouvement ${libelleAnnee}`,
          valeurs: [["entrant", "Nouveaux"], ["present", "Déjà là"], ["sortant", "Partis"]],
          teste: (p, v) => p.mouvement === v,
        }]
      : []),
    {
      cle: "site", titre: "Site",
      valeurs: [...sites.map((s) => [s, s]), ["__aucun", "Sans site"]],
      teste: (p, v) => (v === "__aucun" ? !p.site : p.site === v),
      tons: { __aucun: "alerte" },
    },
    {
      cle: "etat", titre: "État",
      valeurs: [["pret", "Cohérent"], ["ecart", "En écart"], ["inconnu", "Pas vérifié"]],
      teste: (p, v) => etatDe(p, verdicts).etat === v,
      tons: { ecart: "alerte" },
    },
    {
      cle: "manque", titre: "Il lui manque",
      valeurs: [
        ["adresse", "Une adresse constatée"], ["coffre", "Un mot de passe au coffre"],
        ["ine", "L'INE"], ["naissance", "La date de naissance"],
      ],
      // Un adulte n'a pas d'INE : il ne lui « manque » donc pas.
      teste: (p, v) => !p.sans_compte && (v !== "ine" || p.type === "eleve") && !aDeja[v](p),
      tons: { adresse: "attente", coffre: "attente", ine: "attente", naissance: "attente" },
    },
  ]);

  let q = $derived(sansAccents(recherche.trim()));

  // Le texte où l'on cherche, préparé une fois par fiche plutôt qu'à chaque
  // lettre tapée : chaque filtre relit toute la liste pour compter ce qu'il
  // ramènerait, et ôter les accents de deux mille lignes cinq fois par
  // touche se sentait.
  let texteDe = $derived(
    new Map(
      lignes.map((p) => [
        p,
        sansAccents(
          `${p.nom} ${p.prenom} ${p.login ?? ""} ${p.login_constate ?? ""} ${p.cle_pivot ?? ""} ${p.badge ?? ""} ${p.email ?? ""}`,
        ),
      ]),
    ),
  );

  function passeBase(p) {
    if (filtreClasse && p.classe !== filtreClasse) return false;
    if (q && !texteDe.get(p)?.includes(q)) return false;
    return true;
  }

  function passeFacettes(p, sauf = null) {
    for (const d of definitions) {
      if (d.cle === sauf) continue;
      const vs = choix[d.cle];
      if (vs?.length && !vs.some((v) => d.teste(p, v))) return false;
    }
    return true;
  }

  let filtrees = $derived(lignes.filter((p) => passeBase(p) && passeFacettes(p)));

  let facettes = $derived(
    definitions.map((d) => {
      const base = lignes.filter((p) => passeBase(p) && passeFacettes(p, d.cle));
      return {
        cle: d.cle,
        titre: d.titre,
        options: d.valeurs.map(([id, label]) => ({
          id, label, compte: base.filter((p) => d.teste(p, id)).length, ton: d.tons?.[id] ?? "",
        })),
      };
    }),
  );

  let classesDispo = $derived(
    [...new Set(lignes.filter((p) => p.type === "eleve" && p.classe).map((p) => p.classe))].sort(comparerNaturel),
  );

  let filtresActifs = $derived(
    !!recherche || !!filtreClasse || Object.values(choix).some((v) => v?.length),
  );

  function toutEffacer() {
    recherche = "";
    filtreClasse = "";
    choix = {};
  }

  /** Pourquoi un mouvement ne peut pas être établi, s'il ne le peut pas. */
  let raisons = $derived(
    (choix.mouvement ?? [])
      .flatMap((m) => [mouvements.eleve?.raisons?.[m], mouvements.adulte?.raisons?.[m]])
      .filter(Boolean),
  );

  // --- La liste, rangée par classe ------------------------------------------
  function groupeDe(p) {
    if (p.mouvement === "sortant") return { cle: "~3", titre: "Partis" };
    if (p.type === "adulte") return { cle: "~1", titre: "Personnel" };
    if (!p.classe) return { cle: "~2", titre: "Sans classe" };
    return { cle: `${p.site ?? "~"}/${p.classe}`, titre: p.classe, site: p.site };
  }

  let groupes = $derived.by(() => {
    const m = new Map();
    for (const p of filtrees) {
      const g = groupeDe(p);
      if (!m.has(g.cle)) m.set(g.cle, { ...g, personnes: [] });
      m.get(g.cle).personnes.push(p);
    }
    const gs = [...m.values()];
    gs.sort((a, b) => {
      const fa = a.cle.startsWith("~");
      const fb = b.cle.startsWith("~");
      if (fa !== fb) return fa ? 1 : -1;
      if (fa) return a.cle.localeCompare(b.cle);
      return (a.site ?? "").localeCompare(b.site ?? "") || comparerNaturel(a.titre, b.titre);
    });
    for (const g of gs) {
      g.personnes.sort(
        (a, b) => ORDRE.compare(a.nom ?? "", b.nom ?? "") || ORDRE.compare(a.prenom ?? "", b.prenom ?? ""),
      );
    }
    return gs;
  });

  let affichees = $derived(groupes.flatMap((g) => g.personnes));

  // --- La liste ne dessine que ce qui se voit ---------------------------------
  // Deux mille lignes, chacune avec sa photo, sa pastille et sa case : les
  // poser toutes dans la page coûtait plus que de les charger. Une ligne et
  // un titre de classe ont une hauteur fixe, la place de chacun se calcule ;
  // on ne dessine que ce qui est à l'écran, plus une marge pour le défilement.
  const H_TITRE = 36;
  const H_LIGNE = 48;
  const MARGE = 720;

  let defileur = $state(/** @type {HTMLDivElement|null} */ (null));
  let defilement = $state(lire("referentiel.defilement", 0));
  let hauteurVue = $state(800);
  $effect(() => ecrire("referentiel.defilement", defilement));

  let plan = $derived.by(() => {
    let y = 0;
    const blocs = [];
    for (const g of groupes) {
      const h = H_TITRE + g.personnes.length * H_LIGNE;
      blocs.push({ g, haut: y, h });
      y += h;
    }
    return { blocs, total: y };
  });

  let visibles = $derived.by(() => {
    const debut = defilement - MARGE;
    const fin = defilement + hauteurVue + MARGE;
    const r = [];
    for (const b of plan.blocs) {
      if (b.haut + b.h <= debut) continue;
      if (b.haut >= fin) break;
      const i0 = Math.max(0, Math.floor((debut - b.haut - H_TITRE) / H_LIGNE));
      const i1 = Math.min(b.g.personnes.length, Math.ceil((fin - b.haut - H_TITRE) / H_LIGNE));
      r.push({ ...b, i0, personnes: b.g.personnes.slice(i0, i1) });
    }
    return r;
  });

  // Revenir sur l'écran, ou sur l'onglet, retrouve la liste où on l'avait
  // laissée. Le défileur est neuf à chaque fois : on lui rend sa position,
  // puis on relit celle qu'il a vraiment prise — plus courte, la liste a pu
  // l'obliger à remonter.
  $effect(() => {
    const el = defileur;
    const total = plan.total;
    if (!el || !total) return;
    untrack(() => {
      if (Math.abs(el.scrollTop - defilement) > 1) el.scrollTop = defilement;
      defilement = el.scrollTop;
    });
  });

  // Changer de filtre repart du haut : la liste raccourcie laisserait sinon
  // l'écran au milieu de nulle part, loin du premier résultat.
  let premierFiltre = true;
  $effect(() => {
    recherche;
    filtreClasse;
    choix;
    anneeId;
    if (premierFiltre) {
      premierFiltre = false;
      return;
    }
    untrack(() => {
      defilement = 0;
      if (defileur) defileur.scrollTop = 0;
    });
  });

  let personneChoisie = $derived(
    selectionne == null ? null : (lignes.find((p) => p.id === selectionne) ?? parId.get(selectionne) ?? null),
  );

  // Personne choisie : la première de la liste, pour que la fiche ne reste
  // jamais vide quand il y a quelqu'un à montrer.
  $effect(() => {
    if (onglet !== "personnes" || !affichees.length) return;
    if (selectionne == null || !lignes.some((p) => p.id === selectionne)) {
      selectionne = affichees[0].id;
    }
  });

  // Taper une recherche choisit le premier résultat : Entrée ouvre alors
  // ce qu'on vient de chercher.
  let premiereRecherche = true;
  $effect(() => {
    recherche;
    if (premiereRecherche) {
      premiereRecherche = false;
      return;
    }
    untrack(() => {
      if (affichees.length) selectionne = affichees[0].id;
    });
  });

  /** Amène la ligne à l'écran, sans la glisser sous le titre de sa classe. */
  function montrer(id) {
    tick().then(() => {
      const el = defileur;
      if (!el) return;
      for (const b of plan.blocs) {
        const i = b.g.personnes.findIndex((p) => p.id === id);
        if (i < 0) continue;
        const haut = b.haut + H_TITRE + i * H_LIGNE;
        if (haut - H_TITRE < el.scrollTop) el.scrollTop = haut - H_TITRE;
        else if (haut + H_LIGNE > el.scrollTop + el.clientHeight) el.scrollTop = haut + H_LIGNE - el.clientHeight;
        // Sans attendre l'événement de défilement : la ligne doit être
        // dessinée dans ce tour-ci, pas au prochain rafraîchissement.
        defilement = el.scrollTop;
        return;
      }
    });
  }

  function deplacer(sens) {
    if (!affichees.length) return;
    const i = affichees.findIndex((p) => p.id === selectionne);
    const j = i < 0 ? 0 : Math.min(Math.max(i + sens, 0), affichees.length - 1);
    selectionne = affichees[j].id;
    montrer(selectionne);
  }

  // --- Les coches, pour agir sur plusieurs à la fois ------------------------
  function cocher(id, oui) {
    const s = new Set(coches);
    if (oui) s.add(id);
    else s.delete(id);
    coches = s;
  }

  function cocherGroupe(g, oui) {
    const s = new Set(coches);
    for (const p of g.personnes) {
      if (p.sans_compte) continue;
      if (oui) s.add(p.id);
      else s.delete(p.id);
    }
    coches = s;
  }

  let cochees = $derived(lignes.filter((p) => coches.has(p.id) && !p.sans_compte));

  async function exporterCochees() {
    const nom = `Liste_${libelleAnnee || "referentiel"}_${cochees.length}_personnes.csv`;
    await enregistrerFichierBase64(nom, texteEnBase64(csvDeClasse(cochees)), "text/csv");
  }

  // --- Venir d'une autre vue ----------------------------------------------------
  function choisirDepuisClasse(id) {
    const p = lignes.find((x) => x.id === id);
    recherche = "";
    filtreClasse = p?.type === "eleve" ? (p.classe ?? "") : "";
    selectionne = id;
    onglet = "personnes";
    montrer(id);
  }

  function filtrerDepuisManque({ classe, facette, valeur }) {
    recherche = "";
    filtreClasse = classe;
    choix = { [facette]: [valeur] };
    selectionne = null;
    onglet = "personnes";
  }

  // --- Corriger le nom ou le prénom -------------------------------------------
  // Charlemagne se trompe, ou il est en retard. La simulation montre d'abord
  // ce que ça entraîne — l'adresse calculée suit le prénom.
  let enRenommage = $state(/** @type {any} */ (null));
  let nomSaisi = $state("");
  let prenomSaisi = $state("");
  let apercuRenommage = $state(/** @type {any} */ (null));
  let enregistrement = $state(false);

  function ouvrirRenommage(p) {
    enRenommage = p;
    nomSaisi = p.nom ?? "";
    prenomSaisi = p.prenom ?? "";
    apercuRenommage = null;
  }

  async function simulerRenommage() {
    if (!enRenommage) return;
    enregistrement = true;
    try {
      apercuRenommage = await personnes.corrigerIdentite(enRenommage.id, {
        nom: nomSaisi.trim(), prenom: prenomSaisi.trim(), mode: "simulation",
      });
    } catch (e) {
      apercuRenommage = null;
      notify.erreur(libelle(e), { duree: 9000 });
    } finally {
      enregistrement = false;
    }
  }

  async function enregistrerRenommage() {
    if (!enRenommage) return;
    enregistrement = true;
    try {
      const r = await personnes.corrigerIdentite(enRenommage.id, {
        nom: nomSaisi.trim(), prenom: prenomSaisi.trim(), mode: "reel",
      });
      liste = await personnes.lister();
      notify.succes(
        r.changements.length
          ? `${r.prenom_apres} ${r.nom_apres} — ${r.changements.length} changement(s)`
          : "Rien à changer.",
      );
      for (const x of r.reste_a_faire) notify.info(x, { duree: 11000 });
      enRenommage = null;
    } catch (e) {
      notify.erreur(libelle(e), { duree: 9000 });
    } finally {
      enregistrement = false;
    }
  }

  // --- Figer l'adresse ------------------------------------------------------------
  // Pour les cas que le programme refuse de trancher seul : deux homonymes
  // qui viseraient la même adresse, une adresse historique hors convention.
  let enEdition = $state(/** @type {any} */ (null));
  let saisie = $state("");

  function ouvrirEdition(p) {
    enEdition = p;
    saisie = p.email_est_constate ? (p.email ?? "") : "";
  }

  async function enregistrerEmail() {
    if (!enEdition) return;
    enregistrement = true;
    try {
      const maj = await personnes.definirEmail(enEdition.id, saisie.trim());
      liste = liste.map((x) => (x.id === maj.id ? { ...x, ...maj } : x));
      notify.succes(saisie.trim() ? `Adresse figée : ${maj.email}` : `Adresse recalculée : ${maj.email}`);
      enEdition = null;
    } catch (e) {
      notify.erreur(libelle(e));
    } finally {
      enregistrement = false;
    }
  }

  // --- Le clavier -------------------------------------------------------------
  let modaleOuverte = $derived(!!enRenommage || !!enEdition || !!deplacement);

  function surTouche(e) {
    if (onglet !== "personnes" || modaleOuverte) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    const dansUnChamp =
      t instanceof HTMLElement &&
      (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
    const dansLaRecherche = t === champRecherche;
    if (dansUnChamp && !dansLaRecherche) return;

    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      deplacer(e.key === "ArrowDown" ? 1 : -1);
    } else if (e.key === "Enter") {
      if (selectionne != null && selectionne > 0) {
        e.preventDefault();
        onOuvrirFiche?.(selectionne);
      }
    } else if (dansLaRecherche) {
      if (e.key === "Escape") {
        recherche = "";
        champRecherche?.blur();
      }
    } else if (e.key === "/") {
      e.preventDefault();
      champRecherche?.focus();
    } else if (e.key === "c" || e.key === "C") {
      apercu?.copierAdresse();
    } else if (e.key === "m" || e.key === "M") {
      apercu?.montrerMotDePasse();
    }
  }

  const POINTS = {
    pret: "bg-vert-500",
    ecart: "bg-red-500",
    inconnu: "bg-stone-300 dark:bg-stone-600",
  };

  const HAUTEUR = "h-[calc(100vh-18rem)] min-h-[34rem]";
</script>

<svelte:window onkeydown={surTouche} />

<section class="flex flex-col gap-4">
  <EnTetePage
    icon={Users2}
    titre="Référentiel"
    description="Retrouver quelqu'un et agir sur lui, voir une classe, savoir ce qui manque. L'identité est créée à la première apparition et jamais supprimée : l'identifiant reste figé, y compris après un départ."
  >
    {#snippet actions()}
      <span class="text-sm text-stone-600 tabular-nums dark:text-stone-400">
        {#if actualisation || actualisationAnnee}
          <span class="mr-2 inline-flex items-center gap-1.5 text-xs text-stone-400 dark:text-stone-500" title="Ce qui s'affiche est la dernière lecture ; la nouvelle arrive.">
            <RefreshCw class="h-3 w-3 animate-spin" /> mise à jour
          </span>
        {/if}
        <b class="text-stone-900 dark:text-stone-100">{liste.length.toLocaleString("fr-FR")}</b> personnes
        {#if parAnnee && inscrites}
          · <b class="text-stone-900 dark:text-stone-100">{inscrites.toLocaleString("fr-FR")}</b> inscrites en {libelleAnnee}
        {/if}
      </span>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">{erreur}</p>
  {/if}

  <div class="flex items-end gap-6">
    <div class="min-w-0 flex-1">
      <Onglets
        bind:valeur={onglet}
        onglets={[
          { id: "personnes", label: "Personnes" },
          { id: "classes", label: "Par classe" },
          { id: "manque", label: "Ce qui manque" },
        ]}
      />
    </div>
    <label class="flex items-center gap-2 pb-2 text-sm">
      <span class="text-stone-500 dark:text-stone-400">Année</span>
      <select
        class="rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-sm font-semibold dark:border-stone-700 dark:bg-stone-900 dark:text-stone-200"
        bind:value={anneeId}
        aria-label="Année observée"
      >
        <option value={null}>Tout le référentiel</option>
        {#each listeAnnees as a (a.id)}
          <option value={a.id}>{a.libelle}</option>
        {/each}
      </select>
    </label>
  </div>

  {#if onglet === "personnes"}
    {#if chargement && !liste.length}
      <Squelette variante="ligne-tableau" nb={8} colonnes={3} />
    {:else if !liste.length}
      <EtatVide
        icon={Users2}
        titre="Référentiel vide"
        message="Charge d'abord tes comptes existants depuis l'onglet Amorçage KoXo, puis dépose un export Charlemagne dans Snapshots d'années."
      />
    {:else}
      <div class="grid {HAUTEUR} grid-cols-[210px_360px_minmax(0,1fr)] border-t border-stone-200 dark:border-stone-800">
        <!-- Les filtres, chacun avec ce qu'il ramènerait. -->
        <aside class="min-h-0 overflow-y-auto border-r border-stone-200 py-4 pr-5 dark:border-stone-800">
          <Facettes {facettes} bind:choix />
          {#if filtresActifs}
            <button
              type="button"
              class="mt-5 inline-flex items-center gap-1.5 text-xs font-semibold text-stone-500 hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-100"
              onclick={toutEffacer}
            >
              <RotateCcw class="h-3.5 w-3.5" /> Tout effacer
            </button>
          {/if}
        </aside>

        <!-- La liste, rangée par classe. -->
        <div class="flex min-h-0 flex-col border-r border-stone-200 dark:border-stone-800">
          <div class="space-y-2 px-4 pt-4 pb-2">
            <div class="relative">
              <Search class="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-stone-400" />
              <input
                bind:this={champRecherche}
                type="search"
                class="champ !rounded-full !py-1.5 !pr-10 !pl-9"
                placeholder="Nom, identifiant, badge, adresse"
                aria-label="Chercher une personne"
                bind:value={recherche}
              />
              <span class="absolute top-1/2 right-2.5 -translate-y-1/2"><Touche texte="/" /></span>
            </div>
            <div class="flex items-center gap-2">
              <select
                class="min-w-0 flex-1 rounded-lg border border-stone-300 bg-white px-2 py-1 text-[13px] dark:border-stone-700 dark:bg-stone-900 dark:text-stone-200"
                bind:value={filtreClasse}
                aria-label="Filtrer par classe"
              >
                <option value="">Toutes les classes</option>
                {#each classesDispo as c (c)}
                  <option value={c}>{c}</option>
                {/each}
              </select>
              <span class="shrink-0 text-xs tabular-nums text-stone-500 dark:text-stone-400">
                {filtrees.length.toLocaleString("fr-FR")} / {lignes.length.toLocaleString("fr-FR")}
              </span>
            </div>
          </div>

          <div
            bind:this={defileur}
            bind:clientHeight={hauteurVue}
            onscroll={() => (defilement = defileur?.scrollTop ?? 0)}
            class="min-h-0 flex-1 overflow-y-auto px-2 pb-3"
            role="listbox"
            aria-label="Personnes"
          >
            {#if chargementAnnee && !lignes.length}
              <p class="px-2 py-3 text-sm text-stone-500">Lecture de l'année…</p>
            {:else if !filtrees.length}
              <div class="px-2 py-6 text-sm text-stone-500 dark:text-stone-400">
                {#if raisons.length}
                  <p class="flex gap-2"><Info class="mt-0.5 h-4 w-4 shrink-0" />{raisons[0]}</p>
                {:else}
                  <p>Personne ne correspond. Retire un filtre, ou élargis la recherche.</p>
                {/if}
              </div>
            {:else}
              <!-- Toute la hauteur de la liste, pour que la barre de défilement
                   dise vrai ; dedans, seuls les blocs à l'écran. Le titre de
                   classe colle en haut de son bloc tant qu'on y est. -->
              <div class="relative" style="height: {plan.total}px">
              {#each visibles as b (b.g.cle)}
                {@const g = b.g}
                {@const tous = g.personnes.every((p) => p.sans_compte || coches.has(p.id))}
                <div class="absolute inset-x-0" style="top: {b.haut}px; height: {b.h}px">
                <div class="group/g sticky top-0 z-10 flex h-9 items-end gap-2 bg-stone-50 px-2.5 pb-1.5 dark:bg-stone-950">
                  <input
                    type="checkbox"
                    class="h-3.5 w-3.5 cursor-pointer accent-emerald-600 {coches.size ? '' : 'opacity-0 group-hover/g:opacity-100 focus:opacity-100'}"
                    aria-label="Cocher {g.titre}"
                    checked={tous && coches.size > 0}
                    onchange={(e) => cocherGroupe(g, e.currentTarget.checked)}
                  />
                  <span class="libelle-champ flex-1 truncate">
                    {g.titre}{#if g.site}<span class="font-medium text-stone-400"> · {g.site}</span>{/if}
                  </span>
                  <span class="text-xs tabular-nums text-stone-500">{g.personnes.length}</span>
                </div>
                {#each b.personnes as p, k (p.id)}
                  {@const choisi = p.id === selectionne}
                  {@const e = etatDe(p, verdicts)}
                  <div
                    data-ligne={p.id}
                    style="top: {H_TITRE + (b.i0 + k) * H_LIGNE}px"
                    class="group absolute inset-x-0 flex h-12 items-center gap-2.5 rounded-xl px-2.5 transition-colors
                           {choisi
                      ? 'bg-emerald-100/80 dark:bg-emerald-500/15'
                      : 'hover:bg-stone-100 dark:hover:bg-stone-800/60'}"
                  >
                    <input
                      type="checkbox"
                      class="h-3.5 w-3.5 shrink-0 cursor-pointer accent-emerald-600
                             {coches.size || coches.has(p.id) ? '' : 'opacity-0 group-hover:opacity-100 focus:opacity-100'}"
                      aria-label="Cocher {p.prenom} {p.nom}"
                      disabled={p.sans_compte}
                      checked={coches.has(p.id)}
                      onchange={(ev) => cocher(p.id, ev.currentTarget.checked)}
                    />
                    <button
                      type="button"
                      role="option"
                      aria-selected={choisi}
                      class="flex min-w-0 flex-1 items-center gap-3 text-left"
                      onclick={() => (selectionne = p.id)}
                      ondblclick={() => p.id > 0 && onOuvrirFiche?.(p.id)}
                    >
                      <Avatar personneId={p.sans_compte ? null : p.id} nom={p.nom} prenom={p.prenom} taille={32} />
                      <span class="min-w-0 flex-1">
                        <span class="block truncate text-sm {choisi ? 'font-bold' : 'font-semibold'} text-stone-900 dark:text-stone-100">
                          {p.prenom} <span class="uppercase">{p.nom}</span>
                        </span>
                        <span class="block truncate font-mono text-xs text-stone-500 dark:text-stone-400">
                          {p.login_constate ?? p.login ?? (p.sans_compte ? "hors référentiel" : "")}
                        </span>
                      </span>
                      {#if p.mouvement === "entrant"}
                        <span class="text-[10px] font-bold tracking-wide text-emerald-700 uppercase dark:text-emerald-400">nouveau</span>
                      {/if}
                      <span class="h-2.5 w-2.5 shrink-0 rounded-full {POINTS[e.etat]}" title={e.texte}></span>
                    </button>
                  </div>
                {/each}
                </div>
              {/each}
              </div>
            {/if}
          </div>

          {#if cochees.length}
            <div class="flex flex-wrap items-center gap-2 border-t border-stone-200 bg-stone-900 px-3 py-2.5 text-white dark:border-stone-800 dark:bg-stone-100 dark:text-stone-900">
              <span class="text-sm font-bold">{cochees.length} cochée{cochees.length > 1 ? "s" : ""}</span>
              <span class="flex-1"></span>
              <button
                type="button"
                class="inline-flex items-center gap-1.5 rounded-full border border-white/30 px-3 py-1 text-xs font-semibold hover:bg-white/10 dark:border-stone-900/30 dark:hover:bg-stone-900/10"
                onclick={() => (deplacement = cochees)}
              >
                <FolderTree class="h-3.5 w-3.5" /> Déplacer dans Google
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1.5 rounded-full border border-white/30 px-3 py-1 text-xs font-semibold hover:bg-white/10 dark:border-stone-900/30 dark:hover:bg-stone-900/10"
                onclick={exporterCochees}
              >
                <Download class="h-3.5 w-3.5" /> Liste
              </button>
              <button type="button" class="text-xs font-semibold opacity-70 hover:opacity-100" onclick={() => (coches = new Set())}>
                Décocher
              </button>
            </div>
          {/if}
        </div>

        <!-- La fiche, à côté de la liste. -->
        <div class="min-h-0 min-w-0">
          {#if personneChoisie}
            <ApercuPersonne
              bind:this={apercu}
              personne={personneChoisie}
              verdict={verdicts[personneChoisie.id] ?? null}
              {anneeId}
              {onOuvrirFiche}
              onDeplacer={(p) => (deplacement = [p])}
              onRenommer={ouvrirRenommage}
              onFigerAdresse={ouvrirEdition}
            />
          {:else}
            <div class="p-8">
              <EtatVide icon={Users2} titre="Personne à montrer" message="Choisis quelqu'un dans la liste, ou retire un filtre." />
            </div>
          {/if}
        </div>
      </div>
    {/if}
  {:else if onglet === "classes"}
    {#if !parAnnee}
      <EtatVide
        icon={Info}
        titre="Choisis une année"
        message="Les classes changent chaque année : sans année, un élève parti resterait rangé dans sa dernière classe."
      />
    {:else}
      <div class={HAUTEUR}>
        <ParClasse
          {lignes}
          {verdicts}
          {anneeId}
          {libelleAnnee}
          bind:classe={classeOuverte}
          onChoisir={choisirDepuisClasse}
          {onNaviguer}
        />
      </div>
    {/if}
  {:else}
    <div class={HAUTEUR}>
      <CeQuiManque
        anneeId={parAnnee ? anneeId : (listeAnnees.at(-1)?.id ?? null)}
        onFiltrer={filtrerDepuisManque}
        {onNaviguer}
      />
    </div>
  {/if}
</section>

{#if enRenommage}
  <Modale titre="Nom et prénom — {enRenommage.prenom} {enRenommage.nom}" onFermer={() => (enRenommage = null)}>
    <div class="space-y-3">
      <p class="text-sm text-stone-600 dark:text-stone-300">
        Le référentiel se remplit par ingestion, et Charlemagne fait foi. Il
        se trompe parfois, ou il est en retard. Corriger ici fait suivre les
        exports — et l'adresse calculée, si elle n'a pas été figée.
      </p>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="libelle-champ" for="champ-nom">Nom</label>
          <input id="champ-nom" class="champ" bind:value={nomSaisi} oninput={() => (apercuRenommage = null)} />
        </div>
        <div>
          <label class="libelle-champ" for="champ-prenom">Prénom</label>
          <input id="champ-prenom" class="champ" bind:value={prenomSaisi} oninput={() => (apercuRenommage = null)} />
        </div>
      </div>
      {#if apercuRenommage}
        {#if apercuRenommage.changements.length === 0}
          <p class="text-sm text-stone-500 dark:text-stone-400">Rien ne change.</p>
        {:else}
          <ul class="space-y-1 rounded-lg border border-stone-200 bg-stone-50 p-2 text-sm dark:border-stone-700 dark:bg-stone-800">
            {#each apercuRenommage.changements as c}<li>{c}</li>{/each}
          </ul>
        {/if}
        {#each apercuRenommage.reste_a_faire as x}
          <p class="rounded-lg border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">{x}</p>
        {/each}
      {/if}
      <p class="text-xs text-stone-500 dark:text-stone-400">
        L'identifiant <span class="font-mono">{enRenommage.login_constate ?? enRenommage.login}</span>
        ne bouge pas : c'est celui que KoXo détient, et le changer ferait
        renommer le compte de l'annuaire.
      </p>
    </div>
    {#snippet actions()}
      <Bouton onclick={() => (enRenommage = null)}>Annuler</Bouton>
      <Bouton occupe={enregistrement} onclick={simulerRenommage}>Voir ce que ça change</Bouton>
      <Bouton
        variante="primary"
        occupe={enregistrement}
        disabled={!apercuRenommage || apercuRenommage.changements.length === 0}
        onclick={enregistrerRenommage}
      >
        Corriger
      </Bouton>
    {/snippet}
  </Modale>
{/if}

{#if enEdition}
  <Modale titre="Adresse mail — {enEdition.prenom} {enEdition.nom}" onFermer={() => (enEdition = null)}>
    <div class="space-y-3">
      <p class="text-sm text-stone-600 dark:text-stone-300">
        Laisse vide pour utiliser l'adresse calculée à partir du nom et du
        prénom. Saisis une adresse pour la figer — c'est ce qu'il faut faire
        quand un homonyme possède déjà l'adresse calculée.
      </p>
      <div>
        <label class="libelle-champ" for="champ-email">Adresse</label>
        <input
          id="champ-email"
          type="email"
          class="champ font-mono"
          placeholder={enEdition.email ?? "prenom.nom@domaine"}
          bind:value={saisie}
          onkeydown={(e) => e.key === "Enter" && enregistrerEmail()}
        />
      </div>
      <p class="text-xs text-stone-500 dark:text-stone-400">
        Identifiant réseau : <span class="font-mono">{enEdition.login}</span> — il
        reste figé et n'a pas à correspondre à l'adresse.
      </p>
    </div>
    {#snippet actions()}
      <Bouton onclick={() => (enEdition = null)}>Annuler</Bouton>
      <Bouton variante="primary" occupe={enregistrement} onclick={enregistrerEmail}>Enregistrer</Bouton>
    {/snippet}
  </Modale>
{/if}

{#if deplacement?.length}
  <DeplacementGoogle
    personnes={deplacement}
    anneeId={parAnnee ? anneeId : null}
    onFermer={() => (deplacement = null)}
    onApplique={rafraichir}
  />
{/if}
