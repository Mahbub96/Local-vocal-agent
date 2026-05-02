import basicSsl from "@vitejs/plugin-basic-ssl";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const useHttps = process.env.FRONTEND_HTTPS === "1";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), ...(useHttps ? [basicSsl()] : [])],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Phone on LAN uses http://<this-pc-ip>:5173 — same-origin API via proxy (see api.ts).
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
