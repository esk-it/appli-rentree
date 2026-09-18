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
 * ## Le filtre d'adresses, et le piège de sa syntaxe
 *
 * Trois conditions doivent être réunies : la permission `shell:allow-open`
 * dans les capacités, le filtre `plugins.shell.open` dans
 * `tauri.conf.json`, et cet appel-ci.
 *
 * Le filtre vaut `true`, et non un motif maison. Quand on fournit un motif,
 * Tauri l'enveloppe — `format!("^{validator}$")` — et exige donc qu'il
 * décrive l'adresse **entière**. Un `^https?://` d'apparence raisonnable
 * devient `^^https?://$` et n'autorise plus que la chaîne « https:// »
 * elle-même : tous les liens sont refusés, et l'erreur ne dit pas pourquoi.
 * `true` applique le motif du plugin, qui accepte une adresse http(s),
 * mailto ou tel, et rien d'autre.
 *
 * ## Pourquoi l'erreur remonte au lieu d'un simple faux
 *
 * Un refus de portée et un plugin absent produisaient le même « ça n'a pas
 * marché », qui n'apprend rien à celui qui le lit ni à celui qui devra le
 * corriger. Le message réel est donc rendu à l'appelant, et tracé dans
 * `backend.log` — c'est le seul endroit consultable quand le défaut se
 * produit sur le poste de quelqu'un d'autre.
 */

const BASE = "/api";

/** Vrai si l'on tourne dans le shell Tauri, faux dans un navigateur. */
function dansTauri() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/** Laisse une trace dans backend.log. Best-effort. */
async function tracer(message) {
  try {
    await fetch(`${BASE}/trace-frontend`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ source: "liens", message }),
    });
  } catch {
    // Le backend ne répond pas : ce n'est pas le moment d'aggraver.
  }
}

/**
 * Ouvre une URL dans le navigateur par défaut du poste.
 *
 * Hors Tauri (développement), on retombe sur `window.open` : le
 * comportement doit rester le même des deux côtés, sans quoi on teste
 * autre chose que ce qu'on livre.
 *
 * @param {string | null | undefined} url
 * @returns {Promise<string | null>} `null` si l'ouverture a été demandée,
 *   sinon le message d'erreur à montrer tel quel.
 */
export async function ouvrirLien(url) {
  const adresse = typeof url === "string" ? url.trim() : "";
  if (!adresse) return "Aucune adresse à ouvrir.";

  if (!dansTauri()) {
    window.open(adresse, "_blank", "noopener,noreferrer");
    return null;
  }

  try {
    const { open } = await import("@tauri-apps/plugin-shell");
    await open(adresse);
    return null;
  } catch (e) {
    const cause = e instanceof Error ? e.message : String(e);
    console.warn("[liens] Ouverture impossible :", e);
    tracer(`Ouverture de ${adresse} refusée : ${cause}`);
    return `Le navigateur n'a pas pu être ouvert — ${cause}`;
  }
}
