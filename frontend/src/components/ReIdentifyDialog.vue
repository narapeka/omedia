<script setup>
import { ref, computed } from 'vue'
import { recognizeApi } from '@/api'

const props = defineProps({
  item: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['close', 'identified'])

// State
const searchQuery = ref('')
const searchYear = ref(null)
const mediaType = ref(props.item.media_info?.media_type || 'tv')
const searchResults = ref([])
const isSearching = ref(false)
const error = ref(null)

// Initialize with existing data if available
if (props.item.media_info) {
  searchQuery.value = props.item.media_info.title || ''
  searchYear.value = props.item.media_info.year
}

// Methods
async function search() {
  if (!searchQuery.value.trim()) return
  
  isSearching.value = true
  error.value = null
  
  try {
    const response = await recognizeApi.searchTmdb(
      searchQuery.value,
      searchYear.value,
      mediaType.value
    )
    searchResults.value = response.results
  } catch (e) {
    error.value = 'Search failed. Please try again.'
    console.error(e)
  } finally {
    isSearching.value = false
  }
}

async function selectResult(result) {
  try {
    const response = await recognizeApi.reIdentify(
      props.item.file_info.path,
      null,
      null,
      result.tmdb_id,
      mediaType.value
    )
    emit('identified', response)
  } catch (e) {
    error.value = 'Failed to apply selection'
    console.error(e)
  }
}

function close() {
  emit('close')
}
</script>

<template>
  <div 
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
    @click.self="close"
  >
    <div class="card p-6 w-full max-w-2xl max-h-[80vh] flex flex-col">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-bold text-surface-100">Re-identify Media</h2>
        <button @click="close" class="btn-ghost">✕</button>
      </div>
      
      <!-- Current file info -->
      <div class="p-4 bg-surface-700 rounded-lg mb-6">
        <p class="text-surface-400 text-sm">File:</p>
        <p class="text-surface-200 font-medium truncate">{{ item.file_info.name }}</p>
      </div>
      
      <!-- Search form -->
      <div class="space-y-4 mb-6">
        <div class="flex space-x-3">
          <select v-model="mediaType" class="input w-32">
            <option value="tv">TV Show</option>
            <option value="movie">Movie</option>
          </select>
          <input 
            v-model="searchQuery"
            type="text"
            placeholder="Search title..."
            class="input flex-1"
            @keyup.enter="search"
          />
          <input 
            v-model.number="searchYear"
            type="number"
            placeholder="Year"
            class="input w-24"
          />
          <button @click="search" :disabled="isSearching" class="btn-primary">
            {{ isSearching ? 'Searching...' : 'Search' }}
          </button>
        </div>
        
        <!-- Error -->
        <div v-if="error" class="p-3 bg-red-900/30 border border-red-800 rounded text-red-300 text-sm">
          {{ error }}
        </div>
      </div>
      
      <!-- Results -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="isSearching" class="p-8 text-center">
          <div class="animate-spin w-8 h-8 border-3 border-primary-500 border-t-transparent rounded-full mx-auto"></div>
        </div>
        
        <div v-else-if="searchResults.length === 0" class="p-8 text-center text-surface-400">
          {{ searchQuery ? 'No results found' : 'Enter a search term to find media' }}
        </div>
        
        <div v-else class="space-y-2">
          <button
            v-for="result in searchResults"
            :key="result.tmdb_id"
            @click="selectResult(result)"
            class="w-full flex items-start space-x-4 p-4 bg-surface-700 hover:bg-surface-600 rounded-lg transition-colors text-left"
          >
            <!-- Poster placeholder -->
            <div class="w-12 h-16 bg-surface-600 rounded flex items-center justify-center flex-shrink-0">
              <img 
                v-if="result.poster_path"
                :src="`https://image.tmdb.org/t/p/w92${result.poster_path}`"
                :alt="result.title"
                class="w-full h-full object-cover rounded"
              />
              <span v-else class="text-2xl">{{ mediaType === 'movie' ? '🎬' : '📺' }}</span>
            </div>
            
            <div class="flex-1 min-w-0">
              <p class="text-surface-100 font-medium">
                {{ result.title }}
                <span v-if="result.year" class="text-surface-400">({{ result.year }})</span>
              </p>
              <p v-if="result.original_title && result.original_title !== result.title" class="text-surface-400 text-sm">
                {{ result.original_title }}
              </p>
              <p v-if="result.overview" class="text-surface-500 text-sm mt-1 line-clamp-2">
                {{ result.overview }}
              </p>
              <p class="text-surface-600 text-xs mt-1">TMDB ID: {{ result.tmdb_id }}</p>
            </div>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>

