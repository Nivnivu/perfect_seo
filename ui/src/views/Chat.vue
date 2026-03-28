<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import {
  Send, Bot, User, Loader2, Wrench, ChevronDown, ChevronUp,
  Trash2, Settings2, Sparkles,
} from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import { useSitesStore } from '@/stores/sites'

const chatStore = useChatStore()
const sitesStore = useSitesStore()
const input = ref('')
const messagesEl = ref<HTMLElement | null>(null)
const showConfig = ref(false)
const expandedTools = ref<Set<number>>(new Set())

onMounted(async () => {
  await sitesStore.fetchSites()
  // Default to first site's config
  if (!chatStore.config.siteId && sitesStore.sites.length > 0) {
    chatStore.config.siteId = sitesStore.sites[0].id
  }
})

watch(() => chatStore.messages.length, async () => {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
})

async function sendMessage() {
  const text = input.value.trim()
  if (!text || chatStore.isStreaming) return
  input.value = ''
  await chatStore.send(text)
}

function toggleToolExpand(idx: number) {
  if (expandedTools.value.has(idx)) {
    expandedTools.value.delete(idx)
  } else {
    expandedTools.value.add(idx)
  }
}

const TOOL_LABELS: Record<string, string> = {
  list_sites: 'Listing sites',
  run_pipeline: 'Running pipeline',
  get_pipeline_history: 'Fetching run history',
  list_posts: 'Fetching posts',
  list_pending_reviews: 'Checking review queue',
  publish_review: 'Publishing review',
  reject_review: 'Rejecting review',
  list_schedules: 'Fetching schedules',
  create_schedule: 'Creating schedule',
  delete_schedule: 'Deleting schedule',
  toggle_schedule: 'Toggling schedule',
  get_gsc_summary: 'Fetching GSC data',
}

const PROVIDERS = [
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'openai', label: 'OpenAI (GPT)' },
  { value: 'gemini', label: 'Google Gemini' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'mistral', label: 'Mistral' },
]

const MODELS: Record<string, string[]> = {
  anthropic: ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
  openai: ['gpt-4.1', 'gpt-4.1-mini', 'gpt-4o', 'o3', 'o4-mini'],
  gemini: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash'],
  deepseek: ['deepseek-chat', 'deepseek-reasoner'],
  mistral: ['mistral-large-latest', 'mistral-small-latest'],
}

const useCustomKey = ref(false)

const configSource = computed(() => {
  if (useCustomKey.value && chatStore.config.apiKey && chatStore.config.provider) {
    return `${chatStore.config.provider} · custom key`
  }
  if (chatStore.config.siteId) {
    const site = sitesStore.sites.find(s => s.id === chatStore.config.siteId)
    return site ? `${site.name} · site config` : 'site config'
  }
  return 'not configured'
})

const SUGGESTIONS = [
  'What sites do I have configured?',
  'Show me pending reviews',
  'Run a new post for my first site with manual review',
  'What are my active schedules?',
  'Show GSC performance for my main site',
  'Create a weekly schedule to update posts every Monday at 9am',
]

function formatJson(val: unknown): string {
  try {
    return JSON.stringify(val, null, 2)
  } catch {
    return String(val)
  }
}
</script>

<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-3 px-6 py-3 border-b border-border bg-background/80 backdrop-blur-sm flex-shrink-0">
      <Sparkles class="w-5 h-5 text-primary" />
      <div class="flex-1">
        <h1 class="text-base font-semibold text-foreground leading-none">SEO Assistant</h1>
        <p class="text-xs text-muted-foreground mt-0.5">{{ configSource }}</p>
      </div>
      <button
        @click="chatStore.clear()"
        :disabled="!chatStore.messages.length"
        class="h-8 w-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-30"
        title="Clear conversation"
      >
        <Trash2 class="w-4 h-4" />
      </button>
      <button
        @click="showConfig = !showConfig"
        class="flex items-center gap-1.5 h-8 px-2.5 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        :class="showConfig ? 'bg-muted text-foreground' : ''"
      >
        <Settings2 class="w-4 h-4" />
        Config
      </button>
    </div>

    <!-- Config panel (collapsible) -->
    <div v-if="showConfig" class="border-b border-border bg-muted/20 px-6 py-4 space-y-4 flex-shrink-0">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- Source: site or custom key -->
        <div class="space-y-1.5 md:col-span-3">
          <div class="flex items-center gap-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="radio" v-model="useCustomKey" :value="false" class="accent-primary" />
              <span class="text-sm text-foreground">Use a site's configured LLM</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="radio" v-model="useCustomKey" :value="true" class="accent-primary" />
              <span class="text-sm text-foreground">Custom API key</span>
            </label>
          </div>
        </div>

        <!-- Site selector -->
        <div v-if="!useCustomKey" class="space-y-1.5">
          <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Site</label>
          <select
            v-model="chatStore.config.siteId"
            class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option v-for="s in sitesStore.sites" :key="s.id" :value="s.id">
              {{ s.name }} ({{ s.platform }})
            </option>
          </select>
          <p class="text-xs text-muted-foreground">The LLM key and model from this site's config will be used.</p>
        </div>

        <!-- Custom provider -->
        <div v-if="useCustomKey" class="space-y-1.5">
          <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Provider</label>
          <select
            v-model="chatStore.config.provider"
            class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option v-for="p in PROVIDERS" :key="p.value" :value="p.value">{{ p.label }}</option>
          </select>
        </div>

        <!-- Custom model -->
        <div v-if="useCustomKey" class="space-y-1.5">
          <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Model</label>
          <select
            v-model="chatStore.config.model"
            class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option v-for="m in (MODELS[chatStore.config.provider ?? ''] ?? [])" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>

        <!-- Custom API key -->
        <div v-if="useCustomKey" class="space-y-1.5">
          <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">API Key</label>
          <input
            v-model="chatStore.config.apiKey"
            type="password"
            placeholder="sk-..."
            class="w-full h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>
    </div>

    <!-- Messages -->
    <div ref="messagesEl" class="flex-1 overflow-y-auto px-4 py-6 space-y-6 min-h-0">
      <!-- Empty state -->
      <div v-if="chatStore.messages.length === 0" class="flex flex-col items-center justify-center h-full gap-6 text-center">
        <div class="w-14 h-14 rounded-2xl flex items-center justify-center bg-primary/10">
          <Sparkles class="w-7 h-7 text-primary" />
        </div>
        <div>
          <p class="text-lg font-semibold text-foreground">What can I help you with?</p>
          <p class="text-sm text-muted-foreground mt-1">I can run pipelines, manage schedules, review content, and analyse your SEO data.</p>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-xl w-full">
          <button
            v-for="s in SUGGESTIONS"
            :key="s"
            @click="input = s"
            class="text-left text-sm px-4 py-2.5 rounded-xl border border-border hover:border-primary/40 hover:bg-primary/5 text-muted-foreground hover:text-foreground transition-all"
          >
            {{ s }}
          </button>
        </div>
      </div>

      <!-- Message list -->
      <div
        v-for="(msg, idx) in chatStore.messages"
        :key="idx"
        class="flex gap-3"
        :class="msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'"
      >
        <!-- Avatar -->
        <div
          class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
          :class="msg.role === 'user' ? 'bg-primary text-white' : 'bg-muted text-muted-foreground'"
        >
          <User v-if="msg.role === 'user'" class="w-4 h-4" />
          <Bot v-else class="w-4 h-4" />
        </div>

        <!-- Bubble -->
        <div class="flex flex-col gap-2 max-w-[75%]" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
          <!-- Tool calls (assistant only) -->
          <div
            v-if="msg.role === 'assistant' && msg.toolCalls?.length"
            v-for="(tc, tcIdx) in msg.toolCalls"
            :key="tcIdx"
            class="w-full rounded-xl border border-border bg-muted/30 overflow-hidden"
          >
            <button
              @click="toggleToolExpand(idx * 1000 + tcIdx)"
              class="flex items-center gap-2 w-full px-3 py-2 text-xs hover:bg-muted/50 transition-colors"
            >
              <Wrench class="w-3.5 h-3.5 text-muted-foreground" />
              <span class="text-muted-foreground flex-1 text-left">
                {{ TOOL_LABELS[tc.name] ?? tc.name }}
                <span v-if="!tc.done" class="ml-1 text-amber-500">···</span>
                <span v-else class="ml-1 text-emerald-500">✓</span>
              </span>
              <component :is="expandedTools.has(idx * 1000 + tcIdx) ? ChevronUp : ChevronDown" class="w-3 h-3 text-muted-foreground" />
            </button>
            <div v-if="expandedTools.has(idx * 1000 + tcIdx)" class="border-t border-border px-3 py-2 space-y-2">
              <div>
                <p class="text-xs font-semibold text-muted-foreground mb-1">Args</p>
                <pre class="text-xs font-mono text-foreground/70 whitespace-pre-wrap">{{ formatJson(tc.args) }}</pre>
              </div>
              <div v-if="tc.done && tc.result">
                <p class="text-xs font-semibold text-muted-foreground mb-1">Result</p>
                <pre class="text-xs font-mono text-foreground/70 whitespace-pre-wrap max-h-40 overflow-y-auto">{{ formatJson(tc.result) }}</pre>
              </div>
            </div>
          </div>

          <!-- Text content -->
          <div
            v-if="msg.content || msg.streaming"
            class="px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap"
            :class="msg.role === 'user'
              ? 'bg-primary text-white rounded-tr-sm'
              : 'bg-muted/60 text-foreground rounded-tl-sm border border-border/50'"
          >
            <span v-if="msg.content">{{ msg.content }}</span>
            <span v-if="msg.streaming && !msg.content" class="flex items-center gap-1 text-muted-foreground">
              <Loader2 class="w-3.5 h-3.5 animate-spin" />
              Thinking...
            </span>
            <span
              v-if="msg.streaming && msg.content"
              class="inline-block w-0.5 h-4 bg-current ml-0.5 animate-pulse align-middle"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="border-t border-border px-4 py-3 bg-background flex-shrink-0">
      <div class="flex gap-2 items-end max-w-4xl mx-auto">
        <textarea
          v-model="input"
          rows="1"
          placeholder="Ask anything — run a pipeline, check GSC stats, manage schedules..."
          class="flex-1 px-4 py-2.5 rounded-xl border border-input bg-background text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
          style="min-height: 2.5rem; max-height: 8rem; overflow-y: auto;"
          @keydown.enter.exact.prevent="sendMessage"
          @keydown.enter.shift.exact.prevent="input += '\n'"
          :disabled="chatStore.isStreaming"
        />
        <button
          @click="sendMessage"
          :disabled="!input.trim() || chatStore.isStreaming"
          class="flex items-center justify-center w-10 h-10 rounded-xl bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-40 flex-shrink-0"
        >
          <Loader2 v-if="chatStore.isStreaming" class="w-4 h-4 animate-spin" />
          <Send v-else class="w-4 h-4" />
        </button>
      </div>
      <p class="text-xs text-muted-foreground text-center mt-1.5">Enter to send · Shift+Enter for new line</p>
    </div>
  </div>
</template>
