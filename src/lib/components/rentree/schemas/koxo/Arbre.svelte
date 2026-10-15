<script>
  import Repere from "../Repere.svelte";

  /**
   * L'arbre de gauche de KoXo : les groupes primaires sous « Utilisateurs ».
   *
   * @typedef {Object} Props
   * @property {string|null} [selection]
   * @property {number|null} [repere] - le repère posé sur la sélection
   */
  /** @type {Props} */
  let { selection = "Elèves", repere = null } = $props();

  const NOEUDS = [
    { nom: "Utilisateurs", niveau: 0, ouvert: true },
    { nom: "Admins Ordinateurs", niveau: 1 },
    { nom: "Archives", niveau: 1 },
    { nom: "Elèves", niveau: 1 },
    { nom: "Professeurs", niveau: 1 },
    { nom: "Espaces partagés", niveau: 0, feuille: true },
    { nom: "Lieux de stockage", niveau: 0 },
    { nom: "Modèles", niveau: 0 },
  ];
</script>

<div class="h-full bg-[#BCD4EC] py-1 pr-1">
  {#each NOEUDS as n (n.nom)}
    <div class="flex items-center gap-1 py-[1px] whitespace-nowrap" style="padding-left: {4 + n.niveau * 14}px;">
      <span class="w-2.5 text-[9px] text-[#4A5A6A]">{n.feuille ? "" : n.ouvert ? "⌄" : "›"}</span>
      <span class="inline-block h-[10px] w-[13px] shrink-0 rounded-[1px] border border-[#B8961E] bg-[#F3CC52]"></span>
      <span class="px-0.5 {n.nom === selection ? 'bg-[#E3EDF8] outline outline-1 outline-[#8FB3DA]' : ''}">{n.nom}</span>
      {#if repere && n.nom === selection}<Repere n={repere} />{/if}
    </div>
  {/each}
</div>
