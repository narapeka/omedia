import { createLazyRoute } from '@tanstack/react-router'
import { SettingsPage } from '@/features/settings/page'

export const Route = createLazyRoute('/settings')({
  component: SettingsPage,
})
