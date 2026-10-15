<script>
  import Check from "@lucide/svelte/icons/check";
  import Lock from "@lucide/svelte/icons/lock";
  import Clock from "@lucide/svelte/icons/clock";
  import { CALENDRIER, CONTENU } from "$lib/rentree/etapes.js";

  /**
   * Le fil de la rentrée : où l'on en est, la prochaine étape, et le
   * calendrier des six chapitres (maquettes 7D et 7H). On y revient entre
   * deux journées ; le bouton « Reprendre » ramène là où on s'était arrêté.
   *
   * @typedef {Object} Props
   * @property {any} etat
   * @property {boolean} [visite]
   * @property {(vue: any) => void} onAller
   */
  /** @type {Props} */
  let { etat, visite = false, onAller } = $props();

  let an = $derived(Number(etat.annee.slice(0, 4)));
  const jourDe = (mmjj, decal = 0) => {
    const [m, j] = mmjj.split("-").map(Number);
    return new Date(an, m - 1, j + decal);
  };

  // Le calendrier : du 18 août au 12 septembre de l'année de la rentrée.
  let debut = $derived(new Date(an, 7, 18));
  let fin = $derived(new Date(an, 8, 13));
  const pos = (d) => Math.max(0, Math.min(100, (100 * (d.getTime() - debut.getTime())) / (fin.getTime() - debut.getTime())));
  let reperes = $derived([
    { d: new Date(an, 7, 18), texte: "18 août" },
    { d: new Date(an, 7, 22), texte: "22" },
    { d: new Date(an, 7, 26), texte: "26" },
    { d: new Date(an, 8, 1), texte: "1er sept." },
    { d: new Date(an, 8, 5), texte: "5" },
    { d: new Date(an, 8, 9), texte: "9" },
    { d: new Date(an, 8, 12), texte: "12" },
  ]);
  const aujourdhui = new Date();

  const finie = (e) => e.statut === "validee" || e.statut === "reportee";
  let parChapitre = $derived(
    etat.chapitres.map((c, i) => {
      const etapes = etat.etapes.filter((e) => e.chapitre === c.id);
      return { ...c, rang: i + 1, etapes, faites: etapes.filter(finie).length };
    }),
  );
  let nbChapitres = $derived(parChapitre.filter((c) => c.faites === c.etapes.length).length);
  let courante = $derived(etat.etapes.find((e) => e.id === etat.courante) ?? null);
  let chapitreCourant = $derived(parChapitre.find((c) => c.id === courante?.chapitre) ?? null);
  let nb = $derived(visite ? 0 : etat.nb_validees);

  let rythme = $derived.by(() => {
    if (visite) return `Une visite, pour voir le chemin avant de le prendre : la rentrée ${etat.annee} s'ouvre le 1er juillet ${an}.`;
    if (!courante) return `Les dix-huit étapes sont faites.`;
    const cal = CALENDRIER[courante.chapitre];
    const faits = nbChapitres
      ? `${nbChapitres} chapitre${nbChapitres > 1 ? "s" : ""} sur six terminé${nbChapitres > 1 ? "s" : ""}.`
      : "Aucun chapitre terminé pour l'instant.";
    if (aujourdhui > jourDe(cal.fin, 1) && aujourdhui.getFullYear() === an) {
      return `${faits} En retard sur les repères : « ${chapitreCourant.titre} » se faisait vers le ${jourDe(cal.debut).getDate()} ${jourDe(cal.debut).getMonth() === 7 ? "août" : "septembre"}.`;
    }
    return `${faits} Google doit être prêt avant la pré-rentrée du 31 août.`;
  });

  const STATUTS = {
    validee: "Validée",
    reportee: "Reportée",
    en_cours: "En cours",
    a_faire: "À faire",
    fermee: "Plus tard",
  };
  const jour = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "");
</script>

<div class="flex flex-col gap-10 rounded-2xl border border-stone-200 bg-white px-6 py-8 lg:px-12 lg:py-10 dark:border-stone-800 dark:bg-stone-950">
  <!-- Où l'on en est, et le bouton pour reprendre -->
  <section class="grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_420px]">
    <div class="flex items-center gap-7">
      <svg width="120" height="120" viewBox="0 0 120 120" role="img" aria-label="{nb} étapes validées sur {etat.etapes.length}" class="shrink-0">
        <circle cx="60" cy="60" r="50" fill="none" stroke-width="12" class="stroke-stone-200 dark:stroke-stone-800"></circle>
        <circle
          cx="60" cy="60" r="50" fill="none" stroke="#16995F" stroke-width="12" stroke-linecap="round"
          stroke-dasharray="{(314.16 * nb) / etat.etapes.length} 314.16" transform="rotate(-90 60 60)"
        ></circle>
        <text x="60" y="60" text-anchor="middle" class="titre-affiche fill-stone-900 dark:fill-stone-100" font-size="30" font-weight="800">{nb}</text>
        <text x="60" y="80" text-anchor="middle" class="fill-stone-500 dark:fill-stone-400" font-size="13">sur {etat.etapes.length}</text>
      </svg>
      <div class="min-w-0">
        <h1 class="titre-affiche text-4xl text-stone-900 dark:text-stone-100">La rentrée {etat.annee}</h1>
        <p class="mt-2 max-w-xl text-[15px] leading-relaxed text-stone-600 dark:text-stone-300">{rythme}</p>
      </div>
    </div>

    {#if visite}
      <div class="rounded-2xl bg-stone-50 px-5 py-4 dark:bg-stone-900">
        <p class="libelle-champ">La visite</p>
        <p class="mt-1 text-lg font-bold text-stone-900 dark:text-stone-100">Les 18 étapes, sans rien toucher</p>
        <button type="button" class="mt-3 rounded-full bg-stone-900 px-6 py-2.5 text-sm font-bold text-white hover:bg-stone-800 dark:bg-stone-100 dark:text-stone-900" onclick={() => onAller({ type: "etape", id: etat.etapes[0].id })}>
          Commencer la visite →
        </button>
      </div>
    {:else if courante}
      {@const c = chapitreCourant}
      <div class="rounded-2xl px-5 py-4" style="background: color-mix(in srgb, {c.couleur} 11%, transparent);">
        <p class="libelle-champ">Prochaine étape</p>
        <p class="mt-1 text-lg font-bold text-stone-900 dark:text-stone-100">{courante.rang} · {courante.titre}</p>
        <p class="mt-0.5 text-sm text-stone-600 dark:text-stone-300">{c.rang} · {c.titre} — {CONTENU[courante.id]?.duree}</p>
        <button
          type="button"
          class="mt-3 rounded-full px-6 py-2.5 text-sm font-bold text-white hover:brightness-110"
          style="background: color-mix(in srgb, {c.couleur} 58%, black);"
          onclick={() => onAller({ type: "etape", id: courante.id })}
        >
          {courante.statut === "a_faire" && courante.rang === 1 ? "Commencer →" : "Reprendre →"}
        </button>
      </div>
    {:else}
      <div class="rounded-2xl bg-vert-50 px-5 py-4 dark:bg-vert-900/30">
        <p class="libelle-champ">C'est fait</p>
        <p class="mt-1 text-lg font-bold text-stone-900 dark:text-stone-100">La rentrée {etat.annee} est bouclée</p>
        <button type="button" class="mt-3 rounded-full bg-vert-700 px-6 py-2.5 text-sm font-bold text-white hover:brightness-110" onclick={() => onAller({ type: "fin", chapitre: "clore" })}>
          Le bilan →
        </button>
      </div>
    {/if}
  </section>

  <!-- Le calendrier : chaque chapitre à sa place, du 18 août au 12 septembre -->
  <section aria-label="Calendrier des chapitres" class="overflow-x-auto">
    <div class="min-w-[760px]">
      <div class="grid grid-cols-[210px_minmax(0,1fr)]">
        <span></span>
        <div class="relative h-6">
          {#each reperes as r (r.texte)}
            <span class="absolute top-0 -translate-x-1/2 text-xs text-stone-400 tabular-nums" style="left: {pos(r.d)}%;">{r.texte}</span>
          {/each}
        </div>
      </div>
      <div class="relative">
        {#each parChapitre as c (c.id)}
          {@const cal = CALENDRIER[c.id]}
          {@const fait = !visite && c.faites === c.etapes.length}
          {@const encours = !visite && c.id === chapitreCourant?.id}
          {@const gauche = pos(jourDe(cal.debut))}
          {@const droite = pos(jourDe(cal.fin, 1))}
          <div class="grid h-12 grid-cols-[210px_minmax(0,1fr)] items-center border-b border-stone-100 dark:border-stone-900">
            <span class="flex items-center gap-2.5 truncate text-sm font-semibold text-stone-800 dark:text-stone-200">
              <span class="h-2.5 w-2.5 shrink-0 rounded-full" style="background: {c.couleur};"></span>
              {c.rang} · {c.titre}
            </span>
            <div class="relative h-full">
              <div
                class="absolute top-2.5 h-7 rounded-lg"
                style="left: {gauche}%; width: {droite - gauche}%;
                  background: {fait ? `color-mix(in srgb, ${c.couleur} 70%, black)` : `color-mix(in srgb, ${c.couleur} 30%, transparent)`};
                  {encours ? `box-shadow: inset 0 0 0 2px ${c.couleur};` : ''}"
              ></div>
              <!-- Le libellé à côté de la barre : une barre de deux jours ne le contient pas. -->
              <span
                class="absolute top-2.5 flex h-7 items-center px-2 text-xs font-bold whitespace-nowrap text-stone-700 dark:text-stone-200 {droite > 80 ? '-translate-x-full' : ''}"
                style="left: {droite > 80 ? gauche : droite}%;"
              >
                {#if fait}{c.faites}/{c.etapes.length} ✓{:else if !visite && c.faites}{c.faites}/{c.etapes.length}{:else}{c.etapes.length} étape{c.etapes.length > 1 ? "s" : ""}{/if}
              </span>
            </div>
          </div>
        {/each}
        <!-- La pré-rentrée, et aujourd'hui -->
        <div class="pointer-events-none absolute inset-y-0 right-0 left-[210px]">
          <span class="absolute inset-y-0 border-l-2 border-dashed border-red-400/70" style="left: {pos(new Date(an, 7, 31))}%;">
            <span class="absolute -bottom-5 -translate-x-1/2 text-[11px] font-semibold whitespace-nowrap text-red-600 dark:text-red-400">pré-rentrée</span>
          </span>
          {#if aujourdhui >= debut && aujourdhui < fin}
            <span class="absolute inset-y-0 border-l-2 border-stone-900 dark:border-stone-100" style="left: {pos(aujourdhui)}%;">
              <span class="absolute -top-5 -translate-x-1/2 text-[11px] font-bold whitespace-nowrap text-stone-900 dark:text-stone-100">aujourd'hui</span>
            </span>
          {/if}
        </div>
      </div>
      <p class="mt-8 text-[13px] text-stone-500 dark:text-stone-400">
        Les dates sont des repères tirés de la rentrée 2026 : ce qui compte, c'est l'ordre.
      </p>
    </div>
  </section>

  <!-- Les 18 étapes -->
  <section aria-label="Les étapes" class="grid gap-x-10 gap-y-7 md:grid-cols-2 xl:grid-cols-3">
    {#each parChapitre as c (c.id)}
      <div>
        <p class="flex items-center gap-2 text-sm font-bold text-stone-900 dark:text-stone-100">
          <span class="h-2.5 w-2.5 rounded-full" style="background: {c.couleur};"></span>
          {c.rang} · {c.titre}
        </p>
        <ul class="mt-2">
          {#each c.etapes as e (e.id)}
            {@const ouvrable = visite || e.statut !== "fermee"}
            <li>
              <button
                type="button"
                disabled={!ouvrable}
                class="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left text-sm transition-colors enabled:hover:bg-stone-100 disabled:cursor-default dark:enabled:hover:bg-stone-900"
                onclick={() => onAller({ type: "etape", id: e.id })}
              >
                <span
                  class="grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-bold
                    {!visite && e.statut === 'validee' ? 'text-white' : 'border border-stone-300 text-stone-500 dark:border-stone-700 dark:text-stone-400'}"
                  style={!visite && e.statut === "validee" ? `background: color-mix(in srgb, ${c.couleur} 70%, black);` : ""}
                >
                  {#if !visite && e.statut === "validee"}<Check class="h-3.5 w-3.5" strokeWidth={3} />
                  {:else if !visite && e.statut === "fermee"}<Lock class="h-3 w-3" />
                  {:else if !visite && e.statut === "reportee"}<Clock class="h-3 w-3" />
                  {:else}{e.rang}{/if}
                </span>
                <span class="min-w-0 flex-1 {!visite && e.statut === 'fermee' ? 'text-stone-400 dark:text-stone-500' : 'text-stone-800 dark:text-stone-200'} {e.id === etat.courante && !visite ? 'font-bold' : ''}">{e.titre}</span>
                {#if !visite}
                  <span class="shrink-0 text-xs text-stone-500 dark:text-stone-400">
                    {e.statut === "validee" ? jour(e.validee_le) : e.id === etat.courante ? STATUTS[e.statut] : e.statut === "reportee" ? STATUTS.reportee : ""}
                  </span>
                {/if}
              </button>
            </li>
          {/each}
        </ul>
      </div>
    {/each}
  </section>
</div>
