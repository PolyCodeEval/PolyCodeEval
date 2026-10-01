import { normalizeTokens } from '../../shared/lib/benchmark'
import { useJson } from '../../shared/hooks/data'
import type { TokenRow } from '../../shared/types/benchmark'
import type { TokenFilters } from './tokens.types'

export function useTokenData() {
  return useJson('tokens/accounting.json', normalizeTokens, [])
}

export function filterTokenRows(rows: TokenRow[], filters: TokenFilters) {
  return rows.filter(
    (row) =>
      (!filters.level || row.level === filters.level) &&
      (!filters.method || row.method === filters.method) &&
      (!filters.model || row.model === filters.model) &&
      (!filters.language || row.language === filters.language),
  )
}

export function sumTokenField(rows: TokenRow[], key: keyof TokenRow) {
  return rows.reduce((sum, row) => sum + Number(row[key] ?? 0), 0)
}
