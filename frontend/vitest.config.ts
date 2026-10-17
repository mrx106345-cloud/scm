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
      // Ratcheted 2026-10-17 after UI-primitive suites landed (actual
      // lines 40.5 / functions 56.1 / branches 73.8, from lcov.info).
      // Next milestone: cover feature pages, hooks, and lib formatters,
      // then raise toward 80/80/75/80.
      thresholds: {
        lines: 40,
        functions: 55,
        branches: 70,
        statements: 40,
      },
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.d.ts', 'src/**/*.test.{ts,tsx}', 'src/main.tsx', 'src/vite-env.d.ts'],
    },
  },
});
