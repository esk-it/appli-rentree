<script>
  import Construction from "@lucide/svelte/icons/construction";
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">Snapshots d'années</h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Historique brut des ingestions Charlemagne, rattaché à des `Personne` du référentiel.
    </p>
  </header>
  <div class="card border-amber-200 bg-amber-50/50 p-4 text-sm dark:border-amber-800 dark:bg-amber-900/20">
    <div class="flex items-start gap-3">
      <Construction class="mt-0.5 h-5 w-5 text-amber-700 dark:text-amber-400" />
      <div>
        <p class="font-medium text-amber-900 dark:text-amber-200">Sera reconstruit au Lot 3 (Ingestion unifiée)</p>
        <p class="mt-1 text-stone-700 dark:text-stone-300">
          L'ingestion Charlemagne peuplera les `Snapshot` (fusion des ex-`EleveSnapshot` et
          `AdulteSnapshot`), rattachés à leur `Personne` par la clé pivot `(type, id_charlemagne)`.
        </p>
      </div>
    </div>
  </div>
</section>
