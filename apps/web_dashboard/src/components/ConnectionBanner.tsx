import { useEffect, useState } from 'react'
import { isServerReachable, onReachabilityChange } from '../api/network'
import { useSettings } from '../state/settings'

/** Persistent, plain-language notice when the browser is offline or the server is unreachable. */
export function ConnectionBanner() {
  const { t } = useSettings()
  const [online, setOnline] = useState(() => navigator.onLine)
  const [reachable, setReachable] = useState(isServerReachable)

  useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    const unsubscribe = onReachabilityChange(setReachable)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
      unsubscribe()
    }
  }, [])

  if (online && reachable) return null
  return (
    <div className="connection-banner" role="status" aria-live="polite">
      <span aria-hidden="true">⚠</span> {online ? t('state.unreachable') : t('state.offline')}
    </div>
  )
}
