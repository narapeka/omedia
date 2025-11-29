import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Composable for clipboard detection with Capacitor support
 */
export function useClipboard() {
  const clipboardContent = ref('')
  const isCapacitor = ref(false)
  let appStateListener = null
  
  /**
   * Check if running in Capacitor
   */
  function checkCapacitor() {
    try {
      isCapacitor.value = typeof window !== 'undefined' && 
        window.Capacitor !== undefined
      return isCapacitor.value
    } catch {
      return false
    }
  }
  
  /**
   * Read clipboard content
   */
  async function readClipboard() {
    try {
      if (checkCapacitor()) {
        // Use Capacitor Clipboard plugin
        const { Clipboard } = await import('@capacitor/clipboard')
        const result = await Clipboard.read()
        clipboardContent.value = result.value || ''
      } else {
        // Use Web Clipboard API (requires user gesture in some browsers)
        if (navigator.clipboard && navigator.clipboard.readText) {
          clipboardContent.value = await navigator.clipboard.readText()
        }
      }
    } catch (error) {
      console.warn('Failed to read clipboard:', error)
    }
    
    return clipboardContent.value
  }
  
  /**
   * Write to clipboard
   */
  async function writeClipboard(text) {
    try {
      if (checkCapacitor()) {
        const { Clipboard } = await import('@capacitor/clipboard')
        await Clipboard.write({ string: text })
      } else {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text)
        }
      }
      return true
    } catch (error) {
      console.warn('Failed to write to clipboard:', error)
      return false
    }
  }
  
  /**
   * Start watching for clipboard changes on app focus
   * (Capacitor only - reads clipboard when app comes to foreground)
   */
  async function startClipboardWatch() {
    if (!checkCapacitor()) {
      console.log('Clipboard watch only available in Capacitor')
      return
    }
    
    try {
      const { App } = await import('@capacitor/app')
      
      // Listen for app state changes
      appStateListener = await App.addListener('appStateChange', async ({ isActive }) => {
        if (isActive) {
          // App came to foreground - read clipboard
          await readClipboard()
        }
      })
      
      // Initial read
      await readClipboard()
    } catch (error) {
      console.warn('Failed to start clipboard watch:', error)
    }
  }
  
  /**
   * Stop watching clipboard
   */
  async function stopClipboardWatch() {
    if (appStateListener) {
      await appStateListener.remove()
      appStateListener = null
    }
  }
  
  /**
   * Check if content looks like a 115 share link
   */
  function isShareLink(text) {
    if (!text) return false
    return text.includes('115.com/s/') || text.startsWith('115://share')
  }
  
  return {
    clipboardContent,
    isCapacitor,
    readClipboard,
    writeClipboard,
    startClipboardWatch,
    stopClipboardWatch,
    isShareLink
  }
}

