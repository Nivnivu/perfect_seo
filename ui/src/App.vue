<script setup lang="ts">
import { watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from './components/AppLayout.vue'
import { applyLocaleToDocument } from './i18n'

const { locale } = useI18n()

// Keep <html dir> and <html lang> in sync whenever locale changes
watchEffect(() => applyLocaleToDocument(locale.value))
</script>

<template>
  <AppLayout />
</template>
