<script>
  /**
   * Avatar avec fallback initiales colorées. La photo est chargée depuis
   * /api/photos/{personneId} — si le partage réseau `\\ESK-APP01\...` n'est
   * pas accessible, le composant tombe silencieusement sur les initiales.
   */
  let { personneId, nom = "", prenom = "", taille = 40 } = $props();

  let echec = $state(false);

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
</script>

{#if !echec && personneId}
  <img
    {src}
    alt={`${prenom} ${nom}`}
    class="rounded-full object-cover"
    style="width: {taille}px; height: {taille}px;"
    onerror={() => (echec = true)}
  />
{:else}
  <div
    class="flex items-center justify-center rounded-full font-semibold {couleur}"
    style="width: {taille}px; height: {taille}px; font-size: {Math.round(taille * 0.4)}px;"
    title={`${prenom} ${nom}`}
  >
    {initiales}
  </div>
{/if}
