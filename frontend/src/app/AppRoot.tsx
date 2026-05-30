import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App } from '@/app/App'
import { I18nProvider } from './providers/I18nProvider'
import { LocaleProvider } from './providers/LocaleProvider'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 15_000,
    },
  },
})

export function AppRoot() {
  return (
    <LocaleProvider>
      <I18nProvider>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </I18nProvider>
    </LocaleProvider>
  )
}
