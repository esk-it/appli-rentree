<script>
  import Check from "@lucide/svelte/icons/check";
  import { teinteCourante } from "$lib/ecran.svelte.js";

  /**
   * Un ruban d'étapes numérotées, pour un geste qui s'en fait en deux.
   *
   * ## Pourquoi pas des onglets
   *
   * Des onglets disent « deux vues du même sujet, choisis celle que tu
   * veux voir ». Ici l'ordre compte : la bascule définitive échoue si le
   * placement en pré-OU n'a pas eu lieu, parce que les comptes ne sont pas
   * là où le programme les cherche.
   *
   * Le ruban dit ce qu'un onglet ne dit pas — qu'il y a un avant et un
   * après, et où l'on en est. On peut quand même revenir en arrière : les
   * pastilles restent cliquables, parce qu'on relance parfois un placement
   * pour les retardataires une semaine après la rentrée.
   *
   * ## Une étape faite porte une coche, pas son numéro
   *
   * Le numéro sert à se repérer dans l'ordre ; une fois l'étape passée, ce
   * qu'on veut savoir est qu'elle est passée. La coche le dit sans qu'on
   * ait à comparer deux teintes.
   *
   * @typedef {Object} Etape
   * @property {string} id
   * @property {string} label
   * @property {boolean} [faite]
   *
   * @typedef {Object} Props
   * @property {Etape[]} etapes
   * @property {string} valeur - bindable, l'étape ouverte
   * @property {(id: string) => void} [onChange]
   */
  /** @type {Props} */
  let { etapes = [], valeur = $bindable(), onChange } = $props();

  let couleur = $derived(teinteCourante());

  function choisir(id) {
    if (id === valeur) return;
    valeur = id;
    onChange?.(id);
  }
</script>

<div class="flex flex-wrap items-center gap-x-3.5 gap-y-2">
  {#each etapes as e, i (e.id)}
    {#if i > 0}
      <span class="h-px w-12 shrink-0 bg-stone-200 dark:bg-stone-700" aria-hidden="true"></span>
    {/if}
    <button
      type="button"
      class="flex items-center gap-2.5 text-[15px] transition-colors
             {e.id === valeur
               ? 'font-semibold text-stone-900 dark:text-stone-100'
               : 'font-medium text-stone-500 hover:text-stone-700 dark:text-stone-400 dark:hover:text-stone-200'}"
      aria-current={e.id === valeur ? "step" : undefined}
      onclick={() => choisir(e.id)}
    >
      <span
        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[13px] font-bold"
        style={e.id === valeur
          ? `background: ${couleur}; color: #fff;`
          : e.faite
            ? "background: var(--color-vert-100); color: var(--color-vert-700);"
            : ""}
        class:bg-stone-200={e.id !== valeur && !e.faite}
        class:text-stone-600={e.id !== valeur && !e.faite}
        class:dark:bg-stone-800={e.id !== valeur && !e.faite}
        class:dark:text-stone-300={e.id !== valeur && !e.faite}
      >
        {#if e.faite && e.id !== valeur}
          <Check class="h-4 w-4" />
        {:else}
          {i + 1}
        {/if}
      </span>
      {e.label}
    </button>
  {/each}
</div>
