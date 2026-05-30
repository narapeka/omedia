import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type Locale = 'en-US' | 'zh-CN'

type LocaleContextValue = {
  locale: Locale
  setLocale: (locale: Locale) => void
}

const LocaleContext = createContext<LocaleContextValue | null>(null)
const localeKey = 'omedia.locale'

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => initialLocale())

  useEffect(() => {
    localStorage.setItem(localeKey, locale)
    document.body.dataset.locale = locale
    document.documentElement.lang = locale
  }, [locale])

  useEffect(() => {
    localStorage.removeItem('omedia.theme')
    document.documentElement.dataset.theme = 'dark'
  }, [])

  const value = useMemo(
    () => ({
      locale,
      setLocale: setLocaleState,
    }),
    [locale],
  )

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
}

export function useLocale() {
  const value = useContext(LocaleContext)
  if (!value) throw new Error('useLocale must be used within LocaleProvider')
  return value
}

function initialLocale(): Locale {
  const stored = localStorage.getItem(localeKey)
  if (stored === 'en-US' || stored === 'zh-CN') return stored
  return 'zh-CN'
}
