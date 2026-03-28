<script setup lang="ts">
import { onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { PlayCircle, Trash2, Square, Download, Clock, CheckCircle2, XCircle, AlertCircle, ClipboardCheck } from 'lucide-vue-next'
import { useSitesStore } from '@/stores/sites'
import { usePipelinesStore } from '@/stores/pipelines'
import { ref } from 'vue'
import LiveLog from '@/components/LiveLog.vue'

const route = useRoute()
const router = useRouter()
const sitesStore = useSitesStore()
const pipelineStore = usePipelinesStore()
const { t } = useI18n()

const selectedSite = ref('')
const selectedMode = ref('new')
const keywordsRaw = ref('')
const manualPublish = ref(false)

const PREVIEW_SUPPORTED = new Set(['new', 'update', 'recover'])

onMounted(async () => {
  await sitesStore.fetchSites()
  if (route.query.site) {
    selectedSite.value = String(route.query.site)
  } else if (sitesStore.sites.length > 0) {
    selectedSite.value = sitesStore.sites[0].id
  }
  await pipelineStore.fetchHistory(selectedSite.value || undefined)
})

watch(selectedSite, async (id) => {
  await pipelineStore.fetchHistory(id || undefined)
})

const modes = computed(() => [
  {
    group: t('pipelines.groups.content'),
    items: [
      { value: 'new', label: t('pipelines.modes.new.label'), desc: t('pipelines.modes.new.desc') },
      { value: 'update', label: t('pipelines.modes.update.label'), desc: t('pipelines.modes.update.desc') },
      { value: 'full', label: t('pipelines.modes.full.label'), desc: t('pipelines.modes.full.desc') },
      { value: 'static', label: t('pipelines.modes.static.label'), desc: t('pipelines.modes.static.desc') },
    ],
  },
  {
    group: t('pipelines.groups.seo'),
    items: [
      { value: 'recover', label: t('pipelines.modes.recover.label'), desc: t('pipelines.modes.recover.desc') },
      { value: 'diagnose', label: t('pipelines.modes.diagnose.label'), desc: t('pipelines.modes.diagnose.desc') },
      { value: 'dedupe', label: t('pipelines.modes.dedupe.label'), desc: t('pipelines.modes.dedupe.desc') },
      { value: 'impact', label: t('pipelines.modes.impact.label'), desc: t('pipelines.modes.impact.desc') },
    ],
  },
  {
    group: t('pipelines.groups.media'),
    items: [
      { value: 'images', label: t('pipelines.modes.images.label'), desc: t('pipelines.modes.images.desc') },
      { value: 'products', label: t('pipelines.modes.products.label'), desc: t('pipelines.modes.products.desc') },
      { value: 'restore_titles', label: t('pipelines.modes.restore_titles.label'), desc: t('pipelines.modes.restore_titles.desc') },
    ],
  },
])

const keywordsNeeded = computed(() => ['new', 'update', 'full'].includes(selectedMode.value))

const keywords = computed(() =>
  keywordsRaw.value
    .split('\n')
    .map((k) => k.trim())
    .filter(Boolean),
)

async function runPipeline() {
  await pipelineStore.run(
    selectedSite.value,
    selectedMode.value,
    keywordsNeeded.value ? keywords.value : undefined,
    PREVIEW_SUPPORTED.has(selectedMode.value) && manualPublish.value,
  )
  await pipelineStore.fetchHistory(selectedSite.value || undefined)
}

async function abortPipeline() {
  await pipelineStore.abort()
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function formatDuration(start: string, end: string | null): string {
  if (!end) return '—'
  const ms = new Date(end).getTime() - new Date(start).getTime()
  if (ms < 60000) return `${Math.round(ms / 1000)}s`
  const m = Math.floor(ms / 60000)
  const s = Math.round((ms % 60000) / 1000)
  return `${m}m ${s}s`
}
</script>

<template>
  <div class="p-8">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-foreground">{{ $t('pipelines.title') }}</h1>
      <p class="text-muted-foreground mt-1">{{ $t('pipelines.subtitle') }}</p>
    </div>

    <!-- Review ready banner -->
    <div
      v-if="pipelineStore.pendingReviewId"
      class="mb-6 flex items-center gap-3 p-4 rounded-xl border border-emerald-300 bg-emerald-50 dark:bg-emerald-950/30 dark:border-emerald-800"
    >
      <CheckCircle2 class="w-5 h-5 text-emerald-600 flex-shrink-0" />
      <div class="flex-1">
        <p class="text-sm font-semibold text-emerald-800 dark:text-emerald-300">Content ready for review</p>
        <p class="text-xs text-emerald-700 dark:text-emerald-400">The pipeline generated content that needs your approval before publishing.</p>
      </div>
      <button
        @click="router.push(`/reviews/${pipelineStore.pendingReviewId}`)"
        class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 transition-colors"
      >
        <ClipboardCheck class="w-4 h-4" />
        Review &amp; Publish
      </button>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-[320px_1fr] gap-6 items-start">
      <!-- Left panel: config -->
      <div class="space-y-5">
        <!-- Site -->
        <div>
          <label class="block text-sm font-medium text-foreground mb-1.5">{{ $t('pipelines.site') }}</label>
          <select
            v-model="selectedSite"
            class="w-full h-10 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option v-if="sitesStore.sites.length === 0" value="">{{ $t('pipelines.noSitesOption') }}</option>
            <option v-for="s in sitesStore.sites" :key="s.id" :value="s.id">
              {{ s.name }} — {{ s.domain }}
            </option>
          </select>
        </div>

        <!-- Mode -->
        <div>
          <label class="block text-sm font-medium text-foreground mb-2">{{ $t('pipelines.pipelineMode') }}</label>
          <div class="space-y-3">
            <div v-for="group in modes" :key="group.group">
              <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">{{ group.group }}</p>
              <div class="space-y-1">
                <label
                  v-for="mode in group.items"
                  :key="mode.value"
                  class="flex items-start gap-3 p-2.5 rounded-lg border cursor-pointer transition-all"
                  :class="selectedMode === mode.value
                    ? 'border-primary/50 bg-primary/5'
                    : 'border-transparent hover:border-border hover:bg-muted/50'"
                >
                  <input
                    type="radio"
                    :value="mode.value"
                    v-model="selectedMode"
                    class="mt-0.5 flex-shrink-0 accent-primary"
                  />
                  <div>
                    <p class="text-sm font-medium text-foreground leading-none mb-0.5">{{ mode.label }}</p>
                    <p class="text-xs text-muted-foreground">{{ mode.desc }}</p>
                  </div>
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- Keywords -->
        <div v-if="keywordsNeeded">
          <label class="block text-sm font-medium text-foreground mb-1.5">
            {{ $t('pipelines.seedKeywords') }}
            <span class="text-muted-foreground font-normal ms-1">{{ $t('pipelines.keywordsOptional') }}</span>
          </label>
          <textarea
            v-model="keywordsRaw"
            rows="4"
            placeholder="dog food&#10;cat food&#10;pet care"
            class="w-full px-3 py-2 bg-background border border-input rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring resize-none placeholder:text-muted-foreground"
          />
          <p class="text-xs text-muted-foreground mt-1">{{ $t('pipelines.keywordsDefault') }}</p>
        </div>

        <!-- Manual publish toggle (only for preview-supported modes) -->
        <div v-if="PREVIEW_SUPPORTED.has(selectedMode)" class="flex items-center gap-3 p-3 rounded-lg border border-border bg-muted/30">
          <button
            type="button"
            role="switch"
            :aria-checked="manualPublish"
            @click="manualPublish = !manualPublish"
            class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors flex-shrink-0"
            :class="manualPublish ? 'bg-primary' : 'bg-muted-foreground/30'"
          >
            <span
              class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
              :class="manualPublish ? 'translate-x-[18px]' : 'translate-x-[3px]'"
            />
          </button>
          <div class="min-w-0">
            <p class="text-sm font-medium text-foreground leading-none mb-0.5">Manual review before publish</p>
            <p class="text-xs text-muted-foreground">Review and edit generated content before it goes live</p>
          </div>
        </div>

        <!-- Run / Abort / Clear buttons -->
        <div class="flex gap-2">
          <button
            v-if="!pipelineStore.isRunning"
            @click="runPipeline"
            :disabled="!selectedSite"
            class="flex-1 flex items-center justify-center gap-2 h-10 rounded-lg text-sm font-semibold transition-colors"
            :class="!selectedSite
              ? 'bg-muted text-muted-foreground cursor-not-allowed'
              : 'bg-primary text-white hover:bg-primary/90 shadow-sm'"
          >
            <PlayCircle class="w-4 h-4" />
            {{ $t('pipelines.run') }}
          </button>
          <button
            v-else
            @click="abortPipeline"
            class="flex-1 flex items-center justify-center gap-2 h-10 rounded-lg text-sm font-semibold bg-destructive/10 text-destructive hover:bg-destructive/20 border border-destructive/30 transition-colors"
          >
            <Square class="w-4 h-4" />
            {{ $t('pipelines.abort') }}
          </button>
          <button
            @click="pipelineStore.clear()"
            :disabled="pipelineStore.isRunning"
            class="h-10 w-10 flex items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
            :title="$t('pipelines.clearLog')"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </div>
      </div>

      <!-- Right panel: live log -->
      <div class="space-y-2">
        <LiveLog
          :logs="pipelineStore.logs"
          :is-running="pipelineStore.isRunning"
          :exit-code="pipelineStore.exitCode"
        />
        <div class="flex justify-end">
          <button
            @click="pipelineStore.downloadLog()"
            :disabled="!pipelineStore.logs.length"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:bg-muted border border-border transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            :title="$t('pipelines.downloadLog')"
          >
            <Download class="w-3.5 h-3.5" />
            {{ $t('pipelines.downloadLog') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Run history -->
    <div class="mt-10" v-if="pipelineStore.history.length > 0">
      <div class="flex items-center gap-2 mb-4">
        <Clock class="w-4 h-4 text-muted-foreground" />
        <h2 class="text-sm font-semibold text-foreground">{{ $t('pipelines.recentRuns') }}</h2>
        <span class="text-xs text-muted-foreground">({{ $t('pipelines.records', { n: pipelineStore.history.length }) }})</span>
      </div>

      <div class="rounded-xl border border-border overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-muted/40 border-b border-border">
              <th class="px-4 py-2.5 text-start text-xs font-semibold text-muted-foreground">{{ $t('pipelines.col.hash') }}</th>
              <th class="px-4 py-2.5 text-start text-xs font-semibold text-muted-foreground">{{ $t('pipelines.col.site') }}</th>
              <th class="px-4 py-2.5 text-start text-xs font-semibold text-muted-foreground">{{ $t('pipelines.col.mode') }}</th>
              <th class="px-4 py-2.5 text-start text-xs font-semibold text-muted-foreground">{{ $t('pipelines.col.started') }}</th>
              <th class="px-4 py-2.5 text-start text-xs font-semibold text-muted-foreground">{{ $t('pipelines.col.duration') }}</th>
              <th class="px-4 py-2.5 text-start text-xs font-semibold text-muted-foreground">{{ $t('pipelines.col.status') }}</th>
              <th class="px-4 py-2.5 text-start text-xs font-semibold text-muted-foreground">{{ $t('pipelines.col.preview') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="run in pipelineStore.history"
              :key="run.id"
              class="border-b border-border/50 last:border-0 hover:bg-muted/20 transition-colors"
            >
              <td class="px-4 py-3 text-muted-foreground font-mono text-xs">{{ run.id }}</td>
              <td class="px-4 py-3 font-medium text-foreground">{{ run.site_name || run.site_id }}</td>
              <td class="px-4 py-3">
                <span class="inline-flex items-center px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-medium">
                  {{ run.mode }}
                </span>
              </td>
              <td class="px-4 py-3 text-muted-foreground text-xs">{{ formatTime(run.started_at) }}</td>
              <td class="px-4 py-3 text-muted-foreground text-xs font-mono">
                {{ formatDuration(run.started_at, run.finished_at) }}
              </td>
              <td class="px-4 py-3">
                <span v-if="run.exit_code === null && !run.finished_at"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-100 text-amber-700 text-xs font-medium">
                  <span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                  {{ $t('pipelines.status.running') }}
                </span>
                <span v-else-if="run.exit_code === 0"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-700 text-xs font-medium">
                  <CheckCircle2 class="w-3 h-3" />
                  {{ $t('pipelines.status.success') }}
                </span>
                <span v-else-if="run.exit_code === -1"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-orange-100 text-orange-700 text-xs font-medium">
                  <AlertCircle class="w-3 h-3" />
                  {{ $t('pipelines.status.aborted') }}
                </span>
                <span v-else-if="run.exit_code !== null"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-red-100 text-red-700 text-xs font-medium">
                  <XCircle class="w-3 h-3" />
                  {{ $t('pipelines.status.exit', { code: run.exit_code }) }}
                </span>
                <span v-else class="text-muted-foreground text-xs">—</span>
              </td>
              <td class="px-4 py-3 text-muted-foreground text-xs font-mono max-w-xs truncate">
                {{ run.log_preview?.split('\n').pop() || '—' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
