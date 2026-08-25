import { describe, expect, it } from 'vitest'
import { createIncidentTablePagination } from '@/components/incidentTablePagination'

describe('createIncidentTablePagination', () => {
  it('sets rowsNumber for Quasar server-side pagination', () => {
    expect(createIncidentTablePagination(2, 10, 35)).toEqual({
      page: 2,
      rowsPerPage: 10,
      rowsNumber: 35,
    })
  })
})
