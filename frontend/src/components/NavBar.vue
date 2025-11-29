<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const navItems = [
  { path: '/share-import', label: 'Import', icon: 'link' },
  { path: '/organize', label: 'Organize', icon: 'folder' },
  { path: '/jobs', label: 'Jobs', icon: 'clock' },
  { path: '/rules', label: 'Rules', icon: 'filter' },
  { path: '/settings', label: 'Settings', icon: 'cog' },
]

const isActive = (path) => route.path === path
</script>

<template>
  <nav class="bg-surface-900 border-b border-surface-800 sticky top-0 z-50">
    <div class="container mx-auto px-4 max-w-6xl">
      <div class="flex items-center justify-between h-16">
        <!-- Logo -->
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center">
            <span class="text-white font-bold text-lg">O</span>
          </div>
          <span class="text-xl font-semibold text-surface-100 hidden sm:block">OMedia</span>
        </div>
        
        <!-- Desktop Navigation -->
        <div class="hidden md:flex items-center space-x-1">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="[
              isActive(item.path) 
                ? 'bg-primary-600/20 text-primary-400' 
                : 'text-surface-400 hover:text-surface-100 hover:bg-surface-800'
            ]"
          >
            {{ item.label }}
          </router-link>
        </div>
        
        <!-- Status indicator -->
        <div class="flex items-center space-x-2">
          <div class="w-2 h-2 rounded-full bg-success animate-pulse" title="Connected"></div>
          <span class="text-xs text-surface-500 hidden sm:block">Connected</span>
        </div>
      </div>
    </div>
  </nav>
</template>

