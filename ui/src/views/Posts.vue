<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { FileText, ExternalLink, RefreshCw, AlertCircle, Search, PlayCircle, Image } from 'lucide-vue-next'
import { useSitesStore } from '@/stores/sites'
import Badge from '@/components/ui/Badge.vue'
import axios from 'axios'

const sitesStore = useSitesStore()
const selectedSite = ref('')
const loading = ref(false)
const error = ref('')
const posts = ref<any[]>([])
const searchQuery = ref('')

onMounted(async () => {
  await sitesStore.fetchSites()
  if (sitesStore.sites.length > 0) {
    selectedSite.value = sitesStore.sites[0].id
    await loadPosts()
  }
})

watch(selectedSite, loadPosts)

async function loadPosts() {
  if (!selectedSite.value) return
  loading.value = true
  error.value = ''
  posts.value = []
  try {
    const { data } = await axios.get(`/api/posts/${selectedSite.value}`, { params: { limit: 100 } })
    posts.value = data
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? e.message
  } finally {
    loading.value = false
  }
}

const filtered = computed(() => {
  if (!searchQuery.value.trim()) return posts.value
  const q = searchQuery.value.toLowerCase()
  return posts.value.filter(p => p.title?.toLowerCase().includes(q))
})

const currentSite = computed(() => sitesStore.sites.find(s => s.id === selectedSite.value))

function formatDate(iso: string) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }
  catch { return iso }
}

function statusVariant(status: string) {
  if (status === 'published' || status === 'publish') return 'success'
  if (status === 'draft') return 'secondary'
  return 'outline'
}
</script>

<template>
  <div class="p-8 max-w-6xl">
    <!-- Header -->
    <div class="flex items-start justify-between mb-6">
      <div>
        <div class="flex items-center gap-2 mb-1">
          <FileText class="w-5 h-5 text-primary" />
          <h1 class="text-2xl font-bold text-foreground">Posts</h1>
        </div>
        <p class="text-muted-foreground text-sm">Browse published content from your platform.</p>
      </div>
      <div class="flex items-center gap-2">
        <select
          v-model="selectedSite"
          class="h-9 px-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option v-for="s in sitesStore.sites" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <button
          @click="loadPosts"
          :disabled="loading"
          class="flex items-center gap-1.5 h-9 px-3 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="loading ? 'animate-spin' : ''" />
          Refresh
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="flex items-center gap-2 text-destructive bg-destructive/10 px-4 py-3 rounded-lg mb-5">
      <AlertCircle class="w-4 h-4 flex-shrink-0" />{{ error }}
    </div>

    <!-- Search + count -->
    <div v-if="posts.length" class="flex items-center gap-3 mb-5">
      <div class="relative flex-1 max-w-sm">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Filter posts..."
          class="w-full h-9 pl-8 pr-3 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>
      <span class="text-sm text-muted-foreground">
        {{ filtered.length }} of {{ posts.length }} posts
      </span>
      <RouterLink
        v-if="currentSite"
        :to="`/pipelines?site=${currentSite.id}`"
        class="ml-auto flex items-center gap-1.5 h-9 px-3 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary/90 transition-colors"
      >
        <PlayCircle class="w-3.5 h-3.5" />
        Run Pipeline
      </RouterLink>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center gap-2 text-muted-foreground py-12 justify-center">
      <div class="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      Loading posts...
    </div>

    <!-- Empty -->
    <div v-else-if="!loading && posts.length === 0 && !error" class="text-center py-16">
      <FileText class="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
      <p class="text-muted-foreground text-sm">No posts found for this site.</p>
    </div>

    <!-- Posts table -->
    <div v-else-if="filtered.length" class="rounded-xl border border-border overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-muted/40 border-b border-border">
            <th class="px-4 py-3 text-left text-xs font-semibold text-muted-foreground w-8">
              <Image class="w-3.5 h-3.5" />
            </th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Title</th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Status</th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Published</th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="post in filtered"
            :key="post._id"
            class="border-b border-border/40 last:border-0 hover:bg-muted/20 transition-colors"
          >
            <!-- Thumbnail -->
            <td class="px-4 py-3">
              <div v-if="post.image1Url" class="w-8 h-8 rounded overflow-hidden flex-shrink-0">
                <img :src="post.image1Url" :alt="post.title" class="w-full h-full object-cover" loading="lazy" />
              </div>
              <div v-else class="w-8 h-8 rounded bg-muted flex items-center justify-center">
                <FileText class="w-3.5 h-3.5 text-muted-foreground/50" />
              </div>
            </td>

            <!-- Title + excerpt -->
            <td class="px-4 py-3 max-w-sm">
              <p class="font-medium text-foreground text-sm leading-snug line-clamp-1">{{ post.title }}</p>
              <p v-if="post.subtitle" class="text-xs text-muted-foreground mt-0.5 line-clamp-1"
                 v-html="post.subtitle.replace(/<[^>]*>/g, '')" />
              <p v-if="post.price" class="text-xs text-emerald-600 font-medium mt-0.5">${{ post.price }}</p>
            </td>

            <!-- Status badge -->
            <td class="px-4 py-3">
              <Badge :variant="statusVariant(post.status)">
                {{ post.status || 'unknown' }}
              </Badge>
            </td>

            <!-- Date -->
            <td class="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
              {{ formatDate(post.created_at) }}
            </td>

            <!-- Actions -->
            <td class="px-4 py-3">
              <div class="flex items-center gap-1">
                <a
                  v-if="post.url"
                  :href="post.url"
                  target="_blank"
                  class="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  title="Open post"
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
      No posts match "{{ searchQuery }}"
    </div>
  </div>
</template>
