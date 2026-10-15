import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'

export type AsyncState<T> =
  | { status: 'loading'; data?: T }
  | { status: 'success'; data: T }
  | { status: 'error'; error: ApiError; data?: T }

function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (error instanceof Error && error.message)
    return new ApiError(error.message, { status: null, code: 'client_error' })
  return new ApiError('Something unexpected went wrong. Please try again.', {
    status: null,
    code: 'unknown',
  })
}

/** Load data with an abortable fetcher; `reload()` refetches while keeping the old data. */
export function useAsync<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const fetcherRef = useRef(fetcher)
  useLayoutEffect(() => {
    fetcherRef.current = fetcher
  })

  useEffect(() => {
    const controller = new AbortController()
    setState((s) => ({ status: 'loading', data: s.data }))
    fetcherRef
      .current(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ status: 'success', data })
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setState((s) => ({ status: 'error', error: toApiError(error), data: s.data }))
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  return { ...state, reload }
}

/** Run a user action (save, approve…) with pending + error state. */
export function useAction<A extends unknown[], R>(action: (...args: A) => Promise<R>) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const run = useCallback(
    async (...args: A): Promise<R | undefined> => {
      setPending(true)
      setError(null)
      try {
        return await action(...args)
      } catch (e) {
        setError(toApiError(e))
        return undefined
      } finally {
        setPending(false)
      }
    },
    [action],
  )
  return { run, pending, error, clearError: () => setError(null) }
}
