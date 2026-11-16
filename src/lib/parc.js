/**
 * Les mots du parc, partagés par ses écrans.
 *
 * Le serveur sert les listes fermées (organes, raisons) ; ce module ne fait
 * que les dire en français, et dire une machine en une ligne.
 */

export const LIBELLES_ORGANE = {
  ecran: "Écran",
  charniere: "Charnière",
  clavier: "Clavier",
  trackpad: "Trackpad",
  batterie: "Batterie",
  port_charge: "Port de charge",
  haut_parleur: "Haut-parleur",
  webcam: "Webcam",
  carte_mere: "Carte mère",
  coque: "Coque",
  autre: "Autre",
};

export const nomOrgane = (o) => LIBELLES_ORGANE[o] ?? o;

/** L'état d'une machine : libellé et teinte de pastille (`Pastille`). */
export const ETATS = {
  en_service: { texte: "En service", pastille: "pret" },
  en_stock: { texte: "Au stock", pastille: "reference" },
  hs: { texte: "Hors service", pastille: "ecart" },
  reforme: { texte: "Réformée", pastille: "inconnu" },
  desactivee: { texte: "Désactivée", pastille: "inconnu" },
  a_localiser: { texte: "À localiser", pastille: "attente" },
  introuvable: { texte: "Introuvable", pastille: "ecart" },
};

/** Ce qu'on peut constater d'une machine pendant l'inventaire. */
export const CONSTATS = {
  conforme: "C'est juste",
  stock: "Au stock",
  porteur: "Chez quelqu'un",
  lieu: "Dans une salle",
  hs: "En panne",
  reforme: "À réformer",
  introuvable: "Introuvable",
};

export const CATEGORIES = {
  personnel: "Personnel",
  eleves: "Élèves",
  nde: "NDE",
  autre: "Autre",
  hors_google: "Hors Google",
};

export const GESTES = {
  remise: "Remise",
  reprise: "Reprise",
  echange: "Échange",
  panne: "Panne",
  reparation: "Réparation",
  prelevement: "Prélèvement",
  reforme: "Réforme",
  entree_stock: "Entrée au stock",
  pret: "Prêt",
  don: "Don",
  retour: "Retour",
  google: "Google",
};

export const TYPES_ACCESSOIRE = {
  chargeur: "Chargeur",
  souris: "Souris",
  adaptateur: "Adaptateur",
  cable: "Câble",
  housse: "Housse",
  autre: "Autre",
};

/** Où est la machine, en quelques mots : la colonne qu'on lit d'abord. */
export function ouEst(p) {
  if (p.etat === "en_stock") return "Au stock";
  if (p.etat === "a_localiser") return p.tenue_par ? `« ${p.tenue_par} » — on ne sait pas` : "On ne sait pas";
  if (p.etat === "introuvable") return "Introuvable";
  if (p.porteur) return p.porteur_nom ?? p.porteur;
  if (p.lieu) return p.lieu;
  if (p.tenue_par) return p.tenue_par;
  return "—";
}

/** Une machine en une ligne, pour une liste déroulante. */
export function enUneLigne(p) {
  const morceaux = [p.etiquette || p.serie];
  if (p.etiquette) morceaux.push(p.serie);
  if (p.modele) morceaux.push(p.modele.replace(/\s*\(.*\)$/, "").replace(/\/.*$/, ""));
  return morceaux.join(" · ");
}

/** `2026-11-16` → `16/11/2026`. */
export const jour = (iso) => (iso ? String(iso).slice(0, 10).split("-").reverse().join("/") : "—");

/** Il y a combien de temps, en clair. */
export function ilYA(iso) {
  if (!iso) return "jamais";
  const j = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (j <= 0) return "aujourd'hui";
  if (j === 1) return "hier";
  if (j < 31) return `il y a ${j} jours`;
  const mois = Math.round(j / 30.4);
  if (mois < 24) return `il y a ${mois} mois`;
  return `il y a ${Math.round(mois / 12)} ans`;
}

/**
 * La fin des mises à jour Chrome OS, jugée : passée, cette année scolaire,
 * ou plus tard. Une machine qui ne reçoit plus de mises à jour reste
 * utilisable, mais elle n'est plus sûre — et c'est elle qu'on remplace.
 */
export function finMaj(iso) {
  if (!iso) return { texte: "—", ton: "" };
  const d = new Date(iso + "T12:00");
  const maintenant = new Date();
  const finAnnee = new Date(
    maintenant.getMonth() < 8 ? maintenant.getFullYear() : maintenant.getFullYear() + 1,
    7,
    31,
  );
  const texte = d.toLocaleDateString("fr-FR", { month: "short", year: "numeric" });
  if (d < maintenant) return { texte: `finies (${texte})`, ton: "text-red-700 dark:text-red-400 font-semibold" };
  if (d <= finAnnee) return { texte, ton: "text-amber-700 dark:text-amber-400 font-semibold" };
  return { texte, ton: "text-stone-500 dark:text-stone-400" };
}

export const messageErreur = (e) => String(e).replace(/^Error:\s*/, "");
