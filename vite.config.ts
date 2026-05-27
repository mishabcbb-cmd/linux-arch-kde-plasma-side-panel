import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  // Tauri development server port
  server: {
    port: 1420,
    strictPort: true,
  },

  // Ensure builds are optimized for Tauri
  build: {
    target: 'esnext',
    minify: 'esbuild',
    sourcemap: false,
  },
});
