import type { ReactNode } from 'react'
import { useMediaQuery } from '@/lib/useMediaQuery'
import { MobileNavigation, Sidebar } from './Sidebar'

export function AppShell({ children }: { children: ReactNode }) {
  const isMobileShell = useMediaQuery('(max-width: 760px)')

  return (
    <div className="app-shell">
      {isMobileShell ? <MobileNavigation /> : <Sidebar />}
      <main className="app-main">
        {children}
      </main>
    </div>
  )
}
