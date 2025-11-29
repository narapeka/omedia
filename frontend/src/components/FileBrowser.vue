<script setup>
import { ref, watch, onMounted } from 'vue'

const props = defineProps({
  path: {
    type: String,
    default: '/'
  },
  storageType: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['update:path', 'browse'])

// State
const items = ref([])
const isLoading = ref(false)
const error = ref(null)
const currentPath = ref(props.path)
const parentPath = ref(null)

// Watch for path changes
watch(() => props.path, (newPath) => {
  currentPath.value = newPath
})

watch(() => props.storageType, () => {
  // Reset to root when storage type changes
  navigateTo('/')
})

// Load initial directory
onMounted(() => {
  loadDirectory(currentPath.value)
})

async function loadDirectory(path) {
  isLoading.value = true
  error.value = null
  
  try {
    const response = await emit('browse', path)
    if (response) {
      items.value = response.items || []
      parentPath.value = response.parent_path
      currentPath.value = response.path
      emit('update:path', response.path)
    }
  } catch (e) {
    error.value = 'Failed to load directory'
    console.error(e)
  } finally {
    isLoading.value = false
  }
}

function navigateTo(path) {
  loadDirectory(path)
}

function selectItem(item) {
  if (item.is_dir) {
    navigateTo(item.path)
  }
}

function goUp() {
  if (parentPath.value) {
    navigateTo(parentPath.value)
  }
}

function getIcon(item) {
  if (item.is_dir) return '📁'
  const ext = item.extension?.toLowerCase()
  if (['.mp4', '.mkv', '.avi', '.mov'].includes(ext)) return '🎬'
  if (['.mp3', '.flac', '.wav'].includes(ext)) return '🎵'
  if (['.jpg', '.png', '.gif'].includes(ext)) return '🖼️'
  return '📄'
}

function formatSize(bytes) {
  if (!bytes) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${bytes.toFixed(1)} ${units[i]}`
}
</script>

<template>
  <div class="space-y-4">
    <!-- Current path -->
    <div class="flex items-center space-x-2">
      <input 
        v-model="currentPath"
        type="text"
        class="input flex-1 font-mono text-sm"
        @keyup.enter="loadDirectory(currentPath)"
      />
      <button @click="loadDirectory(currentPath)" class="btn-secondary">
        Go
      </button>
    </div>
    
    <!-- Breadcrumb -->
    <div class="flex items-center space-x-1 text-sm text-surface-400 overflow-x-auto pb-2">
      <button 
        @click="navigateTo('/')"
        class="hover:text-surface-200 flex-shrink-0"
      >
        Root
      </button>
      <template v-for="(part, index) in currentPath.split('/').filter(Boolean)" :key="index">
        <span>/</span>
        <button 
          @click="navigateTo('/' + currentPath.split('/').filter(Boolean).slice(0, index + 1).join('/'))"
          class="hover:text-surface-200 truncate max-w-[150px]"
        >
          {{ part }}
        </button>
      </template>
    </div>
    
    <!-- Error -->
    <div v-if="error" class="p-3 bg-red-900/30 border border-red-800 rounded text-red-300 text-sm">
      {{ error }}
    </div>
    
    <!-- Loading -->
    <div v-if="isLoading" class="p-8 text-center">
      <div class="animate-spin w-8 h-8 border-3 border-primary-500 border-t-transparent rounded-full mx-auto"></div>
    </div>
    
    <!-- File list -->
    <div v-else class="border border-surface-700 rounded-lg overflow-hidden max-h-80 overflow-y-auto">
      <!-- Go up button -->
      <button
        v-if="parentPath"
        @click="goUp"
        class="w-full flex items-center space-x-3 px-4 py-3 hover:bg-surface-700 transition-colors border-b border-surface-700"
      >
        <span class="text-xl">⬆️</span>
        <span class="text-surface-300">..</span>
      </button>
      
      <!-- Items -->
      <button
        v-for="item in items"
        :key="item.path"
        @click="selectItem(item)"
        class="w-full flex items-center space-x-3 px-4 py-3 hover:bg-surface-700 transition-colors border-b border-surface-700 last:border-b-0"
      >
        <span class="text-xl flex-shrink-0">{{ getIcon(item) }}</span>
        <span class="text-surface-200 truncate flex-1 text-left">{{ item.name }}</span>
        <span v-if="!item.is_dir" class="text-surface-500 text-sm flex-shrink-0">
          {{ formatSize(item.size) }}
        </span>
      </button>
      
      <!-- Empty state -->
      <div v-if="items.length === 0 && !parentPath" class="p-8 text-center text-surface-400">
        This folder is empty
      </div>
    </div>
  </div>
</template>

