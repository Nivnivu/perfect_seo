<script setup lang="ts">
import { ref, computed } from 'vue'
import axios from 'axios'
import { useWizardStore } from '@/stores/wizard'
import Input from '@/components/ui/Input.vue'
import Label from '@/components/ui/Label.vue'
import Alert from '@/components/ui/Alert.vue'
import { Loader2, Zap } from 'lucide-vue-next'

const wizard = useWizardStore()

type TestState = 'idle' | 'loading' | 'success' | 'error'
const testState = ref<TestState>('idle')
const testMessage = ref('')

const needsSupabase = computed(() =>
  wizard.form.platform === 'mongodb' || wizard.form.platform === 'wordpress',
)

function credentialPayload() {
  const f = wizard.form
  if (f.platform === 'mongodb')     return { uri: f.mongodb_uri }
  if (f.platform === 'wordpress')   return { site_url: f.wp_site_url, username: f.wp_username, app_password: f.wp_app_password }
  if (f.platform === 'woocommerce') return { site_url: f.wc_site_url, consumer_key: f.wc_consumer_key, consumer_secret: f.wc_consumer_secret }
  if (f.platform === 'shopify')     return { store_domain: f.shopify_store_domain, admin_api_token: f.shopify_admin_api_token }
  if (f.platform === 'wix')         return { api_key: f.wix_api_key, site_id: f.wix_site_id }
  return {}
}

async function testConnection() {
  testState.value = 'loading'
  testMessage.value = ''
  try {
    const { data } = await axios.post('/api/sites/test-connection', {
      platform: wizard.form.platform,
      credentials: credentialPayload(),
    })
    testState.value = 'success'
    testMessage.value = data.message
  } catch (e: any) {
    testState.value = 'error'
    testMessage.value = e.response?.data?.detail ?? e.message ?? 'Connection failed'
  }
}
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 class="text-xl font-bold text-foreground">Platform Credentials</h2>
      <p class="text-muted-foreground mt-1 text-sm">
        Connect the SEO engine to your {{ wizard.form.platform }} instance.
      </p>
    </div>

    <div class="space-y-6">

      <!-- ── MongoDB ── -->
      <template v-if="wizard.form.platform === 'mongodb'">
        <div class="space-y-4">
          <p class="text-sm font-semibold text-foreground">MongoDB Connection</p>
          <div class="space-y-1.5">
            <Label>MongoDB URI <span class="text-destructive">*</span></Label>
            <Input v-model="wizard.form.mongodb_uri" type="password" placeholder="mongodb+srv://user:pass@cluster.mongodb.net/" class="font-mono" />
            <p class="text-xs text-muted-foreground">Find this in MongoDB Atlas → Connect → Drivers</p>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-1.5">
              <Label>Database</Label>
              <Input v-model="wizard.form.mongodb_database" placeholder="multiBlogDB" class="font-mono" />
            </div>
            <div class="space-y-1.5">
              <Label>Collection <span class="text-destructive">*</span></Label>
              <Input v-model="wizard.form.mongodb_collection" placeholder="mysite_posts" class="font-mono" />
            </div>
          </div>
        </div>
      </template>

      <!-- ── WordPress ── -->
      <template v-else-if="wizard.form.platform === 'wordpress'">
        <div class="space-y-4">
          <p class="text-sm font-semibold text-foreground">WordPress REST API</p>
          <div class="space-y-1.5">
            <Label>Site URL <span class="text-destructive">*</span></Label>
            <Input v-model="wizard.form.wp_site_url" placeholder="https://myblog.com" />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-1.5">
              <Label>Username <span class="text-destructive">*</span></Label>
              <Input v-model="wizard.form.wp_username" placeholder="admin" />
            </div>
            <div class="space-y-1.5">
              <Label>Application Password <span class="text-destructive">*</span></Label>
              <Input v-model="wizard.form.wp_app_password" type="password" placeholder="xxxx xxxx xxxx xxxx" class="font-mono" />
            </div>
          </div>
          <Alert variant="info">
            Generate an application password in WordPress Admin → Users → Edit your profile → Application Passwords.
            Requires WordPress 5.6 or later.
          </Alert>
        </div>
      </template>

      <!-- ── WooCommerce ── -->
      <template v-else-if="wizard.form.platform === 'woocommerce'">
        <div class="space-y-4">
          <p class="text-sm font-semibold text-foreground">WooCommerce REST API</p>
          <div class="space-y-1.5">
            <Label>Site URL <span class="text-destructive">*</span></Label>
            <Input v-model="wizard.form.wc_site_url" placeholder="https://mystore.com" />
          </div>
          <div class="space-y-1.5">
            <Label>Consumer Key <span class="text-destructive">*</span></Label>
            <Input v-model="wizard.form.wc_consumer_key" type="password" placeholder="ck_..." class="font-mono" />
          </div>
          <div class="space-y-1.5">
            <Label>Consumer Secret <span class="text-destructive">*</span></Label>
            <Input v-model="wizard.form.wc_consumer_secret" type="password" placeholder="cs_..." class="font-mono" />
          </div>
          <Alert variant="info">
            Generate keys in WooCommerce → Settings → Advanced → REST API → Add key (Read/Write permissions).
          </Alert>
        </div>
      </template>

      <!-- ── Shopify ── -->
      <template v-else-if="wizard.form.platform === 'shopify'">
        <div class="space-y-4">
          <p class="text-sm font-semibold text-foreground">Shopify Admin API</p>
          <div class="space-y-1.5">
            <Label>Store Domain <span class="text-destructive">*</span></Label>
            <Input v-model="wizard.form.shopify_store_domain" placeholder="mystore.myshopify.com" class="font-mono" />
            <p class="text-xs text-muted-foreground">Use your .myshopify.com domain</p>
          </div>
          <div class="space-y-1.5">
            <Label>Admin API Access Token <span class="text-destructive">*</span></Label>
            <Input v-model="wizard.form.shopify_admin_api_token" type="password" placeholder="shpat_..." class="font-mono" />
          </div>
          <Alert variant="info">
            Create a custom app in Shopify Admin → Apps → Develop apps. Enable write access for Articles and Products.
          </Alert>
        </div>
      </template>

      <!-- ── Wix ── -->
      <template v-else-if="wizard.form.platform === 'wix'">
        <div class="space-y-4">
          <p class="text-sm font-semibold text-foreground">Wix Headless API</p>
          <div class="space-y-1.5">
            <Label>API Key <span class="text-destructive">*</span></Label>
            <Input v-model="wizard.form.wix_api_key" type="password" placeholder="IST...." class="font-mono" />
          </div>
          <div class="space-y-1.5">
            <Label>Site ID <span class="text-destructive">*</span></Label>
            <Input v-model="wizard.form.wix_site_id" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" class="font-mono" />
            <p class="text-xs text-muted-foreground">Found in your Wix dashboard URL: manage.wix.com/dashboard/<strong>SITE-ID</strong>/home</p>
          </div>
          <Alert variant="warning">
            Wix connection will be verified on the first pipeline run. API key must have Blog and Stores permissions.
          </Alert>
        </div>
      </template>

      <!-- ── Supabase (MongoDB + WordPress) ── -->
      <template v-if="needsSupabase">
        <div class="border-t border-border pt-5 space-y-4">
          <div>
            <p class="text-sm font-semibold text-foreground">Image Storage (Supabase)</p>
            <p class="text-xs text-muted-foreground mt-0.5">Generated images are stored in Supabase Storage.</p>
          </div>
          <div class="space-y-1.5">
            <Label>Supabase URL</Label>
            <Input v-model="wizard.form.supabase_url" placeholder="https://xxxx.supabase.co" class="font-mono" />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-1.5">
              <Label>Supabase Anon Key</Label>
              <Input v-model="wizard.form.supabase_key" type="password" placeholder="eyJ..." class="font-mono" />
            </div>
            <div class="space-y-1.5">
              <Label>Bucket Name</Label>
              <Input v-model="wizard.form.supabase_bucket" placeholder="blog-poster" class="font-mono" />
            </div>
          </div>
        </div>
      </template>

      <!-- ── Test Connection ── -->
      <div class="border-t border-border pt-5">
        <div class="flex items-center gap-3">
          <button
            type="button"
            @click="testConnection"
            :disabled="testState === 'loading'"
            class="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
          >
            <Loader2 v-if="testState === 'loading'" class="w-4 h-4 animate-spin" />
            <Zap v-else class="w-4 h-4 text-primary" />
            {{ testState === 'loading' ? 'Testing...' : 'Test Connection' }}
          </button>
          <span v-if="testState === 'idle'" class="text-xs text-muted-foreground">
            Verify your credentials before saving
          </span>
        </div>

        <div v-if="testState === 'success'" class="mt-3">
          <Alert variant="success">{{ testMessage }}</Alert>
        </div>
        <div v-else-if="testState === 'error'" class="mt-3">
          <Alert variant="error">{{ testMessage }}</Alert>
        </div>
      </div>

    </div>
  </div>
</template>
