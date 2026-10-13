<script>
  import Search from "@lucide/svelte/icons/search";
  import Send from "@lucide/svelte/icons/send";
  import Bouton from "$lib/components/Bouton.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import { googleApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Le mot de passe KoXo, et ce que Google en a fait.
   *
   * KoXo est LE mot de passe ; Google en a reçu une copie à la création du
   * compte, et rien ne la tient à jour (Johann, 13 octobre 2026). Google ne
   * rend aucun mot de passe : on lit dans son journal d'audit qui a changé
   * le sien, et quand. Imposer celui de KoXo est une écriture — « seulement
   * sur mon clic » : rien n'est coché d'avance, et tout passe par une
   * confirmation qui nomme chacun.
   */

  const libelle = (e) => String(e).replace(/^Error:\s*/, "");
  const aujourdhui = new Date();
  // Depuis la rentrée : le 1er août de l'année scolaire en cours.
  let depuis = $state(
    `${aujourdhui.getMonth() >= 7 ? aujourdhui.getFullYear() : aujourdhui.getFullYear() - 1}-08-01`,
  );
  let releve = $state(/** @type {any} */ (null));
  let lecture = $state(false);
  let droitManquant = $state("");
  let coches = $state(/** @type {Set<number>} */ (new Set()));
  let envoi = $state(false);
  let resultats = $state(/** @type {any[]|null} */ (null));

  const STATUTS = {
    impose: { etat: "pret", texte: "Imposé" },
    refuse: { etat: "attente", texte: "Pas envoyé" },
    echec: { etat: "ecart", texte: "Échec" },
  };
  const quand = (iso) =>
    iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—";

  async function lire() {
    lecture = true;
    droitManquant = "";
    resultats = null;
    try {
      releve = await googleApi.changementsMotsDePasse({ depuis });
      coches = new Set();
    } catch (e) {
      const m = libelle(e);
      if (/journal d'audit/i.test(m)) droitManquant = m;
      else notify.erreur(m, { duree: 12000 });
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

  async function imposer() {
    const choisis = (releve?.changements ?? []).filter((c) => coches.has(c.personne_id));
    if (!choisis.length) return;
    const liste = choisis.map((c) => `• ${c.prenom} ${c.nom} — ${c.adresse}`).join("\n");
    const ok = confirm(
      `Imposer à Google le mot de passe KoXo de ${choisis.length} élève(s) ?\n\n${liste}\n\n`
        + "Leur mot de passe Google sera remplacé par celui que le coffre a relu dans KoXo. "
        + "Un élève qui avait changé le sien le perdra.",
    );
    if (!ok) return;
    envoi = true;
    try {
      resultats = await googleApi.imposerMotsDePasse({ personneIds: choisis.map((c) => c.personne_id) });
      const n = resultats.filter((r) => r.statut === "impose").length;
      notify.succes(`${n} mot(s) de passe KoXo imposé(s) à Google.`, { duree: 8000 });
      coches = new Set();
    } catch (e) {
      notify.erreur(libelle(e), { duree: 12000 });
    } finally {
      envoi = false;
    }
  }

  let nbParEleve = $derived((releve?.changements ?? []).filter((c) => c.par_l_eleve).length);
</script>

<div class="card space-y-3 p-4">
  <div class="flex flex-wrap items-end justify-between gap-3">
    <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
      Mots de passe Google
    </h2>
    <div class="flex flex-wrap items-end gap-2">
      <label class="block">
        <span class="libelle-champ">Depuis le</span>
        <input type="date" class="champ w-40" bind:value={depuis} />
      </label>
      <Bouton taille="sm" icon={Search} occupe={lecture} disabled={!depuis} onclick={lire}>
        Lire l'audit Google
      </Bouton>
    </div>
  </div>
  <p class="text-sm text-stone-600 dark:text-stone-400">
    Google ne rend aucun mot de passe : on ne peut pas comparer le sien à
    celui de KoXo. Son journal d'audit dit en revanche qui en a changé un, et
    quand. Un élève qui a changé le sien n'a plus celui de KoXo. Lui imposer
    celui de KoXo ne se fait que sur ton clic, après confirmation.
  </p>

  {#if droitManquant}
    <p class="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
      {droitManquant}
    </p>
  {/if}

  {#if releve}
    <p class="text-sm tabular-nums text-stone-600 dark:text-stone-400">
      Depuis le {new Date(releve.depuis).toLocaleDateString("fr-FR")} :
      <b class="text-stone-900 dark:text-stone-100">{releve.changements.length}</b> élève(s)
      dont le mot de passe Google a changé, dont
      <b class="text-red-700 dark:text-red-400">{nbParEleve}</b> par l'élève lui-même
      {#if releve.nb_hors_eleves}· {releve.nb_hors_eleves} changement(s) hors élèves, non listés{/if}
    </p>
    {#if releve.changements.length}
      <div class="max-h-80 overflow-auto">
        <table class="w-full text-left text-sm">
          <thead class="text-xs uppercase text-stone-500 dark:text-stone-400">
            <tr>
              <th class="w-8 py-1"></th>
              <th class="py-1 pr-3">Élève</th>
              <th class="py-1 pr-3">Dernier changement</th>
              <th class="py-1">Par</th>
            </tr>
          </thead>
          <tbody>
            {#each releve.changements as c (c.personne_id)}
              <tr class="border-t border-stone-200 dark:border-stone-700">
                <td class="py-1.5">
                  <input
                    type="checkbox"
                    class="h-4 w-4 accent-emerald-600"
                    aria-label="Imposer le mot de passe KoXo à {c.prenom} {c.nom}"
                    checked={coches.has(c.personne_id)}
                    onchange={(e) => cocher(c.personne_id, e.currentTarget.checked)}
                  />
                </td>
                <td class="py-1.5 pr-3">
                  {c.nom} {c.prenom}
                  <span class="ml-1 text-xs text-stone-500 dark:text-stone-400">{[c.site, c.classe].filter(Boolean).join(" · ")}</span>
                </td>
                <td class="py-1.5 pr-3 text-xs tabular-nums text-stone-600 dark:text-stone-300">
                  {quand(c.quand)}{c.nb_changements > 1 ? ` · ${c.nb_changements} fois` : ""}
                </td>
                <td class="py-1.5 text-xs">
                  {#if c.par_l_eleve}
                    <Pastille etat="ecart" texte="l'élève" />
                  {:else}
                    <span class="text-stone-600 dark:text-stone-300">{c.par}</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <Bouton variante="primary" taille="sm" icon={Send} occupe={envoi} disabled={!coches.size} onclick={imposer}>
          Imposer le mot de passe KoXo à {coches.size} compte(s)
        </Bouton>
        <span class="text-xs text-stone-500 dark:text-stone-400">
          Rien n'est coché d'avance. Un élève dont le relevé KoXo est à relire n'est pas envoyé.
        </span>
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
          {#if r.statut === "impose" && r.releve_koxo}
            <span class="text-xs text-stone-500 dark:text-stone-400">mot de passe KoXo relevé le {new Date(r.releve_koxo).toLocaleDateString("fr-FR")}</span>
          {/if}
          {#if r.message}
            <span class="w-full text-xs text-stone-500 dark:text-stone-400">{r.message}</span>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>
