import { useState } from 'react'
import { Link, useLocation } from '@tanstack/react-router'
import type { LucideIcon } from 'lucide-react'
import { Activity, ArrowRight, BookOpen, FolderInput, Gauge, Menu, SlidersHorizontal, Workflow } from 'lucide-react'
import { useI18n } from '@/app/providers/I18nProvider'
import type { MessageKey } from '@/app/i18n/messages'
import { useLocale, type Locale } from '@/app/providers/LocaleProvider'
import { Button } from '@/components/common/Button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

type NavTo = '/dashboard' | '/organize' | '/services' | '/transfer' | '/activity' | '/settings'
type NavItem = { to: NavTo; labelKey: MessageKey; icon: LucideIcon }

const navItemClass =
  'flex min-h-12 w-full items-center gap-3 rounded-lg px-3 py-2.5 text-base font-medium leading-6 text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground'
const navIconClass = 'size-7 shrink-0 stroke-[1.8]'
const languageOptions: { value: Locale; labelKey: MessageKey; shortLabel: string }[] = [
  { value: 'zh-CN', labelKey: 'languageChinese', shortLabel: 'ZH' },
  { value: 'en-US', labelKey: 'languageEnglish', shortLabel: 'EN' },
]

const primaryNavItems: NavItem[] = [
  { to: '/dashboard', labelKey: 'navDashboard', icon: Gauge },
  { to: '/organize', labelKey: 'navOrganize', icon: FolderInput },
  { to: '/transfer', labelKey: 'navTransfer', icon: ArrowRight },
  { to: '/services', labelKey: 'navServices', icon: Workflow },
]

const secondaryNavItems: NavItem[] = [
  { to: '/activity', labelKey: 'navActivity', icon: Activity },
  { to: '/settings', labelKey: 'navSettings', icon: SlidersHorizontal },
]

export function Sidebar() {
  const location = useLocation()
  const { t } = useI18n()

  return (
    <aside className="flex h-auto flex-col gap-5 border-b bg-sidebar p-4 text-sidebar-foreground md:sticky md:top-0 md:h-screen md:border-b-0 md:border-r">
      <div className="flex min-h-12 items-center px-3 pt-2 pb-5" aria-label={t('appName')}>
        <span className="omedia-wordmark">OMEDIA</span>
      </div>
      <SidebarNavigation currentPath={location.pathname} />
      <SidebarFooter currentPath={location.pathname} />
    </aside>
  )
}

export function MobileNavigation() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const { t } = useI18n()
  const closeMenu = () => setOpen(false)
  const menuLabel = t('openLabel', { label: t('navPrimaryWorkflows') })

  return (
    <>
      <header className="sticky top-0 z-40 flex min-h-14 items-center gap-2.5 border-b bg-sidebar px-4 text-sidebar-foreground">
        <Button
          aria-label={menuLabel}
          className="size-9 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          onClick={() => setOpen(true)}
          title={menuLabel}
          variant="ghost"
        >
          <Menu className="size-[1.375rem]" />
        </Button>
        <span className="omedia-wordmark">OMEDIA</span>
      </header>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="top-0 left-0 flex h-dvh w-[min(20rem,calc(100vw-2rem))] max-w-none translate-x-0 translate-y-0 flex-col gap-5 overflow-y-auto rounded-none rounded-r-xl bg-sidebar p-4 text-sidebar-foreground sm:max-w-none">
          <DialogTitle className="sr-only">{t('navPrimaryWorkflows')}</DialogTitle>
          <DialogDescription className="sr-only">{menuLabel}</DialogDescription>
          <div className="flex min-h-12 items-center px-3 pt-2 pb-5" aria-label={t('appName')}>
            <span className="omedia-wordmark">OMEDIA</span>
          </div>
          <SidebarNavigation currentPath={location.pathname} onNavigate={closeMenu} />
          <SidebarFooter currentPath={location.pathname} onNavigate={closeMenu} />
        </DialogContent>
      </Dialog>
    </>
  )
}

function SidebarNavigation({ currentPath, onNavigate }: { currentPath: string; onNavigate?: () => void }) {
  const { t } = useI18n()

  return (
    <nav className="flex flex-col gap-4" aria-label={t('navPrimaryWorkflows')}>
      <NavSection title={t('navPrimaryWorkflows')} items={primaryNavItems} currentPath={currentPath} onNavigate={onNavigate} />
      <NavSection title={t('navSecondaryDestinations')} items={secondaryNavItems} currentPath={currentPath} onNavigate={onNavigate} />
    </nav>
  )
}

function SidebarFooter({ currentPath, onNavigate }: { currentPath: string; onNavigate?: () => void }) {
  const { t } = useI18n()

  return (
    <div className="mt-auto flex items-center justify-between gap-3 border-t px-3 pt-4">
      <LanguageSwitcher />
      <HelpButton active={currentPath === '/help'} label={t('getHelp')} onNavigate={onNavigate} />
    </div>
  )
}

function LanguageSwitcher() {
  const { locale, setLocale } = useLocale()
  const { t } = useI18n()

  return (
    <div className="grid h-9 w-24 grid-cols-2 rounded-lg border border-sidebar-border bg-background/40 p-0.5" aria-label={t('language')} role="group">
      {languageOptions.map((option) => {
        const selected = locale === option.value

        return (
          <button
            key={option.value}
            aria-label={t(option.labelKey)}
            aria-pressed={selected}
            className={cn(
              'rounded-md px-2 text-xs font-semibold leading-none text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring',
              selected && 'bg-sidebar-accent text-sidebar-accent-foreground shadow-sm',
            )}
            type="button"
            onClick={() => setLocale(option.value)}
          >
            {option.shortLabel}
          </button>
        )
      })}
    </div>
  )
}

function NavSection({ title, items, currentPath, onNavigate }: { title: string; items: NavItem[]; currentPath: string; onNavigate?: () => void }) {
  const { t } = useI18n()
  return (
    <div className="flex flex-col gap-2">
      <div className="px-3 text-[0.8rem] font-extrabold uppercase leading-5 tracking-normal text-muted-foreground">{title}</div>
      {items.map((item) => (
        <NavLink
          key={item.to}
          active={currentPath === item.to || currentPath.startsWith(`${item.to}/`)}
          icon={item.icon}
          label={t(item.labelKey)}
          onNavigate={onNavigate}
          to={item.to}
        />
      ))}
    </div>
  )
}

function NavLink({ to, active, icon: Icon, label, onNavigate }: { to: NavTo; active: boolean; icon: LucideIcon; label: string; onNavigate?: () => void }) {
  return (
    <Link
      className={navItemClass}
      data-active={active}
      onClick={onNavigate}
      to={to}
    >
      <Icon className={navIconClass} />
      <span className="truncate">{label}</span>
    </Link>
  )
}

function HelpButton({ active, label, onNavigate }: { active: boolean; label: string; onNavigate?: () => void }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Link
          aria-label={label}
          className={cn(
            'inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring',
            active && 'bg-sidebar-accent text-sidebar-accent-foreground',
          )}
          data-active={active}
          onClick={onNavigate}
          title={label}
          to="/help"
        >
          <BookOpen className="size-6 stroke-[1.8]" />
        </Link>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}
