import type { ReactNode } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useI18n } from '@/app/providers/I18nProvider'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'

export function CollapsibleSection({
  children,
  description,
  footer,
  open,
  title,
  onOpenChange,
}: {
  children: ReactNode
  description?: ReactNode
  footer?: ReactNode
  open: boolean
  title: ReactNode
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useI18n()
  const label = typeof title === 'string' ? title : ''
  return (
    <Card className="overflow-visible">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle>{title}</CardTitle>
            {description ? <CardDescription>{description}</CardDescription> : null}
          </div>
          <Button
            aria-expanded={open}
            aria-label={open ? t('collapseLabel', { label }) : t('expandLabel', { label })}
            size="icon-sm"
            variant="ghost"
            onClick={() => onOpenChange(!open)}
          >
            {open ? <ChevronUp /> : <ChevronDown />}
          </Button>
        </div>
      </CardHeader>
      {open ? <CardContent className="p-0">{children}</CardContent> : null}
      {open && footer ? <CardFooter className="justify-end">{footer}</CardFooter> : null}
    </Card>
  )
}
