import axios from 'axios'

// Create axios instance
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    // Handle common errors
    if (error.response) {
      const { status, data } = error.response
      
      if (status === 401) {
        // Handle unauthorized
        console.error('Unauthorized')
      } else if (status === 500) {
        console.error('Server error:', data.detail || 'Unknown error')
      }
    }
    
    return Promise.reject(error)
  }
)

// ============ Share Import API ============

export const shareApi = {
  /**
   * Parse a share link
   */
  parseShareLink(shareUrl) {
    return api.post('/share/parse', { share_url: shareUrl })
  },
  
  /**
   * Save files from a share link
   */
  saveShareFiles(shareCode, receiveCode, targetPath, fileIds = null) {
    return api.post('/share/save', {
      share_code: shareCode,
      receive_code: receiveCode,
      target_path: targetPath,
      file_ids: fileIds
    })
  },
  
  /**
   * Get configured receive paths
   */
  getReceivePaths() {
    return api.get('/share/receive-paths')
  }
}

// ============ Organize API ============

export const organizeApi = {
  /**
   * Browse a directory
   */
  browse(path, storageType) {
    return api.post('/organize/browse', { path, storage_type: storageType })
  },
  
  /**
   * Scan for media files
   */
  scan(sourcePath, storageType, mediaType) {
    return api.post('/organize/scan', {
      source_path: sourcePath,
      storage_type: storageType,
      media_type: mediaType
    })
  },
  
  /**
   * Get dry run report
   */
  dryRun(sourcePath, storageType, mediaType) {
    return api.post('/organize/dry-run', {
      source_path: sourcePath,
      storage_type: storageType,
      media_type: mediaType
    })
  },
  
  /**
   * Execute transfer
   */
  transfer(items, globalRuleOverride = null) {
    return api.post('/organize/transfer', {
      items,
      global_rule_override: globalRuleOverride
    })
  }
}

// ============ Recognition API ============

export const recognizeApi = {
  /**
   * Recognize files
   */
  recognizeFiles(files, mediaType) {
    return api.post('/recognize/files', { files, media_type: mediaType })
  },
  
  /**
   * Re-identify a media item
   */
  reIdentify(filePath, searchTerm, year, tmdbId, mediaType) {
    return api.post('/recognize/re-identify', {
      file_path: filePath,
      search_term: searchTerm,
      year,
      tmdb_id: tmdbId,
      media_type: mediaType
    })
  },
  
  /**
   * Search TMDB
   */
  searchTmdb(query, year, mediaType) {
    return api.post('/recognize/search-tmdb', {
      query,
      year,
      media_type: mediaType
    })
  }
}

// ============ Jobs API ============

export const jobsApi = {
  /**
   * List all jobs
   */
  list(jobType = null, storageType = null, enabledOnly = false) {
    const params = new URLSearchParams()
    if (jobType) params.append('job_type', jobType)
    if (storageType) params.append('storage_type', storageType)
    if (enabledOnly) params.append('enabled_only', 'true')
    return api.get(`/jobs/?${params}`)
  },
  
  /**
   * Create a job
   */
  create(jobData) {
    return api.post('/jobs/', jobData)
  },
  
  /**
   * Get a job
   */
  get(jobId) {
    return api.get(`/jobs/${jobId}`)
  },
  
  /**
   * Update a job
   */
  update(jobId, jobData) {
    return api.put(`/jobs/${jobId}`, jobData)
  },
  
  /**
   * Delete a job
   */
  delete(jobId) {
    return api.delete(`/jobs/${jobId}`)
  },
  
  /**
   * Start a job
   */
  start(jobId) {
    return api.post(`/jobs/${jobId}/start`)
  },
  
  /**
   * Stop a job
   */
  stop(jobId) {
    return api.post(`/jobs/${jobId}/stop`)
  }
}

// ============ Rules API ============

export const rulesApi = {
  /**
   * List all rules
   */
  list(mediaType = null, storageType = null, enabledOnly = false) {
    const params = new URLSearchParams()
    if (mediaType) params.append('media_type', mediaType)
    if (storageType) params.append('storage_type', storageType)
    if (enabledOnly) params.append('enabled_only', 'true')
    return api.get(`/rules/?${params}`)
  },
  
  /**
   * Create a rule
   */
  create(ruleData) {
    return api.post('/rules/', ruleData)
  },
  
  /**
   * Update a rule
   */
  update(ruleId, ruleData) {
    return api.put(`/rules/${ruleId}`, ruleData)
  },
  
  /**
   * Delete a rule
   */
  delete(ruleId) {
    return api.delete(`/rules/${ruleId}`)
  },
  
  /**
   * Get naming patterns
   */
  getNamingPatterns(mediaType = null) {
    const params = mediaType ? `?media_type=${mediaType}` : ''
    return api.get(`/rules/patterns/${params}`)
  },
  
  /**
   * Get version tags
   */
  getVersionTags() {
    return api.get('/rules/version-tags/')
  }
}

// ============ Config API ============

export const configApi = {
  /**
   * Get current config
   */
  get() {
    return api.get('/config/')
  },
  
  /**
   * Get status
   */
  getStatus() {
    return api.get('/config/status')
  },
  
  /**
   * Get template variables
   */
  getTemplateVariables() {
    return api.get('/config/template-variables')
  },
  
  /**
   * Get rule condition fields
   */
  getRuleConditionFields() {
    return api.get('/config/rule-condition-fields')
  }
}

export default api

