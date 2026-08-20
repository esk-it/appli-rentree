<script>
  import { onMount } from "svelte";
  import Settings from "@lucide/svelte/icons/settings";
  import Check from "@lucide/svelte/icons/check";
  import RotateCcw from "@lucide/svelte/icons/rotate-ccw";
  import Squelette from "$lib/components/Squelette.svelte";
  import Cloud from "@lucide/svelte/icons/cloud";
  import Bouton from "$lib/components/Bouton.svelte";
  import { googleApi, parametres } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  // Un test de connexion appartient à l'écran où l'on saisit la
  // configuration : c'est là qu'on veut savoir tout de suite si elle tient.
  let testEnCours = $state(false);

  async function testerGoogle() {
    testEnCours = true;
    try {
      const r = await googleApi.testerConnexion();
      notify.succes(
        `Connexion établie — ${r.nb_utilisateurs_visibles} utilisateur(s) lu(s). ` +
          "Rien n'a été modifié.",
        { duree: 8000 },
      );
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      testEnCours = false;
    }
  }

  let liste = $state(/** @type {any[]} */ ([]));
  let valeursEnEdition = $state(/** @type {Record<string, any>} */ ({}));
  let messagesSucces = $state(/** @type {Record<string, boolean>} */ ({}));
  let erreur = $state("");
  let chargement = $state(true);

  onMount(rafraichir);

  async function rafraichir() {
    chargement = true;
    try {
      liste = await parametres.lister();
      valeursEnEdition = Object.fromEntries(liste.map((p) => [p.cle, p.valeur]));
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  async function sauvegarder(p) {
    erreur = "";
    try {
      await parametres.mettreAJour(p.cle, valeursEnEdition[p.cle]);
      messagesSucces = { ...messagesSucces, [p.cle]: true };
      notify.succes(`${p.libelle} enregistré`);
      setTimeout(() => {
        messagesSucces = { ...messagesSucces, [p.cle]: false };
      }, 1500);
    } catch (e) {
      erreur = `${p.cle} : ${e}`;
      notify.erreur(`Échec sauvegarde ${p.libelle} : ${e}`);
    }
  }

  async function reinitialiser(p) {
    valeursEnEdition[p.cle] = p.defaut;
    await sauvegarder(p);
  }

  let parametresGroupes = $derived.by(() => {
    const groupes = {};
    for (const p of liste) {
      (groupes[p.categorie] = groupes[p.categorie] || []).push(p);
    }
    return Object.entries(groupes);
  });
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">Paramètres</h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Configuration des règles métier de l'application. Les modifications
      s'appliquent immédiatement aux prochaines générations d'exports.
    </p>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">{erreur}</p>
  {/if}

  {#if chargement}
    <div class="card p-5">
      <Squelette variante="texte" nb={5} />
    </div>
  {:else}
    {#each parametresGroupes as [categorie, params] (categorie)}
      <div class="card p-5">
        <h2 class="titre-section mb-4 flex items-center gap-2">
          <Settings class="h-4 w-4" />
          {categorie}
        </h2>
        {#if categorie === "Google Workspace"}
          <div class="mb-4 flex flex-wrap items-center gap-2 rounded-lg bg-stone-50 p-3 dark:bg-stone-800">
            <Bouton icon={Cloud} occupe={testEnCours} onclick={testerGoogle}>
              Tester la connexion
            </Bouton>
            <span class="text-xs text-stone-600 dark:text-stone-400">
              Lit un seul utilisateur pour valider les credentials, les portées
              et la délégation. Ne modifie rien.
            </span>
          </div>
        {/if}

        <div class="space-y-4">
          {#each params as p (p.cle)}
            <div class="border-b border-stone-100 pb-4 last:border-0 last:pb-0 dark:border-stone-700">
              <div class="flex items-start justify-between gap-3">
                <div class="flex-1">
                  <label for={p.cle} class="block text-sm font-medium text-stone-900 dark:text-stone-100">
                    {p.libelle}
                  </label>
                  <p class="mt-0.5 text-xs text-stone-500 dark:text-stone-400">{p.description}</p>
                  <p class="mt-0.5 font-mono text-[10px] text-stone-400">
                    {p.cle}
                  </p>
                </div>
                <div class="flex items-center gap-2">
                  {#if p.type === "int"}
                    <input
                      id={p.cle}
                      type="number"
                      bind:value={valeursEnEdition[p.cle]}
                      class="champ w-24 !py-1.5"
                    />
                  {:else if p.type === "bool"}
                    <input
                      id={p.cle}
                      type="checkbox"
                      bind:checked={valeursEnEdition[p.cle]}
                      class="h-4 w-4 rounded border-stone-300 text-emerald-700 focus:ring-emerald-500"
                    />
                  {:else}
                    <input
                      id={p.cle}
                      type="text"
                      bind:value={valeursEnEdition[p.cle]}
                      class="champ w-72 !py-1.5"
                    />
                  {/if}
                  <button
                    class="btn-primary !py-1.5 !px-3 text-xs"
                    onclick={() => sauvegarder(p)}
                    title="Enregistrer"
                  >
                    {#if messagesSucces[p.cle]}
                      <Check class="h-3.5 w-3.5" />
                      OK
                    {:else}
                      Enregistrer
                    {/if}
                  </button>
                  <button
                    class="rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-700"
                    title="Réinitialiser au défaut : {p.defaut}"
                    onclick={() => reinitialiser(p)}
                  >
                    <RotateCcw class="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/each}
  {/if}
</section>
