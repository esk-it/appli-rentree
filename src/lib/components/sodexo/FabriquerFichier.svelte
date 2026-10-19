<script>
  import Upload from "@lucide/svelte/icons/upload";
  import FileDown from "@lucide/svelte/icons/file-down";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import CircleX from "@lucide/svelte/icons/circle-x";
  import Send from "@lucide/svelte/icons/send";
  import Bouton from "$lib/components/Bouton.svelte";
  import { sodexoApi, enregistrerFichierBase64 } from "$lib/api.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Le fichier élèves du portail, fabriqué ici plutôt que dans le classeur
   * Google.
   *
   * Le classeur n'a jamais transmis les réductions : son script exportait
   * l'onglet Import au lieu de l'onglet Export (constaté le 19 octobre
   * 2026). On dépose l'édition Charlemagne telle qu'elle sort ; le
   * programme applique la règle — le code particulier (PassageS) d'abord,
   * sinon le régime —, vérifie chaque code contre les profils du portail,
   * et met en regard le référentiel.
   *
   * @typedef {Object} Props
   * @property {number|null} [anneeId]
   * @property {() => void} [onTransmettre] - vers « Ce qui a changé », pour déclarer l'envoi
   */
  /** @type {Props} */
  let { anneeId = null, onTransmettre } = $props();

  let fichier = $state(/** @type {File|null} */ (null));
  let rapport = $state(lire("sodexo.rapport", /** @type {any} */ (null)));
  $effect(() => ecrire("sodexo.rapport", rapport));
  let occupe = $state(false);

  const libelle = (e) => String(e).replace(/^Error:\s*/, "");
  const REGIMES = ["D", "E", "P"];

  async function fabriquer() {
    if (!fichier) return;
    occupe = true;
    try {
      rapport = await sodexoApi.fichier({ fichier, anneeId });
    } catch (e) {
      rapport = null;
      notify.erreur(libelle(e), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  async function enregistrer() {
    try {
      await enregistrerFichierBase64(rapport.nom_fichier, rapport.csv_base64, "text/csv");
      notify.succes(`${rapport.nom_fichier} enregistré.`);
    } catch (e) {
      notify.erreur(libelle(e));
    }
  }
</script>

<div class="flex flex-col gap-5">
  <!-- 1. L'édition -->
  <div class="card p-5">
    <p class="libelle-champ">1 · L'édition Charlemagne</p>
    <p class="mt-1 max-w-3xl text-sm text-stone-600 dark:text-stone-300">
      Charlemagne Administratif › Traitement › Éditions › Listes › Les éditions
      établissements › <strong>« Liste des élèves - Export vers SoHappy »</strong>.
      Dépose le fichier tel qu'il sort : plus de classeur Google, plus de copier-coller.
    </p>
    <div class="mt-3 flex flex-wrap items-center gap-3">
      <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
        <Upload class="h-4 w-4" />
        {fichier?.name ?? "Choisir l'édition (.xlsx)"}
        <input
          type="file"
          accept=".xlsx,.xls,.csv"
          class="hidden"
          onchange={(e) => {
            fichier = /** @type {HTMLInputElement} */ (e.currentTarget).files?.[0] ?? null;
            rapport = null;
          }}
        />
      </label>
      <Bouton variante="primary" occupe={occupe} disabled={!fichier} onclick={fabriquer}>
        Fabriquer le fichier
      </Bouton>
    </div>
  </div>

  {#if rapport}
    <!-- Ce qui partira -->
    <div class="flex flex-wrap items-end gap-x-12 gap-y-4 border-b border-stone-200 pb-5 dark:border-stone-800">
      <div>
        <p class="titre-affiche text-3xl leading-none text-stone-900 dark:text-stone-100">{rapport.nb_eleves.toLocaleString("fr-FR")}</p>
        <p class="mt-1 text-xs text-stone-600 dark:text-stone-400">élèves dans le fichier</p>
      </div>
      <div class="flex flex-wrap gap-2">
        {#each Object.entries(rapport.par_code) as [code, n] (code)}
          <span
            class="inline-flex items-baseline gap-1.5 rounded-full px-3 py-1 text-sm
              {REGIMES.includes(code)
              ? 'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-200'
              : 'bg-vert-100 font-semibold text-vert-800 dark:bg-vert-900/40 dark:text-vert-200'}"
          >
            <span class="font-mono">{code}</span><span class="tabular-nums">{n}</span>
          </span>
        {/each}
      </div>
    </div>

    {#if rapport.erreurs.length}
      <div class="rounded-xl border border-red-300 bg-red-50 px-4 py-3 dark:border-red-900 dark:bg-red-950/30" role="alert">
        <p class="flex items-center gap-2 font-semibold text-red-900 dark:text-red-200">
          <CircleX class="h-4 w-4" /> Le fichier n'est pas produit : le portail importerait mal
        </p>
        <ul class="mt-2 flex list-disc flex-col gap-1 pl-5 text-sm text-red-900 dark:text-red-100">
          {#each rapport.erreurs as e, i (i)}<li>{e}</li>{/each}
        </ul>
      </div>
    {/if}

    {#each rapport.avertissements as a, i (i)}
      <p class="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">
        <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" /> {a}
      </p>
    {/each}

    <!-- Ceux que l'ancien classeur envoyait en D ou en E -->
    {#if rapport.particuliers.length}
      <div class="card p-5">
        <p class="libelle-champ">Les codes particuliers</p>
        <p class="mt-1 max-w-3xl text-sm text-stone-600 dark:text-stone-300">
          L'ancien classeur les envoyait avec leur seul régime : ce fichier leur rend
          leur profil — et sa réduction — dès l'import.
        </p>
        <div class="mt-3 overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs text-stone-500 dark:text-stone-400">
                <th class="py-1.5 pr-4 font-semibold">Élève</th>
                <th class="py-1.5 pr-4 font-semibold">Classe</th>
                <th class="py-1.5 pr-4 font-semibold">Badge</th>
                <th class="py-1.5 pr-4 font-semibold">Régime</th>
                <th class="py-1.5 font-semibold">Envoyé</th>
              </tr>
            </thead>
            <tbody>
              {#each rapport.particuliers as p (p.badge)}
                <tr class="border-t border-stone-100 dark:border-stone-800">
                  <td class="py-1.5 pr-4 text-stone-900 dark:text-stone-100">{p.prenom} {p.nom}</td>
                  <td class="py-1.5 pr-4 font-mono">{p.classe}</td>
                  <td class="py-1.5 pr-4 font-mono tabular-nums">{p.badge}</td>
                  <td class="py-1.5 pr-4 font-mono text-stone-500">{p.regime}</td>
                  <td class="py-1.5 font-mono font-semibold text-vert-700 dark:text-vert-300">{p.code}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    {#if rapport.absents.length}
      <details class="text-sm text-stone-600 dark:text-stone-300">
        <summary class="cursor-pointer font-semibold text-stone-800 dark:text-stone-200">Inscrits absents de l'édition ({rapport.absents.length})</summary>
        <p class="mt-1.5 leading-relaxed">{rapport.absents.join(", ")}</p>
      </details>
    {/if}
    {#if rapport.inconnus.length}
      <details class="text-sm text-stone-600 dark:text-stone-300">
        <summary class="cursor-pointer font-semibold text-stone-800 dark:text-stone-200">Badges inconnus du référentiel ({rapport.inconnus.length})</summary>
        <p class="mt-1.5 leading-relaxed">{rapport.inconnus.join(", ")}</p>
      </details>
    {/if}

    {#if rapport.pret}
      <div class="card flex flex-col gap-4 p-5">
        <div>
          <p class="libelle-champ">2 · Le fichier</p>
          <div class="mt-2"><Bouton variante="primary" icon={FileDown} onclick={enregistrer}>Enregistrer {rapport.nom_fichier}</Bouton></div>
        </div>
        <div>
          <p class="libelle-champ">3 · Dans le portail</p>
          <p class="mt-1 text-sm text-stone-600 dark:text-stone-300">
            Administration › Imports › Comptes/Convives › l'engrenage de
            <strong>« Import comptes par badge – CLASSIFICATION 1 – Elèves »</strong>,
            puis ce fichier. Pas une autre ligne : celle des adultes attend d'autres colonnes.
          </p>
        </div>
        <div>
          <p class="libelle-champ">4 · Une fois l'import passé</p>
          <div class="mt-2"><Bouton icon={Send} onclick={() => onTransmettre?.()}>Déclarer l'envoi</Bouton></div>
        </div>
      </div>
    {/if}
  {/if}
</div>
