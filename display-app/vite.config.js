import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  server: {
    port: 5174,
    strictPort: true,
  },
  define: {
    // Backend URL for WebSocket and REST in development
    '__BACKEND_URL__': JSON.stringify('http://localhost:18800'),
  },
});
