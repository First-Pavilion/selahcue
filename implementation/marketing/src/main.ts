import { createApp } from 'vue'
import App from './App.vue'
import router from './router/index.ts'
import './assets/styles/tokens.css'
import './assets/styles/main.css'
import './assets/styles/auth.css'

createApp(App).use(router).mount('#app')
