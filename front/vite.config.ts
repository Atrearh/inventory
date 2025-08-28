import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import run from 'vite-plugin-run';
import type { OutgoingHttpHeaders } from 'http';

// Расширяем тип Error для поддержки свойства code
interface NodeJSError extends Error {
  code?: string;
}

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
    host: '0.0.0.0',
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://192.168.0.143:8000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => `/api${path.replace(/^\/api/, '')}`,
        configure: (proxy) => {
          proxy.on('error', (err: NodeJSError, _req, res) => {
            if (err.code === 'ECONNREFUSED') {
              res.writeHead(503, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ message: 'Сервер недоступний. Перевірте підключення до мережі.' }));
            } else {
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ message: 'Помилка проксі-сервера' }));
            }
          });
        },
      },
    },
  },
});