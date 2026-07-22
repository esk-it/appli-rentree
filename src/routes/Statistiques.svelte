<script>
  import Construction from "@lucide/svelte/icons/construction";
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">Statistiques</h1>
  </header>
  <div class="card border-amber-200 bg-amber-50/50 p-4 text-sm dark:border-amber-800 dark:bg-amber-900/20">
    <div class="flex items-start gap-3">
      <Construction class="mt-0.5 h-5 w-5 text-amber-700 dark:text-amber-400" />
      <div>
        <p class="font-medium text-amber-900 dark:text-amber-200">Sera reconstruit au Lot 13</p>
        <p class="mt-1 text-stone-700 dark:text-stone-300">
          Couche de comptages générique sur le référentiel — extensible sans modifier le modèle
          de données. Effectifs par site/niveau/classe, comparaison N vs N-1, mouvements,
          quarantaines, anomalies (photos orphelines, classes hors table…).
        </p>
      </div>
    </div>
  </div>
</section>
