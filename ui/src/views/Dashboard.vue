<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { Globe, PlayCircle, TrendingUp, Plus, Zap, AlertCircle } from 'lucide-vue-next'
import { useSitesStore } from '@/stores/sites'
import Card from '@/components/ui/Card.vue'
import Badge from '@/components/ui/Badge.vue'

const store = useSitesStore()
onMounted(() => store.fetchSites())

const platformBadge = (p: string): 'default' | 'secondary' | 'success' | 'warning' | 'destructive' | 'outline' => {
  const map: Record<string, any> = {
    mongodb: 'success',
    wordpress: 'default',
    woocommerce: 'warning',
    shopify: 'secondary',
    wix: 'outline',
  }
  return map[p] ?? 'secondary'
}

const platformLabel: Record<string, string> = {
  mongodb: 'MongoDB',
  wordpress: 'WordPress',
  woocommerce: 'WooCommerce',
  shopify: 'Shopify',
  wix: 'Wix',
}
</script>

<template>
  <div class="p-8 max-w-6xl">
    <!-- Header -->
    <div class="mb-8">
      <div class="flex items-center gap-2 mb-1">
        <Zap class="w-5 h-5 text-primary" />
        <h1 class="text-2xl font-bold text-foreground">Dashboard</h1>
      </div>
      <p class="text-muted-foreground">
        Manage your SEO pipelines, monitor site performance, and track content updates.
      </p>
    </div>

    <!-- Loading -->
    <div v-if="store.loading" class="flex items-center gap-2 text-muted-foreground py-12">
      <div class="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      Loading sites...
    </div>

    <!-- Error -->
    <div v-else-if="store.error" class="flex items-center gap-2 text-destructive bg-destructive/10 px-4 py-3 rounded-lg">
      <AlertCircle class="w-4 h-4 flex-shrink-0" />
      {{ store.error }} — Is the API server running on port 8000?
    </div>

    <!-- Empty -->
    <div v-else-if="store.sites.length === 0" class="text-center py-20">
      <div class="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
        <Globe class="w-8 h-8 text-muted-foreground/50" />
      </div>
      <h2 class="text-lg font-semibold text-foreground mb-2">No sites configured</h2>
      <p class="text-muted-foreground text-sm mb-6">
        Add a <code class="bg-muted px-1.5 py-0.5 rounded text-xs">config.mysite.yaml</code> file to the project root to get started.
      </p>
      <RouterLink
        to="/sites"
        class="inline-flex items-center gap-2 bg-primary text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
      >
        <Plus class="w-4 h-4" /> View Sites
      </RouterLink>
    </div>

    <!-- Sites Grid -->
    <div v-else>
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          {{ store.sites.length }} site{{ store.sites.length !== 1 ? 's' : '' }} configured
        </h2>
        <RouterLink to="/sites" class="text-sm text-primary hover:underline">Manage sites →</RouterLink>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        <Card
          v-for="site in store.sites"
          :key="site.id"
          class="p-5 hover:shadow-md transition-shadow group"
        >
          <!-- Top row -->
          <div class="flex items-start justify-between mb-3">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                <Globe class="w-4.5 h-4.5 text-primary" style="width:18px;height:18px" />
              </div>
              <div class="min-w-0">
                <h3 class="font-semibold text-foreground text-sm truncate">{{ site.name }}</h3>
                <p class="text-muted-foreground text-xs truncate">{{ site.domain }}</p>
              </div>
            </div>
            <Badge :variant="platformBadge(site.platform)" class="ml-2 flex-shrink-0">
              {{ platformLabel[site.platform] ?? site.platform }}
            </Badge>
          </div>

          <!-- Meta row -->
          <div class="flex items-center gap-3 text-xs text-muted-foreground mb-4">
            <span class="flex items-center gap-1">
              <span
                class="w-1.5 h-1.5 rounded-full"
                :class="site.has_gsc ? 'bg-emerald-500' : 'bg-zinc-300'"
              />
              {{ site.has_gsc ? 'GSC' : 'No GSC' }}
            </span>
            <span class="w-px h-3 bg-border" />
            <span>{{ site.language.toUpperCase() }}</span>
            <span class="w-px h-3 bg-border" />
            <span class="font-mono">{{ site.file }}</span>
          </div>

          <!-- Action button -->
          <RouterLink
            :to="`/pipelines?site=${site.id}`"
            class="flex items-center justify-center gap-1.5 w-full bg-primary/8 hover:bg-primary/15 text-primary px-3 py-2 rounded-lg text-xs font-semibold transition-colors"
          >
            <PlayCircle class="w-3.5 h-3.5" />
            Run Pipeline
          </RouterLink>
        </Card>
      </div>

      <!-- Quick tips -->
      <div class="mt-8 p-4 bg-muted/50 rounded-xl border border-border">
        <div class="flex items-center gap-2 mb-2">
          <TrendingUp class="w-4 h-4 text-primary" />
          <span class="text-sm font-semibold text-foreground">Quick start</span>
        </div>
        <ul class="text-sm text-muted-foreground space-y-1">
          <li>1. Go to <RouterLink to="/pipelines" class="text-primary hover:underline">Pipelines</RouterLink> and select a site</li>
          <li>2. Choose <strong class="text-foreground">New Post</strong> to generate your first AI blog post</li>
          <li>3. Use <strong class="text-foreground">Update Posts</strong> weekly to improve underperforming content</li>
          <li>4. Run <strong class="text-foreground">Diagnose</strong> for a deep SEO audit with Core Web Vitals</li>
        </ul>
      </div>
    </div>
  </div>
</template>
