/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { linkIncidentIds, renderChatMarkdown, renderMarkdown } from '@/utils/markdown'

describe('renderMarkdown', () => {
  it('renders bold and list items', () => {
    const html = renderMarkdown('**hello**\n\n1. one\n2. two')
    expect(html).toContain('<strong>hello</strong>')
    expect(html).toContain('<li>')
  })

  it('returns empty string for empty input', () => {
    expect(renderMarkdown('')).toBe('')
  })

  it('renders GFM pipe tables', () => {
    const html = renderMarkdown(
      '| 列A | 列B |\n|---|---|\n| a | b |',
    )
    expect(html).toContain('<table>')
    expect(html).toContain('<th>列A</th>')
    expect(html).toContain('<td>a</td>')
  })

  it('renders headings', () => {
    const html = renderMarkdown('### section title')
    expect(html).toContain('<h3>section title</h3>')
  })
})

describe('linkIncidentIds', () => {
  beforeEach(() => {
    vi.stubEnv('BASE_URL', '/oil/')
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('wraps INC IDs in markdown links', () => {
    expect(linkIncidentIds('see INC-2020-00001 and INC-2020-00002')).toBe(
      'see [INC-2020-00001](/oil/incidents/INC-2020-00001) and [INC-2020-00002](/oil/incidents/INC-2020-00002)',
    )
  })
})

describe('renderChatMarkdown', () => {
  beforeEach(() => {
    vi.stubEnv('BASE_URL', '/oil/')
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('renders incident ID as link', () => {
    const html = renderChatMarkdown('詳細は INC-2020-00001 を参照')
    expect(html).toContain('href="/oil/incidents/INC-2020-00001"')
    expect(html).toContain('INC-2020-00001')
  })

  it('renders procedure ID as link', () => {
    const html = renderChatMarkdown('手順書 PRC-00001 を参照')
    expect(html).toContain('href="/oil/procedures/PRC-00001"')
    expect(html).toContain('PRC-00001')
  })
})
