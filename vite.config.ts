import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api-proxy/fred": {
        target: "https://api.stlouisfed.org",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-proxy\/fred/, "/fred"),
      },
      "/api-proxy/gosa": {
        target: "https://download.gosa.ga.gov",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-proxy\/gosa/, ""),
      },
      "/api-proxy/census-geocoder": {
        target: "https://geocoding.geo.census.gov",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-proxy\/census-geocoder/, ""),
      },
      "/api-proxy/census-data": {
        target: "https://api.census.gov",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-proxy\/census-data/, ""),
      },
      "/api-proxy/overpass": {
        target: "https://overpass-api.de",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-proxy\/overpass/, ""),
      },
    },
  },
});
