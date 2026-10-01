import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// BACKEND_ORIGIN is read server-side only (no VITE_ prefix), so the browser
// only ever talks to this dev server's /api and /ws proxy.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendOrigin = env.BACKEND_ORIGIN || "http://localhost:8000";
  const backendWsOrigin = backendOrigin.replace(/^http/, "ws");

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": { target: backendOrigin, changeOrigin: true },
        "/ws": { target: backendWsOrigin, ws: true, changeOrigin: true },
      },
    },
  };
});
