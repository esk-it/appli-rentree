<script>
  import { onMount } from "svelte";
  import Check from "@lucide/svelte/icons/check";
  import Bouton from "$lib/components/Bouton.svelte";
  import { sites as sitesApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Les dossiers de photos propres à un site, à côté du dossier commun.
   *
   * Les photos de NDE ne sont pas rangées avec celles de NDK et de SU : un
   * site peut avoir son propre dossier pour les élèves et pour le
   * personnel. Le réglage vit sur le site depuis la v0.180, mais on le
   * cherche ici, sous le dossier commun — alors il est ici aussi.
   *
   * Vide, le site prend le dossier commun réglé au-dessus.
   */

  let sites = $state(/** @type {any[]} */ ([]));
  let saisies = $state(/** @type {Record<number, {eleves: string, adultes: string}>} */ ({}));
  let enCours = $state(/** @type {number|null} */ (null));

  onMount(async () => {
    try {
      sites = await sitesApi.lister();
      saisies = Object.fromEntries(
        sites.map((s) => [s.id, { eleves: s.dossier_photos_eleves ?? "", adultes: s.dossier_photos_adultes ?? "" }]),
      );
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    }
  });

  const change = (s) =>
    (saisies[s.id]?.eleves ?? "") !== (s.dossier_photos_eleves ?? "") ||
    (saisies[s.id]?.adultes ?? "") !== (s.dossier_photos_adultes ?? "");

  async function enregistrer(s) {
    enCours = s.id;
    try {
      const r = await sitesApi.reglerPhotos(s.id, {
        dossier_photos_eleves: saisies[s.id].eleves,
        dossier_photos_adultes: saisies[s.id].adultes,
      });
      sites = sites.map((x) => (x.id === s.id ? r.site : x));
      saisies[s.id] = { eleves: r.site.dossier_photos_eleves ?? "", adultes: r.site.dossier_photos_adultes ?? "" };
      if (r.injoignables.length) {
        notify.avertissement(
          `${s.nom} : enregistré, mais ce poste ne voit pas ${r.injoignables.join(" ni ")}. ` +
            "Vérifie le chemin, ou que le partage est bien monté.",
          { duree: 12000 },
        );
      } else {
        notify.succes(`Dossiers de photos de ${s.nom} enregistrés.`);
      }
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 10000 });
    } finally {
      enCours = null;
    }
  }
</script>

<div class="mt-5 border-t border-stone-100 pt-4 dark:border-stone-700">
  <p class="text-sm font-medium text-stone-900 dark:text-stone-100">Dossiers propres à un site</p>
  <p class="mt-0.5 text-xs text-stone-500 dark:text-stone-400">
    Pour un site dont les photos ne sont pas rangées avec les autres — NDE,
    par exemple. Vide : le site prend le dossier commun ci-dessus.
  </p>

  <div class="mt-3 space-y-3">
    {#each sites as s (s.id)}
      <div class="grid items-end gap-3 md:grid-cols-[80px_minmax(0,1fr)_minmax(0,1fr)_auto]">
        <span class="pb-2 text-sm font-bold">{s.nom}</span>
        <label class="block">
          <span class="text-xs text-stone-500 dark:text-stone-400">Photos des élèves</span>
          <input
            class="champ mt-1 !py-1.5 font-mono text-xs"
            placeholder="dossier commun"
            bind:value={saisies[s.id].eleves}
          />
        </label>
        <label class="block">
          <span class="text-xs text-stone-500 dark:text-stone-400">Photos du personnel</span>
          <input
            class="champ mt-1 !py-1.5 font-mono text-xs"
            placeholder="dossier commun"
            bind:value={saisies[s.id].adultes}
          />
        </label>
        <Bouton taille="sm" variante="primary" icon={Check} occupe={enCours === s.id} disabled={!change(s)} onclick={() => enregistrer(s)}>
          Enregistrer
        </Bouton>
      </div>
    {/each}
  </div>
</div>
