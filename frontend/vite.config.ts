/// <reference types="vitest/config" />
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

/**
 * The dev server proxies `/api` and `/ws` to the FastAPI backend so the app is
 * same-origin in development. That means no CORS configuration is needed on the
 * Python side, and the WebSocket URL can be derived from `window.location`
 * exactly the same way in dev and in a production build served by any host.
 *
 * Override the target with FLYWIRE_API_URL if the backend runs elsewhere.
 */
const target = process.env.FLYWIRE_API_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target, changeOrigin: true },
      '/ws': { target, ws: true, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    css: true,
    alias: {
      // The real graph library needs a canvas 2D context, which jsdom does not
      // provide. The stub keeps the same props contract and exposes the data it
      // was handed, so tests can assert what the app asked it to draw.
      'react-force-graph-2d': new URL('./tests/stubs/force-graph.tsx', import.meta.url)
        .pathname,
    },
  },
});
