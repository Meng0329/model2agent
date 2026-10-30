import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      // changeOrigin:false keeps the browser's real Host (e.g. LAN-IP:5173) so the
      // backend can build a host-aware preview iframe URL (not 127.0.0.1) for remote browsers.
      "/api": { target: "http://127.0.0.1:8100", changeOrigin: false },
    },
  },
  build: {
    outDir: "dist",
  },
});
