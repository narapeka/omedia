import { createLazyRoute } from '@tanstack/react-router'
import { TransferPage } from '@/features/transfer/page'

export const Route = createLazyRoute('/transfer')({
  component: TransferPage,
})
