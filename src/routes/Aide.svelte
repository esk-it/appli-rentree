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
  import FolderTree from "@lucide/svelte/icons/folder-tree";
  import Cloud from "@lucide/svelte/icons/cloud";
  import ShieldCheck from "@lucide/svelte/icons/shield-check";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import KeyRound from "@lucide/svelte/icons/key-round";

  const sections = [
    { id: "flux", label: "Flux global", icon: BookOpen },
    { id: "amorcage", label: "Amorçage", icon: Rocket },
    { id: "ingestion", label: "Ingestion", icon: BookOpen },
    { id: "seaux", label: "Les 5 seaux", icon: GitCompareArrows },
    { id: "nouveaux", label: "Nouveaux arrivants", icon: UserPlus },
    { id: "bascule", label: "Bascule des OU", icon: FolderTree },
    { id: "compte_service", label: "Compte de service Google", icon: Cloud },
    { id: "conformite", label: "Conformité Google", icon: ShieldCheck },
    { id: "cycle", label: "Le cycle annuel", icon: RefreshCw },
    { id: "ordre_koxo_google", label: "KoXo puis Google", icon: KeyRound },
    { id: "controle_koxo", label: "Contrôle avant synchro KoXo", icon: ShieldCheck },
    { id: "synchro_koxo", label: "Synchroniser KoXo", icon: RefreshCw },
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

      {:else if sectionActive === "bascule"}
        <h2>Bascule des OU Google</h2>
        <p>
          Une rentrée ne se joue pas en une fois côté Google. L'écran suit les
          deux temps réels du processus :
        </p>
        <ol>
          <li>
            <strong>Placement pré-rentrée</strong> — tous les élèves de l'année,
            entrants comme montants, rejoignent l'OU d'attente de leur site
            (une seule par site). Les listes de classe bougent encore : les
            répartir maintenant obligerait à tout refaire.
          </li>
          <li>
            <strong>Bascule de rentrée</strong> — chacun quitte l'OU d'attente
            pour l'OU définitive de sa classe, une fois les répartitions
            arrêtées.
          </li>
        </ol>

        <h3>Ce que le programme sait</h3>
        <p>
          Il n'a aucune vue sur l'état réel de Google. Il mémorise donc ce
          qu'il a demandé, et compare : d'où les trois compteurs
          <strong>à déplacer</strong>, <strong>déjà en place</strong> et
          <strong>bloqués</strong>. C'est ce qui rend l'opération rejouable
          sans tout refaire, et vérifiable après coup.
        </p>
        <p>
          Le bouton « J'ai importé » n'agit pas sur Google : il enregistre que
          <em>tu</em> as importé le CSV dans la console Admin. Sans cette
          confirmation, les mêmes déplacements te seront reproposés.
        </p>

        <h3>Blocage</h3>
        <p>
          Si un élève relève d'une classe absente de la Table de
          correspondance, ou d'une classe dont l'OU n'est pas renseignée,
          <strong>rien n'est téléchargeable ni confirmable</strong>. Aucune OU
          par défaut n'est attribuée : un CSV partiel serait importé sans
          pouvoir être enregistré, et la trace divergerait de la réalité.
          Complète la table, puis reviens.
        </p>

        <h3>Par CSV ou par API</h3>
        <p>
          Les deux canaux suivent les mêmes phases et <strong>partagent le même
          calcul</strong> : le plan API délègue ses déplacements à ce service.
          Ils ne peuvent donc pas diverger. Un sélecteur de phase identique
          figure dans l'onglet Exports, section API Google.
        </p>
        <p>
          Différence : par API, l'appel a répondu, donc l'OU appliquée est
          mémorisée automatiquement. Par CSV, le programme n'a pas vu ton
          import — d'où le bouton « J'ai importé ».
        </p>

        <h3>Et les adultes ?</h3>
        <p>
          Hors périmètre : leur OU ne se déduit pas d'une classe. La Table de
          correspondance ne dit rien de leur rattachement, et deviner serait
          exactement ce que le programme s'interdit.
        </p>

      {:else if sectionActive === "compte_service"}
        <h2>Créer le compte de service Google</h2>
        <p>
          À faire <strong>une seule fois</strong>. Sans lui, le mode API reste
          masqué et tout passe par les fichiers CSV — ce qui fonctionne
          parfaitement, l'API n'est qu'un canal plus direct.
        </p>

        <h3>1. Le projet et l'API — console Google Cloud</h3>
        <ol>
          <li>Va sur <code>console.cloud.google.com</code>, connecté avec ton
            compte administrateur du domaine.</li>
          <li>Crée un projet (ou réutilise-en un) : appelle-le par exemple
            <em>Appli Rentrée ESK</em>.</li>
          <li>Dans <strong>API et services → Bibliothèque</strong>, cherche
            <strong>Admin SDK API</strong> et active-la. C'est elle qui donne
            accès aux utilisateurs et aux unités d'organisation.</li>
        </ol>

        <h3>2. Le compte de service</h3>
        <ol>
          <li><strong>IAM et administration → Comptes de service →
            Créer</strong>. Un nom suffit, aucun rôle IAM n'est nécessaire :
            les droits viendront de la délégation, pas d'IAM.</li>
          <li>Ouvre le compte créé, onglet <strong>Clés → Ajouter une clé →
            Créer une clé → JSON</strong>. Le fichier se télécharge.</li>
          <li>Retourne sur l'onglet <strong>Détails</strong> et note
            l'<strong>ID unique</strong> : une suite d'environ 21 chiffres,
            visible aussi dans le fil d'Ariane
            (<em>Compte de service : 1048…</em>).</li>
        </ol>
        <p>
          Ce fichier JSON est une clé privée : il donne accès à ton domaine.
          Range-le dans un dossier local protégé, jamais sur un partage
          réseau ouvert ni dans un dossier synchronisé.
        </p>
        <p>
          <strong>Le piège :</strong> l'onglet <em>Clés</em> affiche aussi un
          long identifiant, en chiffres <em>et lettres</em>
          (<code>5de2280de9…</code>). C'est l'empreinte de la clé, pas le
          compte de service. La collée dans la délégation donne
          « ID client incorrect ». Celui qu'il faut ne contient que des
          chiffres.
        </p>

        <h3>3. La délégation — console d'administration Google</h3>
        <ol>
          <li>Va sur <code>admin.google.com</code> →
            <strong>Sécurité → Contrôle des données et de l'accès → Commandes
            des API → Gérer la délégation au niveau du domaine</strong>.</li>
          <li><strong>Ajouter</strong>, colle le <em>Client ID</em> noté plus
            haut.</li>
          <li>Dans les champs OAuth, colle ces trois portées, séparées par des
            virgules <strong>sans espace</strong> :</li>
        </ol>
        <pre><code>https://www.googleapis.com/auth/admin.directory.user,https://www.googleapis.com/auth/admin.directory.orgunit,https://www.googleapis.com/auth/admin.directory.group</code></pre>
        <p>
          Ces trois portées, et pas davantage : les utilisateurs, les unités
          d'organisation, les groupes. Rien sur Drive ni Gmail, rien qui
          permette de lire le contenu des comptes.
        </p>

        <h3>4. Dans le programme</h3>
        <p>Onglet <strong>Paramètres</strong>, section Google Workspace :</p>
        <ul>
          <li><strong>Fichier de credentials</strong> — le chemin complet du
            JSON. Son contenu n'est jamais copié en base, seul le chemin est
            enregistré.</li>
          <li><strong>Administrateur à impersonner</strong> — l'adresse d'un
            super-administrateur réel du domaine. La délégation impose que le
            compte de service agisse au nom de quelqu'un ; c'est ce compte qui
            apparaîtra dans les journaux d'audit Google.</li>
          <li><strong>Activer le mode API</strong> — à cocher en dernier.</li>
        </ul>
        <p>
          Puis, dans <strong>Exports</strong>, le bouton
          <em>Tester la connexion</em> : il lit un seul utilisateur, ne
          modifie rien, et confirme que l'authentification, les portées et la
          délégation sont bonnes.
        </p>

        <h3>Si ça ne marche pas</h3>
        <ul>
          <li><em>ID client incorrect</em>, au moment d'enregistrer la
            délégation — c'est l'empreinte de la clé qui a été collée à la
            place de l'ID unique du compte de service. Le bon ne contient
            que des chiffres.</li>
          <li><em>unauthorized_client</em> — l'ID unique ou les portées ne
            correspondent pas à ce qui est déclaré dans la délégation.</li>
          <li><em>Admin SDK API has not been used in project…</em> — l'API
            n'est pas activée dans le projet <strong>où vit le compte de
            service</strong>. Vérifie le sélecteur de projet en haut de la
            console : réutiliser un projet créé pour autre chose est possible,
            mais il faut y activer l'Admin SDK.</li>
          <li><em>Not Authorized to access this resource</em> — l'adresse
            impersonnée n'est pas super-administrateur.</li>
          <li>La délégation peut mettre quelques minutes à se propager :
            réessaie avant de tout défaire.</li>
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

        <h3>Une ligne rejetée ici devient un identifiant volé plus tard</h3>
        <p>
          L'unicité d'un identifiant se vérifie <strong>dans le
          référentiel</strong>, jamais dans KoXo — le programme n'interroge
          pas KoXo à l'ingestion. Un compte KoXo que l'amorçage n'a pas su
          charger reste donc invisible, et son identifiant paraît libre.
        </p>
        <p>
          Le premier entrant dont le nom produit le même identifiant se le
          voit alors attribuer, et le titulaire historique récupère un
          suffixe. C'est arrivé : l'ID unique d'une élève valait un
          identifiant au lieu d'un numéro, sa ligne d'amorçage a été rejetée,
          et son identifiant est parti à une homonyme entrante.
        </p>
        <p>
          <strong>Lis donc les rejets</strong>, et corrige-les dans KoXo avant
          d'ingérer Charlemagne. Le <em>Contrôle KoXo</em> les rattrape après
          coup, mais l'identifiant est déjà attribué à ce moment-là.
        </p>

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

      {:else if sectionActive === "conformite"}
        <h2>Conformité Google</h2>
        <p>
          Trois écarts entre le référentiel et Google font échouer la rentrée,
          chacun sans prévenir. Cet écran les mesure d'abord, et ne propose
          d'agir qu'ensuite.
        </p>

        <h3>Arborescence</h3>
        <p>
          Google refuse un déplacement vers une unité d'organisation qui
          n'existe pas, et rien en amont ne l'annonce : l'échec se constate
          élève par élève, une fois la bascule lancée. Le contrôle compare donc
          l'arbre réel à ce que décrit la Table.
        </p>
        <p>
          Deux façons d'ouvrir l'année, au choix. <strong>Recycler</strong> :
          l'arbre de l'année révolue est renommé, et emporte ses classes d'un
          seul geste — sur l'instance de l'établissement, un renommage couvre
          70 des 90 OU attendues, il en reste 20 à créer. <strong>Créer</strong> :
          on repart d'un arbre neuf, les 90 sont à créer et l'ancien reste en
          place. Le premier suppose que la branche recyclée a été vidée au
          préalable — voir l'écran <em>Sortants</em>.
        </p>
        <p>
          Aucune unité d'organisation n'est jamais supprimée par le programme.
        </p>

        <h3>Adresses</h3>
        <p>
          Aucune règle ne reproduit fidèlement les adresses existantes : les
          particules, les prénoms composés et les homonymes traités à la main
          au fil des ans y ont laissé des exceptions. Quand l'adresse
          enregistrée ne correspond à aucun compte Google, le déplacement
          échoue — et l'export des nouveaux crée un doublon à côté du compte
          réel, ce qui est pire.
        </p>
        <p>
          Une correction n'est proposée que si le nom désigne
          <strong>exactement un</strong> compte Google et
          <strong>exactement une</strong> personne du référentiel. Un homonyme
          rendrait l'attribution arbitraire : ces cas sont comptés à part et
          laissés à l'arbitrage. Ce que Google contient fait foi — c'est là que
          l'élève se connecte.
        </p>

        <h3>Groupes</h3>
        <p>
          L'export CSV <strong>ajoute</strong> des membres et n'en retire
          jamais. Un groupe de 3e conserve donc ses élèves année après année,
          les partis compris : écrire au « groupe des 3e » touche des
          promotions entières qui ont quitté l'établissement. Ici la
          composition est calculée par différence, dans les deux sens, et le
          retrait peut être désactivé pour un premier passage prudent.
        </p>
        <p>
          Deux garde-fous. Un membre qu'aucune personne du référentiel ne porte
          — enseignant, adresse de service, ajout manuel — n'est
          <strong>jamais</strong> retiré : le programme ignore pourquoi il est
          là. Et un groupe déclaré dans la Table mais absent de Google voit ses
          ajouts <strong>retenus</strong> plutôt que tentés : un groupe vide et
          un groupe absent se ressemblent, mais écrire dans le second échoue
          élève par élève.
        </p>
        <p>
          Si un site entier n'a aucun élève pour l'année préparée, l'écran le
          signale en rouge. Ce n'est pas une classe qui a fermé : c'est un
          export Charlemagne qui n'a pas été chargé.
        </p>
        <p>
          Les groupes absents peuvent être <strong>créés</strong> depuis cet
          écran. C'est un geste distinct de la synchronisation : créer un
          groupe fait naître une adresse de messagerie, ajouter un membre
          n'en crée aucune. Par défaut seuls ceux qui débloquent réellement
          des élèves sont proposés — une classe sans effectif cette année
          n'a pas besoin de sa liste tout de suite, et quinze listes vides
          encombreraient la console sans rien résoudre. Aucun groupe n'est
          jamais supprimé par le programme.
        </p>

      {:else if sectionActive === "ordre_koxo_google"}
        <h2>KoXo d'abord, Google ensuite</h2>
        <p>
          Créer un compte Google suppose de lui donner un mot de passe. Le
          programme n'en fabrique aucun : <strong>KoXo est l'autorité
          unique</strong>, il génère le mot de passe à la création et ne le
          régénère jamais. L'ordre des opérations en découle, et il n'est pas
          négociable.
        </p>

        <h3>La séquence</h3>
        <ol>
          <li>Ingérer l'export Charlemagne de l'année préparée.</li>
          <li>Générer l'export <strong>KoXo / Nouveaux</strong> et l'importer
            dans KoXo. C'est là que les comptes naissent, avec leur mot de
            passe.</li>
          <li>Ré-exporter depuis KoXo, <em>en incluant les mots de passe</em>.</li>
          <li>Revenir dans Exports, choisir <strong>Google / Nouveaux</strong>,
            et déposer le fichier KoXo dans l'encadré prévu. Le CSV Google en
            sort avec la colonne « Password » remplie.</li>
          <li>Importer ce CSV dans la console Google.</li>
        </ol>

        <h3>Ce qui arrive si on saute l'étape</h3>
        <p>
          Le CSV se génère quand même, et il n'a l'air de rien manquer : toutes
          les colonnes sont là, les lignes sont présentes. Seule la colonne
          « Password » est vide, et Google refuse les créations sans mot de
          passe. L'échec ne se découvre alors qu'à l'import, une fois le
          fichier transmis. L'écran Exports le signale désormais avant la
          génération.
        </p>

        <h3>Où passent les mots de passe</h3>
        <p>
          Ils traversent l'application <strong>en mémoire seulement</strong>. Le
          fichier KoXo n'est pas conservé, les mots de passe ne sont écrits
          dans aucune base, et le seul endroit où ils réapparaissent est le CSV
          Google que tu enregistres toi-même. Efface-le une fois l'import fait.
        </p>

        <h3>Pourquoi les autres cibles restent des fichiers</h3>
        <p>
          KoXo, PMB, JPM et CardStudio n'exposent pas d'API : l'export est le
          seul canal, et c'est ainsi que c'était prévu. Google est la seule
          cible où le programme peut agir directement — c'est aussi celle qui
          demande le plus de travail, d'où l'écran Conformité Google.
        </p>

      {:else if sectionActive === "cycle"}
        <h2>Le cycle annuel</h2>
        <p>
          Deux arbres d'année vivent à tout moment, et ils se relaient. Le plus
          ancien s'est vidé de lui-même : ses élèves sont partis, ou ont été
          montés dans le suivant. Il est alors recyclé pour la rentrée qui
          arrive, pendant que le second devient à son tour le plus ancien.
        </p>

        <h3>Une année, pas à pas</h3>
        <p>
          Pour la rentrée 2026-2027, avec <code>NDK2026</code> qui porte
          l'année écoulée et <code>NDK2025</code> celle d'avant :
        </p>
        <ol>
          <li><strong>Vider <code>NDK2025</code></strong>. Ce qui s'y trouve
            encore, ce sont les élèves partis au 31 août 2025. Ils rejoignent
            l'OU de sortie qui leur revient — <code>Comptes à supprimer au
            31-12-2026</code> — et y resteront actifs jusqu'à la lettre de
            prévenance.</li>
          <li><strong>Renommer <code>NDK2025</code> en <code>NDK2027</code></strong>.
            L'arbre vidé devient celui de la rentrée, et ses classes suivent :
            c'est ce qui évite d'en recréer quarante-quatre.</li>
          <li><strong>Tourner la Table</strong> de 2026 vers 2027, pour qu'elle
            désigne le nouvel arbre.</li>
          <li><strong>Basculer les élèves de <code>NDK2026</code></strong> vers
            la racine de <code>NDK2027</code> — c'est la pré-rentrée — puis dans
            leur classe le jour J.</li>
          <li>Ce qui reste alors dans <code>NDK2026</code>, ce sont les élèves
            <strong>partis au 31 août 2026</strong>. Ils y dorment un an.</li>
        </ol>

        <h3>Et l'année suivante, à l'identique</h3>
        <p>
          On vide <code>NDK2026</code> vers <code>Comptes à supprimer au
          31-12-2027</code>, on le renomme <code>NDK2028</code>, on tourne la
          Table de 2027 vers 2028, et les élèves de <code>NDK2027</code> montent
          dans <code>NDK2028</code>. Puis ainsi de suite, chaque année.
        </p>

        <h3>Pourquoi les deux renommages ne partent pas de la même année</h3>
        <p>
          C'est la source de confusion la plus fréquente. Côté Google, c'est
          <code>NDK2025</code> qui devient <code>NDK2027</code> : on recycle
          l'arbre <em>vidé</em>, qui a deux ans. Côté Table, on remplace 2026
          par 2027 : elle désignait l'arbre de l'année qui vient de finir. Les
          deux aboutissent à 2027 en partant d'années différentes, et c'est
          normal.
        </p>

        <h3>Ce qui découle du cycle</h3>
        <p>
          Un élève parti au 31 août N reste un an dans l'arbre de son année,
          puis rejoint l'OU datée du 31 décembre N+1. La lettre part à cette
          date, la suppression quatre mois plus tard : vingt mois de
          conservation, au-delà des dix-huit promis.
        </p>
        <p>
          Un élève encore inscrit qu'on trouve dans l'arbre à vider n'est pas
          déplacé — le renommage l'emporte dans le nouvel arbre, et la bascule
          de pré-rentrée le remet au rang. Le déplacer avant serait un détour :
          l'arbre de destination n'existe pas encore, puisque c'est celui-ci qui
          va le devenir.
        </p>

      {:else if sectionActive === "controle_koxo"}
        <h2>Contrôle avant synchronisation KoXo</h2>
        <p>
          La montée de classe se fait dans KoXo par une
          <strong>synchronisation</strong> — la « bascule » — et non par un
          import ordinaire. Elle déplace les comptes existants vers leur
          nouveau groupe secondaire <em>et</em> crée ceux qui manquent, en une
          passe.
        </p>

        <h3>Comment KoXo reconnaît un compte</h3>
        <p>
          Par son <strong>ID unique</strong>. Ce n'est que si ce champ est vide
          qu'il retombe sur la chaîne <code>Nom + Prénom + Date de
          naissance</code>. Or l'établissement ne renseigne pas la date de
          naissance : le repli ne distingue donc rien.
        </p>
        <p>
          Un compte que la synchronisation ne reconnaît pas est un compte
          <strong>recréé sous un autre identifiant</strong> — ou
          <strong>supprimé</strong>, si la synchronisation tourne en mode
          destructif. D'où la règle : <strong>synchronisation non
          destructive</strong>, toujours. Les sortants se traitent à part, avec
          l'export « Anciens ».
        </p>

        <h3>Ce que le contrôle regarde</h3>
        <ul>
          <li><strong>Rapprochement ambigu</strong> — le badge désigne une
            personne, l'identifiant une autre. Le programme ne tranche pas.</li>
          <li><strong>ID unique en double</strong> — deux comptes répondent à
            la même clé ; la synchronisation ne saura pas lequel mettre à
            jour.</li>
          <li><strong>ID unique qui n'est pas un badge</strong> — un
            identifiant écrit là où un numéro est attendu.</li>
          <li><strong>ID unique absent</strong> — rien ne permet de
            reconnaître le compte.</li>
          <li><strong>Identifiant divergent</strong> — KoXo et le référentiel
            ne connaissent pas ce badge sous le même identifiant. Un
            identifiant constaté fait autorité : c'est le référentiel qu'on
            aligne, jamais l'inverse.</li>
          <li><strong>Badge inconnu</strong> — aucune ligne de l'export ne
            s'adressera à ce compte.</li>
          <li><strong>À créer</strong> — le déroulement normal d'une rentrée,
            pas un défaut.</li>
        </ul>

        <h3>Ce qu'il ne fait pas</h3>
        <p>
          Il n'écrit rien, ni dans le référentiel ni dans KoXo. Aucun écart
          n'est corrigé automatiquement : quand KoXo et le référentiel
          divergent, le programme n'a aucun moyen de savoir laquelle des deux
          valeurs fait foi. Il montre, et la correction se fait dans KoXo.
        </p>

        <h3>Une moitié de contrôle peut être muette</h3>
        <p>
          Le sens « qui manque à KoXo » compare la population du référentiel à
          l'export. Les adultes n'ayant pas de photographie annuelle, borner
          par année vide leur population — l'écran le dit alors plutôt que
          d'afficher un zéro rassurant.
        </p>

      {:else if sectionActive === "synchro_koxo"}
        <h2>Synchroniser KoXo</h2>
        <p>
          La montée de classe se fait par une <strong>synchronisation</strong> —
          la « bascule » — et non par un import ordinaire. Elle déplace les
          comptes existants vers leur nouveau groupe secondaire <em>et</em> crée
          ceux qui manquent, en une passe.
        </p>

        <h3>Deux passes, dans cet ordre</h3>
        <ol>
          <li><strong>Les sortants d'abord.</strong> Export
            <em>KoXo / Anciens</em>, avec un <strong>groupe secondaire de
            destination</strong> — <code>Anciens élèves</code>. Sans lui, chaque
            ligne porte la dernière classe de l'élève, et la synchronisation le
            remettrait dans cette classe, au milieu de la promotion suivante. Le
            groupe doit exister dans KoXo avant de lancer.</li>
          <li><strong>Tous les autres ensuite.</strong> Export
            <em>KoXo / Tous</em> — l'état complet visé. C'est cette passe qui
            déplace les élèves dans leur nouvelle classe et crée les entrants
            avec leur mot de passe.</li>
        </ol>

        <h3>Non destructif, dans les deux cas</h3>
        <p>
          Le mode destructif supprime tout ce qui ne figure pas dans le fichier.
          Il supprimerait donc les comptes que la reconnaissance a manqués — et
          la reconnaissance repose ici sur le seul ID unique, la date de
          naissance n'étant pas renseignée.
        </p>
        <p>
          Ranger les sortants dans un groupe dédié est précisément ce qui rend
          le mode destructif inutile : ils sont parqués, identifiables, et leur
          suppression devient un geste distinct et daté plutôt qu'un effet de
          bord.
        </p>

        <h3>Puis la boucle vers Google</h3>
        <p>
          Une fois les créations faites, <strong>ré-exporte depuis KoXo en
          incluant les mots de passe</strong> et dépose ce fichier dans
          l'écran Exports, cible Google. Sans lui, la colonne
          <code>Password</code> reste vide et Google refuse les créations. Le
          fichier n'est pas conservé — voir <em>KoXo puis Google</em>.
        </p>

        <h3>Supprimer ou désactiver un doublon</h3>
        <p>
          Quand le contrôle signale deux comptes sur le même ID unique,
          <strong>désactiver suffit</strong> si l'export KoXo est configuré pour
          exclure les comptes désactivés — ce qui est le cas ici. Les données
          restent, et l'ambiguïté disparaît. Le vérifier est immédiat : repasse
          le contrôle sur un export neuf, l'écart doit avoir disparu.
        </p>

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
          <li><strong>PMB</strong> — le programme ne fabrique pas ce fichier :
            sept des treize colonnes que PMB attend (adresse, code postal,
            ville, téléphone, année de naissance, sexe) n'existent nulle part
            dans le référentiel. Le fichier vient de <strong>Charlemagne</strong>,
            et l'onglet PMB le <strong>coupe par établissement</strong> — son
            export porte les trois sites en vrac, alors que PMB a une instance
            par établissement.</li>
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

        <h3>L'OU d'archivage Google</h3>
        <p>
          Un sortant est <strong>suspendu puis déplacé</strong> dans une OU
          datée, dont le nom porte l'échéance de suppression :
        </p>
        <pre><code>/7. Sortis/Comptes à supprimer au 31-12-2027</code></pre>
        <p>
          Convention reprise du fichier de ton prédécesseur, et elle est
          maligne : le ménage annuel devient lisible depuis la console Google
          seule, sans avoir à consulter le référentiel. L'échéance est arrondie
          au 31 décembre, ce qui donne un dossier par campagne plutôt qu'un par
          jour de départ. La racine <code>/7. Sortis</code> se change dans
          Paramètres (<code>google.ou_sortants</code>).
        </p>
        <p>Deux canaux, même résultat :</p>
        <ul>
          <li><strong>CSV</strong> — onglet Exports, catégorie
            <em>Anciens</em> : tous les sortants pointent vers l'OU
            d'archivage, quelle que soit leur classe d'origine.</li>
          <li><strong>API</strong> — l'opération <em>suspendre</em> fait les
            deux d'un coup : passage en suspendu et déplacement.</li>
        </ul>
        <p>
          La suppression réelle, elle, reste manuelle. Quand l'échéance tombe,
          une anomalie apparaît sur le tableau de bord et l'écran Suivi propose
          d'enregistrer la purge — après que <em>tu</em> l'aies faite dans la
          console. Le programme ne supprime jamais rien lui-même.
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
