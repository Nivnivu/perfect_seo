<script setup lang="ts">
import { cn } from '@/lib/utils'

const props = defineProps<{
  class?: string
  placeholder?: string
  modelValue?: string
  rows?: number
  disabled?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <textarea
    v-bind="$attrs"
    :placeholder="placeholder"
    :value="modelValue"
    :rows="rows ?? 3"
    :disabled="disabled"
    :class="cn(
      'flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm ring-offset-background',
      'placeholder:text-muted-foreground resize-none',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
      'disabled:cursor-not-allowed disabled:opacity-50',
      props.class
    )"
    @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
  />
</template>
