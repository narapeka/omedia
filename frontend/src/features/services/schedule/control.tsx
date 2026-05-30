import { useEffect, useMemo, useRef, useState } from 'react'
import { useI18n } from '@/app/providers/I18nProvider'
import { Button } from '@/components/common/Button'
import { SelectControl } from '@/components/common/SelectControl'
import { Input } from '@/components/ui/input'
import {
  buildCronSchedule,
  clampMonthDay,
  parseCronSchedule,
  weekdayOptions,
  type CronDraft,
  type ScheduleMode,
} from './model'

export function CronScheduleControl({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { t } = useI18n()
  const parsed = useMemo(() => parseCronSchedule(value), [value])
  const localizedWeekdays = useMemo(() => weekdayOptions(t), [t])
  const rootRef = useRef<HTMLDivElement>(null)
  const helperOpenBeforeInputPointer = useRef(false)
  const [helperOpen, setHelperOpen] = useState(false)
  const [rawEditing, setRawEditing] = useState(parsed.mode === 'advanced' && value.trim().length > 0)
  const [mode, setMode] = useState<ScheduleMode>(parsed.mode)
  const [time, setTime] = useState(parsed.time)
  const [weekday, setWeekday] = useState(parsed.weekday)
  const [monthDay, setMonthDay] = useState(parsed.monthDay)

  useEffect(() => {
    const next = parseCronSchedule(value)
    setMode(next.mode)
    setTime(next.time)
    setWeekday(next.weekday)
    setMonthDay(next.monthDay)
    setRawEditing((current) => current || (value.trim().length > 0 && next.mode === 'advanced'))
  }, [value])

  useEffect(() => {
    if (!helperOpen) return

    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (event.target instanceof Node && rootRef.current?.contains(event.target)) return
      if (event.target instanceof Element && event.target.closest('[data-slot="select-content"]')) return
      helperOpenBeforeInputPointer.current = false
      if (parseCronSchedule(value).mode !== 'advanced') setRawEditing(false)
      setHelperOpen(false)
    }

    document.addEventListener('pointerdown', closeOnOutsidePointer)
    return () => document.removeEventListener('pointerdown', closeOnOutsidePointer)
  }, [helperOpen, value])

  const applyHelper = (next: Partial<CronDraft>) => {
    const merged = {
      mode,
      time,
      weekday,
      monthDay,
      ...next,
    }
    setMode(merged.mode)
    setTime(merged.time)
    setWeekday(merged.weekday)
    setMonthDay(merged.monthDay)
    if (merged.mode !== 'advanced') {
      setRawEditing(false)
      onChange(buildCronSchedule(merged))
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <div className="flex items-center gap-2">
        <Input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onPointerDown={() => {
            helperOpenBeforeInputPointer.current = helperOpen
          }}
          onFocus={() => {
            if (!rawEditing || !value.trim()) setHelperOpen(true)
          }}
          onClick={() => {
            if (helperOpenBeforeInputPointer.current && !rawEditing) {
              setRawEditing(true)
              setHelperOpen(false)
              return
            }
            if (!rawEditing || !value.trim()) setHelperOpen(true)
          }}
          readOnly={!rawEditing}
          placeholder="5 4 * * *"
          aria-label={t('transferCronSchedule')}
          className="font-mono"
        />
      </div>
      {helperOpen ? (
        <div className="absolute right-0 top-full z-50 mt-2 w-full min-w-[300px] rounded-lg border bg-popover p-3 text-popover-foreground shadow-lg">
          <div className="flex flex-wrap gap-2">
            {(['daily', 'weekly', 'monthly'] as const).map((item) => (
              <Button
                key={item}
                size="sm"
                variant={mode === item ? 'secondary' : 'ghost'}
                onClick={() => applyHelper({ mode: item })}
              >
                {item === 'daily' ? t('daily') : item === 'weekly' ? t('weekly') : t('monthly')}
              </Button>
            ))}
          </div>
          {mode !== 'advanced' ? (
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                {t('time')}
                <Input type="time" value={time} onChange={(event) => applyHelper({ time: event.target.value || '04:00' })} />
              </label>
              {mode === 'weekly' ? (
                <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                  {t('day')}
                  <SelectControl
                    value={weekday}
                    onValueChange={(nextWeekday) => applyHelper({ weekday: nextWeekday })}
                    options={localizedWeekdays}
                  />
                </label>
              ) : null}
              {mode === 'monthly' ? (
                <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                  {t('dayOfMonth')}
                  <Input
                    inputMode="numeric"
                    min={1}
                    max={31}
                    type="number"
                    value={monthDay}
                    onChange={(event) => applyHelper({ monthDay: clampMonthDay(event.target.value) })}
                  />
                </label>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
