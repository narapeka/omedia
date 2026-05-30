import { describe, expect, it } from 'vitest'
import type { TransferRule } from '@/api/types'
import { previewTransferRelativePath } from '@/features/transfer/depot/model'

describe('transfer preview', () => {
  it('matches relative path conditions without case sensitivity', () => {
    const rule: TransferRule = {
      id: 'case-rule',
      name: 'Case rule',
      fallback_bucket: 'Other',
      categories: [
        {
          name: 'movie',
          bucket: 'Matched',
          conditions: [
            { field: 'relative_path', op: 'contains', value: 'avatar' },
            { field: 'relative_path', op: 'matches', value: String.raw`\.mkv$` },
          ],
        },
      ],
    }

    expect(previewTransferRelativePath('欧美电影/Avatar (2009) {tmdb-19995}/AVATAR.MKV', rule)).toBe(
      '欧美电影/Matched/Avatar (2009) {tmdb-19995}/AVATAR.MKV',
    )
  })
})
