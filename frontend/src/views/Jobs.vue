<script setup>
import { ref, onMounted } from 'vue'
import { jobsApi } from '@/api'

// State
const jobs = ref([])
const isLoading = ref(false)
const showCreateModal = ref(false)
const error = ref(null)

// New job form
const newJob = ref({
  name: '',
  job_type: 'watchdog',
  source_path: '',
  storage_type: 'local',
  auto_approve: false,
  confidence_threshold: 'high',
  poll_interval: 60,
  event_types: []
})

// Load jobs
onMounted(async () => {
  await loadJobs()
})

async function loadJobs() {
  isLoading.value = true
  try {
    const response = await jobsApi.list()
    jobs.value = response.jobs
  } catch (e) {
    error.value = 'Failed to load jobs'
    console.error(e)
  } finally {
    isLoading.value = false
  }
}

async function createJob() {
  try {
    await jobsApi.create(newJob.value)
    showCreateModal.value = false
    await loadJobs()
    resetNewJob()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to create job'
  }
}

async function toggleJob(job) {
  try {
    if (job.status === 'active') {
      await jobsApi.stop(job.id)
    } else {
      await jobsApi.start(job.id)
    }
    await loadJobs()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to toggle job'
  }
}

async function deleteJob(job) {
  if (!confirm(`Delete job "${job.name}"?`)) return
  
  try {
    await jobsApi.delete(job.id)
    await loadJobs()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to delete job'
  }
}

function resetNewJob() {
  newJob.value = {
    name: '',
    job_type: 'watchdog',
    source_path: '',
    storage_type: 'local',
    auto_approve: false,
    confidence_threshold: 'high',
    poll_interval: 60,
    event_types: []
  }
}

function getStatusColor(status) {
  switch (status) {
    case 'active': return 'text-green-400'
    case 'paused': return 'text-yellow-400'
    case 'disabled': return 'text-red-400'
    default: return 'text-surface-400'
  }
}
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-surface-100">Monitoring Jobs</h1>
        <p class="text-surface-400 mt-1">Manage watchdog and life event monitoring jobs</p>
      </div>
      <button @click="showCreateModal = true" class="btn-primary">
        + Create Job
      </button>
    </div>
    
    <!-- Error Message -->
    <div v-if="error" class="p-4 bg-red-900/30 border border-red-800 rounded-lg text-red-300">
      {{ error }}
    </div>
    
    <!-- Jobs List -->
    <div v-if="isLoading" class="card p-12 text-center">
      <div class="animate-spin w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full mx-auto mb-4"></div>
      <p class="text-surface-400">Loading jobs...</p>
    </div>
    
    <div v-else-if="jobs.length === 0" class="card p-12 text-center">
      <div class="text-5xl mb-4">📋</div>
      <h3 class="text-xl font-semibold text-surface-200 mb-2">No Jobs Yet</h3>
      <p class="text-surface-400 mb-6">Create a monitoring job to automatically organize new files</p>
      <button @click="showCreateModal = true" class="btn-primary">Create Your First Job</button>
    </div>
    
    <div v-else class="space-y-4">
      <div 
        v-for="job in jobs" 
        :key="job.id"
        class="card p-6"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center space-x-3">
              <h3 class="text-lg font-semibold text-surface-100">{{ job.name }}</h3>
              <span 
                class="tag"
                :class="job.job_type === 'watchdog' ? 'tag-primary' : 'tag-warning'"
              >
                {{ job.job_type === 'watchdog' ? '👁️ Watchdog' : '📡 Life Event' }}
              </span>
              <span :class="getStatusColor(job.status)" class="text-sm">
                ● {{ job.status }}
              </span>
            </div>
            <p class="text-surface-400 mt-1">{{ job.source_path }}</p>
            <div class="flex items-center space-x-4 mt-3 text-sm text-surface-500">
              <span>Storage: {{ job.storage_type }}</span>
              <span>Auto-approve: {{ job.auto_approve ? 'Yes' : 'No' }}</span>
              <span>Confidence: {{ job.confidence_threshold }}</span>
            </div>
          </div>
          
          <div class="flex items-center space-x-2">
            <button
              @click="toggleJob(job)"
              class="btn-secondary text-sm"
            >
              {{ job.status === 'active' ? 'Pause' : 'Start' }}
            </button>
            <button
              @click="deleteJob(job)"
              class="btn-ghost text-sm text-red-400 hover:text-red-300"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Create Job Modal -->
    <div 
      v-if="showCreateModal" 
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      @click.self="showCreateModal = false"
    >
      <div class="card p-6 w-full max-w-lg">
        <h2 class="text-xl font-bold text-surface-100 mb-6">Create Monitoring Job</h2>
        
        <form @submit.prevent="createJob" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-2">Job Name</label>
            <input v-model="newJob.name" type="text" class="input" required />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-2">Job Type</label>
            <select v-model="newJob.job_type" class="input">
              <option value="watchdog">Watchdog (Local/FUSE)</option>
              <option value="life_event">115 Life Event</option>
            </select>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-2">Source Path</label>
            <input v-model="newJob.source_path" type="text" class="input" required />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-2">Storage Type</label>
            <select v-model="newJob.storage_type" class="input">
              <option value="local">Local</option>
              <option value="p115" v-if="newJob.job_type === 'life_event'">115 Cloud</option>
            </select>
          </div>
          
          <div class="flex items-center space-x-3">
            <input 
              v-model="newJob.auto_approve" 
              type="checkbox" 
              id="auto_approve"
              class="w-4 h-4 rounded border-surface-600 bg-surface-700 text-primary-500"
            />
            <label for="auto_approve" class="text-surface-300">
              Auto-approve high confidence matches
            </label>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-2">Confidence Threshold</label>
            <select v-model="newJob.confidence_threshold" class="input">
              <option value="high">High only</option>
              <option value="medium">Medium and above</option>
              <option value="low">All</option>
            </select>
          </div>
          
          <div v-if="newJob.job_type === 'watchdog'">
            <label class="block text-sm font-medium text-surface-300 mb-2">Poll Interval (seconds)</label>
            <input v-model.number="newJob.poll_interval" type="number" min="10" class="input" />
          </div>
          
          <div class="flex justify-end space-x-3 mt-6">
            <button type="button" @click="showCreateModal = false" class="btn-ghost">
              Cancel
            </button>
            <button type="submit" class="btn-primary">
              Create Job
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

