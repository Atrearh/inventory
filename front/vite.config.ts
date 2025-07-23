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
    host: '0.0.0.0', // Дозволяє доступ через IP (192.168.0.143)
    port: 8080, // Порт фронтенду
    proxy: {
      '/api': {
        target: 'http://192.168.0.143:8000', // Порт бекенду
        changeOrigin: true,
        secure: false,
        rewrite: (path) => {
          console.log(`Rewriting path: ${path} -> /api${path.replace(/^\/api/, '')}`);
          return `/api${path.replace(/^\/api/, '')}`;
        },
        configure: (proxy, _options) => {
          proxy.on('error', (err, req, res) => {
            console.error(`Proxy error for ${req.method} ${req.url}:`, err.message);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log(`Proxying ${req.method} ${req.url} to ${proxyReq.getHeader('host')}${proxyReq.path}`);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log(`Received response for ${req.method} ${req.url}: ${proxyRes.statusCode}`);
          });
        },
      },
    },
  },
});