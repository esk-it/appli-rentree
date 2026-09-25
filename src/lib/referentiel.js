/**
 * Ce que les trois vues du Référentiel partagent.
 *
 * La liste, le rangement par classe et le relevé de ce qui manque parlent
 * des mêmes personnes : l'état d'une fiche, le niveau d'une classe, l'ordre
 * dans lequel on les lit doivent être les mêmes partout, sinon un élève
 * « cohérent » d'un côté serait « pas vérifié » de l'autre.
 */

/** `2_10` après `2_9`, comme on les lit. */
export function cleNaturelle(texte) {
  return String(texte ?? "")
    .split(/(\d+)/)
    .map((x) => (/^\d+$/.test(x) ? Number(x) : x.toLowerCase()));
}

// Un comparateur fait une fois : `localeCompare(…, "fr")` en refabrique un
// à chaque appel, et un tri de deux mille lignes l'appelle vingt mille fois.
const ORDRE = new Intl.Collator("fr");

/** Comparaison de deux clés naturelles, morceau par morceau. */
export function comparerNaturel(a, b) {
  const x = cleNaturelle(a);
  const y = cleNaturelle(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    if (x[i] === undefined) return -1;
    if (y[i] === undefined) return 1;
    if (x[i] === y[i]) continue;
    if (typeof x[i] === "number" && typeof y[i] === "number") {
      return /** @type {number} */ (x[i]) - /** @type {number} */ (y[i]);
    }
    return ORDRE.compare(String(x[i]), String(y[i]));
  }
  return 0;
}

export const NOM_SYSTEME = {
  charlemagne: "Charlemagne",
  google: "Google",
  koxo: "KoXo",
};

/**
 * Ce qu'on peut dire d'une personne sans rien relancer.
 *
 * La cohérence se constate en croisant Charlemagne, Google et KoXo, ce que
 * la Concordance fait sur demande, jamais à l'ouverture d'une liste. Le
 * croisement range son constat — un verdict par personne et par système —
 * et c'est lui qu'on relit ici, sans rien affirmer qui n'ait été regardé.
 *
 * Passent d'abord les deux signalements que le référentiel porte tout
 * seul : sans site, aucune cible n'est calculable ; sans adresse, aucun
 * compte ne se crée.
 *
 * @returns {{etat: "pret"|"ecart"|"inconnu", texte: string}}
 */
export function etatDe(p, verdicts) {
  if (p.sans_compte) return { etat: "inconnu", texte: "Hors référentiel" };
  if (!p.site) return { etat: "ecart", texte: "Sans site" };
  if (!p.email) return { etat: "ecart", texte: "Sans adresse" };
  const v = verdicts?.[p.id];
  if (!v) return { etat: "inconnu", texte: "Pas vérifié" };
  if (v.etat === "coherent") return { etat: "pret", texte: "Cohérent" };
  const casses = v.systemes.filter((s) => s.etat === "ecart");
  if (casses.length === 1) {
    return { etat: "ecart", texte: `≠ ${NOM_SYSTEME[casses[0].systeme] ?? casses[0].systeme}` };
  }
  return { etat: "ecart", texte: casses.length ? `${casses.length} écarts` : "Écart" };
}

const ORDRE_NIVEAUX = [
  "6e", "5e", "4e", "3e", "3e prépa-métiers", "Secondes", "Premières",
  "Terminales", "BTS", "Autres", "Sans classe",
];

/**
 * Le niveau d'une classe, pour ranger l'arbre.
 *
 * Déduit du code : il n'est pas dans le référentiel tant que l'export ne
 * porte pas « Code niveau ». Les codes de la maison suffisent — `2_1`,
 * `1_STMG1`, `T_ST2S`, `BTS_2`, `3_PM` au lycée, `61`, `4J` au collège.
 */
export function niveauDe(classe) {
  if (!classe) return "Sans classe";
  const c = String(classe).toUpperCase();
  if (c.startsWith("BTS")) return "BTS";
  if (c.startsWith("T_") || c.startsWith("TERM")) return "Terminales";
  if (c.startsWith("1_")) return "Premières";
  if (c.startsWith("2_")) return "Secondes";
  if (c.startsWith("3_PM")) return "3e prépa-métiers";
  const d = c.charAt(0);
  if ("6543".includes(d)) return `${d}e`;
  return "Autres";
}

export function ordreNiveau(niveau) {
  const i = ORDRE_NIVEAUX.indexOf(niveau);
  return i < 0 ? 99 : i;
}

/** Un champ CSV, guillemeté seulement quand il le faut. */
function champCsv(v) {
  const s = String(v ?? "");
  return /[";\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/**
 * La liste d'une classe, telle qu'un enseignant l'ouvre dans Excel.
 *
 * Point-virgule et marque d'ordre : c'est ce qu'Excel attend en français
 * pour ouvrir un CSV d'un double-clic sans mélanger les accents.
 */
export function csvDeClasse(personnes) {
  const lignes = [["Classe", "Nom", "Prénom", "Identifiant", "Adresse"]];
  for (const p of personnes) {
    lignes.push([
      p.classe ?? "", p.nom ?? "", p.prenom ?? "",
      p.login_constate ?? p.login ?? "", p.email ?? "",
    ]);
  }
  return "\uFEFF" + lignes.map((l) => l.map(champCsv).join(";")).join("\r\n") + "\r\n";
}

/** Un texte en base64, octets UTF-8 compris — pour l'enregistrer en fichier. */
export function texteEnBase64(texte) {
  const octets = new TextEncoder().encode(texte);
  let binaire = "";
  for (const o of octets) binaire += String.fromCharCode(o);
  return btoa(binaire);
}

/** « 12/03/2012 », depuis « 2012-03-12 ». */
export function jour(iso) {
  return iso ? String(iso).slice(0, 10).split("-").reverse().join("/") : "—";
}
