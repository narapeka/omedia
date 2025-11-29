import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  // State
  const pendingShareLink = ref(null)
  const isLoading = ref(false)
  const notifications = ref([])
  const config = ref(null)
  
  // Getters
  const hasPendingShareLink = computed(() => !!pendingShareLink.value)
  
  // Actions
  function setPendingShareLink(link) {
    pendingShareLink.value = link
  }
  
  function clearPendingShareLink() {
    pendingShareLink.value = null
  }
  
  function setLoading(value) {
    isLoading.value = value
  }
  
  function addNotification(notification) {
    const id = Date.now()
    notifications.value.push({
      id,
      ...notification,
      timestamp: new Date()
    })
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      removeNotification(id)
    }, 5000)
  }
  
  function removeNotification(id) {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index !== -1) {
      notifications.value.splice(index, 1)
    }
  }
  
  function setConfig(newConfig) {
    config.value = newConfig
  }
  
  return {
    // State
    pendingShareLink,
    isLoading,
    notifications,
    config,
    // Getters
    hasPendingShareLink,
    // Actions
    setPendingShareLink,
    clearPendingShareLink,
    setLoading,
    addNotification,
    removeNotification,
    setConfig
  }
})

