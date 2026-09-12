import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      // Backend API base path (see frontend/CONTRACT.md). Point this at the
      // real backend once it exists; VITE_API_BASE_URL overrides it entirely
      // when the mock API is disabled.
      "/api": {
        target: process.env.BACKEND_URL ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
