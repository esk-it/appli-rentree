<script>
  import { onMount } from "svelte";
  import Wrench from "@lucide/svelte/icons/wrench";
  import Plus from "@lucide/svelte/icons/plus";
  import ArrowLeftRight from "@lucide/svelte/icons/arrow-left-right";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Modale from "$lib/components/Modale.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { parc } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";

  /**
   * L'atelier : les machines mortes, et ce qu'on peut en tirer.
   *
   * ## Ce que cet écran sait faire et qu'aucun tableau ne sait
   *
   * Répondre à « j'ai une machine morte de la batterie et une autre morte
   * du clavier — est-ce que je peux en refaire une ? ». La réponse demande
   * de croiser les **organes**, pas de lister des machines.
   *
   * ## Pourquoi le remontage se fait pièce par pièce
   *
   * L'écran propose un plan complet, mais chaque prélèvement se demande
   * séparément. Un plan sur le papier n'est pas un tournevis : la pièce
   * peut être plus abîmée qu'annoncé, la vis peut casser. Appliquer tout
   * d'un bouton écrirait dans la base des réparations qui n'ont pas eu
   * lieu, et la réserve mentirait — ce que ce module existe pour éviter.
   */

  let atelier = $state(lire("atelier.rapport", /** @type {any} */ (null)));
  let vocabulaire = $state(/** @type {any} */ (null));
  let chargement = $state(true);
  let erreur = $state("");
  let enCours = $state("");

  $effect(() => ecrire("atelier.rapport", atelier));

  /** La déclaration d'une panne, quand on ouvre le capot. */
  let saisie = $state(/** @type {null | {serie: string, organe: string, note: string, passerHs: boolean}} */ (null));
  let enregistrement = $state(false);

  const LIBELLES_ORGANE = {
    ecran: "Écran",
    charniere: "Charnière",
    clavier: "Clavier",
    trackpad: "Trackpad",
    batterie: "Batterie",
    port_charge: "Port de charge",
    haut_parleur: "Haut-parleur",
    webcam: "Webcam",
    carte_mere: "Carte mère",
    coque: "Coque",
    autre: "Autre",
  };

  const nomOrgane = (o) => LIBELLES_ORGANE[o] ?? o;

  onMount(charger);

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      const [a, v] = await Promise.all([parc.atelier(), parc.vocabulaire()]);
      atelier = a;
      vocabulaire = v;
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
    } finally {
      chargement = false;
    }
  }

  async function prelever(vers, organe, depuis) {
    enCours = `${depuis}→${vers}:${organe}`;
    try {
      const r = await parc.prelever({ depuis, vers, organe });
      notify.succes(
        `${nomOrgane(organe)} de ${depuis} posé sur ${vers} — ` +
          `${vers} est ${r.receveuse.etat === "en_stock" ? "en stock" : "encore HS"}`,
        { duree: 8000 },
      );
      await charger();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      enCours = "";
    }
  }

  async function enregistrerPanne() {
    if (!saisie?.serie.trim() || !saisie.organe) return;
    enregistrement = true;
    try {
      await parc.declarerPanne(saisie.serie.trim(), {
        organe: saisie.organe,
        note: saisie.note.trim() || null,
        passerHs: saisie.passerHs,
      });
      notify.succes(`${nomOrgane(saisie.organe)} noté en panne sur ${saisie.serie.trim()}`);
      saisie = null;
      await charger();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      enregistrement = false;
    }
  }

  let reserve = $derived(
    Object.entries(atelier?.organes_disponibles ?? {}).sort((a, b) => b[1] - a[1]),
  );
  let bloquees = $derived(atelier?.bloquees ?? []);
</script>

<section class="space-y-5">
  <EnTetePage
    icon={Wrench}
    titre="L'atelier"
    description="Les machines hors service et ce que leurs organes sains permettent de remonter. Une machine morte n'est pas un déchet, c'est une réserve de pièces."
  >
    {#snippet actions()}
      <Bouton
        icon={Plus}
        onclick={() => (saisie = { serie: "", organe: "", note: "", passerHs: true })}
      >
        Noter une panne
      </Bouton>
      <Bouton icon={RefreshCw} occupe={chargement} onclick={charger}>Relire</Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if chargement && !atelier}
    <Squelette variante="ligne-tableau" nb={4} colonnes={3} />
  {:else if atelier}
    {#if atelier.machines_hs.length === 0}
      <EtatVide
        icon={CheckCircle2}
        titre="Aucune machine hors service"
        ton="succes"
        message="Rien à remonter, et c'est une bonne nouvelle. Les pannes se notent au fur et à mesure, avec le bouton en haut."
      />
    {:else}
      <!-- Ce qu'on peut refaire : la réponse à la question qu'on se pose. -->
      <div class="card p-4">
        <div class="mb-3 flex flex-wrap items-baseline gap-3">
          <h2 class="text-lg font-semibold">
            {#if atelier.nb_remontables}
              {atelier.nb_remontables} machine{atelier.nb_remontables > 1 ? "s" : ""} remontable{atelier.nb_remontables > 1 ? "s" : ""}
            {:else}
              Rien de remontable en l'état
            {/if}
          </h2>
          <span class="text-sm text-stone-500 dark:text-stone-400">
            sur {atelier.machines_hs.length} hors service
          </span>
        </div>

        {#if atelier.remontages.length}
          <div class="flex flex-col gap-3">
            {#each atelier.remontages as r (r.serie)}
              <div class="rounded-lg border border-emerald-200 bg-emerald-50/60 p-3 dark:border-emerald-800 dark:bg-emerald-900/20">
                <p class="text-sm">
                  <span class="font-mono font-semibold">{r.serie}</span>
                  <span class="text-stone-600 dark:text-stone-300">
                    remarche s'il reçoit
                    {r.organes_manquants.map(nomOrgane).join(", ").toLowerCase()}
                  </span>
                </p>
                <div class="mt-2 flex flex-col gap-1.5">
                  {#each Object.entries(r.donneurs) as [organe, donneur] (organe)}
                    <div class="flex flex-wrap items-center gap-2 text-sm">
                      <span class="badge-neutre">{nomOrgane(organe)}</span>
                      <span class="text-stone-500">de</span>
                      <span class="font-mono text-xs">{donneur}</span>
                      <Bouton
                        taille="sm"
                        icon={ArrowLeftRight}
                        occupe={enCours === `${donneur}→${r.serie}:${organe}`}
                        onclick={() => prelever(r.serie, organe, donneur)}
                      >
                        Prélever
                      </Bouton>
                    </div>
                  {/each}
                </div>
                <p class="mt-2 text-xs text-stone-500 dark:text-stone-400">
                  Chaque prélèvement se confirme séparément : il note la pièce
                  posée ici <em>et</em> l'organe qui manque désormais à la donneuse.
                </p>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-sm text-stone-600 dark:text-stone-400">
            Aucune machine hors service n'a tous ses organes manquants couverts
            par les autres.
          </p>
        {/if}
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <!-- La réserve -->
        <div class="card p-4">
          <h2 class="titre-section mb-2">Ce qu'il y a en réserve</h2>
          <p class="mb-3 text-xs text-stone-500 dark:text-stone-400">
            Organes encore intacts sur les machines hors service.
          </p>
          {#if reserve.length}
            <div class="flex flex-wrap gap-1.5">
              {#each reserve as [organe, nb] (organe)}
                <span class="badge-neutre">
                  {nomOrgane(organe)}
                  <strong class="tabular-nums">{nb}</strong>
                </span>
              {/each}
            </div>
          {:else}
            <p class="text-sm text-stone-500">Rien à prélever.</p>
          {/if}
        </div>

        <!-- Ce que rien ne couvre -->
        <div class="card p-4">
          <h2 class="titre-section mb-2">Ce que rien ne couvre</h2>
          {#if bloquees.length}
            <ul class="flex flex-col gap-1.5 text-sm">
              {#each bloquees as [serie, organes] (serie)}
                <li class="flex flex-wrap items-center gap-2">
                  <span class="font-mono text-xs">{serie}</span>
                  <span class="text-stone-500">manque</span>
                  {#each organes as o (o)}
                    <span class="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                      {nomOrgane(o)}
                    </span>
                  {/each}
                </li>
              {/each}
            </ul>
          {:else}
            <p class="text-sm text-stone-500">
              Tout ce qui est hors service trouve ses pièces.
            </p>
          {/if}
        </div>
      </div>

      <!-- Le détail machine par machine -->
      <div class="card overflow-hidden">
        <table class="tableau">
          <thead class="entete-tableau">
            <tr>
              <th class="px-3 py-2 text-left">Série</th>
              <th class="px-3 py-2 text-left">Organes morts</th>
              <th class="px-3 py-2 text-left">Hors service depuis</th>
              <th class="px-3 py-2 text-left">Note</th>
            </tr>
          </thead>
          <tbody class="corps-tableau">
            {#each atelier.machines_hs as m (m.serie)}
              <tr>
                <td class="whitespace-nowrap px-3 py-1.5 font-mono text-xs">{m.serie}</td>
                <td class="px-3 py-1.5">
                  <div class="flex flex-wrap gap-1">
                    {#each m.pannes_ouvertes as o (o)}
                      <span class="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900/40 dark:text-red-300">
                        {nomOrgane(o)}
                      </span>
                    {:else}
                      <span class="text-xs text-stone-400">aucun organe noté</span>
                    {/each}
                  </div>
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 text-xs tabular-nums text-stone-500">
                  {m.etat_depuis
                    ? String(m.etat_depuis).split("-").reverse().join("/")
                    : "—"}
                </td>
                <td class="px-3 py-1.5 text-xs text-stone-500">{m.note ?? ""}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</section>

{#if saisie}
  <Modale titre="Noter une panne" onFermer={() => (saisie = null)}>
    <div>
      <label class="libelle-champ" for="panne-serie">Numéro de série</label>
      <input
        id="panne-serie"
        class="champ font-mono"
        placeholder="5CD1234ABC"
        bind:value={saisie.serie}
      />
    </div>

    <div>
      <label class="libelle-champ" for="panne-organe">Organe</label>
      <select id="panne-organe" class="champ" bind:value={saisie.organe}>
        <option value="">Choisir…</option>
        {#each vocabulaire?.organes ?? [] as o (o)}
          <option value={o}>{nomOrgane(o)}</option>
        {/each}
      </select>
      <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
        La liste est fermée exprès : c'est elle qui permet de croiser deux
        machines mortes. « Autre » se note, mais ne se croise pas.
      </p>
    </div>

    <div>
      <label class="libelle-champ" for="panne-note">Détail</label>
      <input
        id="panne-note"
        class="champ"
        placeholder="charnière droite, ne tient plus la charge…"
        bind:value={saisie.note}
      />
    </div>

    <label class="flex items-start gap-2 text-sm">
      <input type="checkbox" class="mt-0.5 accent-emerald-600" bind:checked={saisie.passerHs} />
      <span>
        Passer la machine hors service
        <span class="block text-xs text-stone-500 dark:text-stone-400">
          Décoche pour consigner un défaut sans l'immobiliser — une charnière
          fendue qui tient encore.
        </span>
      </span>
    </label>

    {#snippet actions()}
      <Bouton onclick={() => (saisie = null)}>Annuler</Bouton>
      <Bouton
        variante="primary"
        occupe={enregistrement}
        disabled={!saisie.serie.trim() || !saisie.organe}
        onclick={enregistrerPanne}
      >
        Noter
      </Bouton>
    {/snippet}
  </Modale>
{/if}
