import { Children, isValidElement, type ReactNode } from 'react'

export type GuideSection = {
  id: string
  title: string
}

export function parseGuideSections(markdown: string): GuideSection[] {
  return markdown
    .split(/\r?\n/)
    .map((line) => line.match(/^##\s+(.+?)\s*$/)?.[1]?.trim())
    .filter((title): title is string => Boolean(title))
    .map((title) => ({ id: slugifyHeading(title), title }))
}

export function headingText(node: ReactNode): string {
  return Children.toArray(node)
    .map((child) => {
      if (typeof child === 'string' || typeof child === 'number') return String(child)
      if (isValidElement<{ children?: ReactNode }>(child)) return headingText(child.props.children)
      return ''
    })
    .join('')
}

export function slugifyHeading(text: string) {
  const slug = text
    .trim()
    .toLowerCase()
    .replace(/[`*_~[\](){}]/g, '')
    .replace(/[^\p{Letter}\p{Number}]+/gu, '-')
    .replace(/^-+|-+$/g, '')

  return slug || 'section'
}
