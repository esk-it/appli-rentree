<script>
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import XCircle from "@lucide/svelte/icons/x-circle";
  import Info from "@lucide/svelte/icons/info";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import X from "@lucide/svelte/icons/x";
  import { notify, toasts } from "$lib/toasts.js";

  const ICONES = {
    succes: CheckCircle2,
    erreur: XCircle,
    info: Info,
    avertissement: AlertTriangle,
  };

  // Chaque ton a sa déclinaison sombre : sans elle, les toasts restaient
  // en fond clair sur une interface sombre, donc illisibles.
  const CLASSES = {
    succes:
      "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-100",
    erreur:
      "border-red-200 bg-red-50 text-red-900 dark:border-red-700 dark:bg-red-950 dark:text-red-100",
    info:
      "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-700 dark:bg-sky-950 dark:text-sky-100",
    avertissement:
      "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100",
  };

  const CLASSES_ICONE = {
    succes: "text-emerald-700 dark:text-emerald-400",
    erreur: "text-red-700 dark:text-red-400",
    info: "text-sky-700 dark:text-sky-400",
    avertissement: "text-amber-700 dark:text-amber-400",
  };
</script>

<div class="pointer-events-none fixed bottom-4 right-4 z-[200] flex w-80 flex-col-reverse gap-2">
  {#each $toasts as t (t.id)}
    {@const Icone = ICONES[t.type]}
    <div
      class="pointer-events-auto flex items-start gap-3 rounded-xl border px-3 py-2.5 shadow-lg animate-[slideup_180ms_ease-out] {CLASSES[t.type]}"
      role="alert"
    >
      <Icone class="mt-0.5 h-4 w-4 shrink-0 {CLASSES_ICONE[t.type]}" />
      <p class="flex-1 text-sm leading-tight">{t.message}</p>
      <button
        class="rounded p-0.5 opacity-60 transition-opacity hover:opacity-100"
        onclick={() => notify.retirer(t.id)}
        aria-label="Fermer la notification"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    </div>
  {/each}
</div>

<style>
  @keyframes slideup {
    from {
      transform: translateY(8px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
</style>
