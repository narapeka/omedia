<script setup>
import { computed } from 'vue'

const props = defineProps({
  file: {
    type: Object,
    required: true
  },
  mediaType: {
    type: String,
    default: null
  },
  recognition: {
    type: Object,
    default: null
  }
})

const mediaIcon = computed(() => {
  if (props.mediaType === 'movie') return '🎬'
  if (props.mediaType === 'tv') return '📺'
  return '📁'
})

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

<template>
  <div class="flex items-start space-x-4 p-4 bg-surface-700 rounded-lg">
    <!-- Icon / Poster placeholder -->
    <div class="w-16 h-20 bg-surface-600 rounded flex items-center justify-center text-3xl flex-shrink-0">
      {{ mediaIcon }}
    </div>
    
    <!-- Info -->
    <div class="flex-1 min-w-0">
      <h3 class="text-surface-100 font-medium truncate">{{ file.name }}</h3>
      
      <div class="mt-1 space-y-1">
        <p class="text-sm text-surface-400">
          {{ file.is_dir ? 'Folder' : formatSize(file.size) }}
        </p>
        
        <div v-if="mediaType" class="flex items-center space-x-2">
          <span class="tag tag-primary">
            {{ mediaType === 'movie' ? 'Movie' : mediaType === 'tv' ? 'TV Show' : 'Unknown' }}
          </span>
        </div>
        
        <!-- Recognition result -->
        <div v-if="recognition" class="mt-2 pt-2 border-t border-surface-600">
          <p class="text-surface-200">
            {{ recognition.media_info?.title || 'Not recognized' }}
            <span v-if="recognition.media_info?.year" class="text-surface-400">
              ({{ recognition.media_info.year }})
            </span>
          </p>
          <div class="flex items-center space-x-2 mt-1">
            <span 
              :class="[
                'tag',
                recognition.confidence === 'high' ? 'confidence-high' :
                recognition.confidence === 'medium' ? 'confidence-medium' : 'confidence-low'
              ]"
            >
              {{ recognition.confidence }} confidence
            </span>
            <span v-if="recognition.matched_rule_name" class="tag">
              → {{ recognition.matched_rule_name }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

