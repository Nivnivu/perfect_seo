import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '@/views/Dashboard.vue'
import Sites from '@/views/Sites.vue'
import Pipelines from '@/views/Pipelines.vue'
import History from '@/views/History.vue'
import Analytics from '@/views/Analytics.vue'
import Posts from '@/views/Posts.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard, meta: { title: 'Dashboard' } },
    { path: '/sites', component: Sites, meta: { title: 'Sites' } },
    { path: '/pipelines', component: Pipelines, meta: { title: 'Pipelines' } },
    { path: '/analytics', component: Analytics, meta: { title: 'Analytics' } },
    { path: '/posts', component: Posts, meta: { title: 'Posts' } },
    { path: '/history', component: History, meta: { title: 'History' } },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? 'SEO Engine'} — SEO Blog Engine`
})

export default router
