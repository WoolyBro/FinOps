import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

/**
 * The browser only ever talks to /api on its own origin. In development Vite
 * forwards that to FastAPI, so there is no CORS to get wrong and PDF links work
 * as plain hrefs. In production, serve this build behind the same origin as
 * the API, or set VITE_API_URL at build time.
 */
const API_TARGET = process.env.FF_API_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
    },
  },
  preview: {
    port: 5173,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
    },
  },
});
