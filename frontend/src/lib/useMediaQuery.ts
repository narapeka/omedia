import { useSyncExternalStore } from 'react'

export const TWO_XL_MEDIA_QUERY = '(min-width: 1536px)'

export function useMediaQuery(query: string, fallback = false) {
  return useSyncExternalStore(
    (onStoreChange) => subscribeMediaQuery(query, onStoreChange),
    () => getMediaQueryMatch(query, fallback),
    () => fallback,
  )
}

export function useIs2xl() {
  return useMediaQuery(TWO_XL_MEDIA_QUERY)
}

function getMediaQueryMatch(query: string, fallback: boolean) {
  if (typeof window === 'undefined' || !window.matchMedia) return fallback
  return window.matchMedia(query).matches
}

type MediaQueryStore = {
  listeners: Set<() => void>
  mediaQuery: MediaQueryList
  notify: () => void
}

const mediaQueryStores = new Map<string, MediaQueryStore>()

function subscribeMediaQuery(query: string, listener: () => void) {
  if (typeof window === 'undefined' || !window.matchMedia) return () => {}

  const store = getMediaQueryStore(query)
  store.listeners.add(listener)
  return () => {
    store.listeners.delete(listener)
    if (store.listeners.size > 0) return

    removeMediaQueryListener(store.mediaQuery, store.notify)
    mediaQueryStores.delete(query)
  }
}

function getMediaQueryStore(query: string) {
  const existing = mediaQueryStores.get(query)
  if (existing) return existing

  const mediaQuery = window.matchMedia(query)
  const store: MediaQueryStore = {
    listeners: new Set(),
    mediaQuery,
    notify: () => store.listeners.forEach((listener) => listener()),
  }
  addMediaQueryListener(mediaQuery, store.notify)
  mediaQueryStores.set(query, store)
  return store
}

function addMediaQueryListener(mediaQuery: MediaQueryList, listener: () => void) {
  if (mediaQuery.addEventListener) {
    mediaQuery.addEventListener('change', listener)
    return
  }
  mediaQuery.addListener(listener)
}

function removeMediaQueryListener(mediaQuery: MediaQueryList, listener: () => void) {
  if (mediaQuery.removeEventListener) {
    mediaQuery.removeEventListener('change', listener)
    return
  }
  mediaQuery.removeListener(listener)
}
