import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

/**
 * `SELAHCUE_API_ORIGIN` points the dev proxy at a running API. The compose stack
 * publishes it on 8008 (`implementation/docker-compose.yml`).
 */
const API_ORIGIN = process.env.SELAHCUE_API_ORIGIN ?? 'http://localhost:8008'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src')
    }
  },
  server: {
    /**
     * 2000, not Vite's default 5173, because `FRONTEND_BASE_URL` defaults to
     * `http://localhost:2000` (`selahcue_api/settings.py:277`) and that is the origin
     * baked into the /verify and /reset links of every email the API sends. Serving on
     * any other port means locally-generated emails still land on nothing.
     */
    port: 2000,
    proxy: {
      /**
       * Proxy the API so the SPA calls a RELATIVE `/graphql/account` and is therefore
       * same-origin with it. Three things fall out of that, and they are the reason this
       * is a proxy rather than an absolute base URL:
       *
       *   1. No CORS. The API has `CORS_ALLOWED_ORIGINS` wired to an env var but
       *      `corsheaders` is in neither INSTALLED_APPS nor MIDDLEWARE, so it emits no
       *      CORS headers at all today — a cross-origin call would simply fail.
       *   2. The session cookie works. It is `SameSite=Strict`
       *      (`settings.py:134`), which a browser never sends on a cross-site request.
       *      The sign-in and account-portal tickets that reuse this seam
       *      (86ak11r67, 86ak11rjz) depend on that cookie arriving.
       *   3. Django's CSRF origin check passes, since Origin matches the host.
       *
       * `nginx.conf` carries the production half of the same arrangement.
       */
      '/graphql': {
        target: API_ORIGIN,
        changeOrigin: false,
      },
    },
  },
})
