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
      <h2 class="text-xl font-bold text-foreground">{{ $t('wizard.review.title') }}</h2>
      <p class="text-muted-foreground mt-1 text-sm">
        {{ $t('wizard.review.subtitle', { file: `config.${wizard.form.site_id}.yaml` }) }}
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
          <span class="text-sm font-semibold text-foreground">{{ $t('wizard.review.sitePlatform') }}</span>
        </div>
        <div class="p-4 grid grid-cols-2 gap-x-8 gap-y-2.5 text-sm">
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.siteId') }}</span>
            <code class="font-mono text-foreground">{{ wizard.form.site_id }}</code>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.platform') }}</span>
            <span class="font-medium text-foreground">{{ platformLabel[wizard.form.platform] }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.name') }}</span>
            <span class="text-foreground">{{ wizard.form.site_name }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.domain') }}</span>
            <span class="text-foreground">{{ wizard.form.domain }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.language') }}</span>
            <code class="font-mono text-foreground">{{ wizard.form.language }} / {{ wizard.form.country }}</code>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.googleDomain') }}</span>
            <code class="font-mono text-foreground">{{ wizard.form.google_domain }}</code>
          </div>
        </div>
      </div>

      <!-- AI Settings -->
      <div class="rounded-xl border border-border overflow-hidden">
        <div class="bg-muted/40 px-4 py-2.5 border-b border-border flex items-center gap-2">
          <Zap class="w-4 h-4 text-primary" />
          <span class="text-sm font-semibold text-foreground">{{ $t('wizard.review.aiSettings') }}</span>
        </div>
        <div class="p-4 grid grid-cols-2 gap-x-8 gap-y-2.5 text-sm">
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.provider') }}</span>
            <span class="font-medium text-foreground capitalize">{{ wizard.form.ai_provider }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.model') }}</span>
            <code class="font-mono text-foreground">{{ wizard.form.ai_model }}</code>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.apiKey') }}</span>
            <code class="font-mono text-foreground">{{ mask(wizard.form.ai_api_key) }}</code>
          </div>
          <div v-if="wizard.form.ai_image_model" class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.imageModel') }}</span>
            <code class="font-mono text-foreground">{{ wizard.form.ai_image_model }}</code>
          </div>
        </div>
      </div>

      <!-- Credentials summary -->
      <div class="rounded-xl border border-border overflow-hidden">
        <div class="bg-muted/40 px-4 py-2.5 border-b border-border">
          <span class="text-sm font-semibold text-foreground">{{ $t('wizard.review.credentialsSection') }}</span>
        </div>
        <div class="p-4 grid grid-cols-2 gap-x-8 gap-y-2.5 text-sm">
          <template v-if="wizard.form.platform === 'mongodb'">
            <div class="flex justify-between col-span-2">
              <span class="text-muted-foreground">{{ $t('wizard.review.mongodbUri') }}</span>
              <code class="font-mono text-foreground">{{ mask(wizard.form.mongodb_uri) }}</code>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">{{ $t('wizard.review.database') }}</span>
              <code class="font-mono text-foreground">{{ wizard.form.mongodb_database }}</code>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">{{ $t('wizard.review.collection') }}</span>
              <code class="font-mono text-foreground">{{ wizard.form.mongodb_collection || '—' }}</code>
            </div>
          </template>
          <template v-else-if="wizard.form.platform === 'wordpress'">
            <div class="flex justify-between col-span-2">
              <span class="text-muted-foreground">{{ $t('wizard.review.siteUrl') }}</span>
              <span class="text-foreground">{{ wizard.form.wp_site_url }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">{{ $t('wizard.review.username') }}</span>
              <span class="text-foreground">{{ wizard.form.wp_username }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">{{ $t('wizard.review.appPassword') }}</span>
              <code class="font-mono text-foreground">{{ mask(wizard.form.wp_app_password) }}</code>
            </div>
          </template>
          <template v-else-if="wizard.form.platform === 'shopify'">
            <div class="flex justify-between col-span-2">
              <span class="text-muted-foreground">{{ $t('wizard.review.storeDomain') }}</span>
              <span class="text-foreground">{{ wizard.form.shopify_store_domain }}</span>
            </div>
            <div class="flex justify-between col-span-2">
              <span class="text-muted-foreground">{{ $t('wizard.review.apiToken') }}</span>
              <code class="font-mono text-foreground">{{ mask(wizard.form.shopify_admin_api_token) }}</code>
            </div>
          </template>
          <template v-else>
            <div class="flex justify-between col-span-2">
              <span class="text-muted-foreground">{{ $t('wizard.review.credentialsSection') }}</span>
              <span class="text-emerald-600 font-medium">{{ $t('wizard.review.configuredOk') }}</span>
            </div>
          </template>
        </div>
      </div>

      <!-- GSC + Content summary (compact) -->
      <div class="rounded-xl border border-border overflow-hidden">
        <div class="bg-muted/40 px-4 py-2.5 border-b border-border">
          <span class="text-sm font-semibold text-foreground">{{ $t('wizard.review.additionalSettings') }}</span>
        </div>
        <div class="p-4 grid grid-cols-2 gap-x-8 gap-y-2.5 text-sm">
          <div class="flex justify-between items-center">
            <span class="text-muted-foreground">{{ $t('wizard.review.searchConsole') }}</span>
            <span :class="wizard.form.gsc_enabled ? 'text-emerald-600' : 'text-muted-foreground'">
              {{ wizard.form.gsc_enabled ? $t('wizard.review.enabled') : $t('wizard.review.disabled') }}
            </span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.seedKeywords') }}</span>
            <span class="text-foreground">{{ $t('wizard.review.added', { n: kwCount || 0 }) }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.competitors') }}</span>
            <span class="text-foreground">{{ $t('wizard.review.added', { n: compCount || 0 }) }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted-foreground">{{ $t('wizard.review.brandVoice') }}</span>
            <span :class="wizard.form.brand_voice ? 'text-emerald-600' : 'text-muted-foreground'">
              {{ wizard.form.brand_voice ? $t('wizard.review.set') : $t('wizard.review.notSet') }}
            </span>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>
