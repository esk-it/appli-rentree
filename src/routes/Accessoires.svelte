<script>
  import { onMount } from "svelte";
  import Cable from "@lucide/svelte/icons/cable";
  import Plus from "@lucide/svelte/icons/plus";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import Undo2 from "@lucide/svelte/icons/undo-2";
  import Send from "@lucide/svelte/icons/send";
  import Search from "@lucide/svelte/icons/search";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Modale from "$lib/components/Modale.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { parc } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Les accessoires prêtés, et surtout ceux qui ne sont pas revenus.
   *
   * ## Prêter n'est pas attribuer
   *
   * Une machine est confiée pour l'année ; un chargeur est prêté, et il est
   * censé revenir. L'écran met donc en tête ce qui a dépassé sa date de
   * retour — c'est la seule question qui se pose vraiment sur un stock
   * d'accessoires, et elle ne se lit dans aucune liste triée par série.
   *
   * ## Pourquoi « accessoire » et pas « chargeur »
   *
   * Le stock suivant sera fait de souris ou d'adaptateurs. Nommer l'objet
   * par son usage plutôt que par sa nature évite de refaire l'écran.
   */

  let stock = $state(/** @type {any} */ (null));
  let vocabulaire = $state(/** @type {any} */ (null));
  let chargement = $state(true);
  let erreur = $state("");
  let recherche = $state("");
  let filtreEtat = $state("");

  let nouveau = $state(/** @type {null | {serie: string, type: string, note: string}} */ (null));
  let pret = $state(/** @type {null | {serie: string, aQui: string, retour: string, note: string}} */ (null));
  let occupe = $state(false);

  const LIBELLES_ETAT = {
    en_stock: "En stock",
    prete: "Prêté",
    hs: "Hors service",
    reforme: "Réformé",
  };
  const LIBELLES_TYPE = {
    chargeur: "Chargeur",
    souris: "Souris",
    adaptateur: "Adaptateur",
    cable: "Câble",
    housse: "Housse",
    autre: "Autre",
  };
  const TEINTES_ETAT = {
    en_stock: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
    prete: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
    hs: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
    reforme: "bg-stone-100 text-stone-600 dark:bg-stone-700 dark:text-stone-300",
  };

  const jour = (iso) => (iso ? String(iso).split("-").reverse().join("/") : "—");

  onMount(charger);

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      const [s, v] = await Promise.all([parc.accessoires(), parc.vocabulaire()]);
      stock = s;
      vocabulaire = v;
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
    } finally {
      chargement = false;
    }
  }

  async function ajouter() {
    if (!nouveau?.serie.trim()) return;
    occupe = true;
    try {
      stock = await parc.ajouterAccessoire({
        serie: nouveau.serie.trim(),
        type: nouveau.type,
        note: nouveau.note.trim() || null,
      });
      notify.succes(`${nouveau.serie.trim()} entré en stock`);
      // On garde la fenêtre ouverte : un stock s'enregistre à la chaîne.
      nouveau = { serie: "", type: nouveau.type, note: "" };
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 9000 });
    } finally {
      occupe = false;
    }
  }

  async function sortir() {
    if (!pret?.aQui.trim()) return;
    occupe = true;
    try {
      stock = await parc.preter(pret.serie, {
        aQui: pret.aQui.trim(),
        retourPrevuLe: pret.retour || null,
        note: pret.note.trim() || null,
      });
      notify.succes(`${pret.serie} prêté à ${pret.aQui.trim()}`);
      pret = null;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 9000 });
    } finally {
      occupe = false;
    }
  }

  async function rentrer(serie, etat) {
    try {
      stock = await parc.rendre(serie, { etat });
      notify.succes(
        etat === "hs" ? `${serie} rendu, noté hors service` : `${serie} rendu`,
      );
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 9000 });
    }
  }

  let listeFiltree = $derived.by(() => {
    let r = stock?.accessoires ?? [];
    if (filtreEtat) r = r.filter((a) => a.etat === filtreEtat);
    const q = recherche.trim().toLowerCase();
    if (q) {
      r = r.filter((a) =>
        `${a.serie} ${a.prete_a ?? ""} ${a.note ?? ""}`.toLowerCase().includes(q),
      );
    }
    // Les retards d'abord : c'est la seule urgence d'un stock d'accessoires.
    return [...r].sort(
      (a, b) => Number(b.en_retard) - Number(a.en_retard) || a.serie.localeCompare(b.serie),
    );
  });

  let compteurs = $derived.by(() => {
    const total = {};
    for (const [, etats] of Object.entries(stock?.par_type ?? {})) {
      for (const [etat, n] of Object.entries(etats)) total[etat] = (total[etat] ?? 0) + n;
    }
    return total;
  });
</script>

<section class="space-y-5">
  <EnTetePage
    icon={Cable}
    titre="Les accessoires"
    description="Chargeurs, souris, adaptateurs — qui les a, et lesquels ne sont pas revenus. Un prêt a une échéance, contrairement à une machine attribuée."
  >
    {#snippet actions()}
      <Bouton
        icon={Plus}
        onclick={() => (nouveau = { serie: "", type: "chargeur", note: "" })}
      >
        Entrer en stock
      </Bouton>
      <Bouton icon={RefreshCw} occupe={chargement} onclick={charger}>Relire</Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if chargement && !stock}
    <Squelette variante="ligne-tableau" nb={4} colonnes={4} />
  {:else if stock}
    {#if stock.nb_en_retard > 0}
      <div class="flex items-center gap-3 rounded-lg border-l-4 border-l-amber-500 bg-amber-50 p-3 text-sm dark:bg-amber-900/25">
        <AlertTriangle class="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
        <p>
          <strong class="tabular-nums">{stock.nb_en_retard}</strong>
          accessoire{stock.nb_en_retard > 1 ? "s ont" : " a"} dépassé
          {stock.nb_en_retard > 1 ? "leur" : "sa"} date de retour. Ils sont en tête
          de liste.
        </p>
      </div>
    {/if}

    {#if stock.accessoires.length === 0}
      <EtatVide
        icon={Cable}
        titre="Aucun accessoire enregistré"
        message="Entre tes chargeurs par leur numéro de série — celui du fabricant suffit, il n'y a rien à étiqueter."
      />
    {:else}
      <!-- Combien il en reste, par type : la question la plus fréquente. -->
      <div class="grid gap-px overflow-hidden rounded-xl border border-stone-200 bg-stone-200 dark:border-stone-700 dark:bg-stone-700"
           style="grid-template-columns: repeat(auto-fit, minmax(190px, 1fr))">
        {#each Object.entries(stock.par_type) as [type, etats] (type)}
          <div class="bg-white p-4 dark:bg-stone-800">
            <p class="libelle-champ">{LIBELLES_TYPE[type] ?? type}</p>
            <p class="mt-1 text-2xl font-semibold tabular-nums">
              {etats.en_stock ?? 0}
              <span class="text-sm font-normal text-stone-500">en stock</span>
            </p>
            <p class="text-xs text-stone-500 dark:text-stone-400">
              {etats.prete ?? 0} prêté{(etats.prete ?? 0) > 1 ? "s" : ""}
              {#if etats.hs}· {etats.hs} HS{/if}
            </p>
          </div>
        {/each}
      </div>

      <div class="card overflow-hidden">
        <div class="flex flex-wrap items-center gap-3 border-b border-stone-200 p-3 dark:border-stone-700">
          <div class="relative min-w-56 flex-1">
            <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
            <input
              class="champ pl-9"
              placeholder="Numéro de série, ou à qui il est prêté…"
              bind:value={recherche}
            />
          </div>
          <div class="flex flex-wrap gap-1">
            <button
              class="rounded-full border px-2.5 py-1 text-xs transition {filtreEtat === ''
                ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
              onclick={() => (filtreEtat = "")}
            >
              Tous <span class="tabular-nums">{stock.accessoires.length}</span>
            </button>
            {#each Object.entries(LIBELLES_ETAT) as [id, label] (id)}
              {#if compteurs[id]}
                <button
                  class="rounded-full border px-2.5 py-1 text-xs transition {filtreEtat === id
                    ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                    : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
                  onclick={() => (filtreEtat = id)}
                >
                  {label} <span class="tabular-nums">{compteurs[id]}</span>
                </button>
              {/if}
            {/each}
          </div>
        </div>

        <table class="tableau">
          <thead class="entete-tableau">
            <tr>
              <th class="px-3 py-2 text-left">Série</th>
              <th class="px-3 py-2 text-left">Type</th>
              <th class="px-3 py-2 text-left">État</th>
              <th class="px-3 py-2 text-left">Chez qui</th>
              <th class="px-3 py-2 text-left">Prêté le</th>
              <th class="px-3 py-2 text-left">Retour prévu</th>
              <th class="px-3 py-2 text-right">Geste</th>
            </tr>
          </thead>
          <tbody class="corps-tableau">
            {#each listeFiltree as a (a.serie)}
              <tr class={a.en_retard ? "bg-amber-50/70 dark:bg-amber-900/20" : ""}>
                <td class="whitespace-nowrap px-3 py-1.5 font-mono text-xs">{a.serie}</td>
                <td class="px-3 py-1.5 text-xs">{LIBELLES_TYPE[a.type] ?? a.type}</td>
                <td class="px-3 py-1.5">
                  <span class="rounded-full px-2 py-0.5 text-xs font-medium {TEINTES_ETAT[a.etat]}">
                    {LIBELLES_ETAT[a.etat] ?? a.etat}
                  </span>
                </td>
                <td class="px-3 py-1.5 text-sm">{a.prete_a ?? "—"}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-xs tabular-nums text-stone-500">
                  {jour(a.prete_le)}
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 text-xs tabular-nums">
                  <span class={a.en_retard ? "font-semibold text-amber-700 dark:text-amber-400" : "text-stone-500"}>
                    {jour(a.retour_prevu_le)}
                  </span>
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 text-right">
                  {#if a.etat === "prete"}
                    <Bouton taille="sm" icon={Undo2} onclick={() => rentrer(a.serie, "en_stock")}>
                      Rendu
                    </Bouton>
                    <button
                      class="ml-1 text-xs text-stone-500 underline decoration-dotted hover:text-red-600"
                      onclick={() => rentrer(a.serie, "hs")}
                    >
                      rendu cassé
                    </button>
                  {:else if a.etat === "en_stock"}
                    <Bouton
                      taille="sm"
                      icon={Send}
                      onclick={() => (pret = { serie: a.serie, aQui: "", retour: "", note: "" })}
                    >
                      Prêter
                    </Bouton>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</section>

{#if nouveau}
  <Modale titre="Entrer un accessoire en stock" onFermer={() => (nouveau = null)}>
    <div>
      <label class="libelle-champ" for="acc-serie">Numéro de série</label>
      <input
        id="acc-serie"
        class="champ font-mono"
        placeholder="celui du fabricant"
        bind:value={nouveau.serie}
        onkeydown={(e) => e.key === "Enter" && ajouter()}
      />
    </div>
    <div>
      <label class="libelle-champ" for="acc-type">Type</label>
      <select id="acc-type" class="champ" bind:value={nouveau.type}>
        {#each vocabulaire?.types_accessoire ?? [] as t (t)}
          <option value={t}>{LIBELLES_TYPE[t] ?? t}</option>
        {/each}
      </select>
    </div>
    <div>
      <label class="libelle-champ" for="acc-note">Note</label>
      <input id="acc-note" class="champ" bind:value={nouveau.note} />
    </div>
    <p class="text-xs text-stone-500 dark:text-stone-400">
      La fenêtre reste ouverte après chaque enregistrement : un carton
      s'inventorie à la chaîne.
    </p>

    {#snippet actions()}
      <Bouton onclick={() => (nouveau = null)}>Fermer</Bouton>
      <Bouton
        variante="primary"
        occupe={occupe}
        disabled={!nouveau.serie.trim()}
        onclick={ajouter}
      >
        Enregistrer
      </Bouton>
    {/snippet}
  </Modale>
{/if}

{#if pret}
  <Modale titre="Prêter {pret.serie}" onFermer={() => (pret = null)}>
    <div>
      <label class="libelle-champ" for="pret-qui">À qui</label>
      <input
        id="pret-qui"
        class="champ"
        placeholder="un élève, un professeur, une salle…"
        bind:value={pret.aQui}
      />
    </div>
    <div>
      <label class="libelle-champ" for="pret-retour">Retour prévu</label>
      <input id="pret-retour" type="date" class="champ" bind:value={pret.retour} />
      <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
        C'est elle qui fait la différence avec une attribution : passé cette
        date, l'accessoire remonte en tête de liste.
      </p>
    </div>
    <div>
      <label class="libelle-champ" for="pret-note">Note</label>
      <input id="pret-note" class="champ" bind:value={pret.note} />
    </div>

    {#snippet actions()}
      <Bouton onclick={() => (pret = null)}>Annuler</Bouton>
      <Bouton variante="primary" occupe={occupe} disabled={!pret.aQui.trim()} onclick={sortir}>
        Prêter
      </Bouton>
    {/snippet}
  </Modale>
{/if}
