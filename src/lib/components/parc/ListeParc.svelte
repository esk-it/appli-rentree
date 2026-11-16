<script>
  import Search from "@lucide/svelte/icons/search";
  import CloudAlert from "@lucide/svelte/icons/cloud-alert";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Download from "@lucide/svelte/icons/download";
  import Pastille from "$lib/components/Pastille.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import { enregistrerFichierBase64 } from "$lib/api.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";
  import { ETATS, CATEGORIES, nomOrgane, ouEst, finMaj, ilYA, jour } from "$lib/parc.js";

  /**
   * Tout le parc, une machine par ligne.
   *
   * La colonne qu'on lit d'abord est « où » : la personne pour une machine
   * du personnel, le chariot ou la salle pour une machine élève, « au
   * stock » pour une machine libre. Le champ de recherche accepte la
   * douchette : un numéro de série scanné suivi d'Entrée ouvre la fiche.
   *
   * @typedef {Object} Props
   * @property {any[]} postes
   * @property {(serie: string) => void} onOuvrir
   */
  /** @type {Props} */
  let { postes = [], onOuvrir } = $props();

  let recherche = $state("");
  let categorie = $state(lire("parc.categorie", "tout"));
  let etat = $state(lire("parc.etat", ""));
  let site = $state(lire("parc.site", ""));
  let lieu = $state("");
  let seulementSignalees = $state(false);
  $effect(() => ecrire("parc.categorie", categorie));
  $effect(() => ecrire("parc.etat", etat));
  $effect(() => ecrire("parc.site", site));

  const plier = (s) =>
    String(s ?? "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase();

  let options = $derived([
    { id: "tout", label: "Tout", badge: postes.length },
    ...["personnel", "eleves", "nde"].map((c) => ({
      id: c,
      label: CATEGORIES[c],
      badge: postes.filter((p) => p.categorie === c).length,
    })),
  ]);

  let lieux = $derived(
    [...new Set(postes.filter((p) => categorie === "tout" || p.categorie === categorie).map((p) => p.lieu).filter(Boolean))].sort(),
  );

  let filtres = $derived.by(() => {
    const mots = plier(recherche).trim().split(/\s+/).filter(Boolean);
    return postes.filter((p) => {
      if (categorie !== "tout" && p.categorie !== categorie) return false;
      if (etat && p.etat !== etat) return false;
      if (site && p.site !== site) return false;
      if (lieu && p.lieu !== lieu) return false;
      if (seulementSignalees && !(p.a_reporter.length || p.a_verifier || p.porteur_parti || p.etat === "a_localiser")) return false;
      if (mots.length) {
        const foin = plier(
          [p.serie, p.etiquette, p.porteur, p.porteur_nom, p.lieu, p.tenue_par, p.modele, p.emplacement, p.porteur_probable_nom]
            .concat(p.derniers_utilisateurs ?? [])
            .join(" "),
        );
        if (!mots.every((m) => foin.includes(m))) return false;
      }
      return true;
    });
  });

  // Au-delà, la liste ralentit sans rien apprendre de plus : on affine.
  const LIMITE = 300;

  /** La douchette tape le numéro puis Entrée : on ouvre la machine trouvée. */
  function entree(e) {
    if (e.key !== "Enter") return;
    const q = recherche.trim().toLowerCase();
    const exacte = postes.find((p) => p.serie.toLowerCase() === q || p.etiquette.toLowerCase() === q);
    if (exacte) onOuvrir(exacte.serie);
    else if (filtres.length === 1) onOuvrir(filtres[0].serie);
  }

  function exporter() {
    const entetes = ["Série", "Étiquette", "Modèle", "Catégorie", "Site", "État", "Où / qui",
                     "Adresse", "Pannes", "Fin des mises à jour", "Dernière synchro", "À reporter", "À vérifier"];
    const lignes = filtres.map((p) => [
      p.serie, p.etiquette, p.modele, CATEGORIES[p.categorie] ?? p.categorie, p.site ?? "",
      ETATS[p.etat]?.texte ?? p.etat, ouEst(p), p.porteur ?? "", p.pannes.map(nomOrgane).join(" / "),
      p.fin_maj ?? "", (p.derniere_synchro ?? "").slice(0, 10), p.a_reporter.join(", "), p.a_verifier ?? "",
    ]);
    const csv = [entetes, ...lignes]
      .map((l) => l.map((c) => `"${String(c).replaceAll('"', '""')}"`).join(";"))
      .join("\r\n");
    // Le BOM : sans lui, Excel lit les accents de travers.
    const octets = new TextEncoder().encode("﻿" + csv);
    let binaire = "";
    for (const o of octets) binaire += String.fromCharCode(o);
    enregistrerFichierBase64("Parc_chromebooks.csv", btoa(binaire), "text/csv");
  }
</script>

<div class="space-y-3">
  <div class="flex flex-wrap items-center gap-3">
    <Segments {options} bind:valeur={categorie} taille="sm" />
    <div class="relative min-w-64 flex-1">
      <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
      <input
        class="champ pl-9"
        placeholder="Série (douchette), nom, étiquette, chariot…"
        bind:value={recherche}
        onkeydown={entree}
      />
    </div>
  </div>

  <div class="flex flex-wrap items-center gap-2 text-sm">
    <select class="champ max-w-48 text-xs" bind:value={etat} aria-label="Filtrer par état">
      <option value="">Tous les états</option>
      {#each Object.entries(ETATS) as [id, e] (id)}
        <option value={id}>{e.texte}</option>
      {/each}
    </select>
    <select class="champ max-w-48 text-xs" bind:value={site} aria-label="Filtrer par site">
      <option value="">Tous les sites</option>
      <option value="NDK">NDK</option>
      <option value="SU">SU</option>
      <option value="NDE">NDE</option>
    </select>
    {#if lieux.length}
      <select class="champ max-w-56 text-xs" bind:value={lieu} aria-label="Filtrer par salle ou chariot">
        <option value="">Toutes les salles</option>
        {#each lieux as l (l)}
          <option value={l}>{l}</option>
        {/each}
      </select>
    {/if}
    <label class="flex items-center gap-1.5 text-xs text-stone-600 dark:text-stone-300">
      <input type="checkbox" class="accent-emerald-600" bind:checked={seulementSignalees} />
      Seulement ce qui demande un geste
    </label>
    <span class="ml-auto text-xs text-stone-500 tabular-nums">{filtres.length} machine{filtres.length > 1 ? "s" : ""}</span>
    <Bouton taille="sm" icon={Download} onclick={exporter}>Exporter</Bouton>
  </div>

  <div class="overflow-x-auto">
    <table class="tableau min-w-[58rem]">
      <thead class="entete-tableau">
        <tr>
          <th class="px-3 py-2 text-left">Machine</th>
          <th class="px-3 py-2 text-left">Où / qui</th>
          <th class="px-3 py-2 text-left">État</th>
          <th class="px-3 py-2 text-left">Mises à jour</th>
          <th class="px-3 py-2 text-left">Vue</th>
        </tr>
      </thead>
      <tbody class="corps-tableau">
        {#each filtres.slice(0, LIMITE) as p (p.serie)}
          {@const maj = finMaj(p.fin_maj)}
          <tr class="cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50" onclick={() => onOuvrir(p.serie)}>
            <td class="px-3 py-1.5">
              <p class="font-medium text-stone-900 dark:text-stone-100">
                {p.etiquette_voulue ?? (p.etiquette || "(sans étiquette)")}
              </p>
              <p class="font-mono text-[11px] text-stone-500">{p.serie}</p>
            </td>
            <td class="px-3 py-1.5">
              <p class="text-stone-800 dark:text-stone-200">{ouEst(p)}</p>
              <p class="text-xs text-stone-500 dark:text-stone-400">
                {#if p.porteur_probable && !p.porteur}
                  <span class="italic text-sky-700 dark:text-sky-400">utilisée par {p.porteur_probable_nom}</span>
                {:else if p.porteur_parti}
                  <span class="font-semibold text-red-700 dark:text-red-400">plus inscrit cette année</span>
                {:else if p.porteur && !p.porteur_nom}
                  hors référentiel
                {:else}
                  {p.porteur_detail ?? CATEGORIES[p.categorie] ?? ""}{p.site ? ` · ${p.site}` : ""}
                {/if}
              </p>
            </td>
            <td class="px-3 py-1.5">
              <div class="flex flex-wrap items-center gap-1">
                <Pastille etat={ETATS[p.etat]?.pastille ?? "inconnu"} texte={ETATS[p.etat]?.texte ?? p.etat} />
                {#each p.pannes as o (o)}
                  <Pastille etat="ecart" texte={nomOrgane(o)} />
                {/each}
                {#if p.a_reporter.length}
                  <span title="Google n'a pas encore reçu : {p.a_reporter.join(', ')}">
                    <CloudAlert class="h-4 w-4 text-amber-600 dark:text-amber-400" />
                  </span>
                {/if}
                {#if p.a_verifier}
                  <span title={p.a_verifier}>
                    <TriangleAlert class="h-4 w-4 text-amber-600 dark:text-amber-400" />
                  </span>
                {/if}
              </div>
            </td>
            <td class="whitespace-nowrap px-3 py-1.5 text-xs {maj.ton}">{maj.texte}</td>
            <td class="whitespace-nowrap px-3 py-1.5 text-xs text-stone-500 dark:text-stone-400" title={jour(p.derniere_synchro)}>
              {p.derniere_synchro ? ilYA(p.derniere_synchro) : "jamais"}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
    {#if filtres.length > LIMITE}
      <p class="py-3 text-center text-xs text-stone-500">
        {LIMITE} premières sur {filtres.length} — affine la recherche pour voir les autres.
      </p>
    {:else if !filtres.length}
      <p class="py-8 text-center text-sm text-stone-500">Aucune machine ne correspond.</p>
    {/if}
  </div>
</div>
