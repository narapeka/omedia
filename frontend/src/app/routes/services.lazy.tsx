import { createLazyRoute } from '@tanstack/react-router'
import { ServicesPage } from '@/features/services/page'

export const Route = createLazyRoute('/services')({
  component: ServicesPage,
})
