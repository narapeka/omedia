import type { CSSProperties } from 'react'
import { CircleCheckIcon, InfoIcon, Loader2Icon, OctagonXIcon, TriangleAlertIcon } from 'lucide-react'
import { Toaster as Sonner, type ToasterProps } from 'sonner'

const DEFAULT_TOAST_DURATION_MS = 8000

const Toaster = ({ duration = DEFAULT_TOAST_DURATION_MS, style, toastOptions, ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="dark"
      className="toaster group"
      duration={duration}
      icons={{
        success: (
          <CircleCheckIcon className="size-4" />
        ),
        info: (
          <InfoIcon className="size-4" />
        ),
        warning: (
          <TriangleAlertIcon className="size-4" />
        ),
        error: (
          <OctagonXIcon className="size-4" />
        ),
        loading: (
          <Loader2Icon className="size-4 animate-spin" />
        ),
      }}
      style={
        {
          '--normal-bg': 'var(--popover)',
          '--normal-text': 'var(--popover-foreground)',
          '--normal-border': 'var(--border)',
          '--border-radius': 'var(--radius)',
          '--toast-close-button-start': 'unset',
          '--toast-close-button-end': '0',
          '--toast-close-button-transform': 'translate(35%, -35%)',
          ...style,
        } as CSSProperties
      }
      toastOptions={{
        ...toastOptions,
        classNames: {
          toast: 'cn-toast',
          ...toastOptions?.classNames,
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
