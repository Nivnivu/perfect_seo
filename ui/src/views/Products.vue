<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { ShoppingBag, ExternalLink, RefreshCw, AlertCircle, Search, PlayCircle, Image, Copy, Check, MousePointerClick, Eye, MapPin, Percent } from 'lucide-vue-next'
import { useSitesStore } from '@/stores/sites'
import Badge from '@/components/ui/Badge.vue'
import axios from 'axios'

const sitesStore = useSitesStore()
const selectedSite = ref('')
const loading = ref(false)
const error = ref('')
const products = ref<any[]>([])
const searchQuery = ref('')
const gscStats = ref<Record<string, { clicks: number; impressions: number; position: number; ctr_pct: number }>>({})
const copiedId = ref<string | null>(null)
const hoveredId = ref<string | null>(null)
const tooltipStyle = ref({ top: '0px', left: '0px' })

onMounted(async () => {
  await sitesStore.fetchSites()
  if (sitesStore.sites.length > 0) {
    selectedSite.value = sitesStore.sites[0].id
    await loadAll()
  }
})

watch(selectedSite, loadAll)

async function loadAll() {
  if (!selectedSite.value) return
  loading.value = true
  error.value = ''
  products.value = []
  gscStats.value = {}
  try {
    const [productsRes, gscRes] = await Promise.allSettled([
      axios.get(`/api/products/${selectedSite.value}`, { params: { limit: 100 } }),
      axios.get(`/api/gsc/${selectedSite.value}/pages`),
    ])
    if (productsRes.status === 'fulfilled') products.value = productsRes.value.data
    else error.value = (productsRes.reason as any).response?.data?.detail ?? (productsRes.reason as any).message
    if (gscRes.status === 'fulfilled') gscStats.value = gscRes.value.data ?? {}
  } finally {
    loading.value = false
  }
}

const filtered = computed(() => {
  if (!searchQuery.value.trim()) return products.value
  const q = searchQuery.value.toLowerCase()
  return products.value.filter(p => p.title?.toLowerCase().includes(q))
})

const currentSite = computed(() => sitesStore.sites.find(s => s.id === selectedSite.value))

function formatDate(iso: string) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }
  catch { return iso }
}

function statusVariant(status: string) {
  if (status === 'published' || status === 'publish' || status === 'active') return 'success'
  if (status === 'draft') return 'secondary'
  return 'outline'
}

function getGscStats(product: any) {
  if (!product.title && !product.url) return null

  const decode = (u: string) => { try { return decodeURIComponent(u) } catch { return u } }
  const norm = (u: string) => decode(u).toLowerCase().replace(/\/$/, '')

  if (product.url) {
    const productNorm = norm(product.url)
    const exact = Object.keys(gscStats.value).find(u => norm(u) === productNorm)
    if (exact) return gscStats.value[exact]
  }

  const titleWords = new Set(
    norm(product.title ?? '').replace(/-/g, ' ').split(/\s+/).filter(w => w.length > 1)
  )
  if (titleWords.size === 0) return null

  let bestKey: string | null = null
  let bestScore = 0
  for (const url of Object.keys(gscStats.value)) {
    const slug = norm(url).split('/').pop() ?? ''
    const slugWords = new Set(slug.replace(/-/g, ' ').split(/\s+/).filter(w => w.length > 1))
    if (slugWords.size === 0) continue
    const overlap = [...titleWords].filter(w => slugWords.has(w)).length
    const score = overlap / Math.min(titleWords.size, slugWords.size)
    if (score > bestScore) { bestScore = score; bestKey = url }
  }
  return bestScore >= 0.4 && bestKey ? gscStats.value[bestKey] : null
}

function positionColor(pos: number) {
  if (pos <= 3) return 'text-emerald-600'
  if (pos <= 10) return 'text-amber-500'
  return 'text-red-500'
}

async function copyUrl(product: any) {
  if (!product.url) return
  try {
    await navigator.clipboard.writeText(product.url)
    copiedId.value = product._id
    setTimeout(() => { copiedId.value = null }, 1500)
  } catch {/* ignore */}
}

function onRowMouseEnter(e: MouseEvent, productId: string) {
  hoveredId.value = productId
  const row = (e.currentTarget as HTMLElement)
  const rect = row.getBoundingClientRect()
  tooltipStyle.value = {
    top: `${rect.bottom + window.scrollY + 4}px`,
    left: `${rect.left + window.scrollX + 16}px`,
  }
}
</script>

<template>
  <div class="p-8 max-w-6xl">
    <!-- Header -->
    <div class="flex items-start justify-between mb-6">
      <div>
        <div class="flex items-center gap-2 mb-1">
          <ShoppingBag class="w-5 h-5 text-primary" />
          <h1 class="text-2xl font-bold text-foreground">{{ $t('products.title') }}</h1>
        </div>
        <p class="text-muted-foreground text-sm">{{ $t('products.subtitle') }}</p>
      </div>
      <div class="flex items-center gap-2">
        <select
          v-model="selectedSite"
          class="h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option v-for="s in sitesStore.sites" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <button
          @click="loadAll"
          :disabled="loading"
          class="flex items-center gap-1.5 h-9 px-3 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="loading ? 'animate-spin' : ''" />
          {{ $t('products.refresh') }}
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="flex items-center gap-2 text-destructive bg-destructive/10 px-4 py-3 rounded-lg mb-5">
      <AlertCircle class="w-4 h-4 flex-shrink-0" />{{ error }}
    </div>

    <!-- Search + count -->
    <div v-if="products.length" class="flex items-center gap-3 mb-5">
      <div class="relative flex-1 max-w-sm">
        <Search class="absolute start-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
        <input
          v-model="searchQuery"
          type="text"
          :placeholder="$t('products.filterPlaceholder')"
          class="w-full h-9 ps-8 pe-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>
      <span class="text-sm text-muted-foreground">
        {{ $t('products.countOf', { filtered: filtered.length, total: products.length }) }}
      </span>
      <RouterLink
        v-if="currentSite"
        :to="`/pipelines?site=${currentSite.id}`"
        class="ms-auto flex items-center gap-1.5 h-9 px-3 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary/90 transition-colors"
      >
        <PlayCircle class="w-3.5 h-3.5" />
        {{ $t('products.runPipeline') }}
      </RouterLink>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center gap-2 text-muted-foreground py-12 justify-center">
      <div class="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      {{ $t('products.loading') }}
    </div>

    <!-- Empty -->
    <div v-else-if="!loading && products.length === 0 && !error" class="text-center py-16">
      <ShoppingBag class="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
      <p class="text-muted-foreground text-sm">{{ $t('products.empty') }}</p>
    </div>

    <!-- Products table -->
    <div v-else-if="filtered.length" class="rounded-xl border border-border overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-muted/40 border-b border-border">
            <th class="px-4 py-3 text-start text-xs font-semibold text-muted-foreground w-8">
              <Image class="w-3.5 h-3.5" />
            </th>
            <th class="px-4 py-3 text-start text-xs font-semibold text-muted-foreground">{{ $t('products.col.product') }}</th>
            <th class="px-4 py-3 text-start text-xs font-semibold text-muted-foreground">{{ $t('products.col.price') }}</th>
            <th class="px-4 py-3 text-start text-xs font-semibold text-muted-foreground">{{ $t('products.col.status') }}</th>
            <th class="px-4 py-3 text-start text-xs font-semibold text-muted-foreground">{{ $t('products.col.added') }}</th>
            <th class="px-4 py-3 text-start text-xs font-semibold text-muted-foreground">{{ $t('products.col.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="product in filtered"
            :key="product._id"
            class="border-b border-border/40 last:border-0 hover:bg-muted/20 transition-colors cursor-default"
            @mouseenter="onRowMouseEnter($event, product._id)"
            @mouseleave="hoveredId = null"
          >
            <td class="px-4 py-3">
              <div v-if="product.image1Url" class="w-8 h-8 rounded overflow-hidden flex-shrink-0">
                <img :src="product.image1Url" :alt="product.title" class="w-full h-full object-cover" loading="lazy" />
              </div>
              <div v-else class="w-8 h-8 rounded bg-muted flex items-center justify-center">
                <ShoppingBag class="w-3.5 h-3.5 text-muted-foreground/50" />
              </div>
            </td>

            <td class="px-4 py-3 max-w-sm">
              <p class="font-medium text-foreground text-sm leading-snug line-clamp-1">{{ product.title }}</p>
              <p v-if="product.subtitle" class="text-xs text-muted-foreground mt-0.5 line-clamp-1"
                 v-html="product.subtitle.replace(/<[^>]*>/g, '')" />
            </td>

            <td class="px-4 py-3">
              <span v-if="product.price" class="text-sm font-semibold text-emerald-600">${{ product.price }}</span>
              <span v-else class="text-xs text-muted-foreground">—</span>
            </td>

            <td class="px-4 py-3">
              <div class="flex items-center gap-1.5">
                <Badge :variant="statusVariant(product.status)">{{ product.status || 'unknown' }}</Badge>
                <span
                  v-if="getGscStats(product)"
                  class="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0"
                  :title="$t('products.gscAvailable')"
                />
              </div>
            </td>

            <td class="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
              {{ formatDate(product.created_at) }}
            </td>

            <td class="px-4 py-3">
              <div class="flex items-center gap-1">
                <button
                  v-if="product.url"
                  @click.stop="copyUrl(product)"
                  class="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  :title="copiedId === product._id ? $t('products.copied') : $t('products.copyUrl')"
                >
                  <Check v-if="copiedId === product._id" class="w-3.5 h-3.5 text-emerald-500" />
                  <Copy v-else class="w-3.5 h-3.5" />
                </button>
                <a
                  v-if="product.url"
                  :href="product.url"
                  target="_blank"
                  class="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  :title="$t('products.openProduct')"
                >
                  <ExternalLink class="w-3.5 h-3.5" />
                </a>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- No results after filter -->
    <div v-else-if="searchQuery && !filtered.length" class="text-center py-10 text-muted-foreground text-sm">
      {{ $t('products.noResults', { query: searchQuery }) }}
    </div>

    <!-- GSC Hover Tooltip -->
    <Teleport to="body">
      <Transition name="tooltip">
        <div
          v-if="hoveredId && getGscStats(filtered.find(p => p._id === hoveredId) || {})"
          :style="tooltipStyle"
          class="fixed z-50 pointer-events-none"
        >
          <div class="bg-background/80 backdrop-blur-md border border-border/60 rounded-lg shadow-lg px-3 py-2.5 text-xs min-w-[180px]">
            <p class="font-semibold text-foreground mb-2 text-[11px] uppercase tracking-wide text-muted-foreground">{{ $t('posts.gscTooltip.title') }}</p>
            <div class="grid grid-cols-2 gap-x-4 gap-y-1.5">
              <div class="flex items-center gap-1.5 text-muted-foreground">
                <MousePointerClick class="w-3 h-3" />{{ $t('posts.gscTooltip.clicks') }}
              </div>
              <span class="font-semibold text-foreground text-right">
                {{ getGscStats(filtered.find(p => p._id === hoveredId) || {})?.clicks.toLocaleString() }}
              </span>
              <div class="flex items-center gap-1.5 text-muted-foreground">
                <Eye class="w-3 h-3" />{{ $t('posts.gscTooltip.impressions') }}
              </div>
              <span class="font-semibold text-foreground text-right">
                {{ getGscStats(filtered.find(p => p._id === hoveredId) || {})?.impressions.toLocaleString() }}
              </span>
              <div class="flex items-center gap-1.5 text-muted-foreground">
                <MapPin class="w-3 h-3" />{{ $t('posts.gscTooltip.position') }}
              </div>
              <span
                class="font-semibold text-right"
                :class="positionColor(getGscStats(filtered.find(p => p._id === hoveredId) || {})?.position ?? 99)"
              >
                {{ getGscStats(filtered.find(p => p._id === hoveredId) || {})?.position }}
              </span>
              <div class="flex items-center gap-1.5 text-muted-foreground">
                <Percent class="w-3 h-3" />{{ $t('posts.gscTooltip.ctr') }}
              </div>
              <span class="font-semibold text-foreground text-right">
                {{ getGscStats(filtered.find(p => p._id === hoveredId) || {})?.ctr_pct }}%
              </span>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.tooltip-enter-active, .tooltip-leave-active { transition: opacity 0.1s, transform 0.1s; }
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
