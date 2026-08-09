import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  // Base absoluta: deep links (/establecimientos/…) cargan /assets/* correctamente.
  base: "/",
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "^/api": {
        target: "http://localhost:5011/",
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
