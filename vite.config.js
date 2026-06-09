import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";

const BACKEND_PORT = 8020;

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte(), tailwindcss()],

  resolve: {
    alias: {
      $lib: fileURLToPath(new URL("./src/lib", import.meta.url)),
    },
  },

  // Spécifique au workflow Tauri : prevent Vite from obscuring rust errors
  clearScreen: false,

  server: {
    port: 5173,
    strictPort: true,
    host: "127.0.0.1",
    // Proxy /api/* vers le backend FastAPI en dev
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${BACKEND_PORT}`,
        changeOrigin: true,
      },
    },
  },

  // Empêche Vite d'ouvrir un navigateur (Tauri ouvrira sa fenêtre)
  envPrefix: ["VITE_", "TAURI_"],

  build: {
    // Tauri sur Windows = WebView2 (Edge récent) → on cible Chrome 105+.
    // Sur Mac/Linux ce serait WKWebView/WebKitGTK → safari13 conviendrait,
    // mais ce projet est Windows-only.
    target: "chrome105",
    minify: !process.env.TAURI_DEBUG ? "esbuild" : false,
    sourcemap: !!process.env.TAURI_DEBUG,
  },
});
