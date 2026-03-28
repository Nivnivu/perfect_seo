<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { X, Shield, ShieldCheck, Database, Settings, BookOpen, Check, Save } from 'lucide-vue-next'
import Input from '@/components/ui/Input.vue'
import Label from '@/components/ui/Label.vue'
import Textarea from '@/components/ui/Textarea.vue'
import Alert from '@/components/ui/Alert.vue'
import Badge from '@/components/ui/Badge.vue'

const props = defineProps<{ siteId: string | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const { t } = useI18n()

type Tab = 'settings' | 'credentials' | 'seo' | 'content'
const activeTab = ref<Tab>('settings')
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const saveError = ref<string | null>(null)

const form = reactive({
  site_name: '', domain: '', blog_url: '', language: 'en', country: 'us', google_domain: 'google.com',
  platform: 'wordpress',
  ai_provider: 'gemini', ai_api_key: '', ai_model: 'gemini-2.5-flash', ai_image_model: '',
  mongodb_uri: '', mongodb_database: 'multiBlogDB', mongodb_collection: '',
  supabase_url: '', supabase_key: '', supabase_bucket: 'blog-poster',
  wp_site_url: '', wp_username: '', wp_app_password: '',
  wc_site_url: '', wc_consumer_key: '', wc_consumer_secret: '',
  shopify_store_domain: '', shopify_admin_api_token: '',
  wix_api_key: '', wix_site_id: '',
  gsc_enabled: false, gsc_credentials_file: '', gsc_site_url: '',
  gsc_min_clicks: 10, gsc_min_impressions: 100, gsc_max_position: 20.0,
  protected_pages: '',
  seed_keywords: '', competitors: '', brand_voice: '',
  image_description: '', image_visual_elements: '', image_color_palette: '',
  unique_selling_points: '',
})

const AI_PROVIDERS = [
  { id: 'gemini',    name: 'Gemini',   keyPlaceholder: 'AIza...',          models: ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash', 'gemini-1.5-pro'], hasImageModel: true,  imageModels: ['imagen-4.0-fast-generate-001', 'imagen-3.0-generate-002', 'imagen-3.0-fast-generate-001'] },
  { id: 'openai',    name: 'OpenAI',   keyPlaceholder: 'sk-...',           models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o3-mini'],                   hasImageModel: true,  imageModels: ['dall-e-3', 'dall-e-2'] },
  { id: 'anthropic', name: 'Claude',   keyPlaceholder: 'sk-ant-...',       models: ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],        hasImageModel: false, imageModels: [] },
  { id: 'mistral',   name: 'Mistral',  keyPlaceholder: 'your-mistral-key', models: ['mistral-large-latest', 'mistral-medium-latest', 'mistral-small-latest'],    hasImageModel: false, imageModels: [] },
  { id: 'deepseek',  name: 'DeepSeek', keyPlaceholder: 'sk-...',           models: ['deepseek-chat', 'deepseek-reasoner'],                                       hasImageModel: false, imageModels: [] },
]

const currentProvider = computed(() => AI_PROVIDERS.find(p => p.id === form.ai_provider) ?? AI_PROVIDERS[0])
const needsSupabase = computed(() => form.platform === 'mongodb' || form.platform === 'wordpress')

function selectProvider(id: string) {
  const p = AI_PROVIDERS.find(pr => pr.id === id)!
  form.ai_provider = id
  form.ai_model = p.models[0]
  form.ai_image_model = p.hasImageModel ? p.imageModels[0] : ''
}

const PLATFORM_LABELS: Record<string, string> = {
  mongodb: 'MongoDB', wordpress: 'WordPress', woocommerce: 'WooCommerce', shopify: 'Shopify', wix: 'Wix',
}

function parseConfig(raw: any) {
  const site = raw.site || {}
  form.site_name   = site.name          || ''
  form.domain      = site.domain        || ''
  form.blog_url    = site.blog_url      || ''
  form.language    = site.language      || 'en'
  form.country     = site.country       || 'us'
  form.google_domain = site.google_domain || 'google.com'
  form.platform    = raw.platform       || 'wordpress'

  for (const p of AI_PROVIDERS) {
    if (raw[p.id]) {
      form.ai_provider    = p.id
      form.ai_api_key     = raw[p.id].api_key    || ''
      form.ai_model       = raw[p.id].model       || p.models[0]
      form.ai_image_model = raw[p.id].image_model || ''
      break
    }
  }

  const m = raw.mongodb     || {}
  form.mongodb_uri        = m.uri        || ''
  form.mongodb_database   = m.database   || 'multiBlogDB'
  form.mongodb_collection = m.collection || ''

  const sb = raw.supabase || {}
  form.supabase_url    = sb.url    || ''
  form.supabase_key    = sb.key    || ''
  form.supabase_bucket = sb.bucket || 'blog-poster'

  const wp = raw.wordpress || {}
  form.wp_site_url     = wp.site_url     || ''
  form.wp_username     = wp.username     || ''
  form.wp_app_password = wp.app_password || ''

  const wc = raw.woocommerce || {}
  form.wc_site_url       = wc.site_url       || ''
  form.wc_consumer_key   = wc.consumer_key   || ''
  form.wc_consumer_secret = wc.consumer_secret || ''

  const sh = raw.shopify || {}
  form.shopify_store_domain    = sh.store_domain    || ''
  form.shopify_admin_api_token = sh.admin_api_token || ''

  const wx = raw.wix || {}
  form.wix_api_key = wx.api_key || ''
  form.wix_site_id = wx.site_id || ''

  const gsc = raw.search_console || {}
  form.gsc_enabled          = Boolean(gsc.credentials_file)
  form.gsc_credentials_file = gsc.credentials_file || ''
  form.gsc_site_url         = gsc.site_url         || ''
  const thresh = gsc.protection_thresholds || {}
  form.gsc_min_clicks       = thresh.min_clicks       ?? 10
  form.gsc_min_impressions  = thresh.min_impressions  ?? 100
  form.gsc_max_position     = thresh.max_position     ?? 20.0
  form.protected_pages      = (gsc.protected_pages || []).join('\n')

  const kw = raw.keywords || {}
  form.seed_keywords        = (kw.seeds                       || []).join('\n')
  form.competitors          = (raw.competitors                 || []).join('\n')
  const ctx = raw.context || {}
  form.brand_voice          = ctx.brand_voice                 || ''
  const img = ctx.image_style || {}
  form.image_description    = img.description                 || ''
  form.image_visual_elements = img.visual_elements            || ''
  form.image_color_palette  = img.color_palette               || ''
  form.unique_selling_points = (ctx.unique_selling_points     || []).join('\n')
}

const DEFAULT_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

function buildConfig(): Record<string, any> {
  const lines = (raw: string) => raw.split('\n').map(s => s.trim()).filter(Boolean)
  const config: Record<string, any> = { platform: form.platform }

  const aiBlock: Record<string, any> = { api_key: form.ai_api_key, model: form.ai_model }
  if (form.ai_image_model) aiBlock.image_model = form.ai_image_model
  config[form.ai_provider] = aiBlock

  config.site = {
    name: form.site_name, domain: form.domain,
    blog_url: form.blog_url || `https://${form.domain}/blog`,
    language: form.language, country: form.country, google_domain: form.google_domain,
  }
  config.scraping = { user_agent: DEFAULT_UA, request_delay: 2 }

  if (form.platform === 'mongodb') {
    config.mongodb  = { uri: form.mongodb_uri, database: form.mongodb_database, collection: form.mongodb_collection }
    config.supabase = { url: form.supabase_url, key: form.supabase_key, bucket: form.supabase_bucket }
  } else if (form.platform === 'wordpress') {
    config.wordpress = { site_url: form.wp_site_url, username: form.wp_username, app_password: form.wp_app_password }
    config.supabase  = { url: form.supabase_url, key: form.supabase_key, bucket: form.supabase_bucket }
  } else if (form.platform === 'woocommerce') {
    config.woocommerce = { site_url: form.wc_site_url, consumer_key: form.wc_consumer_key, consumer_secret: form.wc_consumer_secret }
  } else if (form.platform === 'shopify') {
    config.shopify = { store_domain: form.shopify_store_domain, admin_api_token: form.shopify_admin_api_token }
  } else if (form.platform === 'wix') {
    config.wix = { api_key: form.wix_api_key, site_id: form.wix_site_id }
  }

  if (form.gsc_enabled && form.gsc_credentials_file.trim()) {
    const gscCfg: Record<string, any> = {
      credentials_file: form.gsc_credentials_file,
      token_file: 'gsc_token.json',
      site_url: form.gsc_site_url || `https://${form.domain}/`,
      protection_thresholds: {
        min_clicks: form.gsc_min_clicks,
        min_impressions: form.gsc_min_impressions,
        max_position: form.gsc_max_position,
      },
    }
    const pp = lines(form.protected_pages)
    if (pp.length) gscCfg.protected_pages = pp
    config.search_console = gscCfg
  }

  config.keywords  = { seeds: lines(form.seed_keywords) }
  config.competitors = lines(form.competitors)
  config.context   = {
    brand_voice: form.brand_voice,
    image_style: { description: form.image_description, visual_elements: form.image_visual_elements, color_palette: form.image_color_palette },
    unique_selling_points: lines(form.unique_selling_points),
  }
  return config
}

async function load() {
  if (!props.siteId) return
  loading.value = true
  error.value = null
  try {
    const { data } = await axios.get(`/api/sites/${props.siteId}`)
    parseConfig(data)
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? e.message ?? 'Failed to load'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  saveError.value = null
  try {
    await axios.put(`/api/sites/${props.siteId}`, buildConfig())
    emit('saved')
  } catch (e: any) {
    saveError.value = e.response?.data?.detail ?? e.message ?? 'Failed to save'
  } finally {
    saving.value = false
  }
}

watch(() => props.siteId, id => {
  if (id) { activeTab.value = 'settings'; load() }
}, { immediate: true })

const tabs = computed(() => [
  { id: 'settings'     as Tab, label: t('editSite.tabs.settings'),      icon: Settings },
  { id: 'credentials'  as Tab, label: t('editSite.tabs.credentials'),   icon: Database },
  { id: 'seo'          as Tab, label: t('editSite.tabs.seoProtection'), icon: Shield   },
  { id: 'content'      as Tab, label: t('editSite.tabs.content'),       icon: BookOpen },
])
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div
        v-if="siteId"
        class="fixed inset-0 z-50 flex justify-end"
        style="background: rgba(0,0,0,0.45); backdrop-filter: blur(2px);"
        @click.self="emit('close')"
      >
        <div class="bg-background w-[620px] max-w-[95vw] h-full flex flex-col shadow-2xl" @click.stop>

          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-border flex-shrink-0">
            <div>
              <h2 class="text-base font-bold text-foreground">{{ $t('editSite.title') }}</h2>
              <p class="text-xs text-muted-foreground font-mono mt-0.5">config.{{ siteId }}.yaml</p>
            </div>
            <button @click="emit('close')" class="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
              <X class="w-4 h-4" />
            </button>
          </div>

          <!-- Tabs -->
          <div class="flex border-b border-border flex-shrink-0 overflow-x-auto">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              @click="activeTab = tab.id"
              class="flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap"
              :class="activeTab === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'"
            >
              <component :is="tab.icon" class="w-3.5 h-3.5" />
              {{ tab.label }}
            </button>
          </div>

          <!-- Loading -->
          <div v-if="loading" class="flex-1 flex items-center justify-center gap-3 text-muted-foreground text-sm">
            <div class="w-5 h-5 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            {{ $t('editSite.loading') }}
          </div>

          <!-- Error -->
          <div v-else-if="error" class="flex-1 p-6">
            <Alert variant="error">{{ error }}</Alert>
          </div>

          <!-- Content -->
          <div v-else class="flex-1 overflow-y-auto">

            <!-- ── Settings ─────────────────────────────────────── -->
            <div v-if="activeTab === 'settings'" class="p-6 space-y-6">
              <div>
                <p class="text-sm font-semibold text-foreground mb-4">{{ $t('editSite.settings.siteInfoSection') }}</p>
                <div class="space-y-4">
                  <div class="grid grid-cols-2 gap-4">
                    <div class="space-y-1.5">
                      <Label>{{ $t('editSite.settings.siteName') }} <span class="text-destructive">*</span></Label>
                      <Input v-model="form.site_name" placeholder="My Store" />
                    </div>
                    <div class="space-y-1.5">
                      <Label>{{ $t('editSite.settings.domain') }} <span class="text-destructive">*</span></Label>
                      <Input v-model="form.domain" placeholder="mystore.com" class="font-mono" />
                    </div>
                  </div>
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.settings.blogUrl') }}</Label>
                    <Input v-model="form.blog_url" placeholder="https://mystore.com/blog" class="font-mono" />
                  </div>
                  <div class="grid grid-cols-3 gap-4">
                    <div class="space-y-1.5">
                      <Label>{{ $t('editSite.settings.language') }}</Label>
                      <Input v-model="form.language" placeholder="en" class="font-mono" />
                    </div>
                    <div class="space-y-1.5">
                      <Label>{{ $t('editSite.settings.country') }}</Label>
                      <Input v-model="form.country" placeholder="us" class="font-mono" />
                    </div>
                    <div class="space-y-1.5">
                      <Label>{{ $t('editSite.settings.googleDomain') }}</Label>
                      <Input v-model="form.google_domain" placeholder="google.com" class="font-mono" />
                    </div>
                  </div>
                </div>
              </div>

              <div class="border-t border-border pt-5">
                <p class="text-sm font-semibold text-foreground mb-4">{{ $t('editSite.settings.aiSection') }}</p>
                <div class="grid grid-cols-5 gap-2 mb-4">
                  <button
                    v-for="p in AI_PROVIDERS"
                    :key="p.id"
                    type="button"
                    @click="selectProvider(p.id)"
                    class="relative flex flex-col items-center justify-center py-2.5 px-2 rounded-xl border-2 transition-all"
                    :class="form.ai_provider === p.id
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-muted-foreground/30'"
                  >
                    <span class="text-xs font-semibold" :class="form.ai_provider === p.id ? 'text-primary' : 'text-foreground'">{{ p.name }}</span>
                    <div v-if="form.ai_provider === p.id" class="absolute -top-1.5 -end-1.5 w-4 h-4 rounded-full bg-primary flex items-center justify-center">
                      <Check class="w-2.5 h-2.5 text-white" />
                    </div>
                  </button>
                </div>
                <div class="grid grid-cols-2 gap-4">
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.settings.apiKey', { provider: currentProvider.name }) }} <span class="text-destructive">*</span></Label>
                    <Input v-model="form.ai_api_key" type="password" :placeholder="currentProvider.keyPlaceholder" />
                  </div>
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.settings.model') }}</Label>
                    <select
                      v-model="form.ai_model"
                      class="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm font-mono ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 transition-colors"
                    >
                      <option v-for="m in currentProvider.models" :key="m" :value="m">{{ m }}</option>
                    </select>
                  </div>
                </div>
                <div v-if="currentProvider.hasImageModel" class="mt-4 grid grid-cols-2 gap-4">
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.settings.imageModel') }}</Label>
                    <select
                      v-model="form.ai_image_model"
                      class="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm font-mono ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 transition-colors"
                    >
                      <option value="">{{ $t('editSite.settings.noImageModel') }}</option>
                      <option v-for="m in currentProvider.imageModels" :key="m" :value="m">{{ m }}</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            <!-- ── Credentials ──────────────────────────────────── -->
            <div v-else-if="activeTab === 'credentials'" class="p-6 space-y-5">
              <div class="flex items-center gap-3 p-3 bg-muted/50 rounded-lg border border-border">
                <p class="text-xs text-muted-foreground flex-1">{{ $t('editSite.credentials.platformNote') }}</p>
                <Badge variant="default">{{ PLATFORM_LABELS[form.platform] }}</Badge>
              </div>

              <template v-if="form.platform === 'mongodb'">
                <div class="space-y-1.5">
                  <Label>MongoDB URI <span class="text-destructive">*</span></Label>
                  <Input v-model="form.mongodb_uri" type="password" placeholder="mongodb+srv://user:pass@cluster.mongodb.net/" class="font-mono" />
                </div>
                <div class="grid grid-cols-2 gap-4">
                  <div class="space-y-1.5">
                    <Label>Database</Label>
                    <Input v-model="form.mongodb_database" placeholder="multiBlogDB" class="font-mono" />
                  </div>
                  <div class="space-y-1.5">
                    <Label>Collection <span class="text-destructive">*</span></Label>
                    <Input v-model="form.mongodb_collection" placeholder="mysite_posts" class="font-mono" />
                  </div>
                </div>
              </template>

              <template v-else-if="form.platform === 'wordpress'">
                <div class="space-y-1.5">
                  <Label>Site URL <span class="text-destructive">*</span></Label>
                  <Input v-model="form.wp_site_url" placeholder="https://myblog.com" />
                </div>
                <div class="grid grid-cols-2 gap-4">
                  <div class="space-y-1.5">
                    <Label>Username <span class="text-destructive">*</span></Label>
                    <Input v-model="form.wp_username" placeholder="admin" />
                  </div>
                  <div class="space-y-1.5">
                    <Label>App Password <span class="text-destructive">*</span></Label>
                    <Input v-model="form.wp_app_password" type="password" placeholder="xxxx xxxx xxxx xxxx" class="font-mono" />
                  </div>
                </div>
              </template>

              <template v-else-if="form.platform === 'woocommerce'">
                <div class="space-y-1.5">
                  <Label>Site URL <span class="text-destructive">*</span></Label>
                  <Input v-model="form.wc_site_url" placeholder="https://mystore.com" />
                </div>
                <div class="space-y-1.5">
                  <Label>Consumer Key <span class="text-destructive">*</span></Label>
                  <Input v-model="form.wc_consumer_key" type="password" placeholder="ck_..." class="font-mono" />
                </div>
                <div class="space-y-1.5">
                  <Label>Consumer Secret <span class="text-destructive">*</span></Label>
                  <Input v-model="form.wc_consumer_secret" type="password" placeholder="cs_..." class="font-mono" />
                </div>
              </template>

              <template v-else-if="form.platform === 'shopify'">
                <div class="space-y-1.5">
                  <Label>Store Domain <span class="text-destructive">*</span></Label>
                  <Input v-model="form.shopify_store_domain" placeholder="mystore.myshopify.com" class="font-mono" />
                </div>
                <div class="space-y-1.5">
                  <Label>Admin API Token <span class="text-destructive">*</span></Label>
                  <Input v-model="form.shopify_admin_api_token" type="password" placeholder="shpat_..." class="font-mono" />
                </div>
              </template>

              <template v-else-if="form.platform === 'wix'">
                <div class="space-y-1.5">
                  <Label>API Key <span class="text-destructive">*</span></Label>
                  <Input v-model="form.wix_api_key" type="password" placeholder="IST...." class="font-mono" />
                </div>
                <div class="space-y-1.5">
                  <Label>Site ID <span class="text-destructive">*</span></Label>
                  <Input v-model="form.wix_site_id" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" class="font-mono" />
                </div>
              </template>

              <template v-if="needsSupabase">
                <div class="border-t border-border pt-5">
                  <p class="text-sm font-semibold text-foreground mb-1">{{ $t('wizard.credentials.supabaseSection') }}</p>
                  <p class="text-xs text-muted-foreground mb-4">{{ $t('wizard.credentials.supabaseSubtitle') }}</p>
                  <div class="space-y-4">
                    <div class="space-y-1.5">
                      <Label>{{ $t('wizard.credentials.supabaseUrl') }}</Label>
                      <Input v-model="form.supabase_url" placeholder="https://xxxx.supabase.co" class="font-mono" />
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                      <div class="space-y-1.5">
                        <Label>{{ $t('wizard.credentials.supabaseAnonKey') }}</Label>
                        <Input v-model="form.supabase_key" type="password" placeholder="eyJ..." class="font-mono" />
                      </div>
                      <div class="space-y-1.5">
                        <Label>{{ $t('wizard.credentials.bucketName') }}</Label>
                        <Input v-model="form.supabase_bucket" placeholder="blog-poster" class="font-mono" />
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </div>

            <!-- ── SEO Protection ───────────────────────────────── -->
            <div v-else-if="activeTab === 'seo'" class="p-6 space-y-6">

              <!-- Protected pages -->
              <div>
                <div class="flex items-center gap-2 mb-1">
                  <ShieldCheck class="w-4 h-4 text-primary" />
                  <p class="text-sm font-semibold text-foreground">{{ $t('editSite.seoProtection.protectedPagesSection') }}</p>
                </div>
                <p class="text-xs text-muted-foreground mb-3">{{ $t('editSite.seoProtection.protectedPagesHint') }}</p>
                <Textarea
                  v-model="form.protected_pages"
                  :rows="5"
                  :placeholder="$t('editSite.seoProtection.protectedPagesPlaceholder')"
                  class="font-mono text-xs"
                />
              </div>

              <!-- GSC -->
              <div class="border-t border-border pt-5">
                <p class="text-sm font-semibold text-foreground mb-4">{{ $t('editSite.seoProtection.gscSection') }}</p>
                <label
                  class="flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer transition-all mb-4"
                  :class="form.gsc_enabled ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/30'"
                >
                  <input type="checkbox" v-model="form.gsc_enabled" class="w-4 h-4 accent-primary" />
                  <div>
                    <p class="font-semibold text-sm text-foreground">{{ $t('editSite.seoProtection.gscEnabled') }}</p>
                    <p class="text-xs text-muted-foreground mt-0.5">{{ $t('editSite.seoProtection.gscEnabledSubtitle') }}</p>
                  </div>
                </label>
                <div v-if="form.gsc_enabled" class="space-y-4">
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.seoProtection.credentialsFile') }} <span class="text-destructive">*</span></Label>
                    <Input v-model="form.gsc_credentials_file" placeholder="client_secret_xxxx.json" class="font-mono text-xs" />
                    <p class="text-xs text-muted-foreground">{{ $t('editSite.seoProtection.credentialsHint') }}</p>
                  </div>
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.seoProtection.gscSiteUrl') }}</Label>
                    <Input v-model="form.gsc_site_url" :placeholder="`https://${form.domain || 'yoursite.com'}/`" class="font-mono" />
                    <p class="text-xs text-muted-foreground">{{ $t('editSite.seoProtection.gscSiteUrlHint') }}</p>
                  </div>
                </div>
              </div>

              <!-- Thresholds + classification guide -->
              <div class="border-t border-border pt-5">
                <p class="text-sm font-semibold text-foreground mb-1">{{ $t('editSite.seoProtection.thresholdsSection') }}</p>
                <p class="text-xs text-muted-foreground mb-4">{{ $t('editSite.seoProtection.thresholdsHint') }}</p>
                <div class="grid grid-cols-3 gap-4 mb-6">
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.seoProtection.minClicks') }}</Label>
                    <Input v-model.number="form.gsc_min_clicks" type="number" min="0" placeholder="10" />
                  </div>
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.seoProtection.minImpressions') }}</Label>
                    <Input v-model.number="form.gsc_min_impressions" type="number" min="0" placeholder="100" />
                  </div>
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.seoProtection.maxPosition') }}</Label>
                    <Input v-model.number="form.gsc_max_position" type="number" min="1" max="100" step="0.5" placeholder="20" />
                  </div>
                </div>

                <p class="text-xs font-semibold text-foreground mb-2">{{ $t('editSite.seoProtection.classificationGuide') }}</p>
                <div class="rounded-xl border border-border overflow-hidden text-xs">
                  <div class="flex items-center gap-3 px-3 py-2.5 bg-amber-50 dark:bg-amber-950/20 border-b border-border">
                    <span class="text-sm flex-shrink-0">🏆</span>
                    <div class="min-w-0 flex-1">
                      <span class="font-semibold text-foreground">{{ $t('editSite.seoProtection.topPerformer') }}</span>
                      <span class="text-muted-foreground ms-2">{{ $t('editSite.seoProtection.topPerformerDesc', { pos: form.gsc_max_position, clicks: form.gsc_min_clicks }) }}</span>
                    </div>
                    <span class="text-amber-700 dark:text-amber-400 font-bold flex-shrink-0">SKIP</span>
                  </div>
                  <div class="flex items-center gap-3 px-3 py-2.5 bg-blue-50 dark:bg-blue-950/20 border-b border-border">
                    <span class="text-sm flex-shrink-0">📈</span>
                    <div class="min-w-0 flex-1">
                      <span class="font-semibold text-foreground">{{ $t('editSite.seoProtection.page2') }}</span>
                      <span class="text-muted-foreground ms-2">{{ $t('editSite.seoProtection.page2Desc') }}</span>
                    </div>
                    <span class="text-blue-700 dark:text-blue-400 font-bold flex-shrink-0">PRIORITY</span>
                  </div>
                  <div class="flex items-center gap-3 px-3 py-2.5 bg-violet-50 dark:bg-violet-950/20 border-b border-border">
                    <span class="text-sm flex-shrink-0">🎯</span>
                    <div class="min-w-0 flex-1">
                      <span class="font-semibold text-foreground">{{ $t('editSite.seoProtection.ctrOpportunity') }}</span>
                      <span class="text-muted-foreground ms-2">{{ $t('editSite.seoProtection.ctrOpportunityDesc') }}</span>
                    </div>
                    <span class="text-violet-700 dark:text-violet-400 font-bold flex-shrink-0">META ONLY</span>
                  </div>
                  <div class="flex items-center gap-3 px-3 py-2.5 bg-muted/30 border-b border-border">
                    <span class="text-sm flex-shrink-0">📝</span>
                    <div class="min-w-0 flex-1">
                      <span class="font-semibold text-foreground">{{ $t('editSite.seoProtection.lowPerformer') }}</span>
                      <span class="text-muted-foreground ms-2">{{ $t('editSite.seoProtection.lowPerformerDesc') }}</span>
                    </div>
                    <span class="text-foreground/50 font-bold flex-shrink-0">REWRITE</span>
                  </div>
                  <div class="flex items-center gap-3 px-3 py-2.5">
                    <span class="text-sm flex-shrink-0">❓</span>
                    <div class="min-w-0 flex-1">
                      <span class="font-semibold text-foreground">{{ $t('editSite.seoProtection.notIndexed') }}</span>
                      <span class="text-muted-foreground ms-2">{{ $t('editSite.seoProtection.notIndexedDesc') }}</span>
                    </div>
                    <span class="text-foreground/50 font-bold flex-shrink-0">REWRITE</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- ── Content ──────────────────────────────────────── -->
            <div v-else-if="activeTab === 'content'" class="p-6 space-y-5">
              <div class="space-y-1.5">
                <Label>{{ $t('editSite.content.seedKeywords') }}</Label>
                <Textarea v-model="form.seed_keywords" :rows="4" placeholder="dog food&#10;cat food&#10;pet accessories" />
                <p class="text-xs text-muted-foreground">{{ $t('editSite.content.seedKeywordsHint') }}</p>
              </div>
              <div class="space-y-1.5">
                <Label>{{ $t('editSite.content.competitors') }}</Label>
                <Textarea v-model="form.competitors" :rows="3" placeholder="https://competitor1.com/&#10;https://competitor2.com/" />
                <p class="text-xs text-muted-foreground">{{ $t('editSite.content.competitorsHint') }}</p>
              </div>
              <div class="space-y-1.5">
                <Label>{{ $t('editSite.content.brandVoice') }}</Label>
                <Textarea v-model="form.brand_voice" :rows="4" placeholder="We are a friendly pet care brand..." />
                <p class="text-xs text-muted-foreground">{{ $t('editSite.content.brandVoiceHint') }}</p>
              </div>
              <div class="border-t border-border pt-5">
                <p class="text-sm font-semibold text-foreground mb-1">{{ $t('editSite.content.imageStyleSection') }}</p>
                <p class="text-xs text-muted-foreground mb-4">{{ $t('editSite.content.imageStyleSubtitle') }}</p>
                <div class="space-y-3">
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.content.imageDescription') }}</Label>
                    <Textarea v-model="form.image_description" :rows="2" placeholder="A modern pet care brand with bright, friendly visuals" />
                  </div>
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.content.visualElements') }}</Label>
                    <Textarea v-model="form.image_visual_elements" :rows="2" placeholder="Clean backgrounds, natural lighting, happy pets" />
                  </div>
                  <div class="space-y-1.5">
                    <Label>{{ $t('editSite.content.colorPalette') }}</Label>
                    <Textarea v-model="form.image_color_palette" :rows="2" placeholder="Warm oranges, soft greens, clean whites" />
                  </div>
                </div>
              </div>
              <div class="space-y-1.5">
                <Label>{{ $t('editSite.content.usp') }}</Label>
                <Textarea v-model="form.unique_selling_points" :rows="3" placeholder="Free shipping on orders over $50&#10;Vet-approved products only" />
                <p class="text-xs text-muted-foreground">{{ $t('editSite.content.uspHint') }}</p>
              </div>
            </div>

          </div>

          <!-- Footer -->
          <div class="flex-shrink-0 border-t border-border px-6 py-4">
            <div v-if="saveError" class="text-xs text-destructive bg-destructive/10 px-3 py-2 rounded-lg mb-3">
              {{ saveError }}
            </div>
            <div class="flex items-center justify-end gap-3">
              <button
                @click="emit('close')"
                class="px-4 py-2 text-sm rounded-lg border border-border hover:bg-muted transition-colors"
              >
                {{ $t('editSite.cancel') }}
              </button>
              <button
                @click="save"
                :disabled="saving"
                class="flex items-center gap-2 px-5 py-2 text-sm font-semibold bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-60"
              >
                <div v-if="saving" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <Save v-else class="w-4 h-4" />
                {{ saving ? $t('editSite.saving') : $t('editSite.saveChanges') }}
              </button>
            </div>
          </div>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.2s ease;
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-active > div,
.drawer-leave-active > div {
  transition: transform 0.25s ease;
}
.drawer-enter-from > div,
.drawer-leave-to > div {
  transform: translateX(100%);
}
</style>
