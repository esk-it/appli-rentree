<script>
  import Repere from "./Repere.svelte";
  import Planches from "./Planches.svelte";
  import Fenetre from "./koxo/Fenetre.svelte";
  import Arbre from "./koxo/Arbre.svelte";
  import Dialogue from "./koxo/Dialogue.svelte";
  import C from "./koxo/Controles.svelte";

  /**
   * La synchronisation d'une base KoXo depuis le fichier du programme,
   * fenêtre par fenêtre — redessinée d'après les captures de Johann
   * (15 octobre 2026). Les groupes, les noms et les chiffres sont inventés.
   *
   * L'étape 1/8 se règle comme Johann la règle : non destructive, et les
   * orphelins — les sortants — désactivés plutôt que supprimés. Les étapes
   * 3 à 6 ne sont pas dessinées (pas de capture) : on y garde ce que KoXo
   * propose. La fenêtre « Opérations à effectuer » s'ouvre à l'étape 7/8.
   *
   * Les champs de l'étape 2/8 sont ceux du fichier que le programme écrit
   * (`backend/services/exports_koxo.py`, `COLONNES_KOXO`) : si l'ordre des
   * colonnes change là-bas, il change ici.
   *
   * @typedef {Object} Props
   * @property {string} [base]
   */
  /** @type {Props} */
  let { base = "NDK" } = $props();

  const PLANCHES = [
    { id: "menu", titre: "Le menu", reperes: [1, 2] },
    { id: "etape1", titre: "Étape 1/8", reperes: [3] },
    { id: "etape2", titre: "Étape 2/8", reperes: [4] },
    { id: "etape7", titre: "Étape 7/8", reperes: [5] },
  ];
  let actuelle = $state("menu");

  const CLASSES = [
    ["1_1", 32], ["1_2", 34], ["2_1", 35], ["2_2", 33], ["T_1", 31], ["T_2", 30], ["BTS_1", 24],
  ];
  const MENU = [
    { texte: "Rechercher des utilisateurs dans l'arbre", raccourci: "Ctrl+F" },
    { texte: "Importer des utilisateurs dans l'arbre (par groupe secondaire)", sous: true, trait: true },
    { texte: "Synchroniser les groupes secondaires et les utilisateurs", sous: true, cible: true },
    { texte: "Importer des groupes secondaires (sans utilisateurs)" },
    { texte: "Ajouter un groupe secondaire", trait: true },
    { texte: "Etiquettes de compte", sous: true },
    { texte: "Exporter le groupe primaire en XML" },
    { texte: "Importer un groupe secondaire à partir d'un fichier XML" },
    { texte: "Exécuter un script", sous: true },
    { texte: "Renommer les identifiants depuis une formule", trait: true },
    { texte: "Supprimer le groupe primaire" },
  ];
  const ETAPES_KOXO = [
    "Configuration du type de synchronisation et ouverture du fichier texte (CSV) (cliquer sur 'Suivant')",
    "Affectation des champs de la base",
    "Sélection des groupes secondaires à synchroniser",
    "Affectations des stockages des nouveaux groupes",
    "Configuration de l'archivage",
    "Affichage des opérations à effectuer",
    "Synchronisation des groupes secondaires",
    "Bilan de la synchronisation",
  ];
  /** L'en-tête du fichier du programme, tel que « Vérif. » le montre. */
  const EXEMPLE = "Groupe primaire,Groupe secondaire,Titre,Nom,Prénom,Identifiant,ID unique,Mot de passe,…";
</script>

<Planches planches={PLANCHES} {actuelle} onChoisir={(id) => (actuelle = id)}>
  {#if actuelle === "menu"}
    <div role="img" aria-label="KoXo Administrator : clic droit sur le groupe Elèves, puis Synchroniser les groupes secondaires et les utilisateurs, à partir d'un fichier texte CSV">
      <Fenetre titre="KoXo Administrator V4.0 :: [Mode Expert] — base {base}">
        <div class="grid h-[360px] grid-cols-[170px_minmax(0,1fr)]">
          <Arbre selection="Elèves" repere={1} />
          <div class="flex min-w-0 flex-col bg-[#E6EEF7] p-1.5">
            <div class="flex gap-0.5 text-[11px]">
              <span class="rounded-t-[2px] border border-b-0 border-[#B9C6D6] bg-white px-2 py-0.5">Le groupe "Elèves" contient</span>
              <span class="px-2 py-0.5 text-[#444]">Script</span>
              <span class="px-2 py-0.5 text-[#444]">Paramètres avancés</span>
            </div>
            <div class="flex-1 border border-[#B9C6D6] bg-white">
              <div class="grid grid-cols-[90px_minmax(0,1fr)_40px] border-b border-[#E3E3E3] px-1.5 py-0.5 text-[#333]">
                <span>Groupe</span><span>Description</span><span class="text-right">Nb.</span>
              </div>
              {#each CLASSES as [c, n] (c)}
                <div class="grid grid-cols-[90px_minmax(0,1fr)_40px] px-1.5 py-[1px]">
                  <span>{c}</span><span>Classe de {c}</span><span class="text-right">{n}</span>
                </div>
              {/each}
            </div>
          </div>
        </div>
        <!-- Le menu du clic droit sur « Elèves » -->
        <div class="absolute top-[62px] left-[150px] w-[350px] border border-[#A0A0A0] bg-[#F2F2F2] py-0.5 shadow-[2px_3px_6px_rgba(0,0,0,0.25)]">
          {#each MENU as m (m.texte)}
            <div class="relative flex items-center gap-2 py-[3px] pr-2 pl-7 {m.cible ? 'border border-[#E4B95B] bg-[#FDE9B0]' : 'border border-transparent'}">
              <span class="min-w-0 flex-1 truncate">{m.texte}</span>
              {#if m.raccourci}<span class="text-[#444]">{m.raccourci}</span>{/if}
              {#if m.sous}<span class="text-[9px]">▶</span>{/if}
              {#if m.cible}
                <span class="absolute -left-3 top-1/2 -translate-y-1/2"><Repere n={2} /></span>
                <span class="absolute top-[-3px] left-[calc(100%+3px)] flex w-[190px] items-center gap-2 border border-[#A0A0A0] bg-[#F2F2F2] p-0.5 shadow-[2px_3px_6px_rgba(0,0,0,0.25)]">
                  <span class="flex-1 border border-[#E4B95B] bg-[#FDE9B0] px-2 py-[3px]">A partir d'un fichier texte CSV</span>
                </span>
              {/if}
            </div>
            {#if m.trait}<div class="mx-1 my-0.5 border-t border-[#D4D4D4]"></div>{/if}
          {/each}
        </div>
      </Fenetre>
    </div>
  {:else if actuelle === "etape1"}
    <div role="img" aria-label="Étape 1 sur 8 : cocher Synchronisation non destructive">
      <Dialogue titre="Synchronisation à partir d'un fichier texte (CSV) : Etape 1/8">
        <p class="text-[13px] font-bold">La synchronisation s'effectue en 8 étapes :</p>
        <ol class="mt-1.5 ml-6 flex flex-col gap-0.5 text-[#222]">
          {#each ETAPES_KOXO as e, i (i)}<li>{i + 1} - {e}</li>{/each}
        </ol>
        <p class="mt-3 font-bold text-[#E00000] underline">ATTENTION :</p>
        <p class="font-bold">
          Le test d'existance d'un utilisateur est fait sur :<br />
          - Nom + Prénom (non accentué) + Date de naissance<br />
          - Ou sur le champ "ID unique"<br />
          &nbsp;(Si ce champ est vide, le test est fait sur le Nom + Prénom + Date de naissance)
        </p>
        <div class="mt-3 flex flex-col gap-1.5">
          <span class="flex items-center gap-3">
            <C genre="case" coche marque texte="Synchronisation non destructive (pas de suppression d'utilisateurs)" />
            <Repere n={3} />
          </span>
          <span class="ml-5"><C genre="case" coche marque texte="Désactiver les comptes orphelins (comptes non référencés dans la base fournie)" /></span>
          <C genre="case" texte="Archivage des utilisateurs dans un autre groupe primaire" />
          <div class="ml-5 flex max-w-[480px] flex-col gap-1 text-[#8E8E8E]">
            <span>Groupe primaire de l'archivage</span>
            <C genre="liste" grise />
            <span>Nommage des groupes secondaires</span>
            <C genre="liste" grise texte="%SECONDARY_GROUP% %YEAR%" />
            <C genre="case" grise coche texte="Désactiver les comptes archivés" />
          </div>
        </div>
        {#snippet boutons()}
          <span></span>
          <C genre="bouton" icone="suivant" texte="Suivant" />
        {/snippet}
      </Dialogue>
    </div>
  {:else if actuelle === "etape2"}
    <div role="img" aria-label="Étape 2 sur 8 : les champs du fichier du programme">
      <Dialogue titre="Synchronisation à partir d'un fichier texte (CSV) : Etape 2/8">
        <div class="relative rounded-[2px] border border-[#C5CFDA] px-2.5 pt-3 pb-2.5">
          <span class="absolute -top-2 left-2 bg-[#EEF4FB] px-1">Affectation des champs du fichier texte CSV</span>
          <span class="absolute -top-3 -right-3"><Repere n={4} /></span>
          <div class="grid grid-cols-[90px_minmax(0,1fr)_minmax(0,1fr)] gap-x-3 gap-y-1">
            <span>Titre (Civilité)</span><span>Nom</span><span>Prénom</span>
            <C genre="liste" texte="Vide" /><C genre="liste" marque texte="Champ 4" /><C genre="liste" marque texte="Champ 5" />
          </div>
          <div class="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-1">
            <span>Identifiant de connexion (Login)</span><span></span>
            <C genre="liste" marque texte="Champ 6" /><span></span>
            <span class="flex items-center justify-between">Mot de passe <span class="text-[#E8A317]">⚠</span></span><span></span>
            <C genre="liste" marque texte="Champ 8" /><span></span>
            <span>Date de naissance (ou identifiant)</span><span>ID unique (Numéro d'employé)</span>
            <C genre="liste" texte="Vide" /><C genre="liste" marque texte="Champ 7" />
          </div>
          <div class="mt-1.5 flex justify-end">
            <C genre="case" coche marque texte="Utiliser ce champ en priorité pour reconnaître l'utilisateur" />
          </div>
          <div class="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-[#C5CFDA] pt-2">
            <span>Email</span><span>Téléphone</span>
            <C genre="liste" marque texte="Champ 10" /><C genre="liste" texte="Vide" />
            <span class="col-span-2 text-[#8E8E8E]">Téléphone mobile, Fax, Page Web, Fonction, Alias, Photo… : Vide</span>
          </div>
          <div class="mt-2 grid grid-cols-2 items-end gap-x-3 gap-y-1 border-t border-[#C5CFDA] pt-2">
            <span>Groupe secondaire</span><span></span>
            <C genre="liste" marque texte="Champ 2" /><C genre="case" texte="Générer l'email associé automatiquement" />
            <span>Séparateur CSV</span><span></span>
            <C genre="liste" marque texte="Virgule" /><C genre="case" coche marque texte="Ignorer la première ligne" />
          </div>
        </div>
        <div class="mt-2 flex items-center gap-2">
          <span class="whitespace-nowrap">Exemple de ligne :</span>
          <span class="min-w-0 flex-1 truncate border border-[#ABADB3] bg-white px-1.5 py-0.5">{EXEMPLE}</span>
          <C genre="bouton" texte="Vérif." />
        </div>
        {#snippet boutons()}
          <C genre="bouton" icone="precedent" texte="Précédent" />
          <C genre="bouton" icone="suivant" texte="Suivant" />
        {/snippet}
      </Dialogue>
    </div>
    <p class="mt-2 text-xs text-stone-500 dark:text-stone-400">
      Le fichier du programme : 1 Groupe primaire · 2 Groupe secondaire · 3 Titre · 4 Nom · 5 Prénom ·
      6 Identifiant · 7 ID unique · 8 Mot de passe · 9 Date de naissance · 10 Email.
    </p>
  {:else}
    <!-- Étape 7/8 : la fenêtre qui s'ouvre au-dessus du journal, et qui
         décide de tout. Chiffres inventés, dans les proportions d'une rentrée
         de NDK (le 27 août 2026 : 383 créés, 386 désactivés). -->
    <div role="img" aria-label="Étape 7 sur 8 : Opérations à effectuer — comparer Créer et Désactiver à la prévision du contrôle, puis Oui ou Non">
      <div
        class="overflow-hidden rounded-[3px] border border-[#8C99AA] bg-white text-[12px] text-black shadow-[0_6px_20px_-8px_rgba(0,0,0,0.35)]"
        style="font-family: 'Segoe UI', Tahoma, sans-serif;"
      >
        <p class="px-3 py-2 text-[12.5px]">Synchronisation de groupe primaire : Opérations à effectuer</p>
        <div class="grid grid-cols-4 bg-[#F0F0F0] px-1 py-2.5">
          {#each [["Groupe primaire", "Elèves"], ["Utilisateurs actuels", "1000"], ["Dans le fichier", "1008"], ["À traiter", "1008"]] as [l, v], i (l)}
            <div class="px-3 {i ? 'border-l border-[#CFCFCF]' : ''}">
              <p class="text-[11px] text-[#555]">{l}</p>
              <p class="mt-1 text-[19px] font-bold">{v}</p>
            </div>
          {/each}
        </div>
        <div class="grid grid-cols-[150px_minmax(0,1fr)_140px] border-t border-[#D5D5D5]">
          <div class="flex flex-col gap-2 border-r border-[#D5D5D5] p-2.5">
            <p class="text-[10px] tracking-wide text-[#666]">SOURCES</p>
            <div class="rounded-[3px] bg-[#E8F0FB] px-2.5 py-1.5"><p class="text-[19px] font-bold text-[#2059A8]">1000</p><p class="text-[11px] text-[#555]">Base KoXo actuelle</p></div>
            <div class="rounded-[3px] bg-[#EEF7E8] px-2.5 py-1.5"><p class="text-[19px] font-bold text-[#3D7A1F]">1008</p><p class="text-[11px] text-[#555]">Fichier CSV importé</p></div>
          </div>
          <div class="relative flex flex-col gap-1.5 p-2.5">
            <p class="text-[10px] tracking-wide text-[#666]">OPÉRATIONS PLANIFIÉES</p>
            <span class="absolute top-6 -right-3 z-10"><Repere n={5} /></span>
            {#each [
              ["+", "Créer", 308, "#EEF7E8", "#3D7A1F", true],
              ["−", "Désactiver", 300, "#FBECEC", "#B42828", true],
              ["⇄", "Déplacer (intra-GP)", 650, "#E8F0FB", "#2059A8", false],
              ["↩", "Réintégrer (autre GP)", 0, "#F0ECFA", "#4B3A9A", false],
              ["■", "Ne pas supprimer", 0, "#FBF1E4", "#8A5300", false],
              ["↻", "Mettre à jour", 50, "#EAF6F0", "#1F6E4C", false],
            ] as [signe, libelle, n, fond, encre, cle] (libelle)}
              <div class="flex items-center gap-3 rounded-[3px] px-2.5 py-[5px] {cle ? 'outline outline-2 outline-[#FF7A59]' : ''}" style="background: {fond};">
                <span class="w-3 text-center" style="color: {encre};">{signe}</span>
                <span class="flex-1">{libelle}</span>
                <span class="font-bold" style="color: {encre};">{n}</span>
              </div>
            {/each}
          </div>
          <div class="border-l border-[#D5D5D5] p-2.5">
            <p class="text-[10px] tracking-wide text-[#666]">RÉSULTAT</p>
            <div class="mt-2 rounded-[3px] bg-[#EFEFEF] px-2 py-2 text-center"><p class="text-[11px] text-[#555]">Après synchronisation</p><p class="text-[21px] font-bold">1308</p></div>
          </div>
        </div>
        <div class="flex items-center justify-between border-t border-[#D5D5D5] bg-[#F7F7F7] px-3 py-2">
          <span class="text-[#555]">Lancer l'opération ?</span>
          <span class="flex gap-2">
            <span class="w-24 rounded-[2px] border border-[#ADADAD] bg-white py-1 text-center"><span class="underline">O</span>ui</span>
            <span class="w-24 rounded-[2px] border border-[#ADADAD] bg-white py-1 text-center"><span class="underline">N</span>on</span>
          </span>
        </div>
      </div>
    </div>
    <p class="mt-2 text-xs text-stone-500 dark:text-stone-400">
      Créer, ce sont les entrants ; Désactiver, les sortants — des centaines en août, c'est
      normal. Ce qui ne l'est pas : un chiffre différent de celui que le contrôle a annoncé.
    </p>
  {/if}
</Planches>
