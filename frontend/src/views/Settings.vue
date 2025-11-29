<script setup>
import { ref, onMounted } from 'vue'
import { configApi } from '@/api'

// State
const config = ref(null)
const status = ref(null)
const isLoading = ref(false)
const error = ref(null)

// Load config
onMounted(async () => {
  await loadConfig()
  await loadStatus()
})

async function loadConfig() {
  isLoading.value = true
  try {
    config.value = await configApi.get()
  } catch (e) {
    error.value = 'Failed to load configuration'
    console.error(e)
  } finally {
    isLoading.value = false
  }
}

async function loadStatus() {
  try {
    status.value = await configApi.getStatus()
  } catch (e) {
    console.error('Failed to load status:', e)
  }
}

function getStatusIndicator(service) {
  if (!status.value) return { color: 'bg-surface-500', text: 'Unknown' }
  
  const state = status.value[service]
  switch (state) {
    case 'configured':
      return { color: 'bg-success', text: 'Configured' }
    case 'unconfigured':
      return { color: 'bg-warning', text: 'Not Configured' }
    case 'error':
      return { color: 'bg-error', text: 'Error' }
    default:
      return { color: 'bg-surface-500', text: state || 'Unknown' }
  }
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-surface-100">Settings</h1>
      <p class="text-surface-400 mt-1">Configure OMedia application settings</p>
    </div>
    
    <!-- Error Message -->
    <div v-if="error" class="p-4 bg-red-900/30 border border-red-800 rounded-lg text-red-300">
      {{ error }}
    </div>
    
    <!-- Loading State -->
    <div v-if="isLoading" class="card p-12 text-center">
      <div class="animate-spin w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full mx-auto mb-4"></div>
      <p class="text-surface-400">Loading settings...</p>
    </div>
    
    <template v-else-if="config">
      <!-- Status Overview -->
      <div class="card p-6">
        <h2 class="text-lg font-semibold text-surface-100 mb-4">Service Status</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="p-4 bg-surface-700 rounded-lg">
            <div class="flex items-center space-x-2 mb-2">
              <div :class="['w-3 h-3 rounded-full', getStatusIndicator('app').color]"></div>
              <span class="text-surface-300">Application</span>
            </div>
            <p class="text-surface-100 font-medium">{{ getStatusIndicator('app').text }}</p>
          </div>
          
          <div class="p-4 bg-surface-700 rounded-lg">
            <div class="flex items-center space-x-2 mb-2">
              <div :class="['w-3 h-3 rounded-full', getStatusIndicator('llm').color]"></div>
              <span class="text-surface-300">LLM</span>
            </div>
            <p class="text-surface-100 font-medium">{{ getStatusIndicator('llm').text }}</p>
          </div>
          
          <div class="p-4 bg-surface-700 rounded-lg">
            <div class="flex items-center space-x-2 mb-2">
              <div :class="['w-3 h-3 rounded-full', getStatusIndicator('tmdb').color]"></div>
              <span class="text-surface-300">TMDB</span>
            </div>
            <p class="text-surface-100 font-medium">{{ getStatusIndicator('tmdb').text }}</p>
          </div>
          
          <div class="p-4 bg-surface-700 rounded-lg">
            <div class="flex items-center space-x-2 mb-2">
              <div :class="['w-3 h-3 rounded-full', getStatusIndicator('p115').color]"></div>
              <span class="text-surface-300">115 Cloud</span>
            </div>
            <p class="text-surface-100 font-medium">{{ getStatusIndicator('p115').text }}</p>
          </div>
        </div>
      </div>
      
      <!-- LLM Settings -->
      <div class="card p-6">
        <h2 class="text-lg font-semibold text-surface-100 mb-4">LLM Configuration</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm text-surface-400 mb-1">API Key</label>
            <p class="text-surface-200">{{ config.llm.has_api_key ? '••••••••••••' : 'Not configured' }}</p>
          </div>
          <div>
            <label class="block text-sm text-surface-400 mb-1">Model</label>
            <p class="text-surface-200">{{ config.llm.model }}</p>
          </div>
          <div>
            <label class="block text-sm text-surface-400 mb-1">Base URL</label>
            <p class="text-surface-200">{{ config.llm.base_url || 'Default (OpenAI)' }}</p>
          </div>
          <div>
            <label class="block text-sm text-surface-400 mb-1">Rate Limit</label>
            <p class="text-surface-200">{{ config.llm.rate_limit }} req/sec</p>
          </div>
        </div>
        <p class="text-surface-500 text-sm mt-4">
          Configure via environment variables: LLM_API_KEY, LLM_MODEL, LLM_BASE_URL
        </p>
      </div>
      
      <!-- TMDB Settings -->
      <div class="card p-6">
        <h2 class="text-lg font-semibold text-surface-100 mb-4">TMDB Configuration</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm text-surface-400 mb-1">API Key</label>
            <p class="text-surface-200">{{ config.tmdb.has_api_key ? '••••••••••••' : 'Not configured' }}</p>
          </div>
          <div>
            <label class="block text-sm text-surface-400 mb-1">Languages</label>
            <p class="text-surface-200">{{ config.tmdb.languages.join(', ') }}</p>
          </div>
        </div>
        <p class="text-surface-500 text-sm mt-4">
          Configure via environment variables: TMDB_API_KEY
        </p>
      </div>
      
      <!-- 115 Cloud Settings -->
      <div class="card p-6">
        <h2 class="text-lg font-semibold text-surface-100 mb-4">115 Cloud Configuration</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm text-surface-400 mb-1">Cookies</label>
            <p class="text-surface-200">{{ config.p115.has_cookies ? 'Configured' : 'Not configured' }}</p>
          </div>
          <div>
            <label class="block text-sm text-surface-400 mb-1">Share Receive Paths</label>
            <div v-if="config.p115.share_receive_paths.length > 0" class="space-y-1">
              <p 
                v-for="path in config.p115.share_receive_paths" 
                :key="path"
                class="text-surface-200 font-mono text-sm"
              >
                {{ path }}
              </p>
            </div>
            <p v-else class="text-surface-500">No paths configured</p>
          </div>
        </div>
        <p class="text-surface-500 text-sm mt-4">
          Configure via environment variables: P115_COOKIES, P115_SHARE_RECEIVE_PATHS
        </p>
      </div>
      
      <!-- Storage Settings -->
      <div class="card p-6">
        <h2 class="text-lg font-semibold text-surface-100 mb-4">Storage Configuration</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm text-surface-400 mb-1">Local Media Paths</label>
            <div v-if="config.storage.local_media_paths.length > 0" class="space-y-1">
              <p 
                v-for="path in config.storage.local_media_paths" 
                :key="path"
                class="text-surface-200 font-mono text-sm"
              >
                {{ path }}
              </p>
            </div>
            <p v-else class="text-surface-500">No paths configured</p>
          </div>
          <div>
            <label class="block text-sm text-surface-400 mb-1">WebDAV</label>
            <p class="text-surface-200">{{ config.storage.has_webdav ? 'Configured' : 'Not configured' }}</p>
          </div>
        </div>
      </div>
      
      <!-- About -->
      <div class="card p-6">
        <h2 class="text-lg font-semibold text-surface-100 mb-4">About</h2>
        <div class="space-y-2">
          <p class="text-surface-300">
            <span class="text-surface-500">Application:</span> {{ config.app_name }}
          </p>
          <p class="text-surface-300">
            <span class="text-surface-500">Version:</span> 0.1.0
          </p>
          <p class="text-surface-300">
            <span class="text-surface-500">Debug Mode:</span> {{ config.debug ? 'Enabled' : 'Disabled' }}
          </p>
        </div>
      </div>
    </template>
  </div>
</template>

