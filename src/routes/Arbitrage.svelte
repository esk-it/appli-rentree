<script>
  import { onMount } from "svelte";
  import Scale from "@lucide/svelte/icons/scale";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import UserX from "@lucide/svelte/icons/user-x";
  import Users from "@lucide/svelte/icons/users";
  import History from "@lucide/svelte/icons/history";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { arbitrages } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let onglet = $state(/** @type {"en_attente"|"historique"} */ ("en_attente"));
  let liste = $state([]);
  let chargement = $state(false);
  let erreur = $state("");

  // Note libre par ligne, indexée par arbitrage_id
  let notes = $state(/** @type {Record<number, string>} */ ({}));

  onMount(charger);

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      liste =
        onglet === "en_attente"
          ? await arbitrages.enAttente()
          : await arbitrages.lister();
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  async function trancher(arb, decision) {
    try {
      await arbitrages.trancher(arb.id, {
        decision,
        note: notes[arb.id]?.trim() || null,
      });
      notify.succes(`Décision enregistrée : ${decision}`);
      delete notes[arb.id];
      await charger();
    } catch (e) {
      notify.erreur(String(e));
    }
  }

  function libelleType(t) {
    return {
      collision_login: "Collision de login",
      homonymie_ingestion: "Homonymie dans l'export",
      rapprochement: "Rapprochement",
      qualification: "Qualification",
    }[t] ?? t;
  }

  function iconeType(t) {
    return {
      collision_login: UserX,
      homonymie_ingestion: Users,
      rapprochement: Scale,
      qualification: Scale,
    }[t] ?? Scale;
  }

  function decisionsPossibles(arb) {
    if (arb.type_cas === "collision_login") {
      return [
        { valeur: `suffixe:${suffixeAttribue(arb)}`, label: `Garder ${arb.contexte?.login_attribue}`, style: "primary" },
        { valeur: "meme_personne", label: "Même personne (à corriger dans Charlemagne)", style: "secondary" },
      ];
    }
    if (arb.type_cas === "homonymie_ingestion") {
      return [
        { valeur: "personnes_distinctes", label: "Personnes distinctes", style: "primary" },
        { valeur: "meme_personne", label: "Même personne (doublon à corriger)", style: "secondary" },
      ];
    }
    return [
      { valeur: "vu", label: "Marquer comme vu", style: "primary" },
    ];
  }

  function suffixeAttribue(arb) {
    const login = arb.contexte?.login_attribue ?? "";
    const base = arb.contexte?.login_base ?? "";
    if (!base || !login.startsWith(base)) return 0;
    const rest = login.slice(base.length);
    return rest ? Number(rest) : 0;
  }

  function formaterDate(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleString("fr-FR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
</script>

<section class="space-y-5">
  <EnTetePage
    icon={Scale}
    ton="amber"
    titre="Arbitrage"
    description="Chaque décision est mémorisée définitivement et ne sera plus jamais redemandée. Le programme refuse de trancher les cas ambigus lui-même — c'est le principe qui garantit la stabilité inter-années."
  />

  <Segments
    bind:valeur={onglet}
    onChange={charger}
    options={[
      { id: "en_attente", label: "En attente", icon: Scale },
      { id: "historique", label: "Historique complet", icon: History },
    ]}
  />

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if chargement}
    <Squelette variante="texte" nb={4} />
  {:else if liste.length === 0}
    <EtatVide
      icon={CheckCircle2}
      ton={onglet === "en_attente" ? "succes" : "neutre"}
      titre={onglet === "en_attente"
        ? "Aucun cas en attente"
        : "Aucun arbitrage enregistré"}
      message={onglet === "en_attente"
        ? "Rien ne bloque : toutes les collisions et homonymies ont été tranchées."
        : "Les décisions apparaîtront ici au fur et à mesure. Elles sont conservées à vie et ne seront jamais redemandées."}
    />
  {:else}
    <div class="space-y-3">
      {#each liste as arb (arb.id)}
        {@const Ic = iconeType(arb.type_cas)}
        <article class="card p-4 space-y-3">
          <header class="flex items-start justify-between gap-3">
            <div class="flex items-start gap-3">
              <div class="mt-0.5 rounded-lg bg-stone-100 p-2 dark:bg-stone-800">
                <Ic class="h-4 w-4 text-stone-600 dark:text-stone-400" />
              </div>
              <div>
                <p class="text-sm font-semibold text-stone-900 dark:text-stone-100">
                  {libelleType(arb.type_cas)}
                </p>
                <p class="text-xs font-mono text-stone-500 dark:text-stone-400">
                  {arb.cle_cas}
                </p>
              </div>
            </div>
            <div class="text-right text-xs text-stone-500 dark:text-stone-400">
              {formaterDate(arb.date_creation)}
              {#if arb.est_en_attente}
                <span class="ml-2 inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                  <AlertTriangle class="h-3 w-3" />
                  À trancher
                </span>
              {:else}
                <span class="ml-2 inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
                  <CheckCircle2 class="h-3 w-3" />
                  Tranché
                </span>
              {/if}
            </div>
          </header>

          <!-- Contexte : rendu spécifique par type -->
          {#if arb.type_cas === "collision_login"}
            <div class="rounded-lg bg-stone-50 p-3 text-sm dark:bg-stone-800">
              <p>
                <strong>{arb.contexte?.prenom} {arb.contexte?.nom}</strong>
                (id Charlemagne {arb.contexte?.id_charlemagne},
                {arb.contexte?.type_personne})
                — login base <code>{arb.contexte?.login_base}</code> déjà pris.
              </p>
              <p class="mt-1 text-stone-700 dark:text-stone-300">
                Proposition : <code class="rounded bg-emerald-100 px-1.5 py-0.5 font-mono text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200">{arb.contexte?.login_attribue}</code>
              </p>
              {#if arb.contexte?.personnes_deja_presentes?.length > 0}
                <p class="mt-2 text-xs font-medium text-stone-600 dark:text-stone-400">
                  Personne(s) déjà présente(s) avec ce login base :
                </p>
                <ul class="mt-1 space-y-0.5 text-xs">
                  {#each arb.contexte.personnes_deja_presentes as p (p.personne_id)}
                    <li>
                      <code>{p.login}</code> — {p.prenom} {p.nom}
                      <span class="text-stone-400">({p.cle_pivot}, {p.type})</span>
                    </li>
                  {/each}
                </ul>
              {/if}
            </div>
          {:else if arb.type_cas === "homonymie_ingestion"}
            <div class="rounded-lg bg-stone-50 p-3 text-sm dark:bg-stone-800">
              <p>
                <strong>{arb.contexte?.prenom_normalise} {arb.contexte?.nom_normalise}</strong>
                — {arb.contexte?.ids_charlemagne?.length ?? 0} personnes du même nom+prénom dans l'export
                <em>{arb.contexte?.annee_libelle}</em> ({arb.contexte?.type_personne}).
              </p>
              <p class="mt-1 text-xs text-stone-600 dark:text-stone-400">
                IDs Charlemagne : {arb.contexte?.ids_charlemagne?.join(", ")}
              </p>
            </div>
          {:else}
            <div class="rounded-lg bg-stone-50 p-3 text-xs font-mono dark:bg-stone-800">
              <pre class="whitespace-pre-wrap">{JSON.stringify(arb.contexte, null, 2)}</pre>
            </div>
          {/if}

          {#if arb.est_en_attente}
            <div class="space-y-2">
              <input
                type="text"
                placeholder="Note optionnelle (ex : à corriger dans Charlemagne)"
                bind:value={notes[arb.id]}
                class="w-full rounded-lg border border-stone-300 px-3 py-1.5 text-sm dark:border-stone-600 dark:bg-stone-800"
              />
              <div class="flex flex-wrap gap-2">
                {#each decisionsPossibles(arb) as opt (opt.valeur)}
                  <button
                    class={opt.style === "primary" ? "btn-primary" : "btn-secondary"}
                    onclick={() => trancher(arb, opt.valeur)}
                  >
                    {opt.label}
                  </button>
                {/each}
              </div>
            </div>
          {:else}
            <div class="flex items-center justify-between rounded-lg bg-emerald-50 px-3 py-2 text-sm dark:bg-emerald-900/20">
              <span class="text-emerald-900 dark:text-emerald-200">
                Décision : <strong>{arb.decision}</strong>
                <span class="ml-2 text-xs text-emerald-700 dark:text-emerald-400">
                  le {formaterDate(arb.date_decision)}
                </span>
              </span>
              {#if arb.note}
                <span class="text-xs text-stone-600 dark:text-stone-400">« {arb.note} »</span>
              {/if}
            </div>
          {/if}
        </article>
      {/each}
    </div>
  {/if}
</section>
