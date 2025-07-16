import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import run from 'vite-plugin-run';

export default defineConfig({
  plugins: [
    react(),
    run([
      {
        name: 'generate-ts-types',
        run: ['npm run generate:ts'],
        pattern: ['app/schemas.py'],
      },
    ]),
  ],
  server: {
    host: true,
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://localhost:8000', // Порт вашего FastAPI-сервера
        changeOrigin: true,
      },
    },
  },
});