import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    redirect: '/share-import'
  },
  {
    path: '/share-import',
    name: 'ShareImport',
    component: () => import('@/views/ShareImport.vue'),
    meta: { title: 'Import Share Link' }
  },
  {
    path: '/organize',
    name: 'ManualOrganize',
    component: () => import('@/views/ManualOrganize.vue'),
    meta: { title: 'Manual Organize' }
  },
  {
    path: '/jobs',
    name: 'Jobs',
    component: () => import('@/views/Jobs.vue'),
    meta: { title: 'Monitoring Jobs' }
  },
  {
    path: '/rules',
    name: 'Rules',
    component: () => import('@/views/Rules.vue'),
    meta: { title: 'Transfer Rules' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { title: 'Settings' }
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Update document title on navigation
router.beforeEach((to, from, next) => {
  document.title = to.meta.title 
    ? `${to.meta.title} - OMedia` 
    : 'OMedia - Media Organizer'
  next()
})

export default router

