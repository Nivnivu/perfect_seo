<script setup lang="ts">
import { useWizardStore } from '@/stores/wizard'
import { Database, Globe, ShoppingCart, Store, Layout, Check } from 'lucide-vue-next'

const wizard = useWizardStore()

const platforms = [
  {
    id: 'mongodb',
    label: 'MongoDB',
    icon: Database,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    desc: 'Store posts in MongoDB + Supabase for images. Default setup used by the original engine.',
    badge: 'Default',
  },
  {
    id: 'wordpress',
    label: 'WordPress',
    icon: Globe,
    color: 'text-blue-600',
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    desc: 'Publish via WordPress REST API. Uses application passwords — no OAuth needed.',
    badge: null,
  },
  {
    id: 'woocommerce',
    label: 'WooCommerce',
    icon: ShoppingCart,
    color: 'text-purple-600',
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    desc: 'Optimize WooCommerce product pages using the WooCommerce REST API.',
    badge: null,
  },
  {
    id: 'shopify',
    label: 'Shopify',
    icon: Store,
    color: 'text-green-600',
    bg: 'bg-green-50',
    border: 'border-green-200',
    desc: 'Publish to Shopify blog and optimize product descriptions via Admin API.',
    badge: null,
  },
  {
    id: 'wix',
    label: 'Wix',
    icon: Layout,
    color: 'text-amber-600',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    desc: 'Publish to Wix blog and stores using the Wix Headless CMS API.',
    badge: null,
  },
] as const
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 class="text-xl font-bold text-foreground">Choose Your Platform</h2>
      <p class="text-muted-foreground mt-1 text-sm">
        Select where your content will be published. You can change this later by editing the config file.
      </p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <button
        v-for="p in platforms"
        :key="p.id"
        type="button"
        @click="wizard.form.platform = p.id"
        class="relative flex items-start gap-4 p-4 rounded-xl border-2 text-left transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        :class="wizard.form.platform === p.id
          ? 'border-primary bg-primary/5 shadow-sm'
          : 'border-border hover:border-primary/30 hover:bg-muted/40'"
      >
        <!-- Selected checkmark -->
        <div
          v-if="wizard.form.platform === p.id"
          class="absolute top-3 right-3 w-5 h-5 rounded-full bg-primary flex items-center justify-center"
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
        <div class="min-w-0 flex-1 pr-4">
          <div class="flex items-center gap-2 mb-0.5">
            <span class="font-semibold text-sm text-foreground">{{ p.label }}</span>
            <span
              v-if="p.badge"
              class="text-xs bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full font-medium"
            >{{ p.badge }}</span>
          </div>
          <p class="text-xs text-muted-foreground leading-relaxed">{{ p.desc }}</p>
        </div>
      </button>
    </div>

    <!-- Info note -->
    <div class="mt-5 p-3 bg-muted/50 rounded-lg border border-border">
      <p class="text-xs text-muted-foreground">
        <strong class="text-foreground">Note:</strong>
        WordPress, WooCommerce, Shopify, and Wix publishers are coming in Phase 4.
        For now, choose <strong class="text-foreground">MongoDB</strong> to use the existing engine as-is.
      </p>
    </div>
  </div>
</template>
