import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '@/views/Dashboard.vue'
import Sites from '@/views/Sites.vue'
import Pipelines from '@/views/Pipelines.vue'
import History from '@/views/History.vue'
import Analytics from '@/views/Analytics.vue'
import Posts from '@/views/Posts.vue'
import Products from '@/views/Products.vue'
import PostReview from '@/views/PostReview.vue'
import Schedules from '@/views/Schedules.vue'
import Chat from '@/views/Chat.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard, meta: { title: 'Dashboard' } },
    { path: '/chat', component: Chat, meta: { title: 'AI Assistant' } },
    { path: '/sites', component: Sites, meta: { title: 'Sites' } },
    { path: '/pipelines', component: Pipelines, meta: { title: 'Pipelines' } },
    { path: '/analytics', component: Analytics, meta: { title: 'Analytics' } },
    { path: '/posts', component: Posts, meta: { title: 'Posts' } },
    { path: '/products', component: Products, meta: { title: 'Products' } },
    { path: '/history', component: History, meta: { title: 'History' } },
    { path: '/schedules', component: Schedules, meta: { title: 'Schedules' } },
    { path: '/reviews/:id', component: PostReview, meta: { title: 'Review Post' } },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? 'SEO Engine'} — SEO Blog Engine`
})

export default router
