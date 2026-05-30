import { Download, Upload } from 'lucide-react'
import { useI18n } from '@/app/providers/I18nProvider'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { fieldCaptionClassName } from '../field'
import { MaintenanceActionBlock } from './prune'

export function BackupRestoreCard({
  restoreFile,
  backingUp,
  restoring,
  onRestoreFileChange,
  onBackup,
  onRestore,
}: {
  restoreFile: File | null
  backingUp: boolean
  restoring: boolean
  onRestoreFileChange: (file: File | null) => void
  onBackup: () => void
  onRestore: () => void
}) {
  const { t } = useI18n()
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>{t('backupRestore')}</CardTitle>
        <CardDescription>{t('backupRestoreDescription')}</CardDescription>
      </CardHeader>
      <CardContent className="flex h-full flex-col gap-4">
        <MaintenanceActionBlock title={t('backupConfig')} description={t('backupConfigDescription')}>
          <Button className="omedia-backup-action w-full" onClick={onBackup} disabled={backingUp}>
            <Download data-icon="inline-start" />
            {t('backupConfig')}
          </Button>
        </MaintenanceActionBlock>

        <MaintenanceActionBlock title={t('restoreConfig')} description={t('restoreConfigDescription')}>
          <FieldGroup>
            <Field>
              <Input id="restore-config-file" type="file" accept=".yaml,.yml,text/yaml,application/x-yaml" onChange={(event) => onRestoreFileChange(event.target.files?.[0] ?? null)} />
              <FieldLabel htmlFor="restore-config-file" className={fieldCaptionClassName}>{t('backupFile')}</FieldLabel>
            </Field>
            <Button className="w-full" variant="danger" onClick={onRestore} disabled={!restoreFile || restoring}>
              <Upload data-icon="inline-start" />
              {t('restoreConfig')}
            </Button>
          </FieldGroup>
        </MaintenanceActionBlock>
      </CardContent>
    </Card>
  )
}

export function downloadYaml(content: string, filename: string) {
  const blob = new Blob([content], { type: 'application/x-yaml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
