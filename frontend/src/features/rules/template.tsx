import { Check, Download, Info } from 'lucide-react'
import { useEffect, useState } from 'react'
import { categoryCountLabel as formatCategoryCount } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

export type RuleTemplateConditionValue = string | number | readonly string[] | readonly number[]

export type RuleTemplateCondition = {
  field: string
  op: string
  value: RuleTemplateConditionValue
}

export type RuleCategoryTemplate = {
  id: string
  name: string
  bucket: string
  description?: string
  conditions: RuleTemplateCondition[]
}

export type RuleTemplate = {
  id: string
  kind: 'organize'
  title: string
  description?: string
  fallbackBucket: string
  categories: RuleCategoryTemplate[]
}

const westernCountries = ['US', 'GB', 'CA', 'AU', 'NZ', 'FR', 'DE', 'ES', 'IT', 'NL', 'PT', 'PL', 'MX', 'RU', 'SE', 'NO', 'DK', 'FI', 'IN'] as const

export const ruleTemplates: RuleTemplate[] = [
  {
    id: 'tmdb-categories',
    kind: 'organize',
    title: 'TMDB分类',
    description: '按 TMDB 类型 ID 和国家/地区整理媒体分类。',
    fallbackBucket: '未分类',
    categories: [
      {
        id: 'category-1-国漫',
        name: 'category-1-国漫',
        bucket: '国漫',
        description: 'Chinese Animation (Donghua)',
        conditions: [
          { field: 'tmdb.genre_ids', op: 'in', value: [16] },
          { field: 'tmdb.origin_country', op: 'in', value: ['CN', 'TW', 'HK'] },
        ],
      },
      {
        id: 'category-2-日番',
        name: 'category-2-日番',
        bucket: '日番',
        description: 'Japanese Anime',
        conditions: [
          { field: 'tmdb.genre_ids', op: 'in', value: [16] },
          { field: 'tmdb.origin_country', op: 'in', value: ['JP', 'KR'] },
        ],
      },
      {
        id: 'category-3-美漫',
        name: 'category-3-美漫',
        bucket: '美漫',
        description: 'Western Animation',
        conditions: [
          { field: 'tmdb.genre_ids', op: 'in', value: [16] },
          { field: 'tmdb.origin_country', op: 'in', value: westernCountries },
        ],
      },
      {
        id: 'category-4-纪录',
        name: 'category-4-纪录',
        bucket: '纪录',
        description: 'Documentary',
        conditions: [{ field: 'tmdb.genre_ids', op: 'in', value: [99] }],
      },
      {
        id: 'category-5-综艺',
        name: 'category-5-综艺',
        bucket: '综艺',
        description: 'Variety/Talk Shows',
        conditions: [{ field: 'tmdb.genre_ids', op: 'in', value: [10764, 10767] }],
      },
      {
        id: 'category-6-华语剧',
        name: 'category-6-华语剧',
        bucket: '华语剧',
        description: 'Chinese Drama',
        conditions: [{ field: 'tmdb.origin_country', op: 'in', value: ['CN', 'TW', 'HK', 'SG'] }],
      },
      {
        id: 'category-7-日韩剧',
        name: 'category-7-日韩剧',
        bucket: '日韩剧',
        description: 'Japanese Drama (excluding anime)',
        conditions: [{ field: 'tmdb.origin_country', op: 'in', value: ['JP', 'KR', 'TH', 'MY', 'PH', 'VN', 'ID'] }],
      },
      {
        id: 'category-8-欧美剧',
        name: 'category-8-欧美剧',
        bucket: '欧美剧',
        description: 'Western Drama (US, UK, Europe)',
        conditions: [{ field: 'tmdb.origin_country', op: 'in', value: westernCountries }],
      },
    ],
  },
  {
    id: 'keyword-categories',
    kind: 'organize',
    title: '关键字分类',
    description: '按路径关键字整理来源格式和发布组分类。',
    fallbackBucket: '其他电影',
    categories: [
      {
        id: 'category-1-REMUX电影',
        name: 'category-1-REMUX电影',
        bucket: 'REMUX电影',
        conditions: [{ field: 'relative_path', op: 'contains', value: 'REMUX' }],
      },
      {
        id: 'category-2-WEB-DL电影',
        name: 'category-2-WEB-DL电影',
        bucket: 'WEB-DL电影',
        conditions: [{ field: 'relative_path', op: 'contains', value: 'WEB-DL' }],
      },
      {
        id: 'category-3-CHDBits小组',
        name: 'category-3-CHDBits小组',
        bucket: 'CHDBits小组',
        conditions: [{ field: 'relative_path', op: 'contains', value: 'CHDBits' }],
      },
      {
        id: 'category-4-BHYS小组',
        name: 'category-4-BHYS小组',
        bucket: 'BHYS小组',
        conditions: [{ field: 'relative_path', op: 'contains', value: 'BHYS' }],
      },
      {
        id: 'category-5-HDSky小组',
        name: 'category-5-HDSky小组',
        bucket: 'HDSky小组',
        conditions: [{ field: 'relative_path', op: 'contains', value: 'HDSky' }],
      },
      {
        id: 'category-6-原盘电影',
        name: 'category-6-原盘电影',
        bucket: '原盘电影',
        conditions: [{ field: 'relative_path', op: 'contains', value: 'ISO' }],
      },
    ],
  },
]

export function organizeRuleTemplates() {
  return ruleTemplates.filter((template) => template.kind === 'organize')
}


export function RuleTemplateDialog({
  open,
  onOpenChange,
  onImport,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onImport: (template: RuleTemplate) => void
}) {
  const { t } = useI18n()
  const templates = organizeRuleTemplates()
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId)

  useEffect(() => {
    if (!open) setSelectedTemplateId('')
  }, [open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl" data-testid="import-template-dialog">
        <DialogHeader>
          <DialogTitle>{t('importRuleTemplate')}</DialogTitle>
          <DialogDescription>{t('importRuleTemplateDescription')}</DialogDescription>
        </DialogHeader>
        <div className="flex gap-2 rounded-lg border border-primary/20 bg-primary/10 p-3 text-sm">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" />
          <div>{t('importRuleTemplateInfo')}</div>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {templates.map((template) => (
            <button
              key={template.id}
              aria-pressed={selectedTemplateId === template.id}
              className={cn(
                'flex min-w-0 flex-col gap-3 rounded-lg border bg-muted/20 p-3 text-left outline-none transition-colors hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring',
                selectedTemplateId === template.id ? 'border-primary bg-primary/10' : 'border-border',
              )}
              data-template-id={template.id}
              type="button"
              onClick={() => setSelectedTemplateId(template.id)}
            >
              <div className="min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <div className="truncate font-medium">{template.title}</div>
                  {selectedTemplateId === template.id ? <Check className="size-4 text-primary" /> : null}
                </div>
                {template.description ? <div className="mt-1 text-sm text-muted-foreground">{template.description}</div> : null}
              </div>
              <div className="flex flex-wrap gap-1">
                <Badge>{formatCategoryCount(t, template.categories.length)}</Badge>
                <Badge>{t('bucketLabel', { bucket: template.fallbackBucket || '(root)' })}</Badge>
              </div>
              <div className="flex flex-wrap gap-1">
                {template.categories.slice(0, 6).map((category) => (
                  <Badge key={category.id}>{category.bucket}</Badge>
                ))}
                {template.categories.length > 6 ? <Badge>{t('moreCount', { count: template.categories.length - 6 })}</Badge> : null}
              </div>
            </button>
          ))}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>{t('cancel')}</Button>
          <Button data-testid="import-template-submit" disabled={!selectedTemplate} onClick={() => selectedTemplate && onImport(selectedTemplate)}>
            <Download data-icon="inline-start" />
            {t('importTemplate')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
