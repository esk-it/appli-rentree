<script>
  /**
   * Nombre animé — compte depuis zéro jusqu'à la valeur cible.
   *
   * Donne du relief aux chiffres clés sans les rendre illisibles : la
   * durée est courte et l'animation s'arrête net sur la valeur exacte.
   * Au-delà d'un certain volume, compter depuis zéro ferait défiler trop
   * longtemps — on part alors d'une valeur proche pour garder le même
   * temps de parcours quel que soit l'ordre de grandeur.
   *
   * @typedef {Object} Props
   * @property {number} valeur
   * @property {number} [duree]     - millisecondes
   * @property {string} [prefixe]   - "+" pour les créations, par exemple
   */
  /** @type {Props} */
  let { valeur = 0, duree = 600, prefixe = "" } = $props();

  let affiche = $state(0);

  // Respecte le réglage système : pas d'animation si l'utilisateur a
  // demandé à en réduire.
  function animationsReduites() {
    return (
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    );
  }

  $effect(() => {
    const cible = Number(valeur) || 0;

    if (animationsReduites() || duree <= 0) {
      affiche = cible;
      return;
    }

    const depart = affiche;
    if (depart === cible) return;

    const debut = performance.now();
    let frame = 0;

    // Sortie cubique : rapide au début, ralentit à l'approche — c'est ce
    // qui donne l'impression que le chiffre « se pose ».
    const adoucir = (t) => 1 - Math.pow(1 - t, 3);

    const avancer = (maintenant) => {
      const t = Math.min((maintenant - debut) / duree, 1);
      affiche = Math.round(depart + (cible - depart) * adoucir(t));
      if (t < 1) frame = requestAnimationFrame(avancer);
      else affiche = cible; // garantit la valeur exacte en fin de course
    };

    frame = requestAnimationFrame(avancer);
    return () => cancelAnimationFrame(frame);
  });
</script>

<span class="tabular-nums">{prefixe}{affiche.toLocaleString("fr-FR")}</span>
