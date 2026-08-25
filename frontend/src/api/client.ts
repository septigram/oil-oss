import axios, { isAxiosError, type AxiosError } from 'axios'

const apiRoot =
  import.meta.env.VITE_API_BASE_URL || import.meta.env.BASE_URL.replace(/\/$/, '')

export const api = axios.create({
  baseURL: apiRoot,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
  paramsSerializer: {
    indexes: null,
  },
})

export type UnauthorizedHandler = (url: string) => void

let unauthorizedHandler: UnauthorizedHandler | null = null

export function registerUnauthorizedHandler(handler: UnauthorizedHandler) {
  unauthorizedHandler = handler
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const url = String(error.config?.url ?? '')
    if (status === 401 && unauthorizedHandler && !url.includes('/auth/me') && !url.includes('/auth/login')) {
      unauthorizedHandler(url)
    }
    return Promise.reject(error)
  },
)

export function isAxios401(err: unknown): boolean {
  return isAxiosError(err) && err.response?.status === 401
}

export interface OptimisticLockConflictBody {
  detail: 'conflict'
  message: string
  current: Record<string, unknown>
}

export function isOptimisticLockConflict(
  err: unknown,
): err is AxiosError<OptimisticLockConflictBody> {
  if (!isAxiosError(err) || err.response?.status !== 409) return false
  const data = err.response.data
  return !!data && typeof data === 'object' && (data as OptimisticLockConflictBody).detail === 'conflict'
}

export interface UserSummary {
  user_id: string
  employee_id: string
  display_name: string
  roles: string[]
}

export interface AdminUserListItem {
  user_id: string
  employee_id: string
  employee_name: string
  login_name: string
  is_active: boolean
  roles: string[]
  row_version: number
}

export async function authLogin(body: { login_name: string; password: string }): Promise<UserSummary> {
  const { data } = await api.post<UserSummary>('/api/auth/login', body)
  return data
}

export async function authLogout(): Promise<void> {
  await api.post('/api/auth/logout')
}

export async function authFetchMe(): Promise<UserSummary> {
  const { data } = await api.get<UserSummary>('/api/auth/me')
  return data
}

export async function fetchAdminUsers(): Promise<AdminUserListItem[]> {
  const { data } = await api.get<{ items: AdminUserListItem[] }>('/api/admin/users')
  return data.items
}

export async function createAdminUser(body: {
  employee_id: string
  login_name: string
  password: string
  roles: string[]
}): Promise<{ user_id: string; row_version: number; roles: string[] }> {
  const { data } = await api.post('/api/admin/users', body)
  return data
}

export async function updateAdminUser(
  userId: string,
  body: { row_version: number; is_active?: boolean; password?: string },
): Promise<{ user_id: string; row_version: number }> {
  const { data } = await api.put(`/api/admin/users/${userId}`, body)
  return data
}

export async function updateAdminUserRoles(
  userId: string,
  body: { row_version: number; roles: string[] },
): Promise<{ user_id: string; row_version: number; roles: string[] }> {
  const { data } = await api.put(`/api/admin/users/${userId}/roles`, body)
  return data
}

export interface WebhookApiKeyListItem {
  key_id: string
  name: string
  operator_employee_id: string
  expires_at: string | null
  is_active: boolean
  created_by_user_id: string
  created_at: string
  updated_at: string
}

export async function fetchWebhookApiKeys(): Promise<WebhookApiKeyListItem[]> {
  const { data } = await api.get<{ items: WebhookApiKeyListItem[] }>('/api/admin/webhook-api-keys')
  return data.items
}

export async function createWebhookApiKey(body: {
  name: string
  operator_employee_id: string
  expires_at?: string | null
}): Promise<{ key_id: string; api_key: string } & WebhookApiKeyListItem> {
  const { data } = await api.post('/api/admin/webhook-api-keys', body)
  return data
}

export async function updateWebhookApiKey(
  keyId: string,
  body: {
    name?: string
    operator_employee_id?: string
    expires_at?: string | null
    is_active?: boolean
  },
): Promise<WebhookApiKeyListItem> {
  const { data } = await api.put(`/api/admin/webhook-api-keys/${keyId}`, body)
  return data
}

export async function deleteWebhookApiKey(keyId: string): Promise<void> {
  await api.delete(`/api/admin/webhook-api-keys/${keyId}`)
}

export interface NotificationChannelItem {
  channel_id: string
  name: string
  webhook_url: string
  type_ids: string[]
  is_active: boolean
  row_version: number
  created_at: string
  updated_at: string
  updated_by_employee_id: string | null
}

export async function fetchNotificationChannels(): Promise<NotificationChannelItem[]> {
  const { data } = await api.get<{ items: NotificationChannelItem[] }>('/api/notification-channels')
  return data.items
}

export async function createNotificationChannel(body: {
  name: string
  webhook_url: string
  type_ids: string[]
  is_active: boolean
}): Promise<NotificationChannelItem> {
  const { data } = await api.post('/api/notification-channels', body)
  return data
}

export async function updateNotificationChannel(
  channelId: string,
  body: {
    name: string
    webhook_url: string
    type_ids: string[]
    is_active: boolean
    row_version: number
  },
): Promise<NotificationChannelItem> {
  const { data } = await api.put(`/api/notification-channels/${channelId}`, body)
  return data
}

export async function deleteNotificationChannel(channelId: string): Promise<void> {
  await api.delete(`/api/notification-channels/${channelId}`)
}

export async function createMaster(resource: string, body: unknown) {
  const { data } = await api.post(`/api/masters/${resource}`, body)
  return data
}

export async function updateMaster(resource: string, idPath: string, body: unknown) {
  const { data } = await api.put(`/api/masters/${resource}/${idPath}`, body)
  return data
}

export async function fetchMasterDetail(resource: string, idPath: string) {
  const { data } = await api.get(`/api/masters/${resource}/${idPath}`)
  return data
}

export interface UiConfig {
  operator_name: string
  reference_date: string
  reference_date_mode: string
  timezone: string
}

export interface IncidentListItem {
  incident_id: string
  occurred_at: string
  title: string
  status: string
  status_label: string
  severity: string
  response_count: number
  score?: number
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface SearchParams {
  keyword?: string
  occurred_from?: string
  occurred_to?: string
  status?: string[]
  severity?: string[]
  type_id?: string
  page?: number
  page_size?: number
  sort?: string
  initial?: boolean
  quick?: string
  rag?: boolean
}

export async function fetchUiConfig(): Promise<UiConfig> {
  const { data } = await api.get<UiConfig>('/api/config/ui')
  return data
}

export interface LogEntry {
  seq: number
  ts: string
  event: string
  [key: string]: unknown
}

export interface LogsResponse {
  items: LogEntry[]
  next_cursor: number
}

export async function fetchRecentLogs(after = 0): Promise<LogsResponse> {
  const { data } = await api.get<LogsResponse>('/api/logs/recent', { params: { after } })
  return data
}

export async function fetchIncidents(params: SearchParams): Promise<Paginated<IncidentListItem>> {
  const query: Record<string, unknown> = { ...params }
  if (!query.initial) {
    delete query.initial
  }
  delete query.quick
  const { data } = await api.get<Paginated<IncidentListItem>>('/api/incidents', { params: query })
  return data
}

export async function fetchIncidentDetail(id: string) {
  const { data } = await api.get(`/api/incidents/${id}`)
  return data
}

export async function createIncident(body: unknown) {
  const { data } = await api.post('/api/incidents', body)
  return data
}

export async function updateIncident(id: string, body: unknown) {
  const { data } = await api.put(`/api/incidents/${id}`, body)
  return data
}

export async function createResponse(incidentId: string, body: unknown) {
  const { data } = await api.post(`/api/incidents/${incidentId}/responses`, body)
  return data
}

export async function updateResponse(incidentId: string, responseId: string, body: unknown) {
  const { data } = await api.put(`/api/incidents/${incidentId}/responses/${responseId}`, body)
  return data
}

export async function fetchMasters(path: string) {
  const { data } = await api.get(`/api/masters/${path}`)
  return data.items as Array<Record<string, string>>
}

export interface ProcedureListItem {
  procedure_id: string
  title: string
  type_id: string
  usage_count: number
  success_count: number
  success_rate: number | null
  is_active: boolean
  updated_at: string
  score?: number
}

export interface ProcedureSearchParams {
  keyword?: string
  procedure_id?: string
  type_id?: string
  tags?: string
  is_active?: boolean
  page?: number
  page_size?: number
  sort?: string
  rag?: boolean
}

export async function fetchProcedures(params: ProcedureSearchParams): Promise<Paginated<ProcedureListItem>> {
  const { data } = await api.get<Paginated<ProcedureListItem>>('/api/procedures', { params })
  return data
}

export async function fetchProcedureDetail(id: string) {
  const { data } = await api.get(`/api/procedures/${id}`)
  return data
}

export async function createProcedure(body: unknown) {
  const { data } = await api.post('/api/procedures', body)
  return data
}

export async function updateProcedure(id: string, body: unknown) {
  const { data } = await api.put(`/api/procedures/${id}`, body)
  return data
}

export async function fetchProcedureIncidents(procedureId: string) {
  const { data } = await api.get(`/api/procedures/${procedureId}/incidents`)
  return data.items as Array<Record<string, unknown>>
}

export async function fetchIncidentProcedures(incidentId: string) {
  const { data } = await api.get(`/api/incidents/${incidentId}/procedures`)
  return data.items as Array<Record<string, unknown>>
}

export async function applyProcedure(incidentId: string, procedureId: string, notes?: string) {
  const { data } = await api.post(`/api/incidents/${incidentId}/procedures`, {
    procedure_id: procedureId,
    notes,
  })
  return data
}

export async function fetchRecommendedProcedures(incidentId: string) {
  const { data } = await api.get(`/api/incidents/${incidentId}/recommended-procedures`)
  return data as {
    recommended_procedures: Array<Record<string, unknown>>
    similar_incidents: Array<Record<string, unknown>>
  }
}

export interface ProcedureFromIncidentResult {
  preview: Record<string, unknown>
  meta: { source: 'llm' | 'rule_based'; fallback_reason?: string }
}

export async function buildProcedureFromIncident(
  incidentId: string,
): Promise<ProcedureFromIncidentResult> {
  const { data } = await api.post(`/api/incidents/${incidentId}/procedures/from-incident`)
  return data as ProcedureFromIncidentResult
}

export async function updateProcedureSuccess(
  incidentId: string,
  linkId: number,
  wasSuccessful: boolean,
  notes?: string,
) {
  const { data } = await api.patch(`/api/incidents/${incidentId}/procedures/${linkId}`, {
    was_successful: wasSuccessful,
    notes,
  })
  return data
}

export async function unlinkIncidentProcedure(incidentId: string, linkId: number) {
  await api.delete(`/api/incidents/${incidentId}/procedures/${linkId}`)
}

export async function fetchSimilarProcedures(title: string, description: string) {
  const { data } = await api.get('/api/procedures/similar', {
    params: { title, description },
  })
  return data.items as Array<Record<string, unknown>>
}

export function parseSseLines(buffer: string): { events: Array<Record<string, unknown>>; rest: string } {
  const lines = buffer.split('\n')
  const rest = lines.pop() ?? ''
  const events: Array<Record<string, unknown>> = []
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed.startsWith('data:')) continue
    try {
      events.push(JSON.parse(trimmed.slice(5).trim()) as Record<string, unknown>)
    } catch {
      // 不完全な行は次チャンクまで待つ
    }
  }
  return { events, rest }
}

export interface ChatStreamOptions {
  contextIncidentId: string | null
  llmProvider: string
  model: string
}

export interface AiLlmModel {
  provider: string
  model: string
  label: string
}

export interface AiModelsResponse {
  default: { provider: string; model: string }
  items: AiLlmModel[]
  sources: Array<{ provider: string; status: string; error: string | null }>
}

export interface ChatPromptTemplate {
  id: string
  label: string
  message: string
}

export function llmOptionKey(item: { provider: string; model: string }): string {
  return `${item.provider}:${item.model}`
}

export function parseLlmOptionKey(key: string): { provider: string; model: string } {
  const sep = key.indexOf(':')
  if (sep < 0) {
    return { provider: key, model: '' }
  }
  return {
    provider: key.slice(0, sep),
    model: key.slice(sep + 1),
  }
}

export async function fetchAiModels(): Promise<AiModelsResponse> {
  const { data } = await api.get<AiModelsResponse>('/api/ai/models')
  return data
}

export async function fetchChatPromptTemplates(): Promise<ChatPromptTemplate[]> {
  const { data } = await api.get<{ items: ChatPromptTemplate[] }>('/api/chat/prompt-templates')
  return data.items
}

export interface ChatStreamCallbacks {
  onToken: (content: string) => void
  onDone: () => void
  onError: (message: string) => void
  onAbort?: () => void
  onWidget?: (payload: ChatWidgetEvent) => void
  onProposal?: (payload: ChatProposalEvent) => void
  onTriageStarted?: (incidentId: string) => void
  onUsage?: (payload: ChatContextUsage) => void
}

export interface ChatContextUsage {
  promptTokens: number | null
  promptTokensPeak: number | null
  outputTokens: number | null
  outputTokensTotal: number | null
  contextLimit: number | null
  remainingEstimate: number | null
  usageRatio: number | null
  llmCalls: number
}

export interface ChatWidgetOption {
  value: string
  label: string
}

export interface ChatWidgetEvent {
  type: 'widget'
  widget_id: string
  kind: 'text' | 'radio' | 'checkbox' | 'datetime'
  label: string
  required?: boolean
  options?: ChatWidgetOption[]
}

export interface ChatProposalEvent {
  type: 'proposal'
  proposal_id: string
  field: string
  current: unknown
  proposed: unknown
  reason: string
  confidence?: string
}

function mapContextUsage(payload: Record<string, unknown>): ChatContextUsage {
  return {
    promptTokens: payload.prompt_tokens != null ? Number(payload.prompt_tokens) : null,
    promptTokensPeak:
      payload.prompt_tokens_peak != null ? Number(payload.prompt_tokens_peak) : null,
    outputTokens: payload.output_tokens != null ? Number(payload.output_tokens) : null,
    outputTokensTotal:
      payload.output_tokens_total != null ? Number(payload.output_tokens_total) : null,
    contextLimit: payload.context_limit != null ? Number(payload.context_limit) : null,
    remainingEstimate:
      payload.remaining_estimate != null ? Number(payload.remaining_estimate) : null,
    usageRatio: payload.usage_ratio != null ? Number(payload.usage_ratio) : null,
    llmCalls: payload.llm_calls != null ? Number(payload.llm_calls) : 0,
  }
}

function isChatWidgetEvent(payload: unknown): payload is ChatWidgetEvent {
  if (!payload || typeof payload !== 'object') return false
  const p = payload as Record<string, unknown>
  return (
    p.type === 'widget' &&
    typeof p.widget_id === 'string' &&
    typeof p.kind === 'string' &&
    typeof p.label === 'string'
  )
}

function isChatProposalEvent(payload: unknown): payload is ChatProposalEvent {
  if (!payload || typeof payload !== 'object') return false
  const p = payload as Record<string, unknown>
  return (
    p.type === 'proposal' &&
    typeof p.proposal_id === 'string' &&
    typeof p.field === 'string' &&
    typeof p.reason === 'string'
  )
}

export function streamChat(
  messages: Array<{ role: string; content: string }>,
  options: ChatStreamOptions,
  callbacks: ChatStreamCallbacks,
): () => void {
  const { onToken, onDone, onError, onAbort, onWidget, onProposal, onTriageStarted, onUsage } =
    callbacks
  const controller = new AbortController()
  const url = `${apiRoot}/api/chat`
  let finished = false

  const finish = () => {
    if (finished) return
    finished = true
    onDone()
  }

  const abort = () => {
    if (finished) return
    finished = true
    onAbort?.()
  }

  const handleEvent = (payload: Record<string, unknown>) => {
    const type = payload.type
    if (type === 'token') onToken(String(payload.content ?? ''))
    else if (type === 'widget' && onWidget && isChatWidgetEvent(payload)) onWidget(payload)
    else if (type === 'proposal' && onProposal && isChatProposalEvent(payload)) onProposal(payload)
    else if (type === 'triage_started' && onTriageStarted) {
      onTriageStarted(String(payload.incident_id ?? ''))
    } else if (type === 'usage' && onUsage) {
      onUsage(mapContextUsage(payload))
    } else if (type === 'done') finish()
    else if (type === 'error') onError(String(payload.message ?? 'error'))
  }

  fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages,
      context_incident_id: options.contextIncidentId,
      llm_provider: options.llmProvider,
      model: options.model,
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok || !response.body) {
        onError(`HTTP ${response.status}`)
        return
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const { events, rest } = parseSseLines(buffer)
          buffer = rest
          for (const event of events) handleEvent(event)
        }
        if (buffer.trim()) {
          const { events } = parseSseLines(`${buffer}\n`)
          for (const event of events) handleEvent(event)
        }
        finish()
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') {
          abort()
        } else {
          throw err
        }
      } finally {
        reader.releaseLock()
      }
    })
    .catch((err: unknown) => {
      if (err instanceof Error && err.name === 'AbortError') {
        abort()
        return
      }
      if (!finished) onError(String(err))
    })

  return () => controller.abort()
}
