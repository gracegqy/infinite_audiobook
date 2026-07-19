import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev-only proxy to a locally-running server; production is served by FastAPI
// itself from dist/ (DESIGN §1), so no origin/proxy config matters there.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8123" },
  },
});
