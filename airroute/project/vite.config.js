import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  server: {
    // In dev, proxy /api calls to Flask so you don't need CORS headers locally
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
  // In production builds, VITE_API_URL is injected by Vercel env vars
  define: {
    __API_URL__: JSON.stringify(process.env.VITE_API_URL || ''),
  },
});