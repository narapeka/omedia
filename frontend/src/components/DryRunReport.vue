<script setup>
import { ref, computed } from 'vue'
import MediaPreview from './MediaPreview.vue'
import ReIdentifyDialog from './ReIdentifyDialog.vue'

const props = defineProps({
  report: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['transfer'])

// State
const selectedItems = ref([])
const globalRuleOverride = ref(null)
const showReIdentifyDialog = ref(false)
const reIdentifyItem = ref(null)

// Initialize selected items with high confidence results
selectedItems.value = props.report.items
  .filter(item => item.confidence === 'high')
  .map(item => item.file_info.path)

// Computed
const canTransfer = computed(() => selectedItems.value.length > 0)

const groupedItems = computed(() => {
  return {
    high: props.report.items.filter(item => item.confidence === 'high'),
    medium: props.report.items.filter(item => item.confidence === 'medium'),
    low: props.report.items.filter(item => item.confidence === 'low')
  }
})

// Methods
function toggleItem(path) {
  const index = selectedItems.value.indexOf(path)
  if (index === -1) {
    selectedItems.value.push(path)
  } else {
    selectedItems.value.splice(index, 1)
  }
}

function selectAll() {
  selectedItems.value = props.report.items.map(item => item.file_info.path)
}

function selectHighConfidence() {
  selectedItems.value = props.report.items
    .filter(item => item.confidence === 'high')
    .map(item => item.file_info.path)
}

function deselectAll() {
  selectedItems.value = []
}

function openReIdentify(item) {
  reIdentifyItem.value = item
  showReIdentifyDialog.value = true
}

function handleReIdentified(result) {
  // Update the item in the report
  const index = props.report.items.findIndex(
    item => item.file_info.path === result.file_info.path
  )
  if (index !== -1) {
    props.report.items[index] = result
  }
  showReIdentifyDialog.value = false
}

function executeTransfer() {
  const itemsToTransfer = props.report.items.filter(
    item => selectedItems.value.includes(item.file_info.path)
  )
  emit('transfer', itemsToTransfer, globalRuleOverride.value)
}

function getConfidenceBadgeClass(confidence) {
  switch (confidence) {
    case 'high': return 'confidence-high'
    case 'medium': return 'confidence-medium'
    default: return 'confidence-low'
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Summary -->
    <div class="card p-6">
      <h2 class="text-lg font-semibold text-surface-100 mb-4">Recognition Summary</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="p-4 bg-surface-700 rounded-lg text-center">
          <div class="text-3xl font-bold text-surface-100">{{ report.total_items }}</div>
          <div class="text-surface-400">Total Files</div>
        </div>
        <div class="p-4 bg-green-900/30 rounded-lg text-center">
          <div class="text-3xl font-bold text-green-400">{{ report.high_confidence }}</div>
          <div class="text-surface-400">High Confidence</div>
        </div>
        <div class="p-4 bg-yellow-900/30 rounded-lg text-center">
          <div class="text-3xl font-bold text-yellow-400">{{ report.medium_confidence }}</div>
          <div class="text-surface-400">Medium Confidence</div>
        </div>
        <div class="p-4 bg-red-900/30 rounded-lg text-center">
          <div class="text-3xl font-bold text-red-400">{{ report.low_confidence }}</div>
          <div class="text-surface-400">Low Confidence</div>
        </div>
      </div>
    </div>
    
    <!-- Selection controls -->
    <div class="flex items-center justify-between">
      <div class="space-x-2">
        <button @click="selectAll" class="btn-ghost text-sm">Select All</button>
        <button @click="selectHighConfidence" class="btn-ghost text-sm">Select High Confidence</button>
        <button @click="deselectAll" class="btn-ghost text-sm">Deselect All</button>
      </div>
      <div class="text-surface-400">
        {{ selectedItems.length }} / {{ report.total_items }} selected
      </div>
    </div>
    
    <!-- Items grouped by confidence -->
    <template v-for="(confidence, level) in ['high', 'medium', 'low']" :key="level">
      <div v-if="groupedItems[confidence].length > 0" class="space-y-3">
        <h3 class="text-md font-semibold text-surface-200 flex items-center space-x-2">
          <span :class="getConfidenceBadgeClass(confidence)" class="px-2 py-0.5 rounded">
            {{ confidence.charAt(0).toUpperCase() + confidence.slice(1) }} Confidence
          </span>
          <span class="text-surface-500">({{ groupedItems[confidence].length }})</span>
        </h3>
        
        <div class="space-y-2">
          <div 
            v-for="item in groupedItems[confidence]" 
            :key="item.file_info.path"
            class="card p-4 hover:border-surface-600 transition-colors"
            :class="{ 'border-primary-500': selectedItems.includes(item.file_info.path) }"
          >
            <div class="flex items-start space-x-4">
              <!-- Checkbox -->
              <input 
                type="checkbox"
                :checked="selectedItems.includes(item.file_info.path)"
                @change="toggleItem(item.file_info.path)"
                class="mt-1 w-4 h-4 rounded border-surface-600 bg-surface-700 text-primary-500"
              />
              
              <!-- Content -->
              <div class="flex-1 min-w-0">
                <div class="flex items-start justify-between">
                  <div>
                    <p class="text-surface-200 font-medium truncate">{{ item.file_info.name }}</p>
                    <p v-if="item.media_info" class="text-surface-400 mt-1">
                      → {{ item.media_info.title }}
                      <span v-if="item.media_info.year">({{ item.media_info.year }})</span>
                    </p>
                    <p v-else class="text-red-400 mt-1">Not recognized</p>
                  </div>
                  
                  <button 
                    @click="openReIdentify(item)"
                    class="btn-ghost text-sm flex-shrink-0"
                  >
                    Re-identify
                  </button>
                </div>
                
                <!-- Target path -->
                <div v-if="item.target_path" class="mt-2 p-2 bg-surface-700 rounded text-sm font-mono text-surface-300">
                  {{ item.target_path }}
                </div>
                
                <!-- Tags -->
                <div class="flex items-center space-x-2 mt-2">
                  <span :class="getConfidenceBadgeClass(item.confidence)">
                    {{ item.confidence }}
                  </span>
                  <span v-if="item.matched_rule_name" class="tag">
                    {{ item.matched_rule_name }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
    
    <!-- Global override -->
    <div class="card p-6">
      <h3 class="text-md font-semibold text-surface-100 mb-4">Global Override (Optional)</h3>
      <p class="text-surface-400 mb-4">Apply a single rule to all selected items</p>
      <select v-model="globalRuleOverride" class="input">
        <option :value="null">Use matched rules (default)</option>
        <!-- Rules would be loaded from API -->
      </select>
    </div>
    
    <!-- Action buttons -->
    <div class="flex justify-end space-x-3">
      <button 
        @click="executeTransfer"
        :disabled="!canTransfer"
        class="btn-primary px-8"
      >
        Transfer {{ selectedItems.length }} Items
      </button>
    </div>
    
    <!-- Re-identify dialog -->
    <ReIdentifyDialog 
      v-if="showReIdentifyDialog"
      :item="reIdentifyItem"
      @close="showReIdentifyDialog = false"
      @identified="handleReIdentified"
    />
  </div>
</template>

