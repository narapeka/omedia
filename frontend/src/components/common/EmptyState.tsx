import { Empty, EmptyDescription, EmptyHeader } from '@/components/ui/empty'

export function EmptyState({ label }: { label: string }) {
  return (
    <Empty className="min-h-40 rounded-xl border bg-card">
      <EmptyHeader>
        <EmptyDescription>{label}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  )
}
