<script>
  import { onMount } from "svelte";
  import Nfc from "@lucide/svelte/icons/nfc";
  import Upload from "@lucide/svelte/icons/upload";
  import Download from "@lucide/svelte/icons/download";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import ShieldCheck from "@lucide/svelte/icons/shield-check";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import { annees as anneesApi, ts1000 } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";

  /**
   * Le différentiel TS1000, calculé contre l'état réel de la centrale.
   *
   * ## Pourquoi quatre fichiers et non un
   *
   * La centrale les rejoue dans l'ordre où on les importe. Une suppression
   * jouée avant un déplacement effacerait un badge que le déplacement
   * allait sauver. Les lots sont donc numérotés, et l'écran le dit.
   *
   * ## Ce que l'écran met en avant
   *
   * Pas les fichiers : les **garde-fous**. Combien de personnes vivent dans
   * un groupe d'accès et n'ont pas été touchées, combien de suppressions
   * sont proposées sans preuve, et si un CardId serait perdu. Ce sont les
   * trois façons de casser quelque chose ici, et elles se lisent avant les
   * boutons de téléchargement.
   */

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));
  let fichier = $state(lire("ts1000.fichier", /** @type {File | null} */ (null)));
  let rapport = $state(lire("ts1000.rapport", /** @type {any} */ (null)));
  let occupe = $state(false);

  $effect(() => ecrire("ts1000.fichier", fichier));
  $effect(() => ecrire("ts1000.rapport", rapport));

  onMount(async () => {
    try {
      const a = await anneesApi.lister();
      listeAnnees = a;
      anneeId =
        [...a].sort((x, y) => y.libelle.localeCompare(x.libelle))[0]?.id ?? null;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    }
  });

  async function calculer() {
    if (!fichier || !anneeId) return;
    occupe = true;
    try {
      rapport = await ts1000.differentiel({ fichier, anneeId });
      if (rapport.nb_total === 0) {
        notify.succes("TS1000 est déjà à jour — rien à porter.");
      } else {
        notify.info(`${rapport.nb_total} ligne(s) à porter, en ${rapport.lots.length} lot(s)`);
      }
      for (const a of rapport.avertissements) notify.avertissement(a, { duree: 10000 });
    } catch (e) {
      rapport = null;
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  function telecharger(lot) {
    const octets = Uint8Array.from(atob(lot.contenu_base64), (c) => c.charCodeAt(0));
    const url = URL.createObjectURL(
      new Blob([octets], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = lot.nom_fichier;
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<section class="space-y-5">
  <EnTetePage
    icon={Nfc}
    titre="Contrôle d'accès TS1000"
    description="Ce qu'il faut porter dans la centrale, calculé contre son propre export — et non contre une année passée du référentiel."
  />

  <div class="card space-y-3 p-4">
    <div class="grid gap-3 sm:grid-cols-[200px_minmax(0,1fr)_auto] sm:items-end">
      <div>
        <label class="libelle-champ" for="ts-annee">Année qui fait foi</label>
        <select id="ts-annee" class="champ" bind:value={anneeId}>
          {#each listeAnnees as a (a.id)}
            <option value={a.id}>{a.libelle}</option>
          {/each}
        </select>
      </div>
      <div>
        <label class="libelle-champ" for="ts-fichier">Export de la centrale</label>
        <label
          class="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-stone-300 px-3 py-2 text-sm text-stone-600 transition hover:border-emerald-400 dark:border-stone-600 dark:text-stone-300"
        >
          <Upload class="h-4 w-4 shrink-0" />
          <span class="truncate">{fichier?.name ?? "Choisir Users.xls"}</span>
          <input
            id="ts-fichier"
            type="file"
            accept=".xls,.xlsx"
            class="hidden"
            onchange={(e) => {
              const f = e.currentTarget.files?.[0];
              if (f) {
                fichier = f;
                rapport = null;
              }
            }}
          />
        </label>
      </div>
      <Bouton
        variante="primary"
        occupe={occupe}
        disabled={!fichier || !anneeId}
        onclick={calculer}
      >
        Calculer
      </Bouton>
    </div>
    <p class="text-xs text-stone-500 dark:text-stone-400">
      Dans TS1000 : <strong>Usagers → Exporter</strong>. Le fichier porte les
      groupes réels et les CardId — c'est lui qui fait foi, pas ce que le
      référentiel croit savoir.
    </p>
  </div>

  {#if rapport}
    {#if rapport.cardid_perdus.length}
      <div class="rounded-lg border-l-4 border-l-red-500 bg-red-50 p-4 dark:bg-red-900/25">
        <p class="flex items-center gap-2 font-semibold text-red-800 dark:text-red-300">
          <AlertTriangle class="h-5 w-5" /> N'importe rien
        </p>
        <p class="mt-1 text-sm text-red-800 dark:text-red-200">
          {rapport.cardid_perdus.length} ligne(s) perdraient leur CardId. Les cartes
          encodées cesseraient d'ouvrir : {rapport.cardid_perdus.slice(0, 10).join(", ")}.
        </p>
      </div>
    {/if}

    <!-- Les garde-fous d'abord, les fichiers ensuite. -->
    <div class="grid gap-4 lg:grid-cols-3">
      <div class="card p-4">
        <p class="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
          <ShieldCheck class="h-3.5 w-3.5" /> Jamais touchés
        </p>
        <p class="mt-1 text-2xl font-semibold tabular-nums">{rapport.proteges.length}</p>
        <p class="text-xs text-stone-500 dark:text-stone-400">
          personnes dans un groupe d'accès — internat, AVS, ménage. Les ramener
          vers leur classe leur fermerait des portes.
        </p>
      </div>
      <div class="card p-4">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
          Lu dans la centrale
        </p>
        <p class="mt-1 text-2xl font-semibold tabular-nums">{rapport.nb_lignes_lues}</p>
        <p class="text-xs text-stone-500 dark:text-stone-400">
          usagers · {rapport.nb_inscrits} élèves inscrits au référentiel
        </p>
      </div>
      <div class="card p-4">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
          Groupes d'internat appris
        </p>
        {#if rapport.groupes_internat.length}
          <div class="mt-1.5 flex flex-wrap gap-1">
            {#each rapport.groupes_internat as g (g)}
              <span class="badge-neutre">{g}</span>
            {/each}
          </div>
        {:else}
          <p class="mt-1 text-sm text-stone-500">Aucun repéré dans l'export.</p>
        {/if}
      </div>
    </div>

    {#if rapport.nb_total === 0}
      <div class="card flex items-center gap-3 p-5">
        <CheckCircle2 class="h-6 w-6 shrink-0 text-emerald-600 dark:text-emerald-400" />
        <div>
          <p class="font-medium">TS1000 est à jour.</p>
          <p class="text-sm text-stone-500 dark:text-stone-400">
            Aucune création, aucun déplacement, aucune suppression à porter.
          </p>
        </div>
      </div>
    {:else}
      <p class="text-sm text-stone-600 dark:text-stone-400">
        <strong>{rapport.nb_total}</strong> ligne(s) à porter.
        Importe les lots <strong>dans l'ordre des numéros</strong> : une suppression
        jouée avant un déplacement effacerait un badge que le déplacement allait
        sauver.
      </p>

      {#each rapport.lots as lot (lot.id)}
        <div class="card overflow-hidden">
          <div class="flex flex-wrap items-center gap-3 border-b border-stone-200 p-3 dark:border-stone-700">
            <h2 class="font-semibold">{lot.libelle}</h2>
            <span class="badge-neutre tabular-nums">{lot.nb}</span>
            <code class="text-xs text-stone-500">{lot.nom_fichier}</code>
            <div class="ml-auto">
              <Bouton taille="sm" icon={Download} onclick={() => telecharger(lot)}>
                Télécharger
              </Bouton>
            </div>
          </div>
          <div class="max-h-72 overflow-auto">
            <table class="tableau">
              <thead class="entete-tableau">
                <tr>
                  <th class="px-3 py-2 text-left">Badge</th>
                  <th class="px-3 py-2 text-left">Nom</th>
                  <th class="px-3 py-2 text-left">Groupe</th>
                  <th class="px-3 py-2 text-left">Carte</th>
                  <th class="px-3 py-2 text-left">Motif</th>
                </tr>
              </thead>
              <tbody class="corps-tableau">
                {#each lot.mouvements as m (m.badge)}
                  <tr>
                    <td class="whitespace-nowrap px-3 py-1.5 font-mono text-xs tabular-nums">{m.badge}</td>
                    <td class="px-3 py-1.5">{m.nom}</td>
                    <td class="whitespace-nowrap px-3 py-1.5 text-xs">
                      {#if m.groupe_vise && m.groupe_actuel}
                        <span class="text-stone-500">{m.groupe_actuel}</span> →
                        <strong>{m.groupe_vise}</strong>
                      {:else}
                        {m.groupe_vise ?? m.groupe_actuel ?? "—"}
                      {/if}
                    </td>
                    <td class="px-3 py-1.5 text-xs">
                      {#if m.a_une_carte}
                        <span class="text-emerald-700 dark:text-emerald-400">encodée</span>
                      {:else}
                        <span class="text-stone-400">aucune</span>
                      {/if}
                    </td>
                    <td class="px-3 py-1.5 text-xs text-stone-500">{m.motif}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/each}
    {/if}

    {#if rapport.indetermines.length}
      <div class="card p-4">
        <h2 class="titre-section mb-2">Pensionnaires sans destination apprise</h2>
        <p class="mb-2 text-xs text-stone-500 dark:text-stone-400">
          Aucun camarade de leur classe n'est encore rangé à l'internat : le
          groupe ne peut pas être déduit. Les placer une fois à la main suffit,
          le calcul suivant saura.
        </p>
        <ul class="flex flex-col gap-1 text-sm">
          {#each rapport.indetermines as m (m.badge)}
            <li>
              <span class="font-mono text-xs">{m.badge}</span>
              <span class="font-medium">{m.nom}</span>
              <span class="text-stone-500">— {m.motif}</span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}
  {/if}
</section>
