<script>
  import FlaskConical from "@lucide/svelte/icons/flask-conical";
  import { repetition, quitterLaRepetition, dateCopie } from "$lib/repetition.svelte.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Le rappel permanent d'une répétition en cours : tout ce qu'on fait ici
   * se fait sur une copie. Rayé comme un ruban de chantier — il ne doit
   * pas pouvoir passer pour un bandeau d'information ordinaire.
   */
  let sortie = $state(false);

  async function quitter() {
    sortie = true;
    try {
      await quitterLaRepetition();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
      sortie = false;
    }
  }
</script>

{#if repetition.active}
  <div
    role="status"
    class="ruban sticky top-0 z-30 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-amber-500/60 px-6 py-2 text-sm text-amber-950"
  >
    <span class="inline-flex items-center gap-2 rounded-full bg-amber-950 px-3 py-0.5 text-xs font-bold tracking-[0.08em] text-amber-100 uppercase">
      <FlaskConical class="h-3.5 w-3.5" /> Répétition
    </span>
    <span class="min-w-0 flex-1">
      Tu travailles sur une copie de ta base, prise le {dateCopie(repetition.copiee_le)}.
      Google n'est que lu ; ta vraie base ne bouge pas.
    </span>
    <button
      type="button"
      class="rounded-full bg-amber-950 px-4 py-1 text-xs font-bold text-amber-50 hover:bg-amber-900 disabled:opacity-50"
      disabled={sortie}
      onclick={quitter}
    >
      Quitter la répétition
    </button>
  </div>
{/if}

<style>
  .ruban {
    background: repeating-linear-gradient(
      -45deg,
      #fcd34d,
      #fcd34d 14px,
      #fde68a 14px,
      #fde68a 28px
    );
  }
</style>
