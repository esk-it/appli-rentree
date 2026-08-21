<script>
  import { onMount } from "svelte";
  import Laptop from "@lucide/svelte/icons/laptop";
  import Upload from "@lucide/svelte/icons/upload";
  import Undo2 from "@lucide/svelte/icons/undo-2";
  import UserPlus from "@lucide/svelte/icons/user-plus";
  import PackageOpen from "@lucide/svelte/icons/package-open";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Download from "@lucide/svelte/icons/download";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import { enregistrerFichierBase64, googleApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let statutApi = $state(/** @type {any} */ (null));
  let fichier = $state(/** @type {File|null} */ (null));
  let flotte = $state(/** @type {any} */ (null));
  let chargement = $state(false);
  let vue = $state("a_recuperer");

  let apiUtilisable = $derived(
    statutApi?.bibliotheques_disponibles && statutApi?.configuration_complete,
  );

  async function analyser() {
    if (!fichier) return;
    chargement = true;
    try {
      flotte = await googleApi.analyserChromebooks({ fichier });
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      chargement = false;
    }
  }

  let onglets = $derived([
    { id: "a_recuperer", label: "À récupérer", badge: flotte?.nb_a_recuperer ?? 0 },
    { id: "a_attribuer", label: "À équiper", badge: flotte?.a_attribuer?.length ?? 0 },
    { id: "disponibles", label: "Libres", badge: flotte?.disponibles?.length ?? 0 },
    { id: "discordances", label: "À vérifier", badge: flotte?.discordances?.length ?? 0 },
  ]);

  function exporter() {
    if (!flotte) return;
    const lignes = [];
    for (const p of flotte.a_recuperer) {
      for (const a of p.appareils) {
        lignes.push(["À récupérer", p.nom, p.prenom, p.discipline, p.email ?? "",
                     a.modele, a.serie, a.etiquette]);
      }
    }
    for (const p of flotte.a_attribuer) {
      lignes.push(["À équiper", p.nom, p.prenom, p.discipline, p.email ?? "", "", "", ""]);
    }
    for (const a of flotte.disponibles) {
      lignes.push(["Libre", "", "", "", "", a.modele, a.serie, a.etiquette]);
    }
    const entetes = ["Situation", "Nom", "Prénom", "Discipline", "Adresse",
                     "Modèle", "N° de série", "Étiquette"];
    const csv = [entetes, ...lignes]
      .map((l) => l.map((c) => (String(c).includes(";") ? `"${c}"` : c)).join(";"))
      .join("\r\n");
    const b64 = btoa(String.fromCharCode(...new TextEncoder().encode("﻿" + csv)));
    enregistrerFichierBase64("Chromebooks.csv", b64, "text/csv").then(
      ({ chemin, annule }) => {
        if (!annule) {
          notify.succes(`${lignes.length} ligne(s) — ${chemin ?? "Téléchargements"}`,
            { duree: 8000 });
        }
      },
    );
  }

  function jour(iso) {
    return iso ? iso.slice(0, 10).split("-").reverse().join("/") : "—";
  }

  onMount(async () => {
    try {
      statutApi = await googleApi.statut();
    } catch {
      statutApi = null;
    }
  });
</script>

<section class="space-y-4">
  <EnTetePage
    icon={Laptop}
    titre="Chromebooks"
    description="Qui détient quelle machine, ce qu'il faut réclamer aux partants et attribuer aux arrivants. Lecture seule : le programme constate, il ne déplace rien."
  />

  {#if !apiUtilisable}
    <div class="card p-4">
      <EtatVide
        icon={Laptop}
        titre="Mode API non configuré"
        message="Cet écran lit les appareils dans Google. Renseigne le compte de service dans Paramètres, et vérifie que le droit de lecture des Chromebooks lui a été accordé."
      />
    </div>
  {:else}
    <div class="card p-4 space-y-3">
      <p class="text-xs text-stone-600 dark:text-stone-400">
        Google prévoit un champ « utilisateur annoté » pour désigner le porteur
        d'un appareil ; il contient ici partout le même compte technique. C'est
        l'<strong>étiquette</strong> qui porte l'adresse du titulaire, et les
        dernières connexions servent de contre-épreuve. Le mouvement de chaque
        enseignant — entrant, sortant — vient du tableau que tu tiens, où il est
        porté par la couleur.
      </p>

      <div class="flex flex-wrap items-center gap-3">
        <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
          <Upload class="h-4 w-4" />
          {fichier?.name ?? "Choisir le tableau des professeurs (.xlsx)"}
          <input
            type="file"
            accept=".xlsx"
            class="hidden"
            onchange={(e) => (fichier = e.target.files?.[0] ?? null)}
          />
        </label>
        <Bouton variante="primary" occupe={chargement} disabled={!fichier} onclick={analyser}>
          Analyser la flotte
        </Bouton>
        {#if flotte}
          <Bouton icon={Download} classe="ml-auto" onclick={exporter}>Export Excel</Bouton>
        {/if}
      </div>

      {#if flotte}
        <div class="flex flex-wrap gap-x-6 gap-y-1 border-t border-stone-200 pt-3 text-sm dark:border-stone-700">
          <span><strong class="tabular-nums">{flotte.nb_appareils}</strong> appareils</span>
          <span><strong class="tabular-nums">{flotte.nb_profs}</strong> enseignants</span>
          {#each Object.entries(flotte.nb_par_code) as [code, n]}
            <span class="text-stone-500 dark:text-stone-400">{code} : {n}</span>
          {/each}
        </div>
        {#each flotte.avertissements as a}
          <p class="rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">
            {a}
          </p>
        {/each}
      {/if}
    </div>

    {#if flotte}
      <div class="card p-3">
        <Segments bind:valeur={vue} options={onglets} />
      </div>

      <div class="card overflow-hidden">
        {#if vue === "a_recuperer"}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            <Undo2 class="mr-1 inline h-3.5 w-3.5" />
            Enseignants marqués sortants qui détiennent encore une machine.
          </div>
          <div class="max-h-[28rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Enseignant</th>
                  <th class="text-left">Discipline</th>
                  <th class="text-left">Modèle</th>
                  <th class="text-left">N° de série</th>
                  <th class="text-left">Dernière synchro</th>
                </tr>
              </thead>
              <tbody>
                {#each flotte.a_recuperer as p (p.email ?? p.nom)}
                  {#each p.appareils as a (a.serie)}
                    <tr>
                      <td class="whitespace-nowrap font-medium">{p.prenom} {p.nom}</td>
                      <td class="whitespace-nowrap text-stone-600 dark:text-stone-400">{p.discipline}</td>
                      <td class="whitespace-nowrap text-xs">{a.modele}</td>
                      <td class="whitespace-nowrap font-mono text-xs">{a.serie}</td>
                      <td class="whitespace-nowrap text-xs text-stone-500">{jour(a.derniere_synchro)}</td>
                    </tr>
                  {/each}
                {/each}
              </tbody>
            </table>
          </div>

        {:else if vue === "a_attribuer"}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            <UserPlus class="mr-1 inline h-3.5 w-3.5" />
            Arrivants auxquels aucune machine n'est rattachée.
          </div>
          <div class="max-h-[28rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Enseignant</th>
                  <th class="text-left">Discipline</th>
                  <th class="text-left">Adresse</th>
                </tr>
              </thead>
              <tbody>
                {#each flotte.a_attribuer as p (p.nom + p.prenom)}
                  <tr class:ligne-douteuse={!p.email}>
                    <td class="whitespace-nowrap font-medium">{p.prenom} {p.nom}</td>
                    <td class="whitespace-nowrap text-stone-600 dark:text-stone-400">{p.discipline}</td>
                    <td class="whitespace-nowrap font-mono text-xs">
                      {#if p.email}
                        {p.email}
                      {:else}
                        <span class="font-sans text-amber-700 dark:text-amber-400">
                          aucun compte Google — à créer d'abord
                        </span>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

        {:else if vue === "disponibles"}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            <PackageOpen class="mr-1 inline h-3.5 w-3.5" />
            Parc de prêt, et machines étiquetées au nom de comptes qui n'existent plus.
          </div>
          <div class="max-h-[28rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Étiquette</th>
                  <th class="text-left">Modèle</th>
                  <th class="text-left">N° de série</th>
                  <th class="text-left">Dernière synchro</th>
                </tr>
              </thead>
              <tbody>
                {#each flotte.disponibles as a (a.serie)}
                  <tr>
                    <td class="whitespace-nowrap font-mono text-xs">{a.etiquette}</td>
                    <td class="whitespace-nowrap text-xs">{a.modele}</td>
                    <td class="whitespace-nowrap font-mono text-xs">{a.serie}</td>
                    <td class="whitespace-nowrap text-xs text-stone-500">{jour(a.derniere_synchro)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

        {:else}
          <div class="px-4 py-3 text-xs text-stone-600 dark:text-stone-400">
            <TriangleAlert class="mr-1 inline h-3.5 w-3.5" />
            L'étiquette dit une chose, les connexions en disent une autre. Deux
            machines échangées se voient ici. Le programme ne tranche pas.
          </div>
          <div class="max-h-[28rem] overflow-auto">
            <table class="tableau w-full text-sm">
              <thead>
                <tr>
                  <th class="text-left">Étiquette</th>
                  <th class="text-left">Qui s'y connecte</th>
                  <th class="text-left">N° de série</th>
                </tr>
              </thead>
              <tbody>
                {#each flotte.discordances as d (d.appareil.serie)}
                  <tr class="ligne-douteuse">
                    <td class="whitespace-nowrap font-mono text-xs">{d.attendu}</td>
                    <td class="whitespace-nowrap font-mono text-xs">{d.constates.join(", ")}</td>
                    <td class="whitespace-nowrap font-mono text-xs">{d.appareil.serie}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</section>
