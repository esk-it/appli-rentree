<script>
  import { tick } from "svelte";
  import ScanBarcode from "@lucide/svelte/icons/scan-barcode";
  import ClipboardCheck from "@lucide/svelte/icons/clipboard-check";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import UserCheck from "@lucide/svelte/icons/user-check";
  import Bouton from "$lib/components/Bouton.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import ChoixPersonne from "./ChoixPersonne.svelte";
  import { parc } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { CATEGORIES, ETATS, LIBELLES_ORGANE, ilYA, jour, messageErreur, ouEst } from "$lib/parc.js";

  /**
   * L'inventaire physique : faire le tour, et corriger ce que le programme croit.
   *
   * ## Pourquoi (Johann, 16/11/2026)
   *
   * Personne ne sait plus exactement où sont toutes les machines — les
   * « Maintenance » sont-elles chez un adulte, ou dans la pile des pannes ?
   * Le programme ne devine pas : il dit ce qu'il croit, et chaque machine
   * qu'on a sous les yeux le corrige. Au fil du tour, le référentiel se
   * nettoie de ses petites erreurs.
   *
   * ## Le geste
   *
   * Scanner (ou taper) le numéro, puis dire ce qu'on constate. Le champ
   * reprend la main aussitôt : on enchaîne les machines d'un chariot sans
   * toucher la souris pour celles qui sont justes — Entrée, puis Entrée.
   *
   * Les étiquettes Google qui en découlent attendent dans « à reporter » :
   * un clic les écrit toutes, à la fin.
   *
   * @typedef {Object} Props
   * @property {any} inv
   * @property {any[]} personnes
   * @property {any} vocabulaire
   * @property {(inv: any) => void} onInventaire
   * @property {(serie: string) => void} onOuvrir
   */
  /** @type {Props} */
  let { inv, personnes = [], vocabulaire, onInventaire, onOuvrir } = $props();

  let champ = $state(/** @type {HTMLInputElement|null} */ (null));
  let saisie = $state("");
  let choisie = $state(/** @type {any} */ (null));
  let inconnue = $state("");
  let mode = $state(/** @type {"" | "porteur" | "lieu" | "hs"} */ (""));
  let porteur = $state("");
  let lieu = $state("");
  let organes = $state(/** @type {string[]} */ ([]));
  let note = $state("");
  let occupe = $state(false);
  let dernier = $state("");

  let categorie = $state("personnel");
  let priorite = $state(true);

  let postes = $derived(inv?.postes ?? []);
  let depuis = $derived(inv?.pointage_depuis ?? null);
  let total = $derived((inv?.pointees ?? 0) + (inv?.a_pointer ?? 0));
  let part = $derived(total ? Math.round((100 * (inv?.pointees ?? 0)) / total) : 0);

  const vue = (p) => depuis && p.pointe_le && p.pointe_le >= depuis;
  const douteuse = (p) =>
    p.etat === "a_localiser" || p.a_verifier || p.porteur_probable || p.dort || p.porteur_parti;

  let lieux = $derived([...new Set(postes.map((p) => p.lieu).filter(Boolean))].sort());

  /** Ce qui reste à voir, les machines douteuses d'abord. */
  let restantes = $derived(
    postes
      .filter((p) => !["reforme", "desactivee"].includes(p.etat) && p.present_google !== false)
      .filter((p) => !vue(p))
      .filter((p) => categorie === "tout" || p.categorie === categorie)
      .filter((p) => !priorite || douteuse(p))
      .sort((a, b) => Number(!!douteuse(b)) - Number(!!douteuse(a)) || (a.lieu ?? "").localeCompare(b.lieu ?? "") || a.serie.localeCompare(b.serie)),
  );

  async function commencer() {
    occupe = true;
    try {
      onInventaire(await parc.commencerPointage());
      notify.succes("Inventaire ouvert : chaque machine vue à partir d'aujourd'hui compte.");
      await tick();
      champ?.focus();
    } catch (e) {
      notify.erreur(messageErreur(e));
    } finally {
      occupe = false;
    }
  }

  function choisir(p) {
    choisie = p;
    inconnue = "";
    mode = "";
    porteur = p.porteur ?? p.porteur_probable ?? "";
    lieu = p.lieu ?? "";
    organes = [...(p.pannes ?? [])];
    note = "";
  }

  function chercher(e) {
    if (e.key !== "Enter") return;
    const q = saisie.trim().toLowerCase();
    if (!q) {
      // Entrée sur un champ vide : « c'est juste » pour la machine affichée.
      if (choisie && choisie.etat !== "a_localiser") constater("conforme");
      return;
    }
    const p = postes.find((x) => x.serie.toLowerCase() === q || (x.etiquette ?? "").toLowerCase() === q);
    saisie = "";
    if (p) choisir(p);
    else {
      choisie = null;
      inconnue = q.toUpperCase();
    }
  }

  async function constater(constat, serie = choisie?.serie ?? inconnue) {
    if (!serie) return;
    occupe = true;
    try {
      const r = await parc.pointer(serie, {
        constat,
        porteur: constat === "porteur" ? porteur.trim() : null,
        lieu: constat === "lieu" ? lieu.trim() : null,
        organes: constat === "hs" ? organes : [],
        note: note.trim() || null,
      });
      dernier = r.message;
      onInventaire(r.inventaire);
      if (serie === (choisie?.serie ?? inconnue)) {
        choisie = null;
        inconnue = "";
        mode = "";
      }
      await tick();
      champ?.focus();
    } catch (e) {
      notify.erreur(messageErreur(e), { duree: 10000 });
    } finally {
      occupe = false;
    }
  }

  function basculerOrgane(o) {
    organes = organes.includes(o) ? organes.filter((x) => x !== o) : [...organes, o];
  }
</script>

{#if !depuis}
  <div class="max-w-2xl space-y-3">
    <p class="text-sm text-stone-700 dark:text-stone-300">
      Fais le tour du parc, machine en main : scanne son numéro et dis ce que tu constates — elle
      est bien là où le programme le croit, au stock, chez quelqu'un, dans une salle, en panne. À la
      fin, ce que tu n'as pas trouvé se marque « introuvable ».
    </p>
    <p class="text-sm text-stone-600 dark:text-stone-400">
      Le programme compte ce que tu as vu depuis l'ouverture, et met en tête ce qui est douteux : les
      machines qu'il ne sait pas situer, celles qu'un autre utilise que celui de l'étiquette, celles
      qui ne se sont pas connectées depuis un an.
    </p>
    <Bouton variante="primary" icon={ClipboardCheck} occupe={occupe} onclick={commencer}>
      Commencer l'inventaire
    </Bouton>
  </div>
{:else}
  <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
    <!-- Scanner, et dire ce qu'on voit -->
    <section class="space-y-4">
      <div>
        <div class="flex items-baseline justify-between text-sm">
          <span>
            <strong class="tabular-nums">{inv.pointees}</strong> machine{inv.pointees > 1 ? "s" : ""} vue{inv.pointees > 1 ? "s" : ""}
            sur <span class="tabular-nums">{total}</span>
          </span>
          <span class="text-xs text-stone-500">
            inventaire ouvert le {jour(depuis)} ·
            <button
              class="underline decoration-dotted hover:text-stone-800 dark:hover:text-stone-200"
              onclick={() => confirm("Ouvrir un nouvel inventaire ? Toutes les machines redeviendront « à voir » (les corrections déjà faites restent).") && commencer()}
            >
              en ouvrir un nouveau
            </button>
          </span>
        </div>
        <div class="mt-1.5 h-2 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800">
          <div class="h-full rounded-full bg-emerald-600 transition-all" style="width: {part}%"></div>
        </div>
      </div>

      <div class="relative">
        <ScanBarcode class="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-stone-400" />
        <input
          bind:this={champ}
          class="champ py-3 pl-11 font-mono text-base"
          placeholder="Scanne ou tape le numéro de série, ou l'étiquette"
          bind:value={saisie}
          onkeydown={chercher}
        />
      </div>
      {#if dernier}
        <p class="text-xs text-emerald-700 dark:text-emerald-400">✓ {dernier}</p>
      {/if}

      {#if inconnue}
        <div class="card space-y-2 p-4 text-sm">
          <p><span class="font-mono font-semibold">{inconnue}</span> est inconnue de Google et du programme.</p>
          <p class="text-xs text-stone-500">
            Vérifie le numéro. Si c'est bien une machine de l'établissement, note ce qu'elle est : elle
            entrera dans l'inventaire, signalée « hors Google ».
          </p>
          <div class="flex flex-wrap gap-2">
            <Bouton taille="sm" onclick={() => constater("stock")}>Au stock</Bouton>
            <Bouton taille="sm" onclick={() => constater("hs")}>En panne</Bouton>
            <Bouton taille="sm" onclick={() => (inconnue = "")}>Laisser</Bouton>
          </div>
        </div>
      {:else if choisie}
        {@const p = choisie}
        <div class="card space-y-3 p-4">
          <div class="flex flex-wrap items-baseline gap-2">
            <button class="text-lg font-semibold hover:underline" onclick={() => onOuvrir(p.serie)}>
              {p.etiquette_voulue ?? (p.etiquette || p.serie)}
            </button>
            <span class="font-mono text-xs text-stone-500">{p.serie}</span>
            <Pastille etat={ETATS[p.etat]?.pastille ?? "inconnu"} texte={ETATS[p.etat]?.texte ?? p.etat} />
          </div>
          <p class="text-sm">
            Le programme croit : <strong>{ouEst(p)}</strong>
            {#if p.porteur_detail}<span class="text-stone-500"> · {p.porteur_detail}</span>{/if}
          </p>
          {#if p.a_verifier}
            <p class="flex items-start gap-1.5 text-xs text-amber-800 dark:text-amber-300">
              <TriangleAlert class="mt-0.5 h-3.5 w-3.5 shrink-0" /> {p.a_verifier}
            </p>
          {/if}
          <p class="text-xs text-stone-500">
            Dernière connexion {ilYA(p.derniere_synchro)}{#if p.derniers_utilisateurs?.length}, par {p.derniers_utilisateurs[0]}{/if}
          </p>

          <div class="flex flex-wrap gap-2">
            <Bouton variante="primary" occupe={occupe} disabled={p.etat === "a_localiser"} onclick={() => constater("conforme")}>
              C'est juste
            </Bouton>
            {#if p.porteur_probable && p.porteur_probable !== p.porteur}
              <Bouton icon={UserCheck} occupe={occupe} onclick={() => { porteur = p.porteur_probable; constater("porteur"); }}>
                Chez {p.porteur_probable_nom}
              </Bouton>
            {/if}
            <Bouton onclick={() => constater("stock")}>Au stock</Bouton>
            <Bouton onclick={() => (mode = mode === "porteur" ? "" : "porteur")}>Chez quelqu'un…</Bouton>
            <Bouton onclick={() => (mode = mode === "lieu" ? "" : "lieu")}>Dans une salle…</Bouton>
            <Bouton onclick={() => (mode = mode === "hs" ? "" : "hs")}>En panne…</Bouton>
            <Bouton onclick={() => constater("reforme")}>À réformer</Bouton>
          </div>

          {#if mode === "porteur"}
            <div class="flex flex-wrap items-start gap-2">
              <div class="min-w-64 flex-1">
                <ChoixPersonne {personnes} bind:valeur={porteur} />
              </div>
              <Bouton variante="primary" disabled={!porteur.trim()} occupe={occupe} onclick={() => constater("porteur")}>Noter</Bouton>
            </div>
          {:else if mode === "lieu"}
            <div class="flex flex-wrap items-start gap-2">
              <input class="champ min-w-48 flex-1" list="pointage-lieux" placeholder="K-B5-13, SU-CDI, B112…" bind:value={lieu} />
              <datalist id="pointage-lieux">
                {#each lieux as l (l)}<option value={l}></option>{/each}
              </datalist>
              <Bouton variante="primary" disabled={!lieu.trim()} occupe={occupe} onclick={() => constater("lieu")}>Noter</Bouton>
            </div>
          {:else if mode === "hs"}
            <div class="space-y-2">
              <div class="flex flex-wrap gap-1.5">
                {#each vocabulaire?.organes ?? [] as o (o)}
                  <button
                    type="button"
                    class="rounded-full border px-2.5 py-1 text-xs transition {organes.includes(o)
                      ? 'border-red-400 bg-red-50 font-medium text-red-800 dark:bg-red-900/40 dark:text-red-300'
                      : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
                    onclick={() => basculerOrgane(o)}
                  >
                    {LIBELLES_ORGANE[o] ?? o}
                  </button>
                {/each}
              </div>
              <Bouton variante="primary" occupe={occupe} onclick={() => constater("hs")}>Noter en panne</Bouton>
            </div>
          {/if}

          <input class="champ text-sm" placeholder="Note (facultatif) : rangée dans l'armoire B, coque fendue…" bind:value={note} />
          <p class="text-xs text-stone-500">Entrée dans le champ vide = « C'est juste ».</p>
        </div>
      {/if}
    </section>

    <!-- Ce qui reste à voir -->
    <section class="space-y-3">
      <div class="flex flex-wrap items-center gap-3">
        <h3 class="titre-section">Pas encore vues</h3>
        <Segments
          taille="sm"
          bind:valeur={categorie}
          options={[
            { id: "personnel", label: CATEGORIES.personnel },
            { id: "eleves", label: CATEGORIES.eleves },
            { id: "nde", label: CATEGORIES.nde },
            { id: "tout", label: "Tout" },
          ]}
        />
      </div>
      <label class="flex items-center gap-1.5 text-xs text-stone-600 dark:text-stone-300">
        <input type="checkbox" class="accent-emerald-600" bind:checked={priorite} />
        Seulement les douteuses (à localiser, contredites, muettes depuis un an…)
      </label>
      <p class="text-xs text-stone-500 tabular-nums">{restantes.length} machine{restantes.length > 1 ? "s" : ""}</p>
      <ul class="divide-y divide-stone-100 dark:divide-stone-800">
        {#each restantes.slice(0, 200) as p (p.serie)}
          <li class="flex items-center gap-3 py-1.5 text-sm">
            <button class="min-w-0 flex-1 text-left" onclick={() => choisir(p)}>
              <span class="font-medium">{p.etiquette || p.serie}</span>
              <span class="ml-1 text-xs text-stone-500">{ouEst(p)}</span>
              {#if p.a_verifier}
                <span class="block truncate text-xs text-amber-800 dark:text-amber-300">{p.a_verifier}</span>
              {/if}
            </button>
            <button
              class="shrink-0 text-xs text-stone-500 underline decoration-dotted hover:text-red-600"
              title="À la fin du tour : elle n'a pas été trouvée"
              onclick={() => constater("introuvable", p.serie)}
            >
              introuvable
            </button>
          </li>
        {/each}
      </ul>
      {#if !restantes.length}
        <p class="text-sm text-stone-500">
          {priorite ? "Plus rien de douteux ici. Décoche la case pour voir le reste." : "Tout a été vu."}
        </p>
      {/if}
    </section>
  </div>
{/if}
