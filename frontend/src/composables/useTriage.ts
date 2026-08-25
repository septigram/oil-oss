import { fetchIncidentDetail, updateIncident } from '@/api/client'
import type { ChatProposalEvent } from '@/api/client'

const INCIDENT_UPDATE_FIELDS = [
  'type_id',
  'occurred_at',
  'title',
  'description',
  'location_name',
  'affected_service_ids',
  'detector_employee_id',
  'detector_department_id',
  'severity',
  'status',
  'detection_source',
  'related_event_id',
] as const

type IncidentRecord = Record<string, unknown>

function pickIncidentBase(inc: IncidentRecord): IncidentRecord {
  const base: IncidentRecord = {}
  for (const key of INCIDENT_UPDATE_FIELDS) {
    if (key in inc) {
      base[key] = inc[key]
    }
  }
  return base
}

export function buildTriageStartMessage(): string {
  return 'このインシデントのトリアージを開始してください。入力項目の確認と重要度の提案をお願いします。'
}

export function buildWidgetAnswerMessage(widgetId: string, answer: string): string {
  return `[widget:${widgetId}] ${answer}`
}

export async function applyProposalToIncident(
  incidentId: string,
  proposal: ChatProposalEvent,
): Promise<void> {
  const detail = await fetchIncidentDetail(incidentId)
  const source = detail.incident as IncidentRecord
  const inc = pickIncidentBase(source)
  const rowVersion = Number(source.row_version ?? 1)
  let customerIds = (detail.customers ?? []).map((c: { customer_id: string }) => c.customer_id)
  let detectedAt: string | undefined

  const field = proposal.field
  const value = proposal.proposed

  if (field === 'severity' || field === 'type_id' || field === 'location_name') {
    inc[field] = value
  } else if (field === 'occurred_at') {
    inc.occurred_at = value
  } else if (field === 'detected_at') {
    detectedAt = String(value)
  } else if (field === 'affected_service_ids') {
    inc.affected_service_ids = Array.isArray(value) ? value : [String(value)]
  } else if (field === 'customer_ids') {
    customerIds = Array.isArray(value) ? value.map(String) : [String(value)]
  } else {
    throw new Error(`未対応のフィールド: ${field}`)
  }

  const body: Record<string, unknown> = {
    incident: inc,
    customer_ids: customerIds,
    row_version: rowVersion,
  }
  if (detectedAt) {
    body.detected_at = detectedAt
  }
  await updateIncident(incidentId, body)
}
