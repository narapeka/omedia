import { describe, expect, it } from 'vitest'
import type { OrganizeRule } from '@/api/types'
import {
  conditionWithField,
  conditionWithOperator,
  formatReferenceValue,
  fromDraft,
  generatedCategoryNames,
  pruneBlankConditions,
  selectedReferenceValues,
  toDraft,
  validateRuleDraft,
} from '@/features/rules/draft'

const t = (key: string) => key

describe('rules draft model', () => {
  it('round-trips API rules through editable drafts and mutation payloads', () => {
    const draft = toDraft({
      id: 'rule-1',
      name: 'Movie rule',
      description: null,
      fallback_bucket: 'Other',
      categories: [
        {
          name: 'ignored-contract-name',
          bucket: 'Action / Adventure',
          conditions: [{ field: 'tmdb.genre_ids', op: 'in', value: [28, 12] }],
        },
      ],
    } satisfies OrganizeRule)

    expect(draft.categories[0].conditions[0].value).toBe('[28,12]')
    expect(fromDraft(draft)).toEqual({
      name: 'Movie rule',
      description: null,
      fallback_bucket: 'Other',
      categories: [
        {
          name: 'category-1-Action-Adventure',
          bucket: 'Action / Adventure',
          conditions: [{ field: 'tmdb.genre_ids', op: 'in', value: [28, 12] }],
        },
      ],
    })
  })

  it('normalizes category names and reference values', () => {
    expect(generatedCategoryNames([
      { name: '', bucket: 'Drama', conditions: [] },
      { name: '', bucket: 'Drama', conditions: [] },
      { name: '', bucket: '', conditions: [] },
    ])).toEqual(['category-1-Drama', 'category-2-Drama', 'category-3'])

    expect(selectedReferenceValues({ field: 'tmdb.origin_country', op: 'in', value: '["us"," jp "]' })).toEqual(['US', 'JP'])
    expect(formatReferenceValue('tmdb.genre_ids', 'in', ['28', '12'])).toBe('[28, 12]')
    expect(formatReferenceValue('tmdb.origin_country', 'contains', [' jp '])).toBe('JP')
  })

  it('keeps condition operators valid when fields and operators change', () => {
    expect(conditionWithField('organize', { field: 'tmdb.genre_ids', op: 'in', value: '[28]' }, 'relative_path')).toEqual({
      field: 'relative_path',
      op: '',
      value: '',
    })
    expect(conditionWithOperator({ field: 'relative_path', op: 'contains', value: 'Avatar' }, 'in')).toEqual({
      field: 'relative_path',
      op: 'in',
      value: '["Avatar"]',
    })
  })

  it('validates and prunes draft conditions', () => {
    expect(validateRuleDraft({ id: '', name: '', description: '', fallback_bucket: '', categories: [] }, 'organize', t)).toBe('ruleNameRequired')
    expect(validateRuleDraft({
      id: '',
      name: 'Rule',
      description: '',
      fallback_bucket: '',
      categories: [{ name: '', bucket: 'Drama', conditions: [{ field: 'relative_path', op: 'equals', value: 'Avatar' }] }],
    }, 'organize', t)).toBe('conditionOperatorUnsupported')

    expect(pruneBlankConditions({
      id: '',
      name: 'Rule',
      description: '',
      fallback_bucket: '',
      categories: [
        {
          name: '',
          bucket: 'Drama',
          conditions: [
            { field: '', op: '', value: '' },
            { field: 'relative_path', op: 'contains', value: 'Avatar' },
          ],
        },
      ],
    }).categories[0].conditions).toEqual([{ field: 'relative_path', op: 'contains', value: 'Avatar' }])
  })
})
