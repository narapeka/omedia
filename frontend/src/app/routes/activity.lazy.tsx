import { createLazyRoute } from '@tanstack/react-router'
import { ActivityPage } from '@/features/activity/page'

export const Route = createLazyRoute('/activity')({
  component: ActivityPage,
})
