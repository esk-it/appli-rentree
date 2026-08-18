<script>
  import HelpCircle from "@lucide/svelte/icons/help-circle";
  import BookOpen from "@lucide/svelte/icons/book-open";
  import GitCompareArrows from "@lucide/svelte/icons/git-compare-arrows";
  import Scale from "@lucide/svelte/icons/scale";
  import Lock from "@lucide/svelte/icons/lock";
  import Rocket from "@lucide/svelte/icons/rocket";
  import Zap from "@lucide/svelte/icons/zap";
  import FileDown from "@lucide/svelte/icons/file-down";
  import Activity from "@lucide/svelte/icons/activity";
  import UserPlus from "@lucide/svelte/icons/user-plus";

  const sections = [
    { id: "flux", label: "Flux global", icon: BookOpen },
    { id: "amorcage", label: "Amorçage", icon: Rocket },
    { id: "ingestion", label: "Ingestion", icon: BookOpen },
    { id: "seaux", label: "Les 5 seaux", icon: GitCompareArrows },
    { id: "nouveaux", label: "Nouveaux arrivants", icon: UserPlus },
    { id: "arbitrage", label: "Arbitrage", icon: Scale },
    { id: "simulation", label: "Simulation", icon: Zap },
    { id: "exports", label: "Exports", icon: FileDown },
    { id: "suivi", label: "Suivi / purge", icon: Activity },
    { id: "securite", label: "Sécurité", icon: Lock },
    { id: "faq", label: "FAQ", icon: HelpCircle },
  ];

  let sectionActive = $state("flux");
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">Aide</h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Documentation intégrée. Sélectionne un sujet dans le sommaire.
    </p>
  </header>

  <div class="grid grid-cols-1 gap-4 md:grid-cols-[220px_1fr]">
    <!-- Sommaire -->
    <nav class="card p-2 h-fit space-y-0.5">
      {#each sections as s (s.id)}
        <button
          class="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-sm transition
                 {sectionActive === s.id ? 'bg-emerald-100 text-emerald-800 font-medium dark:bg-emerald-900/40 dark:text-emerald-300' : 'text-stone-600 hover:bg-stone-50 dark:text-stone-400 dark:hover:bg-stone-800'}"
          onclick={() => (sectionActive = s.id)}
        >
          <s.icon class="h-4 w-4" />
          <span>{s.label}</span>
        </button>
      {/each}
    </nav>

    <!-- Contenu -->
    <div class="card p-6 prose prose-stone dark:prose-invert max-w-none text-sm leading-relaxed">
      {#if sectionActive === "flux"}
        <h2>Flux global</h2>
        <p>Le programme suit un pipeline strict :</p>
        <ol>
          <li><strong>Amorçage</strong> — chargement du référentiel depuis les comptes KoXo
            existants. À faire une fois, avant tout le reste.</li>
          <li><strong>Ingestion Charlemagne</strong> — dépôt d'un export élèves ou adultes.
            Rapproche par ID Charlemagne, met à jour les Personnes, crée les Snapshots.</li>
          <li><strong>Réconciliation</strong> — compare deux années et classe chaque
            personne dans un des 5 seaux.</li>
          <li><strong>Arbitrage</strong> — tranche manuellement les cas ambigus.</li>
          <li><strong>Simulation</strong> — rapport transverse de ce qui sera fait.</li>
          <li><strong>Exports</strong> — génération des CSV/XLSX pour KoXo, Google, PMB,
            JPM, CardStudio.</li>
          <li><strong>Boucle KoXo → Google</strong> — récupération des MDP KoXo pour
            enrichir le CSV Google.</li>
        </ol>

      {:else if sectionActive === "nouveaux"}
        <h2>Nouveaux arrivants</h2>
        <p>
          La liste des personnes pour lesquelles un compte reste à créer, faite
          pour être <strong>imprimée et relue par un collègue</strong> avant de
          générer quoi que ce soit. À ne pas confondre avec l'export
          « Nouveaux » de l'onglet Exports, qui produit un fichier destiné à
          KoXo ou Google, avec des colonnes techniques.
        </p>

        <h3>Comment un arrivant est reconnu</h3>
        <p>
          Si <strong>deux années</strong> ont été ingérées, la comparaison
          tranche : est arrivant celui qui n'était pas là l'an dernier.
        </p>
        <p>
          Sinon — c'est le cas la première année — le programme croise deux
          signaux indépendants :
        </p>
        <ul>
          <li><strong>aucun compte constaté</strong> : personne ne lui a jamais
            ouvert d'adresse ;</li>
          <li><strong>aucune classe l'an dernier</strong> selon Charlemagne.</li>
        </ul>
        <p>
          Quand les deux concordent, la personne est marquée
          <strong>Nouveau</strong>. Quand ils se contredisent, elle est marquée
          <strong>À vérifier</strong> avec le motif — un élève qui poursuit sa
          scolarité sans compte, ou un élève réinscrit après une absence. Ce
          sont précisément les cas à faire confirmer par un collègue, donc ils
          restent sur la liste plutôt que d'être tranchés par une règle.
        </p>

        <h3>Sortir la liste</h3>
        <ul>
          <li><strong>Imprimer</strong> — met en page sans la navigation ni les
            filtres, une classe par bloc, avec une ligne de signature en bas.</li>
          <li><strong>Export Excel</strong> — CSV point-virgule avec accents,
            qui s'ouvre directement en colonnes dans Excel.</li>
        </ul>

      {:else if sectionActive === "amorcage"}
        <h2>Amorçage</h2>
        <p>
          Chargement du référentiel depuis des exports <strong>KoXo existants</strong>.
          Vital pour préserver les logins déjà attribués.
        </p>
        <p>
          Sans amorçage préalable, la première ingestion Charlemagne créera des Personnes
          avec des logins fraîchement calculés — qui peuvent différer des logins réels
          côté KoXo. L'amorçage évite ce piège.
        </p>
        <p><strong>Que faire :</strong></p>
        <ol>
          <li>Récupérer un export KoXo par site + type (élèves NDK, élèves SU, adultes)</li>
          <li>Onglet Amorçage KoXo → choix Site + Type + Upload CSV</li>
          <li>Simuler d'abord, puis Amorcer (réel)</li>
        </ol>
        <p>Idempotent : rejouer le même fichier ne crée aucun doublon.</p>

      {:else if sectionActive === "ingestion"}
        <h2>Ingestion Charlemagne</h2>
        <p>
          Charge un export Charlemagne au format HTM ou XLSX. Le programme
          rapproche par clé pivot <code>(type, id_charlemagne)</code> et crée un
          Snapshot daté par personne.
        </p>
        <p><strong>Modes :</strong></p>
        <ul>
          <li><strong>Simulation</strong> — évalue et produit le rapport, sans commit.</li>
          <li><strong>Réel</strong> — commit. Bloqué si des classes ne sont pas dans la
            Table de correspondance.</li>
        </ul>

      {:else if sectionActive === "seaux"}
        <h2>Les 5 seaux de la réconciliation</h2>
        <table>
          <thead><tr><th>Seau</th><th>Définition</th><th>Traitement</th></tr></thead>
          <tbody>
            <tr><td><strong>Nouveau</strong></td><td>Absent de l'année source, présent cible</td><td>Création de compte</td></tr>
            <tr><td><strong>Identique</strong></td><td>Aucun attribut changé</td><td>Aucune action</td></tr>
            <tr><td><strong>Modifié</strong></td><td>Attributs changés (classe, régime…)</td><td>Mise à jour</td></tr>
            <tr><td><strong>Sortant</strong></td><td>Présent source, absent cible</td><td>Politique de sortie</td></tr>
            <tr><td><strong>Ambigu</strong></td><td>Rapprochement incertain</td><td>Arbitrage humain</td></tr>
          </tbody>
        </table>

      {:else if sectionActive === "arbitrage"}
        <h2>Arbitrage</h2>
        <p>
          Le programme <strong>refuse de trancher lui-même</strong> les cas ambigus :
          collisions de login, homonymies. Il les présente et attend la décision humaine.
        </p>
        <p>
          Chaque décision est <strong>mémorisée définitivement</strong> via une clé
          déterministe (<code>cle_cas</code>) — elle ne sera plus jamais redemandée
          les années suivantes.
        </p>

      {:else if sectionActive === "simulation"}
        <h2>Simulation transverse</h2>
        <p>
          Vue agrégée de ce qui sera fait par tous les modules cibles (KoXo, Google)
          pour un couple d'années. Compte les créations, modifications, sortants par
          site et par cible. Bloque si des arbitrages sont en attente.
        </p>
        <p>C'est le point de validation avant d'aller générer les CSV.</p>

      {:else if sectionActive === "exports"}
        <h2>Exports vers les cibles</h2>
        <p>Cinq cibles supportées, par site et par catégorie (Tous/Nouveaux/Anciens) :</p>
        <ul>
          <li><strong>KoXo</strong> — CSV cp1252, 10 colonnes. MDP vide (KoXo génère).</li>
          <li><strong>Google Workspace</strong> — CSV UTF-8 BOM, 40 colonnes bulk-import.
            Password rempli via boucle KoXo→Google.</li>
          <li><strong>PMB</strong> — CSV ;-séparateur pour l'import bibliothèque CDI.</li>
          <li><strong>JPM/SmartAir</strong> — CSV différentiel (<code>Op = a/b/m</code>)
            pour les badges d'accès.</li>
          <li><strong>Groupes Google</strong> — CSV 4 colonnes d'appartenances :
            les élèves dans la mailing list de leur classe, les enseignants dans
            le groupe profs de chaque classe où ils sont professeur principal.</li>
          <li><strong>CardStudio</strong> — XLSX 13 colonnes pour l'impression visuelle
            des badges (photo + chambre).</li>
        </ul>
        <h3>Mode API Google (optionnel)</h3>
        <p>
          En complément du CSV, les changements peuvent être appliqués
          directement via l'Admin SDK. <strong>Le mode fichier reste le mode
          nominal</strong> : l'API n'est qu'un canal d'envoi supplémentaire.
        </p>
        <p>Configuration requise (Paramètres → Google Workspace) :</p>
        <ol>
          <li>Projet Google Cloud avec l'<strong>Admin SDK API</strong> activée</li>
          <li>Compte de service + clé JSON déposée sur ce poste</li>
          <li>Délégation à l'échelle du domaine autorisée sur les scopes annuaire</li>
          <li>Email d'un administrateur à impersonner</li>
        </ol>
        <p>
          Le fichier de credentials n'est <strong>jamais copié en base</strong> —
          seul son chemin est mémorisé. Le flux impose de calculer un plan,
          de le relire, puis de confirmer avant tout envoi.
        </p>

        <p><strong>Sortants Google</strong> — la catégorie <em>Anciens</em> place
          tout le monde dans l'OU d'archivage horodatée
          (<code>/7. Sortis/Comptes à supprimer au 31-12-AAAA</code>), quelle que
          soit la classe d'origine. La racine est configurable dans les Paramètres.</p>
        <p><strong>Boucle KoXo → Google (Lot 8b)</strong> — quand tu as le CSV KoXo
          re-exporté après création (avec MDP générés), tu le déposes dans l'écran
          Google Nouveaux pour enrichir le CSV Google. Les MDP transitent en mémoire
          uniquement.</p>

      {:else if sectionActive === "suivi"}
        <h2>Suivi et purge</h2>
        <p>Le cycle de vie d'un compte cible :</p>
        <pre><code>prevu → cree → actif → quarantaine → purge</code></pre>

        <h3>Comment les comptes sont créés</h3>
        <p>
          Quand tu génères un export <strong>Nouveaux</strong> avec la case
          <em>Enregistrer le suivi</em> cochée, les personnes du fichier sont
          inscrites en <code>prevu</code> sur la cible concernée. C'est ce qui
          alimente cet écran.
        </p>
        <p>Ensuite, dans l'onglet Suivi :</p>
        <ol>
          <li>Tu importes le fichier dans la cible (KoXo, Google…)</li>
          <li>Tu cliques <strong>prévu → créé</strong> pour confirmer</li>
          <li>Puis <strong>créé → actif</strong> une fois le compte en service</li>
        </ol>
        <p>
          Aucune action n'est envoyée au système tiers depuis cet écran — seul
          l'état du référentiel change. Le programme ne pilote pas KoXo ni
          Google : il produit des fichiers et mémorise ce que tu en as fait.
        </p>

        <h3>Politique de sortie</h3>
        <p>
          Le bouton <strong>Traiter les sortants</strong> applique
          automatiquement la politique à toutes les personnes présentes à
          l'année source mais absentes de la cible :
        </p>
        <ul>
          <li><strong>Google</strong> : quarantaine 18 mois avant purge.</li>
          <li><strong>KoXo, PMB, JPM, CardStudio</strong> : purge immédiate.</li>
        </ul>
        <p>
          Une échéance déjà posée n'est jamais repoussée — rejouer l'opération
          ne prolonge pas la quarantaine.
        </p>

      {:else if sectionActive === "securite"}
        <h2>Sécurité</h2>
        <ul>
          <li><strong>Aucun mot de passe stocké</strong>. Ni en base, ni dans les logs.
            KoXo est l'autorité unique — il génère à la création et ne régénère jamais.</li>
          <li><strong>Login figé à vie</strong>, y compris son suffixe d'homonymie
            (<code>pdupont2</code> reste <code>pdupont2</code> même après le départ
            de <code>pdupont</code>).</li>
          <li><strong>Aucune suppression directe côté Google</strong>. Un sortant part
            en quarantaine, jamais à la corbeille.</li>
          <li><strong>Cas ambigu → arbitrage humain</strong>. Jamais d'heuristique
            silencieuse.</li>
          <li><strong>Base locale</strong> dans <code>%APPDATA%/appli-rentree</code>.
            Aucune donnée cloud.</li>
        </ul>

      {:else if sectionActive === "faq"}
        <h2>Raccourcis clavier</h2>
        <table>
          <thead><tr><th>Touches</th><th>Action</th></tr></thead>
          <tbody>
            <tr><td><code>Ctrl</code> + <code>K</code></td><td>Recherche rapide</td></tr>
            <tr><td><code>Ctrl</code> + <code>1</code>…<code>9</code></td><td>Aller directement à une page, dans l'ordre de la barre latérale</td></tr>
            <tr><td><code>?</code></td><td>Ouvrir cette aide</td></tr>
          </tbody>
        </table>
        <p>
          Les raccourcis de navigation sont ignorés pendant une saisie, pour ne
          pas détourner les touches d'un champ de texte.
        </p>

        <h2>FAQ</h2>

        <h3>« Failed to fetch » à l'ingestion</h3>
        <p>Ouvre <code>http://127.0.0.1:8020/api/logs</code> dans un navigateur pour voir la stack trace côté backend.</p>

        <h3>Classes inconnues à l'ingestion</h3>
        <p>Complète la Table de correspondance (Sidebar → Table de correspondance) puis relance l'ingestion.</p>

        <h3>Login différent de KoXo après amorçage</h3>
        <p>La base l'emporte (login figé à vie). Vérifie le rapport d'amorçage — un conflit signifie que le login KoXo a été modifié manuellement dans le passé.</p>

        <h3>Où sont mes données ?</h3>
        <p>Base SQLite dans <code>%APPDATA%/appli-rentree/appli_rentree.db</code>. Log dans <code>backend.log</code> au même endroit.</p>

        <h3>Où trouver la version installée ?</h3>
        <p>En bas à gauche de la sidebar, sous « Backend v… ».</p>
      {/if}
    </div>
  </div>
</section>
