/**
 * Ouvrir une adresse dans le navigateur.
 *
 * ## Pourquoi ce détour
 *
 * Dans une fenêtre Tauri, `<a target="_blank">` ne fait **rien** : il n'y a
 * ni onglet ni barre d'adresse, et WebView2 bloque l'ouverture. Le lien
 * paraît cliquable, le curseur change, et il ne se passe rien — le défaut
 * le plus déroutant qui soit, parce qu'il ne laisse aucune trace.
 *
 * C'était le cas des liens de l'écran Sodexo : le portail et le classeur
 * étaient morts dans l'application installée, vivants en développement (un
 * navigateur, lui, sait ouvrir un onglet). Un défaut qui ne se voit donc
 * jamais pendant qu'on code.
 *
 * Trois conditions doivent être réunies, et il en manquait trois :
 * `shell:allow-open` dans les capacités, `plugins.shell.open` dans
 * `tauri.conf.json`, et cet appel-ci.
 */

/** Vrai si l'on tourne dans le shell Tauri, faux dans un navigateur. */
function dansTauri() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/**
 * Ouvre une URL dans le navigateur par défaut du poste.
 *
 * Hors Tauri (développement), on retombe sur `window.open` : le
 * comportement doit rester le même des deux côtés, sans quoi on teste
 * autre chose que ce qu'on livre.
 *
 * @param {string | null | undefined} url
 * @returns {Promise<boolean>} vrai si l'ouverture a été demandée
 */
export async function ouvrirLien(url) {
  const adresse = typeof url === "string" ? url.trim() : "";
  if (!adresse) return false;

  if (!dansTauri()) {
    window.open(adresse, "_blank", "noopener,noreferrer");
    return true;
  }

  try {
    const { open } = await import("@tauri-apps/plugin-shell");
    await open(adresse);
    return true;
  } catch (e) {
    console.warn("[liens] Ouverture impossible :", e);
    return false;
  }
}
