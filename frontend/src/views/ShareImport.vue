<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useAppStore } from '@/stores/app'
import { shareApi } from '@/api'
import { useClipboard } from '@/composables/useClipboard'
import MediaPreview from '@/components/MediaPreview.vue'

const appStore = useAppStore()
const { readClipboard, isShareLink } = useClipboard()

// State
const shareUrl = ref('')
const isLoading = ref(false)
const error = ref(null)
const shareInfo = ref(null)
const selectedFiles = ref([])
const targetPath = ref('')
const receivePaths = ref([])

// Computed
const canSave = computed(() => {
  return shareInfo.value && targetPath.value && (
    shareInfo.value.is_single_media || selectedFiles.value.length > 0
  )
})

// Watch for pending share link from clipboard
watch(() => appStore.pendingShareLink, async (link) => {
  if (link) {
    shareUrl.value = link
    appStore.clearPendingShareLink()
    await parseShareLink()
  }
})

// Load receive paths
onMounted(async () => {
  try {
    const response = await shareApi.getReceivePaths()
    receivePaths.value = response.paths || []
    if (receivePaths.value.length > 0) {
      targetPath.value = receivePaths.value[0]
    }
  } catch (e) {
    console.error('Failed to load receive paths:', e)
  }
  
  // Check clipboard on mount
  const clipboardText = await readClipboard()
  if (isShareLink(clipboardText) && !shareUrl.value) {
    shareUrl.value = clipboardText
  }
})

// Methods
async function parseShareLink() {
  if (!shareUrl.value) return
  
  isLoading.value = true
  error.value = null
  shareInfo.value = null
  selectedFiles.value = []
  
  try {
    const response = await shareApi.parseShareLink(shareUrl.value)
    shareInfo.value = response
    
    // Select all files by default for multi-media shares
    if (!response.is_single_media) {
      selectedFiles.value = response.files.filter(f => !f.is_dir).map(f => f.file_id)
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to parse share link'
    console.error('Parse error:', e)
  } finally {
    isLoading.value = false
  }
}

async function saveFiles() {
  if (!canSave.value) return
  
  isLoading.value = true
  error.value = null
  
  try {
    const fileIds = shareInfo.value.is_single_media ? null : selectedFiles.value
    
    await shareApi.saveShareFiles(
      shareInfo.value.share_code,
      shareInfo.value.receive_code,
      targetPath.value,
      fileIds
    )
    
    appStore.addNotification({
      type: 'success',
      message: 'Files saved successfully!'
    })
    
    // Reset form
    shareUrl.value = ''
    shareInfo.value = null
    selectedFiles.value = []
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to save files'
    console.error('Save error:', e)
  } finally {
    isLoading.value = false
  }
}

function toggleFileSelection(fileId) {
  const index = selectedFiles.value.indexOf(fileId)
  if (index === -1) {
    selectedFiles.value.push(fileId)
  } else {
    selectedFiles.value.splice(index, 1)
  }
}

function selectAll() {
  selectedFiles.value = shareInfo.value.files.filter(f => !f.is_dir).map(f => f.file_id)
}

function deselectAll() {
  selectedFiles.value = []
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-surface-100">Import Share Link</h1>
      <p class="text-surface-400 mt-1">Paste a 115 share link to save files to your cloud storage</p>
    </div>
    
    <!-- Input Section -->
    <div class="card p-6 space-y-4">
      <div>
        <label class="block text-sm font-medium text-surface-300 mb-2">
          Share Link
        </label>
        <div class="flex gap-3">
          <input
            v-model="shareUrl"
            type="text"
            placeholder="https://115.com/s/... or 115://share|..."
            class="input flex-1"
            @keyup.enter="parseShareLink"
          />
          <button
            @click="parseShareLink"
            :disabled="!shareUrl || isLoading"
            class="btn-primary whitespace-nowrap"
          >
            {{ isLoading ? 'Loading...' : 'Parse Link' }}
          </button>
        </div>
      </div>
      
      <!-- Error Message -->
      <div v-if="error" class="p-4 bg-red-900/30 border border-red-800 rounded-lg text-red-300">
        {{ error }}
      </div>
    </div>
    
    <!-- Results Section -->
    <div v-if="shareInfo" class="space-y-6">
      <!-- Single Media Preview -->
      <div v-if="shareInfo.is_single_media" class="card p-6">
        <h2 class="text-lg font-semibold text-surface-100 mb-4">Single Media Detected</h2>
        <MediaPreview 
          v-if="shareInfo.files.length > 0"
          :file="shareInfo.files[0]"
          :mediaType="shareInfo.detected_media_type"
        />
        <p class="text-surface-400 mt-4">
          This share appears to contain a single movie or TV show.
          You can save it directly and organize later.
        </p>
      </div>
      
      <!-- Multiple Files List -->
      <div v-else class="card p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-surface-100">
            Files ({{ shareInfo.files.length }})
          </h2>
          <div class="space-x-2">
            <button @click="selectAll" class="btn-ghost text-sm">Select All</button>
            <button @click="deselectAll" class="btn-ghost text-sm">Deselect All</button>
          </div>
        </div>
        
        <p class="text-surface-400 mb-4">
          Multiple items found. Select items to save. Recognition and organizing will be done later.
        </p>
        
        <div class="space-y-2 max-h-96 overflow-y-auto">
          <div
            v-for="file in shareInfo.files"
            :key="file.file_id"
            class="flex items-center p-3 rounded-lg hover:bg-surface-700 transition-colors cursor-pointer"
            :class="{ 'bg-surface-700': selectedFiles.includes(file.file_id) }"
            @click="toggleFileSelection(file.file_id)"
          >
            <input
              type="checkbox"
              :checked="selectedFiles.includes(file.file_id)"
              class="mr-3 w-4 h-4 rounded border-surface-600 bg-surface-700 text-primary-500 focus:ring-primary-500"
              @click.stop
              @change="toggleFileSelection(file.file_id)"
            />
            <div class="flex-1 min-w-0">
              <p class="text-surface-200 truncate">{{ file.name }}</p>
              <p class="text-sm text-surface-500">
                {{ file.is_dir ? 'Folder' : formatSize(file.size) }}
              </p>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Target Path Selection -->
      <div class="card p-6">
        <h2 class="text-lg font-semibold text-surface-100 mb-4">Save Location</h2>
        
        <div class="space-y-3">
          <div v-if="receivePaths.length > 0">
            <label class="block text-sm font-medium text-surface-300 mb-2">
              Select Target Folder
            </label>
            <select v-model="targetPath" class="input">
              <option v-for="path in receivePaths" :key="path" :value="path">
                {{ path }}
              </option>
            </select>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-2">
              Or Enter Custom Path
            </label>
            <input
              v-model="targetPath"
              type="text"
              placeholder="/我的接收/电影"
              class="input"
            />
          </div>
        </div>
      </div>
      
      <!-- Action Button -->
      <div class="flex justify-end">
        <button
          @click="saveFiles"
          :disabled="!canSave || isLoading"
          class="btn-primary px-8"
        >
          {{ isLoading ? 'Saving...' : 'Save to Cloud' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
// Helper function
function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${bytes.toFixed(1)} ${units[i]}`
}
</script>

