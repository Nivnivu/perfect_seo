<script setup lang="ts">
import { useWizardStore } from '@/stores/wizard'
import { Database, Globe, ShoppingCart, Store, Layout, Check } from 'lucide-vue-next'

const wizard = useWizardStore()

const platforms = [
  { id: 'wordpress',   label: 'WordPress',            icon: Globe,        color: 'text-blue-600',    bg: 'bg-blue-50',    badge: null },
  { id: 'woocommerce', label: 'WooCommerce',           icon: ShoppingCart, color: 'text-purple-600',  bg: 'bg-purple-50',  badge: null },
  { id: 'shopify',     label: 'Shopify',               icon: Store,        color: 'text-green-600',   bg: 'bg-green-50',   badge: null },
  { id: 'wix',         label: 'Wix',                   icon: Layout,       color: 'text-amber-600',   bg: 'bg-amber-50',   badge: null },
  { id: 'mongodb',     label: 'MongoDB (blog-poster)', icon: Database,     color: 'text-emerald-600', bg: 'bg-emerald-50', badge: 'openSource' },
] as const
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 class="text-xl font-bold text-foreground">{{ $t('wizard.platform.title') }}</h2>
      <p class="text-muted-foreground mt-1 text-sm">{{ $t('wizard.platform.subtitle') }}</p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <button
        v-for="p in platforms"
        :key="p.id"
        type="button"
        @click="wizard.form.platform = p.id"
        class="relative flex items-start gap-4 p-4 rounded-xl border-2 text-start transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        :class="wizard.form.platform === p.id
          ? 'border-primary bg-primary/5 shadow-sm'
          : 'border-border hover:border-primary/30 hover:bg-muted/40'"
      >
        <!-- Selected checkmark — uses end-3 so it flips in RTL -->
        <div
          v-if="wizard.form.platform === p.id"
          class="absolute top-3 end-3 w-5 h-5 rounded-full bg-primary flex items-center justify-center"
        >
          <Check class="w-3 h-3 text-white" />
        </div>

        <!-- Icon -->
        <div
          class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
          :class="wizard.form.platform === p.id ? 'bg-primary/10' : p.bg"
        >
          <component
            :is="p.icon"
            class="w-5 h-5"
            :class="wizard.form.platform === p.id ? 'text-primary' : p.color"
          />
        </div>

        <!-- Text -->
        <div class="min-w-0 flex-1 pe-4">
          <div class="flex items-center gap-2 mb-0.5">
            <span class="font-semibold text-sm text-foreground">{{ p.label }}</span>
            <span
              v-if="p.badge"
              class="text-xs bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full font-medium"
            >{{ $t('wizard.platform.openSource') }}</span>
          </div>
          <p class="text-xs text-muted-foreground leading-relaxed">{{ $t(`wizard.platform.desc.${p.id}`) }}</p>
        </div>
      </button>
    </div>

    <div class="mt-5 p-3 bg-muted/50 rounded-lg border border-border">
      <p class="text-xs text-muted-foreground">{{ $t('wizard.platform.allSupported') }}</p>
    </div>
  </div>
</template>
