<script>
  /**
   * Photo d'une personne, avec repli sur ses initiales colorées.
   *
   * La photo vient de `/api/photos/{personneId}` — si le partage réseau
   * `\\ESK-APP01\...` n'est pas joignable, le composant tombe
   * silencieusement sur les initiales.
   *
   * ## Deux formes
   *
   * - `rond` : une pastille de `taille` pixels, pour une ligne de tableau.
   * - `portrait` : la largeur disponible, en 3/4 comme la photo d'identité
   *   d'origine. Le rond y coupe les oreilles et le menton, ce qui suffit à
   *   rendre un visage méconnaissable — et c'est justement ce qu'on demande
   *   à un trombinoscope.
   *
   * @typedef {Object} Props
   * @property {number|null} personneId
   * @property {string} [nom]
   * @property {string} [prenom]
   * @property {number} [taille]            - côté de la pastille, forme ronde
   * @property {"rond"|"portrait"} [forme]
   */
  /** @type {Props} */
  let { personneId, nom = "", prenom = "", taille = 40, forme = "rond" } = $props();

  let echec = $state(false);
  let portrait = $derived(forme === "portrait");

  const BASE = import.meta.env.PROD ? "http://127.0.0.1:8020/api" : "/api";
  let src = $derived(`${BASE}/photos/${personneId}`);

  let initiales = $derived(
    (prenom.charAt(0) + nom.charAt(0)).toUpperCase() || "?",
  );

  // Palette stable : hash simple sur (nom+prenom) → une des 8 couleurs
  const COULEURS = [
    "bg-red-100 text-red-800",
    "bg-orange-100 text-orange-800",
    "bg-amber-100 text-amber-800",
    "bg-emerald-100 text-emerald-800",
    "bg-sky-100 text-sky-800",
    "bg-indigo-100 text-indigo-800",
    "bg-purple-100 text-purple-800",
    "bg-pink-100 text-pink-800",
  ];

  let couleur = $derived.by(() => {
    const cle = (nom + prenom).toLowerCase();
    let hash = 0;
    for (let i = 0; i < cle.length; i++) hash = (hash * 31 + cle.charCodeAt(i)) >>> 0;
    return COULEURS[hash % COULEURS.length];
  });

  /**
   * `shrink-0` n'est pas décoratif.
   *
   * Une image pas encore chargée n'a aucune dimension intrinsèque, et dans
   * une rangée en `flex` elle se laisse écraser à zéro malgré son `width`
   * explicite. Avec le chargement différé, c'est le cas de toutes celles
   * qui sont hors de l'écran : la pastille disparaissait, puis la ligne
   * sautait quand la photo arrivait.
   */
  let classeForme = $derived(
    portrait
      ? "w-full rounded-lg"
      : "shrink-0 rounded-full",
  );
  let styleForme = $derived(
    portrait
      ? "aspect-ratio: 3 / 4;"
      : `width: ${taille}px; height: ${taille}px;`,
  );
</script>

{#if !echec && personneId}
  <!-- Chargement différé : le trombinoscope affiche deux mille cinq cents
       personnes d'un coup, et sans cet attribut le navigateur demande
       autant de photos au partage réseau avant d'en montrer une seule. -->
  <img
    {src}
    alt={`${prenom} ${nom}`}
    loading="lazy"
    decoding="async"
    class="bg-stone-100 object-cover dark:bg-stone-800 {classeForme}"
    style={styleForme}
    onerror={() => (echec = true)}
  />
{:else}
  <div
    class="flex items-center justify-center font-semibold {couleur} {classeForme}"
    style="{styleForme} font-size: {portrait ? 32 : Math.round(taille * 0.4)}px;"
    title={`${prenom} ${nom}`}
  >
    {initiales}
  </div>
{/if}
