import { createLazyRoute } from '@tanstack/react-router'
import { DashboardPage } from '@/features/dashboard/page'

export const Route = createLazyRoute('/dashboard')({
  component: DashboardPage,
})
