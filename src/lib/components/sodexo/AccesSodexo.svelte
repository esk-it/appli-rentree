<script>
  import { onMount } from "svelte";
  import Eye from "@lucide/svelte/icons/eye";
  import EyeOff from "@lucide/svelte/icons/eye-off";
  import Copy from "@lucide/svelte/icons/copy";
  import Check from "@lucide/svelte/icons/check";
  import Lock from "@lucide/svelte/icons/lock";
  import Pencil from "@lucide/svelte/icons/pencil";
  import Bouton from "$lib/components/Bouton.svelte";
  import CopiableTexte from "$lib/components/CopiableTexte.svelte";
  import { coffreApi } from "$lib/api.js";
  import { IDENTIFIANT_SODEXO } from "$lib/sodexo.js";
  import { notify } from "$lib/toasts.js";

  /**
   * L'identifiant et le mot de passe du portail Sodexo, là où on les tape.
   *
   * Johann, 19 octobre 2026 : aller rechercher le mot de passe dans
   * l'ancienne procédure à chaque import. Il n'est pas dans le code — il
   * partirait dans le dépôt et deviendrait faux au premier changement. Il
   * est rangé au coffre, chiffré, et ne s'affiche que coffre ouvert. Le
   * coffre se referme seul après un quart d'heure sans usage.
   */
  const NOM = "sodexo_portail";
  const libelle = (e) => String(e).replace(/^Error:\s*/, "");

  let coffre = $state(/** @type {any} */ (null));
  let service = $state(/** @type {any} */ (null));
  let maitre = $state("");
  let saisie = $state("");
  let edition = $state(false);
  let visible = $state(false);
  let copie = $state(false);
  let occupe = $state(false);

  async function relire() {
    try {
      [coffre, service] = await Promise.all([coffreApi.etat(), coffreApi.service(NOM)]);
    } catch (e) {
      notify.erreur(libelle(e));
    }
  }
  onMount(relire);

  async function ouvrirCoffre() {
    if (!maitre) return;
    occupe = true;
    try {
      await coffreApi.ouvrir(maitre);
      maitre = "";
      await relire();
    } catch (e) {
      notify.erreur(libelle(e));
    } finally {
      occupe = false;
    }
  }

  async function ranger() {
    if (!saisie) return;
    occupe = true;
    try {
      service = await coffreApi.rangerService(NOM, saisie);
      saisie = "";
      edition = false;
      notify.succes("Mot de passe du portail rangé au coffre.");
    } catch (e) {
      notify.erreur(libelle(e));
      await relire();
    } finally {
      occupe = false;
    }
  }

  async function copier() {
    try {
      await navigator.clipboard.writeText(service.mot_de_passe);
      copie = true;
      setTimeout(() => (copie = false), 2000);
    } catch {
      notify.erreur("Le presse-papiers a refusé la copie.");
    }
  }

  const jour = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "");
</script>

<div class="flex flex-wrap items-start gap-x-8 gap-y-3">
  <div>
    <p class="libelle-champ">Identifiant</p>
    <CopiableTexte valeur={IDENTIFIANT_SODEXO} />
  </div>

  <div class="min-w-0">
    <p class="libelle-champ">Mot de passe</p>
    {#if !coffre || !service}
      <p class="mt-1 text-sm text-stone-400">…</p>
    {:else if !coffre.initialise}
      <p class="mt-1 max-w-sm text-sm text-stone-600 dark:text-stone-300">
        Il se range au coffre, qui n'est pas encore créé : L'année › Coffre.
      </p>
    {:else if !service.ouvert}
      <!-- Coffre fermé : le mot de passe maître, ici même. -->
      <form class="mt-1 flex items-center gap-2" onsubmit={(e) => { e.preventDefault(); ouvrirCoffre(); }}>
        <Lock class="h-4 w-4 shrink-0 text-stone-400" />
        <input
          type="password"
          class="champ w-56"
          placeholder="Mot de passe du coffre"
          autocomplete="off"
          bind:value={maitre}
        />
        <Bouton taille="sm" occupe={occupe} disabled={!maitre} onclick={ouvrirCoffre}>Ouvrir</Bouton>
      </form>
      {#if !service.range}
        <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">Pas encore rangé : ouvre le coffre pour le saisir.</p>
      {/if}
    {:else if service.range && !edition}
      <div class="mt-1 flex items-center gap-1.5">
        <span class="rounded-md bg-stone-100 px-2 py-1 font-mono text-sm text-stone-900 dark:bg-stone-800 dark:text-stone-100">
          {visible ? service.mot_de_passe : "••••••••••"}
        </span>
        <button type="button" class="rounded p-1.5 text-stone-500 hover:bg-stone-100 hover:text-stone-900 dark:hover:bg-stone-800 dark:hover:text-stone-100" title={visible ? "Masquer" : "Afficher"} aria-label={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"} onclick={() => (visible = !visible)}>
          {#if visible}<EyeOff class="h-4 w-4" />{:else}<Eye class="h-4 w-4" />{/if}
        </button>
        <button type="button" class="rounded p-1.5 text-stone-500 hover:bg-stone-100 hover:text-stone-900 dark:hover:bg-stone-800 dark:hover:text-stone-100" title="Copier" aria-label="Copier le mot de passe" onclick={copier}>
          {#if copie}<Check class="h-4 w-4 text-vert-600" />{:else}<Copy class="h-4 w-4" />{/if}
        </button>
        <button type="button" class="rounded p-1.5 text-stone-500 hover:bg-stone-100 hover:text-stone-900 dark:hover:bg-stone-800 dark:hover:text-stone-100" title="Changer" aria-label="Changer le mot de passe rangé" onclick={() => (edition = true)}>
          <Pencil class="h-4 w-4" />
        </button>
      </div>
      <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">Rangé au coffre le {jour(service.mis_a_jour_le)}. S'il a changé chez Sodexo, change-le ici.</p>
    {:else}
      <form class="mt-1 flex items-center gap-2" onsubmit={(e) => { e.preventDefault(); ranger(); }}>
        <input
          type="password"
          class="champ w-56"
          placeholder="Mot de passe du portail"
          autocomplete="off"
          bind:value={saisie}
        />
        <Bouton taille="sm" variante="primary" occupe={occupe} disabled={!saisie} onclick={ranger}>Ranger au coffre</Bouton>
        {#if edition}
          <button type="button" class="text-sm text-stone-500 hover:underline" onclick={() => { edition = false; saisie = ""; }}>Annuler</button>
        {/if}
      </form>
    {/if}
  </div>
</div>
