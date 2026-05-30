import { createLazyRoute } from '@tanstack/react-router'
import { OrganizePage } from '@/features/organize/page'

export const Route = createLazyRoute('/organize')({
  component: OrganizePage,
})
