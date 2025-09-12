import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react-swc';
import run from 'vite-plugin-run';
import type { IncomingMessage, ServerResponse } from 'http';

interface NodeJSError extends Error {code?: string;}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  return {
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
      hmr: {
        overlay: true,
      },
      proxy: {
        '/api': {
          target: env.VITE_API_URL || 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/api/, ''),
          configure: (proxy) => {
            proxy.on('error', (err: NodeJSError, _req: IncomingMessage, res: ServerResponse | object) => {
              if ('writeHead' in res && typeof res.writeHead === 'function') {
                if (err.code === 'ECONNREFUSED') {
                  res.writeHead(503, { 'Content-Type': 'application/json' });
                  res.end(JSON.stringify({ message: 'Сервер недоступний. Перевірте підключення до мережі.' }));
                } else {
                  res.writeHead(500, { 'Content-Type': 'application/json' });
                  res.end(JSON.stringify({ message: 'Помилка проксі-сервера' }));
                }
              }
            });
          },
        },
      },
    },
  };
});