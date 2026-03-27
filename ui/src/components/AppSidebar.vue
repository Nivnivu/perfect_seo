<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'
import {
  LayoutDashboard,
  Globe,
  PlayCircle,
  Clock,
  TrendingUp,
  Zap,
  FileText,
} from 'lucide-vue-next'

const route = useRoute()

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/sites', label: 'Sites', icon: Globe },
  { path: '/pipelines', label: 'Pipelines', icon: PlayCircle },
  { path: '/analytics', label: 'Analytics', icon: TrendingUp },
  { path: '/posts', label: 'Posts', icon: FileText },
  { path: '/history', label: 'History', icon: Clock },
]

const isActive = (path: string) =>
  path === '/' ? route.path === '/' : route.path.startsWith(path)
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
          <p class="text-sm font-bold leading-none" style="color: hsl(var(--sidebar-foreground))">SEO Engine</p>
          <p class="text-xs mt-0.5" style="color: hsl(var(--sidebar-foreground) / 0.45)">Open Source</p>
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
    </nav>

    <!-- Footer -->
    <div class="px-5 py-4 border-t border-white/10">
      <div class="flex items-center gap-2">
        <div class="w-1.5 h-1.5 rounded-full bg-emerald-400"></div>
        <p class="text-xs" style="color: hsl(var(--sidebar-foreground) / 0.4)">API Connected</p>
      </div>
    </div>
  </aside>
</template>
