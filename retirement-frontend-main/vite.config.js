import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// Vite's process.env doesn't auto-read .env files in vite.config.js —
// use loadEnv() so .env.local (and all other .env variants) are picked up.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  // In dev, always proxy /api → localhost:8000 so the frontend can talk to
  // the FastAPI backend (api/main.py). If the backend is not running,
  // withMockFallback in apiClient.js catches the connection-refused error
  // and falls back to mock automatically — so enabling this is always safe.
  const proxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000';

  return {
    plugins: [react()],
    server: {
      port: 5173,
      open: false,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
  };
});
