<script setup lang="ts">
import { watch, ref, computed } from 'vue'
import { useWizardStore } from '@/stores/wizard'
import Input from '@/components/ui/Input.vue'
import Label from '@/components/ui/Label.vue'
import { Check } from 'lucide-vue-next'

const wizard = useWizardStore()

const providers = [
  {
    id: 'gemini',
    name: 'Google Gemini',
    short: 'Gemini',
    keyPlaceholder: 'AIza...',
    docsUrl: 'https://aistudio.google.com/app/apikey',
    docsLabel: 'aistudio.google.com',
    models: ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'],
    defaultModel: 'gemini-2.5-flash',
    hasImageModel: true,
    imageModels: ['imagen-4.0-fast-generate-001', 'imagen-3.0-generate-002', 'imagen-3.0-fast-generate-001'],
    defaultImageModel: 'imagen-4.0-fast-generate-001',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    short: 'OpenAI',
    keyPlaceholder: 'sk-...',
    docsUrl: 'https://platform.openai.com/api-keys',
    docsLabel: 'platform.openai.com',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o3-mini'],
    defaultModel: 'gpt-4o',
    hasImageModel: true,
    imageModels: ['dall-e-3', 'dall-e-2'],
    defaultImageModel: 'dall-e-3',
  },
  {
    id: 'anthropic',
    name: 'Anthropic Claude',
    short: 'Claude',
    keyPlaceholder: 'sk-ant-...',
    docsUrl: 'https://console.anthropic.com/settings/keys',
    docsLabel: 'console.anthropic.com',
    models: ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
    defaultModel: 'claude-sonnet-4-6',
    hasImageModel: false,
    imageModels: [],
    defaultImageModel: '',
  },
  {
    id: 'mistral',
    name: 'Mistral AI',
    short: 'Mistral',
    keyPlaceholder: 'your-mistral-key',
    docsUrl: 'https://console.mistral.ai/api-keys/',
    docsLabel: 'console.mistral.ai',
    models: ['mistral-large-latest', 'mistral-medium-latest', 'mistral-small-latest', 'open-mistral-nemo'],
    defaultModel: 'mistral-large-latest',
    hasImageModel: false,
    imageModels: [],
    defaultImageModel: '',
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    short: 'DeepSeek',
    keyPlaceholder: 'sk-...',
    docsUrl: 'https://platform.deepseek.com/api_keys',
    docsLabel: 'platform.deepseek.com',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    defaultModel: 'deepseek-chat',
    hasImageModel: false,
    imageModels: [],
    defaultImageModel: '',
  },
]

const currentProvider = computed(() => providers.find(p => p.id === wizard.form.ai_provider) ?? providers[0])

function selectProvider(id: string) {
  const p = providers.find(pr => pr.id === id)!
  wizard.form.ai_provider = id as any
  wizard.form.ai_model = p.defaultModel
  wizard.form.ai_image_model = p.defaultImageModel
}

// Auto-derive blog_url from domain unless manually edited
const blogUrlTouched = ref(false)
watch(() => wizard.form.domain, (domain) => {
  if (!blogUrlTouched.value) {
    wizard.form.blog_url = domain ? `https://${domain}/blog` : ''
  }
})

// Auto-derive site_id from site_name (lowercase + sanitize)
const siteIdTouched = ref(false)
watch(() => wizard.form.site_name, (name) => {
  if (!siteIdTouched.value) {
    wizard.form.site_id = name.toLowerCase().replace(/[^a-z0-9_-]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')
  }
})

function onSiteIdInput(e: Event) {
  siteIdTouched.value = true
  wizard.form.site_id = (e.target as HTMLInputElement).value
    .toLowerCase().replace(/[^a-z0-9_-]/g, '')
}

watch(() => wizard.form.country, () => {
  wizard.syncGoogleDomain()
})
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 class="text-xl font-bold text-foreground">Site Info & AI Settings</h2>
      <p class="text-muted-foreground mt-1 text-sm">Configure your site details and choose an AI provider.</p>
    </div>

    <div class="space-y-5">
      <!-- Site name + site ID -->
      <div class="grid grid-cols-2 gap-4">
        <div class="space-y-1.5">
          <Label>Site Name <span class="text-destructive">*</span></Label>
          <Input v-model="wizard.form.site_name" placeholder="My Pet Store" />
        </div>
        <div class="space-y-1.5">
          <Label>
            Site ID <span class="text-destructive">*</span>
            <span class="text-muted-foreground font-normal ml-1 text-xs">→ config.{{ wizard.form.site_id || 'mysite' }}.yaml</span>
          </Label>
          <Input
            :value="wizard.form.site_id"
            @input="onSiteIdInput"
            placeholder="mysite"
            class="font-mono"
          />
          <p class="text-xs text-muted-foreground">Lowercase, letters/numbers/hyphens only</p>
        </div>
      </div>

      <!-- Domain + Blog URL -->
      <div class="grid grid-cols-2 gap-4">
        <div class="space-y-1.5">
          <Label>Domain <span class="text-destructive">*</span></Label>
          <Input v-model="wizard.form.domain" placeholder="mypetstore.com" />
          <p class="text-xs text-muted-foreground">Without https://</p>
        </div>
        <div class="space-y-1.5">
          <Label>Blog URL</Label>
          <Input
            v-model="wizard.form.blog_url"
            @focus="blogUrlTouched = true"
            placeholder="https://mypetstore.com/blog"
          />
        </div>
      </div>

      <!-- Language + Country + Google Domain -->
      <div class="grid grid-cols-3 gap-4">
        <div class="space-y-1.5">
          <Label>Language <span class="text-destructive">*</span></Label>
          <Input v-model="wizard.form.language" placeholder="en" class="font-mono" />
          <p class="text-xs text-muted-foreground">e.g. en, he, fr, de</p>
        </div>
        <div class="space-y-1.5">
          <Label>Country <span class="text-destructive">*</span></Label>
          <Input v-model="wizard.form.country" placeholder="us" class="font-mono" />
          <p class="text-xs text-muted-foreground">e.g. us, il, gb, de</p>
        </div>
        <div class="space-y-1.5">
          <Label>Google Domain</Label>
          <Input v-model="wizard.form.google_domain" placeholder="google.com" class="font-mono" />
          <p class="text-xs text-muted-foreground">Auto-set from country</p>
        </div>
      </div>

      <!-- AI Provider section -->
      <div class="border-t border-border pt-5">
        <p class="text-sm font-semibold text-foreground mb-1">AI Provider</p>
        <p class="text-xs text-muted-foreground mb-4">Choose any provider — use your own API key.</p>

        <!-- Provider cards -->
        <div class="grid grid-cols-5 gap-2 mb-5">
          <button
            v-for="p in providers"
            :key="p.id"
            type="button"
            @click="selectProvider(p.id)"
            class="relative flex flex-col items-center justify-center gap-1 py-3 px-2 rounded-xl border-2 transition-all text-center"
            :class="wizard.form.ai_provider === p.id
              ? 'border-primary bg-primary/5'
              : 'border-border hover:border-muted-foreground/30 hover:bg-muted/40'"
          >
            <span
              class="text-xs font-semibold leading-tight"
              :class="wizard.form.ai_provider === p.id ? 'text-primary' : 'text-foreground'"
            >{{ p.short }}</span>
            <div
              v-if="wizard.form.ai_provider === p.id"
              class="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-primary flex items-center justify-center"
            >
              <Check class="w-2.5 h-2.5 text-white" />
            </div>
          </button>
        </div>

        <!-- API Key + Model -->
        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <Label>{{ currentProvider.name }} API Key <span class="text-destructive">*</span></Label>
            <Input
              v-model="wizard.form.ai_api_key"
              type="password"
              :placeholder="currentProvider.keyPlaceholder"
            />
            <p class="text-xs text-muted-foreground">
              Get yours at
              <a :href="currentProvider.docsUrl" target="_blank" class="text-primary hover:underline">
                {{ currentProvider.docsLabel }}
              </a>
            </p>
          </div>
          <div class="space-y-1.5">
            <Label>Model</Label>
            <select
              v-model="wizard.form.ai_model"
              class="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm font-mono ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 transition-colors"
            >
              <option v-for="m in currentProvider.models" :key="m" :value="m">{{ m }}</option>
            </select>
            <p class="text-xs text-muted-foreground">Or type any model ID above after selecting</p>
          </div>
        </div>

        <!-- Image Generation Model (Gemini / OpenAI only) -->
        <div v-if="currentProvider.hasImageModel" class="grid grid-cols-2 gap-4 mt-4">
          <div class="space-y-1.5 col-start-1">
            <Label>Image Generation Model</Label>
            <select
              v-model="wizard.form.ai_image_model"
              class="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm font-mono ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 transition-colors"
            >
              <option value="">None (skip image generation)</option>
              <option v-for="m in currentProvider.imageModels" :key="m" :value="m">{{ m }}</option>
            </select>
            <p class="text-xs text-muted-foreground">Used to generate post featured images</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
