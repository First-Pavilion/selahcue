import { createApp } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import '@/assets/styles/tokens.css'
import '@/assets/styles/main.css'
import ComponentGallery from './ComponentGallery.vue'

/** `router-link` needs a router; every path is a blank page, the gallery never navigates. */
const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/:p(.*)*', component: { render: () => null } }],
})

createApp(ComponentGallery).use(router).mount('#app')
