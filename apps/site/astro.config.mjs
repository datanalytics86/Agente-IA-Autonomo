// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

const site = process.env.PUBLIC_BASE_URL?.trim() || 'http://localhost';

/** @returns {import('vite').Plugin} */
function rewriteProyectoDev() {
  return {
    name: 'rewrite-proyecto-dev',
    configureServer(server) {
      server.middlewares.use((req, _res, next) => {
        const raw = req.url ?? '';
        const path = raw.split('?')[0] ?? '';
        if (/^\/proyecto\/(?!shell(?:\/|$))[^/]+\/?$/.test(path)) {
          const query = raw.includes('?') ? raw.slice(raw.indexOf('?')) : '';
          req.url = `/proyecto/shell${query}`;
        }
        next();
      });
    },
  };
}

export default defineConfig({
  site,
  trailingSlash: 'ignore',
  build: {
    format: 'directory',
    inlineStylesheets: 'always',
  },
  integrations: [
    sitemap({
      filter: (page) =>
        !page.includes('/proyecto') &&
        !page.includes('/checkout/') &&
        !page.includes('/pago/') &&
        !page.endsWith('/404'),
    }),
  ],
  vite: {
    plugins: [rewriteProyectoDev(), tailwindcss()],
    server: {
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  },
});
