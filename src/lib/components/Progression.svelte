<script>
  /**
   * Une barre de progression qui ne ment pas.
   *
   * ## Deux régimes, et pourquoi
   *
   * **Déterminé** — on connaît le total : 1 798 élèves à relever, 471
   * comptes à interroger. La barre avance pour de vrai et le compte est
   * écrit à côté. C'est le seul cas où un pourcentage est honnête.
   *
   * **Indéterminé** — lire un partage réseau, attendre Charlemagne : le
   * programme ne sait pas combien il reste. Une barre qui irait à 90 % en
   * deux secondes puis resterait là promettrait une fin qu'elle ignore. Le
   * trait va et vient : il dit « ça travaille », rien de plus.
   *
   * ## Pourquoi pas seulement un rond qui tourne
   *
   * Un indicateur qui tourne dit qu'on attend, jamais où l'on en est. Sur
   * un relevé de deux mille fichiers ou une bascule de huit cents comptes,
   * la différence entre « ça rame » et « il en reste trois cents » décide
   * si on va chercher un café ou si on ferme la fenêtre.
   *
   * @typedef {Object} Props
   * @property {number} [valeur]   - ce qui est fait
   * @property {number} [total]    - sur combien ; absent = indéterminé
   * @property {string} [libelle]  - ce qui se passe, en clair
   * @property {string} [detail]   - la ligne en cours, facultative
   * @property {string} [teinte]   - couleur de la famille concernée
   * @property {"sm"|"md"} [taille]
   */
  /** @type {Props} */
  let {
    valeur = 0,
    total = 0,
    libelle = "",
    detail = "",
    teinte = "var(--color-emerald-600)",
    taille = "md",
  } = $props();

  let determine = $derived(total > 0);
  let pourcent = $derived(
    determine ? Math.min(100, Math.max(0, (valeur / total) * 100)) : 0,
  );
  let hauteur = $derived(taille === "sm" ? "h-1" : "h-1.5");
</script>

<div class="flex flex-col gap-1.5" style="--teinte: {teinte};">
  {#if libelle || determine}
    <div class="flex items-baseline justify-between gap-3 text-xs">
      <span class="font-medium text-stone-700 dark:text-stone-200">{libelle}</span>
      {#if determine}
        <span class="shrink-0 font-mono text-stone-500 tabular-nums dark:text-stone-400">
          {valeur} / {total}
        </span>
      {/if}
    </div>
  {/if}

  <div
    class="{hauteur} w-full overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800"
    role="progressbar"
    aria-valuenow={determine ? Math.round(pourcent) : undefined}
    aria-valuemin="0"
    aria-valuemax="100"
    aria-label={libelle || "Progression"}
  >
    {#if determine}
      <div
        class="h-full rounded-full transition-[width] duration-300 ease-out"
        style="width: {pourcent}%; background: var(--teinte);"
      ></div>
    {:else}
      <!-- Pas de largeur : le trait traverse, il ne remplit pas. -->
      <div
        class="h-full w-1/3 rounded-full"
        style="background: var(--teinte); animation: va_et_vient 1.4s ease-in-out infinite;"
      ></div>
    {/if}
  </div>

  {#if detail}
    <p class="truncate text-[11px] text-stone-500 dark:text-stone-400">{detail}</p>
  {/if}
</div>
