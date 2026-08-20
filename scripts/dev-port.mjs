// Lance Vite en visant un backend sur un autre port que 8020.
//
// L'application installée occupe 8020 dès qu'elle tourne. Développer
// pendant qu'elle est ouverte suppose donc un second backend ailleurs,
// et un proxy qui pointe dessus. `vite.config.js` lit BACKEND_PORT ;
// ce lanceur le pose, faute d'un moyen portable de préfixer une
// variable d'environnement sous Windows.
import { spawn } from "node:child_process";

const port = process.argv[2] ?? "8021";
spawn("npx", ["vite"], {
  stdio: "inherit",
  shell: true,
  env: { ...process.env, BACKEND_PORT: port },
}).on("exit", (code) => process.exit(code ?? 0));
