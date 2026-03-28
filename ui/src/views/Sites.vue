<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Globe, Trash2, RefreshCw, FileText, AlertCircle, CheckCircle2, Info, Plus, Pencil } from 'lucide-vue-next'
import { useSitesStore } from '@/stores/sites'
import { useWizardStore } from '@/stores/wizard'
import Card from '@/components/ui/Card.vue'
import Badge from '@/components/ui/Badge.vue'
import AddSiteWizard from '@/components/AddSiteWizard.vue'
import EditSiteDrawer from '@/components/EditSiteDrawer.vue'

const store = useSitesStore()
const wizard = useWizardStore()
const { t } = useI18n()
onMounted(() => store.fetchSites())

const deleting = ref<string | null>(null)
const editingSiteId = ref<string | null>(null)
const toast = ref<{ msg: string; type: 'success' | 'error' } | null>(null)

function showToast(msg: string, type: 'success' | 'error') {
  toast.value = { msg, type }
  setTimeout(() => (toast.value = null), 3000)
}

async function handleDelete(id: string, name: string) {
  if (!confirm(t('sites.removeConfirm', { name, id }))) return
  deleting.value = id
  try {
    await store.deleteSite(id)
    showToast(t('sites.removeSuccess', { name }), 'success')
  } catch {
    showToast(t('sites.removeFailed'), 'error')
  } finally {
    deleting.value = null
  }
}

const platformLabel: Record<string, string> = {
  mongodb: 'MongoDB', wordpress: 'WordPress', woocommerce: 'WooCommerce',
  shopify: 'Shopify', wix: 'Wix',
}

const platformBadge = (p: string): any => {
  const map: Record<string, string> = {
    mongodb: 'success', wordpress: 'default', woocommerce: 'warning', shopify: 'secondary', wix: 'outline',
  }
  return map[p] ?? 'secondary'
}
</script>

<template>
  <div class="p-8 max-w-5xl">
    <!-- Header -->
    <div class="flex items-start justify-between mb-8">
      <div>
        <h1 class="text-2xl font-bold text-foreground">{{ $t('sites.title') }}</h1>
        <p class="text-muted-foreground mt-1">{{ $t('sites.subtitle') }}</p>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="store.fetchSites()"
          :disabled="store.loading"
          class="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground border border-border rounded-lg px-3 py-2 transition-colors disabled:opacity-50"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="store.loading ? 'animate-spin' : ''" />
          {{ $t('sites.refresh') }}
        </button>
        <button
          @click="wizard.open()"
          class="flex items-center gap-2 text-sm font-semibold bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary/90 transition-colors shadow-sm"
        >
          <Plus class="w-4 h-4" />
          {{ $t('sites.addSite') }}
        </button>
      </div>
    </div>

    <!-- Toast — uses end-4 so it flips correctly in RTL -->
    <div
      v-if="toast"
      class="fixed top-4 end-4 z-40 flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-medium shadow-lg"
      :class="toast.type === 'success'
        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
        : 'bg-red-50 text-red-800 border border-red-200'"
    >
      <CheckCircle2 v-if="toast.type === 'success'" class="w-4 h-4" />
      <AlertCircle v-else class="w-4 h-4" />
      {{ toast.msg }}
    </div>

    <!-- Error -->
    <div v-if="store.error" class="flex items-center gap-2 text-destructive bg-destructive/10 px-4 py-3 rounded-lg mb-6">
      <AlertCircle class="w-4 h-4" />{{ store.error }}
    </div>

    <!-- Info box -->
    <div class="flex items-start gap-3 bg-primary/5 border border-primary/20 rounded-xl p-4 mb-6">
      <Info class="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
      <div class="text-sm text-foreground/80">
        {{ $t('sites.infoBoxBefore') }}
        <code class="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">config.mysite.yaml</code>
        {{ $t('sites.infoBoxMiddle') }}
        <strong>{{ $t('sites.addSite') }}</strong>
        {{ $t('sites.infoBoxAfter') }}
        <code class="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">config.example.yaml</code>
        {{ $t('sites.infoBoxManual') }}
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading && store.sites.length === 0" class="flex items-center gap-2 text-muted-foreground py-8">
      <div class="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      {{ $t('sites.loading') }}
    </div>

    <!-- Empty -->
    <div v-else-if="store.sites.length === 0" class="text-center py-16">
      <div class="w-14 h-14 rounded-xl bg-muted flex items-center justify-center mx-auto mb-4">
        <Globe class="w-6 h-6 text-muted-foreground/40" />
      </div>
      <p class="text-muted-foreground text-sm mb-5">{{ $t('sites.emptyDesc') }}</p>
      <button
        @click="wizard.open()"
        class="inline-flex items-center gap-2 bg-primary text-white px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-primary/90 transition-colors shadow-sm"
      >
        <Plus class="w-4 h-4" /> {{ $t('sites.addFirstSite') }}
      </button>
    </div>

    <!-- Sites list -->
    <div v-else class="space-y-3">
      <Card
        v-for="site in store.sites"
        :key="site.id"
        class="p-4 flex items-center justify-between gap-4 hover:shadow-sm transition-shadow"
      >
        <!-- Left: icon + info -->
        <div class="flex items-center gap-4 min-w-0">
          <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
            <Globe class="w-5 h-5 text-primary" />
          </div>
          <div class="min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-semibold text-foreground text-sm">{{ site.name }}</span>
              <Badge :variant="platformBadge(site.platform)">
                {{ platformLabel[site.platform] ?? site.platform }}
              </Badge>
              <Badge v-if="site.has_gsc" variant="success">GSC</Badge>
            </div>
            <div class="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
              <span>{{ site.domain }}</span>
              <span class="text-border">·</span>
              <span class="font-mono flex items-center gap-1">
                <FileText class="w-3 h-3" />{{ site.file }}
              </span>
              <span class="text-border">·</span>
              <span>{{ site.language.toUpperCase() }}</span>
            </div>
          </div>
        </div>

        <!-- Right: actions -->
        <div class="flex items-center gap-1 flex-shrink-0">
          <button
            @click="editingSiteId = site.id"
            class="p-2 rounded-lg text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
            :title="$t('sites.editSite')"
          >
            <Pencil class="w-4 h-4" />
          </button>
          <button
            @click="handleDelete(site.id, site.name)"
            :disabled="deleting === site.id"
            class="p-2 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-40"
            :title="$t('sites.removeSite')"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </div>
      </Card>
    </div>
  </div>

  <!-- Wizard modal (teleported to body) -->
  <AddSiteWizard />

  <!-- Edit site drawer (teleported to body) -->
  <EditSiteDrawer
    :site-id="editingSiteId"
    @close="editingSiteId = null"
    @saved="editingSiteId = null; store.fetchSites(); showToast($t('sites.saveSuccess'), 'success')"
  />
</template>
