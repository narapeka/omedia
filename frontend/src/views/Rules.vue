<script setup>
import { ref, onMounted } from 'vue'
import { rulesApi } from '@/api'

// State
const rules = ref([])
const versionTags = ref({ builtin_tags: [], custom_tags: [] })
const isLoading = ref(false)
const showCreateModal = ref(false)
const error = ref(null)

// New rule form
const newRule = ref({
  name: '',
  priority: 100,
  media_type: 'all',
  storage_type: 'all',
  conditions: [],
  target_path: '',
  enabled: true
})

// New condition form
const newCondition = ref({
  field: 'genre',
  operator: 'contains',
  value: ''
})

// Load data
onMounted(async () => {
  await Promise.all([loadRules(), loadVersionTags()])
})

async function loadRules() {
  isLoading.value = true
  try {
    const response = await rulesApi.list()
    rules.value = response.rules
  } catch (e) {
    error.value = 'Failed to load rules'
    console.error(e)
  } finally {
    isLoading.value = false
  }
}

async function loadVersionTags() {
  try {
    const response = await rulesApi.getVersionTags()
    versionTags.value = response
  } catch (e) {
    console.error('Failed to load version tags:', e)
  }
}

async function createRule() {
  try {
    await rulesApi.create(newRule.value)
    showCreateModal.value = false
    await loadRules()
    resetNewRule()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to create rule'
  }
}

async function toggleRule(rule) {
  try {
    await rulesApi.update(rule.id, { enabled: !rule.enabled })
    await loadRules()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to toggle rule'
  }
}

async function deleteRule(rule) {
  if (!confirm(`Delete rule "${rule.name}"?`)) return
  
  try {
    await rulesApi.delete(rule.id)
    await loadRules()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to delete rule'
  }
}

function addCondition() {
  if (!newCondition.value.value) return
  
  newRule.value.conditions.push({ ...newCondition.value })
  newCondition.value = { field: 'genre', operator: 'contains', value: '' }
}

function removeCondition(index) {
  newRule.value.conditions.splice(index, 1)
}

function resetNewRule() {
  newRule.value = {
    name: '',
    priority: 100,
    media_type: 'all',
    storage_type: 'all',
    conditions: [],
    target_path: '',
    enabled: true
  }
}

function formatConditions(conditions) {
  if (!conditions || conditions.length === 0) return 'No conditions (matches all)'
  return conditions.map(c => `${c.field} ${c.operator} "${c.value}"`).join(', ')
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-surface-100">Transfer Rules</h1>
        <p class="text-surface-400 mt-1">Define rules for routing media to target folders</p>
      </div>
      <button @click="showCreateModal = true" class="btn-primary">
        + Create Rule
      </button>
    </div>
    
    <!-- Error Message -->
    <div v-if="error" class="p-4 bg-red-900/30 border border-red-800 rounded-lg text-red-300">
      {{ error }}
    </div>
    
    <!-- Rules List -->
    <div v-if="isLoading" class="card p-12 text-center">
      <div class="animate-spin w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full mx-auto mb-4"></div>
      <p class="text-surface-400">Loading rules...</p>
    </div>
    
    <div v-else-if="rules.length === 0" class="card p-12 text-center">
      <div class="text-5xl mb-4">📋</div>
      <h3 class="text-xl font-semibold text-surface-200 mb-2">No Rules Yet</h3>
      <p class="text-surface-400 mb-6">Create rules to automatically route media to the right folders</p>
      <button @click="showCreateModal = true" class="btn-primary">Create Your First Rule</button>
    </div>
    
    <div v-else class="space-y-4">
      <div 
        v-for="rule in rules" 
        :key="rule.id"
        class="card p-6"
        :class="{ 'opacity-50': !rule.enabled }"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center space-x-3">
              <span class="text-surface-500 text-sm font-mono">{{ rule.priority }}</span>
              <h3 class="text-lg font-semibold text-surface-100">{{ rule.name }}</h3>
              <span class="tag tag-primary">{{ rule.media_type }}</span>
              <span class="tag">{{ rule.storage_type }}</span>
            </div>
            <p class="text-surface-400 mt-2 font-mono text-sm">→ {{ rule.target_path }}</p>
            <p class="text-surface-500 text-sm mt-1">
              {{ formatConditions(rule.conditions) }}
            </p>
          </div>
          
          <div class="flex items-center space-x-2">
            <button
              @click="toggleRule(rule)"
              class="btn-ghost text-sm"
            >
              {{ rule.enabled ? 'Disable' : 'Enable' }}
            </button>
            <button
              @click="deleteRule(rule)"
              class="btn-ghost text-sm text-red-400 hover:text-red-300"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Version Tags Section -->
    <div class="card p-6">
      <h2 class="text-lg font-semibold text-surface-100 mb-4">Version Tags</h2>
      <p class="text-surface-400 mb-4">Available tags to append to folder names</p>
      <div class="flex flex-wrap gap-2">
        <span 
          v-for="tag in [...versionTags.builtin_tags, ...versionTags.custom_tags]" 
          :key="tag"
          class="tag tag-primary"
        >
          {{ tag }}
        </span>
      </div>
    </div>
    
    <!-- Create Rule Modal -->
    <div 
      v-if="showCreateModal" 
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-auto"
      @click.self="showCreateModal = false"
    >
      <div class="card p-6 w-full max-w-2xl my-8">
        <h2 class="text-xl font-bold text-surface-100 mb-6">Create Transfer Rule</h2>
        
        <form @submit.prevent="createRule" class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-surface-300 mb-2">Rule Name</label>
              <input v-model="newRule.name" type="text" class="input" required />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-surface-300 mb-2">Priority (lower = higher)</label>
              <input v-model.number="newRule.priority" type="number" min="1" class="input" />
            </div>
          </div>
          
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-surface-300 mb-2">Media Type</label>
              <select v-model="newRule.media_type" class="input">
                <option value="all">All</option>
                <option value="movie">Movie</option>
                <option value="tv">TV Show</option>
              </select>
            </div>
            
            <div>
              <label class="block text-sm font-medium text-surface-300 mb-2">Storage Type</label>
              <select v-model="newRule.storage_type" class="input">
                <option value="all">All</option>
                <option value="p115">115 Cloud</option>
                <option value="local">Local</option>
                <option value="webdav">WebDAV</option>
              </select>
            </div>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-2">Target Path Template</label>
            <input 
              v-model="newRule.target_path" 
              type="text" 
              class="input font-mono"
              placeholder="/Media/Anime/{title} ({year}) {tmdb-{tmdb_id}}"
              required 
            />
            <p class="text-surface-500 text-sm mt-1">
              Variables: {title}, {year}, {tmdb_id}, {season}, {quality}
            </p>
          </div>
          
          <!-- Conditions -->
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-2">Conditions (all must match)</label>
            
            <div v-if="newRule.conditions.length > 0" class="mb-4 space-y-2">
              <div 
                v-for="(condition, index) in newRule.conditions" 
                :key="index"
                class="flex items-center space-x-2 p-2 bg-surface-700 rounded"
              >
                <span class="text-surface-300 flex-1 font-mono text-sm">
                  {{ condition.field }} {{ condition.operator }} "{{ condition.value }}"
                </span>
                <button 
                  type="button" 
                  @click="removeCondition(index)"
                  class="text-red-400 hover:text-red-300"
                >
                  ✕
                </button>
              </div>
            </div>
            
            <div class="flex space-x-2">
              <select v-model="newCondition.field" class="input flex-1">
                <option value="genre">Genre</option>
                <option value="country">Country</option>
                <option value="language">Language</option>
                <option value="keyword">Filename Keyword</option>
                <option value="network">Network</option>
              </select>
              <select v-model="newCondition.operator" class="input w-32">
                <option value="contains">contains</option>
                <option value="equals">equals</option>
                <option value="in">in list</option>
                <option value="matches">matches</option>
              </select>
              <input 
                v-model="newCondition.value" 
                type="text" 
                class="input flex-1"
                placeholder="Value"
              />
              <button type="button" @click="addCondition" class="btn-secondary">
                Add
              </button>
            </div>
          </div>
          
          <div class="flex justify-end space-x-3 mt-6">
            <button type="button" @click="showCreateModal = false" class="btn-ghost">
              Cancel
            </button>
            <button type="submit" class="btn-primary">
              Create Rule
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

