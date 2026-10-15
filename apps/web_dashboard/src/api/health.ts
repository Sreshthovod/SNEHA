import { apiGet, type RequestOptions } from './client'
import type { HealthResponse, ReadinessResponse } from './types'

export function getHealth(opts?: RequestOptions): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/health', { ...opts, auth: false })
}

/** Readiness returns 503 with a normal body when a dependency is down. */
export function getReadiness(opts?: RequestOptions): Promise<ReadinessResponse> {
  return apiGet<ReadinessResponse>('/health/ready', { ...opts, auth: false, acceptStatuses: [503] })
}
