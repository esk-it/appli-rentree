/// <reference types="vite/client" />

// Les types que Vite fournit pour ce qu'il sait importer : les images
// (`import logo from "./logo.png"`), les feuilles de style en effet de
// bord, et `import.meta.env`. Sans cette ligne, la vérification de types
// ne connaissait aucun de ces imports — qui fonctionnaient pourtant très
// bien à la construction — et noyait les vraies erreurs sous des fausses.
