import DOMPurify from 'dompurify'
import { markdown } from 'markdown'

const INC_ID_PATTERN = /INC-\d{4}-\d{5}/g
const PRC_ID_PATTERN = /PRC-\d{5}/g

function appBasePath(): string {
  return import.meta.env.BASE_URL.replace(/\/$/, '')
}

export function linkIncidentIds(source: string): string {
  const base = appBasePath()
  return source.replace(INC_ID_PATTERN, (id) => `[${id}](${base}/incidents/${id})`)
}

export function linkProcedureIds(source: string): string {
  const base = appBasePath()
  return source.replace(PRC_ID_PATTERN, (id) => `[${id}](${base}/procedures/${id})`)
}

export function linkEntityIds(source: string): string {
  return linkProcedureIds(linkIncidentIds(source))
}

const MARKDOWN_DIALECT = 'Maruku'

export function renderMarkdown(source: string): string {
  if (!source) return ''
  const html = markdown.toHTML(source, MARKDOWN_DIALECT)
  return DOMPurify.sanitize(html)
}

export function renderChatMarkdown(source: string): string {
  if (!source) return ''
  const linked = linkEntityIds(source)
  const html = markdown.toHTML(linked, MARKDOWN_DIALECT)
  return DOMPurify.sanitize(html)
}
