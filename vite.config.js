import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The project previously had no vite.config.js at all, which meant it was relying on
// esbuild's default JSX handling with no Fast Refresh and no dev proxy to FastAPI (the
// frontend had to hardcode an absolute http://localhost:8000 API base and FastAPI had to
// allow-list the Vite origin in CORS). This config restores the standard React plugin and
// proxies /api and /uploads to the backend so VITE_API_BASE can simply be "/api" in dev.
export default defineConfig({
  base: "/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/uploads": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
