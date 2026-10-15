import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import { getHealth, getReadiness } from '../api/health'
import type { HealthResponse, ReadinessResponse } from '../api/types'

export type BackendStatus =
  | { state: 'checking' }
  | { state: 'online'; health: HealthResponse; readiness: ReadinessResponse }
  | { state: 'degraded'; health: HealthResponse; readiness: ReadinessResponse }
  | { state: 'offline'; message: string }

export function useBackendStatus(): { status: BackendStatus; refresh: () => void } {
  const [status, setStatus] = useState<BackendStatus>({ state: 'checking' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      getHealth({ signal: controller.signal }),
      getReadiness({ signal: controller.signal }),
    ])
      .then(([health, readiness]) => {
        setStatus({ state: readiness.status === 'ready' ? 'online' : 'degraded', health, readiness })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const message =
          error instanceof ApiError ? error.message : 'Unexpected error while contacting the server.'
        setStatus({ state: 'offline', message })
      })
    return () => controller.abort()
  }, [attempt])

  const refresh = useCallback(() => {
    setStatus({ state: 'checking' })
    setAttempt((n) => n + 1)
  }, [])

  return { status, refresh }
}
