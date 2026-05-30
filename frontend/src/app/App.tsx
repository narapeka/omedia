import { RouterProvider } from '@tanstack/react-router'
import { useState } from 'react'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { createOmediaRouter } from '@/app/router'

export function App() {
  return <AppContent />
}

function AppContent() {
  const [router] = useState(createOmediaRouter)

  return (
    <>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
      <Toaster closeButton richColors position="bottom-center" />
    </>
  )
}
