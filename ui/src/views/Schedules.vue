<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Plus, Trash2, Pencil, Clock, Play, CheckCircle2,
  XCircle, AlertCircle, ChevronDown, ChevronUp, Calendar,
} from 'lucide-vue-next'
import { useSitesStore } from '@/stores/sites'
import { useSchedulesStore, type Schedule, type ScheduleRun } from '@/stores/schedules'

const sitesStore = useSitesStore()
const store = useSchedulesStore()

onMounted(async () => {
  await sitesStore.fetchSites()
  await store.fetchSchedules()
})

// ---------------------------------------------------------------------------
// Cron helpers
// ---------------------------------------------------------------------------

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

function describeCron(expr: string): string {
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return expr
  const [min, hour, day, , dow] = parts
  const time = `${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
  if (dow !== '*') {
    const dayName = DAY_NAMES[parseInt(dow)] ?? `Day ${dow}`
    return `Every ${dayName} at ${time}`
  }
  if (day !== '*') return `Monthly on day ${day} at ${time}`
  return `Daily at ${time}`
}

function buildCron(freq: string, hour: number, minute: number, dow: number, dom: number): string {
  const h = String(hour)
  const m = String(minute)
  if (freq === 'weekly') return `${m} ${h} * * ${dow}`
  if (freq === 'monthly') return `${m} ${h} ${dom} * *`
  return `${m} ${h} * * *`
}

// ---------------------------------------------------------------------------
// Form state
// ---------------------------------------------------------------------------

type Freq = 'daily' | 'weekly' | 'monthly' | 'custom'

interface FormState {
  site_id: string
  mode: string
  label: string
  freq: Freq
  hour: number
  minute: number
  dow: number      // day of week 0-6 (Sunday=0)
  dom: number      // day of month 1-28
  customCron: string
  keywordsRaw: string
  manual_publish: boolean
  enabled: boolean
}

const emptyForm = (): FormState => ({
  site_id: sitesStore.sites[0]?.id ?? '',
  mode: 'new',
  label: '',
  freq: 'weekly',
  hour: 9,
  minute: 0,
  dow: 1,
  dom: 1,
  customCron: '0 9 * * 1',
  keywordsRaw: '',
  manual_publish: false,
  enabled: true,
})

const showModal = ref(false)
const editingId = ref<number | null>(null)
const form = ref<FormState>(emptyForm())
const saving = ref(false)
const saveError = ref('')

const cronPreview = computed(() => {
  if (form.value.freq === 'custom') return form.value.customCron
  return buildCron(form.value.freq, form.value.hour, form.value.minute, form.value.dow, form.value.dom)
})

function openCreate() {
  form.value = { ...emptyForm(), site_id: sitesStore.sites[0]?.id ?? '' }
  editingId.value = null
  saveError.value = ''
  showModal.value = true
}

function openEdit(s: Schedule) {
  const parts = s.cron_expr.trim().split(/\s+/)
  let freq: Freq = 'custom'
  let hour = 9, minute = 0, dow = 1, dom = 1

  if (parts.length === 5) {
    const [m, h, day, , d] = parts
    hour = parseInt(h) || 9
    minute = parseInt(m) || 0
    if (d !== '*' && day === '*') { freq = 'weekly'; dow = parseInt(d) || 1 }
    else if (day !== '*') { freq = 'monthly'; dom = parseInt(day) || 1 }
    else { freq = 'daily' }
  }

  form.value = {
    site_id: s.site_id,
    mode: s.mode,
    label: s.label,
    freq,
    hour,
    minute,
    dow,
    dom,
    customCron: s.cron_expr,
    keywordsRaw: (s.keywords ?? []).join('\n'),
    manual_publish: !!s.manual_publish,
    enabled: !!s.enabled,
  }
  editingId.value = s.id
  saveError.value = ''
  showModal.value = true
}

async function save() {
  saving.value = true
  saveError.value = ''
  try {
    const keywords = form.value.keywordsRaw.split('\n').map(k => k.trim()).filter(Boolean)
    const payload = {
      site_id: form.value.site_id,
      mode: form.value.mode,
      cron_expr: cronPreview.value,
      label: form.value.label || undefined,
      keywords,
      manual_publish: form.value.manual_publish,
      enabled: form.value.enabled,
    }
    if (editingId.value !== null) {
      await store.updateSchedule(editingId.value, payload)
    } else {
      await store.createSchedule(payload)
    }
    showModal.value = false
  } catch (e: any) {
    saveError.value = e.response?.data?.detail ?? e.message ?? 'Save failed'
  } finally {
    saving.value = false
  }
}

async function remove(id: number) {
  if (!confirm('Delete this schedule? This cannot be undone.')) return
  await store.deleteSchedule(id)
}

// ---------------------------------------------------------------------------
// Run history panel
// ---------------------------------------------------------------------------

const historyScheduleId = ref<number | null>(null)
const historyRuns = ref<ScheduleRun[]>([])
const historyLoading = ref(false)
const logContent = ref('')
const logRunId = ref<number | null>(null)

async function toggleHistory(s: Schedule) {
  if (historyScheduleId.value === s.id) {
    historyScheduleId.value = null
    return
  }
  historyScheduleId.value = s.id
  historyLoading.value = true
  historyRuns.value = await store.fetchRuns(s.id)
  historyLoading.value = false
  logContent.value = ''
  logRunId.value = null
}

async function viewLog(scheduleId: number, runId: number) {
  if (logRunId.value === runId) { logRunId.value = null; return }
  logRunId.value = runId
  logContent.value = await store.fetchRunLog(scheduleId, runId)
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function formatDuration(start: string, end: string | null): string {
  if (!end) return '—'
  const ms = new Date(end).getTime() - new Date(start).getTime()
  if (ms < 60000) return `${Math.round(ms / 1000)}s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

const MODES = [
  'new', 'update', 'full', 'static', 'recover',
  'diagnose', 'dedupe', 'impact', 'images', 'products', 'restore_titles',
]
</script>

<template>
  <div class="p-8">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-foreground">Automated Schedules</h1>
        <p class="text-muted-foreground mt-1">Run pipelines automatically on a recurring schedule</p>
      </div>
      <button
        @click="openCreate"
        class="flex items-center gap-2 h-9 px-4 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary/90 transition-colors"
      >
        <Plus class="w-4 h-4" />
        New Schedule
      </button>
    </div>

    <!-- Empty state -->
    <div v-if="store.schedules.length === 0" class="flex flex-col items-center justify-center py-24 text-center gap-3">
      <Calendar class="w-10 h-10 text-muted-foreground/40" />
      <p class="text-muted-foreground font-medium">No schedules yet</p>
      <p class="text-sm text-muted-foreground/60">Create a schedule to automate your SEO pipelines</p>
    </div>

    <!-- Schedule cards -->
    <div v-else class="space-y-3">
      <div
        v-for="s in store.schedules"
        :key="s.id"
        class="rounded-xl border border-border bg-background overflow-hidden"
      >
        <!-- Main row -->
        <div class="flex items-center gap-4 px-5 py-4">
          <!-- Enable toggle -->
          <button
            type="button"
            role="switch"
            :aria-checked="!!s.enabled"
            @click="store.toggleSchedule(s.id)"
            class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors flex-shrink-0"
            :class="s.enabled ? 'bg-primary' : 'bg-muted-foreground/30'"
          >
            <span
              class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
              :class="s.enabled ? 'translate-x-[18px]' : 'translate-x-[3px]'"
            />
          </button>

          <!-- Info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-semibold text-foreground text-sm">{{ s.label }}</span>
              <span class="inline-flex items-center px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-medium">
                {{ s.mode }}
              </span>
              <span class="text-xs text-muted-foreground">{{ sitesStore.sites.find(x => x.id === s.site_id)?.name ?? s.site_id }}</span>
            </div>
            <div class="flex items-center gap-4 mt-1">
              <span class="text-xs text-muted-foreground flex items-center gap-1">
                <Clock class="w-3 h-3" />
                {{ describeCron(s.cron_expr) }}
              </span>
              <span v-if="s.next_run_at" class="text-xs text-muted-foreground">
                Next: {{ formatTime(s.next_run_at) }}
              </span>
              <span v-if="s.last_run_at" class="text-xs text-muted-foreground">
                Last: {{ formatTime(s.last_run_at) }}
              </span>
              <span v-if="s.manual_publish" class="text-xs text-amber-600">Manual review</span>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-1 flex-shrink-0">
            <button
              @click="toggleHistory(s)"
              class="flex items-center gap-1 h-8 px-2.5 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <component :is="historyScheduleId === s.id ? ChevronUp : ChevronDown" class="w-3.5 h-3.5" />
              History
            </button>
            <button
              @click="openEdit(s)"
              class="h-8 w-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <Pencil class="w-3.5 h-3.5" />
            </button>
            <button
              @click="remove(s.id)"
              class="h-8 w-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- History panel -->
        <div v-if="historyScheduleId === s.id" class="border-t border-border bg-muted/20 px-5 py-3">
          <div v-if="historyLoading" class="text-xs text-muted-foreground py-2">Loading...</div>
          <div v-else-if="historyRuns.length === 0" class="text-xs text-muted-foreground py-2">No runs yet</div>
          <div v-else class="space-y-1">
            <div
              v-for="run in historyRuns"
              :key="run.id"
              class="flex items-center gap-3 text-xs py-1"
            >
              <span
                class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-xs font-medium"
                :class="run.exit_code === 0
                  ? 'bg-emerald-100 text-emerald-700'
                  : run.exit_code === null
                    ? 'bg-amber-100 text-amber-700'
                    : 'bg-red-100 text-red-700'"
              >
                <CheckCircle2 v-if="run.exit_code === 0" class="w-3 h-3" />
                <AlertCircle v-else-if="run.exit_code === null" class="w-3 h-3" />
                <XCircle v-else class="w-3 h-3" />
                {{ run.exit_code === 0 ? 'Success' : run.exit_code === null ? 'Running' : `Exit ${run.exit_code}` }}
              </span>
              <span class="text-muted-foreground">{{ formatTime(run.started_at) }}</span>
              <span class="text-muted-foreground font-mono">{{ formatDuration(run.started_at, run.finished_at) }}</span>
              <button
                @click="viewLog(s.id, run.id)"
                class="text-primary hover:underline"
              >
                {{ logRunId === run.id ? 'Hide log' : 'View log' }}
              </button>
            </div>
            <!-- Log viewer -->
            <pre
              v-if="logRunId !== null && logContent"
              class="mt-2 p-3 rounded-lg bg-background border border-border text-xs font-mono overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap text-foreground/80"
            >{{ logContent }}</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- ------------------------------------------------------------------ -->
    <!-- Create / Edit modal                                                  -->
    <!-- ------------------------------------------------------------------ -->
    <Teleport to="body">
      <div
        v-if="showModal"
        class="fixed inset-0 z-50 flex items-center justify-center"
        @click.self="showModal = false"
      >
        <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" />
        <div class="relative z-10 w-full max-w-lg mx-4 bg-background rounded-2xl border border-border shadow-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
          <!-- Modal header -->
          <div class="px-6 py-4 border-b border-border flex items-center justify-between">
            <h2 class="font-semibold text-foreground">{{ editingId ? 'Edit Schedule' : 'New Schedule' }}</h2>
            <button @click="showModal = false" class="text-muted-foreground hover:text-foreground transition-colors text-xl leading-none">&times;</button>
          </div>

          <!-- Modal body -->
          <div class="px-6 py-5 space-y-4">
            <!-- Site + Mode -->
            <div class="grid grid-cols-2 gap-3">
              <div class="space-y-1.5">
                <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Site</label>
                <select
                  v-model="form.site_id"
                  class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option v-for="site in sitesStore.sites" :key="site.id" :value="site.id">
                    {{ site.name }}
                  </option>
                </select>
              </div>
              <div class="space-y-1.5">
                <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Pipeline Mode</label>
                <select
                  v-model="form.mode"
                  class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option v-for="m in MODES" :key="m" :value="m">{{ m }}</option>
                </select>
              </div>
            </div>

            <!-- Label -->
            <div class="space-y-1.5">
              <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Label <span class="font-normal normal-case">(optional)</span></label>
              <input
                v-model="form.label"
                type="text"
                :placeholder="`${form.mode} — ${form.site_id}`"
                class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <!-- Frequency -->
            <div class="space-y-1.5">
              <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Frequency</label>
              <div class="grid grid-cols-4 gap-1.5">
                <button
                  v-for="f in (['daily', 'weekly', 'monthly', 'custom'] as const)"
                  :key="f"
                  type="button"
                  @click="form.freq = f"
                  class="py-2 rounded-lg border text-sm font-medium transition-colors capitalize"
                  :class="form.freq === f
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:border-primary/40 hover:text-foreground'"
                >
                  {{ f }}
                </button>
              </div>
            </div>

            <!-- Time (daily/weekly/monthly) -->
            <div v-if="form.freq !== 'custom'" class="grid gap-3"
              :class="form.freq === 'weekly' ? 'grid-cols-3' : form.freq === 'monthly' ? 'grid-cols-3' : 'grid-cols-2'"
            >
              <div class="space-y-1.5">
                <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Hour (0–23)</label>
                <input
                  v-model.number="form.hour"
                  type="number" min="0" max="23"
                  class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div class="space-y-1.5">
                <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Minute (0–59)</label>
                <input
                  v-model.number="form.minute"
                  type="number" min="0" max="59"
                  class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div v-if="form.freq === 'weekly'" class="space-y-1.5">
                <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Day of Week</label>
                <select
                  v-model.number="form.dow"
                  class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option v-for="(name, i) in DAY_NAMES" :key="i" :value="i">{{ name }}</option>
                </select>
              </div>
              <div v-if="form.freq === 'monthly'" class="space-y-1.5">
                <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Day of Month (1–28)</label>
                <input
                  v-model.number="form.dom"
                  type="number" min="1" max="28"
                  class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>

            <!-- Custom cron -->
            <div v-if="form.freq === 'custom'" class="space-y-1.5">
              <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Cron Expression</label>
              <input
                v-model="form.customCron"
                type="text"
                placeholder="0 9 * * 1"
                class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p class="text-xs text-muted-foreground">Format: minute hour day month weekday</p>
            </div>

            <!-- Cron preview -->
            <div class="p-3 rounded-lg bg-muted/40 border border-border text-sm flex items-center gap-2">
              <Clock class="w-4 h-4 text-muted-foreground flex-shrink-0" />
              <span class="text-muted-foreground">{{ describeCron(cronPreview) }}</span>
              <span class="text-muted-foreground/50 font-mono text-xs ml-auto">{{ cronPreview }}</span>
            </div>

            <!-- Keywords -->
            <div class="space-y-1.5">
              <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Keywords <span class="font-normal normal-case">(optional, one per line)</span>
              </label>
              <textarea
                v-model="form.keywordsRaw"
                rows="3"
                placeholder="dog food&#10;cat food"
                class="w-full px-3 py-2 bg-background border border-input rounded-lg text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
              />
            </div>

            <!-- Options row -->
            <div class="flex items-center gap-6">
              <!-- Manual review toggle -->
              <div class="flex items-center gap-2.5">
                <button
                  type="button"
                  role="switch"
                  :aria-checked="form.manual_publish"
                  @click="form.manual_publish = !form.manual_publish"
                  class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors flex-shrink-0"
                  :class="form.manual_publish ? 'bg-primary' : 'bg-muted-foreground/30'"
                >
                  <span
                    class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
                    :class="form.manual_publish ? 'translate-x-[18px]' : 'translate-x-[3px]'"
                  />
                </button>
                <span class="text-sm text-foreground">Manual review</span>
              </div>

              <!-- Enabled toggle -->
              <div class="flex items-center gap-2.5">
                <button
                  type="button"
                  role="switch"
                  :aria-checked="form.enabled"
                  @click="form.enabled = !form.enabled"
                  class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors flex-shrink-0"
                  :class="form.enabled ? 'bg-emerald-500' : 'bg-muted-foreground/30'"
                >
                  <span
                    class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
                    :class="form.enabled ? 'translate-x-[18px]' : 'translate-x-[3px]'"
                  />
                </button>
                <span class="text-sm text-foreground">Enabled</span>
              </div>
            </div>

            <!-- Error -->
            <div v-if="saveError" class="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm">
              {{ saveError }}
            </div>
          </div>

          <!-- Modal footer -->
          <div class="px-6 py-4 border-t border-border flex justify-end gap-2">
            <button
              @click="showModal = false"
              class="h-9 px-4 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              Cancel
            </button>
            <button
              @click="save"
              :disabled="saving || !form.site_id"
              class="h-9 px-5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60"
            >
              {{ saving ? 'Saving...' : editingId ? 'Update Schedule' : 'Create Schedule' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
