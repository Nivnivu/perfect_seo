<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, Send, CheckCircle2, XCircle, Loader2,
  FileText, Sparkles, Eye, EyeOff, Image,
} from 'lucide-vue-next'
import TipTapEditor from '@/components/TipTapEditor.vue'
import { useReviewsStore, type Review } from '@/stores/reviews'
import { useSitesStore } from '@/stores/sites'

const route = useRoute()
const router = useRouter()
const reviewsStore = useReviewsStore()
const sitesStore = useSitesStore()

const reviewId = computed(() => parseInt(route.params.id as string))
const review = ref<Review | null>(null)
const loading = ref(true)
const publishing = ref(false)
const published = ref(false)
const publishError = ref('')
const showPreview = ref(false)

// Editable fields
const editTitle = ref('')
const editSubtitle = ref('')
const editBodyHtml = ref('')

// Chat / refine panel
interface ChatMsg { role: 'user' | 'assistant'; text: string }
const chatHistory = ref<ChatMsg[]>([])
const instruction = ref('')
const isRefining = ref(false)

onMounted(async () => {
  await sitesStore.fetchSites()
  const r = await reviewsStore.fetchReview(reviewId.value)
  if (!r) {
    loading.value = false
    return
  }
  review.value = r
  editTitle.value = r.title
  editSubtitle.value = r.subtitle
  editBodyHtml.value = r.body_html
  loading.value = false
})

const siteName = computed(() =>
  sitesStore.sites.find(s => s.id === review.value?.site_id)?.name ?? review.value?.site_id ?? '',
)

const isSubtitleOnly = computed(() => !!review.value?.subtitle_only)

const suggestions = [
  'Make it more concise',
  'Add a FAQ section at the end',
  'Make the tone more professional',
  'Add more detail about the main topic',
  'Improve the introduction paragraph',
  'Add a compelling call to action',
]

async function sendRefinement(text?: string) {
  const msg = text ?? instruction.value.trim()
  if (!msg || isRefining.value) return
  instruction.value = ''
  isRefining.value = true
  chatHistory.value.push({ role: 'user', text: msg })

  try {
    const refined = await reviewsStore.refineReview(reviewId.value, msg, editBodyHtml.value)
    editBodyHtml.value = refined
    chatHistory.value.push({ role: 'assistant', text: 'Content updated based on your instruction.' })
  } catch (e: any) {
    chatHistory.value.push({ role: 'assistant', text: `Error: ${e.response?.data?.detail ?? e.message}` })
  } finally {
    isRefining.value = false
  }
}

async function publish() {
  publishing.value = true
  publishError.value = ''
  try {
    await reviewsStore.publishReview(reviewId.value, {
      title: editTitle.value,
      subtitle: editSubtitle.value,
      body_html: editBodyHtml.value,
    })
    published.value = true
    setTimeout(() => router.push('/posts'), 2500)
  } catch (e: any) {
    publishError.value = e.response?.data?.detail ?? e.message ?? 'Publish failed'
  } finally {
    publishing.value = false
  }
}

async function reject() {
  if (!confirm('Discard this review? This cannot be undone.')) return
  await reviewsStore.rejectReview(reviewId.value)
  router.push('/pipelines')
}

function formatMode(mode: string) {
  return { new: 'New Post', update: 'Update', recover: 'Recovery', static: 'Static Page' }[mode] ?? mode
}
</script>

<template>
  <!-- Loading -->
  <div v-if="loading" class="flex items-center justify-center py-24 text-muted-foreground gap-2">
    <Loader2 class="w-5 h-5 animate-spin" />
    Loading review...
  </div>

  <!-- Not found -->
  <div v-else-if="!review" class="p-8 text-center text-muted-foreground">
    Review not found.
    <RouterLink to="/pipelines" class="text-primary hover:underline ml-1">Back to Pipelines</RouterLink>
  </div>

  <!-- Success -->
  <div v-else-if="published" class="flex flex-col items-center justify-center py-24 gap-4">
    <CheckCircle2 class="w-12 h-12 text-emerald-500" />
    <h2 class="text-xl font-bold text-foreground">Published!</h2>
    <p class="text-muted-foreground text-sm">Redirecting to Posts...</p>
  </div>

  <!-- Review UI -->
  <div v-else class="flex flex-col h-full">
    <!-- Top bar -->
    <div class="flex items-center gap-4 px-6 py-3 border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-10">
      <RouterLink to="/pipelines" class="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft class="w-4 h-4" />
        Back
      </RouterLink>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-medium">
            {{ formatMode(review.mode) }}
          </span>
          <span class="text-sm font-semibold text-foreground truncate">{{ review.topic || review.title }}</span>
          <span class="text-xs text-muted-foreground">· {{ siteName }}</span>
        </div>
      </div>
      <div class="flex items-center gap-2 flex-shrink-0">
        <button
          @click="reject"
          class="flex items-center gap-1.5 h-9 px-3 rounded-lg border border-destructive/40 text-destructive text-sm hover:bg-destructive/10 transition-colors"
        >
          <XCircle class="w-3.5 h-3.5" />
          Discard
        </button>
        <button
          @click="publish"
          :disabled="publishing"
          class="flex items-center gap-1.5 h-9 px-4 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60"
        >
          <Loader2 v-if="publishing" class="w-3.5 h-3.5 animate-spin" />
          <CheckCircle2 v-else class="w-3.5 h-3.5" />
          {{ publishing ? 'Publishing...' : 'Publish' }}
        </button>
      </div>
    </div>

    <!-- Error banner -->
    <div v-if="publishError" class="mx-6 mt-4 p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm flex items-center gap-2">
      <XCircle class="w-4 h-4 flex-shrink-0" />{{ publishError }}
    </div>

    <!-- Main content -->
    <div class="flex-1 grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-0 min-h-0 overflow-hidden">

      <!-- Editor panel -->
      <div class="overflow-y-auto p-6 space-y-4">
        <!-- Image preview -->
        <div v-if="review.image_base64" class="rounded-xl overflow-hidden border border-border">
          <img
            :src="`data:image/png;base64,${review.image_base64}`"
            :alt="editTitle"
            class="w-full max-h-64 object-cover"
          />
          <div class="px-3 py-1.5 text-xs text-muted-foreground bg-muted/30 flex items-center gap-1.5 border-t border-border">
            <Image class="w-3 h-3" />
            Generated image preview
          </div>
        </div>

        <!-- Title -->
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Title (URL Slug)</label>
          <input
            v-model="editTitle"
            type="text"
            class="w-full px-3 py-2 rounded-lg border border-input bg-background text-foreground text-lg font-semibold focus:outline-none focus:ring-2 focus:ring-ring"
            :placeholder="review.original_title || 'Post title'"
          />
          <p v-if="review.original_title && review.original_title !== editTitle" class="text-xs text-amber-600">
            ⚠ Changing the title changes the URL slug and may break existing links.
          </p>
        </div>

        <!-- Subtitle / Meta description -->
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Meta Description</label>
          <textarea
            v-model="editSubtitle"
            rows="2"
            class="w-full px-3 py-2 rounded-lg border border-input bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
            placeholder="Meta description for search engines..."
          />
          <p class="text-xs text-muted-foreground">{{ editSubtitle.length }}/160 characters</p>
        </div>

        <!-- Body editor -->
        <div v-if="!isSubtitleOnly" class="space-y-1.5">
          <div class="flex items-center justify-between">
            <label class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Body Content</label>
            <button
              @click="showPreview = !showPreview"
              class="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <Eye v-if="!showPreview" class="w-3.5 h-3.5" />
              <EyeOff v-else class="w-3.5 h-3.5" />
              {{ showPreview ? 'Edit' : 'Preview' }}
            </button>
          </div>
          <!-- Preview mode: render HTML -->
          <div
            v-if="showPreview"
            class="prose prose-sm max-w-none rounded-xl border border-input bg-background px-5 py-4 min-h-[400px]"
            v-html="editBodyHtml"
          />
          <!-- Edit mode: TipTap -->
          <TipTapEditor v-else v-model="editBodyHtml" placeholder="Post body content..." />
        </div>

        <!-- Subtitle-only mode message -->
        <div v-else class="p-4 rounded-xl border border-amber-200 bg-amber-50 text-amber-800 text-sm">
          <strong>Meta-description only mode</strong> — the post body is protected (CTR optimization).
          Only the meta description above will be updated.
        </div>
      </div>

      <!-- Chat / Refine panel -->
      <div class="border-l border-border flex flex-col overflow-hidden bg-muted/20">
        <div class="px-4 py-3 border-b border-border flex items-center gap-2">
          <Sparkles class="w-4 h-4 text-primary" />
          <span class="text-sm font-semibold text-foreground">Refine with AI</span>
        </div>

        <!-- Chat history -->
        <div class="flex-1 overflow-y-auto p-3 space-y-3">
          <!-- Suggestions (shown when no chat yet) -->
          <div v-if="!chatHistory.length && !isSubtitleOnly" class="space-y-2">
            <p class="text-xs text-muted-foreground px-1">Suggestions:</p>
            <button
              v-for="s in suggestions"
              :key="s"
              @click="sendRefinement(s)"
              class="block w-full text-left text-xs px-3 py-2 rounded-lg border border-border hover:border-primary/40 hover:bg-primary/5 text-muted-foreground hover:text-foreground transition-all"
            >
              {{ s }}
            </button>
          </div>

          <!-- Messages -->
          <div v-for="(msg, i) in chatHistory" :key="i">
            <div
              :class="msg.role === 'user'
                ? 'ml-4 bg-primary text-white'
                : 'mr-4 bg-background border border-border text-foreground'"
              class="rounded-xl px-3 py-2 text-xs"
            >
              {{ msg.text }}
            </div>
          </div>

          <!-- Refining indicator -->
          <div v-if="isRefining" class="flex items-center gap-2 text-xs text-muted-foreground px-3 py-2">
            <Loader2 class="w-3.5 h-3.5 animate-spin" />
            Refining content...
          </div>
        </div>

        <!-- Input -->
        <div v-if="!isSubtitleOnly" class="p-3 border-t border-border space-y-2">
          <div class="flex gap-2">
            <textarea
              v-model="instruction"
              rows="2"
              placeholder="What would you like to change?"
              class="flex-1 px-3 py-2 rounded-lg border border-input bg-background text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
              @keydown.enter.exact.prevent="sendRefinement()"
            />
            <button
              @click="sendRefinement()"
              :disabled="!instruction.trim() || isRefining"
              class="flex items-center justify-center w-9 h-9 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-40 flex-shrink-0 self-end"
            >
              <Send class="w-3.5 h-3.5" />
            </button>
          </div>
          <p class="text-xs text-muted-foreground">Press Enter to send · Shift+Enter for new line</p>
        </div>
      </div>
    </div>
  </div>
</template>
