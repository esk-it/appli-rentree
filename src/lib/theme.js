/**
 * Gestion du thème clair/sombre.
 *
 * Le mode est stocké dans localStorage. Au chargement de l'app, on
 * applique la préférence enregistrée. Si rien n'est enregistré, on
 * suit la préférence système (prefers-color-scheme).
 */
import { writable } from "svelte/store";

const CLE = "appli-rentree:theme";

/** @returns {"clair" | "sombre"} */
function modePreference() {
  try {
    const stored = localStorage.getItem(CLE);
    if (stored === "clair" || stored === "sombre") return stored;
  } catch {}
  if (
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  ) {
    return "sombre";
  }
  return "clair";
}

/** @type {import("svelte/store").Writable<"clair"|"sombre">} */
export const theme = writable(modePreference());

theme.subscribe((mode) => {
  if (typeof document === "undefined") return;
  if (mode === "sombre") {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
  try {
    localStorage.setItem(CLE, mode);
  } catch {}
});

export function basculerTheme() {
  theme.update((m) => (m === "clair" ? "sombre" : "clair"));
}
