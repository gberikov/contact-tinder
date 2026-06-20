import { URL, fileURLToPath } from 'node:url';
import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    // In docker-compose set VITE_API_PROXY_TARGET=http://backend:8000 (service name);
    // defaults to localhost for running the dev server directly on the host.
    proxy: { '/api': process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
});
