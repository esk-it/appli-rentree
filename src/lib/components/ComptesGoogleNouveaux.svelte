<script>
  import Search from "@lucide/svelte/icons/search";
  import UserPlus from "@lucide/svelte/icons/user-plus";
  import FileDown from "@lucide/svelte/icons/file-down";
  import CreditCard from "@lucide/svelte/icons/credit-card";
  import Bouton from "$lib/components/Bouton.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import { enregistrerFichierBase64, exportsCible, googleApi } from "$lib/api.js";
  import { ecrire } from "$lib/memoire.svelte.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Les comptes Google des élèves qui viennent d'arriver.
   *
   * Johann les créait à la main dans la console, une fois le compte KoXo
   * fait et ses identifiants recopiés dans Charlemagne. L'export enrichi
   * range ce mot de passe au coffre : le programme a tout pour créer le
   * compte lui-même. Il montre d'abord qui, où et avec quelle adresse —
   * créer un compte se voit dehors —, puis le fait en un clic, le place
   * dans son groupe de classe, et propose son étiquette et sa carte.
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  const libelle = (e) => String(e).replace(/^Error:\s*/, "");
  const ORIGINES = { google: "fabriqué (NDE)", koxo: "KoXo", charlemagne: "Charlemagne" };
  const STATUTS = {
    cree: { etat: "pret", texte: "Créé" },
    existait: { etat: "reference", texte: "Existait déjà" },
    ignore: { etat: "attente", texte: "Pas créé" },
    echec: { etat: "ecart", texte: "Échec" },
  };

  let releve = $state(/** @type {any} */ (null));
  let lecture = $state(false);
  let creation = $state(false);
  let coches = $state(/** @type {Set<number>} */ (new Set()));
  let resultats = $state(/** @type {any[]|null} */ (null));
  /** Ceux qu'on a demandé de créer, tels que le relevé les décrivait :
   * après la création, le relevé ne les porte plus. */
  let demandes = $state(/** @type {any[]} */ ([]));
  let coffreFerme = $state(false);

  let creables = $derived((releve?.a_creer ?? []).filter((c) => !c.bloque));
  let faits = $derived((resultats ?? []).filter((r) => r.statut === "cree" || r.statut === "existait"));

  /** Lit les comptes du domaine et relève qui n'en a pas. Lecture seule. */
  export async function verifier() {
    lecture = true;
    resultats = null;
    coffreFerme = false;
    try {
      releve = await googleApi.nouveauxSansCompte();
      coches = new Set(creables.map((c) => c.personne_id));
    } catch (e) {
      notify.erreur(libelle(e), { duree: 10000 });
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

  async function creer() {
    const choisis = creables.filter((c) => coches.has(c.personne_id));
    if (!choisis.length) return;
    const liste = choisis.map((c) => `• ${c.prenom} ${c.nom} — ${c.adresse}`).join("\n");
    if (!confirm(`Créer ${choisis.length} compte(s) Google ?\n\n${liste}`)) return;
    creation = true;
    demandes = choisis;
    try {
      resultats = await googleApi.creerNouveauxComptes({ personneIds: choisis.map((c) => c.personne_id) });
      const n = resultats.filter((r) => r.statut === "cree").length;
      notify.succes(`${n} compte(s) Google créé(s).`, { duree: 8000 });
      for (const r of resultats.filter((r) => r.statut === "echec" || r.statut === "ignore")) {
        notify.avertissement(`${r.prenom} ${r.nom} : ${r.message}`, { duree: 12000 });
      }
      const restants = await googleApi.nouveauxSansCompte().catch(() => null);
      if (restants) releve = restants;
    } catch (e) {
      const m = libelle(e);
      coffreFerme = /coffre est fermé/i.test(m);
      notify.erreur(m, { duree: 12000 });
    } finally {
      creation = false;
    }
  }

  async function etiquettes() {
    try {
      const r = await exportsCible.etiquettesCoffre({ personneIds: faits.map((r) => r.personne_id) });
      for (const f of r.fichiers) {
        await enregistrerFichierBase64(
          f.nom_fichier, f.contenu_base64,
          f.nom_fichier.endsWith(".pdf") ? "application/pdf" : "text/html",
        );
      }
      for (const a of r.avertissements) notify.avertissement(a, { duree: 10000 });
      if (r.sans_mot_de_passe.length) {
        notify.avertissement(`Sans mot de passe au coffre : ${r.sans_mot_de_passe.join(", ")}`, { duree: 10000 });
      }
    } catch (e) {
      notify.erreur(libelle(e), { duree: 10000 });
    }
  }

  function cartes() {
    // L'écran des cartes retient sa sélection : on la lui prépare.
    const ids = new Set(faits.map((r) => r.personne_id));
    const lignes = demandes.filter((c) => ids.has(c.personne_id));
    const classes = [...new Set(lignes.map((c) => c.classe).filter(Boolean))];
    const sitesFaits = [...new Set(lignes.map((c) => c.site).filter(Boolean))];
    ecrire("cartes.site", sitesFaits.length === 1 ? sitesFaits[0] : "");
    ecrire("cartes.classes", classes);
    ecrire("cartes.coches", faits.map((r) => r.personne_id));
    onNaviguer?.("cartes");
  }
</script>

<div class="card space-y-3 p-5">
  <div class="flex flex-wrap items-start justify-between gap-3">
    <div class="min-w-0">
      <h2 class="text-lg font-semibold text-stone-900 dark:text-stone-100">Comptes Google des nouveaux</h2>
      <p class="mt-0.5 max-w-2xl text-sm text-stone-600 dark:text-stone-400">
        Les inscrits de l'année qu'aucun compte Google ne porte, avec le mot de
        passe que Charlemagne ou KoXo a mis au coffre. Rien n'est créé sans ton clic.
      </p>
    </div>
    <Bouton icon={Search} occupe={lecture} onclick={verifier}>Vérifier dans Google</Bouton>
  </div>

  {#if releve}
    <p class="text-sm text-stone-600 tabular-nums dark:text-stone-400">
      {releve.annee} · <b>{releve.nb_inscrits}</b> élèves inscrits, dont
      <b>{releve.nb_avec_compte}</b> avec un compte —
      <b class="text-stone-900 dark:text-stone-100">{releve.a_creer.length}</b> à créer
      {#if releve.a_rattacher.length}· <b>{releve.a_rattacher.length}</b> à rattacher{/if}
    </p>

    {#if releve.a_creer.length}
      <div class="overflow-x-auto">
        <table class="tableau w-full text-sm">
          <thead>
            <tr>
              <th class="w-8"></th>
              <th class="text-left">Élève</th>
              <th class="text-left">Classe</th>
              <th class="text-left">Adresse</th>
              <th class="text-left">Unité</th>
              <th class="text-left">Mot de passe</th>
            </tr>
          </thead>
          <tbody>
            {#each releve.a_creer as c (c.personne_id)}
              <tr>
                <td>
                  <input
                    type="checkbox"
                    class="h-4 w-4 accent-emerald-600"
                    aria-label="Créer le compte de {c.prenom} {c.nom}"
                    disabled={!!c.bloque}
                    checked={!c.bloque && coches.has(c.personne_id)}
                    onchange={(e) => cocher(c.personne_id, e.currentTarget.checked)}
                  />
                </td>
                <td class="whitespace-nowrap font-medium">{c.prenom} <span class="uppercase">{c.nom}</span></td>
                <td class="whitespace-nowrap">{c.site ?? "—"} · {c.classe ?? "—"}</td>
                {#if c.bloque}
                  <td colspan="3" class="text-xs text-amber-800 dark:text-amber-300">{c.bloque}</td>
                {:else}
                  <td class="font-mono text-xs">{c.adresse}</td>
                  <td class="font-mono text-xs text-stone-500 dark:text-stone-400">{c.ou}</td>
                  <td><Pastille etat="reference" texte={ORIGINES[c.origine_mot_de_passe] ?? "—"} /></td>
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <Bouton
          variante="primary"
          icon={UserPlus}
          occupe={creation}
          disabled={!creables.some((c) => coches.has(c.personne_id))}
          onclick={creer}
        >
          Créer {creables.filter((c) => coches.has(c.personne_id)).length} compte(s)
        </Bouton>
        {#if coffreFerme}
          <span class="text-sm text-amber-800 dark:text-amber-300">
            Le coffre garde les mots de passe :
            <button type="button" class="font-semibold underline" onclick={() => onNaviguer?.("coffre")}>ouvre-le</button>,
            puis recommence.
          </span>
        {/if}
      </div>
    {:else}
      <p class="text-sm text-stone-600 dark:text-stone-400">Tous les inscrits ont leur compte Google.</p>
    {/if}

    {#if releve.a_rattacher.length}
      <div class="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-900/20">
        <p class="font-medium text-amber-900 dark:text-amber-200">
          Un compte au même nom existe sous une autre adresse — pas de création
        </p>
        <ul class="mt-1.5 space-y-1 text-xs text-amber-900 dark:text-amber-200">
          {#each releve.a_rattacher as a (a.personne_id)}
            <li>
              <b>{a.prenom} {a.nom}</b> ({a.classe ?? "—"}) : <span class="font-mono">{a.adresses_google.join(", ")}</span>
              — si c'est le sien, fige cette adresse sur sa fiche.
            </li>
          {/each}
        </ul>
      </div>
    {/if}
  {/if}

  {#if resultats}
    <ul class="space-y-1.5 border-t border-stone-200 pt-3 text-sm dark:border-stone-700">
      {#each resultats as r (r.personne_id)}
        {@const s = STATUTS[r.statut] ?? STATUTS.echec}
        <li class="flex flex-wrap items-center gap-2">
          <Pastille etat={s.etat} texte={s.texte} />
          <span class="font-medium">{r.prenom} {r.nom}</span>
          <span class="font-mono text-xs text-stone-500 dark:text-stone-400">{r.adresse}</span>
          {#if r.groupe}
            <span class="text-xs text-stone-500 dark:text-stone-400">
              {r.groupe_ok ? `dans ${r.groupe}` : `pas dans ${r.groupe}`}
            </span>
          {/if}
          {#if r.message && r.statut !== "cree"}
            <span class="w-full text-xs text-stone-500 dark:text-stone-400">{r.message}</span>
          {/if}
        </li>
      {/each}
    </ul>
    {#if faits.length}
      <div class="flex flex-wrap gap-2">
        <Bouton taille="sm" icon={FileDown} onclick={etiquettes}>Leurs étiquettes (PDF)</Bouton>
        <Bouton taille="sm" icon={CreditCard} onclick={cartes}>Préparer leurs cartes</Bouton>
      </div>
    {/if}
  {/if}
</div>
