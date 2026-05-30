import type { ReactNode } from 'react'

export function PageHeader({
  title,
  eyebrow,
  actions,
}: {
  title: ReactNode
  eyebrow?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="flex min-h-9 flex-wrap items-center justify-between gap-3">
      <div className="min-w-0">
        {eyebrow ? <div className="mb-1 text-[0.8rem] font-bold uppercase leading-5 tracking-normal text-muted-foreground">{eyebrow}</div> : null}
        <h1 className="truncate text-[1.375rem] font-extrabold leading-tight sm:text-[1.5rem]">{title}</h1>
      </div>
      {actions ? (
        <div className="omedia-page-actions flex flex-wrap items-center gap-2.5 [&_[data-slot=button]]:h-8 [&_[data-slot=button]]:min-w-24 [&_[data-slot=button]]:px-4">
          {actions}
        </div>
      ) : null}
    </header>
  )
}
