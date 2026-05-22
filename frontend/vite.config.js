/**
 * frontend/vite.config.js
 * ──────────────────────────────────────────────────────────────────
 * Cambios respecto al original:
 *
 *  1. base: "/dashboard/"
 *     Todos los assets del build se generan con este prefijo.
 *     Es obligatorio para que la SPA funcione desde /dashboard en FastAPI.
 *
 *  2. server.proxy
 *     En desarrollo (npm run dev), las peticiones /api/* y /feed/*
 *     se reenvían a FastAPI en :8000 → no hay errores CORS en dev.
 *
 *  3. build.outDir → "../app_b/static"
 *     El build se genera directamente en el directorio que sirve FastAPI.
 *     Ejecutar: cd frontend && npm run build
 */

import { defineConfig } from "vite";

export default defineConfig({
  // ── Base path ────────────────────────────────────────────────
  // La SPA se sirve en la raíz /  → base por defecto "."
  base: "/",

  // ── Dev server ───────────────────────────────────────────────
  server: {
    port: 5173,
    proxy: {
      // Peticiones /api/* → FastAPI en :8000
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      // Feeds CSV públicos
      "/feed": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },

  // ── Build ────────────────────────────────────────────────────
  build: {
    // Genera el build directamente en app_b/static/
    // (donde FastAPI lo sirve bajo /dashboard)
    outDir: "../app_b/static",
    emptyOutDir: true,
  },
});
