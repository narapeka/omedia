import { createLazyRoute } from '@tanstack/react-router'
import { HelpPage } from '@/features/help/page'

export const Route = createLazyRoute('/help')({
  component: HelpPage,
})
