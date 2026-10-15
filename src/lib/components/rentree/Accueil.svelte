<script>
  import Lock from "@lucide/svelte/icons/lock";
  import Bouton from "$lib/components/Bouton.svelte";

  /**
   * Avant la toute première étape : ce qui attend, ce qu'il faut sous la
   * main, et quand. Pour quelqu'un qui n'a jamais fait de rentrée — c'est
   * pour lui que l'assistant existe (maquette 7E).
   *
   * @typedef {Object} Props
   * @property {string} annee - la rentrée à préparer, « 2027-2028 »
   * @property {any[]} chapitres
   * @property {boolean} [occupe]
   * @property {boolean} [tropTot] - avant le 1er juillet : on ne peut que visiter
   * @property {string} [ouvreLe]  - ISO
   * @property {() => void} onCommencer
   * @property {() => void} onVisiter
   */
  /** @type {Props} */
  let { annee, chapitres, occupe = false, tropTot = false, ouvreLe = "", onCommencer, onVisiter } = $props();

  const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
  let ouverture = $derived.by(() => {
    if (!ouvreLe) return "";
    const [a, m, j] = ouvreLe.split("-").map(Number);
    return `${j === 1 ? "1er" : j} ${MOIS[m - 1]} ${a}`;
  });

  const SYSTEMES = [
    { court: "Ch", couleur: "#5F4DE8", nom: "Charlemagne", quoi: "le droit d'exporter les élèves et les professeurs" },
    { court: "Kx", couleur: "#16995F", nom: "KoXo", quoi: "administrateur sur NDK et sur SU" },
    { court: "G", couleur: "#2F6CE0", nom: "Console Google", quoi: "un compte administrateur" },
    { court: "Cs", couleur: "#D93A8C", nom: "CardStudio", quoi: "et l'imprimante à cartes" },
    { court: "Ts", couleur: "#C77F00", nom: "La centrale TS1000", quoi: "son export Users.xls" },
  ];
  const JALONS = [
    { quand: "20 → 26 août", couleur: "#8F80FF", quoi: "Ouvrir l'année, charger les élèves, créer les comptes" },
    { quand: "avant le 31 août", couleur: "#2F6CE0", quoi: "Google prêt pour la pré-rentrée" },
    { quand: "dès le 1er sept.", couleur: "#2BC4D8", quoi: "Les professeurs — un export pris plus tôt oublie les entrants" },
    { quand: "1re semaine", couleur: "#FF7A59", quoi: "Étiquettes, cartes, badges, PMB, Sodexo" },
  ];
</script>

<div class="grid min-h-[calc(100vh-9rem)] overflow-hidden rounded-2xl border border-stone-200 bg-white lg:grid-cols-[minmax(0,1fr)_480px] dark:border-stone-800 dark:bg-stone-950">
  <section class="flex flex-col px-8 py-10 lg:px-16 lg:py-14">
    <div class="flex gap-1.5">
      {#each chapitres as c (c.id)}
        <span class="h-1.5 w-10 rounded-full" style="background: {c.couleur};"></span>
      {/each}
    </div>
    <h1 class="titre-affiche mt-6 text-5xl leading-[1.02] text-stone-900 dark:text-stone-100">
      Ta rentrée {annee}&nbsp;?<br />On la fait ensemble.
    </h1>
    <p class="mt-5 max-w-xl text-[17px] leading-relaxed text-stone-600 dark:text-stone-300">
      Six chapitres, dix-huit étapes, toujours dans le même ordre. À chaque
      écran&nbsp;: ce qu'il faut faire, où cliquer, ce qui a changé — et rien ne
      part vers KoXo, Google ou Charlemagne sans ton clic.
    </p>
    <div class="mt-9 grid max-w-2xl grid-cols-3 gap-7">
      <div><p class="titre-affiche text-3xl text-stone-900 dark:text-stone-100">≈ 2 jours</p><p class="mt-0.5 text-[13px] text-stone-500 dark:text-stone-400">de travail, étalés du 20 août au 10 septembre</p></div>
      <div><p class="titre-affiche text-3xl text-stone-900 dark:text-stone-100">18</p><p class="mt-0.5 text-[13px] text-stone-500 dark:text-stone-400">étapes, qu'on reprend n'importe quand</p></div>
      <div><p class="titre-affiche text-3xl text-stone-900 dark:text-stone-100">0</p><p class="mt-0.5 text-[13px] text-stone-500 dark:text-stone-400">envoi sans ton accord</p></div>
    </div>
    <div class="mt-auto flex flex-col gap-3 pt-10">
      {#if tropTot}
        <p class="max-w-xl text-sm text-stone-600 dark:text-stone-300">
          La rentrée {annee} s'ouvre le <b class="text-stone-900 dark:text-stone-100">{ouverture}</b> :
          avant, ses étapes viseraient l'année qui tourne encore. D'ici là, tu peux
          la visiter — les dix-huit étapes, sans rien toucher.
        </p>
        <div><Bouton variante="primary" onclick={onVisiter}>Visiter les étapes →</Bouton></div>
      {:else}
        <div class="flex flex-wrap items-center gap-4">
          <Bouton variante="primary" {occupe} onclick={onCommencer}>
            Commencer la rentrée {annee} →
          </Bouton>
          <button type="button" class="text-sm font-semibold text-stone-600 hover:underline dark:text-stone-300" onclick={onVisiter}>
            Visiter d'abord, sans rien toucher
          </button>
        </div>
      {/if}
    </div>
  </section>

  <aside class="flex flex-col gap-8 border-t border-stone-200 bg-stone-50 px-8 py-10 lg:border-l lg:border-t-0 lg:px-12 dark:border-stone-800 dark:bg-stone-900/60">
    <div>
      <p class="libelle-champ">À avoir sous la main</p>
      <ul class="mt-2">
        {#each SYSTEMES as s (s.nom)}
          <li class="flex items-center gap-3 border-b border-stone-200 py-2.5 text-sm dark:border-stone-800">
            <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-xs font-extrabold text-white" style="background: {s.couleur};">{s.court}</span>
            <span><b class="text-stone-900 dark:text-stone-100">{s.nom}</b> <span class="text-stone-600 dark:text-stone-300">— {s.quoi}</span></span>
          </li>
        {/each}
        <li class="flex items-center gap-3 py-2.5 text-sm">
          <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900"><Lock class="h-4 w-4" /></span>
          <b class="text-stone-900 dark:text-stone-100">Le mot de passe du coffre</b>
        </li>
      </ul>
    </div>
    <div>
      <p class="libelle-champ">Quand</p>
      <ul class="mt-3 flex flex-col gap-3.5 text-sm">
        {#each JALONS as j (j.quand)}
          <li class="grid grid-cols-[110px_14px_minmax(0,1fr)] items-start gap-3">
            <b class="text-stone-900 dark:text-stone-100">{j.quand}</b>
            <span class="mt-1 h-3 w-3 rounded-full" style="background: {j.couleur};"></span>
            <span class="text-stone-600 dark:text-stone-300">{j.quoi}</span>
          </li>
        {/each}
      </ul>
    </div>
  </aside>
</div>
