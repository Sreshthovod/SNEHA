import { describe, expect, it, vi } from 'vitest'
import { ApiError, apiGet, apiRequest } from './client'
import { getReadiness } from './health'
import { getToken, setToken } from './session'

const BASE = 'http://api.test'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('apiRequest', () => {
  it('calls the versioned path with query parameters and the bearer token', async () => {
    setToken('tok')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ ok: true }))
    await expect(apiGet('/x', { baseUrl: BASE, query: { from: '2026-10-01', empty: '' } })).resolves.toEqual({ ok: true })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://api.test/api/v1/x?from=2026-10-01')
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer tok')
  })

  it('maps the backend error envelope to ApiError', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse({ error: { code: 'not_found', message: 'Not Found', request_id: 'r-1' } }, 404),
    )
    const error = await apiGet('/missing', { baseUrl: BASE }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, code: 'not_found', requestId: 'r-1' })
  })

  it('a 401 clears the stored token', async () => {
    setToken('tok')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ error: { code: 'unauthorized', message: 'x' } }, 401))
    await expect(apiGet('/x', { baseUrl: BASE })).rejects.toBeInstanceOf(ApiError)
    expect(getToken()).toBeNull()
  })

  it('reports network failures without leaking internals', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(apiGet('/health', { baseUrl: BASE })).rejects.toMatchObject({ code: 'network_error', status: null })
  })

  it('sends multipart without forcing a JSON content type, and returns blobs and 204s', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'f' }, 201))
    const form = new FormData()
    form.append('file', new Blob(['x']), 'a.png')
    await apiRequest('/up', { method: 'POST', form, baseUrl: BASE })
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get('Content-Type')).toBeNull()

    fetchMock.mockResolvedValueOnce(new Response('abc'))
    const blob = await apiRequest<Blob>('/f', { responseType: 'blob', baseUrl: BASE })
    expect(await blob.text()).toBe('abc')

    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await expect(apiRequest('/d', { method: 'DELETE', responseType: 'none', baseUrl: BASE })).resolves.toBeUndefined()
  })

  it('treats readiness 503 as a readable status', async () => {
    const body = { status: 'not_ready', checks: [], server_time: '2026-01-01T00:00:00Z' }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(body, 503))
    await expect(getReadiness({ baseUrl: BASE })).resolves.toEqual(body)
  })
})
