export const settingsTabs = ['folders', 'rules', 'providers', 'maintenance'] as const
export type SettingsTab = (typeof settingsTabs)[number]
export const defaultSettingsTab: SettingsTab = 'folders'

export function settingsTabFromHash(): SettingsTab | null {
  const value = settingsHashValue()
  if (!value) return null
  return isSettingsTab(value) ? value : null
}

export function asSettingsTab(value: string): SettingsTab {
  return isSettingsTab(value) ? value : defaultSettingsTab
}

export function isSettingsTab(value: string): value is SettingsTab {
  return settingsTabs.includes(value as SettingsTab)
}

export function settingsHashValue() {
  if (typeof window === 'undefined') return ''
  return window.location.hash.replace(/^#/, '')
}

export function replaceSettingsHash(tab: SettingsTab) {
  if (typeof window === 'undefined') return
  const nextHash = `#${tab}`
  if (window.location.hash === nextHash) return
  window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${nextHash}`)
}
