import path from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Bundled assets only (no CDN): vite inlines everything from node_modules.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'cobertura'],
      reportsDirectory: './coverage',
      // Ratchet history: 10/30/35/10 (2026-10-16 initial) -> 40/55/70/40
      // measured on vitest 1.6.1. The vitest 5 upgrade (2026-10-17) changed
      // v8 counting: branches/functions are now far stricter (every ?./??
      // and closure counts), re-baselined to the observed 39.4/43.5/38.5/38.
      // Targets do not weaken: raise next toward 80/80/75/80 by covering
      // feature pages, hooks, and lib formatters.
      thresholds: {
        lines: 39,
        functions: 43,
        branches: 38,
        statements: 37,
      },
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.d.ts', 'src/**/*.test.{ts,tsx}', 'src/main.tsx', 'src/vite-env.d.ts'],
    },
  },
});
