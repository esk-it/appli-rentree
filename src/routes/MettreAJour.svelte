<script>
  import { onMount } from "svelte";
  import DatabaseZap from "@lucide/svelte/icons/database-zap";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Snapshots from "./Snapshots.svelte";
  import { ingestion, personnes as personnesApi } from "$lib/api.js";

  /**
   * Mettre à jour le référentiel : la porte de l'export Charlemagne.
   *
   * Un nouvel élève, un AESH, des INE ou des dates de naissance à
   * compléter — tout entre par un export Charlemagne, et l'import n'avait
   * pas de porte : il vivait dans les outils, sous « Snapshots d'années »,
   * ou au fil des étapes de la rentrée (Johann, 5 novembre 2026).
   *
   * L'écran répond dans l'ordre aux trois questions d'avant un import : de
   * quand date ce que le programme sait, qu'est-ce qui lui manque, et quel
   * export lui apporter. L'import lui-même est celui de toujours —
   * simulation d'abord, puis l'ingestion réelle.
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  let etat = $state(/** @type {any} */ (null));
  let releve = $state(/** @type {any} */ (null));

  const POPULATIONS = { eleve: "Élèves", adulte: "Personnels" };

  async function charger() {
    try {
      etat = await ingestion.etat();
      releve = etat?.annee_id
        ? await personnesApi.completude(etat.annee_id, { photos: false })
        : null;
    } catch {
      // L'état éclaire l'import, il ne le conditionne pas.
    }
  }
  onMount(charger);

  /** @param {string|null} jour - AAAA-MM-JJ */
  function depuis(jour) {
    if (!jour) return null;
    const j = Math.round((Date.now() - new Date(jour + "T12:00").getTime()) / 86400000);
    return j <= 0 ? "aujourd'hui" : j === 1 ? "hier" : `il y a ${j} jours`;
  }
  /** @param {string} jour */
  const date = (jour) => new Date(jour + "T12:00").toLocaleDateString("fr-FR", { day: "numeric", month: "long" });

  /** Ce qui manque, en nombres de fiches — l'INE ne concerne que les élèves. */
  let manques = $derived(
    releve
      ? [
          { libelle: "sans INE", n: releve.eleves - releve.avec_ine, sur: "élèves" },
          { libelle: "sans date de naissance", n: releve.effectif - releve.avec_naissance, sur: "inscrits" },
          { libelle: "sans adresse constatée", n: releve.effectif - releve.avec_adresse, sur: "inscrits" },
          { libelle: "sans mot de passe au coffre", n: releve.effectif - releve.au_coffre, sur: "inscrits" },
        ]
      : [],
  );

  const COLONNES_ELEVES = [
    ["Identifiant Élève, Nom, Prénom", "l'identité — le reste s'y rattache"],
    ["Code classe, Num Badge, Code Régime", "la classe, le badge, Sodexo"],
    ["Id. National", "l'INE (pas « Ancien INE ou INA »)"],
    ["Date de naissance", "KoXo, et départager deux fiches"],
    ["Email", "l'adresse Google"],
    ["Photo, Date Entrée pour tri", "les cartes et le trombinoscope"],
    ["Code niveau, Code établissement", "les codes de CardStudio"],
    ["ID Réseau Péda, MDP Réseau Péda", "le coffre — ouvre-le avant l'import réel"],
  ];
</script>

<section class="space-y-6">
  <EnTetePage
    icon={DatabaseZap}
    titre="Mettre à jour le référentiel"
    description="Un nouvel élève, un professeur, un AESH, des INE ou des dates de naissance à compléter : tout entre par un export Charlemagne. Dépose-le ici — le programme dit d'abord ce qu'il changerait, puis l'applique."
  />

  <!-- De quand date ce que le programme sait : un élève arrivé depuis
       n'existe encore ni aux cartes, ni chez Sodexo, ni pour Google. -->
  {#if etat?.populations?.length}
    <div class="flex flex-wrap gap-x-14 gap-y-4 border-b border-stone-200 pb-5 dark:border-stone-800">
      {#each etat.populations as p (p.type_personne)}
        {@const vieux = p.dernier_export && Date.now() - new Date(p.dernier_export + "T12:00").getTime() > 14 * 86400000}
        <div>
          <p class="titre-affiche text-[32px] leading-none text-stone-900 tabular-nums dark:text-stone-100">
            {p.inscrits.toLocaleString("fr-FR")}
          </p>
          <p class="mt-1 text-[13px] text-stone-600 dark:text-stone-400">
            {POPULATIONS[p.type_personne] ?? p.type_personne} en {etat.annee}
          </p>
          {#if p.dernier_export}
            <p class="mt-0.5 text-xs {vieux ? 'font-semibold text-amber-700 dark:text-amber-400' : 'text-stone-500 dark:text-stone-400'}">
              Dernier export lu le {date(p.dernier_export)} · {depuis(p.dernier_export)}
            </p>
          {/if}
        </div>
      {/each}
      {#if manques.length}
        <div class="min-w-64">
          <p class="libelle-champ">Ce qui manque encore</p>
          <ul class="mt-1.5 space-y-0.5 text-sm">
            {#each manques as m (m.libelle)}
              <li class="flex items-baseline gap-2">
                <span class="w-14 text-right font-semibold tabular-nums {m.n ? 'text-stone-900 dark:text-stone-100' : 'text-stone-400'}">
                  {m.n.toLocaleString("fr-FR")}
                </span>
                <span class="text-stone-600 dark:text-stone-300">{m.libelle}</span>
              </li>
            {/each}
          </ul>
          {#if onNaviguer}
            <button
              class="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:underline dark:text-emerald-400"
              onclick={() => onNaviguer("personnes")}
            >
              Le détail par classe, dans Référentiel › Ce qui manque <ArrowRight class="h-3 w-3" />
            </button>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  <!-- L'import de toujours : simulation, puis réel. -->
  <Snapshots sansEntete onNaviguer={onNaviguer ?? null} onIngere={charger} />

  <!-- Quel export pour quoi. Le programme ne devine rien : une colonne
       absente de l'export laisse le champ tel qu'il est. -->
  <details class="card p-5" open={!etat?.populations?.length}>
    <summary class="cursor-pointer font-semibold text-stone-900 dark:text-stone-100">
      Quel export Charlemagne, avec quelles colonnes
    </summary>
    <div class="mt-3 grid gap-6 lg:grid-cols-2">
      <div>
        <p class="libelle-champ">Les élèves</p>
        <p class="mt-1 text-sm text-stone-600 dark:text-stone-300">
          L'export « Gestion de bases » des élèves, en HTM ou en XLSX. Chaque colonne
          présente complète la fiche ; une colonne absente ne retire rien.
        </p>
        <table class="mt-2 w-full text-sm">
          <tbody>
            {#each COLONNES_ELEVES as [colonnes, usage] (colonnes)}
              <tr class="border-t border-stone-100 align-top dark:border-stone-800">
                <td class="py-1.5 pr-4 font-medium text-stone-800 dark:text-stone-200">{colonnes}</td>
                <td class="py-1.5 text-stone-600 dark:text-stone-400">{usage}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="space-y-4">
        <div>
          <p class="libelle-champ">Les personnels — professeurs, AESH, vie scolaire…</p>
          <p class="mt-1 text-sm text-stone-600 dark:text-stone-300">
            L'export des personnels. Avec le <strong>poste occupé</strong> et les
            <strong>matières</strong> : c'est la matière qui ouvre à un professeur le
            dossier partagé de sa discipline, dans KoXo.
          </p>
        </div>
        <div>
          <p class="libelle-champ">Tout l'établissement, ou quelques-uns</p>
          <p class="mt-1 text-sm text-stone-600 dark:text-stone-300">
            Un export complet montre aussi ceux qui ont disparu de Charlemagne. Pour un
            seul arrivant, un export réduit suffit — ignore alors la liste des
            disparus : ce sont simplement les autres.
          </p>
        </div>
        <div>
          <p class="libelle-champ">Ensuite</p>
          <ul class="mt-1 space-y-1 text-sm">
            {#each [["arrivees", "Un arrivant : ses comptes, de KoXo à Google"], ["cartes", "Sa carte, dans Les cartes"], ["sodexo", "Le self, dans Sodexo"]] as [page, libelle] (page)}
              <li>
                <button
                  class="inline-flex items-center gap-1 text-emerald-700 hover:underline disabled:text-stone-500 dark:text-emerald-400"
                  disabled={!onNaviguer}
                  onclick={() => onNaviguer?.(page)}
                >
                  <ArrowRight class="h-3.5 w-3.5" /> {libelle}
                </button>
              </li>
            {/each}
          </ul>
        </div>
      </div>
    </div>
  </details>
</section>
