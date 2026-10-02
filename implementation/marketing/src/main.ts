import { createApp } from 'vue'
import App from './App.vue'
import router from './router/index.ts'
import { reanchorForBrowser } from './lib/reanchor.ts'
import './assets/styles/tokens.css'
import './assets/styles/main.css'
import './assets/styles/anchors.css'
import './assets/styles/auth.css'

createApp(App).use(router).mount('#app')

// A cold load on a #hash: re-apply the anchor scroll once the web fonts have reflowed the page
// (lib/reanchor.ts). Fire and forget; it never throws.
void router.isReady().then(() => reanchorForBrowser(router.currentRoute.value))
