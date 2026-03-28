<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  LayoutDashboard,
  Globe,
  PlayCircle,
  Clock,
  TrendingUp,
  Zap,
  FileText,
  ShoppingBag,
  ClipboardCheck,
  CalendarClock,
  Bot,
} from 'lucide-vue-next'
import { SUPPORTED_LOCALES } from '@/i18n'
import { useReviewsStore } from '@/stores/reviews'

const route = useRoute()
const { t, locale } = useI18n()
const reviewsStore = useReviewsStore()

onMounted(() => reviewsStore.fetchReviews('pending'))

const navItems = computed(() => [
  { path: '/', label: t('nav.dashboard'), icon: LayoutDashboard },
  { path: '/chat', label: 'AI Assistant', icon: Bot },
  { path: '/sites', label: t('nav.sites'), icon: Globe },
  { path: '/pipelines', label: t('nav.pipelines'), icon: PlayCircle },
  { path: '/schedules', label: 'Schedules', icon: CalendarClock },
  { path: '/analytics', label: t('nav.analytics'), icon: TrendingUp },
  { path: '/posts', label: t('nav.posts'), icon: FileText },
  { path: '/products', label: t('nav.products'), icon: ShoppingBag },
  { path: '/history', label: t('nav.history'), icon: Clock },
])

const isActive = (path: string) =>
  path === '/' ? route.path === '/' : route.path.startsWith(path)

const firstPendingReviewPath = computed(() => {
  const first = reviewsStore.reviews.find(r => r.status === 'pending')
  return first ? `/reviews/${first.id}` : '/pipelines'
})

function setLocale(code: string) {
  locale.value = code
  localStorage.setItem('locale', code)
}
</script>

<template>
  <aside class="w-60 flex flex-col h-full flex-shrink-0" style="background: hsl(var(--sidebar))">
    <!-- Logo -->
    <div class="px-5 py-5 border-b border-white/10">
      <div class="flex items-center gap-2.5">
        <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: hsl(var(--sidebar-accent))">
          <Zap class="w-4 h-4 text-white" />
        </div>
        <div>
          <p class="text-sm font-bold leading-none" style="color: hsl(var(--sidebar-foreground))">{{ $t('sidebar.appName') }}</p>
          <p class="text-xs mt-0.5" style="color: hsl(var(--sidebar-foreground) / 0.45)">{{ $t('sidebar.tagline') }}</p>
        </div>
      </div>
    </div>

    <!-- Nav -->
    <nav class="flex-1 px-3 py-4 space-y-0.5">
      <RouterLink
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150"
        :class="isActive(item.path)
          ? 'font-semibold shadow-sm'
          : 'hover:bg-white/8'"
        :style="isActive(item.path)
          ? 'background: hsl(var(--sidebar-accent)); color: white;'
          : 'color: hsl(var(--sidebar-foreground) / 0.6);'"
      >
        <component :is="item.icon" class="w-4 h-4 flex-shrink-0" />
        {{ item.label }}
      </RouterLink>

      <!-- Reviews — shown when pending reviews exist -->
      <RouterLink
        v-if="reviewsStore.pendingCount > 0"
        :to="firstPendingReviewPath"
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150"
        :class="route.path.startsWith('/reviews')
          ? 'font-semibold shadow-sm'
          : 'hover:bg-white/8'"
        :style="route.path.startsWith('/reviews')
          ? 'background: hsl(var(--sidebar-accent)); color: white;'
          : 'color: hsl(var(--sidebar-foreground) / 0.6);'"
      >
        <ClipboardCheck class="w-4 h-4 flex-shrink-0" />
        <span class="flex-1">Reviews</span>
        <span class="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full bg-primary text-white text-xs font-bold leading-none">
          {{ reviewsStore.pendingCount }}
        </span>
      </RouterLink>
    </nav>

    <!-- Footer: status + language switcher -->
    <div class="px-5 py-4 border-t border-white/10 space-y-3">
      <div class="flex items-center gap-2">
        <div class="w-1.5 h-1.5 rounded-full bg-emerald-400"></div>
        <p class="text-xs" style="color: hsl(var(--sidebar-foreground) / 0.4)">{{ $t('sidebar.apiConnected') }}</p>
      </div>

      <!-- Language selector -->
      <select
        :value="locale"
        @change="setLocale(($event.target as HTMLSelectElement).value)"
        class="w-full text-xs rounded-md px-2 py-1.5 border border-white/10 bg-white/5 focus:outline-none focus:ring-1 focus:ring-white/20 cursor-pointer"
        style="color: hsl(var(--sidebar-foreground) / 0.7)"
      >
        <option
          v-for="loc in SUPPORTED_LOCALES"
          :key="loc.code"
          :value="loc.code"
          style="background: hsl(var(--sidebar)); color: hsl(var(--sidebar-foreground))"
        >
          {{ loc.name }}
        </option>
      </select>
    </div>
  </aside>
</template>
