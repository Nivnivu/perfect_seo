<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { Terminal, CheckCircle2, XCircle, Loader2 } from 'lucide-vue-next'
import type { LogLine } from '@/stores/pipelines'

const props = defineProps<{
  logs: LogLine[]
  isRunning: boolean
  exitCode: number | null
}>()

const container = ref<HTMLElement | null>(null)

watch(
  () => props.logs.length,
  async () => {
    await nextTick()
    if (container.value) {
      container.value.scrollTop = container.value.scrollHeight
    }
  },
)

const lineClass = (type: LogLine['type']) => {
  switch (type) {
    case 'error':   return 'text-red-400'
    case 'warning': return 'text-amber-400'
    case 'success': return 'text-emerald-400'
    case 'dim':     return 'text-zinc-500'
    default:        return 'text-zinc-200'
  }
}
</script>

<template>
  <div class="flex flex-col rounded-xl border border-zinc-800 overflow-hidden" style="background: #0d1117;">
    <!-- Header bar -->
    <div class="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800">
      <div class="flex items-center gap-2">
        <!-- Traffic lights -->
        <span class="w-3 h-3 rounded-full bg-red-500/70"></span>
        <span class="w-3 h-3 rounded-full bg-amber-500/70"></span>
        <span class="w-3 h-3 rounded-full bg-emerald-500/70"></span>
        <span class="ml-2 text-zinc-500 text-xs font-medium flex items-center gap-1.5">
          <Terminal class="w-3.5 h-3.5" /> pipeline output
        </span>
      </div>
      <div class="flex items-center gap-1.5 text-xs">
        <template v-if="isRunning">
          <Loader2 class="w-3.5 h-3.5 text-emerald-400 animate-spin" />
          <span class="text-emerald-400">running</span>
        </template>
        <template v-else-if="exitCode === 0">
          <CheckCircle2 class="w-3.5 h-3.5 text-emerald-400" />
          <span class="text-emerald-400">success</span>
        </template>
        <template v-else-if="exitCode !== null">
          <XCircle class="w-3.5 h-3.5 text-red-400" />
          <span class="text-red-400">exit {{ exitCode }}</span>
        </template>
        <template v-else>
          <span class="text-zinc-600">idle</span>
        </template>
      </div>
    </div>

    <!-- Output -->
    <div
      ref="container"
      class="flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed"
      style="min-height: 420px; max-height: 580px;"
    >
      <div v-if="logs.length === 0" class="text-zinc-600 select-none">
        <span class="text-zinc-500">$</span> Select a site and pipeline mode, then click <span class="text-zinc-400">Run Pipeline</span>...
      </div>
      <div
        v-for="(log, i) in logs"
        :key="i"
        :class="lineClass(log.type)"
        class="whitespace-pre-wrap break-all leading-5"
      >{{ log.text }}</div>
      <div v-if="isRunning" class="flex items-center gap-1 mt-1">
        <span class="text-zinc-500">$</span>
        <span class="w-2 h-4 bg-zinc-400 animate-pulse inline-block" />
      </div>
    </div>
  </div>
</template>
