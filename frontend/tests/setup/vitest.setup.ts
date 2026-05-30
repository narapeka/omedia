import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }),
})

class ResizeObserverMock {
  observe() {
    return undefined
  }
  unobserve() {
    return undefined
  }
  disconnect() {
    return undefined
  }
}

Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: ResizeObserverMock,
})

Object.defineProperty(window, 'scrollTo', {
  writable: true,
  value: () => undefined,
})

Object.defineProperty(URL, 'createObjectURL', {
  writable: true,
  value: () => 'blob:omedia-backup',
})

Object.defineProperty(URL, 'revokeObjectURL', {
  writable: true,
  value: () => undefined,
})

Object.defineProperty(HTMLAnchorElement.prototype, 'click', {
  writable: true,
  value: () => undefined,
})

Object.defineProperty(Element.prototype, 'scrollIntoView', {
  writable: true,
  value: () => undefined,
})

Object.defineProperty(Element.prototype, 'hasPointerCapture', {
  writable: true,
  value: () => false,
})

Object.defineProperty(Element.prototype, 'setPointerCapture', {
  writable: true,
  value: () => undefined,
})

Object.defineProperty(Element.prototype, 'releasePointerCapture', {
  writable: true,
  value: () => undefined,
})

afterEach(() => {
  cleanup()
  document.body.dataset.locale = ''
})
