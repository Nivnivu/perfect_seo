<script setup lang="ts">
import { computed } from 'vue'
import { CheckCircle2, XCircle, AlertTriangle, Info } from 'lucide-vue-next'
import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const alertVariants = cva('flex items-start gap-3 rounded-lg px-4 py-3 text-sm border', {
  variants: {
    variant: {
      success: 'bg-emerald-50 text-emerald-800 border-emerald-200',
      error:   'bg-red-50 text-red-800 border-red-200',
      warning: 'bg-amber-50 text-amber-800 border-amber-200',
      info:    'bg-primary/5 text-foreground/80 border-primary/20',
    },
  },
  defaultVariants: { variant: 'info' },
})

type Variant = 'success' | 'error' | 'warning' | 'info'

const iconMap: Record<Variant, any> = {
  success: CheckCircle2,
  error:   XCircle,
  warning: AlertTriangle,
  info:    Info,
}

const props = defineProps<{
  variant?: Variant
  title?: string
  class?: string
}>()

const v = computed(() => props.variant ?? 'info')
</script>

<template>
  <div :class="cn(alertVariants({ variant: v }), props.class)">
    <component :is="iconMap[v]" class="w-4 h-4 flex-shrink-0 mt-0.5" />
    <div class="flex-1 min-w-0">
      <p v-if="title" class="font-semibold mb-0.5">{{ title }}</p>
      <slot />
    </div>
  </div>
</template>
