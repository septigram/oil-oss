export interface IncidentTablePagination {
  page: number
  rowsPerPage: number
  rowsNumber: number
}

/** Quasar QTable のサーバー側ページネーション用オブジェクト */
export function createIncidentTablePagination(
  page: number,
  pageSize: number,
  total: number,
): IncidentTablePagination {
  return {
    page,
    rowsPerPage: pageSize,
    rowsNumber: total,
  }
}
