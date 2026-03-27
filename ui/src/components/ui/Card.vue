<script setup lang="ts">
import { cn } from '@/lib/utils'

const props = defineProps<{ class?: string }>()
</script>

<template>
  <div :class="cn('rounded-xl border border-border bg-card text-card-foreground shadow-sm', props.class)">
    <slot />
  </div>
</template>
