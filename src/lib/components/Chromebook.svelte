<script>
  /**
   * Un Chromebook dessiné, plutôt qu'une icône générique d'ordinateur.
   *
   * Une photographie de produit poserait deux problèmes : les droits, et le
   * poids d'une image par modèle alors que le parc en compte une dizaine.
   * Un tracé vectoriel reste net à toute taille, suit la couleur du texte
   * qui l'entoure, et pèse quelques centaines d'octets.
   *
   * L'état se lit dans le remplissage de l'écran, pas dans une pastille
   * posée à côté : un objet qui dort n'a pas la même présence qu'un objet
   * en service, et c'est l'écran éteint qui le dit le mieux.
   */

  /**
   * @typedef {Object} Props
   * @property {number} [taille]
   * @property {"actif"|"dormant"|"libre"|"rendu"|"hs"} [etat]
   * @property {string} [classe]
   */
  let { taille = 40, etat = "actif", classe = "" } = $props();

  const ECRANS = {
    actif: "fill-emerald-500/20 dark:fill-emerald-400/25",
    dormant: "fill-amber-500/15 dark:fill-amber-400/15",
    libre: "fill-sky-500/15 dark:fill-sky-400/20",
    rendu: "fill-emerald-500/30 dark:fill-emerald-400/30",
    hs: "fill-stone-400/15 dark:fill-stone-500/20",
  };

  const TRAITS = {
    actif: "text-stone-500 dark:text-stone-400",
    dormant: "text-amber-600/70 dark:text-amber-500/70",
    libre: "text-sky-600/70 dark:text-sky-500/70",
    rendu: "text-emerald-600 dark:text-emerald-500",
    hs: "text-stone-400 dark:text-stone-600",
  };
</script>

<svg
  viewBox="0 0 48 32"
  width={taille}
  height={(taille * 32) / 48}
  fill="none"
  aria-hidden="true"
  class="{TRAITS[etat] ?? TRAITS.actif} {classe}"
>
  <!-- Capot : le coin supérieur légèrement arrondi suffit à évoquer
       l'objet, un cadre parfaitement rectangulaire ferait écran de télé. -->
  <rect
    x="7.5"
    y="3.5"
    width="33"
    height="21"
    rx="2"
    stroke="currentColor"
    stroke-width="1.6"
  />
  <!-- Dalle : c'est elle qui porte l'état. -->
  <rect x="10" y="6" width="28" height="16" rx="1" class={ECRANS[etat] ?? ECRANS.actif} />

  <!-- Base et pied, plus larges que le capot comme sur un portable ouvert. -->
  <path
    d="M3 25.5h42a1.5 1.5 0 0 1 1.5 1.5 2 2 0 0 1-2 2H3.5a2 2 0 0 1-2-2A1.5 1.5 0 0 1 3 25.5Z"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linejoin="round"
  />
  <!-- Encoche du pavé tactile, le détail qui fait lire « portable ». -->
  <path d="M20 27h8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
</svg>
