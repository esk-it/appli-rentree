<script>
  import HelpCircle from "@lucide/svelte/icons/help-circle";
  import ChevronDown from "@lucide/svelte/icons/chevron-down";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import Calendar from "@lucide/svelte/icons/calendar";
  import FileSpreadsheet from "@lucide/svelte/icons/file-spreadsheet";
  import Database from "@lucide/svelte/icons/database";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import GitBranch from "@lucide/svelte/icons/git-branch";

  let sectionsOuvertes = $state(/** @type {Record<string, boolean>} */ ({}));

  const SECTIONS = [
    {
      id: "demarrage",
      titre: "Démarrage rapide (5 minutes)",
      icone: Sparkles,
      contenu: `
        <ol class="list-decimal space-y-2 pl-5 text-sm">
          <li>Dans <strong>Snapshots d'années</strong>, importe ton dernier export Charlemagne (HTM ou XLSX) avec un libellé comme "2025-2026"</li>
          <li>Optionnel : importe aussi un export adultes via <strong>Personnel / Adultes</strong> → Importer</li>
          <li>Vérifie dans <strong>Statistiques</strong> que les nombres correspondent à ce que tu attends</li>
          <li>Va sur le <strong>Tableau de bord</strong> → bouton <strong>Générer tout (ZIP)</strong></li>
          <li>Télécharge le ZIP — il contient les fichiers pour KoXo, PMB, CardStudio, SmartAir et Google (élèves + adultes)</li>
          <li>Importe chaque fichier dans son logiciel cible (procédure détaillée sur chaque page d'export)</li>
        </ol>
        <p class="mt-3 rounded-lg bg-emerald-50 p-2 text-xs text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300">
          💡 Raccourci : <kbd class="rounded border px-1">Ctrl+K</kbd> ouvre la recherche globale cross-snapshot
          depuis n'importe quelle page.
        </p>
      `,
    },
    {
      id: "workflow_rentree",
      titre: "Workflow recommandé pour la rentrée",
      icone: Calendar,
      contenu: `
        <p class="mb-3 text-sm">Le workflow typique en début d'année scolaire :</p>
        <ol class="list-decimal space-y-2 pl-5 text-sm">
          <li><strong>Juin–juillet</strong> : récupère l'export Charlemagne de l'<em>année qui se termine</em>, importe-le si pas déjà fait (libellé "AAAA-AAAA")</li>
          <li><strong>Fin août</strong> : génère l'export Charlemagne <em>de la rentrée</em> (basculement des classes côté Charlemagne)</li>
          <li><strong>Avant la rentrée</strong> : importe ce nouvel export comme nouveau snapshot ("2026-2027" par ex.)</li>
          <li>Dans <strong>Comparaison N vs N-1</strong>, vérifie que les entrants/restants/sortants sont cohérents</li>
          <li>Dans le <strong>Tableau de bord</strong>, choisis N et N-1, dépose optionnellement l'export SmartAir précédent, puis <strong>Générer tout</strong></li>
          <li>Importe les fichiers dans les logiciels métier — l'ordre conseillé est dans le README du ZIP</li>
        </ol>
      `,
    },
    {
      id: "snapshots",
      titre: "Snapshots d'années",
      icone: Database,
      contenu: `
        <p class="text-sm">Un <strong>snapshot</strong> est un export Charlemagne ingéré pour une année scolaire donnée. L'app conserve plusieurs snapshots pour permettre la comparaison N vs N-1.</p>
        <p class="mt-2 text-sm">Les <strong>établissements</strong> sont détectés automatiquement à partir des codes Charlemagne (02-COL = SU, 03-LY = NDK_LY, 04-LP = NDK_LP). Un nouveau code crée un nouvel établissement avec le nom long fourni par Charlemagne.</p>
        <p class="mt-2 text-sm">L'option <strong>"Remplacer si existe"</strong> permet de réimporter un snapshot sans créer de doublons (utile si tu veux corriger un import partiel).</p>
      `,
    },
    {
      id: "comparaison",
      titre: "Comparaison N vs N-1",
      icone: GitBranch,
      contenu: `
        <p class="text-sm">Le matching se fait sur le <strong>numéro de badge Charlemagne</strong>, qui est stable sur toute la scolarité d'un élève dans l'ensemble. Si un élève n'a pas de badge (cas rare), on retombe sur <code>nom + prénom</code> normalisés.</p>
        <p class="mt-2 text-sm">Pour chaque élève présent dans les deux snapshots, on détecte les <strong>changements par champ</strong> (classe, niveau, régime, établissement, nom, prénom). Affichage type : <code>5EME1 → 4EME2</code>.</p>
      `,
    },
    {
      id: "koxo",
      titre: "Export KoXo (comptes AD)",
      icone: FileSpreadsheet,
      contenu: `
        <p class="text-sm">Génère jusqu'à <strong>6 CSV</strong> pour KoXo (2 groupes SU/NDK × 3 types Tous/Nouveaux/Anciens).</p>
        <p class="mt-2 text-sm font-medium">Règles métier appliquées</p>
        <ul class="list-disc space-y-1 pl-5 text-sm">
          <li><strong>Login</strong> : première lettre prénom + nom (sans accents, sans apostrophes, max 10 caractères) → "Tifenn ARGOUARC'H" devient <code>targouarch</code></li>
          <li><strong>Email</strong> : <code>prenom.nom@</code>domaine (configurable dans Paramètres), espaces dans le nom remplacés par des points, doubles tirets compactés</li>
          <li><strong>Mot de passe</strong> : généré uniquement pour les Nouveaux. Format type <code>Sateku68</code> (6 lettres alternées consonne/voyelle + 2 chiffres)</li>
          <li><strong>ID unique</strong> : numéro de badge Charlemagne</li>
          <li><strong>Groupe secondaire</strong> : code classe Charlemagne (31, 4J, 1_BPAGORA…)</li>
        </ul>
        <p class="mt-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">
          <strong>Important</strong> : note ou sauvegarde le fichier "Nouveaux" pour distribuer les mots de passe aux élèves au premier accès.
        </p>
      `,
    },
    {
      id: "pmb",
      titre: "Export PMB (CDI)",
      icone: FileSpreadsheet,
      contenu: `
        <p class="text-sm">Génère <strong>2 CSV</strong> (un par instance PMB : SU et NDK), format séparateur point-virgule.</p>
        <p class="mt-2 text-sm">PMB n'a pas la notion de Nouveaux/Anciens — l'archivage des anciens emprunteurs reste manuel côté PMB.</p>
        <p class="mt-2 text-sm">URLs des instances : <code>https://sainte-ursule.basecdi.fr</code> et <code>https://lycee-ndkreisker.basecdi.fr</code>.</p>
      `,
    },
    {
      id: "cardstudio",
      titre: "Export CardStudio (impression badges)",
      icone: FileSpreadsheet,
      contenu: `
        <p class="text-sm">Génère <strong>2 XLSX</strong> (groupes KREISKER pour NDK et SAINTE-URSULE pour SU) avec 13 colonnes calquées sur l'historique ESK.</p>
        <p class="mt-2 text-sm">Le chemin UNC vers la photo est préservé : CardStudio sait suivre le chemin réseau pour retrouver l'image au moment de l'impression.</p>
        <p class="mt-2 text-sm">La colonne <strong>Chambres</strong> est vide pour l'instant (gestion d'attribution des chambres pas encore intégrée). À renseigner à la main dans Excel si besoin avant impression.</p>
      `,
    },
    {
      id: "smartair",
      titre: "Export SmartAir (contrôle d'accès)",
      icone: FileSpreadsheet,
      contenu: `
        <p class="text-sm">Génère <strong>1 CSV</strong> à 28 colonnes pour SmartAir (JPM). Format séparateur point-virgule.</p>
        <p class="mt-2 text-sm font-medium">Colonne Op</p>
        <ul class="list-disc space-y-1 pl-5 text-sm">
          <li><code>a</code> : ajouter (nouveau badge)</li>
          <li><code>m</code> : modifier (changement de classe/régime)</li>
          <li><code>b</code> : supprimer (départ de l'ensemble)</li>
        </ul>
        <p class="mt-2 text-sm font-medium">CardId (identifiant hex de la carte physique)</p>
        <p class="text-sm">Si tu dépose un <strong>export SmartAir précédent</strong>, l'app récupère les CardId existants et les place dans le nouveau fichier. Sinon, la colonne reste vide et il faudra scanner chaque badge avec le lecteur de SmartAir au premier accès.</p>
      `,
    },
    {
      id: "google",
      titre: "Export Google Workspace",
      icone: FileSpreadsheet,
      contenu: `
        <p class="text-sm">Génère <strong>1 ou 2 CSV</strong> au format bulk-import Google Admin :</p>
        <ul class="list-disc space-y-1 pl-5 text-sm">
          <li><strong>Tous</strong> : tous les élèves, sans MDP (utile pour vérifier les Org Units en dry-run)</li>
          <li><strong>Nouveaux</strong> : entrants avec MDP générés, à créer (seulement si N-1 fournie)</li>
        </ul>
        <p class="mt-2 text-sm">L'<strong>Org Unit Path</strong> suit un template configurable dans Paramètres. Par défaut : <code>/{"{site}/{site}{annee_compact}/{classe}"}</code>, ce qui donne par exemple <code>/SU/SU2026/31</code>.</p>
      `,
    },
    {
      id: "parametres",
      titre: "Paramètres configurables",
      icone: HelpCircle,
      contenu: `
        <p class="text-sm">Les paramètres sont stockés en base SQLite et appliqués immédiatement à toute génération suivante.</p>
        <p class="mt-2 text-sm font-medium">Paramètres disponibles</p>
        <ul class="list-disc space-y-1 pl-5 text-sm">
          <li><code>email.domaine</code> : domaine utilisé pour les emails</li>
          <li><code>google.ou_template</code> : pattern de l'Org Unit Path Google. Variables : <code>{"{site}"}</code>, <code>{"{annee_compact}"}</code>, <code>{"{classe}"}</code></li>
          <li><code>koxo.login_longueur_max</code> : taille max du login KoXo</li>
          <li><code>mdp.longueur_lettres</code> + <code>mdp.nb_chiffres</code> : structure des mots de passe générés</li>
        </ul>
      `,
    },
    {
      id: "adultes",
      titre: "Personnel / Adultes (profs, AESH, surveillants)",
      icone: FileSpreadsheet,
      contenu: `
        <p class="text-sm">Pipeline parallèle à celui des élèves. Import d'un export Charlemagne adultes
        (auto-détection du format selon la présence de colonnes fonction/civilité/discipline).</p>
        <p class="mt-2 text-sm">Génère ses propres CSV :</p>
        <ul class="list-disc space-y-1 pl-5 text-sm">
          <li><strong>KoXo</strong> : groupe primaire "Professeurs", groupe secondaire = fonction</li>
          <li><strong>Google Workspace</strong> : Org Unit dédié <code>/Personnel/{"{fonction}"}</code></li>
        </ul>
        <p class="mt-2 text-sm">Inclus dans le ZIP "Tout générer" si des adultes sont importés.</p>
      `,
    },
    {
      id: "chambres",
      titre: "Chambres internat",
      icone: FileSpreadsheet,
      contenu: `
        <p class="text-sm">Déclare les chambres physiques (numéro, bâtiment, étage, capacité) et affecte les
        élèves internes (régime "P"). La colonne <em>Chambres</em> du fichier CardStudio est ensuite
        renseignée automatiquement à partir de ces affectations.</p>
        <p class="mt-2 text-sm">L'app indique les chambres en surcapacité (en rouge) et liste les internes
        non encore affectés pour chaque chambre sélectionnée.</p>
      `,
    },
    {
      id: "recherche",
      titre: "Recherche globale (Ctrl+K)",
      icone: HelpCircle,
      contenu: `
        <p class="text-sm">Raccourci <kbd class="rounded border border-stone-300 px-1">Ctrl</kbd> +
        <kbd class="rounded border border-stone-300 px-1">K</kbd> depuis n'importe quelle page.</p>
        <p class="mt-2 text-sm">Cherche simultanément dans tous les snapshots, élèves et personnel, par
        nom, prénom, numéro de badge ou numéro de personnel. Regroupe les apparitions multi-année
        pour voir l'historique d'une personne.</p>
      `,
    },
    {
      id: "historique",
      titre: "Historique des générations",
      icone: HelpCircle,
      contenu: `
        <p class="text-sm">Chaque génération d'export (depuis n'importe quelle page) est enregistrée
        en base avec sa date, sa cible, l'année N et N-1, le nombre de fichiers et de lignes produites.</p>
        <p class="mt-2 text-sm">Pratique pour savoir ce qui a déjà été fait dans la préparation
        de la rentrée et éviter les doubles imports côté logiciels métier.</p>
      `,
    },
    {
      id: "mode-sombre",
      titre: "Mode sombre",
      icone: HelpCircle,
      contenu: `
        <p class="text-sm">Bouton soleil/lune dans le coin haut-droit de la sidebar.
        Suit la préférence système au premier lancement, puis mémorise ton choix
        en local pour les lancements suivants.</p>
      `,
    },
    {
      id: "depannage",
      titre: "Dépannage / FAQ",
      icone: HelpCircle,
      contenu: `
        <dl class="space-y-3 text-sm">
          <div>
            <dt class="font-medium text-stone-900">L'app ne démarre plus / écran "Backend hors-ligne"</dt>
            <dd class="mt-1 text-stone-600">Vérifie qu'aucun autre processus n'utilise le port 8020. Si oui, ferme-le. Si tu vois plusieurs <code>appli-rentree-backend.exe</code> dans le Task Manager, tue-les avec <code>taskkill /F /IM appli-rentree-backend.exe</code> et relance l'app.</dd>
          </div>
          <div>
            <dt class="font-medium text-stone-900">La mise à jour n'apparaît pas</dt>
            <dd class="mt-1 text-stone-600">Ferme et relance l'app : la vérification se fait au démarrage. Tu peux aussi télécharger l'installeur directement depuis <a href="https://github.com/esk-it/appli-rentree/releases" target="_blank" class="text-emerald-700 underline">GitHub Releases</a>.</dd>
          </div>
          <div>
            <dt class="font-medium text-stone-900">Un élève n'a pas de badge</dt>
            <dd class="mt-1 text-stone-600">Il est quand même importé et géré (matching par nom+prénom en fallback). Pour les exports qui ont besoin du badge (CardStudio, SmartAir, KoXo ID unique), la colonne sera vide pour cet élève.</dd>
          </div>
          <div>
            <dt class="font-medium text-stone-900">Le format d'un export n'est pas accepté par le logiciel cible</dt>
            <dd class="mt-1 text-stone-600">Le format peut différer selon la version du logiciel cible. Note les colonnes manquantes/en trop et signale-le pour qu'on ajuste l'exporter dans une prochaine version.</dd>
          </div>
        </dl>
      `,
    },
  ];

  function toggle(id) {
    sectionsOuvertes = {
      ...sectionsOuvertes,
      [id]: !sectionsOuvertes[id],
    };
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900">Aide</h1>
    <p class="mt-1 text-sm text-stone-600">
      Documentation de référence de l'application — workflow de rentrée,
      détail de chaque export, paramètres, dépannage.
    </p>
  </header>

  <div class="space-y-2">
    {#each SECTIONS as s (s.id)}
      {@const ouvert = sectionsOuvertes[s.id]}
      <div class="card overflow-hidden">
        <button
          class="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-stone-50"
          onclick={() => toggle(s.id)}
        >
          <s.icone class="h-4 w-4 text-emerald-700" />
          <span class="flex-1 text-sm font-semibold text-stone-900">{s.titre}</span>
          {#if ouvert}
            <ChevronDown class="h-4 w-4 text-stone-400" />
          {:else}
            <ChevronRight class="h-4 w-4 text-stone-400" />
          {/if}
        </button>
        {#if ouvert}
          <div class="border-t border-stone-100 px-4 py-3 text-stone-700">
            {@html s.contenu}
          </div>
        {/if}
      </div>
    {/each}
  </div>

  <div class="card border-emerald-200 bg-emerald-50/30 p-4 text-sm dark:border-emerald-800 dark:bg-emerald-900/20">
    <p class="font-medium text-emerald-900 dark:text-emerald-200">À propos</p>
    <p class="mt-1 text-stone-700 dark:text-stone-300">
      Appli Rentrée est une application interne de l'Ensemble Scolaire du Kreisker (ESK).
      Code source : <a
        href="https://github.com/esk-it/appli-rentree"
        target="_blank"
        rel="noopener"
        class="text-emerald-700 underline dark:text-emerald-400">esk-it/appli-rentree</a
      >. Mises à jour automatiques via la bannière en haut de la fenêtre.
    </p>
    <p class="mt-2 text-xs text-stone-500 dark:text-stone-400">
      Backend FastAPI + SQLite · Frontend Svelte 5 + Tailwind 4 · Shell Tauri 2 · 51 tests automatisés
    </p>
  </div>
</section>
