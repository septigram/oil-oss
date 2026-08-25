import { describe, expect, it, vi } from 'vitest'
import {
  applyProposalToIncident,
  buildTriageStartMessage,
  buildWidgetAnswerMessage,
} from '@/composables/useTriage'

vi.mock('@/api/client', () => ({
  fetchIncidentDetail: vi.fn(),
  updateIncident: vi.fn(),
}))

import { fetchIncidentDetail, updateIncident } from '@/api/client'

const baseIncident = {
  type_id: 'ITYP-001',
  occurred_at: '2026-06-25T12:19:00+00:00',
  title: 'S3 ログ保存障害',
  description: '6/25にS3が溢れ',
  location_name: 'Mercury AWS AP',
  affected_service_ids: ['SVC-001'],
  detector_employee_id: 'EMP-00001',
  detector_department_id: 'DEPT-OPS',
  severity: 'LOW',
  status: 'OPEN',
  detection_source: 'OPS_MONITORING',
  related_event_id: null,
  row_version: 3,
  incident_id: 'INC-2026-00791',
}

describe('useTriage helpers', () => {
  it('builds triage start message', () => {
    expect(buildTriageStartMessage()).toContain('トリアージ')
  })

  it('builds widget answer message', () => {
    expect(buildWidgetAnswerMessage('w1', 'HIGH')).toBe('[widget:w1] HIGH')
  })

  it('applyProposalToIncident sends row_version and incident base fields only', async () => {
    vi.mocked(fetchIncidentDetail).mockResolvedValue({
      incident: baseIncident,
      customers: [],
    })
    vi.mocked(updateIncident).mockResolvedValue({ incident_id: 'INC-2026-00791' })

    await applyProposalToIncident('INC-2026-00791', {
      type: 'proposal',
      proposal_id: 'p1',
      field: 'severity',
      current: 'LOW',
      proposed: 'HIGH',
      reason: 'test',
      confidence: 'high',
    })

    expect(updateIncident).toHaveBeenCalledWith('INC-2026-00791', {
      incident: {
        type_id: 'ITYP-001',
        occurred_at: '2026-06-25T12:19:00+00:00',
        title: 'S3 ログ保存障害',
        description: '6/25にS3が溢れ',
        location_name: 'Mercury AWS AP',
        affected_service_ids: ['SVC-001'],
        detector_employee_id: 'EMP-00001',
        detector_department_id: 'DEPT-OPS',
        severity: 'HIGH',
        status: 'OPEN',
        detection_source: 'OPS_MONITORING',
        related_event_id: null,
      },
      customer_ids: [],
      row_version: 3,
    })
  })
})
