import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { messages, type MessageKey } from '@/app/i18n/messages'
import { useLocale } from '@/app/providers/LocaleProvider'

type MessageValues = Record<string, number | string | null | undefined>

type I18nContextValue = {
  t: (key: MessageKey, values?: MessageValues) => string
  locale: 'en-US' | 'zh-CN'
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const { locale } = useLocale()
  const value = useMemo(
    () => ({
      locale,
      t: (key: MessageKey, values?: MessageValues) => interpolate(messages[locale][key] ?? messages['en-US'][key], values),
    }),
    [locale],
  )
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n must be used within I18nProvider')
  return value
}

function interpolate(template: string, values?: MessageValues) {
  if (!values) return template
  return template.replace(/\{(\w+)\}/g, (match, key) => {
    const value = values[key]
    return value === null || value === undefined ? match : String(value)
  })
}
