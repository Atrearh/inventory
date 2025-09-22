import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react-swc';
import run from 'vite-plugin-run';
import type { IncomingMessage, ServerResponse } from 'http';
import { visualizer } from "rollup-plugin-visualizer";

interface NodeJSError extends Error {code?: string;}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  console.log('Loaded VITE_API_URL:', env.VITE_API_URL);

  return {
    plugins: [
      react(),
      visualizer({ open: true }),
      run([
        {
          name: 'generate-ts-types',
          run: ['npm', 'run', 'generate:ts'],
          pattern: ['../app/schemas.py'],
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
          target: env.VITE_API_URL || 'http://localhost:8000/api',
          changeOrigin: true,
          secure: false,
          timeout: 5000, // Додаємо таймаут 5 секунд
          configure: (proxy) => {
            proxy.on('error', (err: NodeJSError, _req: IncomingMessage, res: ServerResponse | object) => {
              console.error('Proxy error:', err);
              if ('writeHead' in res && typeof res.writeHead === 'function') {
                if (err.code === 'ECONNREFUSED') {
                  res.writeHead(503, { 'Content-Type': 'application/json' });
                  res.end(JSON.stringify({ message: 'Сервер недоступний. Перевірте підключення до мережі.' }));
                } else {
                  res.writeHead(500, { 'Content-Type': 'application/json' });
                  res.end(JSON.stringify({ message: 'Помилка проксі-сервера', details: err.message }));
                }
              }
            });
            proxy.on('proxyReq', (proxyReq) => {
              console.log('Proxying request to:', proxyReq.getHeader('host'), proxyReq.path);
            });
          },
        },
      },
    build: { 
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('antd')) {
                return 'vendor_antd';
              }
              if (id.includes('chart.js') || id.includes('react-chartjs-2')) {
                  return 'vendor_chart';
              }
              if (id.includes('@tanstack')) {
                  return 'vendor_tanstack';
              }
              return 'vendor'; 
            }
          },
        },
      },
    },
  }
  };
});
