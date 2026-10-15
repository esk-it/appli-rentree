<script>
  import Repere from "./Repere.svelte";

  /**
   * La fenêtre d'import de KoXo Administrateur, redessinée : trois
   * repères, rien d'autre (maquette 7F). Volontairement en clair, quel que
   * soit le thème : c'est l'écran d'un autre logiciel.
   *
   * Les chiffres du résumé ne sont pas inventés : KoXo les donne, et c'est
   * à eux qu'on compare ce que le programme attend.
   *
   * @typedef {Object} Props
   * @property {string} [base]
   */
  /** @type {Props} */
  let { base = "NDK" } = $props();
</script>

<div
  role="img"
  aria-label="Schéma de KoXo Administrateur : menu Importer, mode de synchronisation, résumé avant de lancer"
  class="max-w-3xl overflow-hidden rounded-xl border border-[#DCD8EA] bg-white text-[#1E1B3A] shadow-sm"
>
  <div class="flex h-8 items-center gap-1.5 bg-[#EEF0F4] px-3 text-xs text-[#5B6070]">
    <span class="h-2.5 w-2.5 rounded-full bg-[#D0D4DC]"></span>
    <span class="h-2.5 w-2.5 rounded-full bg-[#D0D4DC]"></span>
    <span class="ml-2 font-semibold">KoXo Administrateur — {base}</span>
  </div>
  <div class="grid min-h-[300px] grid-cols-[150px_minmax(0,1fr)] sm:grid-cols-[170px_minmax(0,1fr)]">
    <div class="flex flex-col gap-1.5 border-r border-[#E3E6EC] bg-[#F5F6F8] px-2.5 py-3 text-[13px] text-[#5B6070]">
      <span>Tableau de bord</span>
      <span class="font-bold text-[#1E1B3A]">Utilisateurs</span>
      <span class="ml-2 flex items-center justify-between rounded-md bg-[#FFE6DE] px-2 py-1 font-bold text-[#1E1B3A]">
        Importer <Repere n={1} />
      </span>
      <span class="ml-4">Exporter</span>
      <span>Groupes</span>
      <span>Stations</span>
    </div>
    <div class="px-5 py-4">
      <p class="text-sm font-bold">Importer des utilisateurs</p>
      <div class="mt-3 flex items-center gap-2.5 text-[13px]">
        <span class="w-16 shrink-0 text-[#5B6070]">Fichier</span>
        <span class="min-w-0 flex-1 truncate rounded-md border border-[#D9DCE3] px-2.5 py-1.5">KoXo_{base}.csv</span>
      </div>
      <div class="mt-2.5 flex items-center gap-2.5 text-[13px]">
        <span class="w-16 shrink-0 text-[#5B6070]">Mode</span>
        <span class="min-w-0 flex-1 rounded-md border-2 border-[#FF7A59] px-2.5 py-1 font-bold">Synchronisation non destructive</span>
        <Repere n={2} />
      </div>
      <div class="relative mt-4 grid grid-cols-3 gap-2 rounded-lg border-2 border-[#FF7A59] px-3.5 py-3 text-[13px]">
        <div><p class="text-[#5B6070]">Créer</p><p class="text-xl font-extrabold text-[#9A98AC]">n</p></div>
        <div><p class="text-[#5B6070]">Modifier</p><p class="text-xl font-extrabold text-[#9A98AC]">n</p></div>
        <div><p class="text-[#5B6070]">Désactiver</p><p class="text-xl font-extrabold">0</p></div>
        <span class="absolute -right-3 -top-3"><Repere n={3} /></span>
      </div>
      <div class="mt-3.5 flex justify-end">
        <span class="rounded-md bg-[#2F6CE0] px-4 py-1.5 text-[13px] font-bold text-white">Lancer</span>
      </div>
    </div>
  </div>
</div>
