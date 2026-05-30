export function formatDateTime(value: string | null | undefined, locale: string) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(locale, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function formatCount(value: number | undefined, locale: string) {
  return new Intl.NumberFormat(locale).format(value ?? 0)
}

export function compactPath(value: string | null | undefined) {
  if (!value) return '-'
  if (value.length <= 54) return value
  return `${value.slice(0, 24)}...${value.slice(-24)}`
}
