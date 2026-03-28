<script setup lang="ts">
import { useWizardStore } from '@/stores/wizard'
import Input from '@/components/ui/Input.vue'
import Label from '@/components/ui/Label.vue'
import Alert from '@/components/ui/Alert.vue'

const wizard = useWizardStore()
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 class="text-xl font-bold text-foreground">{{ $t('wizard.gsc.title') }}</h2>
      <p class="text-muted-foreground mt-1 text-sm">{{ $t('wizard.gsc.subtitle') }}</p>
    </div>

    <!-- Enable toggle -->
    <label class="flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all mb-5"
      :class="wizard.form.gsc_enabled ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/30'"
    >
      <input type="checkbox" v-model="wizard.form.gsc_enabled" class="w-4 h-4 accent-primary rounded" />
      <div>
        <p class="font-semibold text-sm text-foreground">{{ $t('wizard.gsc.enableLabel') }}</p>
        <p class="text-xs text-muted-foreground mt-0.5">{{ $t('wizard.gsc.enableSubtitle') }}</p>
      </div>
    </label>

    <div v-if="wizard.form.gsc_enabled" class="space-y-5">

      <!-- OAuth credentials file -->
      <div class="space-y-1.5">
        <Label>{{ $t('wizard.gsc.credentialsFile') }} <span class="text-destructive">*</span></Label>
        <Input
          v-model="wizard.form.gsc_credentials_file"
          placeholder="client_secret_xxxx.apps.googleusercontent.com.json"
          class="font-mono text-xs"
        />
        <p class="text-xs text-muted-foreground">{{ $t('wizard.gsc.credentialsHint') }}</p>
      </div>

      <!-- GSC Site URL -->
      <div class="space-y-1.5">
        <Label>{{ $t('wizard.gsc.gscSiteUrl') }}</Label>
        <Input
          v-model="wizard.form.gsc_site_url"
          :placeholder="`https://${wizard.form.domain || 'yoursite.com'}/`"
          class="font-mono"
        />
        <p class="text-xs text-muted-foreground">{{ $t('wizard.gsc.gscSiteUrlHint') }}</p>
      </div>

      <!-- Protection thresholds -->
      <div class="border-t border-border pt-4">
        <p class="text-sm font-semibold text-foreground mb-3">{{ $t('wizard.gsc.thresholdsTitle') }}</p>
        <p class="text-xs text-muted-foreground mb-4">{{ $t('wizard.gsc.thresholdsHint') }}</p>
        <div class="grid grid-cols-3 gap-4">
          <div class="space-y-1.5">
            <Label>{{ $t('wizard.gsc.minClicks') }}</Label>
            <Input v-model.number="wizard.form.gsc_min_clicks" type="number" min="0" placeholder="10" />
          </div>
          <div class="space-y-1.5">
            <Label>{{ $t('wizard.gsc.minImpressions') }}</Label>
            <Input v-model.number="wizard.form.gsc_min_impressions" type="number" min="0" placeholder="100" />
          </div>
          <div class="space-y-1.5">
            <Label>{{ $t('wizard.gsc.maxPosition') }}</Label>
            <Input v-model.number="wizard.form.gsc_max_position" type="number" min="1" max="100" step="0.5" placeholder="20" />
          </div>
        </div>
      </div>

      <!-- Setup guide -->
      <Alert variant="info" :title="$t('wizard.gsc.setupTitle')">
        1. Go to <strong>Google Cloud Console</strong> → APIs &amp; Services → Credentials<br />
        2. Create an <strong>OAuth 2.0 Client ID</strong> (Desktop application)<br />
        3. Download the JSON file and place it in the project root<br />
        4. Enable the <strong>Google Search Console API</strong> in the API library<br />
        5. On first run, a browser window opens for you to authorize access
      </Alert>

    </div>

    <div v-else class="text-center py-10">
      <p class="text-muted-foreground text-sm">{{ $t('wizard.gsc.laterNote') }}</p>
    </div>
  </div>
</template>
