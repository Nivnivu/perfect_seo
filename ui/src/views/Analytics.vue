<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, Title, Tooltip, Legend, Filler,
} from 'chart.js'
import { Line, Bar } from 'vue-chartjs'
import { useSitesStore } from '@/stores/sites'
import { useI18n } from 'vue-i18n'
import { TrendingUp, MousePointerClick, Eye, Target, AlertCircle, RefreshCw, Info, Link2, Loader2, RotateCcw } from 'lucide-vue-next'
import axios from 'axios'

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, Title, Tooltip, Legend, Filler,
)

const sitesStore = useSitesStore()
const { t } = useI18n()
const selectedSite = ref('')
const weeks = ref(12)
const loading = ref(false)
const seriesLoading = ref(false)
const error = ref('')

interface Summary {
  total_clicks: number
  total_impressions: number
  avg_position: number
  avg_ctr_pct: number
  pages_tracked: number
}
interface PageRow { url: string; clicks: number; impressions: number; position: number; ctr_pct: number }
interface WeekPoint { week_start: string; clicks: number; impressions: number; avg_position: number }

const configured = ref(true)
const authenticated = ref(true)
const authorizing = ref(false)
const authMessage = ref('')
const reindexing = ref(false)
const reindexMessage = ref('')
const reindexSuccess = ref(false)
const summary = ref<Summary | null>(null)
const topPages = ref<PageRow[]>([])
const page2 = ref<PageRow[]>([])
const ctrOpps = ref<PageRow[]>([])
const series = ref<WeekPoint[]>([])
const activeTab = ref<'page2' | 'ctr'>('page2')

async function load() {
  if (!selectedSite.value) return
  loading.value = true
  error.value = ''
  summary.value = null
  topPages.value = []
  page2.value = []
  ctrOpps.value = []

  try {
    const { data } = await axios.get(`/api/gsc/${selectedSite.value}`, { params: { days: weeks.value * 7 } })
    configured.value = data.configured
    authenticated.value = data.authenticated ?? true
    if (data.data) {
      summary.value = data.data.summary
      topPages.value = data.data.top_pages
      page2.value = data.data.opportunities.page2
      ctrOpps.value = data.data.opportunities.ctr
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? e.message
  } finally {
    loading.value = false
  }

  seriesLoading.value = true
  try {
    const { data } = await axios.get(`/api/gsc/${selectedSite.value}/series`, { params: { weeks: weeks.value } })
    if (data.series) series.value = data.series
  } catch {
    // non-critical
  } finally {
    seriesLoading.value = false
  }
}

onMounted(async () => {
  await sitesStore.fetchSites()
  if (sitesStore.sites.length > 0) {
    selectedSite.value = sitesStore.sites[0].id
    await load()
  }
})

watch(selectedSite, load)

const lineChartData = computed(() => ({
  labels: series.value.map(d => {
    const dt = new Date(d.week_start)
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }),
  datasets: [
    {
      label: t('analytics.cards.totalClicks'),
      data: series.value.map(d => d.clicks),
      borderColor: 'hsl(24.6 95% 53.1%)',
      backgroundColor: 'hsla(24.6, 95%, 53.1%, 0.12)',
      fill: true,
      tension: 0.4,
      pointRadius: 2,
    },
    {
      label: t('analytics.cards.impressions'),
      data: series.value.map(d => d.impressions),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59,130,246,0.08)',
      fill: true,
      tension: 0.4,
      pointRadius: 2,
      yAxisID: 'y1',
    },
  ],
}))

const lineChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index' as const, intersect: false },
  plugins: { legend: { position: 'top' as const } },
  scales: {
    y: {
      type: 'linear' as const,
      position: 'left' as const,
      title: { display: true, text: t('analytics.cards.totalClicks') },
    },
    y1: {
      type: 'linear' as const,
      position: 'right' as const,
      grid: { drawOnChartArea: false },
      title: { display: true, text: t('analytics.cards.impressions') },
    },
  },
}))

const barChartData = computed(() => ({
  labels: topPages.value.slice(0, 10).map(p => {
    const path = new URL(p.url).pathname.replace(/^\/blog\//, '').slice(0, 35)
    return path || '/'
  }),
  datasets: [
    {
      label: t('analytics.cards.totalClicks'),
      data: topPages.value.slice(0, 10).map(p => p.clicks),
      backgroundColor: 'hsla(24.6, 95%, 53.1%, 0.75)',
      borderColor: 'hsl(24.6 95% 53.1%)',
      borderWidth: 1,
      borderRadius: 4,
    },
  ],
}))

const barChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { maxRotation: 45, font: { size: 10 } } },
    y: { beginAtZero: true },
  },
}

async function authorizeGsc() {
  if (!selectedSite.value) return
  authorizing.value = true
  authMessage.value = ''
  try {
    const { data } = await axios.post(`/api/gsc/${selectedSite.value}/authorize`)
    authMessage.value = data.message ?? 'Connected!'
    await load()
  } catch (e: any) {
    authMessage.value = e.response?.data?.detail ?? e.message
  } finally {
    authorizing.value = false
  }
}

async function requestIndexing() {
  if (!selectedSite.value) return
  reindexing.value = true
  reindexMessage.value = ''
  reindexSuccess.value = false
  try {
    const { data } = await axios.post(`/api/gsc/${selectedSite.value}/request-indexing`)
    reindexSuccess.value = true
    reindexMessage.value = data.message ?? t('analytics.indexingRequested')
    setTimeout(() => { reindexMessage.value = '' }, 6000)
  } catch (e: any) {
    reindexSuccess.value = false
    reindexMessage.value = e.response?.data?.detail ?? e.message
    setTimeout(() => { reindexMessage.value = '' }, 6000)
  } finally {
    reindexing.value = false
  }
}

function shortUrl(url: string) {
  try { return new URL(url).pathname } catch { return url }
}

function positionClass(pos: number) {
  if (pos <= 3) return 'text-emerald-600 font-semibold'
  if (pos <= 10) return 'text-blue-600'
  if (pos <= 20) return 'text-amber-600'
  return 'text-red-500'
}
</script>

<template>
  <div class="p-8 max-w-7xl">
    <!-- Header -->
    <div class="flex items-start justify-between mb-6">
      <div>
        <div class="flex items-center gap-2 mb-1">
          <TrendingUp class="w-5 h-5 text-primary" />
          <h1 class="text-2xl font-bold text-foreground">{{ $t('analytics.title') }}</h1>
        </div>
        <p class="text-muted-foreground text-sm">{{ $t('analytics.subtitle') }}</p>
      </div>
      <div class="flex items-center gap-2">
        <select
          v-model="selectedSite"
          class="h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option v-for="s in sitesStore.sites" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <select
          v-model="weeks"
          @change="load"
          class="h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option :value="4">{{ $t('analytics.weeksOption', { n: 4 }) }}</option>
          <option :value="12">{{ $t('analytics.weeksOption', { n: 12 }) }}</option>
          <option :value="24">{{ $t('analytics.weeksOption', { n: 24 }) }}</option>
        </select>
        <button
          @click="load"
          :disabled="loading"
          class="flex items-center gap-1.5 h-9 px-3 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="loading ? 'animate-spin' : ''" />
          {{ $t('analytics.refresh') }}
        </button>
        <button
          @click="requestIndexing"
          :disabled="reindexing || !selectedSite || !configured || !authenticated"
          class="flex items-center gap-1.5 h-9 px-3 rounded-lg border border-emerald-500/40 text-sm text-emerald-700 hover:bg-emerald-50 transition-colors disabled:opacity-50"
          :title="$t('analytics.requestIndexing')"
        >
          <Loader2 v-if="reindexing" class="w-3.5 h-3.5 animate-spin" />
          <RotateCcw v-else class="w-3.5 h-3.5" />
          {{ reindexing ? $t('analytics.requestingIndexing') : $t('analytics.requestIndexing') }}
        </button>
        <button
          @click="authorizeGsc"
          :disabled="authorizing || !selectedSite"
          class="flex items-center gap-1.5 h-9 px-3 rounded-lg border border-primary/40 text-sm text-primary hover:bg-primary/5 transition-colors disabled:opacity-50"
          :title="$t('analytics.connectGsc')"
        >
          <Loader2 v-if="authorizing" class="w-3.5 h-3.5 animate-spin" />
          <Link2 v-else class="w-3.5 h-3.5" />
          {{ authorizing ? $t('analytics.authorizing') : $t('analytics.connectGsc') }}
        </button>
      </div>
    </div>

    <!-- Re-index feedback -->
    <div
      v-if="reindexMessage"
      class="flex items-center gap-2 px-4 py-3 rounded-lg mb-4 text-sm"
      :class="reindexSuccess ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-destructive/10 text-destructive'"
    >
      <RotateCcw class="w-4 h-4 flex-shrink-0" />
      {{ reindexMessage }}
    </div>

    <!-- Error -->
    <div v-if="error" class="flex items-center gap-2 text-destructive bg-destructive/10 px-4 py-3 rounded-lg mb-6">
      <AlertCircle class="w-4 h-4 flex-shrink-0" />{{ error }}
    </div>

    <!-- GSC not configured -->
    <div v-else-if="!configured" class="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-5 mb-6">
      <Info class="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
      <div>
        <p class="text-sm font-semibold text-amber-900 mb-1">{{ $t('analytics.notConfigured.title') }}</p>
        <p class="text-sm text-amber-800">{{ $t('analytics.notConfigured.desc', { code: 'search_console' }) }}</p>
      </div>
    </div>

    <!-- GSC not authenticated -->
    <div v-else-if="!authenticated" class="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl p-5 mb-6">
      <Info class="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
      <div class="flex-1">
        <p class="text-sm font-semibold text-blue-900 mb-1">{{ $t('analytics.notAuthenticated.title') }}</p>
        <p class="text-sm text-blue-800 mb-3">{{ $t('analytics.notAuthenticated.desc') }}</p>
        <button
          @click="authorizeGsc"
          :disabled="authorizing"
          class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-60"
        >
          <Loader2 v-if="authorizing" class="w-4 h-4 animate-spin" />
          <Link2 v-else class="w-4 h-4" />
          {{ authorizing ? $t('analytics.openingBrowser') : $t('analytics.connectGscFull') }}
        </button>
        <p v-if="authMessage" class="mt-2 text-sm" :class="authMessage.includes('success') || authMessage.includes('Token') ? 'text-emerald-700' : 'text-red-700'">
          {{ authMessage }}
        </p>
      </div>
    </div>

    <!-- Auth result toast -->
    <div
      v-if="authMessage && authenticated"
      class="flex items-center gap-2 px-4 py-3 rounded-lg mb-4 text-sm"
      :class="authMessage.includes('success') || authMessage.includes('Token') ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-red-50 text-red-800 border border-red-200'"
    >
      <AlertCircle v-if="!authMessage.includes('success') && !authMessage.includes('Token')" class="w-4 h-4 flex-shrink-0" />
      {{ authMessage }}
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="flex items-center gap-2 text-muted-foreground py-12 justify-center">
      <div class="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      {{ $t('analytics.fetching') }}
    </div>

    <template v-else-if="summary">
      <!-- Summary cards -->
      <div class="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <div class="rounded-xl border border-border bg-card p-4">
          <div class="flex items-center gap-2 text-muted-foreground text-xs mb-1">
            <MousePointerClick class="w-3.5 h-3.5" /> {{ $t('analytics.cards.totalClicks') }}
          </div>
          <p class="text-2xl font-bold text-foreground">{{ summary.total_clicks.toLocaleString() }}</p>
          <p class="text-xs text-muted-foreground mt-0.5">{{ $t('analytics.cards.lastDays', { n: weeks * 7 }) }}</p>
        </div>
        <div class="rounded-xl border border-border bg-card p-4">
          <div class="flex items-center gap-2 text-muted-foreground text-xs mb-1">
            <Eye class="w-3.5 h-3.5" /> {{ $t('analytics.cards.impressions') }}
          </div>
          <p class="text-2xl font-bold text-foreground">{{ summary.total_impressions.toLocaleString() }}</p>
          <p class="text-xs text-muted-foreground mt-0.5">{{ $t('analytics.cards.pagesTracked', { n: summary.pages_tracked }) }}</p>
        </div>
        <div class="rounded-xl border border-border bg-card p-4">
          <div class="flex items-center gap-2 text-muted-foreground text-xs mb-1">
            <Target class="w-3.5 h-3.5" /> {{ $t('analytics.cards.avgPosition') }}
          </div>
          <p class="text-2xl font-bold text-foreground">{{ summary.avg_position }}</p>
          <p class="text-xs text-muted-foreground mt-0.5">{{ $t('analytics.cards.acrossAllPages') }}</p>
        </div>
        <div class="rounded-xl border border-border bg-card p-4">
          <div class="flex items-center gap-2 text-muted-foreground text-xs mb-1">
            <TrendingUp class="w-3.5 h-3.5" /> {{ $t('analytics.cards.avgCtr') }}
          </div>
          <p class="text-2xl font-bold text-foreground">{{ summary.avg_ctr_pct }}%</p>
          <p class="text-xs text-muted-foreground mt-0.5">{{ $t('analytics.cards.clickThroughRate') }}</p>
        </div>
      </div>

      <!-- Charts row -->
      <div class="grid grid-cols-1 xl:grid-cols-[2fr_1fr] gap-5 mb-6">
        <div class="rounded-xl border border-border bg-card p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-sm font-semibold text-foreground">{{ $t('analytics.charts.clicksImpressions') }}</h2>
            <span v-if="seriesLoading" class="text-xs text-muted-foreground flex items-center gap-1">
              <div class="w-3 h-3 border border-primary/30 border-t-primary rounded-full animate-spin" />
              {{ $t('analytics.charts.loadingChart') }}
            </span>
          </div>
          <div style="height: 220px">
            <Line v-if="series.length" :data="lineChartData" :options="lineChartOptions" />
            <div v-else class="h-full flex items-center justify-center text-muted-foreground text-sm">
              {{ $t('analytics.charts.noSeriesData') }}
            </div>
          </div>
        </div>

        <div class="rounded-xl border border-border bg-card p-5">
          <h2 class="text-sm font-semibold text-foreground mb-4">{{ $t('analytics.charts.top10Pages') }}</h2>
          <div style="height: 220px">
            <Bar v-if="topPages.length" :data="barChartData" :options="barChartOptions" />
            <div v-else class="h-full flex items-center justify-center text-muted-foreground text-sm">
              {{ $t('analytics.charts.noData') }}
            </div>
          </div>
        </div>
      </div>

      <!-- Opportunities -->
      <div class="rounded-xl border border-border bg-card mb-6">
        <div class="px-5 py-4 border-b border-border flex items-center justify-between">
          <h2 class="text-sm font-semibold text-foreground">{{ $t('analytics.opportunities.title') }}</h2>
          <div class="flex gap-1">
            <button
              @click="activeTab = 'page2'"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
              :class="activeTab === 'page2' ? 'bg-primary text-white' : 'text-muted-foreground hover:bg-muted'"
            >
              {{ $t('analytics.opportunities.page2Tab', { n: page2.length }) }}
            </button>
            <button
              @click="activeTab = 'ctr'"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
              :class="activeTab === 'ctr' ? 'bg-primary text-white' : 'text-muted-foreground hover:bg-muted'"
            >
              {{ $t('analytics.opportunities.lowCtrTab', { n: ctrOpps.length }) }}
            </button>
          </div>
        </div>

        <div v-if="activeTab === 'page2' && !page2.length" class="px-5 py-8 text-center text-muted-foreground text-sm">
          {{ $t('analytics.opportunities.noPage2') }}
        </div>
        <div v-else-if="activeTab === 'ctr' && !ctrOpps.length" class="px-5 py-8 text-center text-muted-foreground text-sm">
          {{ $t('analytics.opportunities.noCtr') }}
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-border/50">
                <th class="px-5 py-2.5 text-start text-xs font-semibold text-muted-foreground">{{ $t('analytics.table.url') }}</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-muted-foreground">{{ $t('analytics.table.clicks') }}</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-muted-foreground">{{ $t('analytics.table.impressions') }}</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-muted-foreground">{{ $t('analytics.table.position') }}</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-muted-foreground">{{ $t('analytics.table.ctr') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="p in (activeTab === 'page2' ? page2 : ctrOpps)"
                :key="p.url"
                class="border-b border-border/30 last:border-0 hover:bg-muted/20"
              >
                <td class="px-5 py-3 font-mono text-xs text-foreground max-w-xs truncate">
                  <a :href="p.url" target="_blank" class="hover:text-primary hover:underline">
                    {{ shortUrl(p.url) }}
                  </a>
                </td>
                <td class="px-4 py-3 text-right text-muted-foreground">{{ p.clicks }}</td>
                <td class="px-4 py-3 text-right text-muted-foreground">{{ p.impressions.toLocaleString() }}</td>
                <td class="px-4 py-3 text-right" :class="positionClass(p.position)">{{ p.position }}</td>
                <td class="px-4 py-3 text-right text-muted-foreground">{{ p.ctr_pct }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Top pages full table -->
      <div class="rounded-xl border border-border bg-card">
        <div class="px-5 py-4 border-b border-border">
          <h2 class="text-sm font-semibold text-foreground">{{ $t('analytics.topPages') }}</h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-border/50">
                <th class="px-5 py-2.5 text-start text-xs font-semibold text-muted-foreground">#</th>
                <th class="px-4 py-2.5 text-start text-xs font-semibold text-muted-foreground">{{ $t('analytics.table.url') }}</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-muted-foreground">{{ $t('analytics.table.clicks') }}</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-muted-foreground">{{ $t('analytics.table.impressions') }}</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-muted-foreground">{{ $t('analytics.table.position') }}</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-muted-foreground">{{ $t('analytics.table.ctr') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(p, i) in topPages"
                :key="p.url"
                class="border-b border-border/30 last:border-0 hover:bg-muted/20"
              >
                <td class="px-5 py-3 text-muted-foreground text-xs">{{ i + 1 }}</td>
                <td class="px-4 py-3 font-mono text-xs text-foreground max-w-xs truncate">
                  <a :href="p.url" target="_blank" class="hover:text-primary hover:underline">
                    {{ shortUrl(p.url) }}
                  </a>
                </td>
                <td class="px-4 py-3 text-right font-semibold text-foreground">{{ p.clicks }}</td>
                <td class="px-4 py-3 text-right text-muted-foreground">{{ p.impressions.toLocaleString() }}</td>
                <td class="px-4 py-3 text-right" :class="positionClass(p.position)">{{ p.position }}</td>
                <td class="px-4 py-3 text-right text-muted-foreground">{{ p.ctr_pct }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
