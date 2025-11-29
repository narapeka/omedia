<script setup>
import { ref, computed, onMounted } from 'vue'
import { organizeApi } from '@/api'
import FileBrowser from '@/components/FileBrowser.vue'
import DryRunReport from '@/components/DryRunReport.vue'

// State
const currentStep = ref(1) // 1: Select source, 2: Choose media type, 3: Review results, 4: Transfer
const storageType = ref('p115')
const sourcePath = ref('/')
const mediaType = ref(null)
const isLoading = ref(false)
const error = ref(null)
const scanResults = ref(null)
const dryRunReport = ref(null)

// Storage type options
const storageOptions = [
  { value: 'p115', label: '115 Cloud', icon: 'cloud' },
  { value: 'local', label: 'Local Disk', icon: 'folder' },
  { value: 'webdav', label: 'WebDAV', icon: 'server' },
]

// Computed
const canProceedToStep2 = computed(() => sourcePath.value && scanResults.value?.file_count > 0)
const canProceedToStep3 = computed(() => mediaType.value)
const canTransfer = computed(() => dryRunReport.value?.recognized_items > 0)

// Methods
async function browsePath(path) {
  try {
    const response = await organizeApi.browse(path, storageType.value)
    return response
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to browse path'
    throw e
  }
}

async function scanForMedia() {
  isLoading.value = true
  error.value = null
  
  try {
    const response = await organizeApi.scan(sourcePath.value, storageType.value, 'unknown')
    scanResults.value = response
    
    if (response.file_count > 0) {
      currentStep.value = 2
    } else {
      error.value = 'No media files found in this folder'
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to scan folder'
  } finally {
    isLoading.value = false
  }
}

function selectMediaType(type) {
  mediaType.value = type
  startRecognition()
}

async function startRecognition() {
  isLoading.value = true
  error.value = null
  currentStep.value = 3
  
  try {
    const response = await organizeApi.dryRun(
      sourcePath.value,
      storageType.value,
      mediaType.value
    )
    dryRunReport.value = response
  } catch (e) {
    error.value = e.response?.data?.detail || 'Recognition failed'
  } finally {
    isLoading.value = false
  }
}

async function executeTransfer() {
  isLoading.value = true
  error.value = null
  
  try {
    await organizeApi.transfer(dryRunReport.value.items)
    currentStep.value = 4
  } catch (e) {
    error.value = e.response?.data?.detail || 'Transfer failed'
  } finally {
    isLoading.value = false
  }
}

function reset() {
  currentStep.value = 1
  sourcePath.value = '/'
  mediaType.value = null
  scanResults.value = null
  dryRunReport.value = null
  error.value = null
}

function goBack() {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-surface-100">Manual Organize</h1>
        <p class="text-surface-400 mt-1">Select a folder to organize media files</p>
      </div>
      
      <!-- Progress Steps -->
      <div class="hidden md:flex items-center space-x-2">
        <div 
          v-for="step in 4" 
          :key="step"
          class="flex items-center"
        >
          <div 
            class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium"
            :class="[
              currentStep >= step 
                ? 'bg-primary-600 text-white' 
                : 'bg-surface-700 text-surface-400'
            ]"
          >
            {{ step }}
          </div>
          <div 
            v-if="step < 4" 
            class="w-12 h-0.5 mx-1"
            :class="currentStep > step ? 'bg-primary-600' : 'bg-surface-700'"
          ></div>
        </div>
      </div>
    </div>
    
    <!-- Error Message -->
    <div v-if="error" class="p-4 bg-red-900/30 border border-red-800 rounded-lg text-red-300">
      {{ error }}
    </div>
    
    <!-- Step 1: Select Source -->
    <div v-if="currentStep === 1" class="space-y-6">
      <!-- Storage Type Selection -->
      <div class="card p-6">
        <h2 class="text-lg font-semibold text-surface-100 mb-4">Storage Type</h2>
        <div class="grid grid-cols-3 gap-4">
          <button
            v-for="option in storageOptions"
            :key="option.value"
            @click="storageType = option.value"
            class="p-4 rounded-lg border-2 transition-all"
            :class="[
              storageType === option.value
                ? 'border-primary-500 bg-primary-900/20'
                : 'border-surface-700 hover:border-surface-500'
            ]"
          >
            <div class="text-center">
              <div class="text-2xl mb-2">
                {{ option.icon === 'cloud' ? '☁️' : option.icon === 'folder' ? '📁' : '🖥️' }}
              </div>
              <div class="text-surface-200 font-medium">{{ option.label }}</div>
            </div>
          </button>
        </div>
      </div>
      
      <!-- File Browser -->
      <div class="card p-6">
        <h2 class="text-lg font-semibold text-surface-100 mb-4">Select Source Folder</h2>
        <FileBrowser
          v-model:path="sourcePath"
          :storageType="storageType"
          @browse="browsePath"
        />
      </div>
      
      <!-- Scan Button -->
      <div class="flex justify-end">
        <button
          @click="scanForMedia"
          :disabled="!sourcePath || isLoading"
          class="btn-primary px-8"
        >
          {{ isLoading ? 'Scanning...' : 'Scan for Media' }}
        </button>
      </div>
    </div>
    
    <!-- Step 2: Choose Media Type -->
    <div v-if="currentStep === 2" class="space-y-6">
      <div class="card p-6">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h2 class="text-lg font-semibold text-surface-100">Found {{ scanResults?.file_count }} Media Files</h2>
            <p class="text-surface-400">in {{ sourcePath }}</p>
          </div>
          <button @click="goBack" class="btn-ghost">← Back</button>
        </div>
        
        <p class="text-surface-300 mb-6">
          What type of media is in this folder?
        </p>
        
        <div class="grid grid-cols-2 gap-6">
          <button
            @click="selectMediaType('movie')"
            class="p-8 rounded-xl border-2 border-surface-700 hover:border-primary-500 hover:bg-primary-900/10 transition-all"
          >
            <div class="text-center">
              <div class="text-5xl mb-4">🎬</div>
              <div class="text-xl font-semibold text-surface-100">Movies</div>
              <div class="text-surface-400 mt-2">Single films or movie collections</div>
            </div>
          </button>
          
          <button
            @click="selectMediaType('tv')"
            class="p-8 rounded-xl border-2 border-surface-700 hover:border-primary-500 hover:bg-primary-900/10 transition-all"
          >
            <div class="text-center">
              <div class="text-5xl mb-4">📺</div>
              <div class="text-xl font-semibold text-surface-100">TV Shows</div>
              <div class="text-surface-400 mt-2">Series with seasons and episodes</div>
            </div>
          </button>
        </div>
      </div>
    </div>
    
    <!-- Step 3: Review Results -->
    <div v-if="currentStep === 3" class="space-y-6">
      <div class="flex items-center justify-between">
        <button @click="goBack" class="btn-ghost">← Back</button>
        <div class="text-surface-400">
          Recognizing {{ mediaType === 'movie' ? 'movies' : 'TV shows' }}...
        </div>
      </div>
      
      <div v-if="isLoading" class="card p-12 text-center">
        <div class="animate-spin w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full mx-auto mb-4"></div>
        <p class="text-surface-300">Recognizing media files...</p>
        <p class="text-surface-500 text-sm mt-2">This may take a while for large collections</p>
      </div>
      
      <DryRunReport 
        v-else-if="dryRunReport" 
        :report="dryRunReport"
        @transfer="executeTransfer"
      />
    </div>
    
    <!-- Step 4: Complete -->
    <div v-if="currentStep === 4" class="card p-12 text-center">
      <div class="text-6xl mb-6">✅</div>
      <h2 class="text-2xl font-bold text-surface-100 mb-4">Organization Complete!</h2>
      <p class="text-surface-400 mb-8">Your media files have been organized successfully.</p>
      <button @click="reset" class="btn-primary">Organize More Files</button>
    </div>
  </div>
</template>

