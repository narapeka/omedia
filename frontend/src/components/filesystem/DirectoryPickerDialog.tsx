import { Fragment, useEffect, useState } from 'react'
import { Folder } from 'lucide-react'
import { useI18n } from '@/app/providers/I18nProvider'
import { Button } from '@/components/common/Button'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useDirectoryListing } from './api'

export function DirectoryPickerDialog({
  open,
  title,
  description,
  initialPath,
  confirmLabel,
  onOpenChange,
  onSelect,
}: {
  open: boolean
  title?: string
  description?: string | null
  initialPath?: string | null
  confirmLabel?: string
  onOpenChange: (open: boolean) => void
  onSelect: (path: string) => void
}) {
  const { t } = useI18n()
  const [currentPath, setCurrentPath] = useState('')
  const listing = useDirectoryListing(currentPath, open)
  const activePath = listing.data?.path ?? ''
  const canSelect = Boolean(activePath && !listing.data?.error)
  const breadcrumbs = directoryBreadcrumbs(activePath)

  useEffect(() => {
    if (!open) return
    const nextPath = initialPath?.trim() ?? ''
    setCurrentPath(nextPath)
  }, [initialPath, open])

  const select = () => {
    if (!canSelect) return
    onSelect(activePath)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title ?? t('chooseFolder')}</DialogTitle>
          <DialogDescription className={description === null ? 'sr-only' : undefined}>
            {description ?? t('browseServerFolders')}
          </DialogDescription>
        </DialogHeader>

        <div className="flex min-h-0 flex-col gap-3">
          <DirectoryBreadcrumb path={activePath} segments={breadcrumbs} loading={listing.isFetching} onNavigate={setCurrentPath} />

          {listing.isLoading || listing.isFetching ? <div className="py-3 text-sm text-muted-foreground">{t('loadingFolders')}</div> : null}
          {listing.error ? <div className="text-sm text-destructive">{errorMessage(listing.error, t('couldNotLoadFolders'))}</div> : null}
          {listing.data?.error ? <div className="text-sm text-destructive">{listing.data.error}</div> : null}

          <div className="min-h-0 overflow-y-auto overflow-x-hidden rounded-md border">
            {(listing.data?.entries ?? []).map((entry) => (
              <button
                key={entry.path}
                type="button"
                className="flex w-full min-w-0 max-w-full items-center gap-2 border-b px-3 py-2 text-left text-sm last:border-b-0 hover:bg-muted/50 disabled:cursor-not-allowed disabled:text-muted-foreground"
                disabled={Boolean(entry.blocked_reason)}
                onClick={() => setCurrentPath(entry.path)}
              >
                <Folder className="size-4 shrink-0 text-muted-foreground" />
                <span className="block min-w-0 flex-1 truncate" title={entry.path}>
                  {entry.name}
                </span>
                {entry.blocked_reason ? <span className="text-xs text-destructive">{entry.blocked_reason}</span> : null}
              </button>
            ))}
            {!listing.isLoading && !listing.isFetching && (listing.data?.entries ?? []).length === 0 ? (
              <div className="px-3 py-6 text-center text-sm text-muted-foreground">{t('noChildFolders')}</div>
            ) : null}
          </div>
        </div>

        <DialogFooter className="shrink-0">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t('cancel')}
          </Button>
          <Button onClick={select} disabled={!canSelect}>
            {confirmLabel ?? t('useThisFolder')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DirectoryBreadcrumb({
  path,
  segments,
  loading,
  onNavigate,
}: {
  path: string
  segments: DirectoryBreadcrumbSegment[]
  loading: boolean
  onNavigate: (path: string) => void
}) {
  const { t } = useI18n()
  return (
    <Breadcrumb aria-label={t('directoryPath')} className="rounded-md border bg-muted/20 px-3 py-2">
      <BreadcrumbList className="flex-nowrap overflow-x-auto">
        <BreadcrumbItem>
          {path ? (
            <BreadcrumbLink asChild>
              <button className="whitespace-nowrap" type="button" disabled={loading} onClick={() => onNavigate('')}>
                {t('roots')}
              </button>
            </BreadcrumbLink>
          ) : (
            <BreadcrumbPage>{t('roots')}</BreadcrumbPage>
          )}
        </BreadcrumbItem>
        {segments.map((segment, index) => {
          const isCurrent = index === segments.length - 1
          return (
            <Fragment key={`${segment.path}-${index}`}>
              <BreadcrumbSeparator />
              <BreadcrumbItem className="min-w-0">
                {isCurrent ? (
                  <BreadcrumbPage className="max-w-48 truncate" title={segment.path}>
                    {segment.label}
                  </BreadcrumbPage>
                ) : (
                  <BreadcrumbLink asChild>
                    <button className="max-w-40 truncate" type="button" disabled={loading} title={segment.path} onClick={() => onNavigate(segment.path)}>
                      {segment.label}
                    </button>
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
            </Fragment>
          )
        })}
      </BreadcrumbList>
    </Breadcrumb>
  )
}

type DirectoryBreadcrumbSegment = {
  label: string
  path: string
}

function directoryBreadcrumbs(path: string): DirectoryBreadcrumbSegment[] {
  const cleanPath = path.trim()
  if (!cleanPath) return []

  const windowsDrive = cleanPath.match(/^([A-Za-z]:)[\\/]*(.*)$/)
  if (windowsDrive) {
    const [, drive, rest = ''] = windowsDrive
    return buildSegments([drive, ...splitPath(rest)], `${drive}/`)
  }

  if (cleanPath.startsWith('\\\\') || cleanPath.startsWith('//')) {
    const parts = splitPath(cleanPath)
    if (parts.length >= 2) {
      const share = `//${parts[0]}/${parts[1]}`
      return buildSegments([share, ...parts.slice(2)], share)
    }
  }

  if (cleanPath.startsWith('/') || cleanPath.startsWith('\\')) {
    return buildSegments(['/', ...splitPath(cleanPath)], '/')
  }

  return buildSegments(splitPath(cleanPath), '')
}

function splitPath(path: string) {
  return path.replace(/^[\\/]+|[\\/]+$/g, '').split(/[\\/]+/).filter(Boolean)
}

function buildSegments(parts: string[], rootPath: string): DirectoryBreadcrumbSegment[] {
  let currentPath = rootPath
  return parts.map((part, index) => {
    if (index === 0) {
      currentPath = rootPath || part
      return { label: part, path: rootPath || part }
    }
    currentPath = joinServerPath(currentPath, part)
    return { label: part, path: currentPath }
  })
}

function joinServerPath(basePath: string, child: string) {
  if (!basePath || basePath === '/') return `/${child}`
  return `${basePath.replace(/[\\/]+$/g, '')}/${child}`
}

function errorMessage(error: unknown, fallback: string) {
  if (error instanceof Error) return error.message
  return fallback
}
