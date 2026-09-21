<script>
  /**
   * État vide — remplace les « Aucun résultat » en texte brut.
   *
   * Un écran vide doit dire trois choses : ce qui est vide, pourquoi, et
   * quoi faire ensuite. Le troisième point est le plus souvent oublié et
   * c'est celui qui débloque réellement l'utilisateur.
   *
   * @typedef {Object} Props
   * @property {any} [icon]        - composant Lucide
   * @property {string} titre
   * @property {string} [message]  - explication ou action suggérée
   * @property {"neutre"|"succes"|"attention"} [ton]
   * @property {import('svelte').Snippet} [children] - bouton d'action optionnel
   */
  /** @type {Props} */
  let { icon: Icon, titre, message = "", ton = "neutre", children } = $props();

  import { teinteCourante } from "$lib/ecran.svelte.js";

  /**
   * Le ton neutre prend la couleur de l'écran plutôt qu'un gris.
   *
   * Un écran vide est le premier que l'on voit en arrivant : c'est le
   * moment où l'identité du module doit se poser, pas celui où tout
   * devient gris. Les deux autres tons gardent la leur — un succès est
   * vert et un avertissement ambre, quel que soit l'écran.
   */
  const TONS = {
    succes: "var(--color-fam-koxo)",
    attention: "var(--color-amber-500)",
  };

  let couleur = $derived(TONS[ton] ?? teinteCourante());
</script>

<div
  class="anim-apparition rounded-3xl p-10 text-center"
  style="--teinte: {couleur}; background: color-mix(in oklab, {couleur} 7%, transparent);"
>
  {#if Icon}
    <span class="plaque-icone mx-auto mb-4 h-14 w-14">
      <Icon class="h-7 w-7" style="stroke-width: 1.6;" />
    </span>
  {/if}
  <p class="titre-affiche text-lg" style="color: {couleur};">{titre}</p>
  {#if message}
    <p class="mx-auto mt-2 max-w-md text-sm leading-relaxed text-stone-600 dark:text-stone-400">
      {message}
    </p>
  {/if}
  {#if children}
    <div class="mt-5 flex justify-center gap-2">
      {@render children()}
    </div>
  {/if}
</div>
