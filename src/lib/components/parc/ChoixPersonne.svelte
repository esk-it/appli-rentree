<script>
  /**
   * Choisir une personne du référentiel, par son nom.
   *
   * La valeur est l'**adresse** : c'est elle que la console Google porte
   * dans l'étiquette, et c'est par elle que l'inventaire retrouve le nom.
   * Taper un nom à la main redonnait les variantes que l'ancien écran
   * devait ensuite rapprocher ; proposer le référentiel les évite.
   *
   * Un texte qui ne correspond à personne reste accepté (« VS Ste
   * Ursule », une salle) : le champ propose, il n'interdit pas.
   *
   * @typedef {Object} Props
   * @property {any[]} personnes - `{adresse, nom, prenom, type, detail}`
   * @property {string} valeur - bindable : l'adresse, ou le texte libre
   * @property {string} [id]
   * @property {string} [placeholder]
   * @property {boolean} [elevesAussi] - proposer aussi les élèves
   * @property {(p: any|null) => void} [onChoix]
   */
  /** @type {Props} */
  let {
    personnes = [],
    valeur = $bindable(""),
    id,
    placeholder = "Nom, prénom ou adresse…",
    elevesAussi = false,
    onChoix,
  } = $props();

  let saisie = $state("");
  let ouvert = $state(false);
  let surligne = $state(0);

  const plier = (s) =>
    String(s ?? "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase();

  let choisie = $derived(personnes.find((p) => p.adresse === valeur) ?? null);

  // Le champ montre le nom de la personne choisie, ou le texte libre.
  $effect(() => {
    if (!ouvert) saisie = choisie ? `${choisie.prenom} ${choisie.nom}` : valeur ?? "";
  });

  let propositions = $derived.by(() => {
    const q = plier(saisie).trim();
    if (q.length < 2) return [];
    const mots = q.split(/\s+/);
    return personnes
      .filter((p) => elevesAussi || p.type !== "eleve")
      .filter((p) => {
        const foin = plier(`${p.nom} ${p.prenom} ${p.adresse} ${p.detail ?? ""}`);
        return mots.every((m) => foin.includes(m));
      })
      .slice(0, 8);
  });

  function choisir(p) {
    valeur = p.adresse;
    saisie = `${p.prenom} ${p.nom}`;
    ouvert = false;
    onChoix?.(p);
  }

  function taper(e) {
    saisie = e.currentTarget.value;
    ouvert = true;
    surligne = 0;
    // Tant que rien n'est choisi, la valeur est le texte tapé.
    valeur = saisie.trim();
    onChoix?.(null);
  }

  function clavier(e) {
    if (!ouvert || !propositions.length) return;
    if (e.key === "ArrowDown") {
      surligne = (surligne + 1) % propositions.length;
      e.preventDefault();
    } else if (e.key === "ArrowUp") {
      surligne = (surligne - 1 + propositions.length) % propositions.length;
      e.preventDefault();
    } else if (e.key === "Enter") {
      choisir(propositions[surligne]);
      e.preventDefault();
    } else if (e.key === "Escape") {
      ouvert = false;
    }
  }
</script>

<div class="relative">
  <input
    {id}
    class="champ"
    autocomplete="off"
    {placeholder}
    value={saisie}
    oninput={taper}
    onkeydown={clavier}
    onfocus={() => (ouvert = true)}
    onblur={() => setTimeout(() => (ouvert = false), 150)}
  />
  {#if choisie}
    <p class="mt-1 truncate text-xs text-stone-500 dark:text-stone-400">
      {choisie.adresse}{#if choisie.detail} · {choisie.detail}{/if}
    </p>
  {:else if valeur && !propositions.length && !ouvert}
    <p class="mt-1 text-xs text-amber-700 dark:text-amber-400">
      Personne du référentiel ne porte ce nom : le texte sera gardé tel quel.
    </p>
  {/if}
  {#if ouvert && propositions.length}
    <ul
      class="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-lg border border-stone-200 bg-white py-1 shadow-lg dark:border-stone-700 dark:bg-stone-900"
      role="listbox"
    >
      {#each propositions as p, i (p.adresse)}
        <li>
          <button
            type="button"
            role="option"
            aria-selected={i === surligne}
            class="flex w-full items-baseline gap-2 px-3 py-1.5 text-left text-sm {i === surligne
              ? 'bg-stone-100 dark:bg-stone-800'
              : ''}"
            onmousedown={(e) => {
              e.preventDefault();
              choisir(p);
            }}
          >
            <span class="font-medium text-stone-900 dark:text-stone-100">{p.prenom} {p.nom}</span>
            <span class="truncate text-xs text-stone-500 dark:text-stone-400">
              {p.detail ?? (p.type === "eleve" ? "élève" : "")}
            </span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>
