<script setup lang="ts">
import { onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { PlayCircle, Trash2, Square, Download, Clock, CheckCircle2, XCircle, AlertCircle } from 'lucide-vue-next'
import { useSitesStore } from '@/stores/sites'
import { usePipelinesStore } from '@/stores/pipelines'
import { ref } from 'vue'
import LiveLog from '@/components/LiveLog.vue'

const route = useRoute()
const sitesStore = useSitesStore()
const pipelineStore = usePipelinesStore()

const selectedSite = ref('')
const selectedMode = ref('new')
const keywordsRaw = ref('')

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

const modes = [
  {
    group: 'Content',
    items: [
      { value: 'new', label: 'New Post', desc: 'Create a new AI-generated blog post with images' },
      { value: 'update', label: 'Update Posts', desc: 'Rewrite underperforming posts based on GSC data' },
      { value: 'full', label: 'Full Pipeline', desc: 'New posts + updates + static pages in one run' },
      { value: 'static', label: 'Static Pages', desc: 'Rewrite home, registration, and other static pages' },
    ],
  },
  {
    group: 'SEO',
    items: [
      { value: 'recover', label: 'Recover', desc: 'Restore pages that lost rankings after updates' },
      { value: 'diagnose', label: 'Diagnose', desc: 'Deep SEO audit: indexing, CWV, cannibalization' },
      { value: 'dedupe', label: 'Deduplicate', desc: 'Detect and fix keyword cannibalization' },
      { value: 'impact', label: 'Impact Report', desc: 'Measure GSC before/after impact of recent updates' },
    ],
  },
  {
    group: 'Media & Products',
    items: [
      { value: 'images', label: 'Generate Images', desc: 'Add desktop + mobile images to posts missing them' },
      { value: 'products', label: 'Products', desc: 'Rewrite product pages + apply branded images' },
      { value: 'restore_titles', label: 'Restore Titles', desc: 'Restore original URL slugs from update history' },
    ],
  },
]

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
  )
  await pipelineStore.fetchHistory(selectedSite.value || undefined)
}

async function abortPipeline() {
  await pipelineStore.abort()
}

// Helpers for history table
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
      <h1 class="text-2xl font-bold text-foreground">Pipelines</h1>
      <p class="text-muted-foreground mt-1">Select a site, choose a mode, and watch the live output.</p>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-[320px_1fr] gap-6 items-start">
      <!-- Left panel: config -->
      <div class="space-y-5">
        <!-- Site -->
        <div>
          <label class="block text-sm font-medium text-foreground mb-1.5">Site</label>
          <select
            v-model="selectedSite"
            class="w-full h-10 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option v-if="sitesStore.sites.length === 0" value="">No sites configured</option>
            <option v-for="s in sitesStore.sites" :key="s.id" :value="s.id">
              {{ s.name }} — {{ s.domain }}
            </option>
          </select>
        </div>

        <!-- Mode -->
        <div>
          <label class="block text-sm font-medium text-foreground mb-2">Pipeline Mode</label>
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
            Seed Keywords
            <span class="text-muted-foreground font-normal ml-1">(optional, one per line)</span>
          </label>
          <textarea
            v-model="keywordsRaw"
            rows="4"
            placeholder="dog food&#10;cat food&#10;pet care"
            class="w-full px-3 py-2 bg-background border border-input rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring resize-none placeholder:text-muted-foreground"
          />
          <p class="text-xs text-muted-foreground mt-1">
            Defaults to seeds from config if empty.
          </p>
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
            Run Pipeline
          </button>
          <button
            v-else
            @click="abortPipeline"
            class="flex-1 flex items-center justify-center gap-2 h-10 rounded-lg text-sm font-semibold bg-destructive/10 text-destructive hover:bg-destructive/20 border border-destructive/30 transition-colors"
          >
            <Square class="w-4 h-4" />
            Abort
          </button>
          <button
            @click="pipelineStore.clear()"
            :disabled="pipelineStore.isRunning"
            class="h-10 w-10 flex items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
            title="Clear log"
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
        <!-- Log actions -->
        <div class="flex justify-end">
          <button
            @click="pipelineStore.downloadLog()"
            :disabled="!pipelineStore.logs.length"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:bg-muted border border-border transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title="Download full log as .txt"
          >
            <Download class="w-3.5 h-3.5" />
            Download log
          </button>
        </div>
      </div>
    </div>

    <!-- Run history -->
    <div class="mt-10" v-if="pipelineStore.history.length > 0">
      <div class="flex items-center gap-2 mb-4">
        <Clock class="w-4 h-4 text-muted-foreground" />
        <h2 class="text-sm font-semibold text-foreground">Recent Runs</h2>
        <span class="text-xs text-muted-foreground">({{ pipelineStore.history.length }} records)</span>
      </div>

      <div class="rounded-xl border border-border overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-muted/40 border-b border-border">
              <th class="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">#</th>
              <th class="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Site</th>
              <th class="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Mode</th>
              <th class="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Started</th>
              <th class="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Duration</th>
              <th class="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Status</th>
              <th class="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Preview</th>
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
                <!-- Running (no exit code yet) -->
                <span v-if="run.exit_code === null && !run.finished_at"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-100 text-amber-700 text-xs font-medium">
                  <span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                  running
                </span>
                <!-- Success -->
                <span v-else-if="run.exit_code === 0"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-700 text-xs font-medium">
                  <CheckCircle2 class="w-3 h-3" />
                  success
                </span>
                <!-- Aborted -->
                <span v-else-if="run.exit_code === -1"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-orange-100 text-orange-700 text-xs font-medium">
                  <AlertCircle class="w-3 h-3" />
                  aborted
                </span>
                <!-- Failed -->
                <span v-else-if="run.exit_code !== null"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-red-100 text-red-700 text-xs font-medium">
                  <XCircle class="w-3 h-3" />
                  exit {{ run.exit_code }}
                </span>
                <!-- Interrupted (finished_at set but no exit_code) -->
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
