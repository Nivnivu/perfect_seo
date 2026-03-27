<script setup lang="ts">
import { computed } from 'vue'
import { useWizardStore } from '@/stores/wizard'
import Alert from '@/components/ui/Alert.vue'
import { Check, Globe, Database, ShoppingCart, Store, Layout, Zap } from 'lucide-vue-next'

const wizard = useWizardStore()

const mask = (v: string) => v ? '●'.repeat(Math.min(v.length, 12)) : '—'

const platformIcon = computed(() => {
  const map: Record<string, any> = {
    mongodb: Database, wordpress: Globe, woocommerce: ShoppingCart, shopify: Store, wix: Layout,
  }
  return map[wizard.form.platform] ?? Globe
})

const platformLabel: Record<string, string> = {
  mongodb: 'MongoDB', wordpress: 'WordPress', woocommerce: 'WooCommerce', shopify: 'Shopify', wix: 'Wix',
}

const kwCount = computed(() =>
  wizard.form.seed_keywords.split('\n').map(s => s.trim()).filter(Boolean).length
)
const compCount = computed(() =>
  wizard.form.competitors.split('\n').map(s => s.trim()).filter(Boolean).length
)
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 class="text-xl font-bold text-foreground">Review & Save</h2>
      <p class="text-muted-foreground mt-1 text-sm">
        Everything looks good? Click "Save Site" to create
        <code class="bg-muted px-1.5 py-0.5 rounded text-xs">config.{{ wizard.form.site_id }}.yaml</code>
        in the project root.
      </p>
    </div>

    <!-- Save error -->
    <div v-if="wizard.saveError" class="mb-5">
      <Alert variant="error">{{ wizard.saveError }}</Alert>
    </div>

    <div class="space-y-4">

      <!-- Site & Platform -->
      <div class="rounded-xl border border-border overflow-hidden">
        <div class="bg-muted/40 px-4 py-2.5 border-b border-border flex items-center gap-2">
          <component :is="platformIcon" class="w-4 h-4 text-primary" />
          <span class="text-sm font-semibold text-foreground">Site & Platform</span>
        </div>
        <div class="p-4 grid grid-cols-2 gap-x-8 gap-y-2.5 text-sm">
          <div class="flex justify-between">
            <span class="text-muted-foreground">Site ID</span>
            <code class="font-mono text-foreground">{{ wizard.form.site_id }}</code>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">Platform</span>
            <span class="font-medium text-foreground">{{ platformLabel[wizard.form.platform] }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">Name</span>
            <span class="text-foreground">{{ wizard.form.site_name }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">Domain</span>
            <span class="text-foreground">{{ wizard.form.domain }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">Language</span>
            <code class="font-mono text-foreground">{{ wizard.form.language }} / {{ wizard.form.country }}</code>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">Google Domain</span>
            <code class="font-mono text-foreground">{{ wizard.form.google_domain }}</code>
          </div>
        </div>
      </div>

      <!-- AI Settings -->
      <div class="rounded-xl border border-border overflow-hidden">
        <div class="bg-muted/40 px-4 py-2.5 border-b border-border flex items-center gap-2">
          <Zap class="w-4 h-4 text-primary" />
          <span class="text-sm font-semibold text-foreground">AI Provider & Settings</span>
        </div>
        <div class="p-4 grid grid-cols-2 gap-x-8 gap-y-2.5 text-sm">
          <div class="flex justify-between">
            <span class="text-muted-foreground">Provider</span>
            <span class="font-medium text-foreground capitalize">{{ wizard.form.ai_provider }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">Model</span>
            <code class="font-mono text-foreground">{{ wizard.form.ai_model }}</code>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">API Key</span>
            <code class="font-mono text-foreground">{{ mask(wizard.form.ai_api_key) }}</code>
          </div>
          <div v-if="wizard.form.ai_image_model" class="flex justify-between">
            <span class="text-muted-foreground">Image Model</span>
            <code class="font-mono text-foreground">{{ wizard.form.ai_image_model }}</code>
          </div>
        </div>
      </div>

      <!-- Credentials summary -->
      <div class="rounded-xl border border-border overflow-hidden">
        <div class="bg-muted/40 px-4 py-2.5 border-b border-border">
          <span class="text-sm font-semibold text-foreground">Platform Credentials</span>
        </div>
        <div class="p-4 grid grid-cols-2 gap-x-8 gap-y-2.5 text-sm">
          <template v-if="wizard.form.platform === 'mongodb'">
            <div class="flex justify-between col-span-2">
              <span class="text-muted-foreground">MongoDB URI</span>
              <code class="font-mono text-foreground">{{ mask(wizard.form.mongodb_uri) }}</code>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">Database</span>
              <code class="font-mono text-foreground">{{ wizard.form.mongodb_database }}</code>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">Collection</span>
              <code class="font-mono text-foreground">{{ wizard.form.mongodb_collection || '—' }}</code>
            </div>
          </template>
          <template v-else-if="wizard.form.platform === 'wordpress'">
            <div class="flex justify-between col-span-2">
              <span class="text-muted-foreground">Site URL</span>
              <span class="text-foreground">{{ wizard.form.wp_site_url }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">Username</span>
              <span class="text-foreground">{{ wizard.form.wp_username }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">App Password</span>
              <code class="font-mono text-foreground">{{ mask(wizard.form.wp_app_password) }}</code>
            </div>
          </template>
          <template v-else-if="wizard.form.platform === 'shopify'">
            <div class="flex justify-between col-span-2">
              <span class="text-muted-foreground">Store Domain</span>
              <span class="text-foreground">{{ wizard.form.shopify_store_domain }}</span>
            </div>
            <div class="flex justify-between col-span-2">
              <span class="text-muted-foreground">API Token</span>
              <code class="font-mono text-foreground">{{ mask(wizard.form.shopify_admin_api_token) }}</code>
            </div>
          </template>
          <template v-else>
            <div class="flex justify-between col-span-2">
              <span class="text-muted-foreground">Credentials</span>
              <span class="text-emerald-600 font-medium">Configured ✓</span>
            </div>
          </template>
        </div>
      </div>

      <!-- GSC + Content summary (compact) -->
      <div class="rounded-xl border border-border overflow-hidden">
        <div class="bg-muted/40 px-4 py-2.5 border-b border-border">
          <span class="text-sm font-semibold text-foreground">Additional Settings</span>
        </div>
        <div class="p-4 grid grid-cols-2 gap-x-8 gap-y-2.5 text-sm">
          <div class="flex justify-between items-center">
            <span class="text-muted-foreground">Search Console</span>
            <span :class="wizard.form.gsc_enabled ? 'text-emerald-600' : 'text-muted-foreground'">
              {{ wizard.form.gsc_enabled ? 'Enabled ✓' : 'Disabled' }}
            </span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">Seed Keywords</span>
            <span class="text-foreground">{{ kwCount || 0 }} added</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">Competitors</span>
            <span class="text-foreground">{{ compCount || 0 }} added</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">Brand Voice</span>
            <span :class="wizard.form.brand_voice ? 'text-emerald-600' : 'text-muted-foreground'">
              {{ wizard.form.brand_voice ? 'Set ✓' : 'Not set' }}
            </span>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>
