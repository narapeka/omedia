import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { useI18n } from '@/app/providers/I18nProvider'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import enGuide from '@/content/user-guide.en.md?raw'
import zhCNGuide from '@/content/user-guide.zh-CN.md?raw'
import { GuideArticle } from './markdown'
import { parseGuideSections, type GuideSection } from './sections'

const guideByLocale = {
  'en-US': enGuide,
  'zh-CN': zhCNGuide,
}

type ScrollRoot = HTMLElement | Window
type NavFrame = {
  left: number
  top: number
  width: number
}

export function HelpPage() {
  const { locale } = useI18n()
  const guide = guideByLocale[locale]
  const pageRef = useRef<HTMLDivElement>(null)
  const navRef = useRef<HTMLDivElement>(null)
  const sections = useMemo(() => parseGuideSections(guide), [guide])
  const [activeSectionId, setActiveSectionId] = useState(sections[0]?.id ?? '')
  const [navFrame, setNavFrame] = useState<NavFrame | null>(null)
  const [navHeight, setNavHeight] = useState(0)

  const scrollToSection = useCallback((sectionId: string, updateHash = true) => {
    const target = document.getElementById(sectionId)
    if (!target) return

    const scrollRoot = getScrollRoot(pageRef.current)
    const navHeight = navRef.current?.getBoundingClientRect().height ?? 0
    const gap = 10

    if (isElementScrollRoot(scrollRoot)) {
      const rootRect = scrollRoot.getBoundingClientRect()
      const targetRect = target.getBoundingClientRect()
      const nextTop = scrollRoot.scrollTop + targetRect.top - rootRect.top - navHeight - gap

      scrollRoot.scrollTo({ top: Math.max(0, nextTop), behavior: 'smooth' })
    } else {
      const nextTop = window.scrollY + target.getBoundingClientRect().top - navHeight - gap
      window.scrollTo({ top: Math.max(0, nextTop), behavior: 'smooth' })
    }

    setActiveSectionId(sectionId)
    if (updateHash) window.history.replaceState(null, '', `#${sectionId}`)
  }, [])

  useEffect(() => {
    let frame = 0

    function updateNavFrame() {
      frame = 0
      const page = pageRef.current
      if (!page) return

      const pageRect = page.getBoundingClientRect()
      const mainRect = page.closest('.app-main')?.getBoundingClientRect()

      setNavFrame({
        left: Math.round(pageRect.left),
        top: Math.max(0, Math.round(mainRect?.top ?? 0)),
        width: Math.round(pageRect.width),
      })
    }

    function scheduleUpdate() {
      if (frame) return
      frame = window.requestAnimationFrame(updateNavFrame)
    }

    scheduleUpdate()
    window.addEventListener('resize', scheduleUpdate)

    return () => {
      window.removeEventListener('resize', scheduleUpdate)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [])

  useEffect(() => {
    setActiveSectionId(sections[0]?.id ?? '')
  }, [sections])

  useEffect(() => {
    const navElement = navRef.current
    if (!navElement) return

    const updateNavHeight = () => {
      setNavHeight(Math.ceil(navElement.getBoundingClientRect().height))
    }

    updateNavHeight()
    const resizeObserver = new ResizeObserver(updateNavHeight)
    resizeObserver.observe(navElement)
    window.addEventListener('resize', updateNavHeight)

    return () => {
      resizeObserver.disconnect()
      window.removeEventListener('resize', updateNavHeight)
    }
  }, [sections])

  useEffect(() => {
    const hash = decodeURIComponent(window.location.hash.replace(/^#/, ''))
    if (!hash || !sections.some((section) => section.id === hash)) return

    const frame = window.requestAnimationFrame(() => scrollToSection(hash, false))
    return () => window.cancelAnimationFrame(frame)
  }, [scrollToSection, sections])

  useEffect(() => {
    const scrollRoot = getScrollRoot(pageRef.current)
    const target = scrollRoot
    let frame = 0

    function updateActiveSection() {
      frame = 0
      const navBottom = navRef.current?.getBoundingClientRect().bottom ?? 0
      const rootTop = isElementScrollRoot(scrollRoot) ? scrollRoot.getBoundingClientRect().top : 0
      const threshold = navBottom - rootTop + 80
      let activeId = sections[0]?.id ?? ''

      for (const section of sections) {
        const heading = document.getElementById(section.id)
        if (!heading) continue

        const headingTop = isElementScrollRoot(scrollRoot)
          ? heading.getBoundingClientRect().top - scrollRoot.getBoundingClientRect().top
          : heading.getBoundingClientRect().top

        if (headingTop <= threshold) activeId = section.id
        else break
      }

      setActiveSectionId((current) => current === activeId ? current : activeId)
    }

    function scheduleUpdate() {
      if (frame) return
      frame = window.requestAnimationFrame(updateActiveSection)
    }

    target.addEventListener('scroll', scheduleUpdate, { passive: true })
    window.addEventListener('resize', scheduleUpdate)
    scheduleUpdate()

    return () => {
      target.removeEventListener('scroll', scheduleUpdate)
      window.removeEventListener('resize', scheduleUpdate)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [sections])

  return (
    <div
      ref={pageRef}
      className="mx-auto w-full max-w-[90rem] pb-10 pt-20"
      style={navHeight > 80 ? { paddingTop: navHeight + 12 } : undefined}
    >
      <GuideSectionTabs
        activeSectionId={activeSectionId}
        frame={navFrame}
        navRef={navRef}
        onSelect={scrollToSection}
        sections={sections}
      />
      <GuideArticle guide={guide} />
    </div>
  )
}

function GuideSectionTabs({
  activeSectionId,
  frame,
  navRef,
  onSelect,
  sections,
}: {
  activeSectionId: string
  frame: NavFrame | null
  navRef: RefObject<HTMLDivElement | null>
  onSelect: (sectionId: string) => void
  sections: GuideSection[]
}) {
  if (!sections.length) return null

  return (
    <div
      ref={navRef}
      className="fixed z-30 border-b bg-background py-3 after:pointer-events-none after:absolute after:inset-x-0 after:top-full after:h-4 after:bg-background"
      style={frame ? { left: frame.left, top: frame.top, width: frame.width } : { visibility: 'hidden' }}
    >
      <Tabs value={activeSectionId} onValueChange={onSelect} className="gap-0">
        <div className="-mx-2 px-2 sm:mx-0 sm:px-0">
          <div className="w-full border-b-2 border-border/80 pb-2">
            <TabsList
              aria-label="Guide sections"
              className="flex !h-auto w-full flex-wrap items-start justify-start gap-1.5 rounded-none border-b-0 p-0 group-data-horizontal/tabs:!h-auto 2xl:!h-12 2xl:flex-nowrap 2xl:justify-center 2xl:group-data-horizontal/tabs:!h-12"
              variant="line"
            >
              {sections.map((section) => (
                <TabsTrigger
                  key={section.id}
                  className="h-9 flex-none rounded-md px-3 text-sm sm:px-3.5 2xl:h-11 2xl:px-4 2xl:text-base"
                  value={section.id}
                >
                  {section.title}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
        </div>
      </Tabs>
    </div>
  )
}

function getScrollRoot(element: HTMLElement | null): ScrollRoot {
  const appMain = element?.closest('.app-main')

  if (appMain instanceof HTMLElement && appMain.scrollHeight > appMain.clientHeight + 1) {
    return appMain
  }

  return window
}

function isElementScrollRoot(scrollRoot: ScrollRoot): scrollRoot is HTMLElement {
  return scrollRoot instanceof HTMLElement
}
