<script>
  import Repere from "./Repere.svelte";
  import Planches from "./Planches.svelte";
  import Fenetre from "./koxo/Fenetre.svelte";
  import Arbre from "./koxo/Arbre.svelte";
  import Dialogue from "./koxo/Dialogue.svelte";
  import C from "./koxo/Controles.svelte";

  /**
   * L'export de tous les comptes élèves d'une base KoXo, mots de passe
   * compris — redessiné d'après les captures de Johann (15 octobre 2026).
   * Les noms et les chiffres sont inventés.
   *
   * @typedef {Object} Props
   * @property {string} [base]
   */
  /** @type {Props} */
  let { base = "NDK" } = $props();

  const PLANCHES = [
    { id: "menu", titre: "Le menu", reperes: [1] },
    { id: "selection", titre: "Le mode sélection", reperes: [2, 3] },
    { id: "filtre", titre: "Le filtre", reperes: [4] },
  ];
  let actuelle = $state("menu");

  const MENU = [
    { texte: "Assistant de démarrage", trait: true },
    { texte: "Sauvegarder", sous: true },
    { texte: "Restaurer à partir d'une archive", trait: true },
    { texte: "Configurer", trait: true },
    { texte: "Configurer l'impression" },
    { texte: "Imprimer des étiquettes et des listes", raccourci: "Ctrl+P" },
    { texte: "Publiposter des documents RTF / DOCX", trait: true },
    { texte: "Exporter", sous: true, cible: true, trait: true },
    { texte: "Voir le journal", raccourci: "Ctrl+J" },
    { texte: "Mode de l'interface", sous: true },
    { texte: "Maintenance générale", sous: true },
    { texte: "Outils / Utilitaires", sous: true, trait: true },
    { texte: "Quitter" },
  ];
  const FORMATS = [
    { texte: "au format texte CSV", cible: true },
    { texte: "au format LDIF" },
    { texte: "au format carte de visite (VCard)" },
    { texte: "en photos d'identités vers un dossier" },
  ];
  const ELEVES = [
    ["1_1", "aexemple", "EXEMPLE", "Alice"],
    ["1_1", "bfictif", "FICTIF", "Bruno"],
    ["1_1", "cmodele", "MODELE", "Chloé"],
    ["1_2", "dessai", "ESSAI", "Damien"],
    ["1_2", "einvente", "INVENTE", "Emma"],
    ["1_2", "fdemo", "DEMO", "Félix"],
    ["2_1", "gpatron", "PATRON", "Gaël"],
    ["2_1", "hgabarit", "GABARIT", "Hugo"],
  ];
  const FILTRES = [
    ["Export Classes pour KoXo Shortcuts", "Groupe secondaire;Partag…", "%SECONDARY_GROUP%;%SECONDARY_GROUP_UNC…"],
    ["Export Utilisateurs pour KoXo Sho…", "Groupe secondaire;Titre;Pr…", "%SECONDARY_GROUP%;%USER_TITLE%;%USER_FIRS…"],
    ['Filtre "Complet Utilisateur"', "Groupe primaire;Groupe se…", "%PRIMARY_GROUP%;%SECONDARY_GROUP%;%USER…", true],
    ['Filtre "Groupe Primaire"', "Nom,Description,Email", "%PRIMARY_GROUP%,%PRIMARY_GROUP_DESC%,%PR…"],
    ['Filtre "Groupe Secondaire"', "Nom,Description,Email", "%SECONDARY_GROUP%,%SECONDARY_GROUP_DES…"],
    ['Filtre "Identifiant + Mot de passe"', "Identifiant;Mot de passe", "%USER_ID%;%USER_PASSWORD%"],
    ['Filtre "Liste Nom Prénom"', "Nom Prénom", "%USER_NAME% %USER_FIRST_NAME%"],
  ];
</script>

<Planches planches={PLANCHES} {actuelle} onChoisir={(id) => (actuelle = id)}>
  {#if actuelle === "menu"}
    <div role="img" aria-label="KoXo Administrator : menu Général, Exporter, des utilisateurs, au format texte CSV">
      <Fenetre titre="KoXo Administrator V4.0 :: [Mode Expert] — base {base}" menu="Général">
        <div class="grid h-[370px] grid-cols-[170px_minmax(0,1fr)]">
          <Arbre selection={null} />
          <div class="bg-[#E6EEF7] p-1.5"><div class="h-full border border-[#B9C6D6] bg-white"></div></div>
        </div>
        <div class="absolute top-0 left-1 w-[290px] border border-[#A0A0A0] bg-[#F2F2F2] py-0.5 shadow-[2px_3px_6px_rgba(0,0,0,0.25)]">
          {#each MENU as m (m.texte)}
            <div class="relative flex items-center gap-2 py-[3px] pr-2 pl-7 {m.cible ? 'border border-[#E4B95B] bg-[#FDE9B0]' : 'border border-transparent'}">
              <span class="min-w-0 flex-1 truncate">{m.texte}</span>
              {#if m.raccourci}<span class="text-[#444]">{m.raccourci}</span>{/if}
              {#if m.sous}<span class="text-[9px]">▶</span>{/if}
              {#if m.cible}
                <!-- Exporter › des utilisateurs › au format texte CSV -->
                <span class="absolute top-[-3px] left-[calc(100%+3px)] w-[140px] border border-[#A0A0A0] bg-[#F2F2F2] p-0.5 shadow-[2px_3px_6px_rgba(0,0,0,0.25)]">
                  <span class="flex items-center justify-between border border-[#E4B95B] bg-[#FDE9B0] px-2 py-[3px]">des utilisateurs <span class="text-[9px]">▶</span></span>
                  <span class="flex items-center justify-between border border-transparent px-2 py-[3px]">des groupes <span class="text-[9px]">▶</span></span>
                  <span class="absolute top-[-3px] left-[calc(100%+3px)] w-[215px] border border-[#A0A0A0] bg-[#F2F2F2] p-0.5 shadow-[2px_3px_6px_rgba(0,0,0,0.25)]">
                    {#each FORMATS as f (f.texte)}
                      <span class="relative flex items-center border px-2 py-[3px] {f.cible ? 'border-[#E4B95B] bg-[#FDE9B0]' : 'border-transparent'}">
                        {f.texte}
                        {#if f.cible}<span class="absolute -right-3 top-1/2 -translate-y-1/2"><Repere n={1} /></span>{/if}
                      </span>
                    {/each}
                  </span>
                </span>
              {/if}
            </div>
            {#if m.trait}<div class="mx-1 my-0.5 border-t border-[#D4D4D4]"></div>{/if}
          {/each}
        </div>
      </Fenetre>
    </div>
  {:else if actuelle === "selection"}
    <div role="img" aria-label="Mode sélection : glisser le groupe Elèves dans la liste, puis Exporter">
      <Fenetre titre=":: [Mode Expert] — base {base}" modeSelection>
        <div class="grid h-[330px] grid-cols-[170px_minmax(0,1fr)]">
          <Arbre selection="Elèves" repere={2} />
          <div class="flex min-w-0 flex-col bg-[#E6EEF7] p-1.5">
            <div class="flex text-[11px]">
              <span class="rounded-t-[2px] border border-b-0 border-[#B9C6D6] bg-white px-2 py-0.5">Liste des utilisateurs</span>
            </div>
            <div class="flex-1 overflow-hidden border border-[#B9C6D6] bg-white">
              <div class="grid grid-cols-[72px_100px_90px_minmax(0,1fr)_70px] border-b border-[#E3E3E3] px-1.5 py-0.5 text-[#333]">
                <span>Grp Primaire</span><span>Grp Secondaire</span><span>Identifiant</span><span>Nom</span><span>Prénom</span>
              </div>
              {#each ELEVES as [classe, login, nom, prenom] (login)}
                <div class="grid grid-cols-[72px_100px_90px_minmax(0,1fr)_70px] px-1.5 py-[1px]">
                  <span>Elèves</span><span>{classe}</span><span>{login}</span><span>{nom}</span><span>{prenom}</span>
                </div>
              {/each}
            </div>
            <div class="mt-1 flex items-center gap-1.5">
              <span class="flex items-center gap-2"><C genre="bouton" marque texte="Exporter" /><Repere n={3} /></span>
              <C genre="bouton" texte="Supprimer" />
              <span class="flex-1"></span>
              <C genre="bouton" texte={'Quitter le "Mode sélection"'} />
            </div>
            <div class="mt-1 flex items-center justify-between">
              <C genre="case" coche texte="Ne pas glisser-déposer les comptes désactivés" />
              <span>1 012 utilisateur(s)</span>
            </div>
          </div>
        </div>
        <!-- Le geste : glisser « Elèves » de l'arbre vers la liste -->
        <svg class="pointer-events-none absolute top-[50px] left-[125px] h-[90px] w-[200px]" viewBox="0 0 200 90" aria-hidden="true">
          <path d="M8 6 C 70 0, 120 30, 186 72" fill="none" stroke="#FF7A59" stroke-width="2.5" stroke-dasharray="6 4" />
          <path d="M176 62 L190 76 L172 78 Z" fill="#FF7A59" />
        </svg>
      </Fenetre>
    </div>
  {:else}
    <div role="img" aria-label="Export en CSV : choisir le filtre Complet Utilisateur, puis OK">
      <Dialogue titre="Export en CSV">
        <div class="relative rounded-[2px] border border-[#C5CFDA] bg-white">
          <span class="absolute -top-3 -right-3"><Repere n={4} /></span>
          <div class="grid grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1.4fr)] border-b border-[#E3E3E3] px-1.5 py-0.5 text-[#333]">
            <span>Nom</span><span>Entête</span><span>Chaine</span>
          </div>
          {#each FILTRES as [nom, entete, chaine, cible] (nom)}
            <div class="grid grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1.4fr)] gap-1 px-1.5 py-[2px] {cible ? 'bg-[#CCE8FF] outline outline-2 outline-[#FF7A59]' : ''}">
              <span class="truncate">{nom}</span><span class="truncate">{entete}</span><span class="truncate">{chaine}</span>
            </div>
          {/each}
        </div>
        {#snippet boutons()}
          <C genre="bouton" icone="ok" texte="OK" />
          <C genre="bouton" icone="annuler" texte="Annuler" />
        {/snippet}
      </Dialogue>
    </div>
  {/if}
</Planches>
