<script>
  import { onMount } from "svelte";
  import Upload from "@lucide/svelte/icons/upload";
  import FileSpreadsheet from "@lucide/svelte/icons/file-spreadsheet";
  import Users from "@lucide/svelte/icons/users";
  import UserPlus from "@lucide/svelte/icons/user-plus";
  import Building2 from "@lucide/svelte/icons/building-2";
  import GraduationCap from "@lucide/svelte/icons/graduation-cap";
  import { charlemagne } from "$lib/api.js";
  import StatCard from "$lib/components/StatCard.svelte";
  import DataTable from "$lib/components/DataTable.svelte";

  let fichiers = $state(/** @type {Array<{nom: string, taille_octets: number}>} */ ([]));
  let fichierSelectionne = $state("");
  let apercu = $state(/** @type {null | {nb_lignes_total: number, colonnes: string[], lignes: object[], stats: object}} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  /** @type {HTMLInputElement | null} */
  let inputFichier = $state(null);

  const libellesColonnes = {
    nom_etablissement: "Établissement",
    code_etablissement: "Code étab.",
    code_niveau: "Niveau",
    code_classe: "Classe",
    num_badge: "Badge",
    code_regime: "Régime",
    nom: "Nom",
    prenom: "Prénom",
    nouvel_eleve: "Statut",
    date_entree: "Entrée",
  };

  onMount(rafraichirListe);

  async function rafraichirListe() {
    try {
      fichiers = await charlemagne.listerFichiers();
      if (fichiers.length && !fichierSelectionne) {
        fichierSelectionne = fichiers[0].nom;
        await chargerApercu();
      }
    } catch (e) {
      erreur = String(e);
    }
  }

  async function chargerApercu() {
    if (!fichierSelectionne) return;
    chargement = true;
    erreur = "";
    try {
      apercu = await charlemagne.apercu(fichierSelectionne, 2000);
    } catch (e) {
      erreur = String(e);
      apercu = null;
    } finally {
      chargement = false;
    }
  }

  async function uploaderFichier(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    chargement = true;
    erreur = "";
    try {
      await charlemagne.upload(f);
      await rafraichirListe();
      fichierSelectionne = f.name;
      await chargerApercu();
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
      if (inputFichier) inputFichier.value = "";
    }
  }
</script>

<section class="space-y-6">
  <header class="flex items-end justify-between gap-4">
    <div>
      <h1 class="text-2xl font-semibold text-stone-900">Import de l'export Charlemagne</h1>
      <p class="mt-1 text-sm text-stone-600">
        Charge le fichier exporté depuis Charlemagne pour démarrer la rentrée. L'app analysera les
        données et te permettra de générer les imports vers KoXo, PMB, Google, SmartAir et CardStudio.
      </p>
    </div>
  </header>

  <div class="card p-4">
    <div class="flex flex-wrap items-center gap-3">
      <select
        bind:value={fichierSelectionne}
        onchange={chargerApercu}
        class="rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
      >
        <option value="">— Choisir un fichier —</option>
        {#each fichiers as f (f.nom)}
          <option value={f.nom}>{f.nom} ({(f.taille_octets / 1024).toFixed(0)} Ko)</option>
        {/each}
      </select>

      <label class="btn-secondary cursor-pointer">
        <Upload class="h-4 w-4" />
        Déposer un nouveau fichier
        <input
          bind:this={inputFichier}
          type="file"
          accept=".htm,.html,.xlsx,.xls"
          onchange={uploaderFichier}
          class="hidden"
        />
      </label>

      <button class="btn-secondary" onclick={rafraichirListe}>
        <FileSpreadsheet class="h-4 w-4" />
        Rafraîchir la liste
      </button>
    </div>

    {#if erreur}
      <p class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erreur}</p>
    {/if}
  </div>

  {#if chargement}
    <div class="card p-8 text-center text-stone-500">
      <p>Analyse de l'export en cours…</p>
    </div>
  {:else if apercu}
    <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatCard
        label="Élèves chargés"
        value={apercu.nb_lignes_total.toLocaleString("fr-FR")}
        icon={Users}
      />
      {#if apercu.stats.nouveaux !== undefined}
        <StatCard
          label="Nouveaux (flag Charlemagne)"
          value={apercu.stats.nouveaux.toLocaleString("fr-FR")}
          variante="success"
          icon={UserPlus}
        />
      {/if}
      {#if apercu.stats.par_etablissement}
        <StatCard
          label="Établissements"
          value={Object.keys(apercu.stats.par_etablissement).length}
          variante="info"
          icon={Building2}
          hint={Object.entries(apercu.stats.par_etablissement)
            .map(([k, v]) => `${v} en ${shortName(k)}`)
            .join(" · ")}
        />
      {/if}
      {#if apercu.stats.par_niveau}
        <StatCard
          label="Niveaux distincts"
          value={Object.keys(apercu.stats.par_niveau).length}
          icon={GraduationCap}
        />
      {/if}
    </div>

    <DataTable
      colonnes={apercu.colonnes}
      lignes={apercu.lignes}
      libelles={libellesColonnes}
    />
  {:else}
    <div class="card p-8 text-center text-stone-500">
      <p>Aucun fichier chargé. Dépose un export Charlemagne (.htm ou .xlsx) pour démarrer.</p>
    </div>
  {/if}
</section>

<script module>
  /** Raccourcit le nom d'un établissement pour l'affichage compact. */
  export function shortName(nom) {
    if (!nom) return "";
    if (nom.includes("SAINTE-URSULE")) return "SU";
    if (nom.includes("KREISKER")) return nom.includes("L.P.") ? "LP" : "LY";
    if (nom.includes("ESPERANCE")) return "NDE";
    return nom.slice(0, 8);
  }
</script>
