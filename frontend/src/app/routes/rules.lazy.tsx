import { createLazyRoute } from '@tanstack/react-router'
import { RulesPage } from '@/features/rules/page'

export const Route = createLazyRoute('/rules')({
  component: RulesPage,
})
