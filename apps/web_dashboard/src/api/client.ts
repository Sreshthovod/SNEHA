import { config } from '../config/env'
import { reportReachable } from './network'
import { getToken, setToken } from './session'
import type { ErrorResponse } from './types'

export const API_PREFIX = '/api/v1'
const DEFAULT_TIMEOUT_MS = 15000

let baseUrlOverride: string | null = null
/** For integration tests only. */
export function setApiBaseUrl(url: string | null): void {
  baseUrlOverride = url
}
export function apiBaseUrl(): string {
  return baseUrlOverride ?? config.apiBaseUrl
}

/** An error from the API or the network, with a message safe to show in the UI. */
export class ApiError extends Error {
  readonly status: number | null
  readonly code: string
  readonly requestId?: string
  readonly details?: Array<Record<string, unknown>>

  constructor(
    message: string,
    opts: {
      status: number | null
      code: string
      requestId?: string
      details?: Array<Record<string, unknown>>
    },
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = opts.status
    this.code = opts.code
    this.requestId = opts.requestId
    this.details = opts.details
  }

  get isNetwork(): boolean {
    return this.status === null
  }
}

type Query = Record<string, string | number | boolean | null | undefined>

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  form?: FormData
  query?: Query
  responseType?: 'json' | 'blob' | 'none'
  /** Non-2xx statuses whose JSON body should be returned instead of thrown. */
  acceptStatuses?: number[]
  signal?: AbortSignal
  timeoutMs?: number
  baseUrl?: string
  /** Send the stored token (default true). */
  auth?: boolean
}

function isErrorResponse(body: unknown): body is ErrorResponse {
  return (
    typeof body === 'object' &&
    body !== null &&
    'error' in body &&
    typeof (body as ErrorResponse).error?.message === 'string'
  )
}

function buildUrl(base: string, path: string, query?: Query): string {
  const url = `${base}${API_PREFIX}${path}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

/** The single function every API call goes through. */
export async function apiRequest<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const base = opts.baseUrl ?? apiBaseUrl()
  const timeout = AbortSignal.timeout(opts.timeoutMs ?? DEFAULT_TIMEOUT_MS)
  const signal = opts.signal ? AbortSignal.any([opts.signal, timeout]) : timeout
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = opts.auth === false ? null : getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let body: BodyInit | undefined
  if (opts.form) {
    body = opts.form // browser sets the multipart boundary
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }

  let response: Response
  try {
    response = await fetch(buildUrl(base, path, opts.query), {
      method: opts.method ?? 'GET',
      headers,
      body,
      signal,
    })
  } catch (cause) {
    if (opts.signal?.aborted) throw cause
    const timedOut = cause instanceof DOMException && cause.name === 'TimeoutError'
    reportReachable(false)
    throw new ApiError(
      timedOut
        ? 'The SNEHA server took too long to answer. Please try again.'
        : 'Cannot reach the SNEHA server. Check your internet connection.',
      { status: null, code: timedOut ? 'timeout' : 'network_error' },
    )
  }
  reportReachable(true)

  const ok = response.ok || opts.acceptStatuses?.includes(response.status)
  if (ok) {
    if (opts.responseType === 'blob') return (await response.blob()) as T
    if (opts.responseType === 'none' || response.status === 204) return undefined as T
    return (await response.json()) as T
  }

  const errorBody: unknown = await response.json().catch(() => null)
  if (response.status === 401 && token) {
    // Session expired or revoked: sign out everywhere in this tab.
    setToken(null)
  }
  if (isErrorResponse(errorBody)) {
    throw new ApiError(errorBody.error.message, {
      status: response.status,
      code: errorBody.error.code,
      requestId: errorBody.error.request_id ?? undefined,
      details: errorBody.error.details ?? undefined,
    })
  }
  throw new ApiError(`Something went wrong (error ${response.status}). Please try again.`, {
    status: response.status,
    code: 'unexpected_response',
  })
}

/** Backwards-compatible GET helper used by the status card. */
export function apiGet<T>(
  path: string,
  opts: Omit<RequestOptions, 'method' | 'body' | 'form'> = {},
): Promise<T> {
  return apiRequest<T>(path, opts)
}
