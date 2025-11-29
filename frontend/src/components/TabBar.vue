<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
  { path: '/share-import', label: 'Import', icon: 'link' },
  { path: '/organize', label: 'Organize', icon: 'folder' },
  { path: '/jobs', label: 'Jobs', icon: 'clock' },
  { path: '/settings', label: 'Settings', icon: 'cog' },
]

const isActive = (path) => route.path === path
</script>

<template>
  <nav class="fixed bottom-0 left-0 right-0 bg-surface-900 border-t border-surface-800 safe-bottom">
    <div class="flex items-center justify-around h-16">
      <router-link
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="flex flex-col items-center justify-center w-full h-full transition-colors"
        :class="[
          isActive(tab.path) 
            ? 'text-primary-400' 
            : 'text-surface-500'
        ]"
      >
        <!-- Icon placeholder - replace with actual icons -->
        <div 
          class="w-6 h-6 mb-1 rounded flex items-center justify-center"
          :class="isActive(tab.path) ? 'bg-primary-600/20' : ''"
        >
          <span class="text-xs">{{ tab.icon.charAt(0).toUpperCase() }}</span>
        </div>
        <span class="text-xs font-medium">{{ tab.label }}</span>
      </router-link>
    </div>
  </nav>
</template>

<style scoped>
.safe-bottom {
  padding-bottom: env(safe-area-inset-bottom);
}
</style>

