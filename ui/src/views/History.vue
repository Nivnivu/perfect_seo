<script setup lang="ts">
import { onMounted, ref } from 'vue'
import axios from 'axios'
import { useSitesStore } from '@/stores/sites'
import { Clock, AlertCircle, FileText, ChevronDown, ChevronUp } from 'lucide-vue-next'

const sitesStore = useSitesStore()
onMounted(async () => {
  await sitesStore.fetchSites()
  if (sitesStore.sites.length > 0) selectedSite.value = sitesStore.sites[0].id
})

const selectedSite = ref('')
const history = ref<any[]>([])
const loading = ref(false)
const error = ref('')
const expanded = ref<Set<number>>(new Set())

async function loadHistory() {
  if (!selectedSite.value) return
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get(`/api/history/${selectedSite.value}`)
    history.value = Array.isArray(data) ? data.reverse() : []
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? e.message
  } finally {
    loading.value = false
  }
}

function toggleExpand(i: number) {
  expanded.value.has(i) ? expanded.value.delete(i) : expanded.value.add(i)
}

const formatDate = (s: string) => {
  if (!s) return '—'
  try { return new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }
  catch { return s }
}
</script>

<template>
  <div class="p-8 max-w-4xl">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-foreground">{{ $t('history.title') }}</h1>
      <p class="text-muted-foreground mt-1">{{ $t('history.subtitle') }}</p>
    </div>

    <!-- Site + Load -->
    <div class="flex gap-3 mb-6">
      <select
        v-model="selectedSite"
        class="h-10 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <option v-for="s in sitesStore.sites" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <button
        @click="loadHistory"
        :disabled="!selectedSite || loading"
        class="h-10 px-4 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
      >
        {{ loading ? $t('history.loading') : $t('history.loadHistory') }}
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="flex items-center gap-2 text-destructive bg-destructive/10 px-4 py-3 rounded-lg mb-4">
      <AlertCircle class="w-4 h-4" />{{ error }}
    </div>

    <!-- Empty -->
    <div v-else-if="history.length === 0 && !loading" class="text-center py-16">
      <Clock class="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
      <p class="text-muted-foreground text-sm">{{ $t('history.empty') }}</p>
    </div>

    <!-- Records -->
    <div v-else class="space-y-2">
      <div
        v-for="(entry, i) in history"
        :key="i"
        class="border border-border rounded-xl overflow-hidden"
      >
        <!-- Row header -->
        <button
          @click="toggleExpand(i)"
          class="w-full flex items-center justify-between px-4 py-3 text-start hover:bg-muted/40 transition-colors"
        >
          <div class="flex items-center gap-3 min-w-0">
            <FileText class="w-4 h-4 text-muted-foreground flex-shrink-0" />
            <div class="min-w-0">
              <p class="text-sm font-medium text-foreground truncate">{{ entry.title ?? entry.post_title ?? $t('history.untitled') }}</p>
              <p class="text-xs text-muted-foreground">{{ formatDate(entry.updated_at ?? entry.date) }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0 ms-3">
            <span v-if="entry.original_title && entry.original_title !== entry.title" class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
              {{ $t('history.titleChanged') }}
            </span>
            <span v-if="entry.original_body" class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
              {{ $t('history.bodyBackup') }}
            </span>
            <ChevronDown v-if="!expanded.has(i)" class="w-4 h-4 text-muted-foreground" />
            <ChevronUp v-else class="w-4 h-4 text-muted-foreground" />
          </div>
        </button>

        <!-- Expanded detail -->
        <div v-if="expanded.has(i)" class="px-4 pb-4 border-t border-border bg-muted/20">
          <dl class="grid grid-cols-2 gap-x-6 gap-y-2 mt-3 text-sm">
            <template v-for="(val, key) in entry" :key="key">
              <template v-if="key !== 'original_body' && String(val).length < 200">
                <dt class="text-muted-foreground font-medium">{{ key }}</dt>
                <dd class="text-foreground font-mono text-xs break-all">{{ val }}</dd>
              </template>
            </template>
          </dl>
        </div>
      </div>
    </div>
  </div>
</template>
