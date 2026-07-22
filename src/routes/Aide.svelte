<script>
  import Construction from "@lucide/svelte/icons/construction";
  import BookOpen from "@lucide/svelte/icons/book-open";
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">Aide</h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      La documentation complète sera écrite au dernier lot, en cohérence avec le nouveau
      parcours utilisateur.
    </p>
  </header>

  <div class="card border-amber-200 bg-amber-50/50 p-4 text-sm dark:border-amber-800 dark:bg-amber-900/20">
    <div class="flex items-start gap-3">
      <Construction class="mt-0.5 h-5 w-5 text-amber-700 dark:text-amber-400" />
      <div>
        <p class="font-medium text-amber-900 dark:text-amber-200">Refonte identité en cours (v0.22.x → v1.0.0)</p>
        <p class="mt-1 text-stone-700 dark:text-stone-300">
          Chaque lot ajoute une couche du référentiel : identité, ingestion unifiée,
          réconciliation, arbitrage, simulation, puis les modules de traitement (KoXo,
          Google, PMB, JPM, CardStudio) sur la nouvelle logique.
        </p>
      </div>
    </div>
  </div>

  <div class="card p-4 text-sm dark:text-stone-300">
    <div class="mb-2 flex items-center gap-2 font-semibold text-stone-700 dark:text-stone-200">
      <BookOpen class="h-4 w-4" />
      Références internes
    </div>
    <ul class="ml-5 list-disc space-y-1 text-stone-600 dark:text-stone-400">
      <li><code>docs/gestion-rentree-logique.md</code> — raisonnement métier</li>
      <li><code>docs/fonctionnement-programme-rentree.md</code> — déroulé opérationnel</li>
      <li><code>docs/prompt-claude-code-refonte.md</code> — cadre de la refonte</li>
    </ul>
  </div>
</section>
