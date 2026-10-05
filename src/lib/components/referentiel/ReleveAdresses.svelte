<script>
  import Search from "@lucide/svelte/icons/search";
  import Check from "@lucide/svelte/icons/check";
  import Bouton from "$lib/components/Bouton.svelte";
  import { googleApi } from "$lib/api.js";
  import { ecrire, lire } from "$lib/memoire.svelte.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Les adresses calculées, relevées dans Google.
   *
   * Le Référentiel montrait « calculée, pas encore relevée dans Google »
   * pour des centaines de personnes dont le compte existait bel et bien —
   * les adultes, les élèves de NDE. Un clic lit l'annuaire, sans y rien
   * écrire : ce qui concorde sans ambiguïté devient un constat, et le reste
   * revient ici avec sa raison, coché quand un compte est proposé.
   *
   * @typedef {Object} Props
   * @property {number|null} anneeId
   * @property {number} nbCalculees - inscrits dont l'adresse n'est pas constatée
   * @property {() => void} [onModifie] - le référentiel a changé : le relire
   */
  /** @type {Props} */
  let { anneeId = null, nbCalculees = 0, onModifie } = $props();

  const libelle = (e) => String(e).replace(/^Error:\s*/, "");
  // Le parent remonte le composant à chaque changement d'année : la clé
  // n'a pas à suivre l'année en cours de route.
  const cle = () => `referentiel.adresses.${anneeId}`;
  /** Les propositions qui portent un compte : cochées d'office. */
  const proposables = (r) =>
    new Set((r?.a_verifier ?? []).filter((x) => x.adresse_google).map((x) => x.personne_id));

  // Le dernier relevé de l'année reste affiché au retour sur l'onglet : la
  // liste à vérifier ne se perd pas le temps d'ouvrir une fiche.
  const garde = lire(cle(), null);
  let releve = $state.raw(/** @type {any} */ (garde));
  let lecture = $state(false);
  let enregistrement = $state(false);
  let coches = $state(/** @type {Set<number>} */ (proposables(garde)));

  let proposees = $derived((releve?.a_verifier ?? []).filter((x) => x.adresse_google));
  let nbCoches = $derived(proposees.filter((x) => coches.has(x.personne_id)).length);

  const TYPES = { eleve: "élève", adulte: "adulte" };
  const qui = (x) => [TYPES[x.type] ?? x.type, x.site, x.classe].filter(Boolean).join(" · ");

  async function relever() {
    lecture = true;
    try {
      const r = await googleApi.releverAdresses({ anneeId });
      releve = r;
      ecrire(cle(), r);
      coches = proposables(r);
      notify.succes(
        r.nb_enregistrees
          ? `${r.nb_enregistrees} adresse(s) confirmée(s) par Google et enregistrée(s).`
          : "Aucune nouvelle adresse à confirmer.",
        { duree: 8000 },
      );
      if (r.nb_enregistrees) onModifie?.();
    } catch (e) {
      notify.erreur(libelle(e), { duree: 12000 });
    } finally {
      lecture = false;
    }
  }

  function cocher(id, oui) {
    const s = new Set(coches);
    if (oui) s.add(id);
    else s.delete(id);
    coches = s;
  }

  async function retenir() {
    const choix = proposees
      .filter((x) => coches.has(x.personne_id))
      .map((x) => ({ personne_id: x.personne_id, adresse: x.adresse_google }));
    if (!choix.length) return;
    enregistrement = true;
    try {
      const resultats = await googleApi.retenirAdresses(choix);
      const faites = new Set(resultats.filter((r) => r.retenue).map((r) => r.personne_id));
      if (faites.size) notify.succes(`${faites.size} adresse(s) retenue(s).`, { duree: 8000 });
      for (const r of resultats.filter((r) => !r.retenue)) {
        const x = proposees.find((p) => p.personne_id === r.personne_id);
        notify.avertissement(`${x ? `${x.prenom} ${x.nom}` : r.adresse} : ${r.motif}`, { duree: 12000 });
      }
      releve = {
        ...releve,
        nb_enregistrees: releve.nb_enregistrees + faites.size,
        a_verifier: releve.a_verifier.filter((x) => !faites.has(x.personne_id)),
        relevees: [...releve.relevees, ...releve.a_verifier.filter((x) => faites.has(x.personne_id))],
      };
      ecrire(cle(), releve);
      if (faites.size) onModifie?.();
    } catch (e) {
      notify.erreur(libelle(e), { duree: 12000 });
    } finally {
      enregistrement = false;
    }
  }
</script>

{#if nbCalculees > 0 || releve}
  <section class="border-b border-stone-200 py-5 dark:border-stone-800">
    <div class="flex flex-wrap items-center gap-3">
      <span class="h-2.5 w-2.5 rounded-full bg-emerald-600"></span>
      <h3 class="titre-affiche text-base text-stone-900 dark:text-stone-100">Adresses à relever dans Google</h3>
      <span class="text-sm tabular-nums text-stone-500 dark:text-stone-400">
        {nbCalculees.toLocaleString("fr-FR")} encore calculée(s)
      </span>
      <span class="flex-1"></span>
      <Bouton taille="sm" icon={Search} occupe={lecture} onclick={relever}>Relever dans Google</Bouton>
    </div>
    <p class="mt-1.5 max-w-3xl text-sm text-stone-600 dark:text-stone-400">
      Google n'est que lu. Une adresse que l'annuaire confirme — même adresse,
      même nom, aucun homonyme, compte actif — devient un constat ; ce qui ne
      concorde pas se propose ici. La Cohérence en fait autant chaque fois
      qu'elle interroge Google.
    </p>

    {#if releve}
      <p class="mt-3 text-sm tabular-nums text-stone-600 dark:text-stone-400">
        {releve.annee} ·
        <b class="text-stone-900 dark:text-stone-100">{releve.nb_enregistrees}</b> confirmée(s) et enregistrée(s) ·
        <b class="text-stone-900 dark:text-stone-100">{releve.a_verifier.length}</b> à vérifier ·
        <b class="text-stone-900 dark:text-stone-100">{releve.sans_compte.length}</b> sans compte à leur nom
      </p>

      {#if releve.a_verifier.length}
        <!-- Bornée : sous elle, le tableau des classes doit garder sa place. -->
        <div class="mt-3 max-h-72 overflow-auto">
          <table class="tableau w-full text-sm">
            <thead>
              <tr>
                <th class="w-8"></th>
                <th class="text-left">Personne</th>
                <th class="text-left">Adresse du référentiel</th>
                <th class="text-left">Compte Google</th>
                <th class="text-left">Pourquoi la vérifier</th>
              </tr>
            </thead>
            <tbody>
              {#each releve.a_verifier as x (x.personne_id)}
                <tr>
                  <td>
                    <input
                      type="checkbox"
                      class="h-4 w-4 accent-emerald-600"
                      aria-label="Retenir l'adresse de {x.prenom} {x.nom}"
                      disabled={!x.adresse_google}
                      checked={!!x.adresse_google && coches.has(x.personne_id)}
                      onchange={(e) => cocher(x.personne_id, e.currentTarget.checked)}
                    />
                  </td>
                  <td class="whitespace-nowrap">
                    <span class="font-medium">{x.prenom} <span class="uppercase">{x.nom}</span></span>
                    <span class="block text-xs text-stone-500 dark:text-stone-400">{qui(x)}</span>
                  </td>
                  <td class="font-mono text-xs text-stone-500 dark:text-stone-400">{x.adresse_affichee ?? "—"}</td>
                  <td class="font-mono text-xs">{x.adresse_google ?? "—"}</td>
                  <td class="text-xs text-amber-800 dark:text-amber-300">{x.motif}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-3">
          <Bouton
            variante="primary"
            taille="sm"
            icon={Check}
            occupe={enregistrement}
            disabled={!nbCoches}
            onclick={retenir}
          >
            Retenir {nbCoches} adresse(s)
          </Bouton>
          <span class="text-xs text-stone-500 dark:text-stone-400">
            Chacune est relue dans Google avant d'être enregistrée.
          </span>
        </div>
      {/if}

      {#if releve.relevees.length}
        <details class="mt-3">
          <summary class="cursor-pointer text-sm text-stone-600 hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-100">
            Les {releve.relevees.length} adresse(s) confirmées
          </summary>
          <ul class="mt-2 max-h-48 columns-1 gap-6 overflow-y-auto text-xs text-stone-600 md:columns-2 xl:columns-3 dark:text-stone-400">
            {#each releve.relevees as x (x.personne_id)}
              <li class="break-inside-avoid py-0.5">
                {x.prenom} <span class="uppercase">{x.nom}</span> —
                <span class="font-mono">{x.adresse_google}</span>
              </li>
            {/each}
          </ul>
        </details>
      {/if}

      {#if releve.sans_compte.length}
        <details class="mt-2">
          <summary class="cursor-pointer text-sm text-stone-600 hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-100">
            Les {releve.sans_compte.length} sans compte à leur nom
          </summary>
          <p class="mt-1.5 text-xs text-stone-500 dark:text-stone-400">
            Leur adresse reste calculée. Pour un élève, le compte se crée depuis
            « Comptes Google des nouveaux », sous l'ingestion.
          </p>
          <ul class="mt-2 max-h-48 columns-1 gap-6 overflow-y-auto text-xs text-stone-600 md:columns-2 xl:columns-3 dark:text-stone-400">
            {#each releve.sans_compte as x (x.personne_id)}
              <li class="break-inside-avoid py-0.5">
                {x.prenom} <span class="uppercase">{x.nom}</span>
                <span class="text-stone-400 dark:text-stone-500">({qui(x)})</span>
              </li>
            {/each}
          </ul>
        </details>
      {/if}
    {/if}
  </section>
{/if}
