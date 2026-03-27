<script setup lang="ts">
import AppSidebar from './AppSidebar.vue'
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-background">
    <AppSidebar />
    <main class="flex-1 overflow-y-auto min-w-0">
      <RouterView />
    </main>
  </div>
</template>
