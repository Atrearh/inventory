// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://localhost:8000', // Порт вашого FastAPI-сервера
        changeOrigin: true,
      },
    },
  },
});