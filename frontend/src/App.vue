<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useClipboard } from '@/composables/useClipboard'
import NavBar from '@/components/NavBar.vue'
import TabBar from '@/components/TabBar.vue'

const router = useRouter()
const appStore = useAppStore()
const { startClipboardWatch, stopClipboardWatch, clipboardContent } = useClipboard()

// Watch for clipboard changes and auto-navigate to share import
onMounted(() => {
  startClipboardWatch()
  
  // Check if there's a share link in clipboard on app focus
  if (clipboardContent.value && isShareLink(clipboardContent.value)) {
    appStore.setPendingShareLink(clipboardContent.value)
    router.push('/share-import')
  }
})

onUnmounted(() => {
  stopClipboardWatch()
})

function isShareLink(text) {
  if (!text) return false
  return text.includes('115.com/s/') || text.startsWith('115://share')
}
</script>

<template>
  <div class="min-h-screen flex flex-col bg-surface-950">
    <!-- Top Navigation -->
    <NavBar />
    
    <!-- Main Content -->
    <main class="flex-1 overflow-auto pb-20 md:pb-0">
      <div class="container mx-auto px-4 py-6 max-w-6xl">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
    
    <!-- Bottom Tab Bar (mobile) -->
    <TabBar class="md:hidden" />
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

