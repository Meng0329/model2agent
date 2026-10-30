import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Generated Agent web UI build config.
// Base "./" so the built static files work under any mount path (FastAPI StaticFiles, Docker).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "./",
  server: {
    host: "127.0.0.1",
    port: 5174,
    // dev-only: forward API calls to the generated agent's FastAPI server
    proxy: { "/api": "http://127.0.0.1:7860" },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
