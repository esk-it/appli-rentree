<script>
  import { onMount } from "svelte";
  import ArrowLeftRight from "@lucide/svelte/icons/arrow-left-right";
  import CloudUpload from "@lucide/svelte/icons/cloud-upload";
  import PackagePlus from "@lucide/svelte/icons/package-plus";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import UserCheck from "@lucide/svelte/icons/user-check";
  import Modale from "$lib/components/Modale.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { parc } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import {
    CATEGORIES, ETATS, GESTES, finMaj, ilYA, jour, messageErreur, nomOrgane, ouEst,
  } from "$lib/parc.js";

  /**
   * Tout ce qu'on sait d'une machine.
   *
   * L'histoire compte autant que l'état : savoir qu'elle a déjà changé
   * trois fois de mains cette année, ou qu'un écran y a déjà été remplacé,
   * change le regard qu'on porte sur elle.
   *
   * @typedef {Object} Props
   * @property {string} serie
   * @property {Record<string, string>} raisons
   * @property {() => void} onFermer
   * @property {(p: any) => void} onEchanger
   * @property {() => void} onModifie - après un geste : relire l'inventaire
   */
  /** @type {Props} */
  let { serie, raisons = {}, onFermer, onEchanger, onModifie } = $props();

  let fiche = $state(/** @type {any} */ (null));
  let occupe = $state("");

  async function charger() {
    try {
      fiche = await parc.fiche(serie);
    } catch (e) {
      notify.erreur(messageErreur(e));
    }
  }
  onMount(charger);

  let p = $derived(fiche?.poste);

  async function reporter() {
    occupe = "google";
    try {
      const r = await parc.reporterGoogle([serie]);
      const res = r.google.find((x) => x.serie === serie);
      if (res?.ok) notify.succes(`Google : ${res.message}`);
      else notify.erreur(res?.message ?? "Rien à écrire.", { duree: 15000 });
      await charger();
      onModifie();
    } catch (e) {
      notify.erreur(messageErreur(e), { duree: 15000 });
    } finally {
      occupe = "";
    }
  }

  /** L'attribuer à celui qui s'en sert : une correction, comme à l'inventaire. */
  async function attribuerAuProbable() {
    occupe = "probable";
    try {
      const r = await parc.pointer(serie, { constat: "porteur", porteur: p.porteur_probable });
      notify.succes(r.message, { duree: 8000 });
      await charger();
      onModifie();
    } catch (e) {
      notify.erreur(messageErreur(e), { duree: 10000 });
    } finally {
      occupe = "";
    }
  }

  async function auStock() {
    occupe = "stock";
    try {
      await parc.mettreAuStock(serie, { precision: "remise au stock depuis la fiche" });
      notify.succes(`${serie} est au stock.`);
      await charger();
      onModifie();
    } catch (e) {
      notify.erreur(messageErreur(e), { duree: 10000 });
    } finally {
      occupe = "";
    }
  }

  /** Une ligne du journal, lue du point de vue de cette machine. */
  function recit(m) {
    const autre = m.autre_serie ? ` (${m.serie === serie ? "avec" : "pour"} ${m.serie === serie ? m.autre_serie : m.serie})` : "";
    const trajet = [m.de, m.vers].filter(Boolean).join(" → ");
    return `${trajet}${autre}`;
  }
</script>

<Modale titre="Chromebook {p?.etiquette_voulue ?? p?.etiquette ?? serie}" largeur="lg" {onFermer}>
  {#if !fiche}
    <Squelette variante="ligne-tableau" nb={4} colonnes={2} />
  {:else if !p}
    <p class="text-sm text-stone-600">Cette machine est inconnue de l'inventaire.</p>
  {:else}
    {@const maj = finMaj(p.fin_maj)}
    <div class="flex flex-wrap items-center gap-2">
      <Pastille etat={ETATS[p.etat]?.pastille ?? "inconnu"} texte={ETATS[p.etat]?.texte ?? p.etat} />
      <span class="text-lg font-semibold text-stone-900 dark:text-stone-100">{ouEst(p)}</span>
      {#if p.porteur_detail}<span class="text-sm text-stone-500">{p.porteur_detail}</span>{/if}
      {#if p.porteur_parti}<Pastille etat="ecart" texte="Plus inscrit cette année" />{/if}
    </div>

    <dl class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-sm">
      <dt class="text-stone-500">Numéro de série</dt>
      <dd class="font-mono">{p.serie}</dd>
      <dt class="text-stone-500">Modèle</dt>
      <dd>{p.modele || "—"}</dd>
      <dt class="text-stone-500">Unité Google</dt>
      <dd class="break-all text-xs">{p.ou || "—"} · {CATEGORIES[p.categorie] ?? p.categorie}{p.site ? ` · ${p.site}` : ""}</dd>
      <dt class="text-stone-500">Étiquette Google</dt>
      <dd>{p.etiquette || "(vide)"}{#if p.emplacement} · emplacement {p.emplacement}{/if}</dd>
      <dt class="text-stone-500">Fin des mises à jour</dt>
      <dd class={maj.ton}>{maj.texte}</dd>
      <dt class="text-stone-500">Dernière synchro</dt>
      <dd>{p.derniere_synchro ? `${jour(p.derniere_synchro)} (${ilYA(p.derniere_synchro)})` : "jamais"}</dd>
      {#if p.derniers_utilisateurs?.length}
        <dt class="text-stone-500">Derniers utilisateurs</dt>
        <dd class="text-xs">{p.derniers_utilisateurs.slice(0, 3).join(", ")}</dd>
      {/if}
      {#if p.depuis}
        <dt class="text-stone-500">Dans cet état depuis</dt>
        <dd>{jour(p.depuis)}</dd>
      {/if}
      <dt class="text-stone-500">Vue à l'inventaire</dt>
      <dd>{p.pointe_le ? jour(p.pointe_le) : "jamais"}</dd>
    </dl>

    {#if p.a_reporter.length}
      <div class="rounded-lg border-l-4 border-l-amber-500 bg-amber-50 p-3 text-sm dark:bg-amber-900/25">
        <p class="font-semibold">Google n'a pas encore suivi</p>
        <ul class="mt-1 text-[13px] text-stone-700 dark:text-stone-300">
          {#if p.a_reporter.includes("étiquette")}
            <li>étiquette : « {p.etiquette || "(vide)"} » → « {p.etiquette_voulue ?? p.porteur} »</li>
          {/if}
          {#if p.a_reporter.includes("emplacement")}
            <li>emplacement : « {p.emplacement || "(vide)"} » → « {p.emplacement_voulu || "(vide)"} »</li>
          {/if}
          {#if p.a_reporter.includes("unité")}
            <li>unité : {p.ou} → {p.ou_voulue}</li>
          {/if}
        </ul>
        <div class="mt-2">
          <Bouton taille="sm" icon={CloudUpload} occupe={occupe === "google"} onclick={reporter}>
            Écrire dans Google
          </Bouton>
        </div>
      </div>
    {/if}

    {#if p.a_verifier}
      <p class="flex items-start gap-2 text-sm text-amber-800 dark:text-amber-300">
        <TriangleAlert class="mt-0.5 h-4 w-4 shrink-0" /> {p.a_verifier}.
      </p>
    {/if}

    {#if p.porteur_probable}
      <div class="flex flex-wrap items-center gap-3 rounded-lg bg-sky-50 p-3 text-sm dark:bg-sky-900/20">
        <UserCheck class="h-4 w-4 shrink-0 text-sky-700 dark:text-sky-400" />
        <span class="flex-1">
          D'après Google, c'est <strong>{p.porteur_probable_nom}</strong> qui s'en sert.
        </span>
        <Bouton taille="sm" occupe={occupe === "probable"} onclick={attribuerAuProbable}>
          La lui attribuer
        </Bouton>
      </div>
    {/if}

    {#if fiche.pannes.length}
      <div>
        <p class="libelle-champ">Pannes</p>
        <ul class="mt-1 space-y-0.5 text-sm">
          {#each fiche.pannes as pa (pa.id)}
            <li class="flex flex-wrap items-baseline gap-2">
              <span class={pa.resolue_le ? "text-stone-500 line-through" : "font-medium text-red-700 dark:text-red-400"}>
                {nomOrgane(pa.organe)}
              </span>
              <span class="text-xs text-stone-500">
                le {jour(pa.constatee_le)}{#if pa.resolue_le} — {pa.resolution === "piece_prelevee" ? "pièce prélevée" : pa.resolution} le {jour(pa.resolue_le)}{/if}
                {#if pa.prelevee_pour} — partie sur {pa.prelevee_pour}{/if}
                {#if pa.note} — {pa.note}{/if}
              </span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    <div>
      <p class="libelle-champ">Son histoire</p>
      {#if fiche.journal.length}
        <ol class="mt-1 space-y-1.5 border-l border-stone-200 pl-3 text-sm dark:border-stone-700">
          {#each fiche.journal as m (m.id)}
            <li>
              <span class="text-xs tabular-nums text-stone-500">{jour(m.quand)}</span>
              <span class="ml-1 font-medium">{GESTES[m.geste] ?? m.geste}</span>
              {#if m.serie !== serie}<span class="text-xs text-stone-500">(de {m.serie})</span>{/if}
              <span class="text-stone-600 dark:text-stone-300">{recit(m)}</span>
              {#if m.raison}<span class="text-xs text-stone-500"> — {raisons[m.raison] ?? m.raison}</span>{/if}
              {#if m.precision}<span class="text-xs text-stone-500"> — {m.precision}</span>{/if}
              {#if m.google}<span class="block text-xs text-stone-500">Google : {m.google}</span>{/if}
            </li>
          {/each}
        </ol>
      {:else}
        <p class="mt-1 text-sm text-stone-500">
          Aucun geste noté dans le programme. Ce que Google dit d'elle est ci-dessus.
        </p>
      {/if}
    </div>
  {/if}

  {#snippet actions()}
    {#if p && ["hs", "reforme", "introuvable", "a_localiser"].includes(p.etat)}
      <Bouton icon={PackagePlus} occupe={occupe === "stock"} onclick={auStock}>Remettre au stock</Bouton>
    {/if}
    {#if p && (p.etat === "en_service" || p.etat === "en_stock")}
      <Bouton variante="primary" icon={ArrowLeftRight} onclick={() => onEchanger(p)}>
        {p.etat === "en_stock" ? "La confier" : "La remplacer ou la reprendre"}
      </Bouton>
    {/if}
    <Bouton onclick={onFermer}>Fermer</Bouton>
  {/snippet}
</Modale>
