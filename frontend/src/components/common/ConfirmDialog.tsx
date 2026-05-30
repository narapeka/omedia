import { Info } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@/components/common/Button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useI18n } from '@/app/providers/I18nProvider'
import { cn } from '@/lib/utils'

export type ConfirmDialogState = {
  title: string
  description: string
  confirmLabel?: string
  destructive?: boolean
  confirmDisabled?: boolean
  notice?: {
    tone: 'info' | 'warning'
    message: ReactNode
  }
  onConfirm: () => void | Promise<void>
}

export function ConfirmDialog({
  state,
  onOpenChange,
}: {
  state: ConfirmDialogState | null
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useI18n()
  const open = Boolean(state)
  const confirmDisabled = Boolean(state?.confirmDisabled)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{state?.title ?? t('confirm')}</DialogTitle>
          {state?.description ? <DialogDescription>{state.description}</DialogDescription> : null}
        </DialogHeader>
        {state?.notice ? (
          <Alert
            className={cn(
              state.notice.tone === 'warning'
                ? 'border-amber-500/30 bg-amber-500/10 text-amber-950 dark:text-amber-100'
                : 'border-border bg-muted/30 text-foreground',
            )}
          >
            <Info />
            <AlertDescription
              className={cn(
                'whitespace-pre-line',
                state.notice.tone === 'warning'
                  ? 'text-amber-950/90 dark:text-amber-100/90'
                  : 'text-muted-foreground',
              )}
            >
              {state.notice.message}
            </AlertDescription>
          </Alert>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('cancel')}
          </Button>
          <Button
            variant={state?.destructive ? 'danger' : 'primary'}
            disabled={confirmDisabled}
            onClick={() => {
              if (!state || confirmDisabled) return
              void Promise.resolve(state.onConfirm()).finally(() => onOpenChange(false))
            }}
          >
            {state?.confirmLabel ?? t('confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
