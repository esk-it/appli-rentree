<script>
  import { onMount } from "svelte";
  import GraduationCap from "@lucide/svelte/icons/graduation-cap";
  import Home from "@lucide/svelte/icons/home";
  import Database from "@lucide/svelte/icons/database";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Key from "@lucide/svelte/icons/key";
  import BookOpen from "@lucide/svelte/icons/book-open";
  import Globe from "@lucide/svelte/icons/globe";
  import IdCard from "@lucide/svelte/icons/id-card";
  import Settings from "@lucide/svelte/icons/settings";
  import Accueil from "./routes/Accueil.svelte";
  import { attendreBackend } from "$lib/api.js";

  let backendOk = $state(/** @type {null | boolean} */ (null));
  let versionBackend = $state("");
  let messageDemarrage = $state("Démarrage du backend…");
  let erreurDemarrage = $state("");

  // Page courante (très simple pour l'instant — on basculera sur svelte-spa-router quand on aura plus de routes)
  let page = $state("accueil");

  onMount(async () => {
    try {
      // Le sidecar Python (PyInstaller) met quelques secondes à se lancer à froid.
      // On retry jusqu'à ce qu'il réponde.
      const h = await attendreBackend({ maxTentatives: 30, baseDelai: 300 });
      backendOk = h.ok;
      versionBackend = h.version;
    } catch (e) {
      backendOk = false;
      erreurDemarrage = e instanceof Error ? e.message : String(e);
    }
  });

  const navItems = [
    { id: "accueil", label: "Accueil", icon: Home, dispo: true },
    { id: "comparaison", label: "Comparaison N vs N-1", icon: Database, dispo: false },
    { id: "koxo", label: "KoXo", icon: Key, dispo: false },
    { id: "google", label: "Google Workspace", icon: Globe, dispo: false },
    { id: "pmb", label: "PMB (CDI)", icon: BookOpen, dispo: false },
    { id: "smartair", label: "SmartAir (accès)", icon: IdCard, dispo: false },
    { id: "cardstudio", label: "CardStudio (badges)", icon: Users2, dispo: false },
    { id: "parametres", label: "Paramètres", icon: Settings, dispo: false },
  ];
</script>

{#if backendOk === null}
  <!-- Écran de démarrage : on attend que le sidecar Python soit prêt -->
  <div class="flex h-screen items-center justify-center bg-stone-50">
    <div class="flex flex-col items-center gap-4 text-center">
      <div class="h-12 w-12 animate-spin rounded-full border-4 border-stone-200 border-t-emerald-700"></div>
      <div>
        <p class="text-lg font-semibold text-stone-900">Appli Rentrée</p>
        <p class="mt-1 text-sm text-stone-500">{messageDemarrage}</p>
      </div>
    </div>
  </div>
{:else if backendOk === false}
  <!-- Backend injoignable : on explique au lieu d'un écran blanc -->
  <div class="flex h-screen items-center justify-center bg-stone-50 px-8">
    <div class="card max-w-xl space-y-4 p-6">
      <h2 class="text-xl font-semibold text-red-700">Backend injoignable</h2>
      <p class="text-sm text-stone-700">
        Le sidecar Python n'a pas répondu après plusieurs tentatives. Cela peut venir d'un
        antivirus qui bloque <code>backend.exe</code>, du port 8020 déjà utilisé, ou d'un
        plantage interne du backend.
      </p>
      {#if erreurDemarrage}
        <pre class="overflow-x-auto rounded-lg bg-stone-100 p-3 text-xs text-stone-700 whitespace-pre-wrap">{erreurDemarrage}</pre>
      {/if}
      <p class="text-sm text-stone-700">
        Vérifie qu'aucun autre programme n'utilise le port 8020, et relance l'application.
      </p>
      <button class="btn-primary" onclick={() => location.reload()}>Réessayer</button>
    </div>
  </div>
{:else}
<div class="flex h-screen overflow-hidden">
  <!-- Barre latérale -->
  <aside class="flex w-64 shrink-0 flex-col border-r border-stone-200 bg-white">
    <div class="flex items-center gap-2 border-b border-stone-200 px-5 py-4">
      <GraduationCap class="h-7 w-7 text-emerald-700" />
      <div class="flex flex-col leading-tight">
        <span class="text-sm font-semibold text-stone-900">Appli Rentrée</span>
        <span class="text-xs text-stone-500">Ensemble Scolaire du Kreisker</span>
      </div>
    </div>

    <nav class="flex-1 space-y-0.5 p-3">
      {#each navItems as item (item.id)}
        <button
          class="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium transition
                 {page === item.id ? 'bg-emerald-50 text-emerald-800' : 'text-stone-700 hover:bg-stone-50'}
                 {!item.dispo ? 'opacity-40 cursor-not-allowed' : ''}"
          disabled={!item.dispo}
          onclick={() => item.dispo && (page = item.id)}
        >
          <item.icon class="h-4 w-4" />
          <span class="flex-1">{item.label}</span>
          {#if !item.dispo}
            <span class="text-[10px] uppercase tracking-wide text-stone-400">À venir</span>
          {/if}
        </button>
      {/each}
    </nav>

    <div class="border-t border-stone-200 p-3 text-xs text-stone-500">
      <div class="flex items-center gap-2">
        <span
          class="inline-block h-2 w-2 rounded-full {backendOk === true ? 'bg-emerald-500' : backendOk === false ? 'bg-red-500' : 'bg-stone-300'}"
        ></span>
        Backend{backendOk === true ? ` v${versionBackend}` : backendOk === false ? " hors-ligne" : "…"}
      </div>
    </div>
  </aside>

  <!-- Zone principale -->
  <main class="flex-1 overflow-auto bg-stone-50">
    <div class="mx-auto max-w-7xl p-6">
      {#if page === "accueil"}
        <Accueil />
      {/if}
    </div>
  </main>
</div>
{/if}
